"""브리티시컬럼비아 지질조사소(BCGS)로 나가는 문 — BC Digital Geology 기반암 (wetherilli 231).

- 주소: `openmaps.gov.bc.ca/geo/pub/WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW/ows` (GeoServer WMS). 레이어
  `pub:WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW`. 열쇠가 없다. 1:5만–1:25만 합본
- **1:50만보다 넓게 보면 그리지 않는다** — 색 스타일(`1903`)의 519 칸이 모두 `MaxScaleDenominator 500000` 이고, 레이어도 1:70만 너머는 빈다.
  스타일을 우리가 보내면(SLD_BODY) 넓게도 칠하겠지만 640 KB 라 주소에 실을 수 없다. 그래서 **줌 11 부터** 얹고(1:27만 남짓), 그보다
  넓으면 캐나다 탭의 Wheeler 1:500만이 밑을 맡는다. 줌 10 은 1:55만이라 빈 그림이었다(2026-10-04)
- Capabilities 는 3005·CRS:84 만 적지만 **3978 GetMap 이 그린다** — 캐나다 탭의 투영으로 곧장 받는다(캄루프스 둘레 512² 2.6 초).
  처음 한 장은 9.5 초 걸렸다(wetherilli 210)
- 속성은 `application/json` 인데 **모양까지 딸려 와 80 KB** 다 — `propertyName` 으로 열을 골라 묻는다(뉴질랜드 `gns.py` 와 같다).
  열이 넉넉하다 — 층서명·암상·시대(Ma)·지구조 구역(terrane)·지은이
- 범례는 GeoServer 그림(326×3480) 그대로
- 조건: **Open Government Licence – British Columbia**(AccessConstraints NONE). CORS 머리가 없어 정적 판은 곧장 못 부른다 — 서버 문으로만
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "bcgs:"
ATTRIBUTION = ('<a href="https://www2.gov.bc.ca/gov/content/industry/mineral-exploration-mining/british-columbia-geological-survey" '
               'target="_blank" rel="noopener">BC Geological Survey</a> (Open Government Licence – British Columbia)')
LAYERS = {"bcgs:bedrock": "pub:WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW"}
#: 이 줌부터 그린다 — 색 스타일이 1:50만 너머를 칠하지 않는다
MIN_ZOOM = 11
FIELDS = ("STRATIGRAPHIC_UNIT_CODE,STRATIGRAPHIC_NAME,ROCK_TYPE_DESCRIPTION,ROCK_CLASS,ORIGINAL_DESCRIPTION,"
          "MAXIMUM_AGE_NAME,MINIMUM_AGE_NAME,MAXIMUM_AGE_VALUE,MINIMUM_AGE_VALUE,GEOLOGICAL_PERIOD,TERRANE_NAME,"
          "MORPHOTECTONIC_BELT,AUTHOR_NAMES")


class BcgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "") in LAYERS


def _names(names: str) -> str:
    if not all(knows(n.strip()) for n in str(names or "").split(",")):
        raise BcgsError(f"모르는 레이어다: {names}")
    return ",".join(LAYERS[n.strip()] for n in names.split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise BcgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.BCGS_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bcgs", ok=False)
        raise BcgsError(f"BC openmaps 에 닿지 못했다: {exc}") from exc
    log.info("BCGS %s -> %s", r.url, r.status_code)
    usage.record("bcgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = _names(params[key])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BcgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png", "layer": _names(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BcgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params.update(info_format="application/json", feature_count="1", propertyName=FIELDS)
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise BcgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BcgsError("속성이 JSON 이 아니다") from exc


def _value(props: dict, key: str) -> str:
    value = props.get(key)
    return "" if value is None else str(value).strip()


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·암석·설명은 영어 그대로, 시대만 옮긴다(`Upper Triassic` → 트라이아스기 후기)"""
    old, young = _value(props, "MAXIMUM_AGE_NAME"), _value(props, "MINIMUM_AGE_NAME")
    age = i18n.age_tidy(old if old == young or not young else f"{old} - {young}") or _value(props, "GEOLOGICAL_PERIOD")
    hi, lo = _value(props, "MAXIMUM_AGE_VALUE"), _value(props, "MINIMUM_AGE_VALUE")
    rows = (("기호", _value(props, "STRATIGRAPHIC_UNIT_CODE")), ("이름", _value(props, "STRATIGRAPHIC_NAME")),
            ("암석", _value(props, "ROCK_TYPE_DESCRIPTION")), ("원 설명", _value(props, "ORIGINAL_DESCRIPTION")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
            ("연대", f"{hi}–{lo} Ma" if hi and lo else ""),
            ("지구조 구역", " · ".join(x for x in (_value(props, "TERRANE_NAME"), _value(props, "MORPHOTECTONIC_BELT")) if x)),
            ("편집", _value(props, "AUTHOR_NAMES")))
    return {k: v for k, v in rows if v}
