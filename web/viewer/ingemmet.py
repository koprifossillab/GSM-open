"""INGEMMET(페루 지질광업야금연구소)로 나가는 문 — 페루 지질도 (wetherilli 195).

- 주소: `geocatmin.ingemmet.gob.pe/arcgis/rest/services/<판>/MapServer` (GEOCATMIN, ArcGIS). 판은 둘 —
  `SERV_GEOLOGIA_50K_INTEGRADA`(1:5만 통합판, 2005–2011 갱신, 폴리곤 15 만 7 천 — 남미에서 가장 자세한 전국판)·
  `SERV_GEOLOGIA_100K_INTEGRADA`(1:10만 통합판). 열쇠가 없다
- **그림은 REST 의 타일 캐시로 받는다**(`tile/{z}/{y}/{x}`, 3857 256 px). WMS 로 넓게 물으면 한 장에 30–46 초다(2026-10-04 — 페루 전체
  줌 5 에서 1:5만 46 초, 1:10만 33 초). 캐시는 줌과 상관없이 한 장에 1.3–1.8 초다. 캐시는 1:5만이 줌 13, 1:10만이 줌 16 까지 있고 그 너머는
  화면이 늘린다. 캐시는 그 판의 모든 레이어(암상·단층·습곡 …)를 한 장에 구운 것이다
- **누른 자리는 REST `query`** — 그 점을 품은 면을 기하 없이 묻는다. WMS 속성의 이름은 REST 번호를 뒤집었고(WMS `0` = REST `7`) 열 이름도
  조금 다르다(`TIP_UNIDAD`·`TIPO_UNIDAD`) — REST 하나로 맞춘다. 빈 값이 `" "`·`"<Null>"` 로 온다
- **범례는 보는 범위의 것** — REST 범례는 1:5만 암상만 3 261 칸이다. 범위 안의 단위는 통계 질의(`groupByFieldsForStatistics` + 개수)로 받고
  (리마 둘레 57 줄·9 KB·2 초), 색은 레이어 정보의 칠하기 규칙(`drawingInfo.renderer`, 1:5만 880 KB)에서 찾는다. 규칙은 한 번 받아 담는다
- **단층·습곡은 따로 켠다**(wetherilli 222) — 통합판 캐시에는 단층·습곡이 구워져 있어 끌 수 없다. 같은 GEOCATMIN 의
  `SERV_GEOLOGIA_FALLAS`(1:100만 단층, 1:10만·1:5만 단층·습곡, 캐시 없음)를 REST `export` 로 타일 칸만큼(256 px) 받는다 — 한 장에
  1.5–2 초(2026-10-04). 통합판 서비스의 단층·습곡 레이어는 1:50만보다 넓으면 빈 그림이라(`minScale`) 쓰지 않는다. 주소는 지질도와 같은
  `ingemmet/<이름>/{z}/{x}/{y}.png` 다. 선이라 누르지 않고 범례도 두지 않는다
- **1:5만 지질 단위만**(wetherilli 234) — 통합판 캐시에는 단층·습곡이 구워져 끌 수 없어, 같은 서비스의 암상 레이어(7)만 `export` 로
  타일 칸만큼 받는 판을 따로 둔다(`UNITS`). 한 칸이 줌 7 에 5 초·줌 9 에 2.6 초·줌 11 에 1.7 초라(222 에서 쟀다) 줌 9 부터 그린다.
  누른 자리·범례는 1:5만 통합판의 것을 그대로 쓴다(`base_of`)
- **광물·지구물리**(wetherilli 277) — GEOCATMIN 의 다른 서비스 넷을 단층·습곡처럼 `export` 로 타일 칸만큼 받는다(`RESOURCES`).
  광물 산지(`SERV_OCURRENCIA_MINERAL`, 금속 1 859·비금속 686, 4326 서비스 — 남위 10–18° 의 연구 띠만 덮는다)·광상과 사업
  (`SERV_METALOGENETICO` 의 1·0 — 한 표를 둘로 거른 것)·금속 광화대(같은 서비스 4, 면 66)·부게 이상(`SERV_GEOFISICA` 5, 래스터)과
  항공 자력(`SERV_AEROMAGNETIICO`, ImageServer — 흰 바탕이라 `noData=255,255,255` 로 비운다). 한 칸이 2–3 초다(2026-10-05).
  누른 자리는 REST `query` 다 — 점은 누른 둘레(`r`°)의 네모로, 면은 그 점으로. 페이지 나눔을 받지 않아 `resultRecordCount` 를 붙이지 않는다
- 지질시대는 에스파냐어다(`Cretácico`). ICS 영문 이름으로 옮긴 뒤 한국어판이면 `i18n.age_ko` 로 한 번 더 옮긴다
- 조건: Capabilities 의 AccessConstraints 는 `referencial`. GEOCATMIN 이용 허락은 INGEMMET 를 출처로 밝히면 쓰기·옮기기를 허락하고,
  메타데이터에 **CC BY-NC-SA 4.0** 이 붙어 있다 — 비상업. 정적 판에는 싣지 않는다
"""
import json
import logging
import math

import requests
from django.conf import settings

from . import arcpoints, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "ingemmet:"
ATTRIBUTION = ('<a href="https://geocatmin.ingemmet.gob.pe/" target="_blank" rel="noopener">INGEMMET</a> '
               "(GEOCATMIN, CC BY-NC-SA 4.0)")

#: 레이어 → 판의 서비스, 캐시의 마지막 줌, 단위 면의 REST 번호, 색을 가르는 열, 범례에 실을 열, 범례를 뜨는 가장 넓은 범위(°)
LAYERS = {
    "ingemmet:50k": {"service": "SERV_GEOLOGIA_50K_INTEGRADA", "max": 13, "units": 7, "by": "CODI",
                     "label": ("ETIQUETA", "UNIDAD", "SISTEMA_MAX", "SISTEMA_MIN"), "span": 4},
    "ingemmet:100k": {"service": "SERV_GEOLOGIA_100K_INTEGRADA", "max": 16, "units": 6, "by": "NAME",
                      "label": ("NAME", "UNIDAD"), "span": 6},
}
#: 단층·습곡(wetherilli 222) → `SERV_GEOLOGIA_FALLAS` 의 레이어 번호, 처음 그리는 줌. 1:10만·1:5만은 넓게 보면 새카맣다
STRUCTURES = {
    "ingemmet:faults_1m": {"show": 0, "min": None},
    "ingemmet:faults_100k": {"show": 2, "min": 8},
    "ingemmet:folds_100k": {"show": 3, "min": 8},
    "ingemmet:faults_50k": {"show": 5, "min": 9},
    "ingemmet:folds_50k": {"show": 6, "min": 9},
}
STRUCTURES_SERVICE = "SERV_GEOLOGIA_FALLAS"
#: 지질 단위만의 판(wetherilli 234) → 바탕 통합판, 그 서비스의 암상 레이어 번호, 처음 그리는 줌
UNITS = {
    "ingemmet:50k_units": {"base": "ingemmet:50k", "show": 7, "min": 9},
}
#: 광물·지구물리(wetherilli 277) → 서비스, 레이어 번호(ImageServer 는 None), 처음 그리는 줌, 누를 때의 꼴(점·면·None), 받을 열
RESOURCES = {
    "ingemmet:occ_metal": {"service": "SERV_OCURRENCIA_MINERAL", "show": 0, "min": 7, "query": "point",
                           "fields": "NOMBRE,ELEMENTO,TIPO_DEPOS,EDAD,FORMACION,FRANJA,LINK"},
    "ingemmet:occ_nonmetal": {"service": "SERV_OCURRENCIA_MINERAL", "show": 1, "min": 7, "query": "point",
                              "fields": "NOMBRE,ELEMENTO,TIPO_DEPOS,EDAD,FORMACION,FRANJA,LINK"},
    "ingemmet:deposits": {"service": "SERV_METALOGENETICO", "show": 1, "min": 7, "query": "point",
                          "fields": "UNIDAD,ELE_PRINC,ESTADO,COD_TIPO,ST_YACIM,FRANJAMET,RECURSO,ALTITUD,LOCALIDAD,HOJA"},
    "ingemmet:projects": {"service": "SERV_METALOGENETICO", "show": 0, "min": 7, "query": "point",
                          "fields": "UNIDAD,ELE_PRINC,ESTADO,COD_TIPO,ST_YACIM,FRANJAMET,RECURSO,ALTITUD,LOCALIDAD,HOJA"},
    "ingemmet:belts": {"service": "SERV_METALOGENETICO", "show": 4, "min": None, "query": "polygon",
                       "fields": "FRANJA,ETIQUETA,TIPO"},
    "ingemmet:bouguer": {"service": "SERV_GEOFISICA", "show": 5, "min": None, "query": None},
    "ingemmet:aeromag": {"service": "SERV_AEROMAGNETIICO", "show": None, "min": None, "query": None},
}
#: 단층·습곡을 그리는 마지막 줌 — 캐시가 아니라 그때그때 그리므로 상류가 정한 끝이 없다
STRUCTURES_MAX = 18
#: 범례 칸을 몇 개까지 싣나
MAX_LEGEND = 60
#: 칠하기 규칙(색 표)을 담아 두는 날 — 판이 바뀔 일이 드물다
COLORS_MAX_AGE = 30 * 86400


class IngemmetError(RuntimeError):
    pass


def knows(name: str) -> bool:
    """지질도(통합판) — 누른 자리·범례가 있는 것. 단층·습곡은 `knows_tiles` 만 안다"""
    return name in LAYERS


def knows_tiles(name: str) -> bool:
    return name in LAYERS or name in STRUCTURES or name in UNITS or name in RESOURCES


def knows_resource(name: str) -> bool:
    """광물·지구물리 가운데 누를 수 있는 것 (wetherilli 277)"""
    return bool(RESOURCES.get(name, {}).get("query"))


def base_of(name: str) -> str:
    """누른 자리·범례를 물을 판 — 지질 단위만의 판은 바탕 통합판의 것을 쓴다 (wetherilli 234)."""
    return UNITS[name]["base"] if name in UNITS else name


def first_zoom(name: str):
    """화면이 처음 그리는 줌 — 단층·습곡과 지질 단위만의 판. 통합판은 None"""
    return (STRUCTURES.get(name) or UNITS.get(name) or RESOURCES.get(name) or {}).get("min")


def max_zoom(name: str) -> int:
    return LAYERS[name]["max"] if name in LAYERS else STRUCTURES_MAX


def sheet_of(name: str) -> str:
    """`ingemmet:50k` → `50k` — 타일 주소의 이름."""
    return name[len(PREFIX):]


def valid_tile(name: str, z: int, x: int, y: int) -> bool:
    return knows_tiles(name) and 0 <= z <= max_zoom(name) and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def _base(name: str) -> str:
    return f"{settings.INGEMMET_URL.rstrip('/')}/{LAYERS[name]['service']}/MapServer"


def _get(url: str, params=None):
    left = usage.paused()
    if left:
        raise IngemmetError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ingemmet", ok=False)
        raise IngemmetError(f"INGEMMET 에 닿지 못했다: {exc}") from exc
    log.info("INGEMMET %s -> %s", r.url, r.status_code)
    # 캐시 밖의 타일은 404 다 — 차단이 아니다
    usage.record("ingemmet", ok=r.status_code in (200, 404), blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def get_tile(name: str, z: int, x: int, y: int):
    """캐시 타일 한 장(PNG). 캐시 밖(바다·나라 밖·마지막 줌 너머)이면 None — 화면에는 빈 타일이 선다."""
    if not valid_tile(name, z, x, y):
        raise IngemmetError("그런 타일은 없다")
    if name in STRUCTURES:
        return structure_tile(name, z, x, y)
    if name in UNITS:
        return units_tile(name, z, x, y)
    if name in RESOURCES:
        return resource_tile(name, z, x, y)
    r = _get(f"{_base(name)}/tile/{z}/{y}/{x}")
    if r.status_code == 404:
        return None
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IngemmetError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def tile_bbox(z: int, x: int, y: int) -> tuple:
    """z/x/y 칸의 3857 범위 (서, 남, 동, 북)."""
    half = 20037508.342789244
    size = 2 * half / 2 ** z
    return (-half + x * size, half - (y + 1) * size, -half + (x + 1) * size, half - y * size)


def _export_tile(base: str, show: int, z: int, x: int, y: int) -> bytes:
    r = _get(f"{base}/export", {"bbox": ",".join(f"{v:.3f}" for v in tile_bbox(z, x, y)), "bboxSR": 3857,
                                "imageSR": 3857, "size": "256,256", "dpi": 96, "format": "png32", "transparent": "true",
                                "layers": f"show:{show}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IngemmetError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def structure_tile(name: str, z: int, x: int, y: int) -> bytes:
    """단층·습곡 한 칸 — `SERV_GEOLOGIA_FALLAS` 의 `export` 를 타일 칸만큼. 선이 없는 칸은 투명한 그림이 온다."""
    return _export_tile(f"{settings.INGEMMET_URL.rstrip('/')}/{STRUCTURES_SERVICE}/MapServer", STRUCTURES[name]["show"], z, x, y)


def _service(name: str) -> str:
    spec = RESOURCES[name]
    kind = "MapServer" if spec["show"] is not None else "ImageServer"
    return f"{settings.INGEMMET_URL.rstrip('/')}/{spec['service']}/{kind}"


def resource_tile(name: str, z: int, x: int, y: int) -> bytes:
    """광물·지구물리 한 칸 (wetherilli 277) — MapServer 는 `export`, 항공 자력(ImageServer)은 흰 바탕을 비운 `exportImage`."""
    spec = RESOURCES[name]
    if spec["show"] is not None:
        return _export_tile(_service(name), spec["show"], z, x, y)
    r = _get(f"{_service(name)}/exportImage", {"bbox": ",".join(f"{v:.3f}" for v in tile_bbox(z, x, y)), "bboxSR": 3857,
                                               "imageSR": 3857, "size": "256,256", "format": "png32", "noData": "255,255,255",
                                               "noDataInterpretation": "esriNoDataMatchAll", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IngemmetError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def resource_attributes(name: str, lat: float, lon: float, radius: float) -> list:
    """누른 자리의 광물 산지·광상(둘레 `radius`° 네모, 가까운 것부터 셋) 또는 광화대(그 점을 품은 면) — 열 이름 그대로."""
    spec = RESOURCES[name]
    if spec["query"] == "point":
        r = max(1e-4, min(0.5, radius))
        geometry = {"geometry": f"{lon - r},{lat - r},{lon + r},{lat + r}", "geometryType": "esriGeometryEnvelope"}
    else:
        geometry = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint"}
    res = _get(f"{_service(name)}/{spec['show']}/query", dict(geometry, inSR="4326", outSR="4326",
               spatialRel="esriSpatialRelIntersects", outFields=spec["fields"], returnGeometry="true" if spec["query"] == "point" else "false",
               f="json"))
    if res.status_code != 200:
        raise IngemmetError(f"질의를 읽지 못했다 (status={res.status_code})")
    try:
        data = res.json()
    except ValueError as exc:
        raise IngemmetError("질의가 JSON 이 아니다") from exc
    if data.get("error"):
        raise IngemmetError(f"질의 오류: {data['error'].get('message', '')}")
    feats = data.get("features") or []

    def away(f):
        g = f.get("geometry") or {}
        return (g.get("x", lon) - lon) ** 2 + (g.get("y", lat) - lat) ** 2
    return [f.get("attributes") or {} for f in sorted(feats, key=away)[:3]]


def resource_friendly(name: str, props: dict, lang: str = "ko") -> dict:
    """광물·지구물리의 열 → 한국어 이름. 값은 에스파냐어 그대로다 (wetherilli 277)"""
    v = lambda k: _clean(props.get(k))          # noqa: E731
    if name == "ingemmet:belts":
        rows = (("이름", v("FRANJA")), ("기호", v("ETIQUETA")), ("갈래", v("TIPO")))
    elif name.startswith("ingemmet:occ_"):
        link = v("LINK")
        rows = (("이름", v("NOMBRE")), ("광종", v("ELEMENTO")), ("광상 형태", v("TIPO_DEPOS")), ("지층", v("FORMACION")),
                ("시대 기호", v("EDAD")), ("광화 지역", v("FRANJA")),
                ("상세", {"text": "", "links": [{"url": link, "label": "열기"}]} if link.startswith(("http://", "https://")) else ""))
    else:
        rows = (("이름", v("UNIDAD")), ("광종", v("ELE_PRINC")), ("개발 단계", v("ESTADO")), ("갈래", v("COD_TIPO")),
                ("광상 형태", v("ST_YACIM")), ("광화 지역", v("FRANJAMET")), ("자원량", v("RECURSO")),
                ("표고 (m)", v("ALTITUD")), ("곳", v("LOCALIDAD")), ("도폭", v("HOJA")))
    return {k: x for k, x in rows if x}


def units_tile(name: str, z: int, x: int, y: int) -> bytes:
    """지질 단위만 한 칸 — 바탕 통합판 서비스의 암상 레이어만 `export` 로 (wetherilli 234)."""
    spec = UNITS[name]
    return _export_tile(_base(spec["base"]), spec["show"], z, x, y)


# `_Door` 가 문마다 셋을 찾는다. 그림은 타일 캐시(`get_tile`)로, 속성·범례는 아래 함수로 가므로 WMS 길은 쓰지 않는다
def get_map(params: dict):
    raise IngemmetError("페루 지질도는 타일 캐시로 그린다")


def get_legend(layer: str):
    raise IngemmetError("페루 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    raise IngemmetError("페루 속성은 누른 자리로 묻는다")


def _query(name: str, params: dict) -> dict:
    r = _get(f"{_base(name)}/{LAYERS[name]['units']}/query", dict(params, f="json"))
    if r.status_code != 200:
        raise IngemmetError(f"질의를 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise IngemmetError("질의가 JSON 이 아니다") from exc
    if data.get("error"):
        raise IngemmetError(f"질의 오류: {data['error'].get('message', '')}")
    return data


def point_attributes(name: str, lat: float, lon: float):
    """누른 자리의 면 하나 — 열 이름 그대로의 속성. 없으면 None."""
    data = _query(name, {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
                         "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false"})
    feats = data.get("features") or []
    return (feats[0].get("attributes") or {}) if feats else None


def colors(name: str) -> dict:
    """색을 가르는 열의 값 → `#rrggbb`. 레이어 정보의 칠하기 규칙에서 뜬다. 한 번 받아 담는다."""
    key = tilecache.key_text("ingemmet-colors", name)
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _get(f"{_base(name)}/{LAYERS[name]['units']}", {"f": "json"})
    try:
        renderer = r.json()["drawingInfo"]["renderer"]
    except (ValueError, KeyError, TypeError) as exc:
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise IngemmetError("칠하기 규칙을 읽지 못했다") from exc
    table = arcpoints.renderer_colors(renderer)
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def extent_legend(name: str, bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"value", "fields", "count"}, …]`, 면이 많은 것부터."""
    spec = LAYERS[name]
    by = (spec["by"],) + tuple(f for f in spec["label"] if f != spec["by"])
    data = _query(name, {"geometry": ",".join(f"{v}" for v in bbox), "geometryType": "esriGeometryEnvelope",
                         "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                         "groupByFieldsForStatistics": ",".join(by),
                         "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID",
                                                       "outStatisticFieldName": "n"}]),
                         "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = str(a.get(spec["by"]) if a.get(spec["by"]) is not None else "").strip()
        if not value:
            continue
        # 개수 열은 상류가 큰 글자로 돌려준다(`N`). 같은 값이 열 차이로 둘이 되면 더한다
        count = int(a.get("n") or a.get("N") or 0)
        if value in rows:
            rows[value]["count"] += count
        else:
            rows[value] = {"value": value, "fields": {k: _clean(a.get(k)) for k in spec["label"]}, "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(name: str, row: dict, table: dict, lang: str = "ko") -> dict:
    """화면이 그리는 한 칸 — 일본(GSJ)·대만·브라질의 칸과 같은 이름이다."""
    f = row["fields"]
    symbol = f.get("ETIQUETA") or f.get("NAME") or row["value"]
    unit = f.get("UNIDAD", "")
    return {"color": table.get(row["value"], "#cccccc"), "symbol": symbol, "swatch": "",
            "lithology": f"{symbol} {unit}".strip(),
            "age": _span(f.get("SISTEMA_MAX", ""), f.get("SISTEMA_MIN", ""), lang)}


# ── 속성 ────────────────────────────────────────────────────────────

def age_en(value: str) -> str:
    """에스파냐어 시대 이름 → ICS 영문 — `i18n.age_es` (멕시코 SGM 과 함께 쓴다, wetherilli 206)"""
    return i18n.age_es(value)


def _clean(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("<null>", "null", "none") else text


def _span(old: str, young: str, lang: str) -> str:
    a, b = (age_en(old) if old else ""), (age_en(young) if young else "")
    age = a if a == b or not b else (b if not a else f"{a} - {b}")
    return i18n.age_ko(age) if lang == "ko" and age else age


def _ma(old, young) -> str:
    def num(v):
        try:
            return f"{float(v):g}" if v not in (None, "", " ") and math.isfinite(float(v)) else ""
        except (TypeError, ValueError):
            return ""
    a, b = num(old), num(young)
    return f"{b}–{a}" if a and b and a != b else (a or b)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·암석·설명은 에스파냐어 그대로 두고 지질시대만 옮긴다."""
    v = lambda k: _clean(props.get(k))          # noqa: E731
    rows = (("기호", v("ETIQUETA") or v("NAME")), ("이름", v("UNIDAD")), ("위계", v("CTG_UNIDAD")),
            ("갈래", v("TIPO_UNIDAD")), ("지질시대", _span(v("SISTEMA_MAX"), v("SISTEMA_MIN"), lang)),
            ("연대 (Ma)", _ma(props.get("E_MAX_MA"), props.get("E_MIN_MA"))), ("암석", v("LITOLOGIA")),
            ("설명", v("DESCRIP")), ("도폭", v("HOJA")), ("문헌", v("REFERENCIA")))
    return {k: x for k, x in rows if x}
