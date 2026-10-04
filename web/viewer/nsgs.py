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
LAYERS = {"nsgs:11": (11, None, True), "nsgs:9": (9, 8, False)}


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
    usage.record("nsgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
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
