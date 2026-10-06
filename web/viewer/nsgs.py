"""노바스코샤 지질조사(Nova Scotia Department of Natural Resources and Renewables, Geoscience and Mines Branch)로 나가는 문 —
노바스코샤 기반암 1:50만 (Keppie 2000, ME 2000-1) (wetherilli 235).

- 주소: `fletcher.novascotia.ca/arcgis/rest/services/geoscience/bedrockgeologyprovscale_new/MapServer` (ArcGIS REST). 열쇠가 없다.
  **WMS 를 열어 두지 않았다** — 멕시코(`sgm.py`)처럼 화면의 WMS 변수를 REST `export`·`identify` 로 옮긴다. 화면의 투영(3978·3857)을
  `bboxSR` 로 그대로 넘긴다 — 상류가 다시 그린다
- 레이어 — `11` 기반암 단위, `9` 단층(상류 minScale 200만, 화면 줌 8 남짓부터)
- 속성은 identify — 단위 이름·서열·상위 단위·시대(ICS 영어 `AGE_DESC`)·짧은 설명
- 조건: 디지털 판(DP ME 43)의 사용 허락 — "NR&R 을 출처로 밝히면 원본 그대로든 일부든 가공물의 일부든 쓰고 나눌 수 있다".
  출처 "Nova Scotia Department of Natural Resources and Renewables"
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "nsgs:"
ATTRIBUTION = ('<a href="https://novascotia.ca/natr/meb/download/dp043.asp" target="_blank" rel="noopener">'
               "Nova Scotia Dept. of Natural Resources and Renewables</a> (Keppie 2000, ME 2000-1)")
#: 레이어 → (REST 번호, 처음 그리는 화면 줌, 누르기가 되나)
LAYERS = {"nsgs:11": (11, None, True), "nsgs:9": (9, 9, False)}      # 단층은 1:200만보다 넓으면 그리지 않는다 — 격자 줌 8(화면 9)부터 (wetherilli 310)


class NsgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def queryable(name: str) -> bool:
    return name in LAYERS and LAYERS[name][2]


def _one(params: dict):
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise NsgsError(f"모르는 레이어다: {names}")
    return names[0], LAYERS[names[0]][0]


def _get(path: str, params: dict):
    left = usage.paused()
    if left:
        raise NsgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{settings.NSGS_URL.rstrip('/')}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("nsgs", ok=False)
        raise NsgsError(f"노바스코샤에 닿지 못했다: {exc}") from exc
    log.info("NSGS %s -> %s", r.url, r.status_code)
    usage.record("nsgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _view(params: dict):
    """WMS 변수 → (EPSG 번호, 범위 네 수, 너비, 높이)."""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if not crs.startswith("EPSG:"):
        raise NsgsError(f"EPSG 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise NsgsError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise NsgsError("범위·크기가 맞지 않다")
    return crs[5:], bbox, width, height


def get_map(params: dict):
    _, layer = _one(params)
    sr, bbox, width, height = _view(params)
    r = _get("export", {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": sr, "imageSR": sr, "size": f"{width},{height}",
                        "format": "png32", "transparent": "true", "dpi": "96", "layers": f"show:{layer}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NsgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise NsgsError("노바스코샤 범례는 따로 받지 않는다")


#: 보는 범위의 범례를 세우는 레이어 (wetherilli 357) — REST 의 칠하기 규칙(`AV_LEGEND` 225 칸)에 보는 범위의 통계 질의를 댄다
EXTENT_LEGENDS = ("nsgs:11",)
LEGEND_SPAN = 8.0          # 주 전체(가로 6° 남짓)가 든다


def renderer(name: str) -> dict:
    """칠하기 규칙 — `{값: [이름, "#rrggbb"]}`. 값은 `AV_LEGEND`("15350North Mountain Formation: …"), 이름은 규칙의 label"""
    if name not in EXTENT_LEGENDS:
        raise NsgsError("범례가 없는 레이어다")
    r = _get(str(LAYERS[name][0]), {"f": "json"})
    try:
        rd = r.json()["drawingInfo"]["renderer"]
    except (ValueError, KeyError, TypeError) as exc:
        raise NsgsError("칠하기 규칙이 없다") from exc
    out = {}
    for info in rd.get("uniqueValueInfos") or []:
        color = (info.get("symbol") or {}).get("color")
        if color and color[3:4] != [0]:
            out[str(info.get("value")).strip()] = [str(info.get("label") or "").strip(), "#" + "".join(f"{int(v):02x}" for v in color[:3])]
    if not out:
        raise NsgsError("칠하기 규칙이 없다")
    return out


def extent_legend(name: str, bbox: tuple, rules: dict, lang: str = "ko") -> list:
    """보는 범위 `(서, 남, 동, 북)`(위경도)에 든 단위 `[{"lithology", "color", "age", "count"}]`, 면이 많은 것부터. 퀸즐랜드(`austates._gsq_legend`)의 꼴"""
    import json
    r = _get(f"{LAYERS[name][0]}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": "AV_LEGEND,AGE_DESC",
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise NsgsError("범례 통계가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise NsgsError(f"범례 통계를 받지 못했다 (status={r.status_code})")
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = str(a.get("AV_LEGEND") or "").strip()
        if value not in rules:
            continue
        label, color = rules[value]
        age = str(a.get("AGE_DESC") or "").strip()
        row = rows.setdefault(value, {"symbol": "", "lithology": label, "color": color, "swatch": "",
                                      "age": i18n.age_ko(age) if lang == "ko" and age else age, "count": 0})
        row["count"] += int(a.get("n") or 0)
    return sorted(rows.values(), key=lambda row: -row["count"])


def get_feature_info(params: dict) -> dict:
    name, layer = _one(params)
    if not queryable(name):
        return {"features": []}
    sr, bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise NsgsError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get("identify", {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": sr, "layers": f"all:{layer}",
                          "tolerance": "2", "mapExtent": ",".join(repr(v) for v in bbox), "imageDisplay": f"{width},{height},96",
                          "returnGeometry": "false", "f": "json"})
    if r.status_code != 200:
        raise NsgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise NsgsError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"nsgs.{n}", "properties": res.get("attributes") or {}}
                         for n, res in enumerate(data.get("results") or [])]}


def friendly(props: dict, lang: str = "ko") -> dict:
    """단위 이름·상위 단위·서열은 영어 그대로, 시대만 옮긴다."""
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    age = v("AGE_DESC")
    rows = (("기호", v("TXT_LABEL")), ("지층", v("UNIT_NAME")), ("상위 단위", v("PARENT")), ("서열", v("UNIT_RANK")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("암석", v("UNIT_DESC")))
    return {k: x for k, x in rows if x and x.lower() not in ("none", "null")}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "nsgs", "tag": "NSNRR", "title": "노바스코샤 자연자원·재생에너지부", "relay": True, "projected": True, "globe": True},
]
