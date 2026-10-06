"""인도 지질조사소(GSI)의 1:200만 인도 지질도로 나가는 문 (wetherilli 226). 그림과 속성을 두 곳에서 받는다.

- **그림은 BGS 가 OneGeology 로 여는 WMS** — `ogc.bgs.ac.uk/cgi-bin/BGS_GSI_Geology/wms`(MapServer). `IND_GSI_2M_Geology`·`_Faults`·
  `_Thrusts`. 3857 로 그린다. 조건은 Capabilities 의 "Free viewing"(AccessConstraints 없음). CORS 는 `*`
- **속성은 GSI 가 ArcGIS Online 에 올린 피처 서비스** — `services7.arcgis.com/…/Geology_2M_WFL1/FeatureServer/7`(소유 `gisadmin.gsi`, 공개 항목).
  BGS 의 WMS 는 GetFeatureInfo 에 `Feature 3712:` 만 주고 열이 비어서다. 누른 화소를 3857 점으로 바꿔 `query` 에 묻는다(모양 없이)
- **GSI 의 지도 창(Bhukosh)·NGDR 는 나라 밖에서 닿지 않는다**(2026-10-04 — 시간 초과·연결 거부, NGDR 는 로그인). 그래서 두 길을 엮었다
- 범례는 두지 않는다 — BGS 의 범례 그림은 칸 이름이 1–98 번호뿐이다. 피처 서비스의 칠하기 규칙(523 칸)은 BGS 그림의 색과 같은지
  확인하지 못했다. 누르면 단위가 뜬다
- 조건: 피처 서비스 항목의 licenseInfo 가 비어 있다. GSI 의 이용 조건은 Bhukosh 가 열리지 않아 읽지 못했다 — **밖에 열기 전에 사람이 읽는다**
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "gsiindia:"
ATTRIBUTION = ('<a href="https://www.gsi.gov.in/" target="_blank" rel="noopener">Geological Survey of India</a> 1:2M — '
               'WMS by <a href="https://www.bgs.ac.uk/" target="_blank" rel="noopener">BGS</a> (OneGeology)')
#: 우리 이름 → BGS WMS 레이어
LAYERS = {
    "gsiindia:geology": "IND_GSI_2M_Geology",
    "gsiindia:faults": "IND_GSI_2M_Faults",
    "gsiindia:thrusts": "IND_GSI_2M_Thrusts",
}
QUERYABLE = ("gsiindia:geology",)
#: 피처 서비스에서 받을 열
FIELDS = "INDEX_,AGE,SUPERGROUP,GROUP_"


class GsiIndiaError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return bool(name) and all(n.strip() in LAYERS for n in str(name).split(","))


def _names(names: str) -> str:
    if not knows(names):
        raise GsiIndiaError(f"모르는 레이어다: {names}")
    return ",".join(LAYERS[n.strip()] for n in names.split(","))


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GsiIndiaError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsiindia", ok=False)
        raise GsiIndiaError(f"인도 지질도에 닿지 못했다: {exc}") from exc
    log.info("GSI 인도 %s -> %s", r.url, r.status_code)
    usage.record("gsiindia", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def get_map(params: dict):
    params = dict(params, service="WMS", request="GetMap", version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _names(params.get("layers"))
    r = _get(settings.GSIINDIA_WMS_URL, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsiIndiaError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise GsiIndiaError("범례를 두지 않는다 — BGS 의 범례 그림은 칸 이름이 번호뿐이다")


def point_of(params: dict) -> tuple:
    """WMS 의 GetFeatureInfo 변수(범위·크기·누른 화소) → 그 화소 가운데의 투영 좌표. 1.3.0(`i`·`j`)과 1.1.1(`x`·`y`) 둘 다"""
    try:
        west, south, east, north = (float(v) for v in str(params["bbox"]).split(","))
        width, height = float(params["width"]), float(params["height"])
        col = float(params.get("i", params.get("x")))
        row = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError) as exc:
        raise GsiIndiaError("누른 자리를 읽지 못했다") from exc
    return west + (col + 0.5) * (east - west) / width, north - (row + 0.5) * (north - south) / height


def get_feature_info(params: dict) -> dict:
    name = str(params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
    if name not in QUERYABLE:
        raise GsiIndiaError(f"누를 수 없는 레이어다: {name}")
    crs = str(params.get("crs") or params.get("srs") or "EPSG:3857")
    x, y = point_of(params)
    r = _get(f"{settings.GSIINDIA_FEATURE_URL.rstrip('/')}/7/query", {
        "geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "inSR": crs.split(":")[-1],
        "spatialRel": "esriSpatialRelIntersects", "outFields": FIELDS, "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise GsiIndiaError("속성이 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise GsiIndiaError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": [{"id": f"GEOLOGY_2M.{i}", "properties": f.get("attributes") or {}}
                         for i, f in enumerate(data.get("features") or [])]}


#: 상류 값의 오탈자 — 2026-10-04 에 시대 값 71 가지를 모아 보니 하나였다
_TYPOS = {"NEOPROTEOZOIC": "NEOPROTEROZOIC"}
#: 시대가 아닌 값 — 지질도가 그리지 않은 자리
_NOT_AGES = ("UNMAPPED", "UNMAPPED AREA")


def age(value: str, lang: str = "ko") -> str:
    """`LATE CRETACEOUS - PALAEOCENE`·`MESOPROTEROZOIC TO NEOPROTEROZOIC` → 한국어(못 옮기면 영어로 다듬은 원문)"""
    raw = str(value or "").strip()
    if raw.upper() in _NOT_AGES:
        return ""
    for wrong, right in _TYPOS.items():
        raw = raw.replace(wrong, right)
    text = " – ".join(p.strip() for p in raw.replace(" TO ", " - ").split(" - ") if p.strip())
    if not text:
        return ""
    if lang == "ko":
        ko = i18n.age_ko(text)
        if ko != text:
            return ko
    return text.title().replace("Palaeo", "Paleo").replace("Archaean", "Archean")


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "none", "-") else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 단위·층군 이름은 영어(대문자) 그대로, 시대만 옮긴다"""
    rows = (("이름", _value(props, "INDEX_")), ("층군", _value(props, "GROUP_")), ("초층군", _value(props, "SUPERGROUP")),
            ("지질시대", age(_value(props, "AGE"), lang)))
    return {k: v for k, v in rows if v}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "gsiindia", "tag": "GSI-IN", "title": "인도 지질조사소 (그림: BGS)", "relay": True, "projected": True, "globe": True},
]
