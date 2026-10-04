"""플랑드르 지하 자료은행(DOV, Databank Ondergrond Vlaanderen)으로 나가는 문 — 플랑드르 제3기 지질도 1:5만·제4기 1:20만 (wetherilli 237).

- 주소: `www.dov.vlaanderen.be/geoserver/wms` (GeoServer WMS — 루트 Capabilities 는 레이어 5 600 남짓·21.8 MB 라 받지 않는다).
  레이어 `neo_paleo:tertiair_50k`(제3기 1:5만)·`quartair:quartair_200k`(제4기 단면형 1:20만). 열쇠가 없다
- 3857 로 나라 줌(8)도 그린다 — 둘을 겹쳐 1.6 초, 뢰번 줌 12 0.9 초(2026-10-04)
- 속성은 `application/json` 인데 모양째 193 KB 라 `propertyName` 으로 열을 골라 받는다(371 B). **시대 열이 없다** — 층(Formatie) 이름뿐이다
- 범례는 GeoServer 그림(제3기 78 칸)
- 조건: **무료 재사용 표준 라이선스**(Modellicentie voor gratis hergebruik — 상업·비상업 모두, 출처 표시만). 출처는 "Databank Ondergrond
  Vlaanderen". CORS 는 `*`
"""
import logging

import requests
from django.conf import settings

from . import arcwms, usage

log = logging.getLogger(__name__)

PREFIX = "dov:"
ATTRIBUTION = ('<a href="https://www.dov.vlaanderen.be/" target="_blank" rel="noopener">Databank Ondergrond Vlaanderen</a> '
               "(Modellicentie gratis hergebruik)")
LAYERS = {"dov:tertiair_50k": "neo_paleo:tertiair_50k", "dov:quartair_200k": "quartair:quartair_200k"}


class DovError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise DovError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("dov", ok=False)
        raise DovError(f"DOV 에 닿지 못했다: {exc}") from exc
    log.info("DOV %s -> %s", r.url, r.status_code)
    usage.record("dov", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


DOOR = arcwms.Door(url=lambda: settings.DOV_WMS_URL, layers=LAYERS, queryable=tuple(LAYERS), get=_get, error=DovError,
                   info_format="application/json",
                   info_params={"dov:tertiair_50k": {"propertyName": "code,formatie,lid,beschrijving", "feature_count": "1"},
                                "dov:quartair_200k": {"propertyName": "profiel,type", "feature_count": "1"}})
knows, get_map, get_legend, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_legend, DOOR.get_feature_info


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 네덜란드어 그대로 — 시대 열이 없다"""
    rows = (("기호", props.get("code")), ("이름", props.get("formatie")), ("부층", props.get("lid")),
            ("설명", props.get("beschrijving")), ("단면", props.get("profiel")))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip() and str(v).strip().lower() != "null"}
