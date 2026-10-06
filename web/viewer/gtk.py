"""GTK(핀란드 지질조사소)로 나가는 문 — 핀란드 기반암 지질도 (wetherilli 140).

- 주소: `gtkdata.gtk.fi/arcgis/services/Rajapinnat/GTK_Kalliopera_WMS/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다
- 조건: **GTK 오픈 라이선스**(CC BY 4.0 과 호환, 2025-12-01 부터). 출처를 밝힌다. `ATTRIBUTION`
- **3413 으로 곧장 받는다.** GetCapabilities 는 4326·3067 만 적지만 ArcGIS 가 3413 도 그려 준다(2026-10-02 확인). NPI·EMODnet 과 같다
- 레이어명에 `gtk:` 를 붙여 카탈로그에 둔다. 상류 이름에 핀란드 글자(`ö`)가 든 것이 있다 — 그대로 보낸다
- 속성은 `application/geo+json` 으로 준다. 값이 없는 칸은 `Null`·`not determined` 로 채워 온다 — 뺀다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "gtk:"
ATTRIBUTION = ('<a href="https://www.gtk.fi/en/open-licence/" target="_blank" rel="noopener">© GTK</a>'
               " (GTK Open Licence, CC BY 4.0)")


#: 기반암 말고 다른 서비스의 레이어 → 그 주소의 설정 이름 (wetherilli 270). 지구물리 영상은 누르지 않는다
SERVICES = {
    "gtk:aeromagneettinen_anomaliakartta": "GTK_GEOPHYSICS_URL",
    "gtk:aeroradiometrinen_yhdistelmakartta": "GTK_GEOPHYSICS_URL",
    "gtk:fennoscandia_mineral_deposit": "GTK_KOKOAVA_URL",
}
NOT_QUERYABLE = ("gtk:aeromagneettinen_anomaliakartta", "gtk:aeroradiometrinen_yhdistelmakartta")


class GtkError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _url(names) -> str:
    first = str(names or "").split(",")[0].strip()
    first = first if first.startswith(PREFIX) else PREFIX + first
    return getattr(settings, SERVICES[first]) if first in SERVICES else settings.GTK_WMS_URL


def _get(params: dict, url: str = ""):
    left = usage.paused()
    if left:
        raise GtkError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url or settings.GTK_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gtk", ok=False)
        raise GtkError(f"GTK 에 닿지 못했다: {exc}") from exc
    log.info("GTK %s -> %s", r.url, r.status_code)
    usage.record("gtk", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
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
    r = _get(_wms(params, "GetMap"), _url(params.get("layers")))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GtkError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)}, _url(layer))
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GtkError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    url = _url(params.get("query_layers") or params.get("layers"))
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params, url)
    if r.status_code != 200:
        raise GtkError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise GtkError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로.** 끝에 `_` 가 붙은 열이 글로 풀린 값이다(번호 열과 짝)
FRIENDLY = (
    ("ROCK_NAME_", "암석"),
    ("ROCK_CLASS_", "암석 갈래"),
    ("ORIGINAL_NAME", "원 이름"),
    ("FORMATION_", "층"),
    ("GROUP__", "층군"),
    ("SUITE_", "암석군"),
    ("SUPERSUITE_", "초암석군"),
    ("LITHODEME_", "암체"),
    ("EPOCH_", "지질시대"),
    ("ERA_", "지질시대"),
    ("PROVINCE_", "지구조 구역"),
    ("TECTONIC_SETTING_", "지구조 환경"),
    ("ENVIRONMENT_", "생성 환경"),
)
_EMPTY = {"null", "not determined", "undefined", "-1"}
#: 지질시대로 옮겨 보는 열 — 앞의 것이 있으면 뒤의 것은 쓰지 않는다
_AGES = ("EPOCH_", "ERA_")


#: 북유럽 광상 FODD 의 열 (wetherilli 270) — 노르웨이·스웨덴·핀란드·러시아 북서부를 한 표로 묶은 것
FODD_FRIENDLY = (
    ("NAME", "이름"),
    ("COUNTRY", "나라"),
    ("MAIN_COMMODITIES", "광종"),
    ("OTHER_COMMODITES", "딸린 광종"),
    ("STATUS", "광산"),
    ("WHEN_MINED", "채굴 기간"),
    ("SIZE_CATEGORY", "광상 규모"),
    ("TOTAL_TONNAGE_MT", "총 광량 (Mt)"),
    ("GENETIC_TYPE", "성인"),
    ("HOST_ROCKS", "모암"),
    ("ORE_MINERALS", "광석 광물"),
    ("AGE_OF_MINERALISATION", "광화 시기"),
    ("METALLOGENIC_AREA", "광화 지역"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    if "MAIN_COMMODITIES" in props:
        out = {}
        for key, label in FODD_FRIENDLY:
            value = str(props.get(key) or "").strip()
            if value and value.lower() not in _EMPTY:
                out[label] = value
        return out
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or value.lower() in _EMPTY or label in out:
            continue
        if key in _AGES and lang == "ko":
            value = i18n.age_ko(value)            # `Statherian 1 (1800-1770 Ma)` 처럼 숫자가 섞이면 원문이다
        out[label] = value
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "gtk", "tag": "GTK", "title": "핀란드 지질조사소", "relay": True, "projected": True, "globe": True},
]
