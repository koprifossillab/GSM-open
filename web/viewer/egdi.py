"""EGDI(유럽 지질 자료 기반, EuroGeoSurveys)로 나가는 문 — 범유럽 1:100만 지표 지질도 (wetherilli 143).

- 주소: `geoserver.geo-zs.si/egdi-surface-geology/gsmlp/wms` (GeoServer, 슬로베니아 지질조사소가 올린다). 열쇠가 없다.
  나라마다의 INSPIRE 1:100만 지표 지질을 모은 것이라 영국·아일랜드·프랑스·스페인·독일을 다 덮는다
- 조건: GetCapabilities 의 AccessConstraints·Fees 가 `NONE`. 출처는 EGDI·EuroGeoSurveys 와 각국 지질조사소
- 3857 을 그대로 받는다. **느리다** — 512 칸 한 장에 9 초 남짓(2026-10-02). 받은 것은 캐시에 담으니 두 번째부터는 빠르다
- **속성은 암상 판에만 묻는다** (wetherilli 177). 2026-10-02 에는 시대 판이 DB 오류를, 암상 판이 20 초 뒤 빈 답을 줬다. 2026-10-04 에
  다시 재니 암상 판은 2–3 초에 답하고 시대 판은 여전히 DB 오류다. 두 판은 같은 덩이(`GeologicUnitView`)를 다르게 칠한 것이고 암상 판의
  답에 시대 URI 도 들어 있어, 어느 레이어를 눌러도 암상 판(`QUERY_LAYER`)에 묻는다. 다시 죽으면 `QUERYABLE` 을 끈다
- 레이어명에 `egdi:` 를 붙여 카탈로그에 둔다. 상류로 나갈 때 뗀다
"""
import logging
import re

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "egdi:"
ATTRIBUTION = ('<a href="https://www.europe-geology.eu/" target="_blank" rel="noopener">EGDI</a>'
               " 1:1M surface geology · EuroGeoSurveys")
QUERYABLE = True
#: 속성을 묻는 판 — 시대 판은 2026-10-04 에도 DB 오류라 암상 판에 묻는다(같은 덩이다)
QUERY_LAYER = "GeologicUnitView_Lithology"
#: 누른 둘레(픽셀). 기본값이면 이웃 면이 서넛 함께 온다
QUERY_BUFFER = 1


#: 메타타일로 받는다 (wetherilli 284) — 1 024 px 한 장이 10 초 남짓이고 예외(서비스 예외 XML)가 잦다. 큰 장이 실패하면 칸 하나로 되받는다
#: (`metatile.serve` 의 `errors`). `metatile.limit` 의 표
METATILE = {"egdi:": None}

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
    usage.record("egdi", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
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
    """누른 자리의 단위 — 암상 판에 JSON 으로 묻는다. 모양(수만 꼭짓점)은 버리고 속성만 캐시에 담는다."""
    if not QUERYABLE:
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params.update(layers=QUERY_LAYER, query_layers=QUERY_LAYER, info_format="application/json",
                  feature_count=3, buffer=QUERY_BUFFER)
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise EgdiError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        body = r.json()
    except ValueError as exc:
        # 상류가 탈 나면 200 에 XML 예외(ServiceExceptionReport)를 싣는다
        raise EgdiError("속성이 JSON 이 아니다 — 상류 예외") from exc
    return {"features": [{"id": f.get("id", ""), "properties": f.get("properties") or {}}
                         for f in body.get("features") or []]}


_NIL = "http://www.opengis.net/def/nil/"
#: INSPIRE 시대 낱말 → ICS. 아래·위 통(lower·upper)은 전기·후기이고, `ionian` 은 ICS 가 2020 년에 Chibanian 으로 정했다
_AGE_WORDS = {"lower": "Early", "upper": "Late", "middle": "Middle", "ionian": "Chibanian"}


def _age_word(uri) -> str:
    """`…/GeochronologicEraValue/lowerCretaceous` → `Early Cretaceous`. 모르면 빈 글자."""
    uri = str(uri or "")
    if not uri or uri.startswith(_NIL):
        return ""
    code = uri.rstrip("/").rsplit("/", 1)[-1]
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", code).split()
    return " ".join(_AGE_WORDS.get(w.lower(), w[:1].upper() + w[1:]) for w in words)


def friendly(props: dict, lang: str = "ko") -> dict:
    """암상·지질시대·제공 기관. 암상은 INSPIRE 의 영어 낱말 그대로(속성 값이라 옮기지 않는다), 시대는 한국어판이면 옮긴다."""
    out = {}
    lith = str(props.get("lithology") or "").strip()
    if lith and not lith.startswith(_NIL):
        out["암상"] = lith
    older, younger = _age_word(props.get("representativeOlderAge_uri")), _age_word(props.get("representativeYoungerAge_uri"))
    age = f"{older} - {younger}" if older and younger and older != younger else (_age_word(props.get("representativeAge_uri"))
                                                                               or older or younger)
    if age:
        out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
    # 식별자의 끝 — `…/GeologicUnitView/FR-BRGM.1353.57975` 의 `FR-BRGM` 이 그 면을 낸 나라·기관이다
    ident = str(props.get("identifier") or "").rsplit("/", 1)[-1]
    if "-" in ident.split(".", 1)[0]:
        out["제공 기관"] = ident.split(".", 1)[0]
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "egdi", "tag": "EGDI", "title": "EGDI (EuroGeoSurveys)", "relay": True, "projected": True, "globe": True},
]
