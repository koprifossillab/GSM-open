"""3857 타일 격자 — 칸 수(2^z)로 센다. 타일 크기(256·512 px)와 상관없이 맞는다. `viewer/tilegrid.py` 의 같은 셈을 옮겼다(viewer 를 타지 않게)."""
import math

HALF = 20037508.342789244            # EPSG:3857 의 반 폭


def lonlat_to_3857(lon: float, lat: float) -> tuple:
    x = lon * HALF / 180
    lat = max(min(lat, 85.0511287798), -85.0511287798)
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * HALF / math.pi
    return x, y


def tiles_for(bbox_lonlat, z: int) -> list:
    """위경도 범위 `(서, 남, 동, 북)` 를 덮는 줌 `z` 의 칸 `(x, y)` 들 — 위에서 아래로 y(OpenLayers 의 tileCoord)."""
    west, south, east, north = bbox_lonlat
    min_x, min_y = lonlat_to_3857(west, south)
    max_x, max_y = lonlat_to_3857(east, north)
    span = 2 * HALF / 2 ** z
    last = 2 ** z - 1
    x0 = max(0, int((min_x + HALF) // span))
    x1 = min(last, int((max_x + HALF) // span))
    y0 = max(0, int((HALF - max_y) // span))
    y1 = min(last, int((HALF - min_y) // span))
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def cell_extent(z: int, x: int, y: int) -> tuple:
    """칸 `(z, x, y)` 의 3857 범위 `(서, 남, 동, 북)` — 칸 수 2^z 로 센다(타일 크기와 상관없다). `viewer/tilegrid.tile_extent` 와 같은 셈의 차례다."""
    res = (2 * HALF / 512) / math.pow(2, z)          # 셈을 그대로 따른다 — 곱하는 차례가 달라도 끝자리가 갈린다
    min_x = -HALF + x * 512 * res
    min_y = HALF - (y + 1) * 512 * res
    return (min_x, min_y, min_x + 512 * res, min_y + 512 * res)


def js_number(value: float) -> str:
    """자바스크립트가 숫자를 적는 꼴 — 정수는 `.0` 없이. 화면이 짓는 BBOX 와 한 글자까지 같아야 서버 캐시의 열쇠가 맞는다(029)."""
    if value == 0:
        return "0"
    if float(value).is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(float(value))


def bbox_text(extent) -> str:
    return ",".join(js_number(v) for v in extent)


# ── 격자 꼴 (wetherilli P17·410) ───────────────────────────────────────
#
# 묶음의 열쇠는 화면 소스의 tileCoord 그대로라, 굽는 쪽이 레이어마다 화면과 **같은 격자**로 세야 한다. 남극 탭에는 격자가 셋이다 —
# 3031 의 투영 범위로 지은 것(`GEOMAP_GRID`·`createXYZ`, 256·512 px), Esri 극 타일(서비스의 `tileInfo`), 그리고 옮겨 그리는 3857(VWorld 테마).
# 범위로 지은 격자는 칸 한 변이 `폭 / 2^z` 라 타일 크기와 상관없다(한국의 3857 과 같다). 이름은 화면(`offline.js` 의 `gridName`)이 짓는 것과 같다 —
# 투영 코드, 원점이 투영 범위의 왼쪽 위가 아니면 `@<원점 x>`.

#: 3031 의 투영 범위 — 화면이 GeoMAP 의 범위로 건 것(`map.js`, `viewer/tilegrid.EXTENT`)
EXTENT_3031 = 3333134.0276

_A = 6378137.0
_F = 1 / 298.257223563
_E = math.sqrt(_F * (2 - _F))


def _t(phi):
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - _E * s) / (1 + _E * s)) ** (_E / 2)


def lonlat_to_3031(lon: float, lat: float) -> tuple:
    """위경도 → 남극 평사도법(표준위도 71°S, 중앙 경선 0°) — `viewer/tilegrid.polar_forward` 의 셈(Snyder 1987)."""
    phi_c = math.radians(71.0)
    mc = math.cos(phi_c) / math.sqrt(1 - (_E * math.sin(phi_c)) ** 2)
    phi, lam = math.radians(-lat), math.radians(-lon)
    rho = _A * mc * _t(phi) / _t(phi_c)
    return (-rho * math.sin(lam), rho * math.cos(lam))


class Grid:
    """타일 격자 하나 — 원점(왼쪽 위)·줌 0 의 칸 한 변(미터)·범위·투영. 칸은 위에서 아래로 y(OpenLayers 의 tileCoord)."""

    def __init__(self, name, origin, span0, extent, project, tile=512):
        self.name, self.origin, self.span0, self.extent, self.project, self.tile = name, origin, span0, extent, project, tile

    def resolution(self, z):
        return (self.span0 / self.tile) / math.pow(2, z)

    def cell_extent(self, z, x, y) -> tuple:
        """칸의 투영 범위 `(서, 남, 동, 북)` — 화면(OpenLayers)의 셈 차례 그대로(해상도 × 타일 크기)."""
        res = self.resolution(z)
        min_x = self.origin[0] + x * self.tile * res
        min_y = self.origin[1] - (y + 1) * self.tile * res
        return (min_x, min_y, min_x + self.tile * res, min_y + self.tile * res)

    def projected_bbox(self, bbox):
        """경위도 네모 → 투영의 덮는 네모. 극 평사도법에서 경위도 네모는 부채꼴이라 가장자리를 촘촘히 짚는다."""
        return _bounds(self.edge(bbox))

    def edge(self, bbox, steps=32):
        """경위도 네모의 테두리 — 투영 좌표의 닫힌 고리(한 변에 `steps` 점).
        극 평사도법에서 극을 품는 네모는 테두리가 고리를 이루지 않는다 — 묶음 박스로는 받지 않는다(`ValueError`)"""
        west, south, east, north = bbox
        if self is not MERCATOR and self.name != MERCATOR.name and (south <= -89.99 or north >= 89.99 or east - west >= 360):
            raise ValueError("극을 품는 박스는 굽지 못한다 — 극 평사도법에서 경위도 네모의 테두리가 고리가 아니다")
        ring = [(west + (east - west) * i / steps, south) for i in range(steps)]
        ring += [(east, south + (north - south) * i / steps) for i in range(steps)]
        ring += [(east - (east - west) * i / steps, north) for i in range(steps)]
        ring += [(west, north - (north - south) * i / steps) for i in range(steps)]
        return [self.project(lon, lat) for lon, lat in ring]

    def tiles_for(self, bbox, z) -> list:
        min_x, min_y, max_x, max_y = self.projected_bbox(bbox)
        span = self.tile * self.resolution(z)
        ex = self.extent
        last_x = math.ceil((ex[2] - self.origin[0]) / span - 1e-9) - 1
        last_y = math.ceil((self.origin[1] - ex[1]) / span - 1e-9) - 1
        first_x = max(0, int((ex[0] - self.origin[0]) // span))
        first_y = max(0, int((self.origin[1] - ex[3]) // span))
        x0 = max(first_x, int((min_x - self.origin[0]) // span))
        x1 = min(last_x, int((max_x - self.origin[0]) // span))
        y0 = max(first_y, int((self.origin[1] - max_y) // span))
        y1 = min(last_y, int((self.origin[1] - min_y) // span))
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def with_tile(self, tile):
        """같은 격자를 다른 타일 크기로 — 칸은 같고 셈의 끝자리만 화면을 따른다(WMS BBOX 글자가 화면과 같아야 할 때)."""
        return Grid(self.name, self.origin, self.span0, self.extent, self.project, tile)


def _bounds(points):
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


#: 한국 탭 — 지금까지의 3857(모듈의 `tiles_for`·`cell_extent` 와 같은 칸, wetherilli 402)
MERCATOR = Grid("EPSG:3857", (-HALF, HALF), 2 * HALF, (-HALF, -HALF, HALF, HALF), lonlat_to_3857)
#: 남극 탭 — GeoMAP·IBCSO·REMA·NPI 가 쓰는 3031 의 범위 격자(256·512 px)
ANTARCTIC = Grid("EPSG:3031", (-EXTENT_3031, EXTENT_3031), 2 * EXTENT_3031,
                 (-EXTENT_3031, -EXTENT_3031, EXTENT_3031, EXTENT_3031), lonlat_to_3031, tile=256)
#: Esri 남극 위성 — 서비스의 `tileInfo`(원점·줌 0 이 238810.813354 m/px·256 px, `map.js` 의 `esriAntarcticLayer`)
ESRI_ANTARCTIC = Grid("EPSG:3031@-33699550.99", (-33699550.99203, 33699551.01703), 256 * 238810.813354,
                      (-4524537.46, -4524537.92, 4524539.62, 4524539.16), lonlat_to_3031, tile=256)
GRIDS = {g.name: g for g in (MERCATOR, ANTARCTIC, ESRI_ANTARCTIC)}
