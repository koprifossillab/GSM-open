"""SCAR 남극 통합 지명사전(Composite Gazetteer of Antarctica, CGA)으로 나가는 문 — 남극 탭의 지명 찾기·이름표 (wetherilli 412).

지명사전은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 호주 남극자료센터(AADC)의 GeoServer WFS(`data.aad.gov.au/geoserver/aadc/ows`). **열쇠가 없다.** 조건은 CC BY —
  인용 꼴은 `CREDIT` 이다(placenames.aq 의 "When citing this dataset…" 예). 지명사전을 운영하는 placenames.aq 에도 같은 것을 내는
  GeoServer 가 있지만, 사람이 읽고 정한 길은 AADC 다
- **화면이 부를 때 상류를 타지 않는다.** 이름 3 만 9 천(쪽마다 4 MB, 넷)을 `manage.py fetch_scar_gazetteer` 가 1 초 간격으로 받아
  지형마다 묶어 `<SCAR_DIR>/cga_place_names.json` 에 줄여 적는다(3 MB 남짓). 찾기·이름표는 이 파일만 읽는다
- 한 줄은 **한 나라 지명사전의 이름 하나**다. 같은 지형은 `scar_common_id` 가 묶는다 — 부스섬은 아르헨티나 `Booth, isla`·벨기에
  `Wandel, Ile`·독일 `Boothinsel`… 일곱. 묶어서 **나라마다의 이름을 다 찾기에 넣고**, 보이는 이름은 `PREFER` 의 차례로 하나 고른다
- 한국 지명사전(KOR)은 27 개이고 **로마자로만 적혀 있다**(Sejong Cape). 한글 이름은 상류에 없다
- 설명(`narrative`)·이름의 내력은 담지 않는다 — 찾기·이름표에 쓰지 않고 파일만 열 배로 커진다
"""
import json
import logging
import time
from pathlib import Path

import requests
from django.conf import settings

from . import arcpoints, usage

log = logging.getLogger(__name__)

WFS = "https://data.aad.gov.au/geoserver/aadc/ows"
#: 행마다 설명이 빠진 판 — 담는 열은 `FIELDS` 로 더 고른다
LAYER = "aadc:SCAR_CGA_PLACE_NAMES_SIMPLIFIED"
FIELDS = ("place_name_mapping", "gazetteer", "feature_type_name", "scar_common_id", "latitude", "longitude")
#: 한 쪽에 받는 이름 수. 4 MB 남짓이라 네 쪽이면 다 온다
PAGE = 10000
PAUSE = 1.0
CREDIT = "SCAR Composite Gazetteer of Antarctica (CC BY)"
SOURCE_URL = "https://placenames.aq/"
#: 카탈로그의 이름표 레이어. 찾기 칸도 같은 이름으로 색인을 고른다(`views.PLACE_SOURCES`)
PLACES = "scar:place_names"
#: 보이는 이름을 고르는 지명사전의 차례 — 한국의 이름이 먼저, 그다음 영어 이름이 많은 넷. 없으면 받은 차례의 첫 이름
PREFER = ("KOR", "USA", "GBR", "AUS", "NZL")
#: 이름표의 생김 — 기지는 점을 찍고(`city`), 물은 파랗게(`lake`). 나머지는 땅의 글씨다 (`map.js` 의 `placeLabelStyle`)
STATIONS = {"Station", "Camp", "AWS", "Building", "Historic"}
WATER = {"Bay", "Water body", "Cove", "Inlet", "Strait", "Channel", "Harbour", "Passage", "Sound", "Anchorage", "Fjord",
         "Bight", "Sea", "Gulf", "Lagoon", "Arm", "Watercourse", "Subglacial lake"}
#: 멀리서도 보일 큰 지형 — 여러 나라가 이름 붙인 것이면 줌 3 부터
LARGE = {"Land", "Coast", "Ice shelf", "Sea", "Plateau", "Range", "Ice sheet", "Continent", "Archipelago", "Gulf",
         "Massif", "Ice stream", "Peninsula", "Subglacial basin", "Territory", "Pole"}


class ScarError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.SCAR_DIR) / "cga_place_names.json"


def available() -> bool:
    return path().exists()


# ── 받기 ─────────────────────────────────────────────────────────────

def _page(start: int) -> dict:
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": LAYER,
              "outputFormat": "application/json", "count": PAGE, "startIndex": start, "sortBy": "gaz_id",
              "propertyName": ",".join(FIELDS)}
    try:
        r = requests.get(WFS, params=params, timeout=(settings.UPSTREAM_TIMEOUT, 300),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("scar", ok=False)
        raise ScarError(f"AADC 에 닿지 못했다: {exc}") from exc
    log.info("scar %s -> %s", r.url, r.status_code)
    if r.status_code != 200:
        usage.record("scar", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise ScarError(f"AADC 가 {r.status_code} 로 답했다")
    try:
        data = r.json()
    except ValueError as exc:
        usage.record("scar", ok=False)
        raise ScarError("AADC 가 GeoJSON 이 아닌 것을 주었다") from exc
    usage.record("scar", ok=True, elapsed=r.elapsed)
    return data


def group(rows: list) -> list:
    """WFS 의 행(속성 dict) → 지형마다 [번호, 경도, 위도, 갈래, [[지명사전, 이름], …]]. 자리는 보일 이름의 행의 것이다."""
    by = {}
    for p in rows:
        cid, name = p.get("scar_common_id"), (p.get("place_name_mapping") or "").strip()
        if cid is None or not name or p.get("latitude") is None or p.get("longitude") is None:
            continue
        by.setdefault(cid, []).append(p)
    out = []
    for cid, names in sorted(by.items()):
        names.sort(key=lambda p: PREFER.index(p.get("gazetteer")) if p.get("gazetteer") in PREFER else len(PREFER))
        main = names[0]
        pairs = [[p.get("gazetteer") or "", p["place_name_mapping"].strip()] for p in names]
        kind = next((p["feature_type_name"] for p in names if p.get("feature_type_name")), "")
        out.append([cid, round(float(main["longitude"]), 5), round(float(main["latitude"]), 5), kind, pairs])
    return out


def download(dest: Path, pause: float = PAUSE) -> dict:
    """이름을 모두 받아 지형마다 묶어 `dest` 에 적는다. {이름 수, 지형 수}."""
    rows, start = [], 0
    while True:
        left = usage.paused()
        if left:
            raise ScarError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
        data = _page(start)
        got = [f.get("properties") or {} for f in data.get("features") or []]
        rows += got
        start += len(got)
        # 쪽 크기로 끝을 가리지 않는다 — 상류가 한 번에 주는 수를 1 만보다 낮게 묶으면 첫 쪽만 받고 끝난다.
        # 전체 수(`numberMatched`)가 있으면 거기까지, 없으면 빈 쪽이 올 때까지
        total = data.get("numberMatched")
        if not got or (isinstance(total, int) and start >= total):
            break
        time.sleep(pause)
    places = group(rows)
    if not places:
        raise ScarError("AADC 가 빈 목록을 주었다")
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps({"source": LAYER, "fetched": time.strftime("%Y-%m-%d"), "license": "CC BY",
                               "names": len(rows), "places": places}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(dest)
    _load.cache_clear()
    place_index_cached.cache_clear()
    label_body.cache_clear()
    return {"names": len(rows), "places": len(places)}


# ── 읽기 ─────────────────────────────────────────────────────────────

def _cached(fn):
    """파일이 바뀌면(다시 받으면) 다시 읽는다 — 고친 때를 열쇠로."""
    memo = {}

    def wrapper():
        stamp = path().stat().st_mtime        # 없으면 FileNotFoundError — 부르는 쪽이 "아직 받지 않았다" 로 옮긴다
        if memo.get("stamp") != stamp:
            memo.update(stamp=stamp, value=fn())
        return memo["value"]
    wrapper.cache_clear = memo.clear
    return wrapper


@_cached
def _load():
    return json.loads(path().read_text(encoding="utf-8"))["places"]


def places() -> list:
    return _load()


def rank(kind: str, nations: int) -> int:
    """이름표의 크기 — 작을수록 멀리서도 뜬다(`rank > 줌 − 1` 이면 숨는다). 이름 붙인 나라가 많을수록 큰 지형이다."""
    if kind in LARGE and nations >= 3:
        return 2
    if kind in STATIONS:
        return 4
    return {0: 8, 1: 8, 2: 7, 3: 6, 4: 5}.get(nations, 4)


def label_kind(kind: str) -> str:
    return "city" if kind in STATIONS else "lake" if kind in WATER else kind


def place_index() -> list:
    """`arcpoints.match_index` 의 색인 — 이름들은 보일 이름과 나라마다의 이름, 곁말은 갈래와 이름 붙인 나라들. 기지를 앞세운다."""
    out = []
    for _, lon, lat, kind, pairs in places():
        shown = tuple(dict.fromkeys(name for _, name in pairs))
        nations = "·".join(dict.fromkeys(g for g, _ in pairs if g))
        side = " · ".join(x for x in (kind, nations) if x)
        out.append((tuple(arcpoints.fold(n) for n in shown), shown, side, lat, lon, 0 if kind in STATIONS else 1))
    return out


#: 찾기마다 2 만 지형의 색인을 다시 짓지 않는다
place_index_cached = _cached(place_index)


def label_features() -> list:
    """이름표 GeoJSON feature 들 — 속성은 `label`·`kind`·`rank`. 한국어판·영어판이 같다(한글 이름이 없다)."""
    out = []
    for cid, lon, lat, kind, pairs in places():
        nations = len({g for g, _ in pairs if g})
        out.append({"type": "Feature", "id": cid, "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"label": pairs[0][1], "kind": label_kind(kind), "rank": rank(kind, nations)}})
    return out


@_cached
def label_body() -> bytes:
    """이름표 덩이(3 MB) — 부를 때마다 다시 짓지 않는다"""
    return json.dumps({"type": "FeatureCollection", "features": label_features()},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "scar", "tag": "SCAR", "title": "남극연구과학위원회"},
]
