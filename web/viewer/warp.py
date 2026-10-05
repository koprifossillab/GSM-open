"""평면 격자(5179·5181·3031)로 잘린 타일을 3857 타일로 다시 편다 — 3D 가 쓴다.

3D(MapLibre, devlog 015)는 3857 래스터만 얹는다. 2D 의 OpenLayers 는 한반도 지질도의
5179(음영판·민판, 027·028)·5181(스캔판, 026) 격자와 남극 GeoMAP 의 3031 격자(018)를
그대로 받아 옮겨 그리지만 3D 는 그러지 못한다. 그래서 3D 가 부르는 3857 타일 한 장마다 **그 자리를 덮는 원본 타일을 모아
붙이고, Pillow 의 `MESH` 변환으로 편다.** numpy·GDAL 없이 된다(requirements-web.txt).

- 타일을 32 px 칸으로 나눠(256 px 이면 8 칸, 512 px 이면 16 칸) 칸마다 네 모서리를 원본
  픽셀로 되짚는다. 칸 안은 선형이다. 줌 14 에서도 휨의 어긋남이 한 픽셀 밑이고, 남극을
  줌 3 에서 보아도(한 칸이 경도 5.6°) 한 픽셀 남짓이다 (040)
- 원본 격자의 단계는 3857 타일의 땅 해상도보다 **한 단계 촘촘한 것 가운데 가장 거친 것**을
  고른다. 너무 촘촘하면 타일을 많이 받고, 거칠면 흐리다
- 수치 격자(IBCSO 표고, 051)는 `render_values` 로 편다 — 색이 아니라 값을 섞는다
- 이것은 문이 아니다 — 원본을 받는 것은 부르는 쪽이 넘긴 `fetch` 가 한다
  (음영판은 우리 디스크, 스캔판은 `phyloserver.get_scan_tile`, GeoMAP 은 2D 와 같은 타일 캐시)
"""
import io
import math

from PIL import Image

from . import crs, geomap, tilegrid

TILE = 256
#: 휘는 칸 한 변의 픽셀 — 256 px 타일이면 8 칸
MESH_PX = 32

#: 5181 — 카카오 격자의 좌표계(중부원점, GRS80, 북가산 500 000). crs.SYSTEMS 에는 없다
_TM_5181 = ("5181", crs.GRS80, 38, 127, 1.0, 200000, 500000, False)


def to_5179(lat: float, lon: float) -> tuple:
    return crs.from_latlon("5179", lat, lon)


def to_5181(lat: float, lon: float) -> tuple:
    return crs._ll_to_tm(lat, lon, _TM_5181)


class Grid:
    """원본 격자 하나.

    levels      고를 수 있는 단계들
    res(l)      단계 l 의 한 픽셀(m)
    origin(l)   단계 l 의 왼쪽 위 (동, 북) — 타일 번호는 여기서 오른쪽·아래로 센다
    size        타일 한 변의 픽셀
    project     (위도, 경도) → (동, 북)
    fetch(l, x, y)  타일 한 장(그림 바이트). 없으면(바다) None
    """

    def __init__(self, levels, res, origin, project, fetch, size=256, valid=None):
        self.levels, self.res, self.origin = list(levels), res, origin
        self.project, self.fetch, self.size = project, fetch, size
        self.valid = valid or (lambda level, x, y: True)

    def pick(self, meters_per_px: float):
        """3857 타일의 땅 해상도에 맞는 단계 — 그보다 촘촘한 것 가운데 가장 거친 것."""
        finer = [l for l in self.levels if self.res(l) <= meters_per_px]
        if finer:
            return max(finer, key=self.res)
        return min(self.levels, key=self.res)


def _lonlat(z: int, x: int, y: int, px: float, py: float, size: int = TILE) -> tuple:
    """3857 타일 (z, x, y) 안의 픽셀 (px, py) → (경도, 위도). 타일 한 변은 `size` px."""
    n = 2 ** z
    lon = (x + px / size) / n * 360.0 - 180.0
    merc = math.pi * (1 - 2 * (y + py / size) / n)
    return lon, math.degrees(math.atan(math.sinh(merc)))


def south_of(z: int, y: int) -> float:
    """3857 타일 줄 y 의 남쪽 끝 위도."""
    return _lonlat(z, 0, y, 0, TILE)[1]


def _plan(grid: Grid, z: int, x: int, y: int, size: int):
    """3857 타일 한 장을 펴는 채비 — (단계, 원본 타일 네모, 칸마다의 원본 픽셀 네모). 너무 멀면 None."""
    # 칸의 꼭짓점을 원본 좌표로
    cells = max(1, size // MESH_PX)
    step = size / cells
    corners = {}
    for i in range(cells + 1):
        for j in range(cells + 1):
            lon, lat = _lonlat(z, x, y, i * step, j * step, size)
            corners[i, j] = grid.project(lat, lon)
    # 땅 해상도 — 타일 가운데 위도에서
    _, mid_lat = _lonlat(z, x, y, size / 2, size / 2, size)
    meters = tilegrid.resolution(z) * 512 / size * math.cos(math.radians(mid_lat))   # tilegrid 는 512 px 기준
    level = grid.pick(meters)
    res, (ox, oy), span = grid.res(level), grid.origin(level), grid.size * grid.res(level)

    xs = [c[0] for c in corners.values()]
    ys = [c[1] for c in corners.values()]
    tx0, tx1 = int((min(xs) - ox) // span), int((max(xs) - ox) // span)
    ty0, ty1 = int((oy - max(ys)) // span), int((oy - min(ys)) // span)
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 36:
        return None                    # 너무 멀리서 본다 — 원본을 수십 장 모으지 않는다

    left, top = ox + tx0 * span, oy - ty0 * span

    def src(key):
        e, n = corners[key]
        return (e - left) / res, (top - n) / res

    mesh = []
    for i in range(cells):
        for j in range(cells):
            box = (round(i * step), round(j * step), round((i + 1) * step), round((j + 1) * step))
            # QUAD 의 차례 — 왼쪽 위, 왼쪽 아래, 오른쪽 아래, 오른쪽 위
            quad = src((i, j)) + src((i, j + 1)) + src((i + 1, j + 1)) + src((i + 1, j))
            mesh.append((box, quad))
    return level, (tx0, tx1, ty0, ty1), mesh


def render(grid: Grid, z: int, x: int, y: int, size: int = TILE):
    """3857 타일 한 장(PNG 바이트, 한 변 `size` px). 원본이 하나도 걸리지 않으면 None."""
    plan = _plan(grid, z, x, y, size)
    if plan is None:
        return None
    level, (tx0, tx1, ty0, ty1), mesh = plan
    mosaic = Image.new("RGBA", ((tx1 - tx0 + 1) * grid.size, (ty1 - ty0 + 1) * grid.size), (0, 0, 0, 0))
    got = False
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            if not grid.valid(level, tx, ty):
                continue
            data = grid.fetch(level, tx, ty)
            if not data:
                continue
            piece = Image.open(io.BytesIO(data)).convert("RGBA")
            mosaic.paste(piece, ((tx - tx0) * grid.size, (ty - ty0) * grid.size))
            got = True
    if not got:
        return None
    out = mosaic.transform((size, size), Image.MESH, mesh, resample=Image.BILINEAR)
    if not out.getbbox():
        return None
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_values(grid: Grid, z: int, x: int, y: int, decode, size: int = TILE):
    """수치 격자를 3857 로 편다 — (값 F, 채움 F) 한 벌. 원본이 하나도 걸리지 않으면 None.

    `decode(바이트)` 가 원본 타일 한 장을 (값, 채움)으로 푼다. **섞는 것은 값이다** — 색 타일처럼
    Terrarium 을 띠마다 섞으면 값이 튄다. 빈 곳이 섞인 픽셀은 채움이 1 보다 작아 부르는 쪽이
    가려 쓴다(051)."""
    plan = _plan(grid, z, x, y, size)
    if plan is None:
        return None
    level, (tx0, tx1, ty0, ty1), mesh = plan
    shape = ((tx1 - tx0 + 1) * grid.size, (ty1 - ty0 + 1) * grid.size)
    value, fill = Image.new("F", shape, 0.0), Image.new("F", shape, 0.0)
    got = False
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            if not grid.valid(level, tx, ty):
                continue
            data = grid.fetch(level, tx, ty)
            if not data:
                continue
            v, f = decode(data)
            at = ((tx - tx0) * grid.size, (ty - ty0) * grid.size)
            value.paste(v, at)
            fill.paste(f, at)
            got = True
    if not got:
        return None
    return (value.transform((size, size), Image.MESH, mesh, resample=Image.BILINEAR),
            fill.transform((size, size), Image.MESH, mesh, resample=Image.BILINEAR))


# ── 원본 격자 셋 ────────────────────────────────────────────────────

def peninsula_grid(sheet) -> Grid:
    """음영판·민판(027·028) — 우리가 잘라 둔 5179 타일. 원점은 범위의 왼쪽 위다."""
    x0, _, _, y1 = sheet.extent
    return Grid(levels=range(sheet.max_zoom + 1), res=sheet.resolution,
                origin=lambda level: (x0, y1), project=to_5179,
                fetch=sheet.read_tile, size=TILE, valid=sheet.valid_tile)


def kakao_grid(levels, origin, top, fetch_tile) -> Grid:
    """스캔판(026) — phyloserver 의 카카오 격자(5181). 레벨 L 의 한 픽셀은 2^(L-3) m 이고
    **번호를 아래에서 위로 센다.** 여기서는 위에서 아래로 센 번호를 받아 뒤집어 넘긴다."""
    lo, hi = levels
    ox, oy = origin
    height = top[1] * 256 * 2 ** (hi - 3)           # 격자 전체의 높이(m) — 레벨과 상관없다

    def rows(level):
        return top[1] * 2 ** (hi - level)

    def fetch(level, x, y):
        return fetch_tile(level, x, rows(level) - 1 - y)

    def valid(level, x, y):
        return 0 <= x < top[0] * 2 ** (hi - level) and 0 <= y < rows(level)

    return Grid(levels=range(lo, hi + 1), res=lambda level: 2.0 ** (level - 3),
                origin=lambda level: (ox, oy + height), project=to_5181,
                fetch=fetch, size=256, valid=valid)


def geomap_grid(fetch_tile) -> Grid:
    """남극 GeoMAP(018) — 우리가 그리는 3031 타일. 격자는 `geomap.py` 머리글의 것 그대로다.
    `fetch_tile(z, x, y)` 는 2D 가 받는 256 px 타일과 같은 것을 준다 — 캐시를 함께 쓴다."""
    return Grid(levels=range(geomap.MAX_ZOOM + 1), res=geomap.resolution,
                origin=lambda level: (geomap.ORIGIN_X, geomap.ORIGIN_Y),
                project=lambda lat, lon: geomap.lonlat_to_3031(lon, lat),
                fetch=fetch_tile, size=geomap.TILE, valid=geomap.valid_tile)


def polar_grid(fetch_tile, max_zoom: int, valid) -> Grid:
    """우리가 GeoMAP 격자(3031, 256 px)로 잘라 둔 남극 판 — IBCSO 자료 출처(TID)·ADMAP 자력 이상 (wetherilli 335).
    `fetch_tile(z, x, y)` 는 잘라 둔 파일(PNG·WebP), 없으면 None"""
    return Grid(levels=range(max_zoom + 1), res=geomap.resolution,
                origin=lambda level: (geomap.ORIGIN_X, geomap.ORIGIN_Y),
                project=lambda lat, lon: geomap.lonlat_to_3031(lon, lat),
                fetch=fetch_tile, size=geomap.TILE, valid=valid)


def ibcso_grid(sheet) -> Grid:
    """남극 해저·빙저 지형 IBCSO(047·051) 의 3D 배경 — 원본의 9354 격자 그대로 잘라 둔 WebP."""
    from . import ibcso
    half = ibcso.SOURCE_HALF
    return Grid(levels=range(ibcso.DEM_MAX_LEVEL + 1), res=ibcso.dem_res,
                origin=lambda level: (-half, half), project=ibcso.to_9354,
                fetch=sheet.read_wide, size=ibcso.TILE, valid=ibcso.dem_valid)


def ibcso_dem_grid(sheet) -> Grid:
    """IBCSO 수치 격자(051) — 원본의 9354 격자 그대로 잘라 둔 16 비트 타일."""
    from . import ibcso
    half = ibcso.SOURCE_HALF
    return Grid(levels=range(ibcso.DEM_MAX_LEVEL + 1), res=ibcso.dem_res,
                origin=lambda level: (-half, half), project=ibcso.to_9354,
                fetch=sheet.read_tile, size=ibcso.TILE, valid=ibcso.dem_valid)
