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
#: 범례가 1:100만 판으로 넘어가는 범위(°) — 1:150만은 화면 줌 8–9 남짓, 화면 너비로 6–8° 다. 그보다 넓으면 1:250만 판의 단위를 센다
FINE_SPAN = 6.0
#: 범례를 뜨는 가장 넓은 범위(°) — 대륙 전체(경도 40°)가 든다. 칸이 많으면 `MAX_LEGEND` 에서 끊는다
SPAN = 45.0
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400


class GaError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def legend_layers() -> list:
    return [n for n, spec in LAYERS.items() if spec[4]]


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
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
    usage.record("ga", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    spec = LAYERS[_one(params)]
    both = f"{spec[0]},{spec[1]}"          # 상류가 축척에 맞는 판을 그린다
    out = dict(params, service="WMS", request=request, layers=both)
    if "query_layers" in out:
        out["query_layers"] = both
    out.setdefault("styles", "")
    return out


def get_map(params: dict):
    r = _get(settings.GA_WMS_URL, _wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GaError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise GaError("호주 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    if not LAYERS[_one(params)][4]:
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    r = _get(settings.GA_WMS_URL, params)
    if r.status_code != 200:
        raise GaError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise GaError("속성이 JSON 이 아니다") from exc


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


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·설명·암상은 영어 그대로, 시대만 옮긴다."""
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
