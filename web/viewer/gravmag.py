"""자력 이상·부게 중력 이상 — 온 세계 격자를 칠해 경위도 타일로 낸다 (wetherilli 391). 해양 지각 연대(`seafloor.py`)와 같은 꼴이다.

| 판 | 원본 | 격자 | 조건 |
|---|---|---|---|
| `magnetic` 자력 이상(4 km 높이) | EMAG2v3 (Meyer 외 2017, NOAA NCEI doi:10.7289/V5H70CVX) `EMAG2_V3_20170530.zip`(CSV 1.2 GB) | 2′, 10 800 × 5 400 | 공공 도메인 |
| `bouguer` 부게 중력 이상 | EIGEN-6C4 (Förste 외 2014, GFZ doi:10.5880/icgem.2015.1)를 ICGEM 계산 서비스로 격자로 뽑은 `.gdf` | 뽑은 대로 | CC BY 4.0 |

**numpy 없이 굽는다**(`manage.py build_gravmag`). EMAG2v3 은 CSV 묶음을 흘려 읽는다 — NOAA 의 GeoTIFF 들은 바다만 덮거나 칠한 그림이다
(`read_emag2`). 부게는 ICGEM 이 내주는 글 격자(머리 뒤 `end_of_head`, 그다음
경도·위도·값 줄)를 읽는다. 원본은 NAS `N:\\GSM\\sources\\earth\\emag2\\`·`…\\icgem\\`, 구운 것은 `<EARTH_DIR>/gravmag_<판>.png`(칠한 그림)·`.i16`
(누른 자리, 정수)·`.json`(격자). 저장소에 두지 않는다.

- **4′(약 7 km)로 줄여 굽는다.** 2′ 그대로면 칠한 그림을 풀어 둔 것이 일꾼 하나에 233 MB 다. 2×2 칸을 빈 곳을 빼고 평균한다. 지역 탭의
  줌 9 남짓까지는 이 격자로 넉넉하다 — EMAG2 자체가 바다·자료가 성긴 곳은 2′ 보다 거칠다
- 값은 nT·mGal 정수(int16). 빈 곳은 −32768
- 색은 0 을 가운데 둔 파랑–흰–빨강. 끝(`SPAN`)을 넘으면 끝의 색이다. 자력은 ±300 nT, 부게는 ±300 mGal 을 끝으로 둔다 — 대륙의 부게는
  고원에서 −400 mGal 아래로 가지만, 끝을 넓히면 지각 경계의 무늬가 묻힌다
- **오늘의 것이다**
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
from .i18n import msg

RENDERER = "1"
MAX_ZOOM = 6                     # 180/2⁶/256 ≈ 0.011° — 4′(0.067°)보다 잘다. 그 너머는 화면이 늘린다
NODATA = -32768
#: 줄이는 배율 — 원본 칸 몇 개를 하나로 (EMAG2 2′ → 4′)
SHRINK = 2
#: 판 → (단위, 색의 끝, 이름, 출처)
KINDS = {
    "magnetic": ("nT", 300, msg("자력 이상 (4 km 높이)"),
                 "EMAG2v3 (Meyer et al. 2017), NOAA NCEI · public domain"),
    "bouguer": ("mGal", 300, msg("부게 중력 이상"),
                "EIGEN-6C4 (Förste et al. 2014, GFZ) via ICGEM · CC BY 4.0"),
}
#: 0 을 가운데 둔 색 — (끝에 대한 비, 색). ColorBrewer RdBu 를 뒤집었다(음 파랑, 양 빨강)
STOPS = ((-1.0, "#053061"), (-0.6, "#2166ac"), (-0.3, "#67a9cf"), (-0.1, "#d1e5f0"), (0.0, "#f7f7f7"),
         (0.1, "#fddbc7"), (0.3, "#ef8a62"), (0.6, "#b2182b"), (1.0, "#67001f"))
#: 범례의 칸 경계 — 끝에 대한 비
EDGES = (-1.0, -0.6, -0.3, -0.1, 0.1, 0.3, 0.6, 1.0)


class GravMagError(RuntimeError):
    pass


def _path(kind: str, suffix: str) -> Path:
    return Path(settings.EARTH_DIR) / f"gravmag_{kind}{suffix}"


def available(kind: str) -> bool:
    return kind in KINDS and _path(kind, ".png").is_file() and _path(kind, ".json").is_file()


def files(kind: str) -> tuple:
    return tuple(_path(kind, s) for s in (".png", ".i16", ".json"))


# ── 원본 읽기 ─────────────────────────────────────────────────────────

def _shrink(values, w: int, h: int, k: int) -> dict:
    """`k`×`k` 칸을 빈 곳(NaN)을 빼고 평균한다 — 다 비면 NaN"""
    nan = float("nan")
    w2, h2 = w // k, h // k
    out = array("f", [nan]) * (w2 * h2)
    for j2 in range(h2):
        rows = [values[(j2 * k + dj) * w:(j2 * k + dj + 1) * w] for dj in range(k)]
        for i2 in range(w2):
            total = n = 0
            for row in rows:
                for v in row[i2 * k:(i2 + 1) * k]:
                    if v == v:
                        total += v
                        n += 1
            if n:
                out[j2 * w2 + i2] = total / n
    return {"values": out, "w": w2, "h": h2}


#: EMAG2v3 의 격자 — 2′, 온 지구
EMAG2_STEP = 1.0 / 30.0
EMAG2_W, EMAG2_H = 10800, 5400


def read_emag2(path, shrink: int = SHRINK, column: str = "UpCont") -> dict:
    """EMAG2v3 의 CSV 묶음(`EMAG2_V3_20170530.zip`) → 경도 −180 부터 북→남·서→동, `shrink` 배로 줄인 격자.

    NOAA 가 내주는 GeoTIFF 둘(`SeaLevel_tiff.tif`·`UpCont_tiff.tif`)은 쓰지 않는다 — 앞의 것은 값이지만 **바다만** 덮고(대륙이 빈칸),
    뒤의 것은 값이 아니라 칠한 RGB 그림이다. 대륙까지 값이 있는 것은 이 CSV(열: i, j, 경도, 위도, SeaLevel, UpCont, 자료 부호, 오차)뿐이다.
    **UpCont(4 km 높이로 위로 이은 값)** 를 쓴다 — 해수면 값(SeaLevel)은 대륙에서 비어 있다. 빈 값(99999)은 NaN. 경도는 0–360 이다.
    zip 을 풀지 않고 줄을 흘려 읽는다 — 5 800 만 줄"""
    import csv
    import zipfile
    nan = float("nan")
    values = array("f", [nan]) * (EMAG2_W * EMAG2_H)
    with zipfile.ZipFile(path) as zf:
        member = next((n for n in zf.namelist() if n.lower().endswith((".csv", ".txt")) and "readme" not in n.lower()), None)
        if member is None:
            raise GravMagError("묶음에 CSV 가 없다")
        with zf.open(member) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="ascii", errors="replace"))
            pick = 5 if column == "UpCont" else 4
            for row in reader:
                if len(row) <= pick:
                    continue
                try:
                    lon, lat, v = float(row[2]), float(row[3]), float(row[pick])
                except ValueError:
                    continue                                    # 머리 줄
                if abs(v) > 9999:                              # 빈 값은 99999 (양수다)
                    continue
                i = int((lon + 180.0) / EMAG2_STEP) % EMAG2_W
                j = int((90.0 - lat) / EMAG2_STEP)
                if 0 <= j < EMAG2_H:
                    values[j * EMAG2_W + i] = v
    grid = _shrink(values, EMAG2_W, EMAG2_H, shrink)
    step = EMAG2_STEP * shrink
    grid.update(lon0=-180.0 + step / 2, lat0=90.0 - step / 2, dx=step, dy=step)
    return grid


def read_gdf(path) -> dict:
    """ICGEM 이 내주는 글 격자(`.gdf`) → 북→남·서→동 격자. 머리의 `latlimit_north`·`longlimit_west`·`gridstep` 을 믿고,
    줄은 `end_of_head` 뒤의 경도·위도·값이다. 경도가 0–360 이면 −180 부터로 돌린다"""
    head, rows, body = {}, [], False
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            if not body:
                parts = line.split()
                if parts and parts[0] == "end_of_head":
                    body = True
                elif len(parts) >= 2:
                    head[parts[0]] = parts[1]
                continue
            parts = line.split()
            if len(parts) >= 3:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
    if not rows:
        raise GravMagError("격자 줄이 없다 — ICGEM 의 .gdf 인가")
    step = float(head.get("gridstep") or head.get("grid_step") or 0)
    lons = sorted({r[0] for r in rows})
    lats = sorted({r[1] for r in rows}, reverse=True)
    if not step:
        step = lons[1] - lons[0]
    if lons[-1] > 180:
        rows = [((x - 360.0) if x >= 180 else x, y, v) for x, y, v in rows]
        lons = sorted({r[0] for r in rows})
    w, h = len(lons), len(lats)
    col = {round(x / step): i for i, x in enumerate(lons)}
    row = {round(y / step): j for j, y in enumerate(lats)}
    values = array("f", [float("nan")]) * (w * h)
    for x, y, v in rows:
        values[row[round(y / step)] * w + col[round(x / step)]] = v
    return {"values": values, "w": w, "h": h, "lon0": lons[0], "lat0": lats[0], "dx": step, "dy": step}


# ── 색·범례 ──────────────────────────────────────────────────────────

def _rgb(hexa):
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def colour(kind: str, value: float) -> tuple:
    f = max(-1.0, min(1.0, value / KINDS[kind][1]))
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if f <= b:
            t = (f - a) / (b - a)
            return tuple(round(x + (y - x) * t) for x, y in zip(_rgb(ca), _rgb(cb)))
    return _rgb(STOPS[-1][1])


def legend(kind: str) -> list:
    """범례의 칸 — `[{"label": "−300 – −180 nT", "color": "#…", "code": i}]`. 칸 가운데의 색. 양 끝 칸은 "이하"·"이상" 을 겸한다"""
    unit, span = KINDS[kind][0], KINDS[kind][1]
    out = []
    for i, (lo, hi) in enumerate(zip(EDGES, EDGES[1:])):
        r, g, b = colour(kind, (lo + hi) / 2 * span)
        a, z = round(lo * span), round(hi * span)
        label = (f"≤ {z:,} {unit}" if i == 0 else f"≥ {a:,} {unit}" if i == len(EDGES) - 2 else f"{a:,} – {z:,} {unit}")
        out.append({"label": label.replace("-", "−"), "color": f"#{r:02x}{g:02x}{b:02x}", "code": i})
    return out


# ── 굽기 ─────────────────────────────────────────────────────────────

def build(kind: str, grid: dict) -> dict:
    """읽은 격자 → `<EARTH_DIR>/gravmag_<판>.png·.i16·.json`. 칠한 그림은 팔레트 255 칸(0 은 빈 곳)"""
    from PIL import Image
    span = KINDS[kind][1]
    ints, index = array("h"), bytearray()
    lo = hi = None
    for v in grid["values"]:
        if v != v:
            ints.append(NODATA)
            index.append(0)
            continue
        n = max(-32767, min(32767, round(v)))
        ints.append(n)
        lo = n if lo is None or n < lo else lo
        hi = n if hi is None or n > hi else hi
        index.append(1 + round((max(-1.0, min(1.0, n / span)) + 1) / 2 * 254))
    if lo is None:
        raise GravMagError("값이 하나도 없다")
    palette = [0, 0, 0]
    for i in range(1, 256):
        palette += colour(kind, ((i - 1) / 254 * 2 - 1) * span)
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
    info.update(min=lo, max=hi)
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
    """경위도 격자(`seafloor.render_tile` 과 같다) 한 장. 격자 칸의 가운데가 `lon0`·`lat0` 라 반 칸 옮겨 잰다"""
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
    """누른 자리의 값(nT·mGal). 빈 곳·파일 없음은 None"""
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
    return None if n == NODATA else n


#: 레이어 이름 → 판. 지역 탭이 경위도 타일을 옮겨 그린다
LAYERS = {"gravmag:magnetic": "magnetic", "gravmag:bouguer": "bouguer"}

#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371). 우리 디스크의 파일이다
REGISTRY = [
    {"upstream": "gravmag", "tag": "EARTH", "title": "온 세계 지구물리 격자 — EMAG2v3·EIGEN-6C4", "local": True},
]
