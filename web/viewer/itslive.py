"""NASA ITS_LIVE 빙하 유속 v2 로 나가는 문 — 120 m 모자이크 COG 에서 **필요한 몫만 Range 로** 받아 칠해 둔다 (wetherilli 433).

ITS_LIVE(NASA MEaSUREs, JPL) v2 정적 모자이크는 위성 영상 쌍의 특징 추적을 여러 해 이은 유속 합성이다. AWS 공개 자료 등록부에
**CC0** 로 올라 있다. RGI 지역마다 COG 하나 — 남극(`RGI19A`, 3031, 5 GB)·그린란드(`RGI05A`, 3413, 0.9 GB)·스발바르(`RGI07A`, 3413,
30 MB). 이름은 2026-10-29 에 버킷 목록으로 확인했다. CORS 가 없어 화면이 곧장 받지 못하고, 받아 칠해 둔 타일을 우리가 낸다.

- **COG 를 통째로 받지 않는다.** 머리(IFD)를 읽고 고른 개관 한 겹의 타일만 Range 로 받는다 — 남극은 480 m 개관(240 MB)을 온 대륙에,
  120 m 원판은 두 기지 둘레(장보고·세종)의 네모만. 그린란드는 240 m 개관, 스발바르는 120 m 원판을 통째로(작다). 붙은 타일은 한 번에
  묻는다(`_ranges`). 1 초 간격, 차단 조짐이면 멈춘다
- COG 는 BigTIFF·LZW·float32·512 칸 타일이다. LZW 는 Pillow(libtiff)가 푼다 — 타일 하나를 띠 하나짜리 작은 TIFF 로 싸서 연다(`_decode`).
  빈 곳은 −32767
- **격자는 GIBS 빙하 속도(413)와 같다** — 원점 (−4 194 304, 4 194 304), 512 칸, 줌 0 이 8 192 m. 줌 6 이 128 m 다. 지역마다 구운 줌보다
  가까우면 서버가 윗 타일을 잘라 늘려 낸다(`read_tile`) — 기지 둘레만 고운 칸이 있다
- 색은 413(MEaSUREs, GIBS 색표)과 같은 **jet 를 log10(1 + v) 에, 0–5 600 m/년** — 413 과 켜서 견주면 같은 색이 같은 빠르기다. 범례도
  GIBS 의 그림을 그대로 쓴다
- 칠하기에 numpy 를 쓴다 — **굽기(`manage.py build_itslive`)는 호스트에서만**(`run.sh`). 제품은 구운 WebP 와 누른 자리의 int16 만 읽는다
"""
import io
import json
import logging
import math
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from django.conf import settings

from . import geomap, usage

log = logging.getLogger(__name__)

UPSTREAM = "itslive"
FORMAT = "webp"
TILE = 512
ORIGIN = 4194304.0
TOP_RES = 8192.0                  # 줌 0 의 한 칸(m) — GIBS 500m 판과 같다
MAX_ZOOM = 6                      # 128 m
NODATA = -32767.0
#: 색의 끝 — GIBS MEaSUREs 색표의 끝과 같다
VMAX = 5600.0
PAUSE = 1.0
#: 붙은 타일을 한 번에 묻는 한도
MERGE_GAP = 1 << 16
MERGE_MAX = 64 << 20
#: 누른 자리 값 파일의 칸 수 한도 — 넘으면 칸을 건너뛰어 적는다
VALUE_CELLS = 40_000_000
ATTRIBUTION = ('<a href="https://its-live.jpl.nasa.gov/" target="_blank" rel="noopener">ITS_LIVE</a> v2 velocity mosaic '
               '(NASA MEaSUREs, JPL; <a href="https://registry.opendata.aws/its-live-data/" target="_blank" rel="noopener">AWS</a>, CC0)')


class ItsLiveError(RuntimeError):
    pass


@dataclass(frozen=True)
class Region:
    rgi: str                      # COG 이름의 RGI 지역
    epsg: str
    base_ifd: int                 # 온 지역에 쓰는 겹 (0 이 120 m 원판, 하나 오를 때마다 두 배)
    base_zoom: int                # 그 겹으로 자르는 마지막 줌
    boxes: tuple = ()             # 원판으로 더 곱게 자를 네모 — (이름, 경도, 위도, 반 너비 m)
    legend: str = "MEaSUREs_Ice_Velocity_Antarctica"

    def url(self) -> str:
        return f"{settings.ITSLIVE_URL.rstrip('/')}/ITS_LIVE_velocity_120m_{self.rgi}_0000_v02_v.tif"


REGIONS = {
    "antarctica": Region("RGI19A", "3031", 2, 4,
                         boxes=(("jangbogo", 163.0, -75.0, 160000.0), ("sejong", -58.8, -62.2, 60000.0))),
    "greenland": Region("RGI05A", "3413", 1, 5, legend="MEaSUREs_Ice_Velocity_Greenland"),
    "svalbard": Region("RGI07A", "3413", 0, 6, legend="MEaSUREs_Ice_Velocity_Greenland"),
}
LAYERS = {f"{UPSTREAM}:{name}": name for name in REGIONS}


def root() -> Path:
    return Path(settings.ITSLIVE_DIR)


def region_dir(region: str) -> Path:
    return root() / region


def tiles_dir(region: str) -> Path:
    return region_dir(region) / "tiles"


def available(region: str) -> bool:
    return tiles_dir(region).is_dir()


def resolution(z: int) -> float:
    return TOP_RES / 2 ** z


def tile_bbox(z: int, x: int, y: int) -> tuple:
    span = TILE * resolution(z)
    west, north = -ORIGIN + x * span, ORIGIN - y * span
    return west, north - span, west + span, north


def tile_count(z: int) -> int:
    """한 변의 칸 수 — 줌 0 이 2×2 장이다(GIBS 극지 격자)"""
    return 2 ** (z + 1)


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < tile_count(z) and 0 <= y < tile_count(z)


def grid() -> dict:
    """화면이 받을 격자 — `basemaps.gibs_overlay_grid` 와 같고 줌만 더 간다"""
    return {"origin": [-ORIGIN, ORIGIN], "extent": [-ORIGIN, -ORIGIN, ORIGIN, ORIGIN], "tileSize": TILE,
            "resolutions": [resolution(z) for z in range(MAX_ZOOM + 1)]}


def legend_url(region: str) -> str:
    """GIBS 의 가로 범례(413 과 같은 그림) — 색이 같으므로 범례도 같다"""
    return f"{settings.GIBS_URL.rstrip('/')}/legends/{REGIONS[region].legend}_H.svg"


# ── 투영 ─────────────────────────────────────────────────────────────

_A, _E = 6378137.0, 0.0818191908426215


def _t(phi):
    s = _E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_E / 2)


def lonlat_to_3413(lon: float, lat: float) -> tuple:
    """위경도 → EPSG:3413 (북극 평사도법, 표준위도 70°N, 중앙 경선 45°W)"""
    ts = math.radians(70.0)
    mc = math.cos(ts) / math.sqrt(1 - (_E * math.sin(ts)) ** 2)
    rho = _A * mc * _t(math.radians(lat)) / _t(ts)
    lam = math.radians(lon + 45.0)
    return rho * math.sin(lam), -rho * math.cos(lam)


def to_xy(epsg: str, lon: float, lat: float) -> tuple:
    return geomap.lonlat_to_3031(lon, lat) if epsg == "3031" else lonlat_to_3413(lon, lat)


# ── 칠하기 ───────────────────────────────────────────────────────────

def jet(t: float) -> tuple:
    """matplotlib jet — 0…1 → RGB"""
    def ch(x):
        return round(255 * max(0.0, min(1.0, 1.5 - abs(4 * t - x))))
    return ch(3), ch(2), ch(1)


def index_of(v: float) -> int:
    """m/년 → 칸 번호 1…255 (0 은 빈 곳)"""
    t = math.log10(1 + max(0.0, min(VMAX, v))) / math.log10(1 + VMAX)
    return 1 + round(t * 254)


def palette() -> list:
    out = [0, 0, 0]
    for i in range(1, 256):
        out += jet((i - 1) / 254)
    return out


# ── 받기 ─────────────────────────────────────────────────────────────

def _get(url: str, start: int, end: int) -> bytes:
    """`start`…`end`(끝 포함) 바이트. 206 이 아니면 멈춘다"""
    try:
        r = requests.get(url, timeout=(settings.UPSTREAM_TIMEOUT, 300), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1", "Range": f"bytes={start}-{end}"})
    except requests.RequestException as exc:
        usage.record(UPSTREAM, ok=False)
        raise ItsLiveError(f"ITS_LIVE 에 닿지 못했다: {exc}") from exc
    blocked = usage.looks_blocked(r.status_code, r.content[:200])
    usage.record(UPSTREAM, ok=r.status_code == 206, blocked=blocked)
    if blocked or r.status_code != 206:
        raise ItsLiveError(f"ITS_LIVE 가 {r.status_code} 를 주었다 — 멈춘다")
    if len(r.content) != end - start + 1:
        raise ItsLiveError(f"{end - start + 1} 바이트를 물었는데 {len(r.content)} 가 왔다")
    return r.content


# ── COG 머리 ─────────────────────────────────────────────────────────

_TYPES = {3: ("H", 2), 4: ("I", 4), 12: ("d", 8), 16: ("Q", 8)}


def parse_ifds(head: bytes) -> list:
    """BigTIFF 머리 → 겹마다 `{"w", "h", "tw", "th", "offsets", "counts", "res", "x0", "ytop"}`. 원판(첫 겹)만 좌표가 있고
    개관은 그것을 나눈다. 표가 머리 밖에 있으면 ItsLiveError — 부르는 쪽이 더 받아 다시 부른다"""
    if head[:4] != b"II+\x00":
        raise ItsLiveError("작은 끝 BigTIFF 가 아니다")
    off = struct.unpack_from("<Q", head, 8)[0]
    out = []
    while off:
        if off + 8 > len(head):
            raise ItsLiveError("머리가 짧다")
        n = struct.unpack_from("<Q", head, off)[0]
        tags = {}
        for i in range(n):
            tag, typ, count = struct.unpack_from("<HHQ", head, off + 8 + 20 * i)
            if typ not in _TYPES:
                continue
            fmt, size = _TYPES[typ]
            at = off + 8 + 20 * i + 12
            if size * count > 8:
                at = struct.unpack_from("<Q", head, at)[0]
            if at + size * count > len(head):
                raise ItsLiveError("머리가 짧다")
            tags[tag] = struct.unpack_from(f"<{count}{fmt}", head, at)
        off = struct.unpack_from("<Q", head, off + 8 + 20 * n)[0]
        if tags.get(259, (0,))[0] != 5 or tags.get(339, (0,))[0] != 3 or tags.get(258, (0,))[0] != 32:
            raise ItsLiveError("LZW·float32 가 아니다")
        if tags.get(317, (1,))[0] != 1:
            raise ItsLiveError("예측자가 붙어 있다")
        out.append({"w": tags[256][0], "h": tags[257][0], "tw": tags[322][0], "th": tags[323][0],
                    "offsets": tags[324], "counts": tags[325], "scale": tags.get(33550), "tie": tags.get(33922)})
    if not out or not out[0]["scale"] or not out[0]["tie"]:
        raise ItsLiveError("원판의 좌표(ModelPixelScale·ModelTiepoint)가 없다")
    res0, left, top = out[0]["scale"][0], out[0]["tie"][3], out[0]["tie"][4]
    for level in out:
        level["res"] = res0 * out[0]["w"] / level["w"]
        level["x0"], level["ytop"] = left, top                 # 왼쪽 위 칸의 가장자리
    return out


def read_head(url: str, size: int = 1 << 17) -> list:
    """머리를 받아 겹을 읽는다 — 표가 머리 밖이면 두 배씩 더 받는다"""
    while True:
        head = _get(url, 0, size - 1)
        try:
            return parse_ifds(head)
        except ItsLiveError as exc:
            if "짧다" not in str(exc) or size >= 1 << 24:
                raise
        size *= 2
        time.sleep(PAUSE)


def _wrap(data: bytes, w: int, h: int) -> bytes:
    """LZW 타일 하나 → 띠 하나짜리 TIFF (Pillow 가 libtiff 로 푼다)"""
    tags = [(256, 4, w), (257, 4, h), (258, 3, 32), (259, 3, 5), (262, 3, 1), (273, 4, 0), (277, 3, 1),
            (278, 4, h), (279, 4, len(data)), (317, 3, 1), (339, 3, 3)]
    start = 8 + 2 + 12 * len(tags) + 4
    out = bytearray(b"II*\x00" + struct.pack("<IH", 8, len(tags)))
    for tag, typ, value in tags:
        value = start if tag == 273 else value
        out += struct.pack("<HHI", tag, typ, 1) + (struct.pack("<HH", value, 0) if typ == 3 else struct.pack("<I", value))
    return bytes(out + b"\0\0\0\0" + data)


def _decode(data: bytes, w: int, h: int):
    from PIL import Image
    image = Image.open(io.BytesIO(_wrap(data, w, h)))
    image.load()
    if image.mode != "F":
        raise ItsLiveError(f"float32 가 아닌 {image.mode} 로 풀렸다")
    return image


def _ranges(wanted: list) -> list:
    """(타일 번호, 자리, 크기) → 붙은 것끼리 묶은 [(시작, 끝, [(번호, 자리, 크기)…])]"""
    groups = []
    for item in sorted(wanted, key=lambda t: t[1]):
        _, off, count = item
        if groups and off - groups[-1][1] <= MERGE_GAP and off + count - groups[-1][0] <= MERGE_MAX:
            groups[-1][1] = max(groups[-1][1], off + count)
            groups[-1][2].append(item)
        else:
            groups.append([off, off + count, [item]])
    return [(a, b - 1, items) for a, b, items in groups]


def read_window(url: str, level: dict, box=None, log_line=print):
    """한 겹의 네모(3031·3413 미터, 없으면 온 겹)를 받아 numpy float32 로 — (배열, 왼쪽 가장자리, 위 가장자리, 칸)"""
    import numpy as np
    res, tw, th = level["res"], level["tw"], level["th"]
    cols, rows = math.ceil(level["w"] / tw), math.ceil(level["h"] / th)
    if box:
        west, south, east, north = box
        c0 = max(0, int((west - level["x0"]) // (res * tw)))
        c1 = min(cols - 1, int((east - level["x0"]) // (res * tw)))
        r0 = max(0, int((level["ytop"] - north) // (res * th)))
        r1 = min(rows - 1, int((level["ytop"] - south) // (res * th)))
    else:
        c0, c1, r0, r1 = 0, cols - 1, 0, rows - 1
    if c1 < c0 or r1 < r0:
        raise ItsLiveError("네모가 격자 밖이다")
    out = np.full(((r1 - r0 + 1) * th, (c1 - c0 + 1) * tw), np.nan, dtype=np.float32)
    wanted = [(r * cols + c, level["offsets"][r * cols + c], level["counts"][r * cols + c])
              for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if level["counts"][r * cols + c]]
    groups = _ranges(wanted)
    got = 0
    for n, (start, end, items) in enumerate(groups):
        if n:
            time.sleep(PAUSE)
        blob = _get(url, start, end)
        got += len(blob)
        for index, off, count in items:
            r, c = divmod(index, cols)
            a = np.asarray(_decode(blob[off - start:off - start + count], tw, th), dtype=np.float32)
            a = np.where(a <= NODATA + 1, np.nan, a)
            out[(r - r0) * th:(r - r0 + 1) * th, (c - c0) * tw:(c - c0 + 1) * tw] = a
        if n % 20 == 0:
            log_line(f"  {n + 1}/{len(groups)} 번째 묶음, 받은 것 {got / 1e6:,.0f} MB")
    # 오른쪽·아래 끝 타일은 겹 밖까지 0 으로 덧대어 있다 — 겹의 크기로 자른다(0 은 빈 곳이 아니라 "멈춘 얼음" 으로 칠해진다)
    out = out[:level["h"] - r0 * th, :level["w"] - c0 * tw]
    return out, level["x0"] + c0 * tw * res, level["ytop"] - r0 * th * res, res, got


# ── 굽기 — 호스트에서만 (numpy) ────────────────────────────────────────

def _colour(values):
    """float32 배열 → Pillow RGBa(미리 곱한) 그림"""
    import numpy as np
    from PIL import Image
    v = np.clip(np.nan_to_num(values, nan=-1.0), -1.0, VMAX)
    t = np.log10(1 + np.clip(v, 0, None)) / math.log10(1 + VMAX)
    index = np.where(v < 0, 0, 1 + np.rint(t * 254)).astype(np.uint8)
    image = Image.fromarray(index, "P")
    image.putpalette(palette())
    image.info["transparency"] = 0
    return image.convert("RGBA").convert("RGBa")


def _cut(full, left, top, res, z, x, y):
    """GIBS 격자 칸 하나를 그림에서 — 다 투명하면 None"""
    from PIL import Image
    west, south, east, north = tile_bbox(z, x, y)
    l, t, r, b = (west - left) / res, (top - north) / res, (east - left) / res, (top - south) / res
    w, h = full.size
    cl, ct, cr, cb = max(l, 0), max(t, 0), min(r, w), min(b, h)
    if cr <= cl or cb <= ct:
        return None
    px = TILE / (r - l)
    ox, oy = round((cl - l) * px), round((ct - t) * px)
    ow, oh = round((cr - l) * px) - ox, round((cb - t) * px) - oy
    if ow < 1 or oh < 1:
        return None
    method = Image.BILINEAR if px >= 1 else Image.BOX
    piece = full.resize((ow, oh), method, box=(cl, ct, cr, cb))
    tile = Image.new("RGBa", (TILE, TILE), (0, 0, 0, 0))
    tile.paste(piece, (ox, oy))
    tile = tile.convert("RGBA")
    return tile if tile.getchannel("A").getbbox() else None


def _tiles_over(left, top, res, w, h, z):
    span = TILE * resolution(z)
    x0, x1 = int((left + ORIGIN) // span), int((left + w * res + ORIGIN) // span)
    y0, y1 = int((ORIGIN - top) // span), int((ORIGIN - (top - h * res)) // span)
    for x in range(max(0, x0), min(tile_count(z) - 1, x1) + 1):
        for y in range(max(0, y0), min(tile_count(z) - 1, y1) + 1):
            yield x, y


def _write_piece(values, left, top, res, zooms, fresh: Path) -> int:
    full = _colour(values)
    written = 0
    for z in zooms:
        for x, y in _tiles_over(left, top, res, full.size[0], full.size[1], z):
            tile = _cut(full, left, top, res, z, x, y)
            if tile is None:
                continue
            target = fresh / str(z) / str(x) / f"{y}.{FORMAT}"
            target.parent.mkdir(parents=True, exist_ok=True)
            tile.save(target, format="WEBP", quality=85, method=4)
            written += 1
    return written


def _write_values(values, left, top, res, path: Path) -> dict:
    """누른 자리 — 정수 m/년(int16, 빈 곳 −32768), 위에서 아래로. 너무 크면 칸을 건너뛴다"""
    import numpy as np
    step = max(1, math.ceil(math.sqrt(values.size / VALUE_CELLS)))
    sub = values[::step, ::step]
    ints = np.where(np.isnan(sub), -32768, np.clip(np.rint(sub), 0, 32767)).astype("<i2")
    path.write_bytes(ints.tobytes())
    return {"file": path.name, "x0": left, "ytop": top, "res": res * step, "ne": int(sub.shape[1]), "nv": int(sub.shape[0])}


def build(region: str, out_dir=None, log_line=print) -> dict:
    """한 지역을 받아 칠해 `<ITSLIVE_DIR>/<지역>/{tiles/, *.i16, meta.json}` 으로. `manage.py build_itslive` 가 부른다"""
    import shutil
    spec = REGIONS[region]
    out = Path(out_dir) if out_dir else region_dir(region)
    out.mkdir(parents=True, exist_ok=True)
    fresh = out / "tiles.new"
    shutil.rmtree(fresh, ignore_errors=True)
    fresh.mkdir()
    url = spec.url()
    levels = read_head(url)
    time.sleep(PAUSE)
    base = levels[spec.base_ifd]
    log_line(f"{region}: {base['w']}×{base['h']} 칸, 한 칸 {base['res']:g} m 겹을 받는다")
    values, left, top, res, got = read_window(url, base, log_line=log_line)
    pieces = [dict(_write_values(values, left, top, res, out / "base.i16.new"), name="base")]
    tiles = _write_piece(values, left, top, res, range(spec.base_zoom + 1), fresh)
    del values
    for name, lon, lat, half in spec.boxes:
        time.sleep(PAUSE)
        cx, cy = to_xy(spec.epsg, lon, lat)
        log_line(f"{region}/{name}: 원판 {levels[0]['res']:g} m 의 네모를 받는다")
        values, left, top, res, more = read_window(url, levels[0], (cx - half, cy - half, cx + half, cy + half), log_line)
        got += more
        pieces.append(dict(_write_values(values, left, top, res, out / f"{name}.i16.new"), name=name))
        tiles += _write_piece(values, left, top, res, range(spec.base_zoom + 1, MAX_ZOOM + 1), fresh)
        del values
    for piece in pieces:
        (out / piece["file"]).replace(out / piece["file"].removesuffix(".new"))
        piece["file"] = piece["file"].removesuffix(".new")
    meta = {"region": region, "epsg": spec.epsg, "base_zoom": spec.base_zoom, "source": url.rsplit("/", 1)[-1],
            "pieces": pieces[1:] + pieces[:1]}              # 고운 네모를 먼저 본다
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    old = out / "tiles.old"
    shutil.rmtree(old, ignore_errors=True)
    if (out / "tiles").exists():
        (out / "tiles").rename(old)
    fresh.rename(out / "tiles")
    shutil.rmtree(old, ignore_errors=True)
    return {"tiles": tiles, "mb_in": round(got / 1e6, 1)}


# ── 내주기 ───────────────────────────────────────────────────────────

def _stored(region: str, z: int, x: int, y: int):
    try:
        return (tiles_dir(region) / str(z) / str(x) / f"{y}.{FORMAT}").read_bytes()
    except FileNotFoundError:
        return None


def read_tile(region: str, z: int, x: int, y: int):
    """타일 한 장(WebP). 구운 줌보다 가까우면 가장 가까운 윗 타일을 잘라 늘린다 — 기지 둘레 밖의 줌 5·6 이 그렇다. 없으면 None"""
    data = _stored(region, z, x, y)
    if data is not None:
        return data
    for up in range(1, z + 1):
        parent = _stored(region, z - up, x >> up, y >> up)
        if parent is None:
            continue
        from PIL import Image
        n = 2 ** up
        part = TILE / n
        ox, oy = (x % n) * part, (y % n) * part
        image = Image.open(io.BytesIO(parent)).convert("RGBA")
        box = (ox, oy, ox + part, oy + part)
        if image.crop(tuple(round(v) for v in box)).getchannel("A").getbbox() is None:
            return None                                       # 그 몫이 비었다 — 이웃 칸이 번진 것을 내지 않는다
        piece = image.resize((TILE, TILE), Image.BILINEAR, box=box)
        buf = io.BytesIO()
        piece.save(buf, format="WEBP", quality=85, method=2)
        return buf.getvalue()
    return None


_metas = {}


def _meta(region: str) -> dict:
    path = region_dir(region) / "meta.json"
    mtime = path.stat().st_mtime
    hit = _metas.get(path)
    if hit is None or hit[0] != mtime:
        hit = _metas[path] = (mtime, json.loads(path.read_text(encoding="utf-8")))
    return hit[1]


def value_at(region: str, lat: float, lon: float):
    """누른 자리의 유속(정수 m/년). 고운 네모부터 본다. 자료 밖·빈 곳·파일 없음은 None"""
    try:
        meta = _meta(region)
    except (OSError, ValueError):
        return None
    x, y = to_xy(meta["epsg"], lon, lat)
    for piece in meta["pieces"]:
        col = int((x - piece["x0"]) // piece["res"])
        row = int((piece["ytop"] - y) // piece["res"])
        if not (0 <= col < piece["ne"] and 0 <= row < piece["nv"]):
            continue
        try:
            with open(region_dir(region) / piece["file"], "rb") as f:
                f.seek(2 * (row * piece["ne"] + col))
                raw = f.read(2)
        except OSError:
            return None
        if len(raw) == 2:
            n = struct.unpack("<h", raw)[0]
            if n != -32768:
                return n
    return None


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": UPSTREAM, "tag": "ITS_LIVE", "title": "NASA ITS_LIVE"},
]
