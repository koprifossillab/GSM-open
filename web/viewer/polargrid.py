"""남극 격자를 칠해 3031 타일로 잘라 두는 틀 — 중력·지열류 모형이 함께 쓴다 (wetherilli 431·432).

ADMAP-2(`admap.py`, wetherilli 262)가 한 번 한 일을 판 여럿이 쓰게 뗐다 — 격자 하나를 칸 번호로 칠하고 GeoMAP 의 3031 격자로 잘라
`tiles/{z}/{x}/{y}.webp` 에, 누른 자리는 칸마다 정수를 int16 으로 적은 `values.i16`(위에서 아래로)과 `meta.json` 에 둔다.
**numpy 없이 돈다.** 원본을 읽는 일(HDF5 는 h5py, 글 격자는 csv)은 판마다의 파일(`antgg.py`·`ghfgrid.py`)이 맡고, 여기는
`Grid` 하나를 받는다. 상류가 아니라 우리 디스크의 파일이라 문이 아니다.

- `Grid` — 칸 한 변 `res`(m), 왼쪽 위 칸의 가운데 `x0`·`ytop`, 줄은 **위에서 아래로**, 빈 곳은 NaN
- 판(`Set`)마다 — 폴더(설정 이름 + 하위 폴더), 정수로 적을 배율(`scale` — 0.1 mGal 이면 10), 칠하기(값 → 칸 번호 1…255 와 팔레트),
  자를 줌(원본 한 칸보다 곱게 자르지 않는다)
- 흩어진 점(경위도로 적힌 모형, Lösing 2021)은 `rasterize` 가 가장 가까운 점으로 칸을 채운다 — 반지름 밖은 비운다
그리는 법을 고치면 다시 굽는다 — 타일 주소의 판은 폴더의 고친 때다(`views._dir_version`).
"""
import io
import json
import math
import shutil
import struct
from array import array
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from . import geomap

FORMAT = "webp"
TILE = geomap.TILE
NODATA = -32768


class PolarGridError(RuntimeError):
    pass


@dataclass(frozen=True, eq=False)
class Set:
    """칠해 잘라 둔 판 하나 — 레이어 하나에 하나"""
    name: str                 # 레이어 이름 (`antgg:free_air`)
    where: str                # 설정 이름(폴더) — `ANTGG_DIR`
    sub: str                  # 그 안의 폴더
    unit: str                 # mGal · mW/m²
    scale: int                # 정수로 적을 배율 — 값 × scale 을 int16 으로
    max_zoom: int
    index_of: object          # 값 → 칸 번호 1…255
    palette: tuple            # 칸 번호 0…255 → RGB 768 개 (0 은 빈 곳)
    prop: str                 # 누른 자리 속성의 이름 — 영어는 `i18n.PROP_EN`
    attribution: str

    def root(self) -> Path:
        return Path(getattr(settings, self.where)) / self.sub

    def tiles_dir(self) -> Path:
        return self.root() / "tiles"

    def available(self) -> bool:
        return self.tiles_dir().is_dir()

    def valid_tile(self, z: int, x: int, y: int) -> bool:
        return 0 <= z <= self.max_zoom and 0 <= x < 2 ** z and 0 <= y < 2 ** z

    def read_tile(self, z: int, x: int, y: int):
        try:
            return (self.tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}").read_bytes()
        except FileNotFoundError:
            return None


@dataclass
class Grid:
    ne: int
    nv: int
    res: float
    x0: float                 # 왼쪽 칸의 가운데
    ytop: float               # 위 칸의 가운데
    values: array             # float32, 위에서 아래로, 빈 곳 NaN


# ── 칠하기 ───────────────────────────────────────────────────────────

def ramp_color(s: float, ramp) -> tuple:
    """늘인 자리 s 의 색 — `ramp` 는 (자리, RGB) 를 자리 차례로"""
    for (s0, c0), (s1, c1) in zip(ramp, ramp[1:]):
        if s <= s1:
            t = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
            return tuple(round(a + (b - a) * max(0.0, min(1.0, t))) for a, b in zip(c0, c1))
    return ramp[-1][1]


def ramp_palette(ramp, lo: float, hi: float) -> tuple:
    """연속 색 — 칸 번호 i(1…255)는 lo…hi 를 254 칸으로 나눈 자리. 늘이기는 부르는 쪽이 index_of 에서"""
    out = [0, 0, 0]
    for i in range(1, 256):
        out += ramp_color(lo + (hi - lo) * (i - 1) / 254.0, ramp)
    return tuple(out)


def ramp_index(stretch, lo: float, hi: float):
    """값 → 칸 번호. `stretch(v)` 가 늘인 자리를 주고, lo…hi 밖은 끝 칸"""
    def index_of(v: float) -> int:
        s = (min(hi, max(lo, stretch(v))) - lo) / (hi - lo)
        return 1 + round(s * 254)
    return index_of


def class_palette(classes) -> tuple:
    """갈래 색 — `classes` 는 (윗 경계, "#rrggbb", …) 차례. 칸 번호 i 는 i 번째 갈래"""
    out = [0, 0, 0]
    for row in classes:
        h = row[1].lstrip("#")
        out += (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    out += [0, 0, 0] * (256 - len(classes) - 1)
    return tuple(out)


def class_index(classes):
    def index_of(v: float) -> int:
        for i, row in enumerate(classes):
            if v < row[0]:
                return i + 1
        return len(classes)
    return index_of


# ── 격자 짓기 ─────────────────────────────────────────────────────────

def from_rows(rows_in, xs, ys) -> Grid:
    """`rows_in[j][i]` 가 (xs[i], ys[j]) 칸인 격자 → `Grid`. xs·ys 는 고른 간격이고 어느 쪽으로 늘어도 된다"""
    ne, nv = len(xs), len(ys)
    res = abs(xs[1] - xs[0])
    if abs(abs(ys[1] - ys[0]) - res) > 1e-6 * res:
        raise PolarGridError("가로와 세로의 칸 간격이 다르다")
    rows = range(nv - 1, -1, -1) if ys[0] < ys[-1] else range(nv)
    cols = range(ne) if xs[0] < xs[-1] else range(ne - 1, -1, -1)
    values = array("f")
    for j in rows:
        line = rows_in[j]
        values.extend(float(line[i]) for i in cols)
    return Grid(ne, nv, res, min(xs[0], xs[-1]), max(ys[0], ys[-1]), values)


def rasterize(points, res: float, radius: float = None) -> Grid:
    """3031 의 흩어진 점 (x, y, 값) → 한 변 `res` 의 칸. 칸마다 가운데에서 가장 가까운 점, `radius` 밖이면 빈 칸.
    점이 그 간격의 격자에 놓였으면 칸 하나에 점 하나다(Stål·Martos). 경위도로 적힌 것(Lösing)은 반지름을 칸 간격보다 넉넉히"""
    pts = [(x, y, v) for x, y, v in points if v == v]
    if not pts:
        raise PolarGridError("값이 있는 점이 없다")
    radius = radius or res * 0.75
    left, bottom = min(p[0] for p in pts), min(p[1] for p in pts)         # 칸을 점에 맞춘다 — 격자에 놓인 점이면 칸 가운데에 선다
    ne = int(math.ceil((max(p[0] for p in pts) - left) / res - 1e-6)) + 1
    nv = int(math.ceil((max(p[1] for p in pts) - bottom) / res - 1e-6)) + 1
    x0, ytop = left, bottom + (nv - 1) * res
    bucket = {}
    size = max(res, radius)
    for p in pts:
        bucket.setdefault((math.floor(p[0] / size), math.floor(p[1] / size)), []).append(p)
    values = array("f", [math.nan]) * (ne * nv)
    r2 = radius * radius
    for row in range(nv):
        cy = ytop - row * res
        by = math.floor(cy / size)
        for col in range(ne):
            cx = x0 + col * res
            bx = math.floor(cx / size)
            best, best_d = None, r2
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for px, py, v in bucket.get((bx + dx, by + dy), ()):
                        d = (px - cx) ** 2 + (py - cy) ** 2
                        if d <= best_d:
                            best, best_d = v, d
            if best is not None:
                values[row * ne + col] = best
    return Grid(ne, nv, res, x0, ytop, values)


# ── 굽기 ─────────────────────────────────────────────────────────────

def bake(spec: Set, grid: Grid, source: str, out_dir=None, log=print) -> dict:
    """`Grid` → `values.i16`·`meta.json`·`tiles/`. 새 타일은 옆 자리(`tiles.new`)에 다 쓰고 바꿔 끼운다"""
    from PIL import Image
    out = Path(out_dir) if out_dir else spec.root()
    out.mkdir(parents=True, exist_ok=True)
    ints = array("h")
    index = bytearray()
    lut = {}
    for v in grid.values:
        if v != v:
            ints.append(NODATA)
            index.append(0)
            continue
        n = max(-32767, min(32767, round(v * spec.scale)))
        ints.append(n)
        i = lut.get(n)
        if i is None:
            i = lut[n] = spec.index_of(n / spec.scale)
        index.append(i)
    (out / "values.i16.new").write_bytes(ints.tobytes())
    (out / "values.i16.new").replace(out / "values.i16")
    meta = {"ne": grid.ne, "nv": grid.nv, "res": grid.res, "x0": grid.x0, "ytop": grid.ytop,
            "scale": spec.scale, "unit": spec.unit, "source": source}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    valid = [n for n in ints if n != NODATA]
    if not valid:
        raise PolarGridError("값이 있는 칸이 없다")
    stats = {"cells": len(valid), "min": min(valid) / spec.scale, "max": max(valid) / spec.scale}
    del ints, valid
    log(f"{spec.name}: 격자 {grid.ne}×{grid.nv}, 한 칸 {grid.res:,.0f} m, 값이 있는 칸 {stats['cells']:,} "
        f"({stats['min']:g} … {stats['max']:g} {spec.unit})")

    image = Image.frombytes("P", (grid.ne, grid.nv), bytes(index))
    del index
    image.putpalette(list(spec.palette))
    image.info["transparency"] = 0
    full = image.convert("RGBA").convert("RGBa")          # 줄일 때 투명한 가장자리가 번지지 않게 미리 곱한다
    del image
    stats.update(write_tiles(full, meta, out, spec.max_zoom))
    return stats


def write_tiles(full, meta: dict, out: Path, max_zoom: int) -> dict:
    tiles, fresh = out / "tiles", out / "tiles.new"
    shutil.rmtree(fresh, ignore_errors=True)
    written = size = 0
    for z in range(max_zoom, -1, -1):
        res = geomap.resolution(z)
        factor = max(1, 2 ** int(math.log2(res / meta["res"]))) if res > meta["res"] else 1
        level = full if factor == 1 else full.reduce(factor)
        for x in range(2 ** z):
            for y in range(2 ** z):
                tile = cut(level, factor, meta, z, x, y)
                if tile is None:
                    continue
                buf = io.BytesIO()
                tile.save(buf, format="WEBP", quality=85, method=4)
                target = fresh / str(z) / str(x) / f"{y}.{FORMAT}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(buf.getvalue())
                written += 1
                size += buf.tell()
        del level
    fresh.mkdir(parents=True, exist_ok=True)              # 다 빈 판도 폴더는 선다 — "없다" 안내와 가른다
    old = out / "tiles.old"
    shutil.rmtree(old, ignore_errors=True)
    if tiles.exists():
        tiles.rename(old)
    fresh.rename(tiles)
    shutil.rmtree(old, ignore_errors=True)
    return {"tiles": written, "mb": round(size / 1e6, 1)}


def source_box(meta: dict, z: int, x: int, y: int) -> tuple:
    """3031 타일이 원본에서 차지하는 화소 네모 (왼, 위, 오른, 아래). 원점은 칸의 가운데라 반 칸 옮긴다"""
    west, south, east, north = geomap.tile_bbox(z, x, y)
    res, left0, top0 = meta["res"], meta["x0"] - meta["res"] / 2, meta["ytop"] + meta["res"] / 2
    return (west - left0) / res, (top0 - north) / res, (east - left0) / res, (top0 - south) / res


def cut(level_image, factor: int, meta: dict, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). 다 투명하면 None — ADMAP·IBCSO 의 `cut` 과 같은 꼴"""
    from PIL import Image
    left, top, right, bottom = (v / factor for v in source_box(meta, z, x, y))
    w, h = level_image.size
    cl, ct, cr, cb = max(left, 0), max(top, 0), min(right, w), min(bottom, h)
    if cr <= cl or cb <= ct:
        return None
    px, py = TILE / (right - left), TILE / (bottom - top)
    ox, oy = round((cl - left) * px), round((ct - top) * py)
    ow, oh = round((cr - left) * px) - ox, round((cb - top) * py) - oy
    if ow < 1 or oh < 1:
        return None
    piece = level_image.resize((ow, oh), Image.BILINEAR, box=(cl, ct, cr, cb))
    tile = Image.new("RGBa", (TILE, TILE), (0, 0, 0, 0))
    tile.paste(piece, (ox, oy))
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile


# ── 누른 자리 ─────────────────────────────────────────────────────────

_metas = {}


def _meta(spec: Set) -> dict:
    path = spec.root() / "meta.json"
    mtime = path.stat().st_mtime
    hit = _metas.get(path)
    if hit is None or hit[0] != mtime:
        hit = _metas[path] = (mtime, json.loads(path.read_text(encoding="utf-8")))
    return hit[1]


def value_at(spec: Set, lat: float, lon: float):
    """누른 자리의 값(단위 그대로, 배율을 푼 것). 자료 밖·빈 곳·파일 없음은 None"""
    try:
        meta = _meta(spec)
    except (OSError, ValueError):
        return None
    x, y = geomap.lonlat_to_3031(lon, lat)
    col = round((x - meta["x0"]) / meta["res"])
    row = round((meta["ytop"] - y) / meta["res"])
    if not (0 <= col < meta["ne"] and 0 <= row < meta["nv"]):
        return None
    try:
        with open(spec.root() / "values.i16", "rb") as f:
            f.seek(2 * (row * meta["ne"] + col))
            raw = f.read(2)
    except OSError:
        return None
    if len(raw) != 2:
        return None
    n = struct.unpack("<h", raw)[0]
    if n == NODATA:
        return None
    return n / meta["scale"] if meta["scale"] != 1 else n
