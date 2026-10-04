"""호주 주 지질조사소로 나가는 문 — 퀸즐랜드(GSQ)·빅토리아(GSV)·남호주(GSSA) (wetherilli 225).

GA(`ga.py`)가 대륙 전체의 1:250만·1:100만을 그린다면, 여기는 주가 내는 더 자세한 판이다. 주마다 서버가 따로라 BGS 문(`bgs.py`)이
GSNI·AGA·GSN 을 함께 내듯 한 파일에 셋을 둔다 — 상류 이름(`gsq`·`gsv`·`gssa`)은 따로다. 셋 다 열쇠가 없고 3857 로 그린다.
조건은 셋 다 **CC BY 4.0** 이다 — 남호주는 Capabilities 의 AccessConstraints 가, 퀸즐랜드·빅토리아는 주 열린자료 목록
(data.qld.gov.au "Queensland geology detailed web map service", discover.data.vic.gov.au "Geological polygons (1:250,000)")이 그렇게 적는다.

- **퀸즐랜드** — `spatial-gis.information.qld.gov.au/arcgis/rest/services/GeoscientificInformation/` 의 `GeologyState`(1:200만, 레이어 6)·
  `GeologyDetailed`(1:10만, 레이어 15 — 1:150만보다 가까울 때만 그린다). WMS 의 레이어 이름에 숫자 꼬리가 붙어
  (`State_Surface_Geology55055`) 판을 다시 올리면 바뀔 수 있다 — REST `export`·`identify` 를 번호로 부른다(남아공 `cgs.py` 와 같은 수)
- **빅토리아** — `opendata.maps.vic.gov.au/geoserver/wms` 의 이음매 없는 지질도(`sg_geological_unit_250k`·`_50k`, GeoSciML 포트레이얼).
  넓게 보면 한 장이 12 초라 가까이서만. 범례는 SGB 처럼 보는 범위의 칸만 JSON 으로 받는다(`hideEmptyRules`) — 이름이 칸에 붙어 온다
- **남호주** — `sarigdata.pir.sa.gov.au/geoserver/ows` 의 `gsmlp:GeologicUnitView`. 1:250만보다 넓으면 빈 그림이다. JSON 범례는 빈 것이 온다
- **범례·구조선**(wetherilli 232) — 퀸즐랜드는 GA 처럼 REST 통계(보는 범위의 단위와 면 수)와 칠하기 규칙(`arcpoints.renderer_colors`)으로,
  남호주는 WFS(보는 범위의 면 — 기하가 따라와 무거워 좁을 때만)와 SLD 의 규칙(`genericSymbolizer` → 색)으로 뜬다. 구조선은 퀸즐랜드
  1:200만 단층·습곡, 1:10만 단층·습곡, 남호주 단층 — 선이라 누르지 않는다
- 속성은 셋 다 JSON. GeoServer 둘은 기하가 따라와 무거워(빅토리아 한 점 38 KB) `propertyName` 으로 열만 받는다
"""
import logging
import math
import re

import requests
from django.conf import settings

import json

from . import arcpoints, i18n, tilecache, usage

log = logging.getLogger(__name__)


class AuStatesError(RuntimeError):
    pass


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _get(upstream: str, url: str, params: dict, timeout: int = 45):
    left = usage.paused()
    if left:
        raise AuStatesError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise AuStatesError(f"{upstream.upper()} 에 닿지 못했다: {exc}") from exc
    log.info("%s %s -> %s", upstream.upper(), r.url, r.status_code)
    usage.record(upstream, ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _one(params: dict, layers: dict, *keys) -> str:
    for key in keys:
        names = [n.strip() for n in str(params.get(key) or "").split(",") if n.strip()]
        if names:
            if len(names) != 1 or names[0] not in layers:
                raise AuStatesError(f"모르는 레이어다: {names}")
            return names[0]
    raise AuStatesError("레이어가 없다")


def _text(value) -> str:
    text = " ".join(str("" if value is None else value).split())
    return "" if text.lower() in ("null", "none", "-999") else text


# ── 지질시대 — GeoSciML 의 ICS 주소 꼬리(`LowerOrdovician`)를 ICS 영어 이름으로 ─────────

_SERIES = {"Lower": "Early", "Upper": "Late"}


def age_of_uri(uri: str) -> str:
    """`…/ischart/LowerOrdovician` → `Early Ordovician`. ICS 의 계(Series) 이름은 Lower·Upper 라 `i18n.age_ko` 가 아는 Early·Late 로 바꾼다."""
    tail = str(uri or "").rstrip("/").rsplit("/", 1)[-1]
    words = re.findall(r"[A-Z][a-z]+|[a-z]+", tail)
    if not words:
        return ""
    if len(words) == 2 and words[0] in _SERIES:
        words[0] = _SERIES[words[0]]
    return " ".join(w.capitalize() for w in words)


def _span(old: str, young: str, lang: str) -> str:
    age = old if old == young or not young else (young if not old else f"{old} - {young}")
    return i18n.age_ko(age) if lang == "ko" and age else age


# ── 퀸즐랜드 GSQ — ArcGIS REST ───────────────────────────────────────

GSQ_ATTRIBUTION = ('<a href="https://www.business.qld.gov.au/industries/mining-energy-water/resources/geoscience-information/gsq" '
                   'target="_blank" rel="noopener">© State of Queensland</a> (Geological Survey of Queensland, CC BY 4.0)')
#: 레이어 → (서비스, REST 레이어 번호들, 처음 그리는 줌, 단위 면인가 — 누르기·범례). 구조선은 선이라 누르지 않는다 (wetherilli 232)
GSQ_LAYERS = {
    "gsq:state": ("GeologyState", "6", None, True),
    "gsq:detailed": ("GeologyDetailed", "15", 9, True),
    "gsq:state_structure": ("GeologyState", "3,4", 7, False),
    "gsq:faults": ("GeologyDetailed", "4", 9, False),
    "gsq:folds": ("GeologyDetailed", "5", 9, False),
    # 광산·광물 산지(MINOCC)와 지구물리 영상 (wetherilli 269)
    "gsq:mines": ("MiningResources", "12", 7, True),
    "gsq:tmi": ("GeophysicalImagery", "0", None, False),
    "gsq:radiometric": ("GeophysicalImagery", "30", None, False),
    "gsq:gravity": ("GeophysicalImagery", "40", None, False),
}
#: 범례 — 단위 면의 통계로 묶을 열. 첫 열(들)이 칠하기 규칙의 열이다
GSQ_LEGEND_FIELDS = {"gsq:state": ("ru_name", "map_symbol", "age"), "gsq:detailed": ("legend", "age")}
#: 칠하기 규칙을 담아 두는 날
COLORS_MAX_AGE = 30 * 86400


def _box(params: dict) -> tuple:
    try:
        box = tuple(float(v) for v in str(params.get("bbox", "")).split(","))
    except ValueError as exc:
        raise AuStatesError("BBOX 를 읽지 못했다") from exc
    if len(box) != 4:
        raise AuStatesError("BBOX 를 읽지 못했다")
    return box


def _size(params: dict) -> tuple:
    try:
        w, h = int(params.get("width") or 256), int(params.get("height") or 256)
    except ValueError as exc:
        raise AuStatesError("크기를 읽지 못했다") from exc
    if not (0 < w <= 2048 and 0 < h <= 2048):
        raise AuStatesError("크기가 지나치다")
    return w, h


def _merc(params: dict):
    code = str(params.get("crs") or params.get("srs") or "EPSG:3857").upper()
    if code not in ("EPSG:3857", "EPSG:900913"):
        raise AuStatesError(f"3857 만 받는다: {code}")


def _gsq_url(name: str, op: str) -> str:
    return f"{settings.GSQ_REST_URL.rstrip('/')}/{GSQ_LAYERS[name][0]}/MapServer/{op}"


def gsq_get_map(params: dict):
    name = _one(params, GSQ_LAYERS, "layers")
    _merc(params)
    box, (w, h) = _box(params), _size(params)
    r = _get("gsq", _gsq_url(name, "export"), {
        "bbox": ",".join(repr(v) for v in box), "bboxSR": 3857, "imageSR": 3857, "size": f"{w},{h}", "dpi": 96,
        "format": "png32", "transparent": "true", "layers": f"show:{GSQ_LAYERS[name][1]}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise AuStatesError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def gsq_get_feature_info(params: dict) -> dict:
    name = _one(params, GSQ_LAYERS, "query_layers", "layers")
    _merc(params)
    box, (w, h) = _box(params), _size(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise AuStatesError("누른 자리를 읽지 못했다") from exc
    x = box[0] + (i + 0.5) * (box[2] - box[0]) / w
    y = box[3] - (j + 0.5) * (box[3] - box[1]) / h
    r = _get("gsq", _gsq_url(name, "identify"), {
        "geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": 3857,
        "layers": f"visible:{GSQ_LAYERS[name][1]}", "tolerance": 2, "mapExtent": ",".join(repr(v) for v in box),
        "imageDisplay": f"{w},{h},96", "returnGeometry": "false", "f": "json"})
    if r.status_code != 200:
        raise AuStatesError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        results = r.json().get("results") or []
    except ValueError as exc:
        raise AuStatesError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"gsq.{(x.get('attributes') or {}).get('OBJECTID', n)}", "properties": x.get("attributes") or {}}
                         for n, x in enumerate(results[:3])]}


def gsq_get_legend(layer: str):
    raise AuStatesError("퀸즐랜드 범례는 아직 없다")


def gsq_friendly(props: dict, lang: str = "ko") -> dict:
    """identify 의 열은 사람이 읽는 이름이다(`Rock Unit Name`). 값은 영어 그대로, 시대(`DEVONIAN - CARBONIFEROUS`)만 옮긴다."""
    v = lambda k: _text(props.get(k))       # noqa: E731
    if "Occurrence name" in props:          # 광산·광물 산지 MINOCC (wetherilli 269)
        rows = (("이름", v("Occurrence name")), ("광종", v("Main commodity").capitalize()), ("모든 광종", v("All commodities")),
                ("광산", v("Mine status").capitalize()), ("광상 규모", v("Deposit size").capitalize()), ("곳", v("Site locality")))
        return {k: x for k, x in rows if x}
    age = v("Age").title()
    rows = (("기호", v("Map Symbol")), ("이름", v("Rock Unit Name")), ("암석", v("Lithological Summary")),
            ("주 암석", v("Dominant Rock").capitalize()), ("갈래", v("Rock Type").capitalize()),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age))
    return {k: x for k, x in rows if x}


GSQ = _NS(get_map=gsq_get_map, get_feature_info=gsq_get_feature_info, get_legend=gsq_get_legend, friendly=gsq_friendly)


# ── 빅토리아 GSV·남호주 GSSA — GeoServer 의 GeoSciML 포트레이얼 ──────────────

GSV_ATTRIBUTION = ('<a href="https://earthresources.vic.gov.au/geology-exploration" target="_blank" rel="noopener">'
                   '© State of Victoria</a> (Geological Survey of Victoria, CC BY 4.0)')
#: 메타타일로 받는다 (wetherilli 287) — 남호주 512 px 12.9–13.6 초, 1 024 px 24.7 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"gssa:": None}

GSSA_ATTRIBUTION = ('<a href="https://www.energymining.sa.gov.au/industry/geological-survey" target="_blank" rel="noopener">'
                    '© Government of South Australia</a> (Geological Survey of South Australia, SARIG, CC BY 4.0)')
#: 레이어 → (상류 레이어, 처음 그리는 줌, 단위 면인가)
GSV_LAYERS = {
    "gsv:250k": ("open-data-platform:sg_geological_unit_250k", 8, True),
    "gsv:50k": ("open-data-platform:sg_geological_unit_50k", 11, True),
    # 광상(면 237)·광상 점(620) (wetherilli 269)
    "gsv:mineral": ("open-data-platform:mineral", 7, True),
    "gsv:mineralp": ("open-data-platform:mineralp", 7, True),
}
GSSA_LAYERS = {
    "gssa:units": ("gsmlp:GeologicUnitView", 9, True),
    # 단층 — 1:200만보다 넓으면 빈 그림이다 (wetherilli 232)
    "gssa:faults": ("gsmlp:ShearDisplacementStructureView", 10, False),
    # 광물 산지 — EarthResourceML 라이트 (wetherilli 269)
    "gssa:minocc": ("erl:MineralOccurrenceView", 7, True),
}
#: 속성으로 받을 열 — 빅토리아는 작은 글자, 남호주는 낙타 꼴이다
GSV_PROPERTIES = "name,description,rank,lithology,geologichistory,representativeage_uri,representativelowerage_uri,representativeupperage_uri"
GSSA_PROPERTIES = ("name,description,rank,lithology,geologicHistory,numericOlderAge,numericYoungerAge,"
                   "representativeOlderAge_uri,representativeYoungerAge_uri")
#: 범례 칸을 몇 개까지 싣나, 범례를 뜨는 가장 넓은 범위(°). 남호주는 WFS 가 기하까지 보내(0.2° 네모에 0.9 MB) 좁을 때만
MAX_LEGEND = 60
LEGEND_SPAN = {"gsq": 6.0, "gsv": 4.0, "gssa": 0.5}
#: 남호주 범례 — WFS 로 받는 면의 수 끝
GSSA_LEGEND_FEATURES = 3000


#: 지질 단위가 아닌 레이어의 속성 열 — 단위의 열(`GSV_PROPERTIES` 따위)을 물으면 상류가 예외를 낸다 (wetherilli 269)
LAYER_PROPERTIES = {
    "gsv:mineral": "name,commdsc,commgrp,resclad,rescladf,locaccd",
    "gsv:mineralp": "name,commdsc,commgrp,resclad,rescladf,locaccd",
    "gssa:minocc": "name,commodity,mineralOccurrenceType,mineralDepositModel,hostGeologicUnit,source",
}


def _gs(upstream: str):
    if upstream == "gsv":
        return settings.GSV_WMS_URL, GSV_LAYERS, GSV_PROPERTIES
    return settings.GSSA_WMS_URL, GSSA_LAYERS, GSSA_PROPERTIES


def _gs_get_map(upstream: str, params: dict):
    url, layers, _ = _gs(upstream)
    name = _one(params, layers, "layers")
    params = dict(params, service="WMS", request="GetMap", layers=layers[name][0], styles="")
    r = _get(upstream, url, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise AuStatesError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def _gs_get_feature_info(upstream: str, params: dict) -> dict:
    url, layers, columns = _gs(upstream)
    name = _one(params, layers, "query_layers", "layers")
    params = dict(params, service="WMS", request="GetFeatureInfo", layers=layers[name][0], query_layers=layers[name][0],
                  styles="", info_format="application/json", feature_count=3, propertyName=LAYER_PROPERTIES.get(name, columns))
    r = _get(upstream, url, params)
    if r.status_code != 200:
        raise AuStatesError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        features = r.json().get("features") or []
    except ValueError as exc:
        raise AuStatesError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f.get("id"), "properties": f.get("properties") or {}} for f in features]}


def _gs_get_legend(layer: str):
    raise AuStatesError("범례는 보는 범위로만 뜬다")


def gs_friendly(props: dict, lang: str = "ko") -> dict:
    """GeoSciML 포트레이얼의 열(빅토리아는 작은 글자, 남호주는 낙타 꼴). 이름·설명·암석은 영어 그대로, 시대만 옮긴다."""
    low = {str(k).lower(): v for k, v in props.items()}
    v = lambda k: _text(low.get(k))         # noqa: E731
    if "commdsc" in low:                    # 빅토리아 광상 (wetherilli 269)
        rows = (("이름", v("name")), ("광종", v("commdsc")), ("광상 규모", v("rescladf") or v("resclad")), ("위치 정확도", v("locaccd")))
        return {k: x for k, x in rows if x}
    if "commodity" in low:                  # 남호주 광물 산지
        src = v("source")
        rows = (("이름", v("name")), ("광종", v("commodity")), ("갈래", v("mineraloccurrencetype")), ("광상 형태", v("mineraldepositmodel")),
                ("모암", v("hostgeologicunit")),
                ("상세", {"text": "", "links": [{"url": src, "label": "열기"}]} if src.startswith(("http://", "https://")) else ""))
        return {k: x for k, x in rows if x}
    old = age_of_uri(low.get("representativeolderage_uri") or low.get("representativelowerage_uri")
                     or low.get("representativeage_uri"))
    young = age_of_uri(low.get("representativeyoungerage_uri") or low.get("representativeupperage_uri"))
    ma_old, ma_young = v("numericolderage"), v("numericyoungerage")
    ma = f"{ma_young}–{ma_old}" if ma_old and ma_young and ma_old != ma_young else (ma_old or ma_young)
    rows = (("이름", v("name")), ("설명", v("description")), ("암석", v("lithology")), ("위계", v("rank")),
            ("지질시대", _span(old, young, lang)), ("연대 (Ma)", ma), ("지질 이력", v("geologichistory")))
    return {k: x for k, x in rows if x}


def _gsv_legend(name: str, bbox_3857: tuple, width: int = 1024, height: int = 768) -> list:
    """빅토리아 — 범위 `(서, 남, 동, 북)`(3857 미터)에 칠해진 칸 `[{"lithology", "color", "count"}]`, 많이 칠해진 것부터.
    GeoServer 가 그 범위를 그려 보고 빈 규칙을 뺀다(`hideEmptyRules`). 규칙 이름이 단위 이름이다 — "Bacchus Marsh Formation (Pxb)" """
    if name not in GSV_LAYERS:
        raise AuStatesError("범례가 없는 레이어다")
    r = _get("gsv", settings.GSV_WMS_URL, {
        "service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "application/json",
        "layer": GSV_LAYERS[name][0], "legend_options": "countMatched:true;hideEmptyRules:true",
        "bbox": ",".join(f"{v:.0f}" for v in bbox_3857), "srs": "EPSG:3857", "crs": "EPSG:3857",
        "srcwidth": str(width), "srcheight": str(height)})
    if r.status_code != 200:
        raise AuStatesError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        rules = (r.json().get("Legend") or [{}])[0].get("rules") or []
    except (ValueError, AttributeError, IndexError) as exc:
        raise AuStatesError("범례가 JSON 이 아니다") from exc
    out = []
    for rule in rules:
        label = str(rule.get("name") or "").strip()
        fill = next((s["Polygon"].get("fill") for s in rule.get("symbolizers") or [] if "Polygon" in s), None)
        if not label or not fill:
            continue
        title = str(rule.get("title") or "")
        count = int(title.rsplit("(", 1)[1].rstrip(") ")) if title.endswith(")") and "(" in title and \
            title.rsplit("(", 1)[1].rstrip(") ").isdigit() else 0
        out.append({"symbol": "", "lithology": label, "color": fill, "swatch": "", "age": "", "count": count})
    return sorted(out, key=lambda r: -r["count"])


def legend_bbox(west: float, south: float, east: float, north: float) -> tuple:
    """위경도 범위 → 3857 미터."""
    def merc(lon, lat):
        lat = max(min(lat, 85.0), -85.0)
        return lon * 20037508.342789244 / 180, math.log(math.tan((90 + lat) * math.pi / 360)) * 6378137
    (x0, y0), (x1, y1) = merc(west, south), merc(east, north)
    return x0, y0, x1, y1


def _rest_json(upstream: str, url: str, params: dict) -> dict:
    r = _get(upstream, url, dict(params, f="json"))
    try:
        data = r.json()
    except ValueError as exc:
        raise AuStatesError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise AuStatesError(f"REST 오류 (status={r.status_code}): {(data.get('error') or {}).get('message', '')}")
    return data


def _held(key: str, build):
    """한 번 받아 담는 표(칠하기 규칙·SLD). 다시 받지 못하면 옛것을 낸다."""
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    try:
        value = build()
    except AuStatesError:
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise
    tilecache.put(key, json.dumps(value, ensure_ascii=False).encode("utf-8"), ".json")
    return value


def gsq_renderer(name: str) -> dict:
    """퀸즐랜드 칠하기 규칙 — `{"fields": [열…], "delimiter", "table": {값: 색}}`. 1:200만은 `RU_NAME:MAP_SYMBOL` 두 열을 `:` 로 잇고,
    1:10만은 `legend` 한 열이다(규칙이 3.6 MB 라 한 번 받아 담는다)"""
    def build():
        r = _rest_json("gsq", _gsq_url(name, GSQ_LAYERS[name][1]), {})
        try:
            rd = r["drawingInfo"]["renderer"]
        except (KeyError, TypeError) as exc:
            raise AuStatesError("칠하기 규칙이 없다") from exc
        fields = [str(rd[k]).lower() for k in ("field1", "field2", "field3") if rd.get(k)]
        return {"fields": fields, "delimiter": rd.get("fieldDelimiter") or ",", "table": arcpoints.renderer_colors(rd)}
    return _held(tilecache.key_text("gsq-renderer", name), build)


def _gsq_legend(name: str, bbox: tuple) -> list:
    rule = gsq_renderer(name)
    group = GSQ_LEGEND_FIELDS[name]
    data = _rest_json("gsq", _gsq_url(name, f"{GSQ_LAYERS[name][1]}/query"), {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": ",".join(group),
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "objectid", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = {str(k).lower(): v for k, v in (f.get("attributes") or {}).items()}
        value = rule["delimiter"].join(_text(a.get(k)) for k in rule["fields"])
        if not value.strip(rule["delimiter"]):
            continue
        label = f"{_text(a.get('map_symbol'))} {_text(a.get('ru_name'))}".strip() if "ru_name" in group else _text(a.get("legend"))
        row = rows.setdefault(value, {"symbol": "", "lithology": label, "color": rule["table"].get(value, "#cccccc"),
                                      "swatch": "", "age": _text(a.get("age")).title(), "count": 0})
        row["count"] += int(a.get("n") or 0)
    return sorted(rows.values(), key=lambda r: -r["count"])


def gssa_colors() -> dict:
    """남호주 SLD 의 규칙 — `genericSymbolizer` 값 → 채움 색. SLD 가 1.8 MB 라 한 번 받아 담는다"""
    def build():
        r = _get("gssa", settings.GSSA_WMS_URL, {"service": "WMS", "version": "1.1.1", "request": "GetStyles",
                                                 "layers": GSSA_LAYERS["gssa:units"][0]})
        if r.status_code != 200:
            raise AuStatesError(f"SLD 를 읽지 못했다 (status={r.status_code})")
        table = {}
        for rule in re.findall(r"<sld:Rule>(.*?)</sld:Rule>", r.text, re.S):
            literal = re.search(r"genericSymbolizer</ogc:PropertyName>\s*<ogc:Literal>([^<]+)</ogc:Literal>", rule)
            fill = re.search(r'<sld:CssParameter name="fill">([^<]+)</sld:CssParameter>', rule)
            if literal and fill:
                table.setdefault(literal.group(1).strip(), fill.group(1).strip())
        if not table:
            raise AuStatesError("SLD 에 규칙이 없다")
        return table
    return _held(tilecache.key_text("gssa-sld", "GeologicUnitView"), build)


def _gssa_legend(name: str, bbox: tuple) -> list:
    table = gssa_colors()
    r = _get("gssa", settings.GSSA_WMS_URL.replace("/ows", "/wfs"), {
        "service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": GSSA_LAYERS[name][0],
        # 앱 스키마라 열에 이름공간을 붙이고, 범위는 경도·위도 차례로 준다(위도 먼저면 빈 답) — 2026-10-04
        "bbox": ",".join(str(v) for v in bbox) + ",EPSG:4326", "propertyName": "gsmlp:name,gsmlp:genericSymbolizer",
        "outputFormat": "application/json", "maxFeatures": str(GSSA_LEGEND_FEATURES)}, timeout=60)
    if r.status_code != 200:
        raise AuStatesError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        features = r.json().get("features") or []
    except ValueError as exc:
        raise AuStatesError("범례가 JSON 이 아니다") from exc
    rows = {}
    for f in features:
        p = f.get("properties") or {}
        label, code = _text(p.get("name")), _text(p.get("genericSymbolizer"))
        if not label:
            continue
        row = rows.setdefault((label, code), {"symbol": "", "lithology": label, "color": table.get(code, "#cccccc"),
                                              "swatch": "", "age": "", "count": 0})
        row["count"] += 1
    return sorted(rows.values(), key=lambda r: -r["count"])


#: 누를 수 있지만 지질 단위가 아닌 레이어 — 광산·광물 산지. 범위 범례를 뜨지 않는다 (wetherilli 269)
RESOURCES = ("gsq:mines", "gsv:mineral", "gsv:mineralp", "gssa:minocc")


def queryable(upstream: str, name: str) -> bool:
    spec = UPSTREAMS[upstream][1][name]
    return bool(spec[3] if upstream == "gsq" else spec[2])


def is_unit(upstream: str, name: str) -> bool:
    return queryable(upstream, name) and name not in RESOURCES


def extent_legend(upstream: str, name: str, bbox: tuple, lang: str = "ko") -> list:
    """보는 범위 `(서, 남, 동, 북)`(위경도)의 범례 칸 `[{"lithology", "color", "age", "count", …}]` — 면이 많은 것부터."""
    if not knows(upstream, name) or not is_unit(upstream, name):
        raise AuStatesError("범례가 없는 레이어다")
    if upstream == "gsv":
        rows = _gsv_legend(name, legend_bbox(*bbox))
    elif upstream == "gsq":
        rows = _gsq_legend(name, bbox)
    else:
        rows = _gssa_legend(name, bbox)
    for row in rows:
        if row.get("age") and lang == "ko":
            row["age"] = i18n.age_ko(row["age"])
    return rows


GSV = _NS(get_map=lambda p: _gs_get_map("gsv", p), get_feature_info=lambda p: _gs_get_feature_info("gsv", p),
          get_legend=_gs_get_legend, friendly=gs_friendly)
GSSA = _NS(get_map=lambda p: _gs_get_map("gssa", p), get_feature_info=lambda p: _gs_get_feature_info("gssa", p),
           get_legend=_gs_get_legend, friendly=gs_friendly)

#: 상류 → (문, 레이어 표, 출처)
UPSTREAMS = {"gsq": (GSQ, GSQ_LAYERS, GSQ_ATTRIBUTION), "gsv": (GSV, GSV_LAYERS, GSV_ATTRIBUTION),
             "gssa": (GSSA, GSSA_LAYERS, GSSA_ATTRIBUTION)}


def knows(upstream: str, name: str) -> bool:
    return upstream in UPSTREAMS and name in UPSTREAMS[upstream][1]


def first_zoom(upstream: str, name: str):
    spec = UPSTREAMS[upstream][1][name]
    return spec[2] if upstream == "gsq" else spec[1]
