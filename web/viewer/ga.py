"""GA(Geoscience Australia)로 나가는 문 — 호주 지표 지질도 1:250만·1:100만 (wetherilli 212).

- 주소: `services.ga.gov.au/gis/services/GA_Surface_Geology/MapServer/WMSServer` (ArcGIS WMS). REST 는
  `services.ga.gov.au/gis/rest/services/GA_Surface_Geology/MapServer`. 열쇠가 없다. 서비스의 투영은 3857(102100)이다
- **축척에 따라 판이 갈마든다** — 1:250만 판은 1:150만보다 멀 때, 1:100만 판은 가까울 때만 그린다. 두 판의 WMS 레이어를 한 번에
  물으면 상류가 그 축척에 맞는 판을 그린다. 그래서 레이어 하나(`ga:<갈래>`)가 두 판을 함께 부른다
- 갈래는 넷 — 암층층서(lithostratigraphy)·연대(age)·암상(lithology)으로 칠한 단위 면과 단층
- **3577(호주 알베르스)은 그리지 않는다**(빈 그림, 2026-10-04). 3857 이 원래 투영이다
- 속성은 `application/geo+json` — 기하 없이 2 KB. GeoSciML 꼴 열(name·description·geologicHistory·lithology·mapSymbol)이 영어로 온다.
  시대는 ICS 영어라 한국어판이면 옮긴다(`Cenozoic to Quaternary` → 신생대~제4기)
- 범례는 보는 범위의 것 — 범례 그림은 198×4096 이다. 페루(`ingemmet.py`)처럼 REST 통계 질의와 칠하기 규칙(`PLOTSYMBOL` 따위)으로 뜬다.
  REST 의 열 이름은 소문자다(`plotsymbol`·`geolhist`) — 큰 글자로 물으면 400
- CORS 는 Origin 을 되비춘다. 조건: **CC BY 4.0**(© Commonwealth of Australia (Geoscience Australia) 2016) — 정적 판에 실을 수 있다
- **확인 자원·수리지질도**(wetherilli 325) — ecat 에서 찾은 `AustraliasIdentifiedMineralResources`(광종 29, 2025 판)와 `Hydrogeology_of_Australia`
  (1987 1:500만의 수치판). 둘 다 CC BY 4.0, 같은 `OTHER` 길. 지하수는 분지별 조사(쿠퍼·갈릴리·보웬…)가 수십 개라 온 나라 한 장만 골랐다
- **다른 서비스**(wetherilli 241) — 서비스 목록(`/gis/rest/services`)이 403 이라 GA 자료 목록(ecat)·검색으로 이름을 찾았다. 셋을 같은 문으로
  부른다(`OTHER`): 지질구(`Australian_Geological_Provinces` — 지각 요소·지질구 전부), 핵심 광물(`AustralianCriticalMineralsOperatingMinesAndDeposits`
  — 광산 셋·광상), 지구물리 격자(`/gis/geophysical-grids/ows` GeoServer — 자력 TMI·완전 부게 중력·방사능 3색). 셋 다 CC BY 4.0.
  격자는 512² 한 장이 PNG 로 1 MB 라 **png8 로 받는다**(260 KB, 투명도는 남는다). 격자 속성은 그림 값(HSI)뿐이라 누르지 않는다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "ga:"
ATTRIBUTION = ('<a href="https://www.ga.gov.au/" target="_blank" rel="noopener">© Geoscience Australia</a> '
               "(Surface Geology of Australia, CC BY 4.0)")
#: 레이어 → (1:250만 WMS 이름, 1:100만 WMS 이름, 1:250만 REST 번호, 1:100만 REST 번호, 범례·누르기가 되는 단위 면인가)
LAYERS = {
    "ga:lithostratigraphy": ("AUS_GA_2500k_GUPoly_Lithostratigraphy", "AUS_GA_1M_GUPoly_Lithostratigraphy", 3, 10, True),
    "ga:age": ("AUS_GA_2500k_GUPoly_Age", "AUS_GA_1M_GUPoly_Age", 5, 12, True),
    "ga:lithology": ("AUS_GA_2500k_GUPoly_Lithology", "AUS_GA_1M_GUPoly_Lithology", 4, 11, True),
    "ga:faults": ("AUS_GA_2500k_Faults", "AUS_GA_1M_Faults", 1, 7, False),
}
OTHER_ATTRIBUTION = '<a href="https://www.ga.gov.au/" target="_blank" rel="noopener">© Geoscience Australia</a> (CC BY 4.0)'
#: 다른 서비스 — 레이어 → (`GA_GIS_URL` 밑의 WMS 경로, WMS 레이어, 누르기가 되나, png8 로 받나)
PROVINCES = "services/Australian_Geological_Provinces/MapServer/WMSServer"
CRITICAL = "services/AustralianCriticalMineralsOperatingMinesAndDeposits/MapServer/WMSServer"
GRIDS = "geophysical-grids/ows"
#: 확인 자원(Australia's Identified Mineral Resources 2025, wetherilli 325) — 광종 29 가 WMS 레이어 하나씩. 범례가 광종마다 상태(광상·생산 광산)×
#: 크기 칸이라(모두 257 칸) 광종마다 레이어 하나로 둔다 — 범례 그림이 그 광종의 몇 칸뿐이다
RESOURCES = "services/AustraliasIdentifiedMineralResources/MapServer/WMSServer"
RESOURCE_LAYERS = ("Antimony", "Bauxite", "BlackCoal", "BrownCoal", "Cobalt", "Copper", "Diamond", "Fluorine", "Gold", "Graphite",
                   "HighPurityAluminaOre", "IronOre", "LeadAndZinc", "LithiumTantalumAndNiobium", "Magnesite", "ManganeseOre", "MineralSands",
                   "Molybdenum", "Nickel", "Phosphate", "PlatinumGroupElements", "Potash", "RareEarthElements", "Scandium", "Silver", "Tin",
                   "Tungsten", "Uranium", "Vanadium")
#: 호주 수리지질도(Hydrogeology of Australia, 1:500만 1987 의 수치판) — 대수층의 갈래(공극·균열·국지)와 생산성 (wetherilli 325)
HYDROGEOLOGY = "services/Hydrogeology_of_Australia/MapServer/WmsServer"
OTHER = {
    "ga:crustal": (PROVINCES, "CrustalElements", True, False),
    "ga:provinces": (PROVINCES, "AllProvinces", True, False),
    "ga:mines": (CRITICAL, "OperatingMines,DevelopingMines,CareMaintenanceMines", True, False),
    "ga:deposits": (CRITICAL, "MineralDeposit", True, False),
    "ga:tmi": (GRIDS, "geophys:tmi_hsi_v2_white", False, True),
    "ga:gravity": (GRIDS, "geophys:2019_A4_CBA_wide_linear_color_Hillshade_HSI_GeoTIFF", False, True),
    "ga:radiometric": (GRIDS, "geophys:radmap_v4_2019_filtered_ternary_image", False, True),
    "ga:hydrogeology": (HYDROGEOLOGY, "Hydrogeology", True, False),
    **{f"ga:resource:{name}": (RESOURCES, name, True, False) for name in RESOURCE_LAYERS},
}
#: 지구물리 격자의 값 — 그리는 것은 칠한 그림(HSI·삼색)이라 누르면 RGB 뿐이고, 같은 GeoServer 에 **값 격자**가 따로 있다. 누른 자리를 그것에
#: 묻는다(`GRAY_INDEX`) — 레이어 → [(값 격자, 팝업 이름, 소수 자리)] (wetherilli 336). 중력은 µm/s²(10 µm/s² = 1 mGal) — GA 의 단위다
GRID_VALUES = {
    "ga:gravity": [("geophys:2019_A4_CBA", "완전 부게 중력 이상 (µm/s²)", 1)],
    "ga:tmi": [("geophys:magmap_v7_2019_TMI", "총자력 이상 (nT)", 1)],
    "ga:radiometric": [("geophys:radmap_v4_2019_filtered_pctk", "칼륨 (%)", 2), ("geophys:radmap_v4_2019_filtered_ppmth", "토륨 (ppm)", 1),
                       ("geophys:radmap_v4_2019_filtered_ppmu", "우라늄 (ppm)", 2)],
}
#: 범례가 1:100만 판으로 넘어가는 범위(°) — 1:150만은 화면 줌 8–9 남짓, 화면 너비로 6–8° 다. 그보다 넓으면 1:250만 판의 단위를 센다
FINE_SPAN = 6.0
#: 범례를 뜨는 가장 넓은 범위(°) — 대륙 전체(경도 40°)가 든다. 칸이 많으면 `MAX_LEGEND` 에서 끊는다
SPAN = 45.0
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400


class GaError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS or name in OTHER


def queryable(name: str) -> bool:
    return LAYERS[name][4] if name in LAYERS else name in GRID_VALUES or (name in OTHER and OTHER[name][2])


def legend_layers() -> list:
    return [n for n, spec in LAYERS.items() if spec[4]]


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or not knows(names[0]):
        raise GaError(f"모르는 레이어다: {names}")
    return names[0]


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GaError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ga", ok=False)
        raise GaError(f"Geoscience Australia 에 닿지 못했다: {exc}") from exc
    log.info("GA %s -> %s", r.url, r.status_code)
    usage.record("ga", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _url(name: str) -> str:
    return f"{settings.GA_GIS_URL.rstrip('/')}/{OTHER[name][0]}" if name in OTHER else settings.GA_WMS_URL


def _wms(params: dict, request: str) -> dict:
    name = _one(params)
    if name in OTHER:
        names = OTHER[name][1]
    else:
        spec = LAYERS[name]
        names = f"{spec[0]},{spec[1]}"     # 상류가 축척에 맞는 판을 그린다
    out = dict(params, service="WMS", request=request, layers=names)
    if "query_layers" in out:
        out["query_layers"] = names
    out.setdefault("styles", "")
    if request == "GetMap" and name in OTHER and OTHER[name][3]:
        out["format"] = "image/png8"        # 격자 — PNG 는 512² 한 장이 1 MB
    return out


def get_map(params: dict):
    r = _get(_url(_one(params)), _wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GaError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype.split(";")[0]


def get_legend(layer: str):
    """지질구·핵심 광물은 상류의 범례 그림(WMS GetLegendGraphic, 첫 레이어). 지표 지질도는 보는 범위로만, 격자는 범례가 없다"""
    if layer not in OTHER or OTHER[layer][3]:
        raise GaError("호주 범례는 보는 범위로만 뜬다")
    r = _get(_url(layer), {"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "image/png",
                           "layer": OTHER[layer][1].split(",")[0]})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GaError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    name = _one(params)
    if not queryable(name):
        return {"features": []}
    if name in GRID_VALUES:
        return {"features": _grid_values(name, params)}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    r = _get(_url(name), params)
    if r.status_code != 200:
        raise GaError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise GaError("속성이 JSON 이 아니다") from exc


def _grid_values(name: str, params: dict) -> list:
    """값 격자에 한 번에 묻는다(`query_layers` 여럿) — 바다·자료 밖은 값이 없거나 상류의 빈 값(아주 큰 음수)이라 뺀다"""
    grids = GRID_VALUES[name]
    names = ",".join(g for g, _, _ in grids)
    q = dict(params, service="WMS", request="GetFeatureInfo", layers=names, query_layers=names, styles="",
             info_format="application/json", feature_count=len(grids))
    r = _get(_url(name), q)
    if r.status_code != 200:
        raise GaError(f"값을 읽지 못했다 (status={r.status_code})")
    try:
        found = r.json().get("features") or []
    except ValueError as exc:
        raise GaError("값이 JSON 이 아니다") from exc
    props = {}
    for (grid, label, digits), feature in zip(grids, found):
        value = (feature.get("properties") or {}).get("GRAY_INDEX")
        if isinstance(value, (int, float)) and abs(value) < 1e6:
            props[label] = f"{value:.{digits}f}"
    return [{"id": f"ga.grid.{name}", "properties": dict(props, _grid=name)}] if props else []


def _v(props: dict, key: str) -> str:
    value = str(props.get(key) if props.get(key) is not None else "").strip()
    return "" if value.lower() in ("null", "none") else value


def history(value: str, lang: str = "ko") -> str:
    """GeoSciML 의 시대 글(`Cenozoic to Quaternary`) → `오랜 - 젊은` 꼴로 이어 한국어판이면 옮긴다."""
    text = str(value or "").strip()
    if not text:
        return ""
    joined = " - ".join(p.strip() for p in text.split(" to ") if p.strip())
    return i18n.age_ko(joined) if lang == "ko" else joined


def other_friendly(props: dict, lang: str = "ko"):
    """지질구·핵심 광물(wetherilli 241). 아니면 None"""
    v = lambda k: _v(props, k)          # noqa: E731
    if "_grid" in props:                                                       # 지구물리 격자의 값 (wetherilli 336)
        return {k: x for k, x in props.items() if not k.startswith("_")}
    if "provinceName" in props:
        older, younger = v("olderNameAge"), v("youngerNamedAge")
        age = " - ".join(x for x in (older, younger if younger != older else "") if x) or v("geologicHistory")
        rows = (("이름", v("provinceName")), ("갈래", " · ".join(x for x in (v("type"), v("subtype"), v("rank")) if x)),
                ("상위 단위", v("parentName")), ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
                ("설명", v("description")), ("주", v("state")), ("참고 문헌", v("source")))
    elif "Entity_ID" in props and "CurrentStatus" in props:              # 확인 자원 (wetherilli 325)
        size = " ".join(x for x in (v("Size"), v("Units")) if x)
        rows = (("이름", v("Entity_ID")), ("광종", v("Commodity")), ("운영", v("CurrentStatus")), ("광상 유형", v("MineralDepositType")),
                ("자원량 칸", size), ("주", v("State")), ("출처", v("Source")))
    elif "AQUIF_TY" in props:                                                  # 수리지질도 (wetherilli 325)
        rows = (("대수층", v("AQUIF_TY")), ("갈래", v("TYPE")), ("분포", v("DISTBN")), ("생산성", v("PRODTY")))
    elif "Commodities" in props or "ProjectName" in props:
        rows = (("이름", v("ProjectName")), ("광종", v("Commodities")), ("운영", v("Status")), ("주", v("STATE")))
    else:
        return None
    return {k: x for k, x in rows if x}


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·설명·암상은 영어 그대로, 시대만 옮긴다."""
    other = other_friendly(props, lang)
    if other is not None:
        return other
    v = lambda k: _v(props, k)          # noqa: E731
    scale = v("resolutionScale")
    rows = (("기호", v("mapSymbol") or v("plotSymbol")), ("이름", v("name")), ("설명", v("description")),
            ("지질시대", history(v("geologicHistory"), lang)), ("암석", v("lithology")),
            ("축척", f"1:{int(float(scale)):,}" if scale.replace(".", "", 1).isdigit() else ""))
    return {k: x for k, x in rows if x}


# ── 보는 범위의 범례 — 페루(`ingemmet.py`)와 같은 꼴 ───────────────

def _rest(path: str, params: dict) -> dict:
    r = _get(f"{settings.GA_REST_URL.rstrip('/')}/{path}", dict(params, f="json"))
    try:
        data = r.json()
    except ValueError as exc:
        raise GaError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise GaError(f"REST 오류 (status={r.status_code}): {(data.get('error') or {}).get('message', '')}")
    return data


def renderer(layer_id: int) -> tuple:
    """(색을 가르는 열(소문자), 값 → 색). 칠하기 규칙은 한 번 받아 담는다."""
    key = tilecache.key_text("ga-renderer", str(layer_id))
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        field, table = json.loads(held)
        return field, table
    try:
        r = _rest(str(layer_id), {})["drawingInfo"]["renderer"]
        field, table = str(r.get("field1") or "").lower(), arcpoints.renderer_colors(r)
    except (GaError, KeyError, TypeError):
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            field, table = json.loads(stale)
            return field, table
        raise
    tilecache.put(key, json.dumps([field, table]).encode("utf-8"), ".json")
    return field, table


def rest_layer(name: str, bbox: tuple) -> int:
    """범위의 너비로 판을 고른다 — 상류가 그리는 판과 같게(넓으면 1:250만, 좁으면 1:100만)."""
    spec = LAYERS[name]
    return spec[2] if max(bbox[2] - bbox[0], bbox[3] - bbox[1]) > FINE_SPAN else spec[3]


def extent_legend(name: str, bbox: tuple) -> tuple:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 칸 — (`[{"value", "name", "age", "count"}, …]`, 값 → 색). 면이 많은 것부터."""
    layer_id = rest_layer(name, bbox)
    field, table = renderer(layer_id)
    if not field:
        raise GaError("칠하기 규칙에 열이 없다")
    group = [field] + [f for f in ("name", "geolhist") if f != field]
    data = _rest(f"{layer_id}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": ",".join(group),
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "objectid", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = _v(a, field)
        if not value:
            continue
        count = int(a.get("n") or a.get("N") or 0)
        if value in rows:
            rows[value]["count"] += count
        else:
            rows[value] = {"value": value, "name": _v(a, "name") if field != "name" else "", "age": _v(a, "geolhist"),
                           "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"]), table


def legend_row(row: dict, table: dict, lang: str = "ko") -> dict:
    return {"color": table.get(row["value"], "#cccccc"), "symbol": row["value"], "swatch": "",
            "lithology": f"{row['value']} {row['name']}".strip(), "age": history(row["age"], lang)}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "ga", "tag": "GA", "title": "Geoscience Australia", "relay": True, "projected": True, "globe": True},
]
