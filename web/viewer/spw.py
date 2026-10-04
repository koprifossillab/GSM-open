"""왈로니아 공공서비스(SPW)로 나가는 문 — 왈로니아 지질도 개정판 1:2.5만 합본 (wetherilli 237).

- 주소: `geoservices.wallonie.be/arcgis/services/SOL_SOUS_SOL/CARTE_GEOLOGIQUE_SIMPLE/MapServer/WMSServer` (ArcGIS WMS, 원래 31370).
  열쇠가 없다. 왈로니아만 덮는다
- 레이어 — 단위는 축척대마다 둘(`1` 1:118만–1:18.9만, `2` 1:18.9만보다 가까이)이라 한 장에 함께 부른다. 단층은 `7`. **WMS 번호와 REST 번호가
  다르다**(REST 는 14·13·8)
- **1:118만보다 넓으면 그리지 않는다** — 줌 8 은 빈 타일(888 B), 줌 9 부터(0.9 초). 단층은 1:9만 4 천보다 가까이서만 — 줌 13 부터
- 속성은 `application/geo+json`(모양 없이) — 프랑스어. `Sigle`·`Nom de la formation`·`Description générale`·`Système`·`Série`·`Etage`·
  도폭(`Nom de planche`)·`Auteurs`·`Année d'édition`·층 설명 링크(`Description de la notice`). 시대는 `i18n.age_local`(프랑스어)로 옮긴다
- 범례는 두지 않는다 — 395 칸이고 이름이 약호뿐이다. 누르면 층 이름이 뜬다
- 조건: 자료는 **CC BY 4.0**(metawal, "Source : Service public de Wallonie (SPW) - Carte géologique de Wallonie"). 서비스 쪽 조건 PDF
  (LicServicesSPW.pdf)는 읽지 않았다. CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "spw:"
ATTRIBUTION = ('<a href="https://geologie.wallonie.be/" target="_blank" rel="noopener">Service public de Wallonie (SPW)</a> — '
               "Carte géologique de Wallonie (CC BY 4.0)")
MIN_ZOOM = 9
FAULTS_MIN_ZOOM = 13


class SpwError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise SpwError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("spw", ok=False)
        raise SpwError(f"SPW 에 닿지 못했다: {exc}") from exc
    log.info("SPW %s -> %s", r.url, r.status_code)
    usage.record("spw", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _url() -> str:
    return f"{settings.SPW_URL.rstrip('/')}/services/SOL_SOUS_SOL/CARTE_GEOLOGIQUE_SIMPLE/MapServer/WMSServer"


DOOR = arcwms.Door(url=_url, layers={"spw:geology": "1,2", "spw:faults": "7"}, queryable=("spw:geology",), get=_get, error=SpwError,
                   info_format="application/geo+json", info_params={"spw:geology": {"feature_count": "1"}})
knows, get_map, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_feature_info


def get_legend(layer: str):
    raise SpwError("범례를 두지 않는다 — 395 칸이고 이름이 약호뿐이다")


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() == "null" else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 프랑스어 그대로, 시대만 옮긴다 — 가장 잘게 가른 것(절 > 통 > 계)"""
    raw = _value(props, "Etage") or _value(props, "Série") or _value(props, "Système")
    ics = i18n.age_local(raw)
    age = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else raw
    sheet = " ".join(x for x in (_value(props, "Numéro de planche"), _value(props, "Nom de planche")) if x)
    rows = (("기호", _value(props, "Sigle")), ("이름", _value(props, "Nom de la formation")),
            ("설명", _value(props, "Description générale")), ("지질시대", age), ("도폭", sheet),
            ("편집", _value(props, "Auteurs")), ("층 설명", _value(props, "Description de la notice")))
    return {k: v for k, v in rows if v}
