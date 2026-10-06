"""사우디 지질조사소(SGS)의 국가 지질 자료(NGD)로 나가는 문 — 사우디 1:25만 지질도 합본 (wetherilli 227).

- 주소: WMS `ngdgis.sgs.gov.sa/ngdgis/services/Geology/Geology_250K/MapServer/WMSServer`(레이어 `Geology_250K_Standard` — 번호
  `0` 은 `LayerNotDefined`), REST `…/rest/services/Geology/Geology_250K/MapServer`. 열쇠가 없다. 주소는 NGD 의 1:25만 안내 페이지에서 찾았다
- 원본이 3857 이다. 서부(아라비아 순상지)와 둘레의 1:25만 도폭을 이어 붙였다 — 나라 전체가 아니다(2026-10-04, 512² 한 장 3.3 초)
- 속성은 `application/geojson`(모양 없이 2 KB) — 영어 열 40 남짓(도폭·단위·암상·누대/대/기·나이 Ma·지구조·보고서 번호)
- **범례는 보는 범위의 것** — REST `legend` 는 1 337 칸에 700 KB 라 통째로 내지 않는다. 칠하기 규칙이 `Symbol`·`Label` 두 열이라
  범위 안의 단위를 그 둘로 묶어 센다(호주·페루와 같은 꼴). 견본은 `legend` 의 그림(무늬 채움이 많다)을 한 번 받아 둔다
- 조건: WMS 의 Fees·AccessConstraints 가 비어 있다. NGD 포털의 내려받기는 회원제다. **밖에 열기 전에 사람이 읽는다.** CORS 는 Origin 을
  되비춘다(WMS)
"""
import json
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "sgs:"
#: 메타타일로 받는다 (wetherilli 287) — 512 px 2.6–12.0 초, 1 024 px 4.4 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"sgs:": None}
ATTRIBUTION = ('<a href="https://ngd.sgs.gov.sa/" target="_blank" rel="noopener">Saudi Geological Survey</a> '
               "(National Geological Database, 1:250,000)")
LAYERS = {"sgs:geology": "Geology_250K_Standard"}
#: 범례를 뜨는 가장 넓은 범위(°) — 2° 네모가 142 칸·6.6 초였다. 그보다 넓으면 "더 들어오라" 고 한다
SPAN = 3.0
MAX_LEGEND = 60
#: 견본 그림(`legend`)을 다시 받는 간격 — 700 KB 라 자주 받지 않는다
SWATCH_MAX_AGE = 30 * 86400
TIMEOUT = 45


class SgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "") in LAYERS or str(name or "") in RESOURCES


#: 광물(wetherilli 280) → (서비스, WMS 이름). 광물 산지 MODS 5 751 곳(광종·중요도·탐사 단계 …)과 금·니켈·아연·VMS 광화대(면 16)
RESOURCES = {
    "sgs:mods": ("Geosciences/MODS", "Mineral_Occurrences"),
    "sgs:belts": ("Geology/Mineralization_Belts", "Gold_Mineral_Belt,Nickel_Mineral_Belt,Zinc_Mineral_Belt,VMS_Mineral_Belt"),
}


def _resource_door(name: str) -> arcwms.Door:
    service, wms = RESOURCES[name]
    return arcwms.Door(url=lambda: f"{settings.SGS_URL.rstrip('/')}/services/{service}/MapServer/WMSServer",
                       layers={name: wms}, queryable=(name,), get=_get, error=SgsError)


def _resource(names) -> str:
    first = str(names or "").split(",")[0].strip()
    return first if first in RESOURCES else ""


def _names(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        if not knows(one.strip()):
            raise SgsError(f"모르는 레이어다: {one}")
        out.append(LAYERS[one.strip()])
    return ",".join(out)


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise SgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgs", ok=False)
        raise SgsError(f"SGS 에 닿지 못했다: {exc}") from exc
    log.info("SGS %s -> %s", r.url, r.status_code)
    usage.record("sgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms_url() -> str:
    return f"{settings.SGS_URL.rstrip('/')}/services/Geology/Geology_250K/MapServer/WMSServer"


def _rest_url() -> str:
    return f"{settings.SGS_URL.rstrip('/')}/rest/services/Geology/Geology_250K/MapServer"


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = _names(params[key])
    return params


def get_map(params: dict):
    if _resource(params.get("layers")):
        return _resource_door(_resource(params.get("layers"))).get_map(params)
    r = _get(_wms_url(), _wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    if layer in RESOURCES:
        return _resource_door(layer).get_legend(layer)
    raise SgsError("그림 범례는 1 337 칸이라 두지 않는다 — 보는 범위의 범례를 쓴다")


def get_feature_info(params: dict) -> dict:
    name = _resource(params.get("query_layers") or params.get("layers"))
    if name:
        return _resource_door(name).get_feature_info(params)
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    # 도폭을 이어 붙인 합본이라 경계에서 같은 단위가 겹쳐 셋씩 온다(2026-10-04, 알히수 도폭) — 맨 위 하나만 받는다
    params["feature_count"] = "1"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(_wms_url(), params)
    if r.status_code != 200:
        raise SgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise SgsError("속성이 JSON 이 아니다") from exc


# ── 보는 범위의 범례 ───────────────────────────────────────────────

def _rest(path: str, params: dict) -> dict:
    r = _get(f"{_rest_url()}/{path}", dict(params, f="json"))
    try:
        data = r.json()
    except ValueError as exc:
        raise SgsError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise SgsError(f"REST 오류 (status={r.status_code}): {(data.get('error') or {}).get('message', '')}")
    return data


def swatches() -> dict:
    """`Symbol: Label` → 견본 그림(data URI). `legend` 를 한 번 받아 담아 둔다"""
    key = tilecache.key_text("sgs-swatches", "Geology_250K")
    held = tilecache.get(key, ".json", max_age=SWATCH_MAX_AGE)
    if held is not None:
        return json.loads(held)
    data = _rest("legend", {})
    table = {}
    for part in data.get("layers") or []:
        for item in part.get("legend") or []:
            if item.get("label") and item.get("imageData"):
                table[item["label"]] = f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def extent_legend(bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"symbol", "name", "period", "count"}, …]`, 면이 많은 것부터"""
    data = _rest("0/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": "Symbol,Label,Period",
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false"})
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        symbol, name = _value(a, "Symbol"), _value(a, "Label")
        if not symbol:
            continue
        count = int(a.get("n") or a.get("N") or 0)
        key = (symbol, name)
        if key in rows:
            rows[key]["count"] += count
        else:
            rows[key] = {"symbol": symbol, "name": name, "period": _value(a, "Period"), "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(row: dict, table: dict, lang: str = "ko") -> dict:
    period = row.get("period") or ""
    return {"symbol": row["symbol"], "lithology": row["name"], "color": "transparent",
            "swatch": table.get(f"{row['symbol']}: {row['name']}", ""),
            "age": i18n.age_ko(period) if lang == "ko" and period else period}


# ── 속성 ─────────────────────────────────────────────────────────

def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "none", "undefined") else value


#: 광물 산지 MODS 의 열 — geojson 은 별칭(`English Name`)으로 온다 (wetherilli 280)
MODS_COLS = (("이름", "English Name"), ("광종", "Major Commodity"), ("딸린 광종", "Minor Commodities"),
             ("중요도", "Occurrence Importance"), ("광산", "Occurrence Status"), ("탐사 단계", "Exploration Status"),
             ("광상 유형", "Gitology"), ("모암", "Host Rocks"), ("변질", "Alteration"), ("지구조 구역", "Structural Province"),
             ("번호", "MODS"))


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·암석·지구조는 영어 그대로, 시대(기 — ICS)만 옮긴다"""
    if "MODS" in props:                                       # 광물 산지 (wetherilli 280)
        return {label: v for label, key in MODS_COLS if (v := _value(props, key) or _value(props, key.replace(" ", "_")))}
    if "Lay_Val" in props or "TYPE" in props and "LAYER" in props:   # 광화대
        rows = (("이름", _value(props, "LAYER")), ("갈래", _value(props, "TYPE")))
        return {k: v for k, v in rows if v}
    period = _value(props, "Period")
    terrane = " · ".join(x for x in dict.fromkeys((_value(props, "Terrane"), _value(props, "Sub_Terane"))) if x)
    rows = (("기호", _value(props, "Unit_SYM")), ("이름", _value(props, "Unit_Name")),
            ("암석", _value(props, "Main_Litho")), ("지질시대", i18n.age_ko(period) if lang == "ko" and period else period),
            ("연대", _value(props, "Age_Ma")), ("지구조 구역", terrane), ("도폭", _value(props, "Map_Name")))
    return {k: v for k, v in rows if v}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "sgs", "tag": "SGS", "title": "사우디 지질조사소", "relay": True, "projected": True, "globe": True},
]
