"""네덜란드 응용과학연구소 지질조사부(TNO GDN)로 나가는 문 — 네덜란드 지표 지질도 (wetherilli 237).

- 주소: `www.gdngeoservices.nl/inspire/geoserver/geomap_as_is/ows` (GeoServer WMS, 원래 꼴 — INSPIRE 판 `geomap` 은 속성이 `gml_id` 뿐이다).
  레이어 `GKNederlandGeolVlak`(면). 열쇠가 없다. 판은 `geological_map_v2021`
- 3857 로 나라 전체(줌 8)도 그린다(2.5 초), 위트레흐트 줌 12 1.6 초(2026-10-04)
- 속성은 `application/json` 인데 **그냥 물으면 모양째 7.3 MB** 다 — `propertyName` 으로 열을 골라 456 B 로 받는다.
  열은 `CODE`·`OMSCHRIJVI`(설명)·`LITHOSTRAT`·`OUDERDOM`(네덜란드어 시대 "Holoceen")·`NAAM1`·`VERWIJZING`(층서 명명집 링크)
- 범례는 GeoServer 그림(65 칸)
- 조건: **CC0** — Capabilities 의 AccessConstraints 가 creativecommons.org/publicdomain/zero/1.0. CORS 는 `*`
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "tno:"
#: 메타타일로 받는다 (wetherilli 287) — 512 px 2.2–7.2 초, 1 024 px 3.0 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"tno:": None}
ATTRIBUTION = ('<a href="https://www.tno.nl/nl/over-tno/organisatie/geologische-dienst-nederland/" target="_blank" rel="noopener">'
               "TNO – Geologische Dienst Nederland</a> (CC0)")
FIELDS = "CODE,OMSCHRIJVI,LITHOSTRAT,OUDERDOM,NAAM1,VERWIJZING"


class TnoError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise TnoError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("tno", ok=False)
        raise TnoError(f"TNO 에 닿지 못했다: {exc}") from exc
    log.info("TNO %s -> %s", r.url, r.status_code)
    usage.record("tno", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


DOOR = arcwms.Door(url=lambda: settings.TNO_WMS_URL, layers={"tno:geology": "GKNederlandGeolVlak"}, queryable=("tno:geology",),
                   get=_get, error=TnoError, info_format="application/json",
                   info_params={"tno:geology": {"propertyName": FIELDS, "feature_count": "1"}})
knows, get_map, get_legend, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_legend, DOOR.get_feature_info


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 네덜란드어 그대로, 시대만 옮긴다(못 옮기면 원문)"""
    raw = str(props.get("OUDERDOM") or "").strip()
    ics = i18n.age_local(raw)
    age = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else raw
    rows = (("기호", props.get("CODE")), ("이름", props.get("NAAM1") or props.get("LITHOSTRAT")), ("설명", props.get("OMSCHRIJVI")),
            ("지질시대", age), ("층서 명명집", props.get("VERWIJZING")))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip()}
