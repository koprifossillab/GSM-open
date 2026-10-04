"""남극 자력 이상 ADMAP-2 — Geosoft 격자를 **우리가 칠해 3031 타일로 잘라 둔다** (wetherilli 262).

ADMAP-2(Golynsky 외 2018, GRL doi:10.1029/2018GL078153, PANGAEA 892723, **CC BY 3.0**)는 남극 항공·선박 자력 탐사를 이어 붙인
1.5 km 격자다. 서비스가 없고 `hs.pangaea.de/mag/airborne/Antarctica/grid.zip`(179 MB, 격자 44 개)뿐이라 IBCSO(047)처럼 받아
굽는다. 상류가 아니라 **우리 디스크의 파일**이라 문이 아니다. 원본은 NAS `N:\\GSM\\sources\\admap2\\`, 구운 것은 `GSM_ADMAP_DIR`
(기본 `<DB 옆>/admap2`). 파일이 없어도 뷰어는 돌고 타일 자리에 안내가 뜬다.

- **쓰는 격자는 `ADMAP_2B_2017.grd` 하나** — 모든 탐사를 이은 합본이다(나머지는 탐사마다의 조각, `_s` 는 다듬은 판, `_R9` 는 다른 줄임).
  4 567×4 568 칸, 한 칸 1 500 m, 극 평사도법(WGS84·표준위도 −71° — 3031 과 같다). 격자의 가운데가 극에서 1.5 km·0.75 km 안에 든다
- **Geosoft 이진 격자를 numpy 없이 읽는다.** 머리 512 바이트(원소 크기 ES·부호 SF·한 줄 칸 수 NE·줄 수 NV·KX, 다음 칸 간격·원점·회전…),
  ES 에 1024 가 더해져 있으면 압축판이다 — 압축 머리(`0xF8E7D8C7`, 방식, 덩이 수, 덩이마다 줄 수) 다음에 덩이의 자리(int64)·크기(int32)가
  오고, 덩이마다 16 바이트 머리 뒤가 zlib 이다. 값은 float32, 빈 곳은 −1e32(Geosoft 의 dummy). 원점은 **왼쪽 아래** 칸의 가운데이고
  줄은 아래에서 위로 쌓인다
- 칠하기: 자력 이상의 흔한 무지개(파랑 → 초록 → 노랑 → 빨강 → 자홍). ±600 nT 를 끝으로 두되 **제곱근으로 늘여** 0 언저리의 작은 이상도
  색이 갈리게 한다. 범례는 갈래 표(`classLegend`) — 그림이 아니다(컨테이너에 한글 글꼴이 없다, IBCSO TID 와 같다)
- 타일은 GeoMAP 의 3031 격자, 줌 4(1 627 m)까지 자른다 — 원본 한 칸이 1 500 m 라 그 위는 화면이 늘린다
- 누른 자리: 칸마다 정수 nT 를 int16 으로 적은 `values.i16`(42 MB, 위에서 아래로)에서 한 칸을 읽는다
그리는 법을 고치면 다시 굽는다 — 타일 주소의 판은 폴더의 고친 때다(`views._dir_version`).
"""
import io
import json
import math
import struct
import zlib
from array import array
from pathlib import Path

from django.conf import settings

from . import geomap

NAME = "admap:anomaly"
GRID = "ADMAP_2B_2017.grd"
FORMAT = "webp"
TILE = geomap.TILE
MAX_ZOOM = 4
DUMMY = -1e30                     # 이보다 작으면 빈 곳(Geosoft dummy −1e32)
NODATA = -32768
#: 색의 끝 — 이 nT 를 넘으면 끝 색
LIMIT = 600.0
#: (늘인 자리 −1…1, 색) — 늘인 자리는 sign(v)·sqrt(|v|/LIMIT)
RAMP = ((-1.0, (35, 20, 120)), (-0.7, (30, 70, 200)), (-0.45, (40, 160, 230)), (-0.2, (90, 200, 160)),
        (0.0, (210, 230, 140)), (0.2, (250, 220, 90)), (0.45, (245, 150, 50)), (0.7, (215, 50, 40)), (1.0, (190, 40, 160)))
#: 범례의 칸 (nT)
LEGEND_STOPS = (-600, -300, -150, -50, 0, 50, 150, 300, 600)
ATTRIBUTION = ('ADMAP-2 (Golynsky et al., 2018, <a href="https://doi.org/10.1594/PANGAEA.892723" target="_blank" '
               'rel="noopener">PANGAEA</a>, CC BY 3.0)')


class AdmapError(RuntimeError):
    pass


def root() -> Path:
    return Path(settings.ADMAP_DIR)


def tiles_dir() -> Path:
    return root() / "tiles"


def values_file() -> Path:
    return root() / "values.i16"


def meta_file() -> Path:
    return root() / "meta.json"


def available() -> bool:
    return tiles_dir().is_dir()


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def read_tile(z: int, x: int, y: int):
    try:
        return (tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}").read_bytes()
    except FileNotFoundError:
        return None


# ── Geosoft 격자 읽기 ─────────────────────────────────────────────────

def read_grd(data: bytes) -> dict:
    """Geosoft 이진 격자 → `{"ne", "nv", "de", "dv", "x0", "y0", "values"}`. `values` 는 float32 `array`, 줄은 **아래에서 위로**."""
    if len(data) < 512:
        raise AdmapError("격자 머리가 짧다")
    es, sf, ne, nv, kx = struct.unpack_from("<5i", data, 0)
    de, dv, x0, y0, rot, zbase, zmult = struct.unpack_from("<7d", data, 20)
    compressed = es >= 1024
    if es % 1024 != 4 or sf != 2:
        raise AdmapError(f"float32 격자가 아니다 (ES={es}, SF={sf})")
    if kx != 1 or rot:
        raise AdmapError(f"줄이 가로가 아니거나 돌아 있다 (KX={kx}, ROT={rot})")
    if ne <= 0 or nv <= 0:
        raise AdmapError("격자 크기가 맞지 않다")
    raw = bytearray()
    if compressed:
        magic, _, nblocks, _ = struct.unpack_from("<Ii2i", data, 512)
        if magic != 0xF8E7D8C7:
            raise AdmapError(f"압축 머리가 아니다 ({magic:#x})")
        offs = struct.unpack_from(f"<{nblocks}q", data, 528)
        sizes = struct.unpack_from(f"<{nblocks}i", data, 528 + 8 * nblocks)
        for off, size in zip(offs, sizes):
            raw += zlib.decompress(data[off + 16:off + size])        # 덩이 머리 16 바이트 뒤가 zlib
    else:
        raw += data[512:512 + 4 * ne * nv]
    if len(raw) != 4 * ne * nv:
        raise AdmapError(f"값이 {len(raw)} 바이트다 — {4 * ne * nv} 를 기다렸다")
    values = array("f")
    values.frombytes(bytes(raw))
    if zmult not in (0.0, 1.0) or zbase:
        values = array("f", (v if v < DUMMY else v / zmult + zbase for v in values))
    return {"ne": ne, "nv": nv, "de": de, "dv": dv, "x0": x0, "y0": y0, "values": values}


# ── 칠하기 ───────────────────────────────────────────────────────────

def stretch(nt: float) -> float:
    """nT → 늘인 자리 −1…1"""
    s = math.copysign(math.sqrt(min(abs(nt), LIMIT) / LIMIT), nt)
    return max(-1.0, min(1.0, s))


def ramp_color(s: float) -> tuple:
    for (s0, c0), (s1, c1) in zip(RAMP, RAMP[1:]):
        if s <= s1:
            t = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
            return tuple(round(a + (b - a) * max(0.0, min(1.0, t))) for a, b in zip(c0, c1))
    return RAMP[-1][1]


def palette() -> list:
    """칸 번호 0(빈 곳) · 1…255 → RGB. 번호 i 는 늘인 자리 −1 + 2(i−1)/254"""
    out = [0, 0, 0]
    for i in range(1, 256):
        out += ramp_color(-1.0 + 2.0 * (i - 1) / 254.0)
    return out


def index_of(nt: int) -> int:
    return 1 + round((stretch(nt) + 1.0) / 2.0 * 254.0)


def legend(lang: str = "ko") -> dict:
    """범례 — 칸마다 (이름, 색). 화면이 HTML 로 그린다(`classLegend`)"""
    from . import i18n
    rows = [{"code": v, "label": f"{v:+,} nT" if v else "0 nT", "color": "#%02x%02x%02x" % ramp_color(stretch(v))}
            for v in LEGEND_STOPS]
    return {"groups": [{"name": i18n.t(i18n.msg("자력 이상"), lang), "rows": rows}], "attribution": ATTRIBUTION}


# ── 굽기 ─────────────────────────────────────────────────────────────

def build(source, out_dir=None, log=print) -> dict:
    """ADMAP-2 zip(또는 .grd 하나) → `values.i16`·`meta.json`·`tiles/`. `manage.py build_admap` 이 부른다."""
    import shutil
    import zipfile

    from PIL import Image
    src = Path(source)
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as zf:
            name = next((n for n in zf.namelist() if n.rsplit("/", 1)[-1] == GRID), None)
            if name is None:
                raise AdmapError(f"zip 에 {GRID} 가 없다")
            data = zf.read(name)
    else:
        data = src.read_bytes()
    grid = read_grd(data)
    del data
    ne, nv = grid["ne"], grid["nv"]
    out = Path(out_dir) if out_dir else root()
    out.mkdir(parents=True, exist_ok=True)

    # 정수 nT(위에서 아래로)와 칸 번호를 한 번에 — 줄을 뒤집어 그림의 차례로
    lut = {}
    ints = array("h")
    index = bytearray()
    vals = grid["values"]
    for row in range(nv - 1, -1, -1):
        for v in vals[row * ne:(row + 1) * ne]:
            if v < DUMMY:
                ints.append(NODATA)
                index.append(0)
                continue
            n = max(-32767, min(32767, round(v)))
            ints.append(n)
            i = lut.get(n)
            if i is None:
                i = lut[n] = index_of(n)
            index.append(i)
    del vals, grid["values"]
    (out / "values.i16.new").write_bytes(ints.tobytes())
    (out / "values.i16.new").replace(out / "values.i16")
    top = grid["y0"] + (nv - 1) * grid["dv"]
    meta = {"ne": ne, "nv": nv, "res": grid["de"], "x0": grid["x0"], "ytop": top, "source": GRID}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    valid = [n for n in ints if n != NODATA]
    stats = {"cells": len(valid), "min": min(valid), "max": max(valid)}
    del ints, valid
    log(f"격자 {ne}×{nv}, 값이 있는 칸 {stats['cells']:,} ({stats['min']} … {stats['max']} nT)")

    image = Image.frombytes("P", (ne, nv), bytes(index))
    del index
    image.putpalette(palette())
    image.info["transparency"] = 0
    full = image.convert("RGBA").convert("RGBa")           # 줄일 때 투명한 가장자리가 번지지 않게 미리 곱한다
    del image

    tiles = out / "tiles"
    fresh = out / "tiles.new"
    shutil.rmtree(fresh, ignore_errors=True)
    written = size = 0
    for z in range(MAX_ZOOM, -1, -1):
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
    old = out / "tiles.old"
    shutil.rmtree(old, ignore_errors=True)
    if tiles.exists():
        tiles.rename(old)
    fresh.rename(tiles)
    shutil.rmtree(old, ignore_errors=True)
    stats.update(tiles=written, mb=round(size / 1e6, 1))
    return stats


def source_box(meta: dict, z: int, x: int, y: int) -> tuple:
    """3031 타일이 원본에서 차지하는 화소 네모 (왼, 위, 오른, 아래). 원점은 칸의 가운데라 반 칸 옮긴다"""
    west, south, east, north = geomap.tile_bbox(z, x, y)
    res, left0, top0 = meta["res"], meta["x0"] - meta["res"] / 2, meta["ytop"] + meta["res"] / 2
    return (west - left0) / res, (top0 - north) / res, (east - left0) / res, (top0 - south) / res


def cut(level_image, factor: int, meta: dict, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). 다 투명하면 None — IBCSO 의 `cut` 과 같은 꼴"""
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

_meta = None


def _load_meta() -> dict:
    global _meta
    if _meta is None or _meta[0] != meta_file().stat().st_mtime:
        _meta = (meta_file().stat().st_mtime, json.loads(meta_file().read_text(encoding="utf-8")))
    return _meta[1]


def value_at(lat: float, lon: float):
    """누른 자리의 자력 이상(정수 nT). 자료 밖·빈 곳·파일 없음은 None"""
    try:
        meta = _load_meta()
    except (OSError, ValueError):
        return None
    x, y = geomap.lonlat_to_3031(lon, lat)
    col = round((x - meta["x0"]) / meta["res"])
    row = round((meta["ytop"] - y) / meta["res"])
    if not (0 <= col < meta["ne"] and 0 <= row < meta["nv"]):
        return None
    try:
        with open(values_file(), "rb") as f:
            f.seek(2 * (row * meta["ne"] + col))
            raw = f.read(2)
    except OSError:
        return None
    if len(raw) != 2:
        return None
    n = struct.unpack("<h", raw)[0]
    return None if n == NODATA else n
