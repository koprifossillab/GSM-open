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
#: 범례 칸을 몇 개까지 싣나
MAX_LEGEND = 60
#: 칠하기 규칙(색 표)을 담아 두는 날 — 판이 바뀔 일이 드물다
COLORS_MAX_AGE = 30 * 86400


class IngemmetError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def sheet_of(name: str) -> str:
    """`ingemmet:50k` → `50k` — 타일 주소의 이름."""
    return name[len(PREFIX):]


def valid_tile(name: str, z: int, x: int, y: int) -> bool:
    return name in LAYERS and 0 <= z <= LAYERS[name]["max"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z


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
    r = _get(f"{_base(name)}/tile/{z}/{y}/{x}")
    if r.status_code == 404:
        return None
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IngemmetError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


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
