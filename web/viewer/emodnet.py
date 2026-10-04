"""EMODnet Geology 로 나가는 문 — 유럽 바다의 해저 퇴적물·해저 지질 (wetherilli 135).

- 주소: `drive.emodnet-geology.eu/geoserver/ows` (GeoServer). 열쇠가 없고 CORS 가 열려 있지만 늘 `/GSM/wms/` 를
  거친다 — 캐시에 담고, 속성의 열을 추린다
- 조건: EMODnet 이 만든 자료는 EU 소유, **CC BY 4.0** 이다. 출처 문구는 `ATTRIBUTION`
- **지역의 투영(3413)으로 곧장 받는다.** GetCapabilities 는 3413 을 적지 않지만 GeoServer 가 그려 준다(2026-10-02).
  NPI 처럼 3857 로 물으면 북위 78° 에서 축척이 다섯 배 부풀어, 축척 따라 판을 고르는 퇴적물(multiscale)이 거친 판을 낸다
- 레이어명에 `emodnet:` 를 붙여 카탈로그에 둔다 — 상류 이름(`bgr:pre_quaternary_faults` 처럼 제 접두사가 있다)과
  다른 상류의 이름이 부딪히지 않게. 상류로 나갈 때 떼어 낸다
- 속성은 `application/json` 으로 준다. 열이 마흔 남짓이라 `FRIENDLY` 에 적은 것만 보인다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "emodnet:"
ATTRIBUTION = ('<a href="https://emodnet.ec.europa.eu/en/geology" target="_blank" rel="noopener">EMODnet Geology</a>'
               " (CC BY 4.0)")


class EmodnetError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    """카탈로그의 이름(여럿이면 쉼표) → 상류의 이름."""
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise EmodnetError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.EMODNET_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("emodnet", ok=False)
        raise EmodnetError(f"EMODnet 에 닿지 못했다: {exc}") from exc
    log.info("EMODnet %s -> %s", r.url, r.status_code)
    usage.record("emodnet", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    """브라우저가 보낸 것을 1.1.1 로 옮겨 적는다 — 1.3.0 의 4326 축 차례를 피하려고."""
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 EmodnetError."""
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise EmodnetError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise EmodnetError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise EmodnetError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise EmodnetError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로** 보인다 — 나머지는 내부 번호·담당자 메일·면적이다
FRIENDLY = (
    # 해저 퇴적물 (Folk)
    ("folk_7cl_txt", "해저 퇴적물 (Folk 7)"),
    ("folk_16cl_txt", "해저 퇴적물 (Folk 16)"),
    ("original_substrate", "원 분류"),
    # 제4기 이전 지질 — 제4기 퇴적층(wetherilli 176)은 암상 열 이름이 다르다
    ("label_litho", "암상"),
    ("label_lithology", "암상"),
    ("label_age", "지질시대"),
    # 단층
    ("fault_type", "단층 종류"),
    ("fault_name", "단층 이름"),
    ("original_legend_text", "원 범례"),
    ("origvalue_legtext", "원 범례"),
    # 지질 사건 분포 — 칸마다 사건 다섯의 보고 여부 (wetherilli 176)
    ("landslide", "해저 사태"),
    ("volcanic_c", "해저 화산"),
    ("tectonics", "제4기 구조운동"),
    ("tsunami", "지진해일"),
    ("fluid_em", "해저 유체 분출"),
    ("country", "나라"),
    ("nation", "나라"),
    ("scale", "축척"),
    ("name", "자료"),
    ("data_holder", "자료 보유 기관"),
    ("reference", "참고 문헌"),
)
_EMPTY = {"n/a", "-", "none"}


def friendly(props: dict, lang: str = "ko") -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = props.get(key)
        if value in (None, "") or str(value).strip().lower() in _EMPTY:
            continue
        if key == "label_age" and lang == "ko":
            value = i18n.age_ko(value)
        elif key == "reference":
            value = str(value).removeprefix("Reference: ")
        elif key == "scale":
            value = f"1:{int(float(value)):,}" if str(value).replace(".", "", 1).isdigit() else value
        out[label] = value
    return out
