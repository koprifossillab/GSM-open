"""GeoSphere Austria(옛 오스트리아 지질조사소 GBA)로 나가는 문 — 오스트리아 지질도 1:100만과 단층 (wetherilli 237).

- 주소: `gis.geosphere.at/maps/services/geologie/geologie_1m/MapServer/WMSServer`(지질), `…/geologie/tektonische_linien_1m/…`(단층·지붕구조
  경계). ArcGIS WMS, 열쇠가 없다. 3857 이 Capabilities 에 있다(할슈타트 둘레 256² 1.4 초, 2026-10-04)
- 지질은 레이어 둘을 한 장에 — `0` 제4기 퇴적층·중기 에오세 뒤 분지를 뺀 바탕, `1` 그 분지들. 단층은 `0`(단층·전단대)과 `6`(1 차 지붕구조 경계)
- **1:14만 1 741 보다 크게는 그리지 않는다**(MinScaleDenominator) — 줌 11 까지 받고 그 위는 화면이 늘린다
- 속성은 `application/geo+json`(모양 없이) — `Beschreibung` 한 열에 "암상; 시대" 가 붙어 온다(`Kalkstein, Dolomit …; Perm - frühe Kreide`).
  `;` 로 떼어 시대는 `i18n.age_local`(독일어)로 옮긴다. `Tektonik` 은 지붕구조 단위
- 범례는 WMS 그림(레이어 `0`, 독일어)
- 조건: **CC BY 4.0**, "(c) GeoSphere Austria" — 1:5만 INSPIRE 메타데이터에 적혀 있다. 1:100만 서비스의 메타데이터는 따로 읽지 않았다.
  CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "geosphere:"
ATTRIBUTION = ('<a href="https://www.geosphere.at/" target="_blank" rel="noopener">(c) GeoSphere Austria</a> (CC BY 4.0)')
#: 그 위로는 상류가 그리지 않는 줌
MAX_ZOOM = 11


class GeosphereError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GeosphereError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("geosphere", ok=False)
        raise GeosphereError(f"GeoSphere Austria 에 닿지 못했다: {exc}") from exc
    log.info("GeoSphere %s -> %s", r.url, r.status_code)
    usage.record("geosphere", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _url(service: str):
    return lambda: f"{settings.GEOSPHERE_URL.rstrip('/')}/services/geologie/{service}/MapServer/WMSServer"


GEOLOGY = arcwms.Door(url=_url("geologie_1m"), layers={"geosphere:geology": "0,1"}, queryable=("geosphere:geology",),
                      get=_get, error=GeosphereError, info_format="application/geo+json")
FAULTS = arcwms.Door(url=_url("tektonische_linien_1m"), layers={"geosphere:faults": "0,6"}, get=_get, error=GeosphereError)
DOORS = (GEOLOGY, FAULTS)


def _door(name: str) -> arcwms.Door:
    first = str(name or "").split(",")[0].strip()
    for door in DOORS:
        if door.knows(first):
            return door
    raise GeosphereError(f"모르는 레이어다: {name}")


def knows(name: str) -> bool:
    return any(d.knows(name) for d in DOORS)


def get_map(params: dict):
    return _door(params.get("layers")).get_map(params)


def get_feature_info(params: dict) -> dict:
    return _door(params.get("query_layers") or params.get("layers")).get_feature_info(params)


def get_legend(layer: str):
    door = _door(layer)
    r = _get(door.url(), {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                          "layer": door.layers[layer].split(",")[0]})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GeosphereError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def friendly(props: dict, lang: str = "ko") -> dict:
    """`Beschreibung` 의 "암상; 시대" 를 떼어 — 암상은 독일어 그대로, 시대는 옮긴다(못 옮기면 원문)"""
    text = str(props.get("Beschreibung") or "").strip()
    rock, _, age = text.rpartition(";") if ";" in text else (text, "", "")
    ics = i18n.age_local(age)
    age = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else age.strip()
    rows = (("암석", rock.strip()), ("지질시대", age), ("지구조 구역", str(props.get("Tektonik") or "").strip()))
    return {k: v for k, v in rows if v}
