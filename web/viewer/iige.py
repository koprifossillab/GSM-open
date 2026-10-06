"""IIGE(에콰도르 지질·에너지 연구소)로 나가는 문 — 에콰도르 일반 지질도 (wetherilli 198).

- 주소: `capas.geoenergia.gob.ec/arcgis/services/Geologia_General/MapServer/WMSServer` (ArcGIS WMS, 레이어 `0` 하나). REST 는 같은
  호스트의 `arcgis/rest/services/Geologia_General/MapServer/0`. 열쇠가 없다. 서비스의 투영은 32717(UTM 17S)이지만 **3857 GetMap 도 그린다**
- 2026-10-04 에 쟀다 — 나라 전체(줌 6) 512² 가 7.4 초, 키토 둘레(줌 9) 3.2 초. 남부는 거의 다, 북부는 도폭 조각만 덮는다. 폴리곤 7 595.
  REST 서비스 정보는 한 번 135 초 동안 답이 없었다 — 응답이 들쭉날쭉하다. 받은 것은 캐시에 담는다
- 같은 서버의 `Cartas_Geologicas_100K` 는 지질도가 아니라 1:10만 **도폭 색인**(156 장의 진행 상태·PDF 고리)이라 싣지 않는다
- 속성은 `application/geo+json` — `ENT_GEOL`(단위)·`INT_ECO`(경제적 쓰임)·`LITOLOGIA`(설명)·`COD_OK`(색 번호). 시대 열은 없다
- 범례는 보는 범위의 것 — 페루(`ingemmet.py`)와 같은 꼴로, 범위 안의 단위는 REST 통계 질의, 색은 칠하기 규칙(새 꼴 `uniqueValueGroups`)
- 조건: Capabilities 의 AccessConstraints 는 비어 있다. IIGE 지오포털의 내려받기 이용 허락은 무료·비독점으로 쓰게 하되 출처
  ("Instituto de Investigación Geológico y Energético")와 내려받은 날을 밝히고 **팔지 못하게** 한다 — 비상업. 정적 판에는 싣지 않는다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "iige:"
#: 메타타일로 받는다 (wetherilli 287) — 512 px 5.6–7.0 초, 1 024 px 5.4 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"iige:": None}
ATTRIBUTION = ('<a href="https://geoportal.geoenergia.gob.ec/" target="_blank" rel="noopener">IIGE</a> '
               "(Instituto de Investigación Geológico y Energético, Ecuador — 비상업)")
#: 카탈로그의 레이어 → 상류의 WMS 레이어. 하나뿐이다
LAYERS = {"iige:geologia_general": "0"}
SERVICE = "Geologia_General"
#: REST 의 단위 면 번호, 색을 가르는 열, 범례에 실을 열
UNITS, BY, LABEL = 0, "COD_OK", ("COD_OK", "ENT_GEOL")
#: 범례를 뜨는 가장 넓은 범위(°) — 나라 전체(경도 6° 남짓)가 든다. 칸이 많으면 `MAX_LEGEND` 에서 끊는다
SPAN = 8
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400


class IigeError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _base() -> str:
    return settings.IIGE_URL.rstrip("/")


def _get(url: str, params: dict, timeout: int = 45):
    left = usage.paused()
    if left:
        raise IigeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("iige", ok=False)
        raise IigeError(f"IIGE 에 닿지 못했다: {exc}") from exc
    log.info("IIGE %s -> %s", r.url, r.status_code)
    usage.record("iige", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise IigeError(f"모르는 레이어다: {names}")
    params = dict(params, service="WMS", request=request, layers=LAYERS[names[0]])
    if "query_layers" in params:
        params["query_layers"] = LAYERS[names[0]]
    return params


def get_map(params: dict):
    r = _get(f"{_base()}/services/{SERVICE}/MapServer/WMSServer", _wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IigeError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise IigeError("에콰도르 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    r = _get(f"{_base()}/services/{SERVICE}/MapServer/WMSServer", params)
    if r.status_code != 200:
        raise IigeError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise IigeError("속성이 JSON 이 아니다") from exc


def _clean(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("<null>", "null", "none") else text


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 에스파냐어 그대로다 — 시대 열이 없어 옮길 것이 없다."""
    rows = (("이름", _clean(props.get("ENT_GEOL"))), ("암석", _clean(props.get("LIT"))),
            ("설명", _clean(props.get("LITOLOGIA"))), ("경제적 쓰임", _clean(props.get("INT_ECO"))),
            ("기호", _clean(props.get("COD_OK"))))
    return {k: v for k, v in rows if v}


# ── 보는 범위의 범례 ────────────────────────────────────────────────

def _rest(path: str, params: dict) -> dict:
    r = _get(f"{_base()}/rest/services/{SERVICE}/MapServer/{path}", dict(params, f="json"))
    if r.status_code != 200:
        raise IigeError(f"REST 를 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise IigeError("REST 가 JSON 이 아니다") from exc
    if data.get("error"):
        raise IigeError(f"REST 오류: {data['error'].get('message', '')}")
    return data


def colors() -> dict:
    """`COD_OK` → `#rrggbb`. 칠하기 규칙에서 떠 한 번 받아 담는다."""
    key = tilecache.key_text("iige-colors", SERVICE)
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    try:
        table = arcpoints.renderer_colors(_rest(str(UNITS), {})["drawingInfo"]["renderer"])
    except (IigeError, KeyError, TypeError):
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def extent_legend(bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"value", "name", "count"}, …]`, 면이 많은 것부터."""
    data = _rest(f"{UNITS}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": ",".join(LABEL),
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = _clean(a.get(BY))
        if not value:
            continue
        count = int(a.get("n") or a.get("N") or 0)
        if value in rows:
            rows[value]["count"] += count
        else:
            rows[value] = {"value": value, "name": _clean(a.get("ENT_GEOL")), "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(row: dict, table: dict) -> dict:
    """화면이 그리는 한 칸 — 일본·대만·브라질·페루의 칸과 같은 이름이다. 시대가 없다."""
    return {"color": table.get(row["value"], "#cccccc"), "symbol": row["value"], "swatch": "",
            "lithology": row["name"] or row["value"], "age": ""}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "iige", "tag": "IIGE", "title": "에콰도르 지질·에너지 연구소", "relay": True, "projected": True, "globe": True},
]
