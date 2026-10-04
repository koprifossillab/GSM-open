"""해양 지각 연대·해저 퇴적층 두께 — 오늘의 지구에 칠한다 (wetherilli 264). 지각 두께(`crust.py`)와 같은 꼴이다.

| 판 | 원본 | 격자 | 조건 |
|---|---|---|---|
| `age` 해양 지각 연대 | Seton 외 2020 (G³ doi:10.1029/2020GC009214), EarthByte `age.2020.1.GTS2012.6m.grd` | 6′, 3 601 × 1 801, 격자점 | CC BY 4.0 (같은 자리의 `LICENSE.txt`) |
| `sediment` 퇴적층 두께 | GlobSed v3 (Straume 외 2019, G³ doi:10.1029/2018GC008115), NOAA NCEI 0305030 `GlobSed-v3.xyz` | 5′, 4 321 × 2 161, 격자점 | "Use Constraints: None" (NCEI 기록) |

**numpy·h5py 없이 굽는다**(`manage.py build_seafloor`). 연대는 NetCDF-3(고전판) — 머리를 읽고 변수 하나를 big-endian 으로 푼다.
GlobSed 의 `.nc` 는 NetCDF-4(HDF5)라 읽지 않고, 같은 판의 글 파일(`.xyz`, 284 MB, 북→남·서→동 줄)을 읽는다.
원본은 NAS `N:\\GSM\\sources\\earth\\`, 구운 것은 `<EARTH_DIR>/seafloor_<판>.png`(칠한 그림)·`.i16`(누른 자리, 정수)·`.json`(격자).
저장소에 두지 않는다 — 수십 MB 다. 파일이 없으면 온 지구 화면에 그 레이어가 서지 않는다.

- **오늘에만 뜬다.** 오늘의 바다 밑을 옛 연대로 돌리지 않는다(연대 격자는 판 회전으로 옛것을 지을 수 있지만 그것은 다른 일이다)
- 연대는 0.1 Myr, 두께는 m 로 적는다(int16). 빈 곳(대륙·자료 밖)은 −32768
- 색: 연대는 젊은 빨강 → 늙은 보라(해령에서 멀어질수록), 두께는 얇은 크림 → 두꺼운 고동
그리는 법을 고치면 `RENDERER` 를 올린다.
"""
import functools
import io
import json
import struct
from array import array
from pathlib import Path

from django.conf import settings

from . import paleo

RENDERER = "1"
MAX_ZOOM = 6                     # 180/2⁶/256 ≈ 0.011° — 원본(0.1°·0.083°)보다 잘다. 그 너머는 늘린다
NODATA = -32768
KINDS = {
    # 판 → (값에 곱하는 수, 단위, (값, 색) 고리, 범례의 칸 경계, 출처)
    "age": (10, "Ma", ((0, "#c80000"), (10, "#ff6400"), (25, "#ffc800"), (45, "#c8f000"), (65, "#32c832"), (90, "#00c0c0"),
                       (120, "#0064ff"), (155, "#3c14c8"), (200, "#6e0a96"), (280, "#3c0050")),
            (0, 10, 25, 45, 65, 90, 120, 155, 200, 280),
            "Seton et al. 2020, G-cubed · EarthByte · CC BY 4.0"),
    "sediment": (1, "m", ((0, "#fff7d6"), (250, "#fde5a8"), (500, "#fbc979"), (1000, "#f2a254"), (2000, "#d97b35"),
                          (4000, "#a85520"), (7000, "#723812"), (12000, "#3d1d08")),
                 (0, 250, 500, 1000, 2000, 4000, 7000, 12000),
                 "GlobSed v3 (Straume et al. 2019, G-cubed) · NOAA NCEI"),
}


class SeafloorError(RuntimeError):
    pass


def _path(kind: str, suffix: str) -> Path:
    return Path(settings.EARTH_DIR) / f"seafloor_{kind}{suffix}"


def available(kind: str) -> bool:
    return kind in KINDS and _path(kind, ".png").is_file() and _path(kind, ".json").is_file()


def files(kind: str) -> tuple:
    return tuple(_path(kind, s) for s in (".png", ".i16", ".json"))


# ── 원본 읽기 ────────────────────────────────────────────────────────

_NC_TYPES = {1: ("b", 1), 2: ("c", 1), 3: ("h", 2), 4: ("i", 4), 5: ("f", 4), 6: ("d", 8)}


def read_netcdf3(data: bytes) -> dict:
    """NetCDF-3 고전판(CDF1·CDF2) → `{"dims": {이름: 길이}, "vars": {이름: {"dims", "type", "atts", "begin", "vsize"}}}`.
    값은 읽지 않는다 — `variable` 이 하나씩 푼다. 기록 차원(unlimited)은 다루지 않는다(격자에는 없다)."""
    if data[:3] != b"CDF" or data[3] not in (1, 2):
        raise SeafloorError("NetCDF-3 고전판이 아니다")
    offset_size = 4 if data[3] == 1 else 8
    at = 8                                          # 마법 4 + numrecs 4

    def u32():
        nonlocal at
        v = struct.unpack_from(">I", data, at)[0]
        at += 4
        return v

    def name():
        nonlocal at
        n = u32()
        s = data[at:at + n].decode("utf-8", "replace")
        at += (n + 3) // 4 * 4
        return s

    def atts():
        nonlocal at
        tag, n = u32(), u32()
        out = {}
        if tag == 0 and n == 0:
            return out
        for _ in range(n):
            key = name()
            typ, count = u32(), u32()
            code, size = _NC_TYPES[typ]
            raw = data[at:at + size * count]
            at += (size * count + 3) // 4 * 4
            out[key] = raw.decode("utf-8", "replace") if code == "c" else list(struct.unpack(f">{count}{code}", raw))
        return out

    tag, n = u32(), u32()
    dims = []
    for _ in range(n if tag else 0):
        dims.append((name(), u32()))
    gatts = atts()
    tag, n = u32(), u32()
    variables = {}
    for _ in range(n if tag else 0):
        vname = name()
        ndim = u32()
        ids = [u32() for _ in range(ndim)]
        vatts = atts()
        typ, vsize = u32(), u32()
        begin = struct.unpack_from(">I" if offset_size == 4 else ">Q", data, at)[0]
        at += offset_size
        variables[vname] = {"dims": [dims[i][0] for i in ids], "type": typ, "atts": vatts, "begin": begin, "vsize": vsize}
    return {"dims": dict(dims), "vars": variables, "atts": gatts}


def variable(data: bytes, head: dict, vname: str) -> array:
    """변수 하나의 값 — 실수 `array("f"|"d")`, 바이트 차례를 이 기계로."""
    v = head["vars"][vname]
    code, size = _NC_TYPES[v["type"]]
    count = 1
    for d in v["dims"]:
        count *= head["dims"][d]
    if code not in ("f", "d"):
        raise SeafloorError(f"{vname} 이 실수가 아니다")
    out = array(code)
    out.frombytes(data[v["begin"]:v["begin"] + size * count])
    out.byteswap()                                  # NetCDF 는 big-endian, 이 기계는 little-endian
    return out


def read_age(path) -> dict:
    """Seton 2020 연대 격자(.grd, NetCDF-3) → `{"w", "h", "lon0", "lat0", "dx", "dy", "values"}`. 줄은 북→남으로 고친다."""
    data = Path(path).read_bytes()
    head = read_netcdf3(data)
    grids = [n for n, v in head["vars"].items() if len(v["dims"]) == 2]
    if len(grids) != 1:
        raise SeafloorError(f"2 차원 변수가 하나가 아니다: {grids}")
    zname = grids[0]
    ydim, xdim = head["vars"][zname]["dims"]
    lon, lat = variable(data, head, xdim), variable(data, head, ydim)
    z = variable(data, head, zname)
    w, h = len(lon), len(lat)
    fill = head["vars"][zname]["atts"].get("_FillValue", [None])[0]
    north_first = lat[0] > lat[-1]
    values = array("f")
    for j in (range(h) if north_first else range(h - 1, -1, -1)):
        row = z[j * w:(j + 1) * w]
        values.extend(float("nan") if (fill is not None and v == fill) else v for v in row)
    return {"w": w, "h": h, "lon0": lon[0], "lat0": max(lat[0], lat[-1]), "dx": (lon[-1] - lon[0]) / (w - 1),
            "dy": abs(lat[-1] - lat[0]) / (h - 1), "values": values}


def read_xyz(path, w: int = 4321, h: int = 2161) -> dict:
    """GlobSed 글 격자(경도·위도·값, 탭, 북→남·서→동) → 같은 꼴. NaN 은 빈 곳"""
    values = array("f")
    first = last = None
    with open(path, encoding="ascii") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) != 3:
                continue
            if first is None:
                first = (float(parts[0]), float(parts[1]))
            values.append(float(parts[2]))
            last = parts
    if len(values) != w * h:
        raise SeafloorError(f"값이 {len(values)} 개다 — {w}×{h} 를 기다렸다")
    lon_last, lat_last = float(last[0]), float(last[1])
    return {"w": w, "h": h, "lon0": first[0], "lat0": first[1], "dx": (lon_last - first[0]) / (w - 1),
            "dy": (first[1] - lat_last) / (h - 1), "values": values}


# ── 칠하기 ───────────────────────────────────────────────────────────

def _rgb(hexa):
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def colour(kind: str, value: float) -> tuple:
    stops = KINDS[kind][2]
    if value <= stops[0][0]:
        return _rgb(stops[0][1])
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if value <= b:
            f = (value - a) / (b - a)
            return tuple(round(x + (y - x) * f) for x, y in zip(_rgb(ca), _rgb(cb)))
    return _rgb(stops[-1][1])


def legend(kind: str) -> list:
    """범례의 칸 — `[{"name": "0–10 Ma", "color": "#…"}…]`. 칸 가운데의 색"""
    edges, unit = KINDS[kind][3], KINDS[kind][1]
    out = []
    for lo, hi in zip(edges, edges[1:]):
        r, g, b = colour(kind, (lo + hi) / 2)
        out.append({"name": f"{lo:,}–{hi:,} {unit}", "color": f"#{r:02x}{g:02x}{b:02x}"})
    return out


# ── 굽기 ─────────────────────────────────────────────────────────────

def build(kind: str, grid: dict) -> dict:
    """읽은 격자 → `<EARTH_DIR>/seafloor_<판>.png·.i16·.json`. 칠한 그림은 팔레트 255 칸(0 은 빈 곳)"""
    from PIL import Image
    scale, _, stops, _, _ = KINDS[kind]
    top = stops[-1][0]
    ints, index = array("h"), bytearray()
    lut = {}
    lo = hi = None
    for v in grid["values"]:
        if v != v:                                  # NaN
            ints.append(NODATA)
            index.append(0)
            continue
        n = max(-32767, min(32767, round(v * scale)))
        ints.append(n)
        lo = n if lo is None or n < lo else lo
        hi = n if hi is None or n > hi else hi
        i = lut.get(n)
        if i is None:
            i = lut[n] = 1 + round(max(0.0, min(1.0, (n / scale) / top)) * 254)
        index.append(i)
    if lo is None:
        raise SeafloorError("값이 하나도 없다")
    palette = [0, 0, 0]
    for i in range(1, 256):
        palette += colour(kind, (i - 1) / 254 * top)
    image = Image.frombytes("P", (grid["w"], grid["h"]), bytes(index))
    image.putpalette(palette)
    out = Path(settings.EARTH_DIR)
    out.mkdir(parents=True, exist_ok=True)
    png, i16, meta = files(kind)
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True, transparency=0)
    for path, data in ((png, buf.getvalue()), (i16, ints.tobytes())):
        tmp = path.with_suffix(path.suffix + ".new")
        tmp.write_bytes(data)
        tmp.replace(path)
    info = {k: grid[k] for k in ("w", "h", "lon0", "lat0", "dx", "dy")}
    info.update(scale=scale, min=lo / scale, max=hi / scale)
    meta.write_text(json.dumps(info), encoding="utf-8")
    _image.cache_clear()
    _meta.cache_clear()
    return info


# ── 타일·누른 자리 ────────────────────────────────────────────────────

@functools.lru_cache(maxsize=2)
def _meta(kind: str) -> dict:
    return json.loads(_path(kind, ".json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=2)
def _image(kind: str):
    from PIL import Image
    return Image.open(_path(kind, ".png")).convert("RGBA")


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(kind: str, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`crust.render_tile` 과 같다) 한 장. 격자점이 화소의 가운데라 반 칸 옮겨 잰다"""
    from PIL import Image
    m = _meta(kind)
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    box = ((west - m["lon0"]) / m["dx"] + 0.5, (m["lat0"] - north) / m["dy"] + 0.5,
           (west + span - m["lon0"]) / m["dx"] + 0.5, (m["lat0"] - north + span) / m["dy"] + 0.5)
    resample = Image.Resampling.NEAREST if span / 256 < min(m["dx"], m["dy"]) / 2 else Image.Resampling.BILINEAR
    tile = _image(kind).transform((paleo.TILE, paleo.TILE), Image.Transform.EXTENT, box, resample)
    buf = io.BytesIO()
    tile.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def at(kind: str, lon: float, lat: float):
    """누른 자리의 값(Ma 또는 m). 빈 곳·파일 없음은 None"""
    try:
        m = _meta(kind)
    except (OSError, ValueError):
        return None
    lon = ((lon + 180.0) % 360.0) - 180.0
    i = round((lon - m["lon0"]) / m["dx"])
    j = round((m["lat0"] - lat) / m["dy"])
    if not (0 <= i < m["w"] and 0 <= j < m["h"]):
        return None
    try:
        with open(_path(kind, ".i16"), "rb") as fh:
            fh.seek(2 * (j * m["w"] + i))
            raw = fh.read(2)
    except OSError:
        return None
    if len(raw) != 2:
        return None
    n = struct.unpack("<h", raw)[0]
    return None if n == NODATA else n / m["scale"]
