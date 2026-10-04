"""필리핀 광산지질국(MGB)으로 나가는 문 — 필리핀 지역 지질도(Regional Geology, 공개 폴더) (wetherilli 228).

- 주소: `controlmap.mgb.gov.ph/arcgis/services/GeospatialDataInventory_Public/GDI_Regional_Geology_Public/MapServer/WMSServer`
  (ArcGIS WMS). 열쇠가 없다. 같은 서버의 `GGS_GeologicUnit`·`WMS` 폴더는 `499 Token Required` — 공개 폴더만 부른다
- 원본이 3857 이다(256² 0.3 초 — 빠르다). 축척은 적혀 있지 않다(면 하나가 2 600 km² — 1:100만급)
- 속성은 **ESRI XML 만** 준다 — `TagKey`·`Age`·`GeneralLithology`·`Lithology`·`Lithologydescription`(영어)
- 범례는 WMS 의 그림(27 칸, 영어 이름) 그대로
- 조건: copyright 비어 있음 — **밖에 열기 전에 사람이 읽는다**. CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "mgb:"
ATTRIBUTION = ('<a href="https://mgb.gov.ph/" target="_blank" rel="noopener">Mines and Geosciences Bureau</a> — '
               "Regional Geology of the Philippines")
LAYERS = {"mgb:geology": "0"}


class MgbError(RuntimeError):
    pass


def _url() -> str:
    return (f"{settings.MGB_URL.rstrip('/')}/services/GeospatialDataInventory_Public/GDI_Regional_Geology_Public/"
            "MapServer/WMSServer")


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise MgbError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("mgb", ok=False)
        raise MgbError(f"MGB 에 닿지 못했다: {exc}") from exc
    log.info("MGB %s -> %s", r.url, r.status_code)
    usage.record("mgb", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


DOOR = arcwms.Door(url=_url, layers=LAYERS, queryable=("mgb:geology",), info_format="text/xml", get=_get, error=MgbError)
knows, get_map, get_legend, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_legend, DOOR.get_feature_info


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(영어)은 그대로, 시대만 옮긴다"""
    age = i18n.age_tidy(props.get("Age", ""))
    rows = (("기호", props.get("TagKey", "")), ("암석 갈래", props.get("GeneralLithology", "")),
            ("암석", props.get("Lithology", "")), ("설명", props.get("Lithologydescription", "")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip()}
