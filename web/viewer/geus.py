"""GEUS(덴마크·그린란드 지질조사소)로 나가는 문 — 그린란드 지질도.

`kigam.py`·`vworld.py` 와 나란한 **세 번째 문**이다 (CLAUDE.md "상류마다 문이
하나"). 그린란드 레이어는 여기로만 나간다.

- 주소: `data.geus.dk/geusmap/ows/3857.jsp?mapname=greenland_portal` (MapServer)
  2026-09-27 에 찾았다. GEUS 안내 페이지는 `mapname=greenland` 를 적었지만
  그 이름은 404 이고, GEUS 지도 화면의 코드에 있던 `greenland_portal` 이 돈다
- **부르는 이를 밝힌다** (`whoami`). GEUS 는 서버가 작아 이름 없는 호출을
  바쁜 시간에 거절할 수 있다고 적었다. 로그에는 적지 않는다 — 이메일이다
- 그림은 3000 × 3000 까지, 한 번에 레이어 5 개까지 (GEUS 의 제한)
- 속성은 `text/plain` 으로 받는다. `application/json` 을 광고하지만 비어 온다
"""
import json
import logging
import re

import requests
from django.conf import settings

from types import SimpleNamespace as _NS

from . import arcwms, tilecache, usage

log = logging.getLogger(__name__)

_WHOAMI_RE = re.compile(r"(whoami=)[^&\s]*", re.I)


class GeusError(RuntimeError):
    pass


def _get(params: dict):
    sent = dict(params, nocache="nocache", mapname=settings.GEUS_MAPNAME,
                whoami=settings.GEUS_WHOAMI)
    try:
        r = requests.get(settings.GEUS_WMS_URL, params=sent, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("geus", ok=False)
        reason = _WHOAMI_RE.sub(r"\1…", str(exc))       # 예외 문구에 URL 이 실려 온다
        raise GeusError(f"GEUS 에 닿지 못했다: {reason}") from exc
    log.info("GEUS %s -> %s", _WHOAMI_RE.sub(r"\1…", r.url), r.status_code)
    usage.record("geus", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 GeusError."""
    params = dict(params, service="WMS", request="GetMap")
    # GEUS 는 WMS 1.1.1 의 SRS 를 쓴다. 브라우저가 1.3.0 의 CRS 로 보내면 옮겨 적는다
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["version"] = "1.1.1"
    r = _get(params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GeusError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
              "format": "image/png", "layer": layer})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GeusError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` → KIGAM 과 같은 꼴의 GeoJSON 비슷한 dict (`features`)."""
    params = dict(params, service="WMS", request="GetFeatureInfo", info_format="text/plain")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    params["version"] = "1.1.1"
    r = _get(params)
    if r.status_code != 200:
        raise GeusError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


_FEATURE = re.compile(r"^\s*Feature\s+(\S+):\s*$")
_ATTR = re.compile(r"^\s{2,}(\w+)\s*=\s*'(.*)'\s*$")
_LAYER = re.compile(r"^Layer '([^']+)'")


def parse_plain(text: str) -> list:
    """MapServer 의 text/plain 속성을 feature 목록으로.

        Layer 'grl_g500_lithostr_search'
          Feature 733:
            gu_name = 'Rapakivi Suite'
    """
    features, layer, current = [], "", None
    for line in (text or "").splitlines():
        m = _LAYER.match(line)
        if m:
            layer = m.group(1)
            continue
        m = _FEATURE.match(line)
        if m:
            current = {"id": f"{layer}.{m.group(1)}", "properties": {}}
            features.append(current)
            continue
        m = _ATTR.match(line)
        if m and current is not None:
            current["properties"][m.group(1)] = m.group(2)
    return features


#: GEUS 의 열 이름 → 팝업에 보일 이름. 여기 없는 열은 그대로 보인다.
#: 안쪽에서만 쓰는 열(`id_hidden`·`rgb`)은 뺀다.
FRIENDLY = {
    "gu_mapcode": "지질기호",
    "gu_name": "지질 단위",
    "ics_min_age_num": "최소 연대 (Ma)",
    "ics_max_age_num": "최대 연대 (Ma)",
    "report_link": "설명",
}
HIDDEN = {"id_hidden", "rgb", "fid", "objectid", "gid"}


def friendly(props: dict) -> dict:
    out = {}
    for key, value in props.items():
        if key.lower() in HIDDEN:
            continue
        if isinstance(value, str) and re.fullmatch(r"-?\d+\.0+", value):
            value = value.split(".")[0]                   # 1600.000000 → 1600
        out[FRIENDLY.get(key, key)] = value
    return out


# ── GEUS 의 ArcGIS 서버 — 자력 편찬·DTU 부게 중력·지질구 (wetherilli 259) ───────────────
#
# 지도 화면(greenland_portal)은 지구물리를 `data.geus.dk/arcgis/rest/services/Greenland/<서비스>/MapServer` 에서 받는다. 목록이 열려 있다.
# 상류 이름은 `geusarc` 로 따로 두되 문은 여기다(같은 기관이다).
#
# - 조건: 지도 서비스와 같은 GEUS 이용 조건(`terms_20140620.pdf`) — **개인 용도**로 쓰고 GEUS 를 출처로 밝힌다. 다시 펴내거나 퍼뜨리려면
#   서면 동의가 든다. 그래서 다른 GEUS 레이어처럼 서버가 받아 보이기만 하고 **정적 판에는 싣지 않는다**. 부게 중력은 DTU Space 의 것이다
# - REST `export` 를 화면의 투영(3413)으로 곧장 받는다 — 서비스의 투영은 UTM 24N(32624)이라 상류가 다시 그린다. 자력 편찬은 넓게 보면 한 장이
#   40 초를 넘을 때가 있다(2026-10-05) — 캐시에 기댄다
# - whoami 는 이 서버에도 붙인다(쓰지 않아도 해가 없다) — 로그에서는 지운다
_ARC_ROOT = "https://data.geus.dk/arcgis/rest/services/Greenland"
#: 레이어 → (서비스, 보일 REST 레이어, 누르기가 되나)
ARC_LAYERS = {
    "geusarc:magnetic": ("Magnetic_compilation", "0", False),          # 측선(6)은 뺀다
    "geusarc:bouguer": ("dtu_bouguer_anomaly", "3", False),            # 관측점(0–2)은 뺀다
    "geusarc:provinces": ("Geological_provinces_2500k", "1,0,3,6,5", True),
    # 더한 것 (wetherilli 301) — 공중 자력 셋은 조사한 곳만 덮는다(서남부·동부·북부의 조각)
    "geusarc:aeromag": ("Geophysics_Aeromag_Magnetic", "0", False),               # AEROMAG 1992–2013 총자력
    "geusarc:aeromag_tilt": ("Geophysics_Aeromag_Magnetic", "2", False),          # 같은 것의 기울기 도함수 — 구조선이 잘 보인다
    "geusarc:awi": ("Geophysics_Aeromag_AWI", "2", False),                       # AWI 1993–96 동부 해안, 300–600 nT 색 척도(측선 0 은 뺀다)
    "geusarc:aem": ("Geophysics_Aem_Magnetic", "1,2,3,4,5,6,7,8,9,10", False),     # 국지 헬기 조사 열
    "geusarc:g2500k": ("Geological_map_2500k", "4,2,1", True),                    # 지질·경계·구조선(글자 0 은 뺀다)
    "geusarc:g100k_ssw": ("Geological_map_100k_SSW", "5,3,0", True),              # 서남부 1:10만 — 지질·경계·구조선
    "geusarc:g100k_karrat": ("Geological_map_100k_Karrat", "17,13,10", True),     # 카라트 1:10만 — 지질·경계·구조선
}
#: 누를 때만 다른 REST 레이어에 묻는 것 — 선(경계·구조선)을 빼고 면에만. 목록 범례도 이 면의 것이다
ARC_QUERY = {"geusarc:g2500k": "4", "geusarc:g100k_ssw": "5", "geusarc:g100k_karrat": "17"}
#: 목록 범례(`views.list_legend`)를 내는 레이어 — 지구물리는 REST 범례가 RGB 띠 이름뿐이라 두지 않는다 (wetherilli 301)
LEGEND_LAYERS = tuple(ARC_QUERY)
LEGEND_MAX_AGE = 30 * 86400
#: 메타타일로 받는다 (wetherilli 307) — REST export 는 요청마다 드는 값이 크다: 서남부 1:10만 512 px 40 초·1 024 px(칸 넷) 40–48 초,
#: 자력 편찬 1.9·2.3 초. 화면이 3413 이라 극지 격자로 자른다. `metatile.limit` 의 표
METATILE = {"geusarc:": None}
ARC_ATTRIBUTION = {"geusarc:bouguer": "Bouguer anomaly © DTU Space · via GEUS"}
GEUS_ATTRIBUTION = '© <a href="https://www.geus.dk/" target="_blank" rel="noopener">GEUS</a> (personal use, terms 2014-06-20)'


def arc_knows(name: str) -> bool:
    return name in ARC_LAYERS


def _arc(name: str):
    if name not in ARC_LAYERS:
        raise GeusError(f"모르는 레이어다: {name}")
    return ARC_LAYERS[name]


def _arc_get(path: str, params: dict):
    sent = dict(params, whoami=settings.GEUS_WHOAMI)
    left = usage.paused()
    if left:
        raise GeusError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{_ARC_ROOT}/{path}", params=sent, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("geusarc", ok=False)
        reason = _WHOAMI_RE.sub(r"\1…", str(exc))
        raise GeusError(f"GEUS ArcGIS 에 닿지 못했다: {reason}") from exc
    log.info("GEUS-ArcGIS %s -> %s", _WHOAMI_RE.sub(r"\1…", r.url), r.status_code)
    usage.record("geusarc", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _view(params: dict):
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if not crs.startswith("EPSG:"):
        raise GeusError(f"EPSG 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise GeusError("범위·크기를 읽지 못했다") from exc
    return crs[5:], bbox, width, height


def arc_get_map(params: dict):
    service, layers, _ = _arc(str(params.get("layers") or "").strip())
    sr, bbox, width, height = _view(params)
    r = _arc_get(f"{service}/MapServer/export", {
        "bbox": ",".join(repr(v) for v in bbox), "bboxSR": sr, "imageSR": sr, "size": f"{width},{height}",
        "format": "png32", "transparent": "true", "dpi": "96", "layers": f"show:{layers}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GeusError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def arc_get_legend(layer: str):
    raise GeusError("GEUS ArcGIS 범례는 그림으로 받지 않는다 — 지질도는 목록 범례(`legend_rows`)")


def legend_rows(layer: str) -> list:
    """지질도 1:250만·1:10만의 칸 — REST 범례의 이름표와 견본(78·195·79 칸). 한 번 받아 30 일 담아 둔다 (wetherilli 301)"""
    if layer not in LEGEND_LAYERS:
        raise GeusError(f"범례가 없는 레이어다: {layer}")
    service, _, _ = _arc(layer)
    key = tilecache.key_text("geusarc-legend", layer)
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _arc_get(f"{service}/MapServer/legend", {"f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise GeusError("범례가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise GeusError(f"범례를 받지 못했다 (status={r.status_code})")
    rows = [{"symbol": "", "lithology": label, "age": "", "color": "transparent", "swatch": uri}
            for label, uri in arcwms.legend_list(data, layer_ids=(int(ARC_QUERY[layer]),))]
    tilecache.put(key, json.dumps(rows, ensure_ascii=False).encode("utf-8"), ".json")
    return rows


def arc_get_feature_info(params: dict) -> dict:
    name = str(params.get("query_layers") or params.get("layers") or "").strip()
    service, layers, queryable = _arc(name)
    if not queryable:
        return {"features": []}
    sr, bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise GeusError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _arc_get(f"{service}/MapServer/identify", {
        "geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": sr, "layers": f"all:{ARC_QUERY.get(name, layers)}", "tolerance": "2",
        "mapExtent": ",".join(repr(v) for v in bbox), "imageDisplay": f"{width},{height},96", "returnGeometry": "false", "f": "json"})
    if r.status_code != 200:
        raise GeusError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        results = r.json().get("results") or []
    except ValueError as exc:
        raise GeusError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"geusarc.{n}", "properties": dict(res.get("attributes") or {}, _layer=res.get("layerName", ""))}
                         for n, res in enumerate(results)]}


#: 지질구 레이어 이름 → 한국어 갈래
PROVINCE_KINDS = {"Quaternary": "제4기", "Sedimentary_basins": "퇴적분지", "Supracrustal_rocks": "표성암",
                  "Magmatic_provinces": "화성구", "Precambrian_basement": "선캄브리아 기반"}


def arc_friendly(props: dict, lang: str = "ko") -> dict:
    if "gm_label" in props:                      # 지질도 1:250만·1:10만 (wetherilli 301) — 열 이름이 판마다 조금씩 다르다
        def first(*keys):
            return next((str(props[k]).strip() for k in keys if str(props.get(k) or "").strip()), "")
        rows = (("기호", first("gm_label")), ("단위", first("gm_unit_name", "Legend_Heading", "Heading")),
                ("설명", first("Description", "short_description")))
        return {k: x for k, x in rows if x}
    kind = str(props.get("_layer") or "")
    text = str(props.get("Description") or props.get("short_text") or "").strip()
    rows = (("갈래", PROVINCE_KINDS.get(kind, kind) if lang == "ko" else kind.replace("_", " ")), ("지질구", text))
    return {k: x for k, x in rows if x}


ARC = _NS(get_map=arc_get_map, get_feature_info=arc_get_feature_info, get_legend=arc_get_legend)


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "geus", "tag": "GEUS", "title": "덴마크·그린란드 지질조사소", "relay": True, "globe": True},
    {"upstream": "geusarc", "tag": "GEUS", "title": "덴마크·그린란드 지질조사소", "relay": ARC, "projected": True, "globe": True},
]
