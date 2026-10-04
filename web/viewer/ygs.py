"""YGS(유콘 지질조사소)로 나가는 문 — 유콘 기반암 지질도 1:25만 (wetherilli 210).

- 주소: `mapservices.gov.yk.ca/arcgis/services/GeoYukon/GY_Geological/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다.
  WMS 레이어 `47` 기반암·`50` 단층(REST 로는 113·114 — 번호가 다르다)
- Capabilities 에 3978 이 없지만 **3978 로 물어도 그린다**(2026-10-04) — 캐나다 탭처럼 3978 로 곧장 받는다
- **넓게 보면 느리다** — 준주 전체(줌 5) 한 장이 12.9 초, 화이트호스 둘레(줌 9) 0.6 초. 그래서 화면 줌 7 부터 그린다. 그보다 멀면
  NRCan 1:500만이 덮는다. 그림에 단위 기호·무늬가 박혀 있다. 단층은 상류가 1:64만보다 가까울 때만 그린다(화면 줌 10 남짓)
- 속성은 `application/geo+json` — 기하 없이 1.5 KB. 단위(1:100만·1:25만 기호)·지층·암상·짧은 설명, 그리고 시대가 **ICS 영어**로
  오래된 쪽(ERA/PERIOD/EPOCH/STAGE_MAX)과 젊은 쪽(…_MIN), Ma 까지 온다. 한국어판이면 옮긴다. 빈 값은 `"Null"` 글자다
- 조건: Open Government Licence – Yukon — 상업 이용까지 허락하고 출처 표기를 바란다. 출처 "Government of Yukon"
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "ygs:"
ATTRIBUTION = ('<a href="https://data.geology.gov.yk.ca/" target="_blank" rel="noopener">Yukon Geological Survey</a> '
               "(Government of Yukon, OGL–Yukon)")
#: 레이어 → (WMS 번호, 처음 그리는 화면 줌, 누르기가 되나)
LAYERS = {"ygs:47": ("47", 7, True), "ygs:50": ("50", 10, False)}


class YgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def queryable(name: str) -> bool:
    return name in LAYERS and LAYERS[name][2]


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise YgsError(f"모르는 레이어다: {names}")
    return names[0]


def _get(params: dict):
    left = usage.paused()
    if left:
        raise YgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.YGS_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ygs", ok=False)
        raise YgsError(f"유콘에 닿지 못했다: {exc}") from exc
    log.info("YGS %s -> %s", r.url, r.status_code)
    usage.record("ygs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    name = _one(params)
    out = dict(params, service="WMS", request=request, layers=LAYERS[name][0])
    if "query_layers" in out:
        out["query_layers"] = LAYERS[name][0]
    out.setdefault("styles", "")
    return out


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise YgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "image/png",
              "layer": LAYERS[layer][0] if layer in LAYERS else layer})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise YgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    if not queryable(_one(params)):
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    r = _get(params)
    if r.status_code != 200:
        raise YgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise YgsError("속성이 JSON 이 아니다") from exc


def _v(props: dict, key: str) -> str:
    value = str(props.get(key) if props.get(key) is not None else "").strip()
    return "" if value.lower() in ("null", "none") else value


def _age(props: dict, lang: str) -> str:
    """가장 자세한 시대 — 절이 있으면 절, 없으면 세·기·대. 오래된 것과 젊은 것이 다르면 `오랜 - 젊은`."""
    for level in ("STAGE", "EPOCH", "PERIOD", "ERA"):
        old, young = _v(props, f"{level}_MAX"), _v(props, f"{level}_MIN")
        if old or young:
            age = old if old == young or not young else (young if not old else f"{old} - {young}")
            return i18n.age_ko(age) if lang == "ko" else age
    return ""


def friendly(props: dict, lang: str = "ko") -> dict:
    v = lambda k: _v(props, k)          # noqa: E731
    ma = " – ".join(x for x in (v("AGE_MIN_MA"), v("AGE_MAX_MA")) if x)
    rows = (("기호", v("UNIT_250K") or v("UNIT_1M")), ("지층", v("FORMATION") or v("GP_SUITE") or v("ASSEMBLAGE")),
            ("암석", v("SHORT_DESCRIPTION") or v("ROCK_MAJOR")), ("암석 분류", v("ROCK_CLASS")), ("지질시대", _age(props, lang)),
            ("연대 (Ma)", ma), ("지구조 요소", v("TECTONIC_ELEMENT")), ("지괴", v("TERRANE")))
    return {k: x for k, x in rows if x}
