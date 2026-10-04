"""SGM(멕시코 지질조사소)로 나가는 문 — 멕시코 지질·광업도 1:25만·1:5만 연속판 (wetherilli 206).

- 주소: `portal.sgm.gob.mx/arcgis/rest/services/SGM/SUNGeologiaContinuoMineDatosEs/MapServer` (ArcGIS REST). GeoInfoMex 가 쓰는
  서비스다. 열쇠가 없다. **WMSServer 는 400** 이라 WMS 로 받지 못한다 — 화면이 보내는 WMS 변수(3857 범위·크기)를 이 문이 REST `export`
  로 옮겨 묻는다(PGC 경사와 같은 길). 그래서 화면에서는 다른 WMS 상류와 다르지 않다
- 레이어명은 `sgm:<REST 번호>` — `8` 암상 1:25만(전국)·`7` 암상 1:5만(광업 지구)·`6` 구조 1:25만·`5` 구조 1:5만
- 2026-10-04 에 쟀다 — 나라 전체(줌 5) 512² 가 5.9 초, 사카테카스 둘레(줌 9) 1.3 초. 타일 캐시는 없다
- 속성은 REST `identify` — 열 별칭(Clave·Litología·Roca·Formación·Era·Periodo·Edad inicial·Edad final)으로 온다
- 범례는 보는 범위의 것 — REST 범례는 1:5만 2 571 칸·1:25만 888 칸(1.3 MB)이다. 페루(`ingemmet.py`)처럼 범위 안의 단위는 통계 질의,
  색은 칠하기 규칙(`CLAVE_SGM`)에서 찾는다
- 시대는 에스파냐어다 — `i18n.age_es` 로 ICS 영문을 거쳐 한국어판이면 `i18n.age_ko`
- 조건: datos.gob.mx 의 "Cartografía Geológica de la República Mexicana 1:250,000" 이 **CC BY 4.0**. 서비스 저작권 "© SGM"
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "sgm:"
ATTRIBUTION = ('<a href="https://www.sgm.gob.mx/GeoInfoMexGobMx/" target="_blank" rel="noopener">© SGM</a> '
               "(Servicio Geológico Mexicano, CC BY 4.0)")
#: 레이어 → (REST 번호, 처음 그리는 화면 줌, 범례·누르기가 되는 단위 면인가)
LAYERS = {
    "sgm:8": (8, None, True),
    "sgm:7": (7, 10, True),         # 상류 minScale 75만 — 화면 줌 10 남짓부터 그린다
    "sgm:6": (6, None, False),
    "sgm:5": (5, 8, False),         # 상류 minScale 200만
}
#: 범례에 실을 열 — 기호, 암상, 지층, 시대
LABEL = ("CLAVE_SGM", "LITOLOGIA", "FORMACION", "PERIODO")
#: 범례를 뜨는 가장 넓은 범위(°)
SPAN = {8: 8, 7: 3}
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400


class SgmError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def legend_layers() -> list:
    return [n for n, spec in LAYERS.items() if spec[2]]


def _one(params_or_name):
    name = params_or_name if isinstance(params_or_name, str) else \
        (params_or_name.get("layers") or params_or_name.get("query_layers") or "")
    names = [n.strip() for n in str(name).split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SgmError(f"모르는 레이어다: {names}")
    return names[0], LAYERS[names[0]][0]


def _base() -> str:
    return settings.SGM_URL.rstrip("/")


def _get(path: str, params: dict):
    left = usage.paused()
    if left:
        raise SgmError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{_base()}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 45),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgm", ok=False)
        raise SgmError(f"SGM 에 닿지 못했다: {exc}") from exc
    log.info("SGM %s -> %s", r.url, r.status_code)
    usage.record("sgm", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _view(params: dict):
    """WMS 변수 → (3857 범위 네 수, 너비, 높이). 화면은 늘 3857 로 묻는다."""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in ("EPSG:3857", "EPSG:900913"):
        raise SgmError(f"3857 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise SgmError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise SgmError("범위·크기가 맞지 않다")
    return bbox, width, height


def get_map(params: dict):
    """WMS GetMap → REST export. 받은 그림은 투명 PNG 다."""
    _, layer = _one(params)
    bbox, width, height = _view(params)
    r = _get("export", {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": "3857", "imageSR": "3857",
                        "size": f"{width},{height}", "format": "png32", "transparent": "true", "dpi": "96",
                        "layers": f"show:{layer}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SgmError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise SgmError("멕시코 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    """WMS GetFeatureInfo → REST identify. 누른 자리(I·J)를 3857 의 한 점으로 셈해 그 레이어만 묻는다."""
    name, layer = _one(params)
    if not LAYERS[name][2]:
        return {"features": []}
    bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise SgmError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get("identify", {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": "3857",
                          "layers": f"all:{layer}", "tolerance": "2", "mapExtent": ",".join(repr(v) for v in bbox),
                          "imageDisplay": f"{width},{height},96", "returnGeometry": "false", "f": "json"})
    if r.status_code != 200:
        raise SgmError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise SgmError("속성이 JSON 이 아니다") from exc
    if data.get("error"):
        raise SgmError(f"identify 오류: {data['error'].get('message', '')}")
    return {"features": [{"id": f"{res.get('layerId')}.{(res.get('attributes') or {}).get('ObjectId', n)}",
                          "properties": res.get("attributes") or {}}
                         for n, res in enumerate(data.get("results") or [])]}


def _clean(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("null", "<null>", "none", "indeterminado", "no aplicable") else text


def _span(old: str, young: str, lang: str) -> str:
    a, b = (i18n.age_es(old) if old else ""), (i18n.age_es(young) if young else "")
    age = a if a == b or not b else (b if not a else f"{a} - {b}")
    return i18n.age_ko(age) if lang == "ko" and age else age


def friendly(props: dict, lang: str = "ko") -> dict:
    """identify 의 별칭 열 → 한국어. 암상·지층은 에스파냐어 그대로, 시대만 옮긴다."""
    v = lambda k: _clean(props.get(k))          # noqa: E731
    period = _span(v("Periodo"), "", lang)
    stage = _span(v("Edad inicial"), v("Edad final"), lang)
    rows = (("기호", v("Clave")), ("암석", v("Litología")), ("갈래", v("Roca")), ("지층", v("Formación")),
            ("지질시대", " · ".join(x for x in (period, stage) if x)), ("위계", v("Tipo de unidad")))
    return {k: x for k, x in rows if x}


# ── 보는 범위의 범례 — 페루(`ingemmet.py`)와 같은 꼴 ───────────────

def colors(layer: int) -> dict:
    key = tilecache.key_text("sgm-colors", str(layer))
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _get(str(layer), {"f": "json"})
    try:
        table = arcpoints.renderer_colors(r.json()["drawingInfo"]["renderer"])
    except (ValueError, KeyError, TypeError) as exc:
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise SgmError("칠하기 규칙을 읽지 못했다") from exc
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def extent_legend(name: str, bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"value", "fields", "count"}, …]`, 면이 많은 것부터."""
    _, layer = _one(name)
    r = _get(f"{layer}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": ",".join(LABEL),
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise SgmError("질의가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise SgmError(f"질의 오류 (status={r.status_code})")
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = _clean(a.get("CLAVE_SGM"))
        if not value:
            continue
        count = int(a.get("n") or a.get("N") or 0)
        if value in rows:
            rows[value]["count"] += count
        else:
            rows[value] = {"value": value, "fields": {k: _clean(a.get(k)) for k in LABEL}, "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(row: dict, table: dict, lang: str = "ko") -> dict:
    f = row["fields"]
    name = " · ".join(x for x in (f.get("LITOLOGIA"), f.get("FORMACION")) if x)
    return {"color": table.get(row["value"], "#cccccc"), "symbol": row["value"], "swatch": "",
            "lithology": f"{row['value']} {name}".strip(), "age": _span(f.get("PERIODO", ""), "", lang)}


def legend_span(name: str) -> float:
    return SPAN[LAYERS[name][0]]
