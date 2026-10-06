"""앨버타 지질조사소(Alberta Geological Survey, AER)로 나가는 문 — 앨버타 기반암 1:100만 (Map 600)의 누른 자리 (wetherilli 235).

- **그림은 문을 거치지 않는다.** AGS 가 ArcGIS Online 에 올린 타일(`Bedrock_Geology_1M_Map_600_No_Labels_NEW`, 3857 z/x/y, 줌 0–12)뿐이고
  `export` 가 없다(TilesOnly). 일본 지리원 주제 타일(wetherilli 172)처럼 카탈로그 행의 `tiles` 를 화면이 곧장 받는다 — 열쇠가 없고
  CORS 가 열렸다. 캐나다 탭(3978)에서는 OpenLayers 가 옮겨 그린다
- **누른 자리만 이 문이 묻는다** — 같은 자료의 피처 서비스(`Bedrock_Geology_of_Alberta_POLY_DIG_2013_0018/FeatureServer/0`)에 누른 점
  하나로 `query`(`inSR` 은 화면의 투영)
- 조건: Open Government Licence – Alberta. "AER/AGS 를 출처로 밝힌다" — 타일 서비스의 저작권 칸이 그렇게 적는다
- **광물 산지**(wetherilli 321) — AGS 가 ArcGIS Online 에 모아 둔 `Mineral_Occurrences` 피처 서비스(5 454 점) — 금속 광물(DIG 2019-0026)·산업 광물
  (DIG 2019-0027)·지하수·지층수의 리튬(DIG 2019-0029)·규사·광물 코어·비에너지 광물 생산자가 한 레이어에 갈래 열(`feature_layer_source`)로 든다.
  그림이 없는 피처 서비스라 파나마(`stri.py`)처럼 **한 덩이로 받아 화면이 그린다** — 2 000 점씩 세 번, 캐시에 30 일. 색은 상류의 칠하기 규칙 그대로
"""
import json
import logging

import requests
from django.conf import settings

from . import i18n, tilecache, usage
from .i18n import msg

log = logging.getLogger(__name__)

PREFIX = "ags:"
ATTRIBUTION = ('<a href="https://ags.aer.ca/publications/all-publications/map-600" target="_blank" rel="noopener">'
               "Alberta Energy Regulator / Alberta Geological Survey</a> (Map 600, OGL–Alberta)")
TILE_URL = ("https://tiles.arcgis.com/tiles/jQV6VMr2Loovu7GU/arcgis/rest/services/Bedrock_Geology_1M_Map_600_No_Labels_NEW/"
            "MapServer/tile/{z}/{y}/{x}")
#: 레이어 → (타일 주소, 타일의 마지막 줌)
LAYERS = {"ags:bedrock": (TILE_URL, 12)}
FIELDS = ("Unit_Name", "Lithology", "Environ", "Age", "GeolRegion")


class AgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise AgsError(f"모르는 레이어다: {names}")
    return names[0]


def get_map(params: dict):
    raise AgsError("앨버타 타일은 화면이 곧장 받는다")


def get_legend(layer: str):
    raise AgsError("앨버타 범례는 따로 받지 않는다")


def get_feature_info(params: dict) -> dict:
    """WMS GetFeatureInfo 변수(화면이 누른 자리 둘레로 지은 작은 네모) → 그 가운데 점 하나로 피처 서비스 `query`."""
    _one(params)
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    try:
        west, south, east, north = (float(v) for v in str(params["bbox"]).split(","))
    except (KeyError, ValueError) as exc:
        raise AgsError("범위를 읽지 못했다") from exc
    if not crs.startswith("EPSG:"):
        raise AgsError(f"EPSG 로만 묻는다: {crs}")
    left = usage.paused()
    if left:
        raise AgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.AGS_FEATURE_URL.rstrip("/") + "/query",
                         params={"geometry": f"{(west + east) / 2!r},{(south + north) / 2!r}", "geometryType": "esriGeometryPoint",
                                 "inSR": crs[5:], "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(FIELDS),
                                 "returnGeometry": "false", "f": "json"},
                         timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ags", ok=False)
        raise AgsError(f"앨버타에 닿지 못했다: {exc}") from exc
    log.info("AGS %s -> %s", r.url, r.status_code)
    usage.record("ags", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise AgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise AgsError("속성이 JSON 이 아니다") from exc
    if data.get("error"):
        raise AgsError(f"query 오류: {data['error'].get('message', '')}")
    return {"features": [{"id": f"ags.{n}", "properties": f.get("attributes") or {}}
                         for n, f in enumerate(data.get("features") or [])]}


#: 보는 범위의 범례를 세우는 레이어 (wetherilli 357) — 피처 서비스가 단위마다 그림의 색을 `RGB` 열("93-168-115")로 들고 있다.
#: 타일 범례(88 칸)와 대 보니 ±1 로 같았다. 그래서 통계 질의 한 번이면 이름·색·시대가 다 온다
EXTENT_LEGENDS = ("ags:bedrock",)
LEGEND_SPAN = 14.0         # 주 전체(가로 10°·세로 11°)가 든다


def _ics(age: str) -> str:
    # Map 600 은 `Upper`·`Lower` 를 쓴다 — ICS 의 Late·Early 로
    return " ".join({"Upper": "Late", "Lower": "Early"}.get(w, w) for w in age.split())


def extent_legend(name: str, bbox: tuple, lang: str = "ko") -> list:
    """보는 범위 `(서, 남, 동, 북)`(위경도)에 든 단위 `[{"lithology", "color", "age", "count"}]`, 면이 많은 것부터"""
    if name not in EXTENT_LEGENDS:
        raise AgsError("범례가 없는 레이어다")
    left = usage.paused()
    if left:
        raise AgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.AGS_FEATURE_URL.rstrip("/") + "/query", params={
            "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": "Unit_Name,RGB,Age",
            "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "FID", "outStatisticFieldName": "n"}]),
            "returnGeometry": "false", "f": "json"},
            timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ags", ok=False)
        raise AgsError(f"앨버타에 닿지 못했다: {exc}") from exc
    log.info("AGS %s -> %s", r.url, r.status_code)
    usage.record("ags", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    try:
        data = r.json()
    except ValueError as exc:
        raise AgsError("범례 통계가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise AgsError(f"범례 통계를 받지 못했다 (status={r.status_code})")
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        unit = str(a.get("Unit_Name") or "").strip()
        try:
            color = "#" + "".join(f"{int(v):02x}" for v in str(a.get("RGB") or "").split("-"))
        except ValueError:
            continue
        if not unit or len(color) != 7:
            continue
        age = str(a.get("Age") or "").strip()
        ko = i18n.age_ko(_ics(age)) if lang == "ko" and age else age
        row = rows.setdefault(unit, {"symbol": "", "lithology": unit, "color": color, "swatch": "",
                                     "age": ko if ko != _ics(age) else age, "count": 0})
        row["count"] += int(a.get("n") or 0)
    return sorted(rows.values(), key=lambda row: -row["count"])


def friendly(props: dict, lang: str = "ko") -> dict:
    """지층·암상·퇴적 환경은 영어 그대로, 시대(`Upper Cretaceous` 따위)만 옮긴다."""
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    age = v("Age")
    # Map 600 은 `Upper`·`Lower` 를 쓴다 — ICS 의 Late·Early 로 바꿔 옮긴다
    ics = " ".join({"Upper": "Late", "Lower": "Early"}.get(w, w) for w in age.split())
    rows = (("지층", v("Unit_Name")), ("암석", v("Lithology")), ("퇴적 환경", v("Environ")),
            ("지질시대", (i18n.age_ko(ics) if i18n.age_ko(ics) != ics else age) if lang == "ko" and age else age), ("지역", v("GeolRegion")))
    return {k: x for k, x in rows if x}


def probe_tile(url: str):
    """화면이 곧장 부르는 ArcGIS Online 타일 한 장을 대조가 받아 본다 (`verify_layers`, wetherilli 311). (상태, content-type, 바이트)"""
    left = usage.paused()
    if left:
        raise AgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ags", ok=False)
        raise AgsError(f"앨버타 타일에 닿지 못했다: {exc}") from exc
    usage.record("ags", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r.status_code, r.headers.get("content-type", ""), r.content


# ── 광물 산지 — 한 덩이 (wetherilli 321) ─────────────────────────────────

POINTS = "ags:minocc"
OCC_ATTRIBUTION = ('<a href="https://geology-ags-aer.opendata.arcgis.com/" target="_blank" rel="noopener">'
                   "Alberta Energy Regulator / Alberta Geological Survey</a> (Mineral Occurrences, OGL–Alberta)")
OCC_SOURCE_URL = "https://geology-ags-aer.opendata.arcgis.com/"
OCC_FIELDS = ("site_name", "commodity", "other_commodity", "dev_stage", "site_type", "geo_unit", "geo_age", "location",
              "feature_layer_source")
OCC_HELD = 30 * 86400
PAGE = 2000
#: 갈래 — (부호, 갈래 열에 든 자료 이름의 조각, 이름, 색). 색은 상류의 칠하기 규칙 그대로
CLASSES = (
    ("metal", "Metallic Mineral Occurrences", msg("금속 광물"), "#a7c636"),
    ("industrial", "Industrial Mineral Occurrences", msg("산업 광물"), "#149ece"),
    ("lithium", "Lithium Content", msg("리튬 (지하수·지층수)"), "#ed5151"),
    ("silica", "Silica Sand", msg("규사"), "#fc921f"),
    ("producer", "Non-Energy Mineral Producers", msg("비에너지 광물 생산자"), "#ffde3e"),
    ("core", "Mineral Core Locations", msg("광물 코어"), "#9e559c"),
)
OCC_LABELS = {"name": "이름", "commodity": "광종", "other": "다른 광종", "stage": "개발 단계", "site": "갈래", "unit": "지층", "age": "지질시대",
              "location": "곳"}


def knows_points(name: str) -> bool:
    return name == POINTS


def _occ_page(offset: int) -> list:
    left = usage.paused()
    if left:
        raise AgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.AGS_OCCURRENCES_URL.rstrip("/") + "/query", params={
            "where": "1=1", "outFields": ",".join(OCC_FIELDS), "outSR": "4326", "f": "geojson", "orderByFields": "OBJECTID ASC",
            "resultOffset": offset, "resultRecordCount": PAGE, "geometryPrecision": "5"},
            timeout=max(settings.UPSTREAM_TIMEOUT, 45), verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ags", ok=False)
        raise AgsError(f"앨버타 광물 산지에 닿지 못했다: {exc}") from exc
    log.info("AGS %s -> %s", r.url, r.status_code)
    usage.record("ags", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise AgsError(f"받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise AgsError("JSON 이 아니다") from exc
    if isinstance(data, dict) and data.get("error"):
        raise AgsError(f"상류 오류: {data['error'].get('message', '')}")
    return data.get("features") or []


def occurrences() -> list:
    """점 전부 — 2 000 점씩. 받은 것은 30 일 담아 둔다"""
    key = tilecache.key_text("ags", "occurrences")
    held = tilecache.get(key, ".json", max_age=OCC_HELD)
    if held is not None:
        return json.loads(held)
    out, offset = [], 0
    while True:
        page = _occ_page(offset)
        out += page
        if len(page) < PAGE or offset > 50000:
            break
        offset += PAGE
    tilecache.put(key, json.dumps(out, separators=(",", ":")).encode("utf-8"), ".json")
    return out


def _class_of(source: str) -> str:
    return next((code for code, part, _, _ in CLASSES if part in source), "")


def points_body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 지역 탭의 점 레이어(`earthpoints`)와 같다(`style: class`)"""
    if not knows_points(name):
        raise AgsError(f"모르는 레이어다: {name}")
    items, counts = [], {}
    for f in occurrences():
        p = f.get("properties") or {}
        code = _class_of(str(p.get("feature_layer_source") or ""))
        if not code or not f.get("geometry"):
            continue
        v = lambda k: str(p.get(k) or "").strip()          # noqa: E731
        age = v("geo_age")
        props = {"code": code, "name": v("site_name"), "commodity": v("commodity"), "other": v("other_commodity"),
                 "stage": v("dev_stage"), "site": v("site_type"), "unit": v("geo_unit"),
                 "age": (i18n.age_ko(age) if lang == "ko" else age) if age else "", "location": v("location")}
        items.append({"type": "Feature", "geometry": f["geometry"], "properties": {k: x for k, x in props.items() if x}})
        counts[code] = counts.get(code, 0) + 1
    legend = [{"code": code, "label": i18n.t(label, lang), "color": color, "shape": "dot", "count": counts[code]}
              for code, _, label, color in CLASSES if counts.get(code)]
    out = {"type": "FeatureCollection", "style": "class", "labels": OCC_LABELS, "legend": legend, "features": items}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "ags", "tag": "AGS", "title": "앨버타 지질조사소", "relay": True},
]
