"""ISPRA(이탈리아 환경보호연구원)·이탈리아 지질조사소(Servizio Geologico d'Italia)로 나가는 문 — 이탈리아 지질도 1:100만·1:10만 (wetherilli 211).

- 주소: `sgi2.isprambiente.it/arcgis/services/servizi/<서비스>/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다
  - `geologia1M` — WMS `0` 지질 단위·`1` 단층 (REST 와 번호가 거꾸로다 — REST 0 이 단층)
  - `carta_geologica_100k` — 옛 1:10만 지질도를 벡터로 옮긴 것. WMS `1` 지질 단위·`2` 지구조(REST 14·13). **상류가 1:50만보다 가까울 때만 그린다**
- 1:100만 Capabilities 는 4326 만 적지만 3857 GetMap 이 된다(2026-10-04). 이름은 `ispra:<판>:<WMS 번호>`
- 속성은 `application/geojson` — 1:100만은 성인·환경·조산 주기·설명·시대(위·아래)·암상, 1:10만은 층 이름·시대·범례 글. 값은 이탈리아어 그대로 둔다
- CORS 는 Origin 을 되비춘다. 조건(Capabilities AccessConstraints): "자료는 보고 열람하는 데 자유롭고, 지적 재산과 알맞은 축척을 지켜 쓴다", 무료.
  출처 "ISPRA – Servizio Geologico d'Italia"
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 우리 이름 → (서비스, WMS 번호)
LAYERS = {
    "ispra:1m:0": ("geologia1M", "0"),
    "ispra:1m:1": ("geologia1M", "1"),
    "ispra:100k:1": ("carta_geologica_100k", "1"),
    "ispra:100k:2": ("carta_geologica_100k", "2"),
}
#: 상류가 그리는 줌 (첫, 끝) — 1:10만 단위는 1:50만(3857 줌 10)부터, 지구조는 1:100만(줌 9)부터
ZOOMS = {"ispra:100k:1": (10, None), "ispra:100k:2": (9, None)}
#: 메타타일로 받는다 (wetherilli 287) — 1:100만 512 px 11.3–14.9 초, 1 024 px 19.1 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"ispra:1m:": None}

ATTRIBUTION = ('Carta Geologica d\'Italia — <a href="https://www.isprambiente.gov.it/it/attivita/suolo-e-territorio/cartografia" '
               'target="_blank" rel="noopener">ISPRA – Servizio Geologico d\'Italia</a>')
TIMEOUT = 45


class IspraError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _split(names: str) -> tuple:
    services, numbers = set(), []
    for one in str(names or "").split(","):
        one = one.strip()
        if one not in LAYERS:
            raise IspraError(f"모르는 레이어다: {one}")
        service, number = LAYERS[one]
        services.add(service)
        numbers.append(number)
    if len(services) != 1:
        raise IspraError("판이 다른 레이어를 한 번에 묻지 않는다")
    return services.pop(), ",".join(numbers)


def _url(service: str) -> str:
    return f"{settings.ISPRA_URL.rstrip('/')}/services/servizi/{service}/MapServer/WMSServer"


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise IspraError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ispra", ok=False)
        raise IspraError(f"ISPRA 에 닿지 못했다: {exc}") from exc
    log.info("ISPRA %s -> %s", r.url, r.status_code)
    usage.record("ispra", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> tuple:
    service, numbers = _split(params.get("layers") or params.get("query_layers"))
    params = dict(params, service="WMS", request=request, version="1.3.0", layers=numbers)
    if "query_layers" in params:
        params["query_layers"] = _split(params["query_layers"])[1]
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params.setdefault("styles", "")
    return _url(service), params


def get_map(params: dict):
    url, params = _wms(params, "GetMap")
    r = _get(url, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IspraError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    service, number = _split(layer)
    r = _get(_url(service), {"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0", "format": "image/png",
                             "layer": number, "sld_version": "1.1.0"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IspraError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    url, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    if "x" in params and "i" not in params:
        params["i"], params["j"] = params.pop("x"), params.pop("y", "0")
    r = _get(url, params)
    if r.status_code != 200:
        raise IspraError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise IspraError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업 이름. 적은 것만, 적은 차례로 — 1:100만과 1:10만의 열이 다르다
FRIENDLY = (
    ("NOME_FORMAZIONE", "이름"),
    ("Descrizione", "설명"),
    ("LEGENDA", "설명"),
    ("ETA_FORMAZIONE", "지질시대"),
    ("Litho1", "암석"),
    ("Genetica", "성인"),
    ("Ambiente", "퇴적 환경"),
    ("Ciclo_Orog", "조산 주기"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(이탈리아어)은 그대로 둔다. 1:100만의 시대는 아래·위 두 열을 하나로 잇는다."""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip().replace("&quot;", '"')
        if value and value.lower() != "null" and label not in out:
            out[label] = value
    low, high = (str(props.get(k) or "").strip() for k in ("eta_inf", "eta_sup"))
    if low and "지질시대" not in out:
        out["지질시대"] = low if not high or high == low else f"{low} – {high}"
    if props.get("Litho2") and out.get("암석"):
        out["암석"] = f"{out['암석']}, {str(props['Litho2']).strip()}"
    return out
