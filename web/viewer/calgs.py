"""캘리포니아 지질조사소(CGS)로 나가는 문 — 캘리포니아 지질도 1:75만(2010 판) (wetherilli 231).

- 주소: `gis.conservation.ca.gov/server/rest/services/CGS/Geologic_Map_of_California/MapServer` (ArcGIS REST). 열쇠가 없다.
  **WMSServer 가 없다**(FeatureServer 만) — 말레이시아(`jmg.py`)·멕시코(`sgm.py`)처럼 화면이 보내는 WMS 변수를 REST `export`·`identify` 로 옮긴다.
  상류 이름 `cgs` 는 남아공(Council for Geoscience)이 이미 쓴다 — 그래서 `calgs`
- **미국 탭은 3978 이다**(wetherilli 210) — 서버의 타일 캐시(3857)는 쓰지 못하고, export 에 `bboxSR`·`imageSR` 3978 을 준다
  (주 전체 512² 1.3 초, 2026-10-04). 3D 는 3857 로 같은 길을 간다
- **레이어는 하나다** — export 가 `layers` 를 무시한다(`show:`·`hide:`·`include:` 셋 다 같은 그림, 2026-10-04). 타일 캐시가 있는 서비스라
  늘 인쇄도 그대로 — 암석 갈래 면·경계·단층에, 1:14만–1:60만에서는 지명·주향 주석까지 그린다. 그래서 면과 선을 따로 켜고 끄지 못한다
- 면은 **1:14만보다 크게는 그리지 않는다**(maxScale) — 줌 12 까지 받고 그 위는 화면이 늘린다(`MAX_ZOOM`, 인도네시아와 같다)
- 속성은 identify JSON — `PTYPE`(기호)·`GENERAL_LITHOLOGY`·`AGE`·`DESCRIPTION`(영어)
- 범례: 면은 REST 범례(기호 54 칸)에 이름·시대가 없어, 면의 값(기호·암상·시대)을 한 번 모아(`returnDistinctValues`) 붙여 목록으로 낸다
  (`list/legend/`). 뒤에 경계·단층의 칸을 잇는다
- 조건: © California Geological Survey. 공개 오픈데이터 포털에 올라 있으나 조건 문구는 읽지 않았다 — **밖에 열기 전에 사람이 읽는다**.
  CORS 는 Origin 을 되비춘다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "calgs:"
ATTRIBUTION = ('<a href="https://www.conservation.ca.gov/cgs" target="_blank" rel="noopener">© California Geological Survey</a> — '
               "Geologic Map of California 1:750,000 (2010)")
#: 우리 이름 → (보일 REST 번호들 — 상류가 무시하지만 적어 둔다, 누를 REST 번호)
LAYERS = {"calgs:geology": ((12, 6, 9), 12)}
LEGEND_LAYERS = tuple(LAYERS)
#: 면이 이 줌까지만 그려진다 — 상류 maxScale 1:14만
MAX_ZOOM = 12
LEGEND_MAX_AGE = 30 * 86400
_CRS = {"EPSG:3857": "3857", "EPSG:900913": "3857", "EPSG:3978": "3978"}


class CalgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise CalgsError(f"모르는 레이어다: {names}")
    return names[0]


def _base() -> str:
    return f"{settings.CALGS_URL.rstrip('/')}/rest/services/CGS/Geologic_Map_of_California/MapServer"


def _get(path: str, params: dict):
    left = usage.paused()
    if left:
        raise CalgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{_base()}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("calgs", ok=False)
        raise CalgsError(f"CGS 에 닿지 못했다: {exc}") from exc
    log.info("CGS(캘리포니아) %s -> %s", r.url, r.status_code)
    usage.record("calgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _view(params: dict):
    """WMS 변수 → (wkid, 범위 네 수, 너비, 높이). 화면은 3978(미국·캐나다·북미 탭) 또는 3857(3D)로 묻는다"""
    sr = _CRS.get(str(params.get("crs") or params.get("srs") or "").upper())
    if not sr:
        raise CalgsError(f"3978·3857 로만 묻는다: {params.get('crs') or params.get('srs')}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise CalgsError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise CalgsError("범위·크기가 맞지 않다")
    return sr, bbox, width, height


def get_map(params: dict):
    shown = LAYERS[_one(params)][0]
    sr, bbox, width, height = _view(params)
    r = _get("export", {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": sr, "imageSR": sr,
                        "size": f"{width},{height}", "format": "png32", "transparent": "true", "dpi": "96",
                        "layers": "show:" + ",".join(str(i) for i in shown), "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise CalgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    layer = LAYERS[_one(params)][1]
    sr, bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise CalgsError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get("identify", {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": sr,
                          "layers": f"all:{layer}", "tolerance": "1", "mapExtent": ",".join(repr(v) for v in bbox),
                          "imageDisplay": f"{width},{height},96", "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise CalgsError("속성이 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise CalgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": [{"id": f"rock_types.{n}", "properties": x.get("attributes") or {}}
                         for n, x in enumerate(data.get("results") or [])][:1]}


def get_legend(layer: str):
    raise CalgsError("그림 범례 대신 목록 범례(`legend_rows`)를 쓴다")


def _cached(key_name: str, fetch) -> list:
    key = tilecache.key_text("calgs-legend", key_name)
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is None:
        held = json.dumps(fetch()).encode("utf-8")
        tilecache.put(key, held, ".json")
    return json.loads(held)


def _json(r) -> dict:
    try:
        data = r.json()
    except ValueError as exc:
        raise CalgsError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise CalgsError(f"REST 오류 (status={r.status_code})")
    return data


def legend_rows(layer: str) -> list:
    """암석 갈래 면의 칸 — REST 범례(기호 54 칸)에 이름·시대가 없어, 면의 값(기호·암상·시대)을 한 번 모아 붙인다. 뒤에 경계·단층의 칸을 잇는다"""
    if layer not in LEGEND_LAYERS:
        raise CalgsError(f"범례가 없는 레이어다: {layer}")
    swatches = _cached("swatches", lambda: arcwms.legend_list(_json(_get("legend", {"f": "json"})), layer_ids=(7, 8, 10, 11, 12)))
    swatch = {}
    for label, uri in swatches:
        swatch.setdefault(label, uri)
    units = _cached("units", lambda: [f.get("attributes") or {} for f in _json(_get("12/query", {
        "where": "1=1", "outFields": "PTYPE,GENERAL_LITHOLOGY,AGE", "returnDistinctValues": "true",
        "returnGeometry": "false", "f": "json"})).get("features") or []])
    seen, rows = set(), []
    for a in sorted(units, key=lambda a: str(a.get("PTYPE") or "")):
        symbol = str(a.get("PTYPE") or "").strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        rows.append({"symbol": symbol, "lithology": str(a.get("GENERAL_LITHOLOGY") or "").strip(),
                     "age": i18n.age_tidy(a.get("AGE")), "color": "transparent", "swatch": swatch.get(symbol, "")})
    rows += [{"symbol": "", "lithology": label, "age": "", "color": "transparent", "swatch": uri}
             for label, uri in swatches if label not in seen]
    return rows


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(영어)은 그대로, 시대만 옮긴다"""
    age = i18n.age_tidy(props.get("AGE"))
    rows = (("기호", props.get("PTYPE")), ("암석 갈래", props.get("GENERAL_LITHOLOGY")),
            ("설명", props.get("DESCRIPTION")), ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip() and str(v).strip().lower() != "null"}
