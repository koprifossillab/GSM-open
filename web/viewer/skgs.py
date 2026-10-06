"""사스카치원 지질조사소(Saskatchewan Geological Survey)로 나가는 문 — 사스카치원 기반암 1:100만·1:25만 (wetherilli 235).

- 주소: `gis.saskatchewan.ca/arcgis/services/Economy/Geology/MapServer/WMSServer` (ArcGIS WMS, GeoAtlas 가 쓰는 것). 열쇠가 없다
- **WMS 레이어 번호가 REST 와 거꾸로다** — WMS `2` 기반암 1:100만(REST 11)·`3` 1:25만(REST 10, 선캄브리아 순상지만)·`11` 큰 단층·전단대 1:100만(REST 2)
- Capabilities 에 3978 이 없지만 **3978 로 물어도 그린다**(2026-10-04) — 캐나다 탭처럼 곧장 받는다
- 속성은 `application/geo+json` — 기호·암상·층서 일곱 단·지역, 시대가 ICS 영어로 누대·대·기(`EON`·`ERA`·`PERIOD`)와 Ma 까지 온다
- 조건: Government of Saskatchewan Standard Unrestricted Use Data License (Version 2.0) — 캐나다 열린 정부 포털의 기록이 그렇게 적는다.
  인용은 "레이어와 날짜를 밝힌다". 출처 "Saskatchewan Geological Survey, Ministry of Energy and Resources"
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "skgs:"
ATTRIBUTION = ('<a href="https://www.saskatchewan.ca/geoatlas" target="_blank" rel="noopener">Saskatchewan Geological Survey</a> '
               "(Ministry of Energy and Resources, Standard Unrestricted Use Data Licence 2.0)")
#: 레이어 → (WMS 번호, 누르기가 되나)
LAYERS = {"skgs:2": ("2", True), "skgs:3": ("3", True), "skgs:11": ("11", False)}
#: 광물 산지 목록 SMDI 6 012 곳·광산 위치(wetherilli 288) → `Economy/Mineral_Exploration` 의 REST 번호. 이 서비스는 WMS 를 켜지 않아(400)
#: REST export·identify 로 옮긴다(`arcwms.rest_*`)
RESOURCES = {"skgs:smdi": "5", "skgs:mines": "1"}


class SkgsError(RuntimeError):
    pass


def _rest_url() -> str:
    return settings.SKGS_WMS_URL.replace("/services/Economy/Geology/MapServer/WMSServer", "/rest/services/Economy/Mineral_Exploration/MapServer")


def _resource(params: dict) -> str:
    names = [n.strip() for n in str(params.get("query_layers") or params.get("layers") or "").split(",") if n.strip()]
    return names[0] if len(names) == 1 and names[0] in RESOURCES else ""


def knows(name: str) -> bool:
    if name in RESOURCES:
        return True
    return name in LAYERS


def queryable(name: str) -> bool:
    return name in RESOURCES or (name in LAYERS and LAYERS[name][1])


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SkgsError(f"모르는 레이어다: {names}")
    return names[0]


def _get(params: dict, url: str = ""):
    left = usage.paused()
    if left:
        raise SkgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url or settings.SKGS_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("skgs", ok=False)
        raise SkgsError(f"사스카치원에 닿지 못했다: {exc}") from exc
    log.info("SKGS %s -> %s", r.url, r.status_code)
    usage.record("skgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    name = _one(params)
    out = dict(params, service="WMS", request=request, layers=LAYERS[name][0])
    if "query_layers" in out:
        out["query_layers"] = LAYERS[name][0]
    out.setdefault("styles", "")
    return out


def get_map(params: dict):
    name = _resource(params)
    if name:
        try:
            r = _get(arcwms.rest_export_params(params, RESOURCES[name]), f"{_rest_url()}/export")
        except ValueError as exc:
            raise SkgsError(str(exc)) from exc
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise SkgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
        return r.content, ctype
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SkgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    if layer in RESOURCES:
        raise SkgsError("광물 산지는 범례를 두지 않는다 — 누르면 광종이 뜬다")
    r = _get({"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "image/png",
              "layer": LAYERS[layer][0] if layer in LAYERS else layer})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise SkgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    name = _resource(params)
    if name:
        try:
            r = _get(arcwms.rest_identify_params(params, RESOURCES[name]), f"{_rest_url()}/identify")
            data = r.json()
        except ValueError as exc:
            raise SkgsError(str(exc)) from exc
        if r.status_code != 200 or data.get("error"):
            raise SkgsError(f"속성을 읽지 못했다 (status={r.status_code})")
        return {"features": arcwms.identify_features(data, name)}
    if not queryable(_one(params)):
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    r = _get(params)
    if r.status_code != 200:
        raise SkgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise SkgsError("속성이 JSON 이 아니다") from exc


def _v(props: dict, key: str) -> str:
    value = str(props.get(key) if props.get(key) is not None else "").strip()
    return "" if value.lower() in ("null", "none") else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 암상·층서는 영어 그대로, 시대(가장 자세한 마디)만 옮긴다."""
    v = lambda k: _v(props, k)          # noqa: E731
    if "SMDI" in props or "PRIMARYCOMMODITIES" in props:            # SMDI (wetherilli 288)
        # query 는 큰 글자 이름(`PRIMARYCOMMODITIES`), identify 는 별칭(`PrimaryCommodities`)으로 준다
        up = {str(k).upper(): val for k, val in props.items()}
        u = lambda k: _v(up, k)                                      # noqa: E731
        link = u("WEBLINK")
        rows = (("이름", u("NAME")), ("번호", u("SMDI")), ("광종", u("PRIMARYCOMMODITIES")), ("딸린 광종", u("ASSOCIATEDCOMMODITIES")),
                ("갈래", u("GROUPING")), ("개발 단계", u("STATUS")), ("발견", u("DISCOVERYTYPE")), ("생산", u("PRODUCTION")),
                ("상세", {"text": "", "links": [{"url": link, "label": "SMDI"}]} if link.startswith(("http://", "https://")) else ""))
        return {k: x for k, x in rows if x}
    age = v("PERIOD") or v("ERA") or v("EON")
    strat = " · ".join(x for x in (v(f"STRAT_LEV{n}") for n in range(2, 8)) if x)
    rows = (("기호", v("ROCK_CODE_1M") or v("ROCK_CODE")), ("암석", v("LITHOLOGY")), ("층서", strat),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("연대 (Ma)", v("Age_Ma")),
            ("지역", v("Geological_Region_1M") or v("COMMENT")))
    return {k: x for k, x in rows if x}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "skgs", "tag": "SGS-SK", "title": "사스카치원 지질조사소", "relay": True, "projected": True, "globe": True},
]
