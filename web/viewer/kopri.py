"""극지연구소(KOPRI)로 나가는 문 — 암석 시료 DB·KPDC 자료 목록·KPDC 지도 서버.

상류마다 문이 하나라는 규칙(CLAUDE.md)에서 **극지연구소를 한 상류로 친다.**
주소는 셋이지만 같은 기관의 한 자료 센터(KPDC)가 차린 것이다.

- `rock.kopri.re.kr/rock?page=N` — 암석 시료 목록(시료 번호·채집일·지역·암석 갈래·층·지질시대·
  좌표). 한 장에 100 행 남짓, 마지막 장을 넘겨 부르면 **마지막 장을 되풀이해 준다** — 새 시료가
  하나도 없는 장에서 멈춘다 (053)
- `kpdc.kopri.re.kr/search/?c=<묶음>&size=500&page=N` — 자료 목록. 한 행에 uuid·제목이 있다.
  `search/<uuid>` 상세 페이지에 과학 키워드·지역·기간·**공간 범위**(점·면)가 있다. 파일 자체는
  로그인해 신청해야 받는다 — 우리는 **위치와 설명만** 싣고 KPDC 페이지로 잇는다 (055·056)
- `kpdcgeo.kopri.re.kr/geoserver/kpdc/{wms,wfs}` — 남극 기지·해안선·해안선 변화 따위. 3031 을
  그대로 준다 (054·057)

**목록과 상세는 한 번 모아 파일로 둔다** (`manage.py fetch_kopri`, `settings.KOPRI_DIR`).
3 천 쪽을 2 초 간격으로 받는 데 두 시간쯤 걸려, 화면이 부를 때 받을 수 없다. 다음부터는 새로
올라온 것만 받는다. 파일이 없으면 그 레이어에 "자료가 없다" 가 뜰 뿐 뷰어는 돈다.
"""
import html as htmlmod
import json
import logging
import math
import re
import ssl
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import requests.adapters
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 쪽과 쪽 사이에 쉬는 초. 한 번 모으는 일이라 서두르지 않는다 (devlog 010)
PAUSE = 2.0
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS` 와 같다)
DIGITS = 5
ATTRIBUTION = "© 극지연구소 KPDC"
KPDC_HOME = "https://kpdc.kopri.re.kr/"
ROCK_HOME = "https://rock.kopri.re.kr/rock"


class KopriError(RuntimeError):
    pass


def _get(url: str, params: dict = None, *, timeout: int = None):
    try:
        r = requests.get(url, params=params, timeout=timeout or max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("kopri", ok=False)
        raise KopriError(f"극지연구소에 닿지 못했다: {exc}") from exc
    log.info("kopri %s -> %s", r.url, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("kopri", ok=r.status_code == 200, blocked=blocked, elapsed=r.elapsed)
    if r.status_code != 200:
        raise KopriError(f"극지연구소가 받지 않았다 (status={r.status_code})")
    return r


def _text(fragment: str) -> str:
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# ── 암석 시료 (053) ──────────────────────────────────────────────────

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
ROCK_COLUMNS = ("sample", "date", "region", "rocktype", "strat", "age", "coord")


def parse_rock_page(page: str) -> list:
    """목록 한 장 → 행들. 칸이 일곱 개인 행만 받는다."""
    rows = []
    for tr in _ROW.findall(page):
        cells = [_text(c) for c in _CELL.findall(tr)]
        if len(cells) >= len(ROCK_COLUMNS) and cells[0]:
            rows.append(dict(zip(ROCK_COLUMNS, cells)))
    return rows


def harvest_rock(pause: float = PAUSE, max_pages: int = 100, say=None) -> list:
    """암석 시료 목록을 끝까지. 새 시료가 하나도 없는 장에서 멈춘다 — 상류가 마지막 장을
    되풀이해 주기 때문이다(한 번 모를 때 200 장을 불렀다, 053)."""
    seen, out = set(), []
    for page in range(max_pages):
        if page:
            time.sleep(pause)
        rows = parse_rock_page(_get(settings.KOPRI_ROCK_URL, {"page": page}).text)
        fresh = [r for r in rows if r["sample"] not in seen]
        if say:
            say(f"암석 시료 {page} 장: {len(rows)} 행, 새 것 {len(fresh)}")
        if not fresh:
            break
        for row in fresh:
            seen.add(row["sample"])
            out.append(row)
    else:
        log.warning("암석 시료: %d 장을 넘겨도 끝나지 않아 멈췄다", max_pages)
    return out


def rock_coord(text: str):
    """"-74.4773,165.3399" → (위도, 경도). 없거나 0,0 이면 None."""
    try:
        lat, lon = (float(v) for v in str(text).split(",")[:2])
    except ValueError:
        return None
    if (lat == 0 and lon == 0) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


#: 암석 갈래 — 상류의 표기가 들쭉날쭉하다(`Igneous`·`igneous`·`IGNEOUS`). 접어서 가른다
ROCK_CLASSES = (
    ("sedimentary", ("sedimentary", "sediment"), "퇴적암", "#e0a526"),
    ("volcanic", ("volcanic",), "화산암", "#d7301f"),
    ("plutonic", ("igneous", "plutonic"), "화성암·심성암", "#c51b7d"),
    ("metamorphic", ("metamorphic",), "변성암", "#2c7fb8"),
    ("other", (), "그 밖·미상", "#8c8c8c"),
)


def rock_class(text: str) -> str:
    folded = (text or "").strip().lower()
    for code, words, _, _ in ROCK_CLASSES:
        if folded in words:
            return code
    return "other"


# ── KPDC 자료 목록 (055·056) ────────────────────────────────────────

_ITEM = re.compile(r'<tr class="item result-item" data-id="([0-9a-f-]{36})"(.*?)</tr>', re.S)
_ENTRY = re.compile(r'<span class="entry_id">\[([^\]]+)\]</span>')


def parse_list_page(page: str) -> list:
    """목록 한 장 → [{uuid, id, title}]."""
    out = []
    for uuid, rest in _ITEM.findall(page):
        title = re.search(r'data-title="([^"]*)"', rest)
        entry = _ENTRY.search(rest)
        out.append({"uuid": uuid, "id": entry.group(1) if entry else "",
                    "title": " ".join(htmlmod.unescape(title.group(1)).split()) if title else ""})
    return out


def list_collection(collection: str, pause: float = PAUSE, size: int = 500, max_pages: int = 30,
                    say=None) -> list:
    """묶음(`KPDC`·`KoreaMet`) 하나의 목록 전체. 목록은 가볍다 — 500 행이 한 장이다."""
    seen, out = set(), []
    url = settings.KOPRI_KPDC_URL.rstrip("/") + "/search/"
    for page in range(max_pages):
        if page:
            time.sleep(pause)
        rows = parse_list_page(_get(url, {"page": page, "size": size, "c": collection}).text)
        fresh = [r for r in rows if r["uuid"] not in seen]
        if say:
            say(f"{collection} 목록 {page} 장: {len(rows)} 행, 새 것 {len(fresh)}")
        if not fresh:
            break
        for row in fresh:
            seen.add(row["uuid"])
            out.append(row)
    return out


_DL = re.compile(r"<dt>\s*(.*?)\s*</dt>\s*<dd[^>]*>(.*?)</dd>", re.S)
_BLOCK = re.compile(r'<p class="point-header">\s*([A-Za-z]+)\s*</p>(.*?)</ul>', re.S)
_LATLON = re.compile(r"lat:</span>\s*(-?[\d.]+)\s*,\s*<span[^>]*>\s*lon:</span>\s*(-?[\d.]+)")


def parse_detail(page: str) -> dict:
    """상세 페이지 → 우리 것. 공간 범위는 [(갈래, [(위도, 경도), …]), …] 이다.

    KPDC 의 `POLYGON` 은 대개 **모서리 두 점**(사각형)이다 — 셋 이상이면 그대로 면으로 둔다.
    """
    fields = {}
    for key, value in _DL.findall(page):
        key = _text(key)
        if key and key not in fields:
            fields[key] = value
    shapes = []
    for kind, body in _BLOCK.findall(page):
        pts = [(float(a), float(b)) for a, b in _LATLON.findall(body)]
        if pts:
            shapes.append([kind.upper(), pts])

    def one(key):
        return _text(fields.get(key, ""))

    def keyword(key):
        # "EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > …" — 여럿이면 줄마다 하나
        raw = fields.get(key, "")
        parts = [_text(p) for p in re.split(r"<br\s*/?>|</li>|\n\s*\n", raw)]
        return [re.sub(r"\s*>\s*", " > ", p) for p in parts if p]

    # 운석은 KoreaMet 의 기록으로 잇는 고리가 `Dataset` 둘째 칸에 있다 — 페이지에서 곧장 찾는다
    link = re.search(r'href="(https?://koreamet\.kopri\.re\.kr/[^"]+)"', page)
    return {
        "doi": one("DOI"),
        "keywords": keyword("Science Keyword"),
        "location": keyword("Location"),
        "period": one("Research period"),
        "paleo": one("Paleo age") or one("Paleo"),
        "platform": one("Platforms"),
        "instrument": one("Instruments"),
        "shapes": shapes,
        **({"link": link.group(1)} if link else {}),
    }


def fetch_detail(uuid: str) -> dict:
    return parse_detail(_get(settings.KOPRI_KPDC_URL.rstrip("/") + "/search/" + uuid).text)


def detail_url(uuid: str) -> str:
    return "https://kpdc.kopri.re.kr/search/" + uuid


# ── 모아 둔 파일 ─────────────────────────────────────────────────────

def data_dir() -> Path:
    return Path(settings.KOPRI_DIR)


def load(name: str) -> dict:
    """`rock`·`kpdc` 파일 하나. 없으면 빈 것."""
    path = data_dir() / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save(name: str, data: dict) -> None:
    """다 쓴 뒤 바꿔 끼운다 — 모으다 멈춰도 앞의 파일이 깨지지 않는다."""
    path = data_dir() / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def available(name: str) -> bool:
    return (data_dir() / f"{name}.json").exists()


def mtime(name: str) -> float:
    try:
        return (data_dir() / f"{name}.json").stat().st_mtime
    except FileNotFoundError:
        return 0.0


# ── 화면에 내는 것 ────────────────────────────────────────────────────
#
# 암석 시료·운석·KPDC 자료는 모아 둔 파일에서, 기지는 KPDC 지도 서버의 WFS 에서 온다. 넷 다
# 한 꼴(`style: class`)로 브라우저에 간다 — feature 마다 `code`, 덩이에 `legend`
# ([{code, label, color, shape, count}]). 브라우저는 그 표 하나로 그리고 범례를 적는다.
# 팝업 이름(`labels`)·범례 이름은 한국어이고 영어판이면 브라우저가 `T()` 로 옮긴다.

#: 레이어 → 무엇을 어디서. `box` 는 (서, 남, 동, 북) — 이 안의 것만 싣는다
LAYERS = {
    "kopri:rock_antarctica": {"from": "rock", "box": (-180, -90, 180, -50)},
    "kopri:rock_svalbard": {"from": "rock", "box": (5, 74, 36, 81.5)},
    "kopri:rock_greenland": {"from": "rock", "box": (-75, 59, -10, 84)},
    "kopri:meteorites": {"from": "kpdc", "collection": "KoreaMet", "box": (-180, -90, 180, -50)},
    "kopri:stations": {"from": "wfs", "types": ("antarctic_human_facilities", "antarctic_human_facilities_k")},
    # 아라온호 항적 — `fetch_araon` 이 매시간 쌓은 것 (koprifossillab 006). 탭마다 이름이 하나라 둘이지만 같은 것이다.
    # `kopri:araon` 은 온 지구 화면이 부르는 이름이다 — 카탈로그(DB)에는 없다
    "kopri:araon": {"from": "araon"},
    "kopri:araon_antarctica": {"from": "araon"},
    "kopri:araon_arctic_ocean": {"from": "araon"},
}

#: KPDC 자료는 주제(GCMD 과학 키워드)마다 한 레이어다 — 레이어 패널에서 켜고 끄는 것이 곧 고르기다.
#: (코드, 한국어, 색, 키워드에 이것이 들면). 위에서부터 먼저 맞는 것
TOPICS = (
    ("sediment", "해양 퇴적물·코어", "#8c510a", ("MARINE SEDIMENTS", "SEDIMENT")),
    ("solid", "고체지구", "#c51b7d", ("SOLID EARTH",)),
    ("paleo", "고기후", "#e08214", ("PALEOCLIMATE",)),
    ("cryo", "빙권", "#2c7fb8", ("CRYOSPHERE", "GLACIERS", "ICE SHEETS", "SEA ICE", "SNOW")),
    ("ocean", "해양", "#1b9e77", ("OCEANS",)),
    ("atmo", "대기", "#7570b3", ("ATMOSPHERE", "CLIMATE INDICATORS")),
    ("bio", "생물", "#66a61e", ("BIOSPHERE", "BIOLOGICAL CLASSIFICATION", "AGRICULTURE")),
    ("other", "그 밖", "#6b6b6b", ()),
)
#: 북극은 탭마다 한 벌이다 — 스발바르·그린란드는 암석 시료와 같은 네모다 (075). 북극해 탭은 두 탭을 뺀
#: 북위 50° 너머 전부다 — 축치해·베링해 항해, 캐나다 케임브리지베이, 시베리아·스칸디나비아 관측소 (076)
ARCTIC_BOXES = {"svalbard": LAYERS["kopri:rock_svalbard"]["box"],
                "greenland": LAYERS["kopri:rock_greenland"]["box"]}
ARCTIC_OCEAN_BOX = (-180, 50, 180, 90)
#: 북극해의 넓은 범위 한계(경도, 위도). 아라온 항해 백여 건이 같은 기본 네모(북위 60–80°, 160°E–150°W —
#: 경도 50°·위도 20°, 남극의 한계에 딱 걸린다)를 적어, 겹쳐 칠하면 축치해가 한 덩이로 덮인다. 그 네모는 "어디서"
#: 를 말하지 않으므로 뺀다 — 항적(선·점)이 있는 자료는 그대로 나온다 (076)
ARCTIC_OCEAN_WIDE = (45, 15)
for _code, _label, _color, _words in TOPICS:
    LAYERS[f"kopri:kpdc_{_code}"] = {"from": "kpdc", "collection": "KPDC", "topic": _code,
                                     "box": (-180, -90, 180, -50)}
    for _region, _box in ARCTIC_BOXES.items():
        LAYERS[f"kopri:kpdc_{_code}_{_region}"] = {"from": "kpdc", "collection": "KPDC", "topic": _code,
                                                   "box": _box}
    # `outside` — 이 네모 안의 점은 제 탭이 있어 여기 싣지 않는다. `wide` — 넓은 범위의 한계를 좁힌다
    LAYERS[f"kopri:kpdc_{_code}_arctic_ocean"] = {"from": "kpdc", "collection": "KPDC", "topic": _code,
                                                  "box": ARCTIC_OCEAN_BOX,
                                                  "outside": tuple(ARCTIC_BOXES.values()),
                                                  "wide": ARCTIC_OCEAN_WIDE}

#: 이보다 넓은 범위(경도 60° 또는 위도 20° 넘게)는 그리지 않는다 — 남극 전체·남빙양 전체를 덮는
#: 위성 자료가 대륙을 네모로 덮어 다른 것을 가린다. 그런 자료는 KPDC 에서 찾는 편이 낫다
WIDE_LON, WIDE_LAT = 60, 20

#: KPDC 지도 서버의 3031 WMS — 레이어명 → 상류 레이어
WMS = {
    "kopri:coast_change": "antarctic_coastline_coast_change",
    "kopri:lakes": "antarctic_water_lakes",
    "kopri:streams": "antarctic_water_streams",
    "kopri:moraines": "antarctic_topography_moraines",
    # 2026-09-30 에 더했다 (wetherilli 095). `_group` 은 KPDC 가 축척마다 고해상·중해상 판을 바꿔 주는 묶음이다
    "kopri:rock_outcrops": "antarctic_topography_rock_group",
    "kopri:contours": "antarctic_topography_contours_group",
    "kopri:historic": "antarctic_human_historic",
    "kopri:arctic_depth_contours": "arctic_topography_bathymetric_contours",
    "kopri:greenland_ice_contours": "arctic_topography_ice_contours",
}

#: 3031 이 아닌 레이어의 받을 투영. 북극 것은 KPDC 가 3995 로만 적어 두지만 GeoServer 가 3413 으로도 그려 준다
#: — 우리 북극 화면이 3413 이라 그대로 받는다 (wetherilli 095)
WMS_PROJECTION = {
    "kopri:arctic_depth_contours": "EPSG:3413",
    "kopri:greenland_ice_contours": "EPSG:3413",
}


def wms_projection(name: str) -> str:
    return WMS_PROJECTION.get(name, "EPSG:3031")

LABELS = {
    "rock": {"no": "시료 번호", "type": "암석 갈래", "strat": "지층", "age": "지질시대",
             "date": "채취일", "region": "지역"},
    "kpdc": {"title": "제목", "id": "자료 번호", "kw": "과학 키워드", "where": "지역", "period": "연구 기간",
             "paleo": "고기후 시기", "gear": "장비", "page": "KPDC 자료 페이지", "doi": "DOI"},
    "met": {"title": "운석", "id": "자료 번호", "period": "찾은 날", "where": "지역",
            "page": "KPDC 자료 페이지", "db": "운석 기록 (KoreaMet)"},
    "araon": {"name": "배", "time": "시각 (UTC)", "sog": "속력 (kn)", "cog": "침로 (°)", "hdg": "선수방위 (°)",
              "temp": "기온 (°C)", "humi": "습도 (%)", "from": "첫 기록", "to": "마지막 기록", "fixes": "자리 수",
              "day": "날짜 (하루 창, UTC)", "harvested": "받은 때"},
    "wfs": {"name": "기지", "nation": "나라", "type": "갈래", "status": "운영", "opened": "처음 연 해",
            "winter": "월동 인원", "peak": "여름 최대 인원", "alt": "고도", "other": "다른 이름", "notes": "비고"},
}
LINKS = ("page", "doi", "db")

#: KPDC 지도 서버 속성 → 팝업 이름 (073). 여기 없는 열(편집자·SCAR 갈래 번호·참고 번호 따위)은 보이지 않는다.
#: 차례가 팝업의 차례다. 날짜(`revdate`)는 두 꼴(19570101 · 13/01/1992)로 와서 그대로 둔다
WMS_PROPS = {
    "kopri:coast_change": (("year", "연도"), ("source_inf", "그린 근거"), ("reliabilit", "신뢰도"),
                           ("revdate", "고친 날")),
    "kopri:lakes": (("surface", "갈래"), ("bedtype", "바닥")),
    "kopri:streams": (("imw_sheet", "도폭 (IMW)"), ("source", "출처"), ("sourcedate", "출처 날짜"),
                      ("revdate", "고친 날")),
    "kopri:moraines": (("surface", "갈래"), ("subsurface", "밑"), ("source", "출처")),
    "kopri:rock_outcrops": (("type", "갈래"), ("surface", "표면"), ("source", "출처"), ("revdate", "고친 날")),
    "kopri:contours": (("height", "높이 (m)"), ("bedtype", "바닥"), ("surface", "표면"), ("certainty", "확실성"),
                       ("sourcedate", "출처 날짜")),
    "kopri:historic": (("no", "HSM 번호"), ("name", "이름"), ("descriptio", "설명"), ("proposing_", "제안국"),
                       ("managing_c", "관리국"), ("lat", "위도"), ("lon", "경도")),
    "kopri:arctic_depth_contours": (("depth", "수심 (m)"),),
    "kopri:greenland_ice_contours": (("contour", "높이 (m)"),),
}

STATION_CLASSES = (
    ("korea", "대한민국 기지", "#c8102e", "star"),
    ("year", "상주 기지", "#1f4e79", "square"),
    ("season", "하계 기지", "#6fa8dc", "square"),
    ("other", "그 밖 시설", "#8c8c8c", "dot"),
)


def knows(name: str) -> bool:
    return name in LAYERS


def knows_file(name: str) -> bool:
    return name in LAYERS and LAYERS[name]["from"] != "wfs"


def knows_points(name: str) -> bool:
    """점 레이어의 문(`views._POINT_DOORS`)이 받는 것 — WFS 로 통째로 받는 기지."""
    return name in LAYERS and LAYERS[name]["from"] == "wfs"


def knows_wms(name: str) -> bool:
    return name in WMS


def source_url(name: str) -> str:
    return ROCK_HOME if LAYERS.get(name, {}).get("from") == "rock" else KPDC_HOME


def file_of(name: str) -> str:
    return LAYERS[name]["from"]


def _inside(box, lat, lon) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def _covers(spec, lat, lon) -> bool:
    """레이어가 이 점을 싣나 — `box` 안이고 `outside` 의 어느 네모에도 들지 않는다."""
    return _inside(spec["box"], lat, lon) and not any(_inside(b, lat, lon) for b in spec.get("outside", ()))


def _pt(lat, lon):
    return [round(lon, DIGITS), round(lat, DIGITS)]


def _age(value: str, lang: str) -> str:
    from . import i18n
    return value if lang == "en" else i18n.age_ko(value)


def rock_features(rows: list, box, lang: str = "ko") -> list:
    out = []
    for row in rows:
        ll = rock_coord(row.get("coord"))
        if not ll or not _inside(box, *ll):
            continue
        props = {"code": rock_class(row.get("rocktype")), "no": row["sample"],
                 "type": row.get("rocktype"), "strat": row.get("strat"),
                 "age": _age(row.get("age"), lang) if row.get("age") not in ("", "?", "Unknown") else "",
                 "date": row.get("date"), "region": row.get("region")}
        out.append({"type": "Feature", "id": row["sample"], "geometry": {"type": "Point", "coordinates": _pt(*ll)},
                    "properties": {k: v for k, v in props.items() if v}})
    return out


def topic_of(keywords: list) -> str:
    text = " ".join(keywords or []).upper()
    for code, _, _, words in TOPICS:
        if any(w in text for w in words):
            return code
    return "other"


def _box_ring(a, b, step: float = 1.0) -> list:
    """모서리 두 점 → 경위선을 따라 촘촘히 이은 고리. 3031 에서 위선이 휜다 —
    네 점만 이으면 곧은 선이 되어 범위가 틀린다. 경도 폭이 180° 를 넘으면 날짜변경선을 넘는
    것으로 본다."""
    (lat1, lon1), (lat2, lon2) = a, b
    south, north = min(lat1, lat2), max(lat1, lat2)
    west, east = min(lon1, lon2), max(lon1, lon2)
    if east - west > 180:
        west, east = east, west + 360
    n = max(2, int(math.ceil((east - west) / step)) + 1)
    lons = [west + (east - west) * i / (n - 1) for i in range(n)]
    m = max(2, int(math.ceil((north - south) / step)) + 1)
    lats = [south + (north - south) * i / (m - 1) for i in range(m)]
    wrap = lambda lon: lon - 360 if lon > 180 else lon
    ring = ([_pt(south, wrap(x)) for x in lons] + [_pt(y, wrap(east)) for y in lats[1:]]
            + [_pt(north, wrap(x)) for x in reversed(lons[:-1])] + [_pt(y, wrap(west)) for y in reversed(lats[:-1])])
    return ring


def _lon_span(lons: list) -> float:
    """경도들을 덮는 가장 짧은 호의 폭 — 360 에서 가장 큰 빈틈을 뺀다. 날짜변경선을 넘는 베링해 네모
    (160°E–150°W)는 50°, 한 위선을 빙 두른 고리(-180·-90·0·90·180)는 270° 다. 앞 판은 양 끝만 보아
    그 고리를 0° 로 읽었다 (076)."""
    xs = sorted(x % 360 for x in lons)
    gaps = [b - a for a, b in zip(xs, xs[1:])] + [xs[0] + 360 - xs[-1]]
    return 360 - max(gaps)


def _shape_geometry(kind: str, pts: list, wide=None):
    """KPDC 의 공간 범위 하나 → GeoJSON 기하. 넓은 범위면 None. `wide` 는 (경도, 위도) 한계."""
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    if kind == "POINT":
        if len(pts) == 1:
            return {"type": "Point", "coordinates": _pt(*pts[0])}
        return {"type": "MultiPoint", "coordinates": [_pt(*p) for p in pts]}
    wide_lon, wide_lat = wide or (WIDE_LON, WIDE_LAT)
    if _lon_span(lons) > wide_lon or max(lats) - min(lats) > wide_lat:
        return None
    if kind in ("LINE", "LINESTRING"):
        return {"type": "LineString", "coordinates": [_pt(*p) for p in pts]}
    if len(pts) == 2:
        return {"type": "Polygon", "coordinates": [_box_ring(*pts)]}
    ring = [_pt(*p) for p in pts]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def kpdc_features(records: dict, spec: dict, lang: str = "ko") -> tuple:
    """모아 둔 KPDC 자료 → (feature 목록, 넓어서 뺀 자료 수)."""
    out, wide = [], 0
    meteor = spec["collection"] == "KoreaMet"
    for uuid, rec in records.items():
        if rec.get("c") != spec["collection"]:
            continue
        if not meteor and topic_of(rec.get("keywords")) != spec["topic"]:
            continue
        shapes = [(kind, pts) for kind, pts in rec.get("shapes") or []
                  if any(_covers(spec, lat, lon) for lat, lon in pts)]
        if not shapes:
            continue
        doi = rec.get("doi") or ""
        if doi and not doi.startswith("http"):
            doi = "https://doi.org/" + doi
        props = {"code": "met" if meteor else spec["topic"], "title": rec.get("title"), "id": rec.get("id"),
                 "where": " · ".join(rec.get("location") or []), "period": rec.get("period"),
                 "page": detail_url(uuid)}
        if meteor:
            props["db"] = rec.get("link")
        else:
            props.update(kw=" · ".join(rec.get("keywords") or []), paleo=rec.get("paleo"),
                         gear=" · ".join(v for v in (rec.get("platform"), rec.get("instrument")) if v), doi=doi)
        props = {k: v for k, v in props.items() if v}
        drawn = 0
        for index, (kind, pts) in enumerate(shapes):
            geom = _shape_geometry(kind, pts, spec.get("wide"))
            if geom is None:
                continue
            drawn += 1
            out.append({"type": "Feature", "id": f"{uuid}#{index}", "geometry": geom, "properties": props})
        if not drawn:
            wide += 1
    return out, wide


def legend_for(name: str, features: list) -> list:
    spec = LAYERS[name]
    counts = {}
    for f in features:
        code = f["properties"].get("code")
        counts[code] = counts.get(code, 0) + 1
    if spec["from"] == "rock":
        table = [(c, label, color, "dot") for c, _, label, color in ROCK_CLASSES]
    elif spec["from"] == "wfs":
        table = list(STATION_CLASSES)
    elif spec["from"] == "araon":
        table = list(ARAON_CLASSES)
    elif spec.get("collection") == "KoreaMet":
        table = [("met", "운석 발견 지점", "#4d4d4d", "diamond")]
    else:
        table = [(c, label, color, "dot") for c, label, color, _ in TOPICS if c == spec["topic"]]
    return [{"code": c, "label": label, "color": color, "shape": shape, "count": counts.get(c, 0)}
            for c, label, color, shape in table if counts.get(c)]


def _labels_of(name: str) -> dict:
    spec = LAYERS[name]
    if spec["from"] == "kpdc":
        return LABELS["met" if spec["collection"] == "KoreaMet" else "kpdc"]
    return LABELS[spec["from"]]


def _pack(name: str, features: list, **extra) -> bytes:
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": _labels_of(name),
                       "links": list(LINKS), "legend": legend_for(name, features), **extra,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def file_body(name: str, lang: str = "ko") -> bytes:
    """모아 둔 파일에서 레이어 하나. 파일이 없으면 FileNotFoundError."""
    spec = LAYERS[name]
    if spec["from"] == "araon":
        if not araon_available():
            raise FileNotFoundError(ARAON_FILE)
        return _pack(name, araon_features(araon_track(), araon_past()))
    if not available(spec["from"]):
        raise FileNotFoundError(spec["from"])
    data = load(spec["from"])
    if spec["from"] == "rock":
        return _pack(name, rock_features(data.get("rows") or [], spec["box"], lang),
                     harvested=data.get("harvested"))
    features, wide = kpdc_features(data.get("records") or {}, spec, lang)
    return _pack(name, features, wide=wide, harvested=data.get("harvested"))


# ── 기지 — KPDC 지도 서버의 WFS (054) ────────────────────────────────

def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 — 받는 상류 레이어가 바뀌면 받아 둔 것을 쓰지 않는다."""
    return "wfs|" + ",".join(LAYERS[name]["types"]) + "|v1"


def _station(feature: dict):
    p = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") != "Point" or len(coords) < 2:
        return None
    status = (p.get("current_st") or "").lower()
    code = ("korea" if p.get("nationa_01") == "KOR" else "year" if "year" in status
            else "season" if "season" in status else "other")
    props = {"code": code, "name": p.get("facility_n"), "nation": p.get("national_p"),
             "type": p.get("facilty_ty"), "status": p.get("current_st"), "opened": p.get("first_open"),
             "winter": p.get("winter_pop"), "peak": p.get("peak_popul"), "alt": p.get("alt_masl"),
             "other": p.get("cga_name_o"), "notes": p.get("notes")}
    return {"type": "Feature", "id": p.get("un_locode") or feature.get("id"),
            "geometry": {"type": "Point", "coordinates": [round(float(coords[0]), DIGITS),
                                                          round(float(coords[1]), DIGITS)]},
            "properties": {k: v for k, v in props.items() if v not in (None, "")}}


def fetch(name: str, pause: float = 1.0) -> list:
    """기지를 통째로 — 상류 레이어 둘(COMNAP 100 곳, 한국 기지 2 곳). 같은 기지는 한 번만."""
    out, seen = [], set()
    for index, layer in enumerate(LAYERS[name]["types"]):
        if index:
            time.sleep(pause)
        r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wfs",
                 {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": f"kpdc:{layer}",
                  "outputFormat": "application/json", "srsName": "EPSG:4326"})
        try:
            data = r.json()
        except ValueError as exc:
            raise KopriError("KPDC 지도 서버가 JSON 이 아닌 것을 주었다") from exc
        for feature in data.get("features") or []:
            row = _station(feature)
            if row is None:
                continue
            key = row["properties"].get("name")
            if key in seen:
                # 한국 기지 레이어가 뒤에 온다 — 같은 이름이면 그쪽으로 덮는다
                out = [f for f in out if f["properties"].get("name") != key]
            seen.add(key)
            out.append(row)
    return out


def body(name: str, features_json: bytes) -> bytes:
    return _pack(name, json.loads(features_json))


# ── 해안선 따위 — KPDC 지도 서버의 3031 WMS (057) ────────────────────

_PASS = ("bbox", "width", "height", "srs", "crs", "format", "transparent", "version", "styles")


def get_map(params: dict):
    """`GetMap` 을 그대로 넘긴다 — 레이어명만 상류 것으로. (바이트, content-type)."""
    layer = WMS.get((params.get("layers") or "").split(",")[0].strip())
    if not layer:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    sent = {k: v for k, v in params.items() if k in _PASS}
    sent.update(service="WMS", request="GetMap", layers=f"kpdc:{layer}")
    sent.setdefault("styles", "")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms", sent, timeout=settings.UPSTREAM_TIMEOUT)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise KopriError(f"그림이 아닌 것이 왔다 (type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` — GeoServer 가 JSON 으로 준다. KIGAM 과 같은 꼴(`features`)로."""
    layer = WMS.get((params.get("query_layers") or params.get("layers") or "").split(",")[0].strip())
    if not layer:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    sent = {k: v for k, v in params.items() if k in _PASS + ("i", "j", "x", "y", "feature_count")}
    sent.update(service="WMS", request="GetFeatureInfo", layers=f"kpdc:{layer}", query_layers=f"kpdc:{layer}",
                info_format="application/json")
    sent.setdefault("styles", "")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms", sent, timeout=settings.UPSTREAM_TIMEOUT)
    try:
        data = r.json()
    except ValueError as exc:
        raise KopriError("KPDC 지도 서버가 JSON 이 아닌 것을 주었다") from exc
    names = WMS_PROPS.get((params.get("query_layers") or params.get("layers") or "").split(",")[0].strip(), ())
    return {"features": [{"id": f.get("id", ""), "properties": _wms_props(f.get("properties") or {}, names)}
                         for f in data.get("features") or []]}


def _wms_props(props: dict, names) -> dict:
    """상류 열 → 팝업 이름. 빈 값은 뺀다. 이름표가 없는 레이어면 상류 것을 그대로(id 따위만 빼고)."""
    if not names:
        return {k: v for k, v in props.items() if k not in ("id", "fid", "gid")}
    return {label: props[key] for key, label in names if props.get(key) not in (None, "")}


def get_legend(layer: str):
    name = WMS.get(layer)
    if not name:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms",
             {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": f"kpdc:{name}"}, timeout=settings.UPSTREAM_TIMEOUT)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise KopriError("범례가 그림이 아니다")
    return r.content, ctype


# ── 아라온호 위치 ─────────────────────────────────────────────────────
#
# 극지연구소 누리집의 "아라온호 위치"(infra/030303) 가 싣는 `live.kopri.re.kr/araon/` 한 쪽. 배가 보낸 마지막
# 자리를 판(대시보드)에 적어 둔다 — 시각(UTC)·위경도·속력·침로·선수방위·기온·습도. 그 밑의 항적(`latlngs`)은
# 시각이 없어 받지 않는다. 지난 자리는 이 쪽이 지워 버리므로 **매시간 받아 우리가 쌓는다**(`fetch_araon`).
#
# 그 서버는 인증서 체인에서 중간 인증서(Sectigo DV R36)를 빼고 보낸다 — 브라우저는 스스로 채우지만 파이썬은
# 못 채워 멈춘다. 검증을 끄지 않고, 그 중간 인증서(`data/certs/`)를 시스템 꾸러미에 더해 제대로 검증한다.

ARAON_URL = "https://live.kopri.re.kr/araon/"
ARAON_PAGE = "https://www.kopri.re.kr/kopri/html/infra/030303.html"
ARAON_FILE = "araon.jsonl"
LIVE_INTERMEDIATE = settings.REPO_DIR / "data" / "certs" / "sectigo_dv_r36.pem"
#: 풍속 칸이 비면 16 비트 최댓값(0xFFFF)의 1/10 이 찍혀 나온다
_NO_VALUE = 6553.5

_FIELD = re.compile(r"<b>\s*([A-Z]+)[^<]*</b>\s*:?\s*([^<]*)")


class _LiveAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=settings.CA_BUNDLE or None)
        ctx.load_verify_locations(str(LIVE_INTERMEDIATE))
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


def parse_araon(page: str, now: datetime = None) -> dict:
    """판에서 마지막 자리 하나. 판이 없거나 위경도가 없으면 `KopriError`.

    날짜에 해가 없다("Thu Oct 01") — 지금에서 거꾸로 세어 요일이 맞는 해를 고른다.
    """
    start = page.find('id="dashboard_show"')
    if start < 0:
        raise KopriError("아라온호 위치 판이 없다")
    fields = {}
    for key, value in _FIELD.findall(page[start:start + 6000]):
        fields.setdefault(key, htmlmod.unescape(value).strip())
    try:
        lat, lon = float(fields["LAT"]), float(fields["LON"])
    except (KeyError, ValueError) as exc:
        raise KopriError("아라온호 위경도를 읽지 못했다") from exc
    if not (-90 <= lat <= 90 and -180 <= lon <= 360):
        raise KopriError(f"아라온호 위경도가 이상하다 ({lat}, {lon})")
    if lon > 180:                               # 날짜변경선을 넘어 360 까지 적는다
        lon -= 360
    when = _araon_time(fields.get("DATE", ""), fields.get("TIME", ""), now or datetime.now(timezone.utc))
    row = {"time": when, "lat": round(lat, DIGITS), "lon": round(lon, DIGITS)}
    for key, name in (("SOG", "sog"), ("COG", "cog"), ("HDG", "hdg"), ("TEMP", "temp"), ("HUMI", "humi"),
                      ("WIND", "wind")):
        match = re.match(r"-?[\d.]+", fields.get(key, ""))
        if match and float(match.group()) != _NO_VALUE:
            row[name] = float(match.group())
    direction = re.search(r"\b([NESW]{1,3})$", fields.get("WIND", ""))
    if "wind" in row and direction:
        row["wind_dir"] = direction.group(1)
    return row


def _araon_time(date: str, clock: str, now: datetime) -> str:
    parts = date.split()
    if len(parts) != 3:
        raise KopriError(f"아라온호 시각을 읽지 못했다 ({date} {clock})")
    for year in (now.year, now.year - 1, now.year + 1):
        try:
            when = datetime.strptime(f"{year} {parts[1]} {parts[2]} {clock.replace('UTC', '').strip()}",
                                     "%Y %b %d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:                      # 2 월 29 일이 없는 해, 또는 읽지 못한 꼴
            continue
        if when.strftime("%a") == parts[0][:3] and when <= now + timedelta(days=1):
            return when.isoformat(timespec="minutes").replace("+00:00", "Z")
    raise KopriError(f"아라온호 시각을 읽지 못했다 ({date} {clock})")


def _araon_page(nday: int, nhour: int) -> str:
    session = requests.Session()
    session.mount("https://live.kopri.re.kr/", _LiveAdapter())
    try:
        r = session.get(ARAON_URL, params={"nday": nday, "nhour": nhour}, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                        verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("kopri", ok=False)
        raise KopriError(f"아라온호 위치에 닿지 못했다: {exc}") from exc
    log.info("kopri %s -> %s", r.url, r.status_code)
    usage.record("kopri", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise KopriError(f"아라온호 위치가 받지 않았다 (status={r.status_code})")
    return r.text


def fetch_araon() -> dict:
    return parse_araon(_araon_page(3, 1))


# ── 지난 항적 — 날짜는 하루 단위 (koprifossillab 009) ─────────────────
#
# 위치 판은 지난 날들(`nday`, 365 까지)의 항적을 `nhour` 간격으로 준다 — 하지만 **자리마다 시각이 없다.** 365 일을
# 한 시간 간격으로 물으면 8 760 이 아니라 4 869 자리가 왔다(2026-10-01) — 빈 시간·빈 날이 많아 순서로 시각을 짐작할
# 수 없다. 그런데 판은 메뉴에 없는 `nday`(1, 2, 3 …)도 받는다. `nday` 를 1 부터 늘려 가며 자리 수를 세면, 새것부터
# 적힌 목록에서 **N 일 전 하루에 든 자리가 몇 번째부터 몇 번째까지인지** 나온다. 그래서 자리마다 "며칠 전"(`ago`)을
# 붙인다 — 그날 안의 시각은 모른다. 매시간 쌓는 기록(`araon.jsonl`)과는 섞지 않는다.
#
# 판이 하루마다 가장 오래된 날을 지우므로 한 번 떠 두는 것이다(`fetch_araon --past`). 365 번을 천천히 부른다.
# 받는 사이에 새 자리가 붙으면 목록의 앞이 한두 자리 밀린다 — 그만큼 비켜 맞춘다. 다시 뜨면 덮지 않고 날짜를
# 붙인 파일로 남긴다.

ARAON_PAST_FILE = "araon_past.json"
ARAON_PAST_DAYS = 365
_LATLNGS = re.compile(r"var\s+latlngs\s*=\s*(\[.*?\]);", re.S)


def _latlngs(page: str) -> list:
    """판의 `latlngs` 그대로 — [[위도, 경도], …] 새것부터."""
    m = _LATLNGS.search(page)
    if not m:
        raise KopriError("아라온호 항적(latlngs)이 없다")
    try:
        return json.loads(m.group(1))
    except ValueError as exc:
        raise KopriError("아라온호 항적을 읽지 못했다") from exc


def _lonlat(pair) -> list:
    lat, lon = pair
    return [round(lon - 360 if lon > 180 else lon, DIGITS), round(lat, DIGITS)]


def _counted(base: list, page: list) -> int:
    """`nday` 를 줄여 받은 목록이 `base` 의 앞 몇 자리인가. 그 사이 새 자리가 붙었으면 그만큼 비켜 맞춘다."""
    if not page:
        return 0
    for shift in range(3):
        if page[shift:shift + 1] == base[:1]:
            n = len(page) - shift
            if page[shift:] == base[:n]:
                return n
            break
    raise KopriError("아라온호 항적이 받는 사이에 바뀌었다 — 다시 떠야 한다")


def fetch_araon_past(nday: int = ARAON_PAST_DAYS, pause: float = 2.0, say=None) -> dict:
    harvested = datetime.now(timezone.utc)
    page = _araon_page(nday, 1)
    base = _latlngs(page)
    latest = parse_araon(page)
    counts = []                                 # counts[n-1] — `nday=n` 에 든 자리 수 (새것부터 센)
    for n in range(1, nday + 1):
        time.sleep(pause)
        counts.append(_counted(base, _latlngs(_araon_page(n, 1))))
        if say and n % 30 == 0:
            say(f"  {n} 일 — {counts[-1]} 자리")
    points = []
    for i, pair in enumerate(base):             # i 번째(새것부터) 자리는 `nday` 가 처음 그것을 품는 날
        ago = next((n for n, c in enumerate(counts, 1) if c > i), None)
        points.append(_lonlat(pair) + [ago])
    points.reverse()                            # 오래된 것부터
    return {"harvested": harvested.isoformat(timespec="minutes").replace("+00:00", "Z"),
            "source": ARAON_URL, "nday": nday, "nhour": 1, "latest": latest, "counts": counts,
            "points": points}


def araon_past() -> dict:
    path = data_dir() / ARAON_PAST_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_araon_past(data: dict) -> Path:
    """처음이면 `araon_past.json`, 이미 있으면 날짜를 붙여 곁에 둔다 — 먼저 뜬 것이 더 오래 전까지 간다."""
    path = data_dir() / ARAON_PAST_FILE
    if path.exists():
        path = data_dir() / f"araon_past_{data['harvested'][:10].replace('-', '')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return path


def araon_track() -> list:
    """쌓아 둔 자리를 시각 순으로. 없으면 빈 것."""
    path = data_dir() / ARAON_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def append_araon(row: dict) -> bool:
    """새 시각이면 한 줄 보탠다. 배가 아직 새 자리를 안 보냈으면(같은 시각) 보태지 않고 False."""
    path = data_dir() / ARAON_FILE
    last = araon_track()[-1:] or [{}]
    if last[0].get("time") == row["time"]:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True


# ── 아라온호 항적 — 화면에 내는 것 (koprifossillab 006) ───────────────
#
# 쌓은 자리를 잇는 선과 마지막 자리 하나. 지역 탭(남극·북극해)은 `style: class` 의 점 레이어로, 온 지구 화면은
# 같은 GeoJSON 을 점묶음처럼 그린다. 선은 두 곳에서 끊는다 —
# - **날짜변경선** — 베링해·척치해에서 179°E → 179°W 로 넘는다. 이으면 지구를 반 바퀴 가로지른다. ±180° 에
#   자리를 끼워 넣어 두 조각으로 나눈다
# - **오래 빈 사이** — 보고가 `ARAON_GAP` 넘게 끊기면(위성 통신이 끊긴 극지·정비) 그 사이를 곧게 잇지 않는다.
#   곧은 선이 땅을 가로질러 거기를 지난 것처럼 보이게 된다

ARAON_CLASSES = (
    ("last", "아라온호 마지막 자리", "#e4002b", "star"),
    ("track", "아라온호 항적", "#ffb000", "line"),
    ("past", "지난 항적 (날짜는 하루 단위)", "#ffb000", "dash"),
)
#: 지난 항적은 이웃한 두 자리가 이보다 멀면 끊는다 — 그날 안의 빈 시간이 얼마인지 몰라, 한 시간에 갈 수 있는 거리
#: (15 kn ≈ 28 km)의 몇 배를 넘으면 그 사이를 지나지 않은 것으로 본다. 하루가 통째로 빠져도 끊는다
ARAON_PAST_GAP_KM = 200
ARAON_GAP = timedelta(hours=12)
#: 브라우저가 들고 있을 초 — 매시간 한 자리가 붙으므로 하루(다른 점 레이어)는 길다
ARAON_MAX_AGE = 600


def _when(row: dict) -> datetime:
    return datetime.fromisoformat(row["time"].replace("Z", "+00:00"))


def _km(a, b) -> float:
    (x0, y0), (x1, y1) = a, b
    p0, p1 = math.radians(y0), math.radians(y1)
    h = math.sin((p1 - p0) / 2) ** 2 + math.cos(p0) * math.cos(p1) * math.sin(math.radians(x1 - x0) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def _split_lines(points: list, broken) -> list:
    """[[경도, 위도], …] → 선 조각들. `broken(i)` 가 참이면 i-1 과 i 사이를 잇지 않는다. 날짜변경선에서는 ±180 에
    자리를 끼워 넣어 끊는다 — 이으면 지구를 반 바퀴 가로지른다."""
    lines, line = [], []
    for i, here in enumerate(points):
        if i == 0 or broken(i):
            if line:
                lines.append(line)
            line = [here]
            continue
        (x0, y0), (x1, y1) = points[i - 1], here
        if abs(x1 - x0) > 180:                  # 경도를 이어 붙여 ±180 의 위도를 낸다
            east = 180.0 if x0 > 0 else -180.0
            x1u = x1 + 360 if x0 > 0 else x1 - 360
            t = (east - x0) / (x1u - x0)
            y = round(y0 + t * (y1 - y0), DIGITS)
            line.append([east, y])
            lines.append(line)
            line = [[-east, y]]
        line.append(here)
    if line:
        lines.append(line)
    return [l for l in lines if len(l) >= 2]


def _araon_lines(rows: list) -> list:
    return _split_lines([[r["lon"], r["lat"]] for r in rows],
                        lambda i: _when(rows[i]) - _when(rows[i - 1]) > ARAON_GAP)


def _araon_past_days(past: dict) -> list:
    """지난 항적 → 하루마다 (며칠 전, 선 조각들, 자리 수). 앞날과 이어지면 앞날의 마지막 자리에서 시작한다."""
    points = [p for p in past.get("points") or [] if len(p) > 2 and p[2]]
    out, i = [], 0
    while i < len(points):
        ago = points[i][2]
        j = i
        while j < len(points) and points[j][2] == ago:
            j += 1
        day = [p[:2] for p in points[i:j]]
        if i and points[i - 1][2] == ago + 1:   # 바로 앞날 — 이어 그린다
            day.insert(0, points[i - 1][:2])
        lines = _split_lines(day, lambda k: _km(day[k - 1], day[k]) > ARAON_PAST_GAP_KM)
        if lines:
            out.append((ago, lines, j - i))
        i = j
    return out


def _day_window(harvested: str, ago: int) -> str:
    """N 일 전 하루 — 받은 때에서 거꾸로 센 24 시간 창. 판이 그렇게 자른다."""
    end = datetime.fromisoformat(harvested.replace("Z", "+00:00")) - timedelta(days=ago - 1)
    fmt = lambda t: t.strftime("%Y-%m-%d %H:%MZ")
    return f"{fmt(end - timedelta(days=1))} ~ {fmt(end)}"


def araon_available() -> bool:
    return (data_dir() / ARAON_FILE).exists() or (data_dir() / ARAON_PAST_FILE).exists()


#: 고를 수 있는 기간(일) — 앞의 것이 기본. 화면은 이 안의 조각만 그리고 오래된 것일수록 옅게 한다 (koprifossillab 017)
ARAON_PERIODS = (30, 182, 365)


def _days_since(when: datetime, now: datetime) -> float:
    return round(max(0.0, (now - when).total_seconds() / 86400), 2)


def _araon_track_days(rows: list, now: datetime) -> list:
    """시각 있는 항적 → 하루마다(지금에서 거꾸로 센 24 시간) (며칠 전, 선 조각들, 자리 수). 앞날과 이어지면(빈 사이가
    `ARAON_GAP` 안쪽) 앞날의 마지막 자리에서 시작한다 — 날 사이가 끊겨 보이지 않게."""
    out, i = [], 0
    bucket = lambda r: int((now - _when(r)).total_seconds() // 86400)
    while i < len(rows):
        day = bucket(rows[i])
        j = i
        while j < len(rows) and bucket(rows[j]) == day:
            j += 1
        part = rows[i:j]
        if i and _when(rows[i]) - _when(rows[i - 1]) <= ARAON_GAP:
            part = [rows[i - 1]] + part
        lines = _araon_lines(part)
        if lines:
            mid = _when(part[0]) + (_when(part[-1]) - _when(part[0])) / 2
            out.append((_days_since(mid, now), lines, j - i, part[0]["time"], part[-1]["time"]))
        i = j
    return out


def araon_features(rows: list, past: dict = None, now: datetime = None) -> list:
    """항적을 하루 한 조각으로 — 조각마다 `ago`(지금에서 며칠 전, 그 조각의 가운데). 화면이 기간(`ARAON_PERIODS`)으로 거르고
    오래된 것일수록 옅게 한다. 마지막 자리는 `ago` 0 이다."""
    now = now or datetime.now(timezone.utc)
    out = []
    if past and past.get("harvested"):
        since = _days_since(datetime.fromisoformat(past["harvested"].replace("Z", "+00:00")), now)
        for ago, lines, fixes in _araon_past_days(past):
            out.append({"type": "Feature", "id": f"araon-past-{ago}",
                        "geometry": {"type": "MultiLineString", "coordinates": lines},
                        "properties": {"code": "past", "name": "ARAON", "day": _day_window(past["harvested"], ago),
                                       "fixes": fixes, "harvested": past.get("harvested"),
                                       "ago": round(since + ago - 0.5, 2)}})
    if not rows:
        return out
    for ago, lines, fixes, first, last_time in _araon_track_days(rows, now):
        out.append({"type": "Feature", "id": f"araon-track-{first}",
                    "geometry": {"type": "MultiLineString", "coordinates": lines},
                    "properties": {"code": "track", "name": "ARAON", "from": first, "to": last_time, "fixes": fixes,
                                   "ago": ago}})
    last = rows[-1]
    props = {"code": "last", "name": "ARAON", "ago": 0}
    props.update({k: last[k] for k in ("time", "sog", "cog", "hdg", "temp", "humi") if k in last})
    out.append({"type": "Feature", "id": "araon-last", "geometry": {"type": "Point", "coordinates": [last["lon"], last["lat"]]},
                "properties": props})
    return out
