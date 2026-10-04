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


# ── 지역의 투영 격자 (3413·3031·3575·4326) ──────────────────────────────
#
# NPI 는 지역의 투영으로 곧장 받는다(021). 화면의 `npolarSource` 가
# `ol.tilegrid.createXYZ({extent, tileSize: 512})` 로 짓는 격자를 옮겼다.
# 범위는 `map.js` 가 투영에 건 것과 같다 — 3413 은 ±4194304, 3031 은 GeoMAP 의
# 범위(±3333134.0276). 셈의 차례는 3857 과 같다(`tile_extent`).
#
# 같은 `npolarSource` 를 타는 유럽 상류도 여기 선다(wetherilli 182) — NGU 의 북극 람베르트(3575, `map.js` 가 건 ±9009964.76)와
# IGME 1:100만의 4326(OpenLayers 가 아는 범위 ±180·±90). 4326 은 가로가 세로의 두 배라 OpenLayers 가 **가로 폭으로** 해상도를
# 정한다 — 줌 0 은 360° 네모 한 장(남쪽이 -270° 까지 걸친다), 줄 수는 칸 수의 반이다. 그리고 WMS 1.3.0 의 4326 은 **위도가 먼저**라
# OpenLayers 가 BBOX 를 남,서,북,동 으로 적는다(`bbox_text`).

EXTENT = {
    "EPSG:3413": (-4194304.0, -4194304.0, 4194304.0, 4194304.0),
    "EPSG:3031": (-3333134.0276, -3333134.0276, 3333134.0276, 3333134.0276),
    "EPSG:3575": (-9009964.76, -9009964.76, 9009964.76, 9009964.76),
    "EPSG:4326": (-180.0, -90.0, 180.0, 90.0),
    # 캐나다 람베르트(wetherilli 204) — 3857 과 같은 너비로 잡아 줌 번호가 3857 과 같은 해상도다(`map.js` 가 같은 범위를 건다)
    "EPSG:3978": (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244),
}
#: 위도가 먼저인 투영 — WMS 1.3.0 의 축 차례
LAT_FIRST = ("EPSG:4326",)


class Grid:
    def __init__(self, crs: str, tile: int = TILE):
        self.crs = crs
        self.extent = EXTENT[crs]
        self.tile = tile
        width, height = self.extent[2] - self.extent[0], self.extent[3] - self.extent[1]
        self.max_res = max(width, height) / tile          # OpenLayers 의 `resolutionsFromExtent`
        self.height = height

    def resolution(self, z: int) -> float:
        return self.max_res / math.pow(2, z)

    def last(self, z: int) -> tuple:
        """줌 `z` 의 마지막 칸 (x, y). 4326 은 줄이 칸의 반이다."""
        rows = math.ceil(self.height / (self.tile * self.resolution(z)) - 1e-9)
        return 2 ** z - 1, max(1, rows) - 1

    def tile_extent(self, z: int, x: int, y: int) -> tuple:
        res = self.resolution(z)
        min_x = self.extent[0] + x * self.tile * res
        min_y = self.extent[3] - (y + 1) * self.tile * res
        return (min_x, min_y, min_x + self.tile * res, min_y + self.tile * res)

    def tiles_for(self, bbox_lonlat, z: int):
        min_x, min_y, max_x, max_y = projected_bbox(bbox_lonlat, self.crs)
        span = self.tile * self.resolution(z)
        last_x, last_y = self.last(z)
        x0 = max(0, int((min_x - self.extent[0]) // span))
        x1 = min(last_x, int((max_x - self.extent[0]) // span))
        y0 = max(0, int((self.extent[3] - max_y) // span))
        y1 = min(last_y, int((self.extent[3] - min_y) // span))
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                yield z, x, y

    def bbox_text(self, extent) -> str:
        """WMS 의 BBOX 글자 — 브라우저(OpenLayers `TileWMS`)가 적는 그대로."""
        min_x, min_y, max_x, max_y = extent
        values = (min_y, min_x, max_y, max_x) if self.crs in LAT_FIRST else (min_x, min_y, max_x, max_y)
        return ",".join(js_number(v) for v in values)

    def wms_params(self, layer: str, z: int, x: int, y: int) -> dict:
        return dict(wms_params(layer, z, x, y), crs=self.crs, bbox=self.bbox_text(self.tile_extent(z, x, y)))


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


def forward(lon: float, lat: float, crs: str) -> tuple:
    """위경도 → 격자의 투영. 북극 람베르트(3575)는 `crs.py` 의 식(중앙 경선 10°)이다."""
    if crs == "EPSG:4326":
        return lon, lat
    if crs == "EPSG:3575":
        from . import crs as planar      # crs 는 import 가 없다 — 돌고 도는 일이 없다
        return planar.latlon_to_laea_north(lat, lon, 10.0)
    if crs == "EPSG:3978":
        # NAD83 / Canada Atlas Lambert — 표준위선 49°·77°, 원점 49°N 95°W. NAD83(GRS80)과 WGS84 는 이 셈에서 같다
        from . import crs as planar
        return planar.latlon_to_lcc(lat, lon, -95.0, 49.0, 77.0, lat0=49.0)
    return polar_forward(lon, lat, crs)


#: 극점을 품는 투영 — 북극 1·남극 -1
_POLE = {"EPSG:3413": 1, "EPSG:3031": -1, "EPSG:3575": 1, "EPSG:3978": 0}


def projected_bbox(bbox_lonlat, crs: str) -> tuple:
    """위경도 네모 → 그 투영에서 네모를 덮는 범위. 극 평사도법·람베르트에서 위경도 네모는
    부채꼴이라 가장자리를 촘촘히 짚어 본다. 극점을 품으면 극점도 넣는다."""
    west, south, east, north = bbox_lonlat
    if crs == "EPSG:4326":
        return west, south, east, north
    steps = 32
    points = []
    for i in range(steps + 1):
        lon = west + (east - west) * i / steps
        lat = south + (north - south) * i / steps
        points += [(lon, south), (lon, north), (west, lat), (east, lat)]
    sign = _POLE[crs]
    if (sign > 0 and north >= 89.999) or (sign < 0 and south <= -89.999):
        points.append((0.0, 90.0 * sign))
    xy = [forward(lon, lat, crs) for lon, lat in points]
    return (min(p[0] for p in xy), min(p[1] for p in xy),
            max(p[0] for p in xy), max(p[1] for p in xy))
