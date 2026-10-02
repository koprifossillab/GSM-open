"""브라우저가 부르는 타일을 서버에서 똑같이 셈한다 — 미리 데우기가 쓴다.

**한 글자라도 다르면 캐시가 맞지 않는다.** 캐시 열쇠는 WMS 변수의 문자열
(`tilecache.key_for`)이라, 브라우저가 `BBOX=0,…` 을 보내는데 우리가
`BBOX=0.0,…` 으로 받아 두면 헛일이다. 그래서 OpenLayers 가 하는 셈을 그
차례 그대로 옮겼다.

- 격자: `ol.tilegrid.createXYZ({tileSize: 512})` (`map.js` 의 `wmsSource`)
- 해상도: `최대해상도 / 2^z`, 최대해상도 = 세계 폭 / 512
- 타일 범위: `minX = 원점X + x·512·해상도`, `minY = 원점Y − (y+1)·512·해상도`
  (OpenLayers 의 `getTileCoordExtent`, 곱하는 차례까지 같게)
- 숫자 적기: 자바스크립트 `Number` 의 문자열과 같게 — 정수면 `.0` 을 뗀다

2026-09-27 에 브라우저가 실제로 부른 타일 주소와 한 글자까지 대조했다
(`test_tilegrid`).
"""
import math

HALF = 20037508.342789244            # EPSG:3857 의 반 폭
WORLD = HALF * 2
TILE = 512
MAX_RES = WORLD / TILE


def resolution(z: int) -> float:
    return MAX_RES / math.pow(2, z)


def tile_extent(z: int, x: int, y: int) -> tuple:
    res = resolution(z)
    min_x = -HALF + x * TILE * res
    min_y = HALF - (y + 1) * TILE * res
    return (min_x, min_y, min_x + TILE * res, min_y + TILE * res)


def js_number(value: float) -> str:
    """자바스크립트가 숫자를 문자열로 적는 꼴. 이 범위의 값에서는 파이썬의
    `repr` 과 같되, 정수는 `.0` 을 붙이지 않는다."""
    if value == 0:
        return "0"
    if float(value).is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(float(value))


def lonlat_to_3857(lon: float, lat: float) -> tuple:
    x = lon * HALF / 180
    lat = max(min(lat, 85.0511287798), -85.0511287798)
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * HALF / math.pi
    return x, y


def tiles_for(bbox_lonlat, z: int):
    """위경도 범위 `(서, 남, 동, 북)` 를 덮는 줌 `z` 의 타일 `(z, x, y)` 들."""
    west, south, east, north = bbox_lonlat
    min_x, min_y = lonlat_to_3857(west, south)
    max_x, max_y = lonlat_to_3857(east, north)
    span = TILE * resolution(z)
    last = 2 ** z - 1
    x0 = max(0, int((min_x + HALF) // span))
    x1 = min(last, int((max_x + HALF) // span))
    y0 = max(0, int((HALF - max_y) // span))
    y1 = min(last, int((HALF - min_y) // span))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield z, x, y


def wms_params(layer: str, z: int, x: int, y: int) -> dict:
    """브라우저의 `TileWMS` 가 보내는 것과 같은 변수 (이름은 소문자로)."""
    return {
        "service": "WMS", "version": "1.3.0", "request": "GetMap",
        "format": "image/png", "transparent": "true", "layers": layer,
        "tiled": "true", "styles": "",
        "width": str(TILE), "height": str(TILE), "crs": "EPSG:3857",
        "bbox": ",".join(js_number(v) for v in tile_extent(z, x, y)),
    }


# ── 극지 격자 (3413·3031) ─────────────────────────────────────────────
#
# NPI 는 지역의 투영으로 곧장 받는다(021). 화면의 `npolarSource` 가
# `ol.tilegrid.createXYZ({extent, tileSize: 512})` 로 짓는 격자를 옮겼다.
# 범위는 `map.js` 가 투영에 건 것과 같다 — 3413 은 ±4194304, 3031 은 GeoMAP 의
# 범위(±3333134.0276). 셈의 차례는 3857 과 같다(`tile_extent`).

POLAR_EXTENT = {
    "EPSG:3413": (-4194304.0, -4194304.0, 4194304.0, 4194304.0),
    "EPSG:3031": (-3333134.0276, -3333134.0276, 3333134.0276, 3333134.0276),
}


class PolarGrid:
    def __init__(self, crs: str, tile: int = TILE):
        self.crs = crs
        self.extent = POLAR_EXTENT[crs]
        self.tile = tile
        self.max_res = (self.extent[2] - self.extent[0]) / tile

    def resolution(self, z: int) -> float:
        return self.max_res / math.pow(2, z)

    def tile_extent(self, z: int, x: int, y: int) -> tuple:
        res = self.resolution(z)
        min_x = self.extent[0] + x * self.tile * res
        min_y = self.extent[3] - (y + 1) * self.tile * res
        return (min_x, min_y, min_x + self.tile * res, min_y + self.tile * res)

    def tiles_for(self, bbox_lonlat, z: int):
        min_x, min_y, max_x, max_y = projected_bbox(bbox_lonlat, self.crs)
        span = self.tile * self.resolution(z)
        last = 2 ** z - 1
        x0 = max(0, int((min_x - self.extent[0]) // span))
        x1 = min(last, int((max_x - self.extent[0]) // span))
        y0 = max(0, int((self.extent[3] - max_y) // span))
        y1 = min(last, int((self.extent[3] - min_y) // span))
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                yield z, x, y

    def wms_params(self, layer: str, z: int, x: int, y: int) -> dict:
        return dict(wms_params(layer, z, x, y), crs=self.crs,
                    bbox=",".join(js_number(v) for v in self.tile_extent(z, x, y)))


# 극 평사도법 (Snyder 1987, 21-33~21-40). pyproj 없이 — crs.py 와 같은 까닭이다.
# 남극(3031)은 geomap.lonlat_to_3031 과 같은 식이다.
_A = 6378137.0
_F = 1 / 298.257223563
_E = math.sqrt(_F * (2 - _F))

#: 투영 → (북극이면 1·남극이면 -1, 표준위도, 중앙 경선)
_POLAR = {"EPSG:3413": (1, 70.0, -45.0), "EPSG:3031": (-1, -71.0, 0.0)}


def _t(phi):
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - _E * s) / (1 + _E * s)) ** (_E / 2)


def polar_forward(lon: float, lat: float, crs: str) -> tuple:
    """위경도 → 극 평사도법(3413·3031)의 미터."""
    sign, lat_ts, lon0 = _POLAR[crs]
    phi_c = math.radians(sign * lat_ts)
    mc = math.cos(phi_c) / math.sqrt(1 - (_E * math.sin(phi_c)) ** 2)
    phi = math.radians(sign * lat)
    lam = math.radians(sign * (lon - lon0))
    rho = _A * mc * _t(phi) / _t(phi_c)
    return (sign * rho * math.sin(lam), -sign * rho * math.cos(lam))


def projected_bbox(bbox_lonlat, crs: str) -> tuple:
    """위경도 네모 → 그 투영에서 네모를 덮는 범위. 극 평사도법에서 위경도 네모는
    부채꼴이라 가장자리를 촘촘히 짚어 본다. 극점을 품으면 극점도 넣는다."""
    west, south, east, north = bbox_lonlat
    steps = 32
    points = []
    for i in range(steps + 1):
        lon = west + (east - west) * i / steps
        lat = south + (north - south) * i / steps
        points += [(lon, south), (lon, north), (west, lat), (east, lat)]
    sign = _POLAR[crs][0]
    if (sign > 0 and north >= 89.999) or (sign < 0 and south <= -89.999):
        points.append((0.0, 90.0 * sign))
    xy = [polar_forward(lon, lat, crs) for lon, lat in points]
    return (min(p[0] for p in xy), min(p[1] for p in xy),
            max(p[0] for p in xy), max(p[1] for p in xy))

