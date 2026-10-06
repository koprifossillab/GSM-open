"""얀마옌 지질도 — 노르웨이 극지연구소(NPI)의 1:25만 기반암 지질도를 우리 디스크에서 읽는다.

자료는 `NP_J250_Geologi` (Dallmann 편, 디지털판 2022-12, CC BY 4.0,
data.npolar.no 의 자료 8c7a7c18-eec9-47d9-b86b-1e86938050c8). GeoJSON 셋이다 — 지질 단위(면 306),
분출 열극·용암 전선·칼데라(선 15), 분출 중심·분기공(점 97). devlog 022.

- **상류가 아니라 파일이다.** GeoMAP(018)처럼 서버 디스크의 파일을 읽는다.
  파일은 저장소에 두지 않는다 — 저장소가 공개라서, 받은 것을 다시 내주는
  꼴이 된다(CLAUDE.md "받아온 것의 순위"). 운영은 /srv/GSM/npolar 를 읽기
  전용으로 붙이고, 그 안의 `NP_J250_Geologi/` 에 셋을 둔다 (`settings.NPOLAR_DIR`)
- **타일이 아니라 모양을 통째로 준다.** 면 306 개, 꼭짓점 2 만 8 천이라 한
  덩이(줄이면 수백 KB)로 브라우저에 주고 OpenLayers 가 그린다. 그린란드 정부
  포털의 점(019)과 같은 길(`/points/`)이다 — 점 말고 선·면도 싣는다
- 원본 좌표는 EPSG:25829(ETRS89 / UTM 29N)다. `crs.utm_to_latlon` 으로 위경도로
  옮긴다. pyproj 를 들이지 않는다 (013)
- **옮긴 것은 프로세스가 들고 있다.** 파일의 크기·고친 때가 같으면 다시 읽지
  않는다. 디스크 캐시에 담지 않는다 — 받아온 것이 아니라 우리 파일이라, 읽는
  값(1 초 안쪽)이 담는 값보다 작다. GeoMAP 의 속성·범례와 같은 까닭이다

색은 자료에 든 `rgb` 열을 그대로 쓴다(면). 선·점에는 색 열이 없어, 함께 온
QGIS 스타일(.qml)의 색을 아래 `STYLES` 에 옮겨 적었다 — 여섯 줄이라 뽑는 명령을
두지 않았다.
"""
import json
import logging
import threading
from pathlib import Path

from django.conf import settings

from . import crs, i18n

log = logging.getLogger(__name__)

DATASET = "NP_J250_Geologi"
#: 원본의 좌표계. EPSG:25829 = ETRS89 / UTM 29N
UTM_ZONE = 29
#: 좌표를 이 자리까지만 둔다. 소수 다섯째 자리가 1 m 남짓이다 (얀마옌에서 경도 쪽은 0.4 m)
DIGITS = 5
#: 지도 귀퉁이의 출처. 레이어 셋이 같은 글이라 OpenLayers 가 한 줄로 합친다
SOURCE_URL = "https://data.npolar.no/dataset/8c7a7c18-eec9-47d9-b86b-1e86938050c8"
ATTRIBUTION = ('© <a href="' + SOURCE_URL + '" target="_blank" rel="noopener">'
               "Norsk Polarinstitutt</a> — NP_J250_Geologi (CC BY 4.0)")


class JanMayenError(RuntimeError):
    pass


#: 레이어명 → 파일과 그리는 갈래. 갈래는 `map.js` 의 `legendStyle` 이 읽는다.
LAYERS = {
    "janmayen:units": {"file": "NP_J250_Geologi_f.geojson", "style": "unit"},
    "janmayen:lines": {"file": "NP_J250_Geologi_l.geojson", "style": "line"},
    "janmayen:vents": {"file": "NP_J250_Geologi_p.geojson", "style": "vent"},
}

#: 팝업에 올리는 열과 그 이름. 차례가 팝업의 차례다. 영어는 `i18n.PROP_EN`.
#: 이름·노르웨이어 이름·층서는 속성 값이라 옮기지 않는다(CLAUDE.md "영어판").
LABELS = {
    "name": "이름",
    "navn": "노르웨이어 이름",
    "age": "지질시대",
    "path": "층서 계통",
    "code": "암층 코드",
}

#: geo_code → 지질시대. 자료의 단위 이름에 괄호로 적힌 것을 ICS 이름으로 옮겼다
#: — Inndalen 층은 "(Holocene)", Nordvestkapp 층은 "(latest Pleistocene)",
#: Havhestberget 층은 "(late Pleistocene)". "latest" 는 ICS 에 없는 말이라 둘 다
#: 플라이스토세 후기로 적고, 더 늦은 쪽인 것은 이름이 말한다. 미고결 퇴적물
#: (1020·1090)은 자료가 시대를 적지 않아 비워 둔다 — 지어내지 않는다.
AGES = {
    1160: "홀로세", 1161: "홀로세", 1162: "홀로세", 1163: "홀로세",
    1164: "홀로세", 1165: "홀로세",
    1170: "플라이스토세 후기",
    1180: "플라이스토세 후기",
}

#: 선·점의 그리는 법 — 자료에 딸린 QGIS 스타일(.qml)에서 옮겼다.
#: `shape` 는 점의 모양, `dash` 는 끊은 선(픽셀).
STYLES = {
    502: {"color": "#ed2322", "width": 1.8},                      # 분출 열극
    520: {"color": "#8a8989", "width": 1.6, "dash": [2, 4]},      # 1970·1985 용암 전선 (점 무늬)
    503: {"color": "#111111", "width": 1.6, "dash": [9, 3]},      # 칼데라 (톱니 무늬 대신)
    501: {"color": "#e31a1c", "shape": "triangle"},               # 분출 중심
    531: {"color": "#e31a1c", "shape": "star"},                   # 분기공
}

#: 범례의 차례 — 자료 설명서 그림 2 의 차례(미고결 → 젊은 것 → 옛 것).
LEGEND_ORDER = [1020, 1090, 1160, 1161, 1162, 1163, 1164, 1165, 1170, 1180,
                501, 531, 502, 520, 503]


def knows(name: str) -> bool:
    return name in LAYERS


def data_dir():
    root = settings.NPOLAR_DIR
    return Path(root) / DATASET if root else None


def data_file(name: str):
    root = data_dir()
    return root / LAYERS[name]["file"] if root else None


def available(name: str = None) -> bool:
    names = [name] if name else list(LAYERS)
    for n in names:
        path = data_file(n)
        if path is None or not path.is_file():
            return False
    return True


# ── 읽기·옮기기 ────────────────────────────────────────────────────

def _map_coords(coords, fn):
    """GeoJSON 좌표 배열(깊이는 기하마다 다르다)의 [동, 북] 하나하나에 fn 을."""
    if coords and isinstance(coords[0], (int, float)):
        return fn(coords[0], coords[1])
    return [_map_coords(c, fn) for c in coords]


def _to_lonlat(east, north):
    lat, lon = crs.utm_to_latlon(UTM_ZONE, east, north)
    return [round(lon, DIGITS), round(lat, DIGITS)]


def _rgb(text):
    """"230, 235, 8" → "#e6eb08". 비었거나 이상하면 None."""
    try:
        parts = [int(p) for p in str(text).replace(",", " ").split()[:3]]
    except ValueError:
        return None
    if len(parts) != 3 or not all(0 <= p <= 255 for p in parts):
        return None
    return "#%02x%02x%02x" % tuple(parts)


def _text(value):
    text = " ".join(str(value or "").split())
    return text or None


def pretty_path(path):
    """`Lithostratigraphy-->Quaternary …-->youngest basalt …` → `… › …`.
    맨 앞의 뿌리(`Lithostratigraphy`)는 모든 단위에 같아 뗀다."""
    parts = [p.strip() for p in str(path or "").split("-->") if p.strip()]
    if len(parts) > 1 and parts[0] == "Lithostratigraphy":
        parts = parts[1:]
    return " › ".join(parts) or None


def _code(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def convert(data: dict) -> dict:
    """원본 FeatureCollection(UTM 29N) 하나 → (feature 목록, 범례).

    feature 의 속성은 짧은 열쇠(`LABELS` 의 열쇠와 `color`)로 줄인다. 면이
    300 개라 이름을 되풀이해도 크지 않지만, 팝업에 올릴 것만 싣는다.
    """
    name_of_crs = ((data.get("crs") or {}).get("properties") or {}).get("name", "")
    if name_of_crs and not name_of_crs.endswith("25829"):
        raise JanMayenError(f"좌표계가 EPSG:25829 가 아니다: {name_of_crs}")
    features, legend = [], {}
    for index, feature in enumerate(data.get("features") or []):
        geom = feature.get("geometry") or {}
        if not geom.get("coordinates"):
            continue
        src = feature.get("properties") or {}
        code = _code(src.get("geo_code"))
        props = {
            "name": _text(src.get("Name")),
            "navn": _text(src.get("Navn")),
            "age": AGES.get(code),
            "path": pretty_path(src.get("path")),
            "code": code,
        }
        color = _rgb(src.get("rgb")) or (STYLES.get(code) or {}).get("color")
        if color:
            props["color"] = color
        props = {k: v for k, v in props.items() if v is not None}
        fid = src.get("fid") if "path" in src else src.get("ogc_fid")
        features.append({
            "type": "Feature",
            "id": f"{fid if fid is not None else index}-{index}",
            "geometry": {"type": geom["type"], "coordinates": _map_coords(geom["coordinates"], _to_lonlat)},
            "properties": props,
        })
        if code is not None:
            item = legend.setdefault(code, {"code": code, "label": props.get("name") or str(code),
                                            "count": 0, **(STYLES.get(code) or {})})
            item["count"] += 1
            if color and "color" not in item:
                item["color"] = color
            # 들여쓰기 — 층서 계통의 깊이 (Inndalen 층 밑의 다섯이 한 칸 들어간다)
            if props.get("path"):
                item["depth"] = props["path"].count(" › ")
    rank = {c: i for i, c in enumerate(LEGEND_ORDER)}
    ordered = sorted(legend.values(), key=lambda r: (rank.get(r["code"], 999), r["code"]))
    if ordered and "depth" in ordered[0]:
        low = min(r.get("depth", 0) for r in ordered)
        for r in ordered:
            r["depth"] = r.get("depth", low) - low
    return {"features": features, "legend": ordered}


_memo = {}
_lock = threading.Lock()


def _load(name: str) -> dict:
    """레이어 하나를 읽어 옮긴 것. 파일이 그대로면 들고 있던 것을 준다."""
    path = data_file(name)
    if path is None or not path.is_file():
        raise JanMayenError(f"얀마옌 지질도 파일이 없다: {path}")
    st = path.stat()
    stamp = (str(path), st.st_size, st.st_mtime_ns)
    with _lock:
        hit = _memo.get(name)
        if hit and hit[0] == stamp:
            return hit[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise JanMayenError(f"얀마옌 지질도 파일을 읽지 못했다: {exc}") from exc
        out = convert(data)
        _memo[name] = (stamp, out)
        log.info("얀마옌 %s — %d 개를 위경도로 옮겼다", name, len(out["features"]))
        return out


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이. 꼴은 `grportal.body` 와 같고 `legend` 가 더 붙는다.

    지질시대 값만 영어판에서 옮긴다(`i18n.age_en`) — 나머지 값은 자료 그대로다.
    """
    loaded = _load(name)
    features = loaded["features"]
    if lang == "en":
        features = [dict(f, properties=dict(f["properties"], age=i18n.age_en(f["properties"]["age"])))
                    if "age" in f["properties"] else f for f in features]
    out = {"type": "FeatureCollection", "labels": LABELS, "style": LAYERS[name]["style"],
           "legend": loaded["legend"], "features": features}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "janmayen", "tag": "NPI", "title": "노르웨이 극지연구소"},
]
