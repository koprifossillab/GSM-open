"""EGDI(유럽 지질 자료 기반, EuroGeoSurveys)로 나가는 문 — 범유럽 1:100만 지표 지질도 (wetherilli 143).

- 주소: `geoserver.geo-zs.si/egdi-surface-geology/gsmlp/wms` (GeoServer, 슬로베니아 지질조사소가 올린다). 열쇠가 없다.
  나라마다의 INSPIRE 1:100만 지표 지질을 모은 것이라 영국·아일랜드·프랑스·스페인·독일을 다 덮는다
- 조건: GetCapabilities 의 AccessConstraints·Fees 가 `NONE`. 출처는 EGDI·EuroGeoSurveys 와 각국 지질조사소
- 3857 을 그대로 받는다. **느리다** — 512 칸 한 장에 9 초 남짓(2026-10-02). 받은 것은 캐시에 담으니 두 번째부터는 빠르다
- **속성은 묻지 않는다.** GetFeatureInfo 가 시대 판은 DB 오류를, 암상 판은 20 초 뒤 빈 답을 준다(2026-10-02) — 카탈로그에서 누르지
  못하게 둔다(`views._layer_extra`). 상류가 고치면 `QUERYABLE` 을 켠다
- 레이어명에 `egdi:` 를 붙여 카탈로그에 둔다. 상류로 나갈 때 뗀다
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "egdi:"
ATTRIBUTION = ('<a href="https://www.europe-geology.eu/" target="_blank" rel="noopener">EGDI</a>'
               " 1:1M surface geology · EuroGeoSurveys")
QUERYABLE = False


class EgdiError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise EgdiError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.EGDI_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("egdi", ok=False)
        raise EgdiError(f"EGDI 에 닿지 못했다: {exc}") from exc
    log.info("EGDI %s -> %s", r.url, r.status_code)
    usage.record("egdi", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise EgdiError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise EgdiError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    """화면은 묻지 않는다(`QUERYABLE`). 누가 불러도 상류의 DB 오류를 그대로 올리지 않게 빈 답을 준다."""
    return {"features": []}
