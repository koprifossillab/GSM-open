"""폴란드 지질연구소(PIG-PIB)로 나가는 문 — 폴란드 지질도 1:50만 2022 판 (wetherilli 237).

- 주소: `cbdgmapa.pgi.gov.pl/arcgis/services/kartografia/mgp500k_2022/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다. 3857 이 Capabilities 에
  있다(크라쿠프 둘레 256² 1.6 초, 2026-10-04)
- **세 층을 겹쳐 그린다** — `1` 신생대 밑 기반, `6` 고·신제3기, `11` 제4기. 밑에서부터 이 차례로 부른다. **WMS 번호가 REST 와 거꾸로다**
  (REST 번호로 부르면 도폭 범위 선만 온다). 단층은 `3`(기반)·`9`(제3기)
- **1:9만 4 494 보다 크게는 단위를 그리지 않는다** — 줌 12 까지 받고 그 위는 화면이 늘린다. 단층은 1:70만보다 넓으면 비어 줌 10 부터
- 속성은 `application/geo+json` — 폴란드어(`Opis wydzielenia`·`Litologia`·`Stratygrafia` "jura górna"·`Geneza`). 층마다 하나씩 온다.
  시대는 `i18n.age_local`(폴란드어, 절 이름 포함)로 옮긴다
- 범례는 WMS 그림(제4기 층)
- 조건: 메타데이터(metadane.pgi.gov.pl)가 "Brak ograniczeń w publicznym dostępie"·"Brak warunków dostępu i użytkowania"(접근·이용 조건 없음)라
  적는다. 출처는 "PIG-PIB". CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "pig:"
ATTRIBUTION = ('<a href="https://www.pgi.gov.pl/" target="_blank" rel="noopener">PIG-PIB</a> — Mapa geologiczna Polski 1:500 000 (2022)')
MAX_ZOOM = 12
FAULTS_MIN_ZOOM = 10


class PigError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise PigError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("pig", ok=False)
        raise PigError(f"PIG-PIB 에 닿지 못했다: {exc}") from exc
    log.info("PIG %s -> %s", r.url, r.status_code)
    usage.record("pig", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _url() -> str:
    return f"{settings.PIG_URL.rstrip('/')}/services/kartografia/mgp500k_2022/MapServer/WMSServer"


DOOR = arcwms.Door(url=_url, layers={"pig:mgp500k": "1,6,11", "pig:faults": "3,9"}, queryable=("pig:mgp500k",),
                   get=_get, error=PigError, info_format="application/geo+json")
knows, get_map, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_feature_info


def get_legend(layer: str):
    r = _get(_url(), {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                      "layer": DOOR.layers[layer].split(",")[-1]})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise PigError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() == "null" else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 폴란드어 그대로, 시대만 옮긴다(못 옮기면 원문)"""
    raw = _value(props, "Stratygrafia")
    ics = i18n.age_local(raw)
    age = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else raw
    rows = (("기호", _value(props, "Symbol wydzielenia")), ("설명", _value(props, "Opis wydzielenia")),
            ("암석", _value(props, "Litologia")), ("지질시대", age), ("성인", _value(props, "Geneza")),
            ("빙하 층서", _value(props, "Klimatostratygrafia")))
    return {k: v for k, v in rows if v}
