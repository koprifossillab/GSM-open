"""GNS Science(뉴질랜드 지질·핵과학연구소)로 나가는 문 — 뉴질랜드 QMAP 1:25만·1:100만, 남극 남빅토리아랜드 1:25만 (wetherilli 218).

- 주소: `maps.gns.cri.nz/geology/wms` (GeoServer WMS). 열쇠가 없다
- 조건: **CC BY 3.0 NZ** — Capabilities 의 AccessConstraints 가 "Copyright GNS Science 2014. … released free under the Creative Commons
  Attribution 3.0 New Zealand (CC-BY 3.0) Licence" 다. 출처를 밝힌다. `ATTRIBUTION`
- 뉴질랜드는 3857, 남빅토리아랜드는 3031 로 곧장 받는다 — GeoServer 가 다시 투영해 그린다(2026-10-04, 3031 256² 2.0 초)
- **QMAP 합본(`…seamless_qmap_geological_map_current_view`)은 넓게 보면 느리다** — 나라 전체 512² 가 34 초, 줌 8 칸 하나는 2.1 초.
  그래서 줌 7 부터 그리고, 그보다 넓으면 1:100만(나라 전체 2.3 초)이 바탕이다. 합본은 단층·경계까지 한 장에 그려 준다
- 속성은 `application/json`. **뉴질랜드 판은 모양까지 딸려 온다**(1:25만 26 KB, 1:100만 140 KB) — `propertyName` 으로 열을 골라 묻는다
  (629 B). 열 이름이 판마다 달라 레이어마다 적는다. 없는 열을 적으면 상류가 예외를 낸다. 합본은 누를 때 단위 레이어
  (`NZL_GNS_250K_geologic_units`)에 묻는다
- 연대는 숫자(Ma, `abs_min`·`abs_max`)로 온다 — 1:25만의 `strat_age` 는 뉴질랜드 층서 부호(`Q2`·`Tr J`)라, 숫자에서 ICS 시대를 고른다
  (`ics_span`). 1:100만은 ICS 영어(`geolhist`)가 그대로 온다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('<a href="https://www.gns.cri.nz/" target="_blank" rel="noopener">© GNS Science</a> (CC BY 3.0 NZ)')

_QMAP_FIELDS = ("code,main_rock,sub_rocks,key_name,stratlex,strat_age,abs_min,abs_max,descriptio,qmap_name,"
                "terrane_eq,supergroup")
_GMNZ_FIELDS = "mapsymbol,name,descr,geolhist,lithology,sgrpequiv,terrequiv,absmin_ma,absmax_ma"

#: 우리 이름 → 부를 상류 레이어, 누를 때 묻는 레이어(없으면 누르지 않는다), 고를 열(없으면 다 받는다), 투영, 이 줌부터
LAYERS = {
    "gns:qmap": {"wms": "NZL_GNS_250K_seamless_qmap_geological_map_current_view", "query": "NZL_GNS_250K_geologic_units",
                 "fields": _QMAP_FIELDS, "crs": "EPSG:3857", "min": 7},
    "gns:NZL_GNS_1M_geological_units": {"wms": "gns:NZL_GNS_1M_geological_units", "query": "gns:NZL_GNS_1M_geological_units",
                                        "fields": _GMNZ_FIELDS, "crs": "EPSG:3857"},
    "gns:NZL_GNS_1M_faults": {"wms": "gns:NZL_GNS_1M_faults", "crs": "EPSG:3857"},
    "gns:NZL_GNS_250K_faults": {"wms": "gns:NZL_GNS_250K_faults", "crs": "EPSG:3857", "min": 7},
    "gns:NZL_GNS_250K_folds": {"wms": "gns:NZL_GNS_250K_folds", "crs": "EPSG:3857", "min": 8},
    "gns:NZL_GNS_250K_metamorphic_zones": {"wms": "gns:NZL_GNS_250K_metamorphic_zones", "crs": "EPSG:3857", "min": 7},
    # 남극 남빅토리아랜드 — 남극 탭(3031)에 얹는다. 속성에 모양이 딸려 오지 않아(850 B) 열을 고르지 않는다
    "gns:ATA_SVL_GNS_250K_geological_units": {"wms": "gns:ATA_SVL_GNS_250K_geological_units",
                                              "query": "gns:ATA_SVL_GNS_250K_geological_units", "crs": "EPSG:3031"},
    "gns:ATA_SVL_GNS_250K_faults": {"wms": "gns:ATA_SVL_GNS_250K_faults", "crs": "EPSG:3031"},
    # 중력 이상(wetherilli 269) — 지질 서비스(`/geology/wms`)가 아니라 GNS 전체 서비스(`/gns/wms`)에만 있다. 그림이라 누르지 않는다
    "gns:gravity": {"wms": "gns:NZGravity", "crs": "EPSG:3857", "service": "all"},
}
#: 범례 그림을 두지 않는 레이어 — 합본은 칸이 수천이라 그림이 쓸모없이 크다. 누르면 단위가 뜬다
NO_LEGEND = ("gns:qmap",)

#: ICS 의 바닥 나이(Ma)와 이름 — 젊은 것부터. 제4기·신진기·고진기는 세(Epoch)까지, 그보다 오래면 기(Period)까지
_ICS = (
    (0.0117, "Holocene"), (0.129, "Late Pleistocene"), (0.774, "Middle Pleistocene"), (2.58, "Early Pleistocene"),
    (5.333, "Pliocene"), (23.03, "Miocene"), (33.9, "Oligocene"), (56.0, "Eocene"), (66.0, "Paleocene"),
    (145.0, "Cretaceous"), (201.4, "Jurassic"), (251.9, "Triassic"), (298.9, "Permian"), (358.9, "Carboniferous"),
    (419.2, "Devonian"), (443.8, "Silurian"), (485.4, "Ordovician"), (538.8, "Cambrian"),
    (1000.0, "Neoproterozoic"), (1600.0, "Mesoproterozoic"), (2500.0, "Paleoproterozoic"), (4031.0, "Archean"),
)
#: 경계에서 이만큼(나이의 비율) 안쪽이면 이웃 시대로 친다 — 상류가 경계 나이를 둥글려 적는다(`Tr J` 단위가 142 Ma 까지 내려온다)
_SLACK = 0.03


class GnsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return bool(name) and all(n.strip() in LAYERS for n in str(name).split(","))


def queryable(name: str) -> bool:
    return bool(LAYERS.get(name, {}).get("query"))


def _names(names: str, key: str = "wms") -> str:
    if not knows(names):
        raise GnsError(f"모르는 레이어다: {names}")
    return ",".join(LAYERS[n.strip()][key] for n in names.split(","))


def _url(names: str) -> str:
    """지질 서비스와 GNS 전체 서비스 — 레이어의 `service` 가 가른다 (wetherilli 269)"""
    first = str(names or "").split(",")[0].strip()
    return settings.GNS_ALL_WMS_URL if LAYERS.get(first, {}).get("service") == "all" else settings.GNS_WMS_URL


def _get(params: dict, url: str = ""):
    left = usage.paused()
    if left:
        raise GnsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url or settings.GNS_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 45),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gns", ok=False)
        raise GnsError(f"GNS 에 닿지 못했다: {exc}") from exc
    log.info("GNS %s -> %s", r.url, r.status_code)
    usage.record("gns", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    if "layers" in params:
        params["layers"] = _names(params["layers"])
    return params


def get_map(params: dict):
    url = _url(params.get("layers"))
    r = _get(_wms(params, "GetMap"), url)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GnsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    if layer in NO_LEGEND:
        raise GnsError("이 레이어는 범례 그림을 두지 않는다")
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": _names(layer)}, _url(layer))
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GnsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    name = str(params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
    if not queryable(name):
        raise GnsError(f"누를 수 없는 레이어다: {name}")
    spec = LAYERS[name]
    params = _wms(params, "GetFeatureInfo")
    params["layers"] = params["query_layers"] = spec["query"]
    params["info_format"] = "application/json"
    params["feature_count"] = "1"
    if spec.get("fields"):
        params["propertyName"] = spec["fields"]
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise GnsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise GnsError("속성이 JSON 이 아니다") from exc


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ics_at(ma: float, young: bool) -> str:
    """그 나이를 품은 ICS 이름. 경계 바로 밑(`_SLACK` 안)이면 — 젊은 끝은 더 오랜 쪽, 오랜 끝은 더 젊은 쪽으로 — 이웃에 붙인다"""
    for i, (base, name) in enumerate(_ICS):
        if ma < base:
            top = _ICS[i - 1][0] if i else 0.0
            if young and i + 1 < len(_ICS) and base - ma < base * _SLACK:
                return _ICS[i + 1][1]
            if not young and i and ma - top < ma * _SLACK:
                return _ICS[i - 1][1]
            return name
    return _ICS[-1][1]


def ics_span(young, old) -> str:
    """숫자 나이(Ma) 둘 → ICS 이름(영어). 같으면 하나, 다르면 `오랜 – 젊은`. 0·0 은 얼음 따위라 빈 글"""
    young, old = _number(young), _number(old)
    if young is None or old is None or old <= 0:
        return ""
    a, b = _ics_at(old, young=False), _ics_at(young, young=True)
    return a if a == b else f"{a} – {b}"


def _value(props: dict, key: str) -> str:
    value = props.get(key)
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("none", "null") else text


def _ma(young, old) -> str:
    young, old = _number(young), _number(old)
    if young is None or old is None or old <= 0:
        return ""
    fmt = lambda v: f"{v:g}"          # noqa: E731
    return f"{fmt(old)}–{fmt(young)} Ma"


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·암석·설명은 영어 그대로, 지질시대만 옮긴다. 1:100만(`geolhist`)은 ICS 영어가 오고,
    1:25만은 숫자 나이에서 고른다"""
    age = _value(props, "geolhist")
    if age:
        ma = _ma(props.get("absmin_ma"), props.get("absmax_ma"))
        rows = (("기호", _value(props, "mapsymbol")), ("이름", _value(props, "name")), ("설명", _value(props, "descr")),
                ("암석", _value(props, "lithology")), ("초층군", _value(props, "sgrpequiv")),
                ("지구조 구역", _value(props, "terrequiv")))
    else:
        age = ics_span(props.get("abs_min"), props.get("abs_max"))
        ma = _ma(props.get("abs_min"), props.get("abs_max"))
        rock = ", ".join(x for x in (_value(props, "main_rock"), _value(props, "sub_rocks")) if x)
        rows = (("기호", _value(props, "code") or _value(props, "unit_code")),
                ("이름", _value(props, "key_name") or _value(props, "stratlex") or _value(props, "strat_unit")),
                ("설명", _value(props, "descriptio")), ("암석", rock),
                ("초층군", _value(props, "supergroup")),
                ("지구조 구역", _value(props, "terrane_eq") or _value(props, "terrane")),
                ("도폭", _value(props, "qmap_name")))
    out = {k: v for k, v in rows if v}
    if age:
        out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
    if ma:
        out["연대"] = ma
    return out
