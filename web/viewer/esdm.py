"""인도네시아 에너지광물자원부(ESDM) 지질청(Badan Geologi)으로 나가는 문 — 인도네시아 지질도 1:10만 편집 2018 (wetherilli 228).

- 주소: `geoportal.esdm.go.id/gis4/services/BGS_PM/Geologi_Litologi/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다. 섬 전체(95–141°E)
- Capabilities 는 4326·CRS:84 만 적지만 **3857 GetMap 이 그린다**(2026-10-04, 반둥 둘레 256² 2.0 초). Capabilities 는 17 초 걸렸다
- **1:57만 7 790 보다 크게 확대하면 그리지 않는다**(서비스의 maxScale) — 화면 줌 10 까지만 받고 그 위는 화면이 늘려 그린다(`LAST_ZOOM` →
  카탈로그의 `maxZoom`, `map.js` 의 `npolarSource` 가 격자를 거기서 멈춘다)
- 속성은 **ESRI XML 만** 준다(geojson 을 물어도 XML) — `<FIELDS NotasiFormasi="Qyt" NamaFormasi="Pumiceous Tuff" UmurFormasi="Kuarter" …/>`.
  지층명은 영어, 시대·설명은 인도네시아어다. 시대는 값 28 가지(2026-10-04 에 모았다)를 ICS 로 옮긴다(`AGES`)
- **범례는 보는 범위의 것**(wetherilli 243) — 전체는 1 403 칸이라 사우디(`sgs.py`)처럼 REST 통계 질의로 범위 안의 단위와 면 수를 세고,
  색은 칠하기 규칙(`simobj` 로 가른 1 402 칸)에서 찾는다. REST 의 열 이름은 WMS 와 다르다(`simobj`·`namobj`·`umurobj`, 개수는 `objectid_1`)
- **광물 잠재력**(wetherilli 280) — 같은 서버 `BGD_TU` 폴더의 금속(3 214)·비금속(6 738) 광물 잠재력 점. **WMS 를 켜지 않았다**(400) —
  REST `export`·`identify` 로 WMS 꼴을 옮긴다(`arcwms.rest_export_params`). 원본 4326 이지만 3857 로 그린다(1.6 초, 2026-10-05).
  copyright 는 PSDMBP(광물·석탄·지열 자원센터)
- 조건: copyright "Pusat Survei Geologi" 뿐, 이용 조건 문서를 찾지 못했다 — **밖에 열기 전에 사람이 읽는다**. CORS 는 Origin 을 되비춘다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "esdm:"
ATTRIBUTION = ('<a href="https://geoportal.esdm.go.id/" target="_blank" rel="noopener">Badan Geologi (ESDM)</a> — '
               "Peta Geologi Indonesia 1:100.000")
LAYERS = {"esdm:geology": "0"}
#: 이 줌까지만 받는다 — 상류가 1:57만 7 790 보다 크게는 그리지 않는다
LAST_ZOOM = 10
#: 범례를 뜨는 가장 넓은 범위(°)와 싣는 칸 수, 칠하기 규칙을 담아 두는 날 (wetherilli 243)
SPAN = 6.0
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400
#: 인도네시아어 시대 → ICS(영어). 상류의 값 28 가지 그대로다. 옮기지 못하는 것(`Pra Tersier` 따위)은 원문을 보인다
AGES = {
    "Kuarter": "Quaternary", "Holosen": "Holocene", "Tersier": "Tertiary", "Neogen": "Neogene", "Paleogen": "Paleogene",
    "Miosen": "Miocene", "Miocene": "Miocene", "Oligocene": "Oligocene", "Kapur": "Cretaceous", "Jura": "Jurassic",
    "Trias": "Triassic", "Triassic": "Triassic", "Perm": "Permian", "Permian": "Permian", "Permo Karbon": "Carboniferous – Permian",
    "Karbon": "Carboniferous", "Carbonifer": "Carboniferous", "Devonian": "Devonian", "Silurian": "Silurian",
    "Ordovician": "Ordovician", "Mesozoikum": "Mesozoic", "Paleozoikum": "Paleozoic", "Paleo - Meso": "Paleozoic – Mesozoic",
    "Meso - Paleo": "Paleozoic – Mesozoic", "Proteroz": "Proterozoic", "Prakambrium": "Precambrian",
}


class EsdmError(RuntimeError):
    pass


def _url() -> str:
    return f"{settings.ESDM_URL.rstrip('/')}/services/BGS_PM/Geologi_Litologi/MapServer/WMSServer"


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise EsdmError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 45),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("esdm", ok=False)
        raise EsdmError(f"ESDM 에 닿지 못했다: {exc}") from exc
    log.info("ESDM %s -> %s", r.url, r.status_code)
    usage.record("esdm", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


DOOR = arcwms.Door(url=_url, layers=LAYERS, queryable=("esdm:geology",), info_format="text/xml", get=_get, error=EsdmError)
#: 광물 잠재력(wetherilli 280) → REST 서비스. 레이어는 둘 다 `0`
RESOURCES = {"esdm:metal": "BGD_TU/Potensi_Sumber_Daya_dan_Cadangan_Mineral_Logam",
             "esdm:nonmetal": "BGD_TU/Potensi_Mineral_Bukan_Logam_dan_Batuan"}


def _resource(names) -> str:
    first = str(names or "").split(",")[0].strip()
    return first if first in RESOURCES else ""


def _resource_url(name: str) -> str:
    return f"{settings.ESDM_URL.rstrip('/')}/rest/services/{RESOURCES[name]}/MapServer"


def knows(name: str) -> bool:
    return DOOR.knows(name) or name in RESOURCES


def get_map(params: dict):
    name = _resource(params.get("layers"))
    if not name:
        return DOOR.get_map(params)
    try:
        query = arcwms.rest_export_params(params, "0")
    except ValueError as exc:
        raise EsdmError(str(exc)) from exc
    r = _get(f"{_resource_url(name)}/export", query)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise EsdmError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    name = _resource(params.get("query_layers") or params.get("layers"))
    if not name:
        return DOOR.get_feature_info(params)
    try:
        query = arcwms.rest_identify_params(params, "0")
    except ValueError as exc:
        raise EsdmError(str(exc)) from exc
    r = _get(f"{_resource_url(name)}/identify", query)
    try:
        data = r.json()
    except ValueError as exc:
        raise EsdmError("속성이 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise EsdmError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": arcwms.identify_features(data, name)}


def get_legend(layer: str):
    raise EsdmError("그림 범례는 1 403 칸이라 쓰지 않는다 — 보는 범위의 범례(`esdm/legend/`)를 쓴다")


# ── 보는 범위의 범례 (wetherilli 243) — 사우디(`sgs.py`)·호주(`ga.py`)와 같은 꼴 ─────────

def _rest(path: str, params: dict) -> dict:
    r = _get(f"{settings.ESDM_URL.rstrip('/')}/rest/services/BGS_PM/Geologi_Litologi/MapServer/{path}", dict(params, f="json"))
    try:
        data = r.json()
    except ValueError as exc:
        raise EsdmError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise EsdmError(f"REST 오류 (status={r.status_code}): {(data.get('error') or {}).get('message', '')}")
    return data


def colors() -> dict:
    """기호(`simobj`) → `#rrggbb`. 칠하기 규칙을 한 번 받아 담는다."""
    key = tilecache.key_text("esdm-colors", LAYERS["esdm:geology"])
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    try:
        table = arcpoints.renderer_colors(_rest(LAYERS["esdm:geology"], {})["drawingInfo"]["renderer"])
    except (EsdmError, KeyError, TypeError):
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "none", "<null>") else value


def extent_legend(bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"symbol", "name", "age", "count"}, …]`, 면이 많은 것부터"""
    data = _rest(f"{LAYERS['esdm:geology']}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": "simobj,namobj,umurobj",
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "objectid_1", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = {str(k).lower(): v for k, v in (f.get("attributes") or {}).items()}
        symbol = _value(a, "simobj")
        if not symbol:
            continue
        row = rows.setdefault((symbol, _value(a, "namobj")), {"symbol": symbol, "name": _value(a, "namobj"),
                                                             "age": _value(a, "umurobj"), "count": 0})
        row["count"] += int(a.get("n") or 0)
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(row: dict, table: dict, lang: str = "ko") -> dict:
    return {"symbol": row["symbol"], "lithology": f"{row['symbol']} {row['name']}".strip(), "swatch": "",
            "color": table.get(row["symbol"], "#cccccc"), "age": age(row["age"], lang)}


def age(value: str, lang: str = "ko") -> str:
    text = str(value or "").strip()
    ics = AGES.get(text)
    if not ics:
        return text
    return i18n.age_ko(ics) if lang == "ko" else ics


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 지층명(영어)·설명(인도네시아어)은 그대로, 시대만 옮긴다"""
    if "namobj" in props:                       # 광물 잠재력 (wetherilli 280) — 금속(`…lgm`)과 비금속(`…bl`)의 열이 조금 다르다
        v = lambda *keys: next((str(props[k]).strip() for k in keys if str(props.get(k) or "").strip()), "")   # noqa: E731
        rows = (("이름", v("namobj")), ("광종", v("jnskom", "jnskombl")), ("광종 갈래", v("kellgm", "kelkombl")),
                ("기호", v("lbunsur", "lbunsurbl")), ("조사 단계", v("statdiklgm", "statdikbl")), ("곳", v("lokasilgm", "lokasibl")),
                ("비고", v("remark")))
        return {k: x for k, x in rows if x}
    rows = (("기호", props.get("NotasiFormasi", "")), ("이름", props.get("NamaFormasi", "")),
            ("설명", props.get("Keterangan", "")), ("지질시대", age(props.get("UmurFormasi", ""), lang)))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip()}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "esdm", "tag": "ESDM", "title": "인도네시아 지질청 (ESDM)", "relay": True, "projected": True, "globe": True},
]
