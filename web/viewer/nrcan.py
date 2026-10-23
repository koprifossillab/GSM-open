"""NRCan(캐나다 천연자원부)·GSC 로 나가는 문 — 캐나다 지질도 1:500만 (Wheeler 외 1996) (wetherilli 204).

- 주소: `maps-cartes.services.geo.ca/server_serveur/services/NRCan/geological_map_canada_wheeler_en/MapServer/WMSServer` (ArcGIS WMS).
  열쇠가 없다. 레이어는 `0`(지질 단위) 하나 — 이름은 `nrcan:wheeler`
- Capabilities 는 3978·4326 만 적지만 **3857·3413 도 그대로 그린다**(2026-10-04). 캐나다 탭은 3978(캐나다 람베르트)로 받는다 — devlog 204
- 속성은 `application/geojson` — 단위·대/기/세·암상(RXTP·SUBRXTP)·지질구(GEOLPROV), 그리고 같은 것의 프랑스어 짝(ERE·TPRCH…).
  영어 열만 쓴다. 지질시대는 ICS 영어라 한국어판에서 옮긴다
- CORS 는 Origin 을 되비춘다(정적 판에 실을 수 있다 — 기본값에는 넣지 않았다, #153)
- 조건: Open Government Licence – Canada. 출처 "Natural Resources Canada"
- **같은 서버의 다른 서비스**(wetherilli 250) — `SERVICES`: 캐나다 지질도 편찬 CGMC(`cdn_geol_compil_en`, 주·준주 지질도를 모은 **래스터** —
  누르면 칸 번호뿐이라 처음엔 누르지 않았다. **이제 누른다**(wetherilli 320) — REST identify 의 `OBJECTID` 에서 1 을 빼면 REST 범례 34 칸의 차례다
  (`Pixel Value` 는 한 칸이 비어 어긋난다 — 일곱 자리에서 그린 색과 맞대어 보았다)), 핵심 광물 시설(`critical_minerals_en` — 광산·처리 시설·고급 탐사·처리 계획 넷을 한 레이어로),
  광상 유망도 둘(`carbonatite_ree_en` 탄산염암 희토류·`pegmatite_lithium_en` 페그마타이트 리튬 — 딥러닝 모형의 래스터). 지구물리 격자(자력·중력)는
  이 서버에 없고 GSC 의 CAGDB WMS(`wms.agg.nrcan.gc.ca`)는 2026-10-05 에 60 초 안에 답하지 않았다. **이 서버는 느리다** — 2026-10-05 에
  대륙 한 장이 40–77 초, Wheeler 도 13 초였다
- **북극 지질도 1:500만**(GSC Open File 5816, Harrison 외 2008 — CGMW 협력, wetherilli 414) — `international_polar_year_en`. 60°N 북쪽의
  육상 셋(캐나다·미국 0, 그린란드 2, 북유럽·러시아 3)과 해저 1 을 레이어 하나(`nrcan:arctic`)로 부른다 — 해저를 맨 밑에. 원본은 3978 이고
  Capabilities 도 3978·4326 만 적지만 **3413 으로 곧장 그려 준다**(2026-10-22) — 북극 탭의 투영 그대로 받는다. 넓으면 느리다(3413 의 1 000 km 칸
  3 초, 2 000 km 7 초, 4 000 km 31 초). 칠하기는 `COLOUR` 의 고유값 210 칸이고 이름표가 `MAP_LABEL` 기호뿐이라 범례 그림은 읽히지 않는다 —
  **보는 범위의 범례**를 REST 통계로 뜨고 색은 레이어의 칠하기 규칙에서 찾는다(`arctic_legend`). 시대(`AGE_DESCRI`)는 "고원생대 중기 및 후기
  (… ) (2050 - 1600 Ma)" 꼴이라 괄호를 떼어 옮긴다(`arctic_age`)
"""
import json
import logging
import re

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

LAYERS = {"nrcan:wheeler": "0"}
#: 다른 서비스 — 레이어 → (서비스 이름, WMS 레이어, 누르기가 되나) (wetherilli 250)
SERVICES = {
    "nrcan:cgmc": ("cdn_geol_compil_en", "0", True),               # 래스터 — 누르면 REST identify 로 칸을 읽고 범례로 풀어 낸다 (wetherilli 320)
    "nrcan:critical": ("critical_minerals_en", "0,1,2,3", True),
    "nrcan:ree": ("carbonatite_ree_en", "0", False),
    "nrcan:lithium": ("pegmatite_lithium_en", "0", False),
    "nrcan:arctic": ("international_polar_year_en", "1,0,2,3", True),   # 북극 지질도 — 해저 1 을 맨 밑에 (wetherilli 414)
}
OTHER_ATTRIBUTION = ('<a href="https://open.canada.ca/en/open-government-licence-canada" target="_blank" rel="noopener">'
                     "Natural Resources Canada, OGL–Canada</a>")
ARCTIC_ATTRIBUTION = ('Geological Map of the Arctic 1:5M (Harrison et al. 2008, GSC Open File 5816) — '
                      '<a href="https://open.canada.ca/en/open-government-licence-canada" target="_blank" rel="noopener">'
                      "Natural Resources Canada, OGL–Canada</a>")
ATTRIBUTION = ('Geological Map of Canada 1:5M (Wheeler et al. 1996) — <a href="https://open.canada.ca/en/open-government-licence-canada" '
               'target="_blank" rel="noopener">Natural Resources Canada, OGL–Canada</a>')
TIMEOUT = 45


class NrcanError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS or name in SERVICES


def queryable(name: str) -> bool:
    return name in LAYERS or (name in SERVICES and SERVICES[name][2])


def _service_of(names: str) -> str:
    """요청 하나는 서비스 하나로만 간다 — Wheeler 면 빈 글"""
    found = {SERVICES[n.strip()][0] if n.strip() in SERVICES else "" for n in str(names or "").split(",") if n.strip()}
    if len(found) != 1:
        raise NrcanError("서비스가 다른 레이어를 한 번에 물을 수 없다")
    return found.pop()


def _numbers(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if one in SERVICES:
            out.append(SERVICES[one][1])
            continue
        if one not in LAYERS:
            raise NrcanError(f"모르는 레이어다: {one}")
        out.append(LAYERS[one])
    return ",".join(out)


def _url(service: str = "") -> str:
    if not service:
        return settings.NRCAN_WMS_URL
    return settings.NRCAN_WMS_URL.split("/NRCan/", 1)[0] + f"/NRCan/{service}/MapServer/WMSServer"


def _get(params: dict, service: str = ""):
    left = usage.paused()
    if left:
        raise NrcanError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(_url(service), params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("nrcan", ok=False)
        raise NrcanError(f"NRCan 에 닿지 못했다: {exc}") from exc
    log.info("NRCan %s -> %s", r.url, r.status_code)
    usage.record("nrcan", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.3.0")
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params["layers"] = _numbers(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _numbers(params["query_layers"])
    params.setdefault("styles", "")
    return params


def get_map(params: dict):
    service = _service_of(params.get("layers"))
    r = _get(_wms(params, "GetMap"), service)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NrcanError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0", "format": "image/png",
              "layer": _numbers(layer).split(",")[0], "sld_version": "1.1.0"}, _service_of(layer))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NrcanError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


#: CGMC 범례(암상 34 칸)를 담아 두는 날
CGMC_TABLE_SECONDS = 30 * 86400


def _rest(service: str) -> str:
    return settings.NRCAN_WMS_URL.split("/services/", 1)[0] + f"/rest/services/NRCan/{service}/MapServer"


def _rest_get(service: str, path: str, params: dict, post: bool = False):
    """`post` — 모양이 긴 질의(북극 지질도의 범위 고리)는 주소가 길어 GET 이 404 다"""
    left = usage.paused()
    if left:
        raise NrcanError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        if post:
            r = requests.post(f"{_rest(service)}/{path}", data=dict(params, f="json"), timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                              verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
        else:
            r = requests.get(f"{_rest(service)}/{path}", params=dict(params, f="json"), timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                             verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("nrcan", ok=False)
        raise NrcanError(f"NRCan 에 닿지 못했다: {exc}") from exc
    log.info("NRCan REST %s -> %s", r.url, r.status_code)
    usage.record("nrcan", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise NrcanError(f"REST 가 답하지 않았다 (status={r.status_code})")
    try:
        return r.json()
    except ValueError as exc:
        raise NrcanError("REST 가 JSON 이 아니다") from exc


def cgmc_classes() -> list:
    """CGMC 의 암상 34 칸 — REST 범례의 차례 그대로. 한 번 받아 캐시에 30 일"""
    from . import tilecache
    key = tilecache.key_text("nrcan-cgmc-classes", SERVICES["nrcan:cgmc"][0])
    held = tilecache.get(key, ".json", max_age=CGMC_TABLE_SECONDS)
    if held is not None:
        return json.loads(held)
    layers = _rest_get(SERVICES["nrcan:cgmc"][0], "legend", {}).get("layers") or []
    labels = [str(row.get("label") or "").strip() for row in (layers[0].get("legend") or [])] if layers else []
    if not labels:
        raise NrcanError("CGMC 범례가 비었다")
    tilecache.put(key, json.dumps(labels, ensure_ascii=False).encode("utf-8"), ".json")
    return labels


# ── 북극 지질도의 범례 (wetherilli 414) ───────────────────────────

ARCTIC_SERVICE = SERVICES["nrcan:arctic"][0]
ARCTIC_LAYERS = (1, 0, 2, 3)
#: 범례에 적는 칸 수 — 나머지는 "그 밖 n칸"
MAX_LEGEND = 60


def arctic_colors() -> dict:
    """`COLOUR` 값 → 칠한 색(#rrggbb). 네 레이어의 칠하기 규칙을 한 번 받아 캐시에 30 일 — 같은 값은 같은 색이다"""
    from . import tilecache
    key = tilecache.key_text("nrcan-arctic-colors", ARCTIC_SERVICE)
    held = tilecache.get(key, ".json", max_age=CGMC_TABLE_SECONDS)
    if held is not None:
        return json.loads(held)
    table = {}
    for number in ARCTIC_LAYERS:
        renderer = ((_rest_get(ARCTIC_SERVICE, str(number), {}).get("drawingInfo") or {}).get("renderer") or {})
        for info in renderer.get("uniqueValueInfos") or []:
            rgba = (info.get("symbol") or {}).get("color") or []
            if len(rgba) >= 3 and str(info.get("value")) not in table:
                table[str(info.get("value"))] = "#%02x%02x%02x" % tuple(int(v) for v in rgba[:3])
    if not table:
        raise NrcanError("북극 지질도의 칠하기 규칙이 비었다")
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def _ring(bbox: tuple, steps: int = 24) -> list:
    """위경도 네모를 촘촘한 고리로 — 3978 로 옮겨도 극 둘레에서 모서리 넷만 옮긴 네모처럼 찌그러지지 않게"""
    west, south, east, north = bbox
    edge = lambda a, b, n: [round(a + (b - a) * k / n, 4) for k in range(n)]   # noqa: E731
    return ([[x, south] for x in edge(west, east, steps)] + [[east, y] for y in edge(south, north, steps)]
            + [[x, north] for x in edge(east, west, steps)] + [[west, y] for y in edge(north, south, steps)] + [[west, south]])


def arctic_legend(bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"symbol", "colour", "age", "lithology", "area"}, …]`, 넓은 것부터.
    넓이는 범위에 걸친 면 전체의 것이다(잘라 재지 않는다) — 차례를 정하는 데만 쓴다"""
    geometry = json.dumps({"rings": [_ring(bbox)], "spatialReference": {"wkid": 4326}})
    rows = {}
    for number in ARCTIC_LAYERS:
        data = _rest_get(ARCTIC_SERVICE, f"{number}/query", {
            "geometry": geometry, "geometryType": "esriGeometryPolygon", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "groupByFieldsForStatistics": "MAP_LABEL,COLOUR,AGE_DESCRI,LITHOLOGY", "returnGeometry": "false",
            "outStatistics": json.dumps([{"statisticType": "sum", "onStatisticField": "Shape_Area", "outStatisticFieldName": "area"}])},
            post=True)
        if data.get("error"):
            raise NrcanError(f"REST 오류: {(data.get('error') or {}).get('message', '')}")
        for f in data.get("features") or []:
            a = f.get("attributes") or {}
            symbol = str(a.get("MAP_LABEL") or "").strip()
            if not symbol:
                continue
            key = (symbol, str(a.get("COLOUR") or "").strip())
            area = float(a.get("area") or a.get("AREA") or 0)
            if key in rows:
                rows[key]["area"] += area
            else:
                rows[key] = {"symbol": symbol, "colour": key[1], "area": area,
                             "age": str(a.get("AGE_DESCRI") or "").strip(), "lithology": str(a.get("LITHOLOGY") or "").strip()}
    return sorted(rows.values(), key=lambda r: -r["area"])


def legend_row(row: dict, colors: dict, lang: str = "ko") -> dict:
    return {"symbol": row["symbol"], "lithology": f"{row['symbol']} {row['lithology']}".strip(),
            "color": colors.get(row["colour"], "transparent"), "age": arctic_age(row["age"], lang)}


_AGE_SPAN = re.compile(r"^(?P<head>.*?)\s*\((?P<old>[\d.]+)\s*-\s*(?P<young>[\d.]+)\s*Ma\)\s*$")
_AGE_STAGES = re.compile(r"^(?P<head>.*?)\s*\((?P<stages>[^()]+)\)\s*$")


def arctic_age(text: str, lang: str = "ko") -> str:
    """`middle and late Paleoproterozoic (Orosirian and Statherian) (2050 - 1600 Ma)` → `고원생대 중기 및 후기 (오로세이라기 및 스타테로스기)
    (2050–1600 Ma)`. 시대 낱말을 못 옮기는 조각은 원문 그대로 둔다. `… and younger` 는 "… 이후" 다"""
    text = str(text or "").strip()
    if lang != "ko" or not text:
        return text
    span = ""
    m = _AGE_SPAN.match(text)
    if m:
        text, span = m.group("head"), f"{m.group('old')}–{m.group('young')} Ma"
    stages = ""
    m = _AGE_STAGES.match(text)
    if m:
        text, stages = m.group("head"), i18n.age_ko(m.group("stages").strip())
    later = text.lower().endswith(" and younger")
    if later:
        text = text[: -len(" and younger")]
    head = i18n.age_ko(text)
    if later:
        head = f"{head} 이후"
    return " ".join(x for x in (head, f"({stages})" if stages else "", f"({span})" if span else "") if x)


def _clicked(params: dict):
    """WMS 의 범위·크기·픽셀 → 그 투영의 (x, y)와 EPSG 번호. WMS 1.3.0 의 4326 은 위도가 먼저다"""
    crs = str(params.get("crs") or params.get("srs") or "EPSG:3978").upper()
    bbox = [float(v) for v in str(params.get("bbox") or "").split(",")]
    width, height = float(params.get("width") or 256), float(params.get("height") or 256)
    i = float(params.get("i", params.get("x", 0)))
    j = float(params.get("j", params.get("y", 0)))
    if crs == "EPSG:4326" and str(params.get("version") or "1.3.0") == "1.3.0":
        bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]
    west, south, east, north = bbox
    x = west + (i + 0.5) * (east - west) / width
    y = north - (j + 0.5) * (north - south) / height
    return x, y, crs.split(":")[-1].replace("CRS84", "4326"), (west, south, east, north), (int(width), int(height))


def _cgmc_info(params: dict) -> dict:
    x, y, sr, extent, size = _clicked(params)
    data = _rest_get(SERVICES["nrcan:cgmc"][0], "identify", {
        "geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": sr, "layers": "all", "tolerance": "0",
        "mapExtent": ",".join(repr(v) for v in extent), "imageDisplay": f"{size[0]},{size[1]},96", "returnGeometry": "false"})
    out = []
    for res in data.get("results") or []:
        attrs = res.get("attributes") or {}
        try:
            index = int(str(attrs.get("OBJECTID"))) - 1
        except ValueError:
            continue                                       # 칸이 없는 자리(NoData)
        labels = cgmc_classes()
        if 0 <= index < len(labels):
            out.append({"id": f"nrcan.cgmc.{index}", "properties": {"cgmc_lithology": labels[index]}})
    return {"features": out[:1]}


def get_feature_info(params: dict) -> dict:
    names = params.get("query_layers") or params.get("layers")
    if not all(queryable(n.strip()) for n in str(names or "").split(",") if n.strip()):
        return {"features": []}
    if str(names).strip() == "nrcan:cgmc":
        return _cgmc_info(params)
    service = _service_of(names)
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    if "x" in params and "i" not in params:
        params["i"], params["j"] = params.pop("x"), params.pop("y", "0")
    r = _get(params, service)
    if r.status_code != 200:
        raise NrcanError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise NrcanError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업 이름. 적은 것만, 적은 차례로. 프랑스어 짝(UNITE·ERE·TPRCH …)은 뺀다
FRIENDLY = (
    ("UNIT", "기호"),
    ("NAME", "이름"),
    ("RXTP", "암석"),
    ("SUBRXTP", "암석 갈래"),
    ("AGERXTP", "시대별 암석"),
    ("EPOCH", "지질시대"),
    ("PERIOD", "지질시대"),
    ("ERA", "지질시대"),
    ("METGRADE", "변성 정도"),
    ("GEOLPROV", "지질구"),
    ("DOMAIN", "영역"),
    ("COMP", "편집"),
)
AGE_KEYS = ("EPOCH", "PERIOD", "ERA")


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 지질시대는 가장 잘게 가른 것(세 > 기 > 대) 하나이고 한국어판이면 ICS 이름을 옮긴다."""
    if "cgmc_lithology" in props:               # 편찬 지질도 CGMC 의 칸 (wetherilli 320) — 암상은 상류의 영어 그대로
        return {"암상": props["cgmc_lithology"]}
    if "IPY_CODE" in props:                     # 북극 지질도 (wetherilli 414) — 암상·지구조는 영어 그대로, 시대만 옮긴다
        v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
        domain = " · ".join(x for x in dict.fromkeys((v("DOMAIN_R_1"), v("DOMAIN_R_2"), v("DOMAIN_R_3"))) if x)
        rows = (("기호", v("MAP_LABEL")), ("지질시대", arctic_age(v("AGE_DESCRI"), lang)), ("암석", v("LITHOLOGY")),
                ("환경", v("SETTING")), ("변성 정도", "" if v("METAMORPHI") == "Not known" else v("METAMORPHI")),
                ("지구조 구역", domain), ("출처 지역", v("SOURCE_LOC")), ("편집", v("COMPILATIO")))
        return {k: x for k, x in rows if x}
    if "Property Name" in props:                # 핵심 광물 시설 (wetherilli 250)
        v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
        site = v("Website")
        rows = (("이름", v("Property Name")), ("갈래", v("Operation Group")), ("광종", v("Commodities")),
                ("개발 단계", v("Development Stage")), ("운영", v("Activity Status")), ("운영사", v("Operator Owners")),
                ("주", v("Province/Territory")),
                ("누리집", {"text": "", "links": [{"url": site, "label": "열기"}]} if site.startswith(("http://", "https://")) else ""))
        return {k: x for k, x in rows if x}
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or label in out:
            continue
        out[label] = i18n.age_ko(value) if key in AGE_KEYS and lang == "ko" else value
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "nrcan", "tag": "NRCan", "title": "캐나다 천연자원부", "relay": True, "projected": True, "globe": True},
]
