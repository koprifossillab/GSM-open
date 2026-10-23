"""곧장 — 쓰는 사람의 KIGAM·VWorld 키로 상류를 부른다. GSM 이 닿지 않는 곳에서 굽는 길 (wetherilli P16·407).

**묶음 굽기에만 쓰는 둘째 문이다**(CLAUDE.md "상류마다 문이 하나") — GSM 자신은 이것을 쓰지 않는다(`viewer.kigam`·`viewer.vworld`).
받는 꼴은 GSM 의 문과 같게 짓는다 — KIGAM 은 `tilegrid.wms_params`(3857, 512 px)를 2048 px 큰 그림 한 장(`prewarm --meta 4`)으로,
VWorld 는 WMTS 경로 그대로.

- **키는 환경변수로만 받는다**(`GSM_KIGAM_KEY`·`GSM_VWORLD_KEY`, 또는 한 줄짜리 파일 `GSM_*_KEY_FILE`) — 묶음·parts·로그에 적지 않는다
- 지층 면은 GeoServer(`/mgeo/geoserver`)의 DescribeLayer·WFS — 키를 묻지 않는 곳이라 키를 붙이지 않는다
- 엮은 레이어(`L_50K_Geology_Map_NoAttitude`, GSM 의 `kigam.COMPOSED`)는 굽지 못한다 — GSM 경유로 굽는다
"""
import io
import json
import math
import os
import time
import urllib.parse
from pathlib import Path

from PIL import Image

from .. import bake, grid, net, units as units_mod
from . import PartsSource

WMS_URL = "https://data.kigam.re.kr/openapi/wms"
GEOSERVER_URL = "https://data.kigam.re.kr/mgeo/geoserver"
VWORLD_WMTS_URL = "https://api.vworld.kr/req/wmts/1.0.0/{key}/{layer}/{z}/{y}/{x}.{ext}"
VWORLD_LAYERS = {"Base": "png", "white": "png", "midnight": "png", "Hybrid": "png", "Satellite": "jpeg"}
COMPOSED = {"L_50K_Geology_Map_NoAttitude"}
META = 4
KIGAM_ATTRIBUTION = "한국지질자원연구원 지오빅데이터 오픈플랫폼"
VWORLD_ATTRIBUTION = "VWorld (국토교통부 공간정보 오픈플랫폼)"


def key_from_env(name: str) -> str:
    """`GSM_KIGAM_KEY`, 없으면 `GSM_KIGAM_KEY_FILE` 의 첫 줄. 값을 내보이지 않는다."""
    value = os.environ.get(name, "").strip()
    if not value and os.environ.get(f"{name}_FILE"):
        path = Path(os.environ[f"{name}_FILE"])
        value = path.read_text(encoding="utf-8").strip().splitlines()[0].strip() if path.is_file() else ""
    return value


def _crop(content, nx, ny, size=512):
    image = Image.open(io.BytesIO(content))
    pieces = {}
    for dx in range(nx):
        for dy in range(ny):
            buf = io.BytesIO()
            image.crop((dx * size, dy * size, dx * size + size, dy * size + size)).save(buf, format="PNG", optimize=True)
            pieces[(dx, dy)] = buf.getvalue()
    return pieces


class KigamDirect(PartsSource):
    """KIGAM `/openapi/wms` — 화면의 `wmsSource`(3857, 512 px). 화면 줌 s 는 격자 줌 s − 1. 큰 그림 한 장으로 열여섯 칸."""
    tile_size, kind, type, attribution = 512, "kigam", "image/png", KIGAM_ATTRIBUTION

    def __init__(self, name, key, parts, title=None):
        if name in COMPOSED:
            raise ValueError(f"{name} 은 엮은 레이어라 곧장 굽지 못한다 — GSM 경유(--via)로 굽는다")
        super().__init__(name, parts)
        self.key, self.title = key, title or name

    def grid_zoom(self, screen):
        return max(0, screen - 1)

    def calls_for(self, missing):
        return math.ceil(missing / (META * META) * 1.5)

    def fetch(self, z, x, y):
        last = 2 ** z - 1
        x0, y0 = x // META * META, y // META * META
        x1, y1 = min(x0 + META - 1, last), min(y0 + META - 1, last)
        nx, ny = x1 - x0 + 1, y1 - y0 + 1
        sw, ne = grid.cell_extent(z, x0, y1), grid.cell_extent(z, x1, y0)
        params = {"service": "WMS", "version": "1.3.0", "request": "GetMap", "format": "image/png", "transparent": "true",
                  "layers": self.name, "tiled": "true", "styles": "", "width": str(512 * nx), "height": str(512 * ny),
                  "crs": "EPSG:3857", "bbox": grid.bbox_text((sw[0], sw[1], ne[2], ne[3])), "key": self.key}
        where = f"{self.name}/{z}/{x0}–{x1}/{y0}–{y1}"
        status, head, body = net.get(WMS_URL + "?" + urllib.parse.urlencode(params), where=where, secrets=(self.key,))
        if status != 200 or not head.get("content-type", "").startswith("image/"):
            raise bake.FetchError(f"KIGAM 이 지도가 아닌 것을 주었다 ({where}, status={status})",
                                  blocked=net.looks_blocked(status, body))
        try:
            pieces = _crop(body, nx, ny)
        except OSError as exc:
            raise bake.FetchError(f"KIGAM 의 그림을 읽지 못했다 ({where})") from exc
        for (dx, dy), data in pieces.items():
            self.keep(z, x0 + dx, y0 + dy, data)
        return self.cached(z, x, y)


class VWorldDirect(PartsSource):
    """VWorld WMTS — 화면의 `vworldSource`(256 px XYZ). 격자 줌이 화면 줌이다. 자료 밖은 200 에 XML — 빈 것이다."""
    tile_size, attribution = 256, VWORLD_ATTRIBUTION

    def __init__(self, name, key, parts):
        layer = name.split(":", 1)[1]
        if layer not in VWORLD_LAYERS:
            raise ValueError(f"VWorld 배경에 {layer} 가 없다 — {', '.join(VWORLD_LAYERS)}")
        super().__init__(name, parts)
        self.layer, self.key = layer, key
        self.title, self.kind = f"VWorld {layer}", name
        self.type = "image/jpeg" if VWORLD_LAYERS[layer] == "jpeg" else "image/png"

    def grid_zoom(self, screen):
        return screen

    def fetch(self, z, x, y):
        where = f"{self.layer}/{z}/{y}/{x}"
        url = VWORLD_WMTS_URL.format(key=self.key, layer=self.layer, z=z, y=y, x=x, ext=VWORLD_LAYERS[self.layer])
        status, head, body = net.get(url, where=where, secrets=(self.key,))
        if status == 200 and head.get("content-type", "").startswith("image/"):
            return self.keep(z, x, y, body)
        if status == 200:
            return self.keep(z, x, y, b"")
        raise bake.FetchError(f"VWorld 가 타일을 주지 않았다 ({where}, status={status})", blocked=net.looks_blocked(status, body))


def _geoserver(path, params, where):
    status, _, body = net.get(f"{GEOSERVER_URL}/{path}?" + urllib.parse.urlencode(params), where=where)
    if status != 200:
        raise bake.FetchError(f"GeoServer 가 받지 않았다 ({where}, status={status})", blocked=net.looks_blocked(status, body))
    try:
        return json.loads(body)
    except ValueError as exc:
        raise bake.FetchError(f"GeoServer 의 {where} 가 JSON 이 아니다") from exc


def units(names, bbox, gap, log=print) -> dict:
    """`{레이어: (GeoJSON 바이트, 피처 타입들)}` — 레이어마다 DescribeLayer 한 번과 지층 피처 타입마다 WFS 한 번, `gap` 초 간격.
    속성은 링크만 가른다(영어판 없음, `units.plain`). 실패해도 묶음은 굽는다(속성 없이)"""
    west, south, east, north = bbox
    out = {}
    for name in names:
        try:
            rows = _geoserver("wms", {"service": "WMS", "version": "1.1.1", "request": "DescribeLayer",
                                      "layers": f"geoOpen:{name}", "outputFormat": "application/json"},
                              f"DescribeLayer {name}").get("layerDescriptions") or []
            types = [r["typeName"] for r in rows if r.get("owsType") == "WFS" and "litho" in (r.get("typeName") or "").lower()]
            time.sleep(gap)
            features = []
            for type_name in types:
                data = _geoserver("wfs", {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "srsName": "EPSG:4326",
                                          "typeNames": type_name, "outputFormat": "application/json",
                                          "bbox": f"{south},{west},{north},{east},urn:ogc:def:crs:EPSG::4326"}, f"WFS {type_name}")
                features += units_mod.features(data, bbox)
                time.sleep(gap)
        except bake.FetchError as exc:
            log(f"  {name} 지층 면을 받지 못했다 — 속성 없이 굽는다: {exc}")
            continue
        if not features:
            continue
        body = bake.units_body(features)
        out[name] = (body, types)
        log(f"  {name} 지층 면 {len(features)} — {', '.join(types)}, {len(body) / 1024:.0f} KB")
    return out
