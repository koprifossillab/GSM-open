"""남아프리카공화국 지질조사소(CGS) 1:100만으로 나가는 문 — 정부(DPME) GIS 의 사본 (wetherilli 209).

- CGS 자신의 지도 서버(`maps.geoscience.org.za`)는 이 서버에서 45 초 시간 초과다(docs/다른_대륙_지질도.md §10). 그래서 계획·감시·평가부
  (DPME) 의 ArcGIS 11.3 `dpmegis.dpme.gov.za/arcgis/rest/services/Geology/MapServer` 의 레이어 5 "Geology 1 million (Council for Geoscience)" 를 쓴다
- **WMS 가 꺼져 있다**(WMSServer 400) — ArcGIS REST 의 `export`·`identify`·`legend` 를 부른다. 화면은 다른 상류처럼 WMS 변수를 보내고
  (`map.js` 의 `npolarSource`) 문이 옮긴다 — NPI 문(021)과 같은 수다. 문은 서로를 타지 않아 옮기는 셈을 여기 따로 둔다
- 3857 로 그린다. 넓은 그림 한 장이 11 초까지 걸린다(2026-10-04, 요하네스버그 둘레 250 km) — 가까우면 2–3 초
- 속성(`identify`): `STRAT_NAME`·`STRAT_RANK`·`STRAT_PAR_`(상위 층서)·`CHRONO_NAM`·`LITHO_1..5`·`LABEL`. 값은 영어 대문자 그대로 둔다
- **광업·자원 지역**(wetherilli 285) — 같은 서비스의 레이어 0 "Main Mining areas (CSIR)"(면 8 — 새·쇠퇴·생산 광업 지역)·
  1 "Main Coal resource areas (CGS)"(면 86)·2 "Uranium areas (CGS)"(면 19 — 층군 이름). 거친 지역 구분이지 광상 점이 아니다.
  석탄 지역은 속성이 번호뿐이라 누르지 않는다. 같은 조건(NO_STORE)을 따른다
- 조건: `copyrightText` 가 비었다. 자료의 주인은 CGS 이고 CGS 자료는 원래 판다. **서버 캐시에 담지 않는다**(`views.NO_STORE`) —
  받은 것을 다시 내주지 않으려는 것이다. 출처는 "Council for Geoscience (via DPME)". 정적 판에 싣지 않는다
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "cgs:"
ATTRIBUTION = ('Geology 1:1 000 000 — <a href="https://www.geoscience.org.za/" target="_blank" rel="noopener">Council for Geoscience</a>'
               ' (via DPME GIS)')
#: 레이어 → MapServer 의 레이어 번호
LAYERS = {"cgs:geology_1m": 5, "cgs:mining_areas": 0, "cgs:coal": 1, "cgs:uranium": 2}
#: 누르지 않는 레이어 — 석탄 지역은 속성이 번호뿐이다 (wetherilli 285)
NOT_QUERYABLE = ("cgs:coal",)
TIMEOUT = 45


class CgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _layer(params: dict, *keys) -> int:
    for key in keys:
        name = str(params.get(key) or "").split(",")[0].strip()
        if name:
            if name not in LAYERS:
                raise CgsError(f"모르는 레이어다: {name}")
            return LAYERS[name]
    raise CgsError("레이어가 없다")


def _box(params: dict) -> tuple:
    try:
        box = tuple(float(v) for v in str(params.get("bbox", "")).split(","))
    except ValueError as exc:
        raise CgsError("BBOX 를 읽지 못했다") from exc
    if len(box) != 4:
        raise CgsError("BBOX 를 읽지 못했다")
    return box


def _size(params: dict) -> tuple:
    try:
        w, h = int(params.get("width") or 256), int(params.get("height") or 256)
    except ValueError as exc:
        raise CgsError("크기를 읽지 못했다") from exc
    if not (0 < w <= 2048 and 0 < h <= 2048):
        raise CgsError("크기가 지나치다")
    return w, h


def _srs(params: dict) -> int:
    code = str(params.get("crs") or params.get("srs") or "EPSG:3857").upper()
    if code not in ("EPSG:3857", "EPSG:900913"):
        raise CgsError(f"3857 만 받는다: {code}")
    return 3857


def _get(op: str, params: dict):
    left = usage.paused()
    if left:
        raise CgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{settings.CGS_REST_URL.rstrip('/')}/{op}", params=params,
                         timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("cgs", ok=False)
        raise CgsError(f"DPME(CGS) 에 닿지 못했다: {exc}") from exc
    log.info("CGS %s -> %s", r.url, r.status_code)
    usage.record("cgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def export_params(params: dict) -> dict:
    """WMS `GetMap` 꼴 → ArcGIS `export` 변수."""
    layer, srs, box, (w, h) = _layer(params, "layers"), _srs(params), _box(params), _size(params)
    return {"bbox": ",".join(repr(v) for v in box), "bboxSR": srs, "imageSR": srs, "size": f"{w},{h}", "dpi": 96,
            "format": "png32", "transparent": "true", "layers": f"show:{layer}", "f": "image"}


def get_map(params: dict):
    r = _get("export", export_params(params))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise CgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def identify_params(params: dict) -> dict:
    """WMS `GetFeatureInfo` 꼴 → ArcGIS `identify` 변수. 누른 픽셀의 한가운데를 BBOX 안의 좌표로 옮긴다."""
    layer = _layer(params, "query_layers", "layers")
    srs, box, (w, h) = _srs(params), _box(params), _size(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise CgsError("누른 자리를 읽지 못했다") from exc
    x = box[0] + (i + 0.5) * (box[2] - box[0]) / w
    y = box[3] - (j + 0.5) * (box[3] - box[1]) / h
    return {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": srs, "layers": f"visible:{layer}",
            "tolerance": 2, "mapExtent": ",".join(repr(v) for v in box), "imageDisplay": f"{w},{h},96",
            "returnGeometry": "false", "f": "json"}


def get_feature_info(params: dict) -> dict:
    r = _get("identify", identify_params(params))
    if r.status_code != 200:
        raise CgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        results = r.json().get("results") or []
    except ValueError as exc:
        raise CgsError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"cgs.{x.get('attributes', {}).get('OBJECTID', i)}", "properties": x.get("attributes") or {}}
                         for i, x in enumerate(results[:3])]}


def get_legend(layer: str):
    raise CgsError("그림 범례는 쓰지 않는다 — 목록 범례(`legend_rows`)를 쓴다")


def legend_rows(layer: str) -> list:
    """REST `legend?f=json` → 화면이 그리는 줄 `[{"lithology", "swatch", "color"}]` (우루과이와 같은 꼴, wetherilli 196). 칸은 시대 12 개다."""
    number = LAYERS.get(layer)
    if number is None:
        raise CgsError(f"모르는 레이어다: {layer}")
    r = _get("legend", {"f": "json"})
    if r.status_code != 200:
        raise CgsError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise CgsError("범례가 JSON 이 아니다") from exc
    rows = []
    for part in data.get("layers") or []:
        if part.get("layerId") != number:
            continue
        for item in part.get("legend") or []:
            label = str(item.get("label") or "").strip()
            if label and item.get("imageData"):
                rows.append({"symbol": "", "lithology": label.capitalize(), "color": "transparent",
                             "swatch": f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"})
    return rows


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "") else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """층서 이름·상위 층서·시대·암석(LITHO_1..5 를 잇는다)·기호. 값은 영어 그대로 둔다."""
    if "resource" in props:                       # 우라늄 지역 (wetherilli 285)
        rows = (("광종", _value(props, "resource")), ("층군", _value(props, "Fields")), ("이름", _value(props, "Name")))
        return {k: v for k, v in rows if v}
    if "OID" in props and "Name" in props and "STRAT_NAME" not in props:   # 광업 지역
        return {"광업 지역": v} if (v := _value(props, "Name")) else {}
    out = {}
    name = _value(props, "STRAT_NAME")
    if name:
        rank = _value(props, "STRAT_RANK")
        out["층서 이름"] = f"{name} ({rank})" if rank else name
    parent = _value(props, "STRAT_PAR_")
    if parent:
        out["상위 층서"] = parent
    chrono = _value(props, "CHRONO_NAM")
    if chrono:
        out["지질시대"] = chrono
    rocks = [_value(props, k) for k in ("LITHO_1", "LITH0_2", "LITHO_2", "LITHO_3", "LITHO_4", "LITHO_5")]
    rocks = [r for r in dict.fromkeys(rocks) if r]
    if rocks:
        out["암석"] = ", ".join(rocks)
    label = _value(props, "LABEL")
    if label:
        out["기호"] = label
    return out
