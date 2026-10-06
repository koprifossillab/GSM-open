"""미국 주 지질조사소로 나가는 문 넷 — 네바다 NBMG·워싱턴 DNR·오리건 DOGAMI (wetherilli 291)·알래스카 DGGS 광물 (wetherilli 322).

호주의 주 판(`austates.py`, wetherilli 225)처럼 한 파일에 문 셋을 둔다 — 셋 다 ArcGIS REST `export`·`identify` 를 같은 꼴로 부르고,
캘리포니아(`calgs.py`, 231)처럼 미국 탭의 3978 로 곧장 그린다. 화면이 보내는 WMS 변수는 `arcwms.rest_*` 가 옮긴다(3D 는 3857).

| 상류 | 서비스 | 판 |
|---|---|---|
| `nbmg` | `gisweb.unr.edu/nbmg/rest/services/Geology/NV_500k_Geology` | 네바다 1:50만(Stewart & Carlson 1978, USGIN) |
| `wadnr` | `gis.dnr.wa.gov/site1/rest/services/Public_Geology/500k_Surface_Geology`·`100K_Surface_Geology_WA_GeMS` | 워싱턴 1:50만·1:10만 GeMS |
| `dogami` | `gis.dogami.oregon.gov/arcgis/rest/services/Public/OGDC6` | 오리건 지질 자료 편찬(OGDC) 6 판 |
| `dggs` | `maps.dggs.alaska.gov/arcgis/rest/services/Mineral_Occurrences_2020_MIL1`·`minerals/mineral_districts` | 알래스카 중요 광산·산지 335 곳(DDS 18)·광업 지구 |

- **주 밖 타일은 묻지 않는다** — 카탈로그 행의 `clip`(하와이·푸에르토리코와 같다, wetherilli 238)이 레이어의 범위 밖 칸을 거른다
- 한 장의 시간(2026-10-05, 주 전체 400²): 네바다 1.2 초·워싱턴 1:50만 1.8 초·1:10만 8.2 초·오리건 10.8 초 — 뒤의 둘은 처음 줌을 둔다
- 범례는 REST `legend` 를 목록으로(54–101 칸) — `list/legend/`. 칸 이름이 기호뿐인 곳은 단위 표를 한 번 받아 이름·시대를 붙인다 —
  워싱턴 1:50만은 면에 기호(`Map_Unit`)뿐이라 단위 설명 표(`Description Of Map Units`, 표 5)를, 네바다는 면의 값을 모아(`returnDistinctValues`)
- 조건: 네바다 "© 2019 The University of Nevada, Reno. All Rights Reserved", 워싱턴은 출판물(Digital Data Series) 인용, 오리건은 비었다 —
  **밖에 열기 전에 사람이 읽는다**. 정적 판에 싣지 않는다
- 알래스카 DGGS(wetherilli 322) — 지질도는 SIM 3340(`mrdata`)이 덮어 광물만 둔다. 광산·산지는 DDS 18(Alaska Minerals Database)의 공개 층 —
  `distribution_policy` 가 모두 `public`. 조건은 메타데이터의 Use_Constraints "출처를 밝힌다(고쳤으면 고쳤다고)" 뿐이다
- 유타 UGS(`webmaps.geology.utah.gov`)·애리조나 AZGS(`services.azgs.az.gov`)는 이 서버에서 연결이 시간 초과다(2026-10-05) — TODOs.
  알래스카는 USGS SIM 3340(`mrdata`)이 이미 덮는다
"""
import json
import logging
from types import SimpleNamespace as _NS

import requests
from django.conf import settings

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

#: 상류 → (출처, 앞 주소의 설정 이름)
UPSTREAMS = {
    "nbmg": ('<a href="https://nbmg.unr.edu/" target="_blank" rel="noopener">Nevada Bureau of Mines and Geology</a> — '
             "Geologic map of Nevada 1:500,000 (Stewart & Carlson)", "NBMG_URL"),
    "wadnr": ('<a href="https://www.dnr.wa.gov/geology" target="_blank" rel="noopener">Washington Geological Survey</a> — '
              "Surface geology (Digital Data Series)", "WADNR_URL"),
    "dogami": ('<a href="https://www.oregon.gov/dogami/" target="_blank" rel="noopener">Oregon DOGAMI</a> — '
               "Oregon Geologic Data Compilation (OGDC-6)", "DOGAMI_URL"),
    "dggs": ('<a href="https://dggs.alaska.gov/pubs/id/30873" target="_blank" rel="noopener">Alaska DGGS</a> — '
             "Alaska Minerals Database (DDS 18)", "DGGS_URL"),
}
#: 우리 이름 → 상류, 서비스(앞 주소 뒤), 보일 레이어, 누를 레이어, 처음 줌, 단위 표(레이어·표 번호, 기호·이름·시대·설명·암석의 열 — 없으면 None)
LAYERS = {
    "nbmg:geology": _NS(upstream="nbmg", service="Geology/NV_500k_Geology", show="3,2", query="3", min=None,
                        units=("3", "genericSymbolizer", "name", "geologicHistory", "description", "lithology")),
    "wadnr:500k": _NS(upstream="wadnr", service="Public_Geology/500k_Surface_Geology", show="3,1,0", query="3", min=None,
                      units=("5", "Map_Unit", "Name", "Age", "Description", "GeoMaterial")),
    "wadnr:100k": _NS(upstream="wadnr", service="Public_Geology/100K_Surface_Geology_WA_GeMS", show="11,7,6", query="11", min=8, units=None),
    "dogami:ogdc": _NS(upstream="dogami", service="Public/OGDC6", show="3,0,1", query="3", min=7, units=None),
    "dggs:minerals": _NS(upstream="dggs", service="Mineral_Occurrences_2020_MIL1", show="12", query="12", min=None, units=None),
    "dggs:districts": _NS(upstream="dggs", service="minerals/mineral_districts", show="0", query="0", min=None, units=None),
}
#: 점 레이어 — 누를 때 둘레를 넓게 잡는다
POINT_LAYERS = ("dggs:minerals",)
#: 목록 범례를 내는 레이어 — 광업 지구는 한 색이라 범례 칸 이름이 비어 두지 않는다
LEGEND_LAYERS = tuple(n for n in LAYERS if n != "dggs:districts")
LEGEND_MAX_AGE = 30 * 86400


class UsStatesError(RuntimeError):
    pass


def knows(upstream: str, name: str) -> bool:
    return name in LAYERS and LAYERS[name].upstream == upstream


def first_zoom(name: str):
    return LAYERS[name].min


def _base(name: str) -> str:
    spec = LAYERS[name]
    return f"{getattr(settings, UPSTREAMS[spec.upstream][1]).rstrip('/')}/{spec.service}/MapServer"


def _get(name: str, path: str, params: dict):
    upstream = LAYERS[name].upstream
    left = usage.paused()
    if left:
        raise UsStatesError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{_base(name)}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise UsStatesError(f"{upstream} 에 닿지 못했다: {exc}") from exc
    log.info("%s %s -> %s", upstream.upper(), r.url, r.status_code)
    usage.record(upstream, ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _one(params: dict, upstream: str) -> str:
    names = [n.strip() for n in str(params.get("query_layers") or params.get("layers") or "").split(",") if n.strip()]
    if len(names) != 1 or not knows(upstream, names[0]):
        raise UsStatesError(f"모르는 레이어다: {names}")
    return names[0]


def _json(r) -> dict:
    try:
        data = r.json()
    except ValueError as exc:
        raise UsStatesError("REST 가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise UsStatesError(f"REST 오류 (status={r.status_code})")
    return data


def _get_map(upstream: str, params: dict):
    name = _one(params, upstream)
    try:
        query = arcwms.rest_export_params(params, LAYERS[name].show)
    except ValueError as exc:
        raise UsStatesError(str(exc)) from exc
    r = _get(name, "export", query)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise UsStatesError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def _get_feature_info(upstream: str, params: dict) -> dict:
    name = _one(params, upstream)
    try:
        # 점 레이어는 기호 둘레까지 잡게 4 픽셀, 면은 1 픽셀 (wetherilli 322)
        query = arcwms.rest_identify_params(params, LAYERS[name].query, tolerance=4 if name in POINT_LAYERS else 1)
    except ValueError as exc:
        raise UsStatesError(str(exc)) from exc
    features = arcwms.identify_features(_json(_get(name, "identify", query)), name, limit=1)
    units = _units(name) if LAYERS[name].units and name == "wadnr:500k" else {}     # 네바다는 identify 가 이미 이름·시대를 준다
    for f in features:
        props = f["properties"]
        unit = units.get(str(props.get("Map Unit") or props.get("Map_Unit") or "").strip())
        if unit:
            props.update({f"_{k}": v for k, v in unit.items()})
    return {"features": features}


def _get_legend(layer: str):
    raise UsStatesError("그림 범례 대신 목록 범례(`legend_rows`)를 쓴다")


def _cached(key_name: str, fetch):
    key = tilecache.key_text("usstates-legend", key_name)
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is None:
        held = json.dumps(fetch()).encode("utf-8")
        tilecache.put(key, held, ".json")
    return json.loads(held)


def _units(name: str) -> dict:
    """단위 표 — 기호 → {Name, Age, Description, GeoMaterial}. 워싱턴은 GeMS 의 단위 설명 표, 네바다는 면의 값을 모은 것. 한 번 받아 담는다"""
    number, sym, *cols = LAYERS[name].units

    def fetch():
        data = _json(_get(name, f"{number}/query", {
            "where": "1=1", "outFields": ",".join((sym, *cols)), "returnDistinctValues": "true", "returnGeometry": "false", "f": "json"}))
        out = {}
        for a in (f.get("attributes") or {} for f in data.get("features") or []):
            key = str(a.get(sym) or "").strip()
            if key and key not in out:
                out[key] = dict(zip(("Name", "Age", "Description", "GeoMaterial"), (a.get(c) for c in cols)))
        return out
    return _cached(f"{name}/units", fetch)


def legend_rows(name: str) -> list:
    """REST 범례의 면 칸 — 워싱턴 1:50만은 단위 설명 표의 이름·시대를 붙인다"""
    if name not in LAYERS:
        raise UsStatesError(f"범례가 없는 레이어다: {name}")
    swatches = _cached(f"{name}/swatches", lambda: arcwms.legend_list(_json(_get(name, "legend", {"f": "json"})),
                                                                     layer_ids=(int(LAYERS[name].query),)))
    units = _units(name) if LAYERS[name].units else {}
    rows = []
    for label, uri in swatches:
        symbol = label.split(",")[0].strip()          # 워싱턴의 칸 이름은 "Qd, Holocene dune sand" 꼴이다
        unit = units.get(symbol) or {}
        rows.append({"symbol": symbol if unit else "", "lithology": str(unit.get("Name") or label).strip(),
                     "age": i18n.age_tidy(unit.get("Age") or ""), "color": "transparent", "swatch": uri})
    return rows


# ── 속성 ─────────────────────────────────────────────────────────

def _v(props: dict, *keys) -> str:
    for key in keys:
        value = str(props.get(key) if props.get(key) is not None else "").strip()
        if value and value.lower() not in ("null", "no data", "unknown", "<null>", "none reported"):
            return value
    return ""


def friendly(props: dict, lang: str = "ko") -> dict:
    """주의 열 → 한국어 이름. 값(영어)은 그대로, 시대만 옮긴다 — identify 는 별칭(`Unit Symbol`)으로 준다"""
    if "property" in props or "commodities_major" in props:     # 알래스카 광산·산지 (wetherilli 322)
        rows = (("이름", _v(props, "property")), ("광종", _v(props, "commodities_major")), ("핵심 광물", _v(props, "critical_minerals_ardf")),
                ("광종 갈래", _v(props, "commodity_group_map")), ("광상 유형", _v(props, "deposit_type_map")),
                ("개발 단계", _v(props, "property_status")), ("과거 생산", _v(props, "past_producer")), ("자원량 공개", _v(props, "resource_public")))
        return {k: x for k, x in rows if x}
    if "sq_miles" in props or ("region" in props and "name" in props):  # 알래스카 광업 지구
        rows = (("광업 지구", _v(props, "name")), ("권역", " ".join(_v(props, "region").split())))
        return {k: x for k, x in rows if x}
    if "MAP_UNIT_L" in props or "AGE_NAME" in props:             # 오리건 OGDC
        age = i18n.age_tidy(_v(props, "AGE_NAME").replace("/", " - "))
        rows = (("기호", _v(props, "MAP_UNIT_L")), ("이름", _v(props, "MAP_UNIT_N")), ("지층", _v(props, "FORMATION")),
                ("암석", _v(props, "GEO_GENL_U", "LITH_GEN_U")), ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
                ("지구조 구역", _v(props, "TERRANE_GR")), ("설명", _v(props, "des")), ("원도", _v(props, "Citation")))
    elif "MAP_UNIT_100K" in props:                               # 워싱턴 1:10만 GeMS
        rows = (("기호", _v(props, "MAP_UNIT_100K_LABEL", "MAP_UNIT_100K")), ("이름", _v(props, "MAP_UNIT_100K_SYMBOL")),
                ("도폭", _v(props, "MAP_UNIT_100K_QUAD_NAME")))
    elif "_Name" in props or "Map Unit" in props or "Map_Unit" in props:   # 워싱턴 1:50만 — 단위 설명 표를 붙였다
        age = i18n.age_tidy(_v(props, "_Age"))
        rows = (("기호", _v(props, "Map Unit", "Map_Unit", "Label")), ("이름", _v(props, "_Name")), ("암석", _v(props, "_GeoMaterial")),
                ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("설명", _v(props, "_Description")))
    else:                                                        # 네바다 1:50만 (USGIN)
        age = i18n.age_tidy(_v(props, "Geologic History"))
        rows = (("기호", _v(props, "Unit Symbol")), ("이름", _v(props, "Name").title()), ("암석", _v(props, "Lithology")),
                ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("설명", _v(props, "Description")))
    return {k: x for k, x in rows if x}


def _door(upstream: str) -> _NS:
    return _NS(get_map=lambda p: _get_map(upstream, p), get_feature_info=lambda p: _get_feature_info(upstream, p),
               get_legend=_get_legend, friendly=friendly)


NBMG, WADNR, DOGAMI, DGGS = _door("nbmg"), _door("wadnr"), _door("dogami"), _door("dggs")
DOORS = {"nbmg": NBMG, "wadnr": WADNR, "dogami": DOGAMI, "dggs": DGGS}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "dggs", "tag": "DGGS", "title": "알래스카 지질·지구물리조사소", "relay": DOORS["dggs"], "projected": True, "globe": True},
    {"upstream": "dogami", "tag": "DOGAMI", "title": "오리건 지질광물산업부", "relay": DOORS["dogami"], "projected": True, "globe": True},
    {"upstream": "nbmg", "tag": "NBMG", "title": "네바다 광산지질국", "relay": DOORS["nbmg"], "projected": True, "globe": True},
    {"upstream": "wadnr", "tag": "WGS", "title": "워싱턴 지질조사소", "relay": DOORS["wadnr"], "projected": True, "globe": True},
]
