"""남극 지질도 — SCAR GeoMAP v2022-08 을 **우리가 그린다** (devlog 018).

`kigam.py`·`geus.py` 와 나란한 문이지만 **바깥으로 나가지 않는다.** 대륙 전체를
공개로 여는 지도 서비스가 없어서(devlog 016) GNS Science 가 배포하는 GeoPackage
파일을 우리 디스크에 두고 여기서 읽는다. 그래서 `requests` 도 없다.

**공간 라이브러리를 쓰지 않는다.** GDAL·shapely 를 들이면 web 이미지가 200 MB
대에서 몇 배로 붇는다(requirements-web.txt 머리글). 필요한 것은 넷뿐이라
표준 라이브러리와 Pillow 로 한다.

- GeoPackage 는 SQLite 다 — `sqlite3` 로 연다. 공간 색인(`rtree_<표>_geom`)도
  SQLite 의 R*Tree 라 그대로 쓴다
- 기하는 GeoPackage WKB 다 — `parse_geometry()` 가 `struct` 로 푼다
- 타일은 Pillow `ImageDraw` 로 칠한다. 색은 GNS 가 딸려 준 QGIS 스타일에서
  뽑아 둔 `data/geomap_styles.json` 이다 (`manage.py geomap_styles`)
- 속성은 R*Tree 로 후보를 추리고 점-다각형 판정(짝홀 규칙)을 파이썬으로 한다

좌표는 모두 **EPSG:3031**(남극 평사도법, WGS84, 표준위도 71°S)이다. 타일 격자는
화면 쪽과 약속한 것이라 **바꾸지 않는다** — 바꾸면 받아둔 타일이 다 어긋난다.

    원점(왼쪽 위)  (-3333134.0276, 3333134.0276)
    z0 해상도     6666268.0552 / 256  (타일 한 장이 대륙 전체)
    한 줌 오를 때마다 해상도가 반으로, y 는 위에서 아래로

자료: SCAR GeoMAP v2022-08, GNS Science, CC-BY 4.0, doi:10.1594/PANGAEA.951482.
"""
import io
import json
import logging
import math
import re
import sqlite3
import struct
import threading
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageChops, ImageDraw, ImageFont

log = logging.getLogger(__name__)

#: 화면이 레이어 곁에 적는 출처. CC-BY 라 반드시 보여야 한다.
ATTRIBUTION = "SCAR GeoMAP v2022-08 (GNS Science, CC-BY 4.0)"

# ── 타일 격자 (EPSG:3031) ─────────────────────────────────────────────

ORIGIN_X, ORIGIN_Y = -3333134.0276, 3333134.0276
EXTENT = 6666268.0552
TILE = 256
MAX_ZOOM = 18

#: 그리는 법이 바뀌면 올린다. 타일 캐시의 열쇠에 들어가서, 올리면 옛 그림을
#: 다시 쓰지 않는다 — 캐시는 스스로 지우지 않으므로(tilecache.py) 이것이 없으면
#: 고친 그림이 3 년 동안 안 보인다.
RENDERER = "1"


def resolution(z: int) -> float:
    return EXTENT / TILE / (2 ** z)


def tile_bbox(z: int, x: int, y: int) -> tuple:
    """타일 `(z, x, y)` 의 범위 `(minx, miny, maxx, maxy)`. y 는 위에서 아래로."""
    span = EXTENT / (2 ** z)
    min_x = ORIGIN_X + x * span
    max_y = ORIGIN_Y - y * span
    return (min_x, max_y - span, min_x + span, max_y)


def tile_of(z: int, px: float, py: float) -> tuple:
    """3031 좌표 한 점이 드는 타일 `(x, y)`."""
    span = EXTENT / (2 ** z)
    return int((px - ORIGIN_X) // span), int((ORIGIN_Y - py) // span)


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


# ── 남극 평사도법 (EPSG:3031) ─────────────────────────────────────────
#
# 속성 요청이 3857·4326 으로 와도 받으려고 둔다. Snyder(1987) 21-33~21-40 의
# 극 평사도법, 표준위도 71°S. pyproj 없이 — crs.py 와 같은 까닭이다.

_A = 6378137.0
_F = 1 / 298.257223563
_E = math.sqrt(_F * (2 - _F))
_LAT_TS = math.radians(71.0)


def _t(phi):
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - _E * s) / (1 + _E * s)) ** (_E / 2)


_MC = math.cos(_LAT_TS) / math.sqrt(1 - (_E * math.sin(_LAT_TS)) ** 2)
_TC = _t(_LAT_TS)


def lonlat_to_3031(lon: float, lat: float) -> tuple:
    """위경도 → EPSG:3031. 남반구의 식을 북반구 꼴로 뒤집어 쓴다."""
    phi = math.radians(-lat)
    lam = math.radians(-lon)
    rho = _A * _MC * _t(phi) / _TC
    return (-rho * math.sin(lam), rho * math.cos(lam))


def xy3031_to_lonlat(x: float, y: float) -> tuple:
    rho = math.hypot(x, y)
    t = rho * _TC / (_A * _MC)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(10):
        s = _E * math.sin(phi)
        nxt = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (_E / 2))
        if abs(nxt - phi) < 1e-12:
            phi = nxt
            break
        phi = nxt
    lon = math.degrees(math.atan2(x, y)) if rho else 0.0
    return (lon, -math.degrees(phi))


def _from_3857(x: float, y: float) -> tuple:
    half = 20037508.342789244
    lon = x / half * 180
    lat = math.degrees(2 * math.atan(math.exp(y / half * math.pi)) - math.pi / 2)
    return lon, lat


def to_3031(crs: str, a: float, b: float, version: str = "1.3.0") -> tuple:
    """요청의 좌표계에서 3031 로. 4326 은 WMS 1.3.0 이면 위도가 먼저다."""
    code = (crs or "").upper()
    if code in ("EPSG:3031",):
        return a, b
    if code in ("EPSG:3857", "EPSG:900913"):
        return lonlat_to_3031(*_from_3857(a, b))
    if code == "CRS:84":
        return lonlat_to_3031(a, b)
    if code == "EPSG:4326":
        return lonlat_to_3031(b, a) if version.startswith("1.3") else lonlat_to_3031(a, b)
    raise GeomapError(f"모르는 좌표계다: {crs}")


# ── GeoPackage WKB ────────────────────────────────────────────────────

class GeomapError(RuntimeError):
    pass


_ENVELOPE = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def parse_geometry(blob: bytes):
    """GeoPackage 기하 → `(갈래, 조각들)`.

    - `"point"`   조각은 `(x, y)`
    - `"line"`    조각은 납작한 좌표 튜플 `(x0, y0, x1, y1, …)`
    - `"polygon"` 조각은 고리들의 목록 — 첫째가 바깥, 나머지가 구멍.
      고리 하나는 납작한 좌표 튜플이다

    멀티는 조각이 여럿일 뿐이다. Z·M 은 버린다. 빈 기하는 `(None, [])`.
    """
    if not blob or blob[:2] != b"GP":
        raise GeomapError("GeoPackage 기하가 아니다")
    flags = blob[3]
    if flags & 0b10000:                         # 빈 기하
        return None, []
    env = _ENVELOPE.get((flags >> 1) & 0b111)
    if env is None:
        raise GeomapError("모르는 envelope 이다")
    kind, parts, _ = _wkb(blob, 8 + env)
    return kind, parts


def _wkb(buf, off):
    order = "<" if buf[off] == 1 else ">"
    (code,) = struct.unpack_from(order + "I", buf, off + 1)
    off += 5
    # ISO(1000·2000·3000 을 더한다)와 EWKB(높은 비트) 둘 다 받는다
    dims = 2
    if code & 0x80000000:
        dims += 1
    if code & 0x40000000:
        dims += 1
    if code & 0x20000000:                       # EWKB 의 SRID
        off += 4
    code &= 0x0FFFFFFF
    iso = code // 1000
    code %= 1000
    dims += {0: 0, 1: 1, 2: 1, 3: 2}[iso]

    if code == 1:
        vals = struct.unpack_from(f"{order}{dims}d", buf, off)
        return "point", [vals[:2]], off + 8 * dims
    if code == 2:
        ring, off = _points(buf, off, order, dims)
        return "line", [ring], off
    if code == 3:
        rings, off = _rings(buf, off, order, dims)
        return "polygon", [rings], off
    if code in (4, 5, 6, 7):
        (n,) = struct.unpack_from(order + "I", buf, off)
        off += 4
        kind, parts = None, []
        for _ in range(n):
            k, p, off = _wkb(buf, off)
            kind = kind or k
            parts.extend(p)
        return kind or {4: "point", 5: "line", 6: "polygon"}.get(code), parts, off
    raise GeomapError(f"모르는 기하 갈래다: {code}")


def _points(buf, off, order, dims):
    (n,) = struct.unpack_from(order + "I", buf, off)
    off += 4
    vals = struct.unpack_from(f"{order}{n * dims}d", buf, off)
    off += 8 * n * dims
    if dims != 2:
        flat = []
        for i in range(0, n * dims, dims):
            flat.append(vals[i])
            flat.append(vals[i + 1])
        vals = tuple(flat)
    return vals, off


def _rings(buf, off, order, dims):
    (n,) = struct.unpack_from(order + "I", buf, off)
    off += 4
    rings = []
    for _ in range(n):
        ring, off = _points(buf, off, order, dims)
        rings.append(ring)
    return rings, off


# ── 점과 기하 ─────────────────────────────────────────────────────────

def ring_contains(ring, x: float, y: float) -> bool:
    """짝홀 규칙. 고리는 납작한 좌표 튜플이다."""
    inside = False
    n = len(ring)
    if n < 6:
        return False
    x1, y1 = ring[n - 2], ring[n - 1]
    for i in range(0, n, 2):
        x2, y2 = ring[i], ring[i + 1]
        if (y2 > y) != (y1 > y):
            if x < (x1 - x2) * (y - y2) / (y1 - y2) + x2:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def polygon_contains(rings, x: float, y: float) -> bool:
    """바깥 고리 안이고 어느 구멍에도 들지 않는다."""
    if not rings or not ring_contains(rings[0], x, y):
        return False
    return not any(ring_contains(hole, x, y) for hole in rings[1:])


def distance_to_path(flat, x: float, y: float) -> float:
    """점에서 꺾은선(납작한 좌표)까지의 가장 짧은 거리."""
    best = math.inf
    for i in range(0, len(flat) - 2, 2):
        ax, ay, bx, by = flat[i], flat[i + 1], flat[i + 2], flat[i + 3]
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / seg))
        d = math.hypot(ax + t * dx - x, ay + t * dy - y)
        if d < best:
            best = d
    return best


def distance(kind, parts, x: float, y: float) -> float:
    """기하까지의 거리. 면 안이면 0."""
    if kind == "polygon":
        if any(polygon_contains(rings, x, y) for rings in parts):
            return 0.0
        return min((distance_to_path(r, x, y) for rings in parts for r in rings), default=math.inf)
    if kind == "line":
        return min((distance_to_path(p, x, y) for p in parts), default=math.inf)
    if kind == "point":
        return min((math.hypot(px - x, py - y) for px, py in parts), default=math.inf)
    return math.inf


# ── 자료 파일 ─────────────────────────────────────────────────────────

#: 표의 이름 앞머리. 판(v2022_08)이 뒤에 붙으므로 앞머리로 찾는다.
TABLE_PREFIX = {
    "units": "ATA_GeoMAP_geological_units",
    "faults": "ATA_GeoMAP_faults",
    "quality": "ATA_GeoMAP_quality",
    "sources": "ATA_GeoMAP_sources",
}
_FILE_GLOB = "ATA_SCAR_GeoMAP_Geology_*.gpkg"
_NAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_local = threading.local()
_lock = threading.Lock()
_meta_cache = {}


def data_file():
    """GeoMAP 파일. 판이 여럿이면 이름이 가장 뒤인 것(새 판). 없으면 None."""
    root = Path(settings.GEOMAP_DIR) if settings.GEOMAP_DIR else None
    if root is None or not root.is_dir():
        return None
    found = sorted(root.glob(_FILE_GLOB))
    return found[-1] if found else None


def available() -> bool:
    return data_file() is not None


def data_version() -> str:
    """`ATA_SCAR_GeoMAP_Geology_v2022_08.gpkg` → `2022-08`."""
    path = data_file()
    m = re.search(r"v(\d{4})_(\d{2})", path.name if path else "")
    return f"{m.group(1)}-{m.group(2)}" if m else (path.stem if path else "")


def _connect():
    path = data_file()
    if path is None:
        raise GeomapError("GeoMAP 파일이 없다")
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "path", None) == path:
        return conn
    # 읽기만 한다. immutable 은 잠금 파일(-journal)을 찾지 않게 한다 —
    # 운영에서는 읽기 전용으로 붙인 자리라 잠금을 만들 수 없다
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    _local.conn, _local.path = conn, path
    return conn


def _meta(conn, path):
    """표 이름·기하 열·범위. 파일마다 한 번 읽는다."""
    with _lock:
        if path in _meta_cache:
            return _meta_cache[path]
    tables = {}
    rows = conn.execute(
        "SELECT c.table_name, g.column_name, c.min_x, c.min_y, c.max_x, c.max_y "
        "FROM gpkg_contents c JOIN gpkg_geometry_columns g ON g.table_name = c.table_name "
        "WHERE c.data_type = 'features'").fetchall()
    for name, geom, *bounds in rows:
        for role, prefix in TABLE_PREFIX.items():
            if name.startswith(prefix) and _NAME_OK.match(name) and _NAME_OK.match(geom):
                tables[role] = {"table": name, "geom": geom, "rtree": f"rtree_{name}_{geom}",
                                "bounds": tuple(bounds)}
    with _lock:
        _meta_cache[path] = tables
    return tables


def _table(role: str):
    conn = _connect()
    meta = _meta(conn, data_file())
    if role not in meta:
        raise GeomapError(f"GeoMAP 파일에 {role} 표가 없다")
    return conn, meta[role]


# ── 스타일 ────────────────────────────────────────────────────────────

class Style:
    """`data/geomap_styles.json` 의 스타일 하나. 규칙은 위에서부터 처음 맞는 것."""

    def __init__(self, spec: dict):
        self.table = spec["table"]
        self.kind = spec["kind"]
        self.fields = [f for f in spec["fields"] if _NAME_OK.match(f)]
        self.rules = spec["rules"]
        self._memo = {}

    def pick(self, values: tuple):
        """열 값들 → 규칙 번호. 없으면 None. 같은 값은 다시 셈하지 않는다."""
        if values in self._memo:
            return self._memo[values]
        row = dict(zip(self.fields, values))
        found = None
        for index, rule in enumerate(self.rules):
            if any(all(_same(row.get(f), v) for f, v in cond.items()) for cond in rule["when"]):
                found = index
                break
        self._memo[values] = found
        return found


def _same(have, want) -> bool:
    if want is None:
        # `IS NULL`. gpkg 로 옮기며 NULL 이 빈 글자로 바뀐 열이 있다 (LITHCODE)
        return have is None or have == ""
    if isinstance(want, (int, float)) and not isinstance(have, str):
        return have is not None and float(have) == float(want)
    return str(have) == str(want)


_styles = None


def styles() -> dict:
    global _styles
    if _styles is None:
        data = json.loads(Path(settings.GEOMAP_STYLES).read_text(encoding="utf-8"))
        _styles = {name: Style(spec) for name, spec in data["styles"].items()}
    return _styles


#: 레이어 → 스타일. 레이어 이름은 카탈로그(`data/geomap_layers.json`)와 같다.
LAYERS = {
    "geomap_simple_geology": "simple_geology",
    "geomap_simple_lithology": "simple_lithology",
    "geomap_chronostratigraphic": "chronostratigraphic",
    "geomap_faults": "faults",
    "geomap_quality": "quality",
    # 암층 — GNS 의 무늬(빗금·점 무늬)까지 그린다 (`_pattern_image`)
    "geomap_lithostratigraphic": "lithostratigraphic",
}


def style_of(layer: str) -> Style:
    try:
        return styles()[LAYERS[layer]]
    except KeyError:
        raise GeomapError(f"모르는 레이어다: {layer}") from None


# ── 그리기 ────────────────────────────────────────────────────────────

#: 이보다 작은(픽셀) 것은 기하를 풀지 않고 점 하나로 찍는다. 저줌에서 대륙
#: 전체의 노두 9 만 개를 다 풀면 느리다 — 어차피 한 픽셀에 든다.
DOT_PX = 1.5
#: 몇 배로 크게 그려 줄이나. 2 면 가장자리가 부드러워지고 시간은 거의 그대로다
#: (시간은 꼭짓점을 푸는 파이썬이 먹고, 칠하는 것은 Pillow 의 C 가 한다)
SUPERSAMPLE = 2
#: 저줌에서 고리를 성기게 읽는다 — 이 픽셀 길이에 꼭짓점 하나면 충분하다.
VERTEX_PX = 0.75


def render(layer: str, bbox: tuple, width: int, height: int) -> bytes:
    """범위 `bbox`(3031) 를 `width × height` 의 투명 PNG 로."""
    img = render_image(layer, bbox, width, height)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def render_image(layer: str, bbox: tuple, width: int, height: int, ss: int = None) -> Image.Image:
    """`ss` 배로 크게 그려 줄인다 — ImageDraw 는 가장자리를 부드럽게 하지 않는다."""
    ss = SUPERSAMPLE if ss is None else max(1, ss)
    out_size = (width, height)
    width, height = width * ss, height * ss
    style = style_of(layer)
    conn, meta = _table(style.table)
    min_x, min_y, max_x, max_y = bbox
    kx = width / (max_x - min_x)
    ky = height / (max_y - min_y)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # 범위 밖이면 묻지도 않는다 — 바다의 타일이 대부분이다
    b = meta["bounds"]
    if None not in b and (max_x < b[0] or min_x > b[2] or max_y < b[1] or min_y > b[3]):
        return img.resize(out_size, Image.Resampling.BOX) if ss > 1 else img

    draw = ImageDraw.Draw(img)
    pad = 3 * ss / kx                                # 테두리·선 굵기만큼 넉넉히
    cols = ", ".join(f't."{f}"' for f in style.fields)
    rows = conn.execute(
        f'SELECT r.id, r.minx, r.maxx, r.miny, r.maxy{", " + cols if cols else ""} '
        f'FROM "{meta["rtree"]}" r JOIN "{meta["table"]}" t ON t.fid = r.id '
        f"WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ? ORDER BY r.id",
        (min_x - pad, max_x + pad, min_y - pad, max_y + pad)).fetchall()

    # 무늬는 지도 전역의 픽셀 자리에 맞춘다 — 이웃 타일에서 빗금·점이 끊기지 않게.
    # 규칙마다 이 그림 크기의 무늬를 한 번만 만든다
    origin = (min_x * kx, -max_y * ky)
    patterns = {}

    def paint(index):
        if index not in patterns:
            patterns[index] = _pattern_image(style.rules[index], width, height, origin, ss)
        return patterns[index]

    big = []
    for fid, x0, x1, y0, y1, *values in rows:
        index = style.pick(tuple(values))
        if index is None:
            continue
        rule = style.rules[index]
        wpx, hpx = (x1 - x0) * kx, (y1 - y0) * ky
        if style.kind == "fill" and wpx < DOT_PX * ss and hpx < DOT_PX * ss:
            color = _rgba(rule.get("fill") or rule.get("outline") or _pattern_color(rule))
            if color:
                # 한 (최종) 픽셀을 꽉 채운다 — 줄였을 때 흐려지지 않게
                cx, cy = ((x0 + x1) / 2 - min_x) * kx, (max_y - (y0 + y1) / 2) * ky
                draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=color)
            continue
        big.append((fid, index, max(wpx, hpx)))

    geoms = _fetch_geoms(conn, meta, [fid for fid, _, _ in big])
    tr = (min_x, max_y, kx, ky)
    for fid, index, size_px in big:
        blob = geoms.get(fid)
        if not blob:
            continue
        kind, parts = parse_geometry(blob)
        rule = style.rules[index]
        if kind == "polygon":
            for rings in parts:
                _fill_polygon(img, draw, rings, rule, tr, size_px, ss, paint=lambda i=index: paint(i))
        elif kind == "line":
            for flat in parts:
                for run in _clip_runs(_to_px(flat, tr, size_px), width, height, 8 * ss):
                    _stroke(draw, run, rule.get("strokes") or [], ss)
    return img.resize(out_size, Image.Resampling.BOX) if ss > 1 else img


def _fetch_geoms(conn, meta, fids) -> dict:
    out = {}
    for i in range(0, len(fids), 500):
        chunk = fids[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for fid, blob in conn.execute(
                f'SELECT fid, "{meta["geom"]}" FROM "{meta["table"]}" WHERE fid IN ({marks})', chunk):
            out[fid] = blob
    return out


def _rgba(value):
    return tuple(value) if value else None


def _to_px(flat, tr, size_px):
    """3031 좌표 → 픽셀 `[(x, y), …]`. 작은 것은 꼭짓점을 성기게 읽는다."""
    min_x, max_y, kx, ky = tr
    n = len(flat) // 2
    step = 1
    if n > 8:
        need = max(4, int(size_px * 4 / VERTEX_PX))   # 둘레 ≈ 4 × 크기
        if n > need:
            step = n // need
    xs = flat[0::2 * step] if step > 1 else flat[0::2]
    ys = flat[1::2 * step] if step > 1 else flat[1::2]
    pts = [((x - min_x) * kx, (max_y - y) * ky) for x, y in zip(xs, ys)]
    if step > 1:
        pts.append(((flat[-2] - min_x) * kx, (max_y - flat[-1]) * ky))
    return pts


def _clip_runs(pts, width, height, margin):
    """타일 둘레에 걸친 토막만 이어서 돌려준다. 긴 단층의 대부분은 타일 밖이다.
    (끊긴 자리에서 점선의 박자가 새로 시작하는 것은 받아들인다.)"""
    lo_x, lo_y, hi_x, hi_y = -margin, -margin, width + margin, height + margin
    run = []
    for a, b in zip(pts, pts[1:]):
        if (max(a[0], b[0]) < lo_x or min(a[0], b[0]) > hi_x
                or max(a[1], b[1]) < lo_y or min(a[1], b[1]) > hi_y):
            if len(run) >= 2:
                yield run
            run = []
            continue
        if not run:
            run = [a]
        run.append(b)
    if len(run) >= 2:
        yield run


def _fill_polygon(img, draw, rings, rule, tr, size_px, ss=1, paint=None):
    """`paint` 는 이 규칙의 무늬 그림(그림 전체 크기)을 주는 손이다. 무늬가 있으면
    바탕 → 무늬 → 외곽선 차례로 가림막에 칠한다."""
    fill = _rgba(rule.get("fill"))
    outline = _rgba(rule.get("outline"))
    if rule.get("pattern") not in (None, "solid"):
        # 빗금 무늬(diagonal_x 등)는 그리지 않고 반투명 면으로 대신한다
        fill = fill[:3] + (110,) if fill else None
    outer = _to_px(rings[0], tr, size_px)
    if len(outer) < 3:
        return
    # 구멍 가운데 한 픽셀이 넘는 것만 판다
    holes = []
    for hole in rings[1:]:
        xs, ys = hole[0::2], hole[1::2]
        hsize = max(max(xs) - min(xs), max(ys) - min(ys)) * tr[2]
        if hsize >= 1.0:
            holes.append(_to_px(hole, tr, hsize))
    width = max(1, int(round((rule.get("width") or 1) * ss)))
    patterned = paint is not None and (rule.get("hatch") or rule.get("dots"))
    if not holes and not patterned:
        draw.polygon(outer, fill=fill, outline=outline if outline != fill or width > 1 else fill,
                     width=width)
        return
    # 구멍이 있다: 이 다각형만의 가림막을 만들어 칠한다. ImageDraw 는 구멍을 모른다
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    x0, y0 = max(0, int(min(xs)) - 1), max(0, int(min(ys)) - 1)
    x1, y1 = min(img.width, int(max(xs)) + 2), min(img.height, int(max(ys)) + 2)
    if x1 <= x0 or y1 <= y0:
        return
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(x - x0, y - y0) for x, y in outer], fill=255)
    for hole in holes:
        md.polygon([(x - x0, y - y0) for x, y in hole], fill=0)
    if fill:
        img.paste(Image.new("RGBA", mask.size, fill), (x0, y0), mask)
    pattern = paint() if patterned else None
    if pattern is not None:
        piece = pattern.crop((x0, y0, x1, y1))
        piece.putalpha(ImageChops.multiply(piece.getchannel("A"), mask))
        img.alpha_composite(piece, (x0, y0))
    if outline:
        for ring in [outer] + holes:
            draw.line(ring + ring[:1], fill=outline, width=width)


def _pattern_color(rule):
    for item in (rule.get("hatch") or []) + (rule.get("dots") or []):
        return item.get("color")
    return None


def _pattern_image(rule, width, height, origin=(0.0, 0.0), ss=1):
    """규칙의 무늬(빗금·점 무늬)를 `width × height` 투명 그림에 깐다. 없으면 None.

    `origin` 은 이 그림 왼쪽 위의 **전역 픽셀 자리**다(3031 미터 × 픽셀/미터, y 는
    아래로). 무늬를 그 자리에 맞추므로 이웃 타일의 무늬가 이어진다. 크기(간격·굵기·
    마커)는 스타일의 px 에 `ss` 를 곱한다 — QGIS 처럼 화면에서 늘 같은 크기다."""
    hatch, dots = rule.get("hatch") or [], rule.get("dots") or []
    if not hatch and not dots:
        return None
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    gx, gy = origin
    reach = width + height
    for h in hatch:
        spacing = max(1.0, h["spacing"] * ss)
        theta = math.radians(h.get("angle") or 0)
        dx, dy = math.cos(theta), -math.sin(theta)          # 선의 방향 (그림 좌표, y 아래로)
        nx, ny = -dy, dx                                    # 선에 수직
        base = nx * gx + ny * gy                           # 그림 원점의 전역 자리를 법선에 내린 것
        corners = [nx * x + ny * y for x, y in ((0, 0), (width, 0), (0, height), (width, height))]
        lo = math.floor((min(corners) + base) / spacing) - 1
        hi = math.ceil((max(corners) + base) / spacing) + 1
        color = _rgba(h.get("color"))
        lw = max(1, int(round((h.get("width") or 1) * ss)))
        for k in range(lo, hi + 1):
            c = k * spacing - base
            px, py = nx * c, ny * c                        # 그림 원점에서 이 선에 내린 발
            far = abs(c) + reach                           # 발에서 그림 끝까지 넉넉히
            draw.line([(px - dx * far, py - dy * far), (px + dx * far, py + dy * far)],
                      fill=color, width=lw)
    for d in dots:
        sx, sy = max(1.0, d["dx"] * ss), max(1.0, d["dy"] * ss)
        shift = (d.get("shift") or 0) * ss
        half = max(0.5, d["size"] * ss / 2)
        color, outline = _rgba(d.get("color")), _rgba(d.get("outline"))
        j0, j1 = math.floor(gy / sy) - 1, math.ceil((gy + height) / sy) + 1
        for j in range(j0, j1 + 1):
            cy = j * sy + sy / 2 - gy
            off = shift if j % 2 else 0.0                  # 줄마다 어긋난다
            i0 = math.floor((gx - off) / sx) - 1
            i1 = math.ceil((gx + width - off) / sx) + 1
            for i in range(i0, i1 + 1):
                cx = i * sx + sx / 2 + off - gx
                if d["marker"] == "half_square":
                    draw.rectangle((cx - half, cy - half, cx, cy + half), fill=color, outline=outline)
                elif d["marker"] == "square":
                    draw.rectangle((cx - half, cy - half, cx + half, cy + half), fill=color, outline=outline)
                else:
                    draw.ellipse((cx - half, cy - half, cx + half, cy + half), fill=color, outline=outline)
    return img


def _stroke(draw, pts, strokes, ss=1):
    if len(pts) < 2:
        return
    for s in strokes:
        color = _rgba(s.get("color"))
        width = max(1, int(round((s.get("width") or 1) * ss)))
        dash = [v * ss for v in s["dash"]] if s.get("dash") else None
        if not dash or not any(dash):
            draw.line(pts, fill=color, width=width, joint="curve" if width > 2 else None)
            continue
        for seg in _dashes(pts, dash):
            if len(seg) >= 2:
                draw.line(seg, fill=color, width=width)
            elif seg:
                draw.point(seg[0], fill=color)


def _dashes(pts, pattern):
    """꺾은선을 켜고 끄는 길이(`pattern`, 픽셀)로 자른 토막들."""
    pattern = [max(0.0, float(v)) for v in pattern]
    if sum(pattern) <= 0:
        return [pts]
    out, cur = [], [pts[0]]
    index, left, on = 0, pattern[0], True
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        pos = 0.0
        while seg - pos > left:                 # 이 토막 안에서 켜고 끄기가 바뀐다
            pos += left
            t = pos / seg
            p = (ax + (bx - ax) * t, ay + (by - ay) * t)
            if on:
                cur.append(p)
                out.append(cur)
                cur = []
            else:
                cur = [p]
            on = not on
            index = (index + 1) % len(pattern)
            left = pattern[index]
        left -= seg - pos
        if on:
            cur.append((bx, by))
    if on and cur:
        out.append(cur)
    return out


# ── 범례 ──────────────────────────────────────────────────────────────

LEGEND_MAX_W = 520


def legend(layer: str) -> bytes:
    """스타일의 규칙을 줄마다 견본 + 이름표로. 글자는 GNS 스타일의 영어 그대로다
    — 타일 안의 글자처럼 옮기지 않는다 (CLAUDE.md "영어판")."""
    style = style_of(layer)
    font = _font(11)
    bold = _font(11, bold=True)
    rows = []
    last_group = None
    for rule in style.rules:
        if rule.get("group") and rule["group"] != last_group:
            rows.append(("group", rule["group"]))
            last_group = rule["group"]
        rows.append(("rule", rule))
    line_h, pad, sw = 17, 6, 26
    # 이름표가 다 들어갈 만큼 넓게, 그래도 패널을 넘지 않게
    widest = max([font.getlength(r[1]["label"] or "") + sw + 18 if r[0] == "rule"
                  else bold.getlength(r[1]) for r in rows] + [200])
    width = int(min(LEGEND_MAX_W, widest + pad * 2))
    height = pad * 2 + line_h * len(rows) + 14
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    y = pad
    for what, item in rows:
        if what == "group":
            draw.text((pad, y + 2), item, fill=(40, 36, 32, 255), font=bold)
        else:
            box = (pad + 4, y + 3, pad + 4 + sw, y + line_h - 3)
            if style.kind == "fill":
                fill = _rgba(item.get("fill"))
                if item.get("pattern") not in (None, "solid") and fill:
                    fill = fill[:3] + (110,)
                draw.rectangle(box, fill=fill)
                swatch = _pattern_image(item, box[2] - box[0], box[3] - box[1])
                if swatch is not None:
                    img.alpha_composite(swatch, (box[0], box[1]))
                draw.rectangle(box, outline=_rgba(item.get("outline")) or (120, 120, 120, 255))
            else:
                mid = (box[1] + box[3]) / 2
                _stroke(draw, [(box[0], mid), (box[2], mid)], item.get("strokes") or [])
            label = item.get("label") or ""
            room = width - (box[2] + 8) - pad
            while label and font.getlength(label) > room:
                label = label[:-2] + "…"
            draw.text((box[2] + 8, y + 2), label, fill=(40, 36, 32, 255), font=font)
        y += line_h
    draw.text((pad, y + 2), ATTRIBUTION, fill=(110, 104, 96, 255), font=_font(9))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _font(size, bold=False):
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):              # FreeType 가 없는 Pillow
        return ImageFont.load_default()


# ── 속성 ──────────────────────────────────────────────────────────────

#: 팝업에 보일 열 → 한국어 이름. 영어는 `i18n.PROP_EN`. 여기 없는 열은 보이지 않는다.
#: 차례가 팝업의 차례다.
PROPS = {
    "units": (
        ("NAME", "지질 단위"),
        ("MAPSYMBOL", "지질기호"),
        ("DESCR", "설명"),
        ("LITHOLOGY", "암상"),
        ("SIMPDESC", "간추린 지질"),
        ("GEOLHIST", "지질시대"),
        ("_AGE", "연대 (Ma)"),
        ("POLYGTYPE", "노두 갈래"),
        ("STRATRANK", "층서 단위"),
        ("TECTPROV", "지체구조구"),
        ("REGION", "지역"),
        ("CONFIDENCE", "신뢰도"),
        ("OBSMETHOD", "관찰 방법"),
        ("POSACC_M", "위치 정확도 (m)"),
        ("_SCALE", "축척"),
        ("SOURCE", "출처"),
        ("_CITATION", "출처 문헌"),
    ),
    "faults": (
        ("NAME", "이름"),
        ("TYPENAME", "단층 갈래"),
        ("EXPOSURE", "노출"),
        ("ACCURACY", "위치 정확성"),
        ("MVTTYPE", "운동 갈래"),
        ("DIP_DEG", "경사 (°)"),
        ("DIPDIR_DEG", "경사 방향 (°)"),
        ("GEOLHIST", "지질시대"),
        ("DESCR", "설명"),
        ("CONFIDENCE", "신뢰도"),
        ("SOURCE", "출처"),
        ("_CITATION", "출처 문헌"),
    ),
    "quality": (
        ("QUALITY", "자료 품질 (1–5)"),
        ("OUTCROP", "노두"),
        ("COMMENTS", "설명"),
    ),
}
#: 모든 속성 끝에 붙는 자료 출처
DATASET_LABEL = "자료"
#: 값이 이것이면 없는 것으로 친다 — GeoSciML 의 "모른다" 표시들
_EMPTY = {"", "unknown", "Unknown", "missing", "?"}
#: 숫자 열의 "모른다". 단층의 경사·경사 방향은 모르면 99·999 로 적혀 있다
_UNKNOWN_NUMBER = {"DIP_DEG": (99,), "DIPDIR_DEG": (999,)}

#: 클릭 둘레 (픽셀). 저줌에서 노두는 한 점이라 정확히 누르기 어렵다
TOLERANCE_PX = 4


def get_feature_info(params: dict) -> dict:
    """WMS `GetFeatureInfo` 꼴의 변수 → `{"features": [{"id", "properties"}]}`.

    속성 이름은 이미 한국어다(`PROPS`). 뷰가 영어판이면 `PROP_EN` 으로 옮긴다.
    """
    layer = (params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
    style = style_of(layer)
    x, y, tol = click_point(params)
    return {"features": query(style.table, x, y, tol, layer=layer)}


def click_point(params: dict) -> tuple:
    """BBOX·WIDTH·HEIGHT·I·J·CRS → 3031 의 한 점과 둘레(m)."""
    try:
        bbox = [float(v) for v in str(params.get("bbox", "")).split(",")[:4]]
        width = float(params.get("width") or 0)
        height = float(params.get("height") or 0)
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError):
        raise GeomapError("속성을 물을 자리가 없다 (BBOX·WIDTH·HEIGHT·I·J)") from None
    if len(bbox) != 4 or width <= 0 or height <= 0:
        raise GeomapError("속성을 물을 자리가 없다 (BBOX·WIDTH·HEIGHT·I·J)")
    crs = params.get("crs") or params.get("srs") or "EPSG:3031"
    version = str(params.get("version") or ("1.3.0" if params.get("crs") else "1.1.1"))
    a0, b0, a1, b1 = bbox
    if crs.upper() == "EPSG:4326" and version.startswith("1.3"):
        # 1.3.0 의 4326 은 (위도, 경도) — 세로가 첫째 축이다
        lat = a1 - (j + 0.5) * (a1 - a0) / height
        lon = b0 + (i + 0.5) * (b1 - b0) / width
        p = to_3031(crs, lat, lon, version)
        q = to_3031(crs, lat, lon + (b1 - b0) / width, version)
    else:
        px = a0 + (i + 0.5) * (a1 - a0) / width
        py = b1 - (j + 0.5) * (b1 - b0) / height
        p = to_3031(crs, px, py, version)
        q = to_3031(crs, px + (a1 - a0) / width, py, version)
    per_px = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
    return p[0], p[1], per_px * TOLERANCE_PX


def query(role: str, x: float, y: float, tol: float, *, layer: str = "", limit: int = 3) -> list:
    """3031 의 한 점에 걸린 것들. 면 안이 먼저, 그다음 가까운 차례."""
    conn, meta = _table(role)
    cand = [r[0] for r in conn.execute(
        f'SELECT id FROM "{meta["rtree"]}" WHERE maxx >= ? AND minx <= ? AND maxy >= ? AND miny <= ?',
        (x - tol, x + tol, y - tol, y + tol))]
    if not cand:
        return []
    style = styles()[LAYERS[layer]] if layer in LAYERS else None
    cols = [c for c, _ in PROPS[role] if not c.startswith("_")]
    extra = ["ABSMIN_MA", "ABSMAX_MA", "RESSCALE", "Shape_Area"] if role == "units" else []
    have = {r[1] for r in conn.execute(f'PRAGMA table_info("{meta["table"]}")')}
    names = [n for n in dict.fromkeys(cols + extra + (style.fields if style else []))
             if _NAME_OK.match(n) and n in have]
    select = ", ".join(['fid', f'"{meta["geom"]}"'] + [f'"{n}"' for n in names])
    rows = []
    for i in range(0, len(cand), 500):
        chunk = cand[i:i + 500]
        rows += conn.execute(f'SELECT {select} FROM "{meta["table"]}" '
                             f'WHERE fid IN ({",".join("?" * len(chunk))})', chunk).fetchall()

    hits = []
    for fid, blob, *values in rows:
        row = dict(zip(names, values))
        if style is not None and style.pick(tuple(row.get(f) for f in style.fields)) is None:
            continue                            # 이 레이어에 그려지지 않는 것
        kind, parts = parse_geometry(blob)
        d = distance(kind, parts, x, y)
        if d <= tol:
            hits.append((d, row.get("Shape_Area") or 0, fid, row))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [{"id": f"{meta['table']}.{fid}", "properties": friendly(role, row, conn)}
            for _, _, fid, row in hits[:limit]]


def friendly(role: str, row: dict, conn=None) -> dict:
    out = {}
    for col, label in PROPS[role]:
        if col == "_AGE":
            value = _age(row.get("ABSMIN_MA"), row.get("ABSMAX_MA"))
        elif col == "_SCALE":
            value = f"1:{int(row['RESSCALE']):,}" if row.get("RESSCALE") else ""
        elif col == "_CITATION":
            value = _citation(conn, row.get("SOURCE")) if conn is not None else ""
        elif col == "QUALITY":
            value = str(row.get("QUALITY")) if row.get("QUALITY") is not None else ""
        else:
            value = row.get(col)
        if value is None or (isinstance(value, str) and value.strip() in _EMPTY):
            continue
        if value in _UNKNOWN_NUMBER.get(col, ()):
            continue
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        out[label] = value if not isinstance(value, str) else value.strip()
    out[DATASET_LABEL] = ATTRIBUTION
    return out


def _age(young, old) -> str:
    def fmt(v):
        return f"{v:g}"
    if young is None and old is None:
        return ""
    if young is None or old is None or young == old:
        return fmt(young if young is not None else old)
    return f"{fmt(young)} – {fmt(old)}"


def _citation(conn, source):
    """`Riley et al. 2011b` → 출처 표(sources)의 저자·연도·제목·발간처."""
    if not source:
        return ""
    try:
        meta = _meta(conn, data_file())["sources"]
        row = conn.execute(
            f'SELECT AUTHORS, YEAR, TITLE, PUBLICATION FROM "{meta["table"]}" '
            "WHERE IDENTIFIER = ? LIMIT 1", (source,)).fetchone()
    except (KeyError, sqlite3.Error, GeomapError):
        return ""
    if not row:
        return ""
    authors, year, title, pub = row
    parts = [p.strip() for p in (authors, f"({year})" if year else "", title, pub) if p and str(p).strip()]
    return " ".join(parts)


# ── 높이 그래프의 지질 띠 (wetherilli 180) ────────────────────────────

#: 띠를 그릴 수 있는 레이어 — 면을 칠하는 것만. 단층(선)·자료 품질은 지질 단위가 아니다
BAND_LAYERS = ("geomap_simple_geology", "geomap_simple_lithology", "geomap_chronostratigraphic",
               "geomap_lithostratigraphic")


def band_color(rule: dict) -> str:
    """규칙의 칠 → `#rrggbb`. 암층은 칠 없이 무늬뿐인 것이 있어 무늬·테두리의 색을 쓴다."""
    rgba = rule.get("fill") or next((d.get("color") for d in rule.get("dots") or [] if d.get("color")), None) \
        or rule.get("outline") or (160, 160, 160)
    return "#%02x%02x%02x" % tuple(int(v) for v in rgba[:3])


def units_along(layer: str, points: list) -> list:
    """3031 의 점들 → 점마다 든 면의 규칙 번호(이 레이어에 그려지지 않으면 None).
    겹치면 작은 면이 이긴다 — 팝업(`query`)의 차례와 같다. 한 선의 이웃한 점은 같은 면을 다시 묻기 쉬워 기하를 들고 있는다."""
    style = style_of(layer)
    if style.kind != "fill":
        raise GeomapError(f"띠를 그릴 수 없는 레이어다: {layer}")
    conn, meta = _table(style.table)
    have = {r[1] for r in conn.execute(f'PRAGMA table_info("{meta["table"]}")')}
    fields = [f for f in style.fields if f in have]
    select = ", ".join([f'"{meta["geom"]}"', '"Shape_Area"' if "Shape_Area" in have else "0"] + [f'"{f}"' for f in fields])
    seen = {}
    out = []
    for x, y in points:
        best = None
        for (fid,) in conn.execute(f'SELECT id FROM "{meta["rtree"]}" WHERE maxx >= ? AND minx <= ? '
                                   'AND maxy >= ? AND miny <= ?', (x, x, y, y)):
            if fid not in seen:
                row = conn.execute(f'SELECT {select} FROM "{meta["table"]}" WHERE fid = ?', (fid,)).fetchone()
                rule = style.pick(tuple(row[2:])) if row else None
                seen[fid] = None if rule is None else (parse_geometry(row[0]), row[1] or 0, rule)
            hit = seen[fid]
            if hit is None or hit[0][0] != "polygon":
                continue
            if any(polygon_contains(rings, x, y) for rings in hit[0][1]) and (best is None or hit[1] < best[0]):
                best = (hit[1], hit[2])
        out.append(None if best is None else best[1])
    return out


# ── 뷰가 부르는 꼴 (kigam·geus 와 같게) ───────────────────────────────

def get_map(params: dict):
    """WMS `GetMap` 꼴. 3031 만 받는다 — 우리 타일 격자가 3031 이다."""
    crs = (params.get("crs") or params.get("srs") or "").upper()
    if crs != "EPSG:3031":
        raise GeomapError(f"GeoMAP 은 EPSG:3031 로만 그린다 (받은 것: {crs or '없음'})")
    try:
        bbox = tuple(float(v) for v in str(params.get("bbox", "")).split(","))
        width = max(1, min(int(params.get("width") or 256), 2048))
        height = max(1, min(int(params.get("height") or 256), 2048))
    except ValueError:
        raise GeomapError("BBOX·WIDTH·HEIGHT 를 읽지 못했다") from None
    if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise GeomapError("BBOX 가 틀렸다")
    layer = (params.get("layers") or "").split(",")[0].strip()
    return render(layer, bbox, width, height), "image/png"


def get_legend(layer: str):
    return legend(layer), "image/png"
