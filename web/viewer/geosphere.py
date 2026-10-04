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
- **1:5만**(`geologie/einheiten_50`, wetherilli 239) — 도폭별 1:5만 지질도를 GeoSciML-Lite 로 이은 것. **WMS 가 꺼져 있어**(WFS 뿐) REST
  `export`·`identify` 로 옮긴다(말레이시아 `jmg.py` 와 같다). 줌 13 한 장 1.8 초, 줌 9 는 3.3 초라 **줌 11 부터**만 그린다. 도폭이 나온 곳만
  덮는다. 속성은 영어 열 이름에 독일어 값 — `geologicUnitName`·`description`·`lithology`·`representativeAge`("Obertrias")·
  `tectonicUnitName`·`collectionName`(도폭). 범례는 두지 않는다(도폭마다 수백 칸)
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
#: 1:5만은 이 줌부터
UNITS50_MIN_ZOOM = 11
UNITS50 = "geosphere:units50k"


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
    usage.record("geosphere", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _url(service: str):
    return lambda: f"{settings.GEOSPHERE_URL.rstrip('/')}/services/geologie/{service}/MapServer/WMSServer"


GEOLOGY = arcwms.Door(url=_url("geologie_1m"), layers={"geosphere:geology": "0,1"}, queryable=("geosphere:geology",),
                      get=_get, error=GeosphereError, info_format="application/geo+json")
FAULTS = arcwms.Door(url=_url("tektonische_linien_1m"), layers={"geosphere:faults": "0,6"}, get=_get, error=GeosphereError)
DOORS = (GEOLOGY, FAULTS)


def _rest(path: str) -> str:
    return f"{settings.GEOSPHERE_URL.rstrip('/')}/rest/services/geologie/einheiten_50/MapServer/{path}"


def _view(params: dict):
    """WMS 변수 → (3857 범위 네 수, 너비, 높이). 1:5만은 REST 로 옮긴다"""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in ("EPSG:3857", "EPSG:900913"):
        raise GeosphereError(f"3857 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise GeosphereError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise GeosphereError("범위·크기가 맞지 않다")
    return bbox, width, height


def _units50_map(params: dict):
    bbox, width, height = _view(params)
    r = _get(_rest("export"), {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": "3857", "imageSR": "3857",
                               "size": f"{width},{height}", "format": "png32", "transparent": "true", "dpi": "96",
                               "layers": "show:0", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GeosphereError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def _units50_info(params: dict) -> dict:
    bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise GeosphereError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get(_rest("identify"), {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": "3857",
                                 "layers": "all:0", "tolerance": "1", "mapExtent": ",".join(repr(v) for v in bbox),
                                 "imageDisplay": f"{width},{height},96", "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise GeosphereError("속성이 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise GeosphereError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": [{"id": f"einheiten_50.{n}", "properties": x_.get("attributes") or {}}
                         for n, x_ in enumerate(data.get("results") or [])][:1]}


def _door(name: str) -> arcwms.Door:
    first = str(name or "").split(",")[0].strip()
    for door in DOORS:
        if door.knows(first):
            return door
    raise GeosphereError(f"모르는 레이어다: {name}")


def knows(name: str) -> bool:
    return name == UNITS50 or any(d.knows(name) for d in DOORS)


def get_map(params: dict):
    if str(params.get("layers") or "").strip() == UNITS50:
        return _units50_map(params)
    return _door(params.get("layers")).get_map(params)


def get_feature_info(params: dict) -> dict:
    name = str(params.get("query_layers") or params.get("layers") or "").strip()
    if name == UNITS50:
        return _units50_info(params)
    return _door(name).get_feature_info(params)


def get_legend(layer: str):
    if layer == UNITS50:
        raise GeosphereError("1:5만은 범례를 두지 않는다 — 도폭마다 수백 칸이다")
    door = _door(layer)
    r = _get(door.url(), {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                          "layer": door.layers[layer].split(",")[0]})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GeosphereError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def _age(raw: str, lang: str) -> str:
    ics = i18n.age_local(raw)
    return (i18n.age_ko(ics) if lang == "ko" else ics) if ics else raw.strip()


def friendly(props: dict, lang: str = "ko") -> dict:
    """1:100만은 `Beschreibung` 의 "암상; 시대" 를 떼어, 1:5만은 GeoSciML 열에서 — 값은 독일어 그대로, 시대만 옮긴다(못 옮기면 원문)"""
    if "geologicUnitName" in props:
        value = lambda k: "" if str(props.get(k) or "").strip() in ("Unknown", "Null") else str(props.get(k) or "").strip()  # noqa: E731
        rows = (("이름", value("geologicUnitName")), ("설명", value("description")), ("암석", value("lithology")),
                ("지질시대", _age(value("representativeAge"), lang) if value("representativeAge") else ""),
                ("지구조 구역", value("tectonicUnitName")), ("도폭", value("collectionName")))
        return {k: v for k, v in rows if v}
    text = str(props.get("Beschreibung") or "").strip()
    rock, _, age = text.rpartition(";") if ";" in text else (text, "", "")
    ics = i18n.age_local(age)
    age = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else age.strip()
    rows = (("암석", rock.strip()), ("지질시대", age), ("지구조 구역", str(props.get("Tektonik") or "").strip()))
    return {k: v for k, v in rows if v}
