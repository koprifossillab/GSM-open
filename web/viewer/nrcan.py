"""NRCan(캐나다 천연자원부)·GSC 로 나가는 문 — 캐나다 지질도 1:500만 (Wheeler 외 1996) (wetherilli 204).

- 주소: `maps-cartes.services.geo.ca/server_serveur/services/NRCan/geological_map_canada_wheeler_en/MapServer/WMSServer` (ArcGIS WMS).
  열쇠가 없다. 레이어는 `0`(지질 단위) 하나 — 이름은 `nrcan:wheeler`
- Capabilities 는 3978·4326 만 적지만 **3857·3413 도 그대로 그린다**(2026-10-04). 캐나다 탭은 3978(캐나다 람베르트)로 받는다 — devlog 204
- 속성은 `application/geojson` — 단위·대/기/세·암상(RXTP·SUBRXTP)·지질구(GEOLPROV), 그리고 같은 것의 프랑스어 짝(ERE·TPRCH…).
  영어 열만 쓴다. 지질시대는 ICS 영어라 한국어판에서 옮긴다
- CORS 는 Origin 을 되비춘다(정적 판에 실을 수 있다 — 기본값에는 넣지 않았다, #153)
- 조건: Open Government Licence – Canada. 출처 "Natural Resources Canada"
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

LAYERS = {"nrcan:wheeler": "0"}
ATTRIBUTION = ('Geological Map of Canada 1:5M (Wheeler et al. 1996) — <a href="https://open.canada.ca/en/open-government-licence-canada" '
               'target="_blank" rel="noopener">Natural Resources Canada, OGL–Canada</a>')
TIMEOUT = 45


class NrcanError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _numbers(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if one not in LAYERS:
            raise NrcanError(f"모르는 레이어다: {one}")
        out.append(LAYERS[one])
    return ",".join(out)


def _url() -> str:
    return settings.NRCAN_WMS_URL


def _get(params: dict):
    left = usage.paused()
    if left:
        raise NrcanError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(_url(), params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("nrcan", ok=False)
        raise NrcanError(f"NRCan 에 닿지 못했다: {exc}") from exc
    log.info("NRCan %s -> %s", r.url, r.status_code)
    usage.record("nrcan", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.3.0")
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params["layers"] = _numbers(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _numbers(params["query_layers"])
    params.setdefault("styles", "")
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NrcanError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0", "format": "image/png",
              "layer": _numbers(layer), "sld_version": "1.1.0"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NrcanError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    if "x" in params and "i" not in params:
        params["i"], params["j"] = params.pop("x"), params.pop("y", "0")
    r = _get(params)
    if r.status_code != 200:
        raise NrcanError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise NrcanError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업 이름. 적은 것만, 적은 차례로. 프랑스어 짝(UNITE·ERE·TPRCH …)은 뺀다
FRIENDLY = (
    ("UNIT", "기호"),
    ("NAME", "이름"),
    ("RXTP", "암석"),
    ("SUBRXTP", "암석 갈래"),
    ("AGERXTP", "시대별 암석"),
    ("EPOCH", "지질시대"),
    ("PERIOD", "지질시대"),
    ("ERA", "지질시대"),
    ("METGRADE", "변성 정도"),
    ("GEOLPROV", "지질구"),
    ("DOMAIN", "영역"),
    ("COMP", "편집"),
)
AGE_KEYS = ("EPOCH", "PERIOD", "ERA")


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 지질시대는 가장 잘게 가른 것(세 > 기 > 대) 하나이고 한국어판이면 ICS 이름을 옮긴다."""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or label in out:
            continue
        out[label] = i18n.age_ko(value) if key in AGE_KEYS and lang == "ko" else value
    return out
