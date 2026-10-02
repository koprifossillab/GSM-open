"""상류로 나가는 유일한 문.

뷰는 여기를 거치지 않고 `requests` 를 부르지 않는다. 상류가 바뀌거나 주소가
닫힐 때 고칠 자리를 하나로 묶어두려는 것이다. CLAUDE.md 의 "구조" 를 볼 것.

인증키는 이 파일 밖으로 나가지 않는다 — 브라우저에게도, 로그에게도.
"""
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 브라우저가 넘겨도 되는 WMS 변수. 여기 없는 것은 버린다.
#: `key` 가 빠져 있는 것이 이 목록의 요점이다 — 키는 서버가 붙인다.
ALLOWED = {
    "service", "version", "request", "layers", "query_layers", "styles",
    "srs", "crs", "bbox", "width", "height", "format", "transparent",
    "bgcolor", "exceptions", "tiled", "info_format", "feature_count",
    "x", "y", "i", "j", "buffer",
}

_KEY_RE = re.compile(r"(key=)[^&\s]*", re.I)

#: 오픈API 로 열린 GeoServer 워크스페이스. 개발 스위치가 켜졌을 때만 쓴다.
OPEN_WORKSPACE = "geoOpen"


def redact(text: str) -> str:
    """로그에 남길 문자열에서 인증키를 지운다."""
    return _KEY_RE.sub(r"\1…", text or "")


def has_key() -> bool:
    """상류에 요청을 낼 수 있는 상태인가.

    개발 스위치가 켜져 있으면 키 없이도 낼 수 있다 — 그 길은 키를 묻지
    않기 때문이다. 뷰가 "키가 없다" 안내 타일을 띄울지 판단할 때 쓴다.
    """
    return bool(settings.KIGAM_KEY) or settings.DEV_DIRECT_WMS


#: `/openapi/wms` 가 막아둔 요청. 이것만은 인증키가 있어도 GeoServer 로 간다.
#: 2026-09-27 에 키를 받아 대조해 보니 `GetMap`·`GetLegendGraphic` 은 되고
#: `GetFeatureInfo` 는 형식·판을 바꿔도 500 이었다 — 문서의 "`REQUEST=GetMap`
#: 고정" 이 그 뜻이다. 속성을 못 읽는 뷰어는 반쪽이라 이것만 갈라 보낸다.
#: devlog 006 을 볼 것. `/openapi/wms` 가 열어주면 여기서 지운다.
DIRECT_REQUESTS = {"getfeatureinfo"}

#: GeoServer 의 낱레이어를 엮어 만든 레이어 — `/openapi/wms` 에 없는 판이다.
#: `L_50K_Geology_Map` 은 묶음(layer group)이라 층리·엽리 기호만 빼 달라는
#: 요청이 WMS 에 없다. 그래서 묶음을 이루는 낱레이어 가운데 자세 기호가 아닌
#: 것만 골라 부른다. `/openapi/wms` 는 낱레이어 이름에 빈 그림을 준다
#: (docs/KIGAM_5만_구조요소.md §8).
#:
#: **그림(`GetMap`)만 GeoServer 로 간다.** 속성·범례는 `base` 묶음으로 바꿔
#: 지금 길 그대로 묻는다 — 낱레이어의 속성은 칸 이름이 영어라 팝업이 달라진다.
#: KIGAM 이 같은 판을 `/openapi/wms` 에 열어 주면 여기서 지운다.
COMPOSED = {
    "L_50K_Geology_Map_NoAttitude": {
        "base": "L_50K_Geology_Map",
        "layers": (
            "Geology_map:l_50k_geology_litho_view_latest",
            "Geology_map:l_50k_geology_alterationzone_latest",
            "Geology_map:l_50k_geology_metamorphismzone_latest",
            "Geology_map:l_50k_geology_boundary_latest",
            "Geology_map:l_50k_geology_fold_latest",
            "Geology_map:l_50k_geology_fault_latest",
        ),
    },
}


def _composed_name(params: dict) -> str:
    """이번 요청이 엮은 레이어를 부르면 그 이름. 여럿을 한꺼번에 부르지 않는다."""
    for key in ("layers", "layer"):
        name = str(params.get(key) or "").split(",")[0].strip()
        if name in COMPOSED:
            return name
    return ""


def _as_base(params: dict, name: str) -> dict:
    """엮은 레이어 이름을 그 바탕 묶음으로 바꾼다 — 속성·범례는 묶음에 묻는다."""
    base = COMPOSED[name]["base"]
    out = dict(params)
    for key in ("layers", "query_layers", "layer"):
        if out.get(key):
            out[key] = ",".join(base if part.strip() == name else part
                                for part in str(out[key]).split(","))
    return out


def _endpoint(request: str = ""):
    """이번 요청이 나갈 주소와, 레이어명에 붙일 워크스페이스 접두사.

    문서화된 `/openapi/wms` 는 접두사 없는 이름(`L_250K_Geology_Map`)을 받고,
    GeoServer 로 곧장 갈 때는 워크스페이스가 필요하다
    (`geoOpen:L_250K_Geology_Map`). 갈리는 자리를 여기 하나로 모은다.

    GeoServer 로 가는 것은 둘이다 — 개발 스위치가 켜졌을 때, 그리고
    `/openapi/wms` 가 막아둔 요청(`DIRECT_REQUESTS`)일 때.
    """
    if settings.DEV_DIRECT_WMS or request.lower() in DIRECT_REQUESTS:
        return settings.CAPABILITIES_URL, f"{OPEN_WORKSPACE}:"
    return settings.WMS_URL, ""


def _verify():
    """`requests` 에 넘길 `verify` 값.

    KOPRI 망이 TLS 를 가로채는 탓에 certifi 꾸러미로는 검증이 멈춘다.
    까닭은 `gsmweb.settings._default_ca_bundle()` 에 적었다.
    """
    return settings.CA_BUNDLE or True


class UpstreamError(RuntimeError):
    """상류가 돌려준 것이 지도가 아닐 때."""

    def __init__(self, message, status=None, body=""):
        super().__init__(message)
        self.status = status
        self.body = body


def clean_params(query) -> dict:
    """브라우저가 준 질의 변수를 걸러낸다. 이름은 소문자로 모은다 —
    WMS 는 변수 이름의 대소문자를 가리지 않는다."""
    out = {}
    for raw_key in query:
        low = raw_key.lower()
        if low in ALLOWED:
            out[low] = query[raw_key]
    return out


def _qualify(params: dict, prefix: str) -> dict:
    """레이어명에 워크스페이스 접두사를 붙이거나 뗀다."""
    if not prefix:
        return params
    out = dict(params)
    for key in ("layers", "query_layers", "layer"):
        value = out.get(key)
        if value:
            out[key] = ",".join(
                name if ":" in name else prefix + name
                for name in str(value).split(","))
    return out


def _get(params: dict, *, stream=False):
    request = str(params.get("request", ""))
    composed = _composed_name(params)
    if composed and request.lower() != "getmap":
        params, composed = _as_base(params, composed), ""
    url, prefix = _endpoint(request)
    sent = _qualify(params, prefix)
    if composed:
        # 엮은 레이어의 그림 — 낱레이어는 GeoServer 에만 있다. 이름에 이미
        # 워크스페이스가 붙어 있고, 키는 붙이지 않는다(묻지 않는 곳이다)
        url = settings.CAPABILITIES_URL
        sent = dict(params, layers=",".join(COMPOSED[composed]["layers"]), styles="")
        log.debug("%s 는 낱레이어를 엮어 GeoServer 에서 그린다", composed)
    elif settings.DEV_DIRECT_WMS:
        log.debug("개발 스위치로 GeoServer 에 곧장 간다")
    elif request.lower() in DIRECT_REQUESTS:
        # 키를 붙이지 않는다 — GeoServer 는 묻지 않고, 묻지 않는 곳에
        # 키를 흘릴 까닭이 없다
        log.debug("%s 은 /openapi/wms 가 막아 GeoServer 로 간다", request)
    elif settings.KIGAM_KEY:
        sent = dict(sent, key=settings.KIGAM_KEY)
    else:
        raise UpstreamError("인증키가 없다")
    # 차단 조짐이 이어지면 잠시 묻지 않는다 (usage.py). 캐시가 대신 내준다
    left = usage.paused()
    if left:
        raise UpstreamError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=sent, stream=stream,
                         timeout=settings.UPSTREAM_TIMEOUT,
                         verify=_verify(),
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("kigam", ok=False)
        raise UpstreamError(f"상류에 닿지 못했다: {redact(str(exc))}") from exc
    log.info("상류 %s -> %s", redact(r.url), r.status_code)
    head = b"" if stream else r.content[:1000]
    blocked = usage.looks_blocked(r.status_code, head)
    if blocked:
        log.warning("상류가 차단하는 얼굴을 보였다 (status=%s)", r.status_code)
    usage.record("kigam", ok=r.status_code == 200, blocked=blocked)
    return r


def get_map(params: dict):
    """`GetMap`. (바이트, content-type) 을 돌려준다.

    상류는 잘못된 요청에도 200 에 HTML 을 실어 보내는 일이 있다. 그래서
    상태코드가 아니라 **돌아온 것이 이미지인지**로 성패를 가른다."""
    r = _get(dict(params, service="WMS", request="GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise UpstreamError(
            f"지도가 아닌 것이 왔다 (status={r.status_code}, type={ctype})",
            status=r.status_code, body=r.text[:500])
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo`. GeoJSON FeatureCollection 을 돌려준다.

    **인증키가 있어도 GeoServer 로 간다** (`DIRECT_REQUESTS`). 문서의 요청변수
    표가 `REQUEST=GetMap` 고정이라 적은 대로 `/openapi/wms` 가 이것을 막는다.
    devlog 001·006 을 볼 것.
    """
    r = _get(dict(params, service="WMS", request="GetFeatureInfo",
                  info_format="application/json"))
    if r.status_code != 200:
        raise UpstreamError(f"속성을 읽지 못했다 (status={r.status_code})",
                            status=r.status_code, body=r.text[:500])
    try:
        return r.json()
    except ValueError as exc:
        raise UpstreamError("속성이 JSON 이 아니다", body=r.text[:500]) from exc


def probe_openapi_feature_info(layer: str, bbox: str) -> str:
    """`/openapi/wms` 가 `GetFeatureInfo` 를 열었는지 한 번 찔러본다.

    `DIRECT_REQUESTS` 를 건너뛰고 문서화된 주소로 키를 붙여 보낸다. 제품이
    도는 길에서는 부르지 않는다 — `manage.py verify_layers` 가 대조 끝에
    한 번 부른다. 돌려주는 것은 사람이 읽을 한 줄이고, 열렸으면
    "열렸다" 로 시작한다. 그때 사람이 `DIRECT_REQUESTS` 에서 지운다.
    """
    if not settings.KIGAM_KEY:
        return "인증키가 없어 찔러보지 못했다"
    params = {"service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo",
              "layers": layer, "query_layers": layer, "srs": "EPSG:4326",
              "bbox": bbox, "width": "64", "height": "64", "x": "32", "y": "32",
              "info_format": "application/json", "key": settings.KIGAM_KEY}
    try:
        r = requests.get(settings.WMS_URL, params=params,
                         timeout=settings.UPSTREAM_TIMEOUT, verify=_verify(),
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("kigam", ok=False)
        return f"닿지 못했다: {redact(str(exc))}"
    usage.record("kigam", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    if r.status_code == 200:
        try:
            r.json()
        except ValueError:
            return f"아직 막혀 있다 (200 이지만 JSON 이 아니다, type={r.headers.get('content-type', '')})"
        return "열렸다 — kigam.DIRECT_REQUESTS 에서 getfeatureinfo 를 지워도 된다"
    return f"아직 막혀 있다 (status={r.status_code})"


def get_legend(layer: str):
    """`GetLegendGraphic`. (바이트, content-type) 을 돌려준다.

    문서에 적혀 있지 않지만 상류가 GeoServer 라 된다. 범례를 우리가 그리지
    않고 상류 것을 그대로 거는 까닭은, 지질도의 범례가 암상마다 색과 무늬를
    달리 쓰는 통에 우리가 다시 그리면 원본과 어긋나기 때문이다.
    """
    r = _get({"service": "WMS", "version": "1.0.0",
              "request": "GetLegendGraphic", "format": "image/png",
              "layer": layer})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise UpstreamError(f"범례가 아닌 것이 왔다 (status={r.status_code})",
                            status=r.status_code)
    return r.content, ctype


def fetch_capabilities() -> str:
    """`GetCapabilities` XML 을 통째로 받는다.

    **문서에 없는 주소를 탄다.** 제품이 도는 길에서는 부르지 않는다 —
    `manage.py seed_catalog --from-upstream` 이 사람 손에 불릴 때만 온다.
    CLAUDE.md 의 "두 개의 상류 주소" 를 볼 것.
    """
    url = settings.CAPABILITIES_URL
    log.warning("문서에 없는 주소로 씨앗을 뽑는다: %s", url)
    r = requests.get(url, params={"service": "WMS", "version": "1.3.0",
                                  "request": "GetCapabilities"},
                     timeout=60, verify=_verify(),
                     headers={"User-Agent": "GSM/0.1 (catalog seed)"})
    if r.status_code != 200 or "xml" not in r.headers.get("content-type", ""):
        raise UpstreamError(
            f"카탈로그를 받지 못했다 (status={r.status_code}). "
            "이 주소가 닫혔을 수 있다 — data/kigam_layers.json 의 씨앗을 쓴다.",
            status=r.status_code)
    return r.text
