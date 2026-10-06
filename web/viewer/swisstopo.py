"""swisstopo(스위스 연방 지형청)로 나가는 문 — 스위스 지질도 1:50만·GeoCover 1:2.5만 (wetherilli 211).

- 그림: `wms.geo.admin.ch` (MapServer WMS). 열쇠가 없다. 레이어 `ch.swisstopo.geologie-geologische_karte`(1:50만)·
  `ch.swisstopo.geologie-geocover`(GeoCover — 지질 아틀라스 1:2.5만을 벡터로 이은 것). 이름은 `swisstopo:<뒷부분>`. 3857 을 그린다
- 속성: WMS GetFeatureInfo 는 JSON 을 오류로 돌려준다(2026-10-04). 대신 **geo.admin.ch REST `identify`** — 화면이 보낸 WMS 꼴(범위·크기·누른
  화소)을 그 투영의 좌표 그대로 넘긴다(`sr`). 1:50만은 범례 글(독일어·프랑스어), GeoCover 는 암상·연대·지구조(독일어·프랑스어)
- CORS 가 `*` 이다. 조건: swisstopo 의 열린 정부 자료(OGD) — 자유롭게 쓰되 출처 "© swisstopo" 를 밝힌다
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "swisstopo:"
#: 메타타일로 받는다 (wetherilli 287) — 1:50만 512 px 2.1–4.5 초, 1 024 px 2.3 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"swisstopo:": None}
LAYERS = {"swisstopo:geologische_karte": "ch.swisstopo.geologie-geologische_karte",
          "swisstopo:geocover": "ch.swisstopo.geologie-geocover"}
ATTRIBUTION = '<a href="https://www.swisstopo.admin.ch/" target="_blank" rel="noopener">© swisstopo</a>'
TIMEOUT = 45


class SwisstopoError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _names(names: str) -> list:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if one not in LAYERS:
            raise SwisstopoError(f"모르는 레이어다: {one}")
        out.append(LAYERS[one])
    return out


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise SwisstopoError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("swisstopo", ok=False)
        raise SwisstopoError(f"swisstopo 에 닿지 못했다: {exc}") from exc
    log.info("swisstopo %s -> %s", r.url, r.status_code)
    usage.record("swisstopo", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def get_map(params: dict):
    params = dict(params, service="WMS", request="GetMap", version="1.3.0", layers=",".join(_names(params.get("layers"))))
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params.setdefault("styles", "")
    r = _get(settings.SWISSTOPO_WMS_URL, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SwisstopoError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get(settings.SWISSTOPO_WMS_URL, {"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0",
                                          "format": "image/png", "layer": _names(layer)[0], "sld_version": "1.1.0"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SwisstopoError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


def identify_params(params: dict) -> dict:
    """WMS GetFeatureInfo 꼴 → geo.admin.ch identify 꼴. 누른 화소의 가운데를 그 투영의 좌표로 셈한다(4326 은 받지 않는다)."""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if not crs.startswith("EPSG:") or crs == "EPSG:4326":
        raise SwisstopoError(f"이 좌표계로는 속성을 묻지 않는다: {crs}")
    try:
        a0, b0, a1, b1 = (float(v) for v in str(params.get("bbox", "")).split(",")[:4])
        width, height = float(params["width"]), float(params["height"])
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError):
        raise SwisstopoError("속성을 물을 자리가 없다 (BBOX·WIDTH·HEIGHT·I·J)") from None
    x = a0 + (i + 0.5) * (a1 - a0) / width
    y = b1 - (j + 0.5) * (b1 - b0) / height
    return {"geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "sr": crs.split(":")[1],
            "layers": "all:" + ",".join(_names(params.get("query_layers") or params.get("layers"))), "tolerance": "2",
            "mapExtent": f"{a0},{b0},{a1},{b1}", "imageDisplay": f"{int(width)},{int(height)},96",
            "returnGeometry": "false", "lang": "de"}


def get_feature_info(params: dict) -> dict:
    r = _get(settings.SWISSTOPO_IDENTIFY_URL, identify_params(params))
    if r.status_code != 200:
        raise SwisstopoError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        results = r.json().get("results") or []
    except ValueError as exc:
        raise SwisstopoError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"swisstopo.{hit.get('featureId', n)}", "properties": hit.get("attributes") or {}}
                         for n, hit in enumerate(results)]}


#: 상류의 열 → 팝업 이름. 독일어 열을 쓴다(스위스 연방 자료의 첫 언어). 프랑스어 짝은 뺀다
FRIENDLY = (
    ("leg_geol_d", "설명"),
    ("litho_de", "암석"),
    ("chrono_de", "지질시대"),
    ("tecto_de", "지구조 단위"),
    ("orig_description_de", "원 설명"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(독일어)은 그대로 둔다. `-` 는 빈 값이다."""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and value not in ("-", "null") and label not in out:
            out[label] = value
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "swisstopo", "tag": "swisstopo", "title": "스위스 연방 지형청", "relay": True, "projected": True, "globe": True},
]
