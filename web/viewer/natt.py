"""아이슬란드 자연사연구소(Náttúrufræðistofnun, NÍ)로 나가는 문 — 아이슬란드 지질도 1:60만·1:10만 (wetherilli 216).

- 주소: `gis.natt.is/geoserver/wms` (GeoServer WMS). 열쇠가 없다. 여러 기관이 함께 쓰는 서버라 레이어가 500 남짓이다 —
  `LAYERS` 에 적은 지질 레이어만 부른다. 레이어명은 상류 이름(`ni:ni_j600v_…`) 그대로다 — 워크스페이스 `ni:` 가 이미 붙어 있다
- 조건: **CC BY 4.0** (natt.is "use of data", 법 45/2018). 출처를 밝힌다. `ATTRIBUTION`
- **3413 으로 곧장 받는다.** Capabilities 는 3057·4326·3857 따위만 적지만 GeoServer 가 다시 투영해 그린다(2026-10-04, 남부 500 km 2.2 초).
  NPI·GTK 와 같은 길이다
- 속성은 `application/json`(GeoJSON). 1:60만은 값이 부호뿐이라(`jardmLandmBerg=hra`, `magnKisiloxids=basisur`,
  `jardsogulegurAldur=H_iss`) 상류 범례(`GetLegendGraphic` JSON)의 칸 이름으로 푼다 — `UNITS`. 1:10만은 영어 열(`myndunEN`)이 있다
- 범례는 GeoServer 의 그림 그대로다(칸 이름이 아이슬란드어 – 영어 두 벌)
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('<a href="https://www.natt.is/" target="_blank" rel="noopener">© Náttúrufræðistofnun</a>'
               " (CC BY 4.0)")

#: 부르는 레이어 → 누를 수 있는가. 선·점 레이어는 속성이 부호뿐이라 누르지 않는다
LAYERS = {
    # 1:60만 기반암 2 판(Haukur Jóhannesson 2014)
    "ni:ni_j600v_berg_2_jardlog_2utg_fl": True,
    "ni:ni_j600v_berg_2_jardlogMork_2utg_li": False,
    "ni:ni_j600v_berg_2_brotalina_1utg_li": False,
    "ni:ni_j600v_berg_2_gosspr_1utg_li": False,
    "ni:ni_j600v_berg_2_gigar_1utg_p": False,
    # 1:60만 구조도 — 화산계
    "ni:ni_j600v_hoggun_eldstodvakerfi_li": False,
    # 1:10만 — 서부 화산대·동부만 나왔다
    "ni:ni_j100v_vesturgosbelti_berggrunnur_1utg_fl": True,
    "ni:ni_j100v_vesturgosbelti_jardgrunnur_1utg_fl": True,
    "ni:ni_j100v_austurland_berggrunnur_1utg_fl": True,
}

#: 1:60만 기반암의 칸 — (jardmLandmBerg, magnKisiloxids, jardsogulegurAldur) → 상류 범례의 영어 이름.
#: 2026-10-04 에 `GetLegendGraphic&format=application/json` 으로 받은 규칙 그대로다. `None` 은 그 열을 보지 않는 칸
UNITS = (
    ((None, None, "H"), "Holocene sediments"),
    (("hra", "basisur", "H_iss"), "Historic basic and intermediate lavas, younger than 871 AD"),
    (("hra", "basisur", "H_isfs"), "Prehistoric basic and intermediate lavas, older than 871 AD"),
    (("hra", "sur", "H_iss"), "Historic acid lavas, younger than 871 AD"),
    (("hra", "sur", "H_isfs"), "Prehistoric acid lavas, older than 871 AD"),
    (("hra_mob", "sur", "KT"), "Acid extrusives, older than 11 000 years"),
    (("mob", "basisur", "K_isgy"), "Hyaloclastite, pillow lava and associated sediments, younger than 0.8 m.y."),
    (("hra", "basisur", "K_isgy"), "Lavas with intercalated sediments, younger than 0.8 m.y."),
    (("hra_mob", "basisur", "K_isge"), "Extrusive rocks with intercalated sediments, 0.8–3.3 m.y."),
    (("hra_mob", "basisur", "T_sib"), "Extrusive rocks with intercalated sediments, older than 3.3 m.y."),
    (("inn03", "basisur", None), "Basic and intermediate intrusions"),
    (("inn03", "sur", None), "Acid intrusions"),
)

#: 연대 부호 → ICS 이름(영어 — 한국어는 `i18n.age_ko`). 범례가 적은 나이로 골랐다: 0.8 Ma 는 플라이스토세 중기의 바닥,
#: 3.3 Ma 는 플라이오세 후기, 아이슬란드의 가장 오랜 바위는 마이오세다
AGES = {
    "H": "Holocene", "H_iss": "Holocene", "H_isfs": "Holocene",
    "K_isgy": "Middle – Late Pleistocene",
    "K_isge": "Late Pliocene – Early Pleistocene",
    "T_sib": "Miocene – Pliocene",
    "KT": "Miocene – Pleistocene",
    "Kp_wei": "Late Pleistocene",
}
#: 표에 없는 부호는 앞 글자로 — H 홀로세, K 플라이스토세, T 제3기(신진기)
_AGE_PREFIX = (("H", "Holocene"), ("K", "Pleistocene"), ("T", "Neogene"))


class NattError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return all(n.strip() in LAYERS for n in str(name or "").split(",")) and bool(name)


def queryable(name: str) -> bool:
    return LAYERS.get(name, False)


def _check(names: str) -> str:
    if not knows(names):
        raise NattError(f"모르는 레이어다: {names}")
    return ",".join(n.strip() for n in names.split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise NattError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.NATT_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("natt", ok=False)
        raise NattError(f"NÍ 에 닿지 못했다: {exc}") from exc
    log.info("NÍ %s -> %s", r.url, r.status_code)
    usage.record("natt", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = _check(params[key])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NattError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": _check(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise NattError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise NattError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise NattError("속성이 JSON 이 아니다") from exc


def _value(props: dict, key: str) -> str:
    value = props.get(key)
    return "" if value is None else str(value).strip()


def unit_name(props: dict) -> str:
    """1:60만 기반암의 부호 셋 → 상류 범례의 영어 이름. 맞는 칸이 없으면 빈 글"""
    got = (_value(props, "jardmLandmBerg"), _value(props, "magnKisiloxids"), _value(props, "jardsogulegurAldur"))
    for want, name in UNITS:
        if all(w is None or w == g for w, g in zip(want, got)):
            return name
    return ""


def age_name(code: str) -> str:
    """연대 부호 → ICS 이름(영어). 모르는 부호는 빈 글"""
    code = str(code or "").strip()
    if code in AGES:
        return AGES[code]
    for prefix, name in _AGE_PREFIX:
        if code.startswith(prefix):
            return name
    return ""


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 1:10만은 영어 열을, 1:60만은 범례의 영어 이름을 쓴다 — 값(지층명·암석명)은 옮기지 않는다.
    지질시대만 부호를 ICS 이름으로 풀어 옮긴다"""
    out = {}
    name = _value(props, "nafnfitju")
    if name:
        out["이름"] = name
    rock = _value(props, "myndunEN") or _value(props, "myndunIS") or unit_name(props)
    if rock:
        out["암석"] = rock
    age = age_name(_value(props, "jardsogulegurAldur"))
    if age:
        out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
    elif _value(props, "alduris"):
        out["지질시대"] = _value(props, "alduris")
    if _value(props, "aldur"):
        out["연대"] = _value(props, "aldur")
    if _value(props, "segultimatal"):
        out["고지자기"] = _value(props, "segultimatal")
    if _value(props, "heimild"):
        out["출처"] = _value(props, "heimild")
    return out
