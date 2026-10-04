"""표고로 나가는 문 — 시료 고도 붙이기(P03)와 3D 의 일본 지형(031).

상류는 셋이고 모두 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나").

| 상류 | 무엇 | 쓰는 곳 | 높이 기준 |
|---|---|---|---|
| AWS Terrain Tiles (Terrarium) | 전 지구 z/x/y PNG, SRTM 약 30 m | 그 밖 전부. 3D 가 브라우저에서 곧장도 부른다 | 해발 (EGM96) |
| 국토지리원 표고 타일 (`dem_png`) | 일본, 기반지도정보 10 m | 일본의 시료, 3D 의 일본 지형 | 해발 (일본 지오이드) |
| PGC ArcticDEM·REMA (ImageServer) | 북위·남위 60° 너머, 2 m 모자이크 | 극지의 시료 | 해발 (`Height Orthometric`) |

**PGC 는 기본값이 타원체고다.** `identify` 에 `Height Orthometric` 을 붙여야 해발이 온다 —
2026-09-29 에 Summit Station 이 3 254 m(타원체고)와 3 210 m(해발, 알려진 값 3 216 m),
McMurdo 가 −39 m 와 14 m 로 갈렸다. `getSamples` 는 여러 점을 한 번에 받지만 이 함수를
듣지 않아 쓰지 않는다. 한 점에 한 번이고, 사이를 둔다.

3D 의 남극 바다·빙저는 IBCSO v2 수치 격자(우리가 잘라 둔 것, `ibcso.py`)를 Terrarium 으로 펴서 낸다(051) —
상류가 아니지만 AWS 로 메우는 일이 여기 있어 이 파일에 둔다.

받은 타일은 `tilecache` 에 담고 스스로 지우지 않는다(007). 자료가 없다는 대답(404)도
담는다 — 한국 자리를 국토지리원에 거듭 묻지 않게.
"""
import io
import json
import logging
import math
import threading
import time

import requests
from django.conf import settings
from PIL import Image

from . import tilecache, usage

log = logging.getLogger(__name__)

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
GSI_DEM_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png"
PGC_URL = "https://di-pgc.img.arcgis.com/arcgis/rest/services/{service}/ImageServer/identify"

#: 시료에 쓰는 줌. Terrarium z12 는 북위 37° 에서 한 픽셀 30 m 남짓 — SRTM 해상도다.
#: 국토지리원 `dem_png` 는 z14 가 끝이고 10 m 격자다
TERRARIUM_ZOOM = 12
GSI_ZOOM = 14
#: 이 위도 너머는 PGC 에 묻는다
POLAR_LAT = 60.0
#: PGC 에 묻는 사이(초). 한 점에 한 번이라 한도를 재지 않는 빠르기로 간다(010)
PGC_PAUSE = 0.2

#: 출처 → (화면에 적는 이름, 높이 기준). 값은 `Point.elev_source`·`elev_datum` 에 든다
SOURCES = {
    "aws-terrarium-z12": ("AWS Terrain Tiles (SRTM 등, z12)", "egm96"),
    "gsi-dem-10m": ("국토지리원 표고 타일 (10 m)", "gsi-geoid"),
    "pgc-arcticdem-2m": ("PGC ArcticDEM (2 m, 해발)", "pgc-orthometric"),
    "pgc-rema-2m": ("PGC REMA (2 m, 해발)", "pgc-orthometric"),
}


class ElevationError(RuntimeError):
    pass


def _get(url: str, upstream: str, **kwargs):
    left = usage.paused()
    if left:
        raise ElevationError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"}, **kwargs)
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise ElevationError(f"{upstream} 에 닿지 못했다: {exc}") from exc
    usage.record(upstream, ok=r.status_code in (200, 404),
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


# ── 타일 ────────────────────────────────────────────────────────────

#: 자료가 없다는 대답을 담아 두는 표식
_NONE = b"none"


def _tile(kind: str, url: str, upstream: str, z: int, x: int, y: int):
    """타일 한 장(PNG 바이트). 그 자리에 자료가 없으면 None."""
    key = tilecache.key_text("elev", f"{kind}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    r = _get(url.format(z=z, x=x, y=y), upstream)
    if r.status_code == 404:
        tilecache.put(key, _NONE)
        return None
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise ElevationError(f"{upstream} 가 표고 타일을 주지 않았다 (status={r.status_code})")
    tilecache.put(key, r.content)
    return r.content


def terrarium_tile(z, x, y):
    return _tile("terrarium", TERRARIUM_URL, "aws", z, x, y)


def gsi_tile(z, x, y):
    return _tile("gsi-dem", GSI_DEM_URL, "gsi", z, x, y)


def terrarium_value(rgb) -> float:
    r, g, b = rgb[:3]
    return r * 256 + g + b / 256 - 32768


def gsi_value(rgb):
    """국토지리원 `dem_png` 한 픽셀 → m. (128,0,0) 은 자료 없음, 2^23 넘는 것은 음수다."""
    v = rgb[0] * 65536 + rgb[1] * 256 + rgb[2]
    if v == 2 ** 23:
        return None
    if v > 2 ** 23:
        v -= 2 ** 24
    return v * 0.01


def tile_xy(lat: float, lon: float, z: int) -> tuple:
    """위경도 → 줌 z 의 타일 번호(소수까지)."""
    n = 2 ** z
    lat = max(min(lat, 85.0511), -85.0511)
    x = (lon + 180.0) / 360.0 * n
    rad = math.radians(lat)
    y = (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * n
    return x, y


def _sample(image, fx: float, fy: float, decode):
    """타일 안의 소수 픽셀 자리를 네 이웃으로 쌍선형 보간. 이웃에 빈 칸이 있으면 가장 가까운 값."""
    w, h = image.size
    px, py = fx * w - 0.5, fy * h - 0.5
    x0, y0 = max(0, min(w - 1, int(math.floor(px)))), max(0, min(h - 1, int(math.floor(py))))
    x1, y1 = min(w - 1, x0 + 1), min(h - 1, y0 + 1)
    tx, ty = min(max(px - x0, 0.0), 1.0), min(max(py - y0, 0.0), 1.0)
    vals = [decode(image.getpixel((x, y))) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    if any(v is None for v in vals):
        near = decode(image.getpixel((min(w - 1, max(0, round(px))), min(h - 1, max(0, round(py))))))
        return near
    top = vals[0] * (1 - tx) + vals[1] * tx
    bottom = vals[2] * (1 - tx) + vals[3] * tx
    return top * (1 - ty) + bottom * ty


def _from_tiles(points: dict, z: int, fetch, decode) -> dict:
    """{번호: (위도, 경도)} → {번호: m}. 타일마다 한 번만 받는다."""
    by_tile = {}
    for key, (lat, lon) in points.items():
        fx, fy = tile_xy(lat, lon, z)
        by_tile.setdefault((int(fx), int(fy)), []).append((key, fx % 1, fy % 1))
    out = {}
    for (x, y), items in by_tile.items():
        data = fetch(z, x, y)
        if not data:
            continue
        image = Image.open(io.BytesIO(data)).convert("RGB")
        for key, fx, fy in items:
            value = _sample(image, fx, fy, decode)
            if value is not None:
                out[key] = value
    return out


# ── PGC ─────────────────────────────────────────────────────────────

def pgc_value(lat: float, lon: float):
    """PGC 모자이크의 해발 한 점. 자료 밖이면 None."""
    service = "arcticdem_latest" if lat > 0 else "rema_latest"
    r = _get(PGC_URL.format(service=service), "pgc", params={
        "geometry": f'{{"x":{lon},"y":{lat},"spatialReference":{{"wkid":4326}}}}',
        "geometryType": "esriGeometryPoint", "renderingRule": '{"rasterFunction":"Height Orthometric"}',
        "returnGeometry": "false", "returnCatalogItems": "false", "f": "json"})
    if r.status_code != 200:
        raise ElevationError(f"PGC 가 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise ElevationError("PGC 가 JSON 이 아닌 것을 주었다") from exc
    if "error" in data:
        raise ElevationError(f"PGC 의 오류: {data['error'].get('message', '')}")
    try:
        return float(data.get("value"))
    except (TypeError, ValueError):
        return None                                    # "NoData"


# ── 점마다 고른다 ────────────────────────────────────────────────────

def in_japan(lat: float, lon: float) -> bool:
    """국토지리원에 물을 만한 자리. 한국의 동해안·부산·울릉도·독도는 뺀다 — 물어도
    404 라 헛걸음이다. 빼지 못한 것은 404 가 걸러 AWS 로 넘어간다."""
    if not (122.9 <= lon <= 154.0 and 20.0 <= lat <= 45.6):
        return False
    if lon < 129.0:
        return False
    if lat > 35.0 and lon < 129.7:
        return False                                   # 한반도 동남해안
    if 130.7 <= lon <= 131.95 and 37.1 <= lat <= 37.6:
        return False                                   # 울릉도·독도
    return True


def elevations(points: dict, pause: float = PGC_PAUSE) -> dict:
    """{번호: (위도, 경도)} → {번호: (m, 출처)}. 못 읽은 점은 빠진다.

    극지는 PGC, 일본은 국토지리원, 나머지와 앞의 둘이 못 준 것은 AWS 다."""
    out, rest = {}, {}
    polar = {k: p for k, p in points.items() if abs(p[0]) >= POLAR_LAT}
    for index, (key, (lat, lon)) in enumerate(polar.items()):
        if index and pause:
            time.sleep(pause)
        value = pgc_value(lat, lon)
        if value is not None:
            out[key] = (value, "pgc-arcticdem-2m" if lat > 0 else "pgc-rema-2m")
    japan = {k: p for k, p in points.items() if k not in polar and in_japan(*p)}
    for key, value in _from_tiles(japan, GSI_ZOOM, gsi_tile, gsi_value).items():
        out[key] = (value, "gsi-dem-10m")
    rest = {k: p for k, p in points.items() if k not in out}
    for key, value in _from_tiles(rest, TERRARIUM_ZOOM, terrarium_tile, terrarium_value).items():
        out[key] = (value, "aws-terrarium-z12")
    return out


#: 높이 그래프의 점 수 끝 — 한 선에 타일을 수십 장 받는다
PROFILE_MAX_POINTS = 512
PROFILE_MAX_VERTICES = 200


def profile(vertices: list, n: int = 256) -> dict:
    """잰 선을 따라 고르게 찍은 점의 표고 (wetherilli 109). `{"dist", "elev", "lon", "lat", "sources"}`, 못 읽은 점은 None.

    **타일로만 읽는다** — 일본은 국토지리원(10 m), 나머지는 AWS Terrarium(z12). 극지의 PGC(`pgc_value`)는 한 점에 한 번씩
    쉬며 묻는 길이라 256 점이면 50 초가 넘는다 — 그래서 높이 그래프에서는 극지도 AWS 로 읽는다(위도 85° 너머는 없다).
    시료 한 점의 고도(`elevations`)와 다른 까닭이다."""
    from . import crs
    n = max(2, min(int(n), PROFILE_MAX_POINTS))
    pts = crs.great_circle_points(vertices, n)
    points = {i: (lat, lon) for i, (lon, lat, _) in enumerate(pts)}
    # 점 사이가 넓으면 거친 줌으로 — 타일 한 칸이 점 한 걸음쯤이면 된다. 긴 선(수백 km)이 z12 타일 수백 장을 받지 않게
    step = max(1.0, pts[-1][2] / max(1, len(pts) - 1))
    mid_lat = math.radians(sum(p[0] for p in points.values()) / len(points))
    fit = int(math.log2(max(1.0, 40075016.7 * math.cos(mid_lat) / (256 * step)))) + 1   # 한 단계 더 — 봉우리가 덜 깎인다
    japan = {k: p for k, p in points.items() if in_japan(*p)}
    zj = max(5, min(GSI_ZOOM, fit))
    got = {k: (v, f"gsi-dem-z{zj}") for k, v in _from_tiles(japan, zj, gsi_tile, gsi_value).items()}
    rest = {k: p for k, p in points.items() if k not in got and abs(p[0]) < 85.05}
    zt = max(4, min(TERRARIUM_ZOOM, fit))
    got.update({k: (v, f"aws-terrarium-z{zt}") for k, v in
                _from_tiles(rest, zt, terrarium_tile, terrarium_value).items()})
    return {"dist": [round(d, 1) for _, _, d in pts],
            "elev": [round(got[i][0], 1) if i in got else None for i in range(len(pts))],
            "lon": [round(lon, 6) for lon, _, _ in pts], "lat": [round(lat, 6) for _, lat, _ in pts],
            "sources": sorted({src for _, src in got.values()})}


def _pixels(image):
    """픽셀 차례대로. Pillow 14 에서 `getdata` 가 없어진다."""
    flat = getattr(image, "get_flattened_data", None)
    return flat() if flat else image.getdata()


# ── 3D 의 극지 지형 ──────────────────────────────────────────────────
#
# 북위 60° 너머는 PGC ArcticDEM(남쪽은 REMA)을 3857 타일로 옮겨 3D 에 준다 (032).
# **PGC 는 3857 로 물으면 값이 비고, 4326 으로 물으면 자리가 어긋나 온다**(2026-09-29,
# `identify` 한 점 값과 견줬다). 제 투영(3413·3031)으로는 맞게 준다. 그래서 타일이 덮는
# 극 평사도법 네모를 받아, 칸마다 네 모서리를 되짚어 편다(`warp.py` 와 같은 `MESH`).

PGC_EXPORT_URL = "https://di-pgc.img.arcgis.com/arcgis/rest/services/{service}/ImageServer/exportImage"
#: 3D 가 극지 표고를 받는 줌. 2 m 모자이크라 z15 까지 값이 촘촘하다. z11 밑은 AWS 로 둔다 —
#: PGC 는 한 장에 3 초 남짓이고 브라우저는 한 서버에 연결을 여섯만 연다. 스발바르를 z8 로 기울여
#: 열면 z9 타일이 89 장이라 빈 캐시에서 48 초 걸렸다(2026-09-29). 가까이 볼 때만 PGC 로 간다
POLAR_MAX_ZOOM = 15
POLAR_MIN_ZOOM = 11
_NODATA = -9999.0
#: 이보다 낮으면 자료 없음으로 본다 — 쌍선형이 빈 칸(−9999)과 섞인 가장자리까지 거른다.
#: 모자이크의 가장 낮은 값이 −155 m 다
_FLOOR = -500.0
_MESH = 8
#: PGC 에 묻는 그림의 한 변. 512 면 한 장에 3.7 초, 256 이면 2.7 초다(2026-09-29). 3D 의 256 px
#: 타일을 펴는 데는 256 으로 모자라지 않다
_SRC = 256


def _terrarium_rgb(value):
    v = value + 32768
    r, rem = divmod(v, 256)
    g = int(rem)
    b = int(round((rem - g) * 256))
    if b == 256:
        g, b = g + 1, 0
    return (max(0, min(255, int(r))), g, b)


def _merc_lonlat(z, x, y, px, py):
    n = 2 ** z
    lon = (x + px / 256) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / 256) / n))))
    return lon, lat


#: 한 번 물을 때 받는 네모 — 4×4 타일. 한 장씩이면 16 장에 45 초, 네모째면 5 초다(2026-09-29)
POLAR_BLOCK = 4
_block_locks = {}
_block_locks_guard = threading.Lock()


def _block_lock(key):
    with _block_locks_guard:
        return _block_locks.setdefault(key, threading.Lock())


def polar_terrarium(z: int, x: int, y: int):
    """PGC 해발을 Terrarium 으로 옮긴 3857 타일. 모자이크 밖이면 None(→ AWS).

    타일 하나를 부르면 그 타일이 든 4×4 네모를 한 번에 받아 16 장을 다 담는다 — 3D 는 이웃
    타일을 곧 부른다. 같은 네모를 여럿이 한꺼번에 부르면 하나만 묻고 나머지는 기다린다."""
    key = polar_key(z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    n = 2 ** z
    block = min(POLAR_BLOCK, n)
    bx, by = x // block * block, y // block * block
    with _block_lock((z, bx, by)):
        hit = tilecache.get(key)                       # 기다리는 사이 다른 스레드가 담았다
        if hit is not None:
            return None if hit == _NONE else hit
        tiles = _polar_block(z, bx, by, block)
    return tiles.get((x, y))


def polar_key(z: int, x: int, y: int) -> str:
    """3D 의 극지 표고 타일을 담는 열쇠 — `polar_terrarium` 과 미리 데우기(034)가 함께 쓴다."""
    return tilecache.key_text("elev", f"pgc-terrarium/{z}/{x}/{y}")


def polar_block(z: int, x: int, y: int) -> int:
    """(x, y) 가 든 4×4 네모를 받아 담는다 — 미리 데우기(`prewarm --layers dem`). 담은 타일 수.
    네모의 타일이 벌써 다 있으면 묻지 않는다."""
    block = min(POLAR_BLOCK, 2 ** z)
    bx, by = x // block * block, y // block * block
    with _block_lock((z, bx, by)):
        if all(tilecache.get(polar_key(z, bx + dx, by + dy)) is not None
               for dx in range(block) for dy in range(block)):
            return 0
        return len(_polar_block(z, bx, by, block))


def _polar_block(z: int, bx: int, by: int, block: int) -> dict:
    """(bx, by) 에서 block×block 타일을 한 번에 만들어 담는다. {(x, y): PNG 또는 None}."""
    from . import tilegrid
    size = 256 * block
    _, lat_mid = _merc_lonlat(z, bx, by, size / 2, size / 2)
    crs, service = ("EPSG:3413", "arcticdem_latest") if lat_mid > 0 else ("EPSG:3031", "rema_latest")
    cells = _MESH * block
    step = size / cells
    corners = {(i, j): tilegrid.polar_forward(*_merc_lonlat(z, bx, by, i * step, j * step), crs)
               for i in range(cells + 1) for j in range(cells + 1)}
    xs = [c[0] for c in corners.values()]
    ys = [c[1] for c in corners.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    side = max(x1 - x0, y1 - y0)                       # 정사각으로 받아 픽셀이 반듯하게
    x1, y0 = x0 + side, y1 - side
    src_px = _SRC * block
    r = _get(PGC_EXPORT_URL.format(service=service), "pgc", params={
        "bbox": f"{x0},{y0},{x1},{y1}", "bboxSR": crs.split(":")[1], "imageSR": crs.split(":")[1],
        "size": f"{src_px},{src_px}", "format": "tiff", "compression": "LZ77", "pixelType": "F32",
        "noData": _NODATA, "interpolation": "RSP_BilinearInterpolation",
        "renderingRule": '{"rasterFunction":"Height Orthometric"}', "f": "image"})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise ElevationError(f"PGC 가 표고 그림을 주지 않았다 (status={r.status_code})")
    src = Image.open(io.BytesIO(r.content))
    src.load()
    if src.mode != "F":
        raise ElevationError(f"PGC 가 뜻밖의 그림을 주었다 ({src.mode})")
    res = side / src_px

    def px(k):
        e, north = corners[k]
        return (e - x0) / res, (y1 - north) / res

    mesh = []
    for i in range(cells):
        for j in range(cells):
            box = (round(i * step), round(j * step), round((i + 1) * step), round((j + 1) * step))
            mesh.append((box, px((i, j)) + px((i, j + 1)) + px((i + 1, j + 1)) + px((i + 1, j))))
    warped = src.transform((size, size), Image.MESH, mesh, resample=Image.BILINEAR, fillcolor=_NODATA)

    out = {}
    for dx in range(block):
        for dy in range(block):
            x, y = bx + dx, by + dy
            piece = warped.crop((dx * 256, dy * 256, dx * 256 + 256, dy * 256 + 256))
            png = _terrarium_png(piece, z, x, y)
            tilecache.put(polar_key(z, x, y), png or _NONE)
            out[x, y] = png
    return out


def _terrarium_png(piece, z, x, y):
    """해발(F) 256×256 → Terrarium PNG. 다 비었으면 None. 구멍은 같은 자리의 AWS 값으로."""
    values = list(_pixels(piece))
    if all(v < _FLOOR for v in values):
        return None
    fill = None
    out = []
    for index, v in enumerate(values):
        if v < _FLOOR:
            # 모자이크의 구멍(바다·자료 밖) — 남극은 IBCSO(051), 그 밖은 같은 자리의 AWS 값
            if fill is None:
                aws = _hole_tile(z, x, y)
                fill = list(_pixels(Image.open(io.BytesIO(aws)).convert("RGB"))) if aws else []
            out.append(fill[index] if fill else (128, 0, 0))
            continue
        out.append(_terrarium_rgb(v))
    image = Image.new("RGB", (256, 256))
    image.putdata(out)
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


# ── 3D 의 남극 해저 지형 (051) ─────────────────────────────────────────
#
# 남위 50° 남쪽은 IBCSO v2 의 수치 격자(`ibcso.DEMS`, 500 m)를 Terrarium 으로 편다. AWS 는 여기서
# 바다가 GEBCO 옛 판(수 km)이라 해저가 뭉개지고, 빙붕 밑이 비어 있다. IBCSO 는 두 판이다 —
# **얼음 위**(`ice`)는 REMA 와 같은 면이라 가까이서 REMA 로 넘어가도 땅이 튀지 않고(REMA 의 구멍인
# 바다를 IBCSO 가 메운다), **해저·빙저**(`bed`)는 빙상과 빙붕을 걷어 낸 기반암이다. 높이는 둘 다
# 해발이다 — REMA 도 `Height Orthometric` 으로 받는다.
#
# 격자 밖(남위 50° 언저리의 네모 밖)과 빈 곳이 섞인 픽셀은 같은 자리의 AWS 로 메운다.

IBCSO_NORTH = -50.0
#: 편 타일을 담는 열쇠의 판. 수치 타일을 새로 자르면 올린다
IBCSO_TERRAIN_VERSION = 1


def _tile_lat(z, y):
    return _merc_lonlat(z, 0, y, 128, 128)[1]


def _hole_tile(z, x, y):
    """REMA 의 구멍을 메울 Terrarium 타일 — 남극 바다는 IBCSO 얼음 위, 그 밖은 AWS."""
    if _tile_lat(z, y) <= IBCSO_NORTH:
        png = ibcso_terrarium("ice", z, x, y)
        if png:
            return png
    return terrarium_tile(z, x, y)


def terrarium_encode(value):
    """해발(F) → Terrarium RGB. 한 픽셀씩 돌지 않고 띠마다 셈한다(ImageMath)."""
    from PIL import ImageMath
    code = ImageMath.lambda_eval(lambda a: a["int"]((a["v"] + 32768) * 256 + 0.5), v=value)
    bands = [ImageMath.lambda_eval(fn, c=code).convert("L") for fn in (
        lambda a: a["c"] / 65536, lambda a: (a["c"] / 256) % 256, lambda a: a["c"] % 256)]
    return Image.merge("RGB", bands)


def ibcso_terrarium(kind: str, z: int, x: int, y: int):
    """IBCSO 수치 격자를 편 3857 Terrarium 타일(PNG). 격자에 하나도 걸리지 않으면 None(→ AWS)."""
    from . import ibcso, warp
    sheet = ibcso.DEMS[kind]
    if not sheet.available():
        return None
    key = tilecache.key_text("elev", f"ibcso-terrarium/{kind}/v{IBCSO_TERRAIN_VERSION}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    got = warp.render_values(warp.ibcso_dem_grid(sheet), z, x, y, ibcso.decode_dem)
    png = None
    if got is not None and got[1].getextrema()[1] > 0:
        value, fill = got
        # 채움이 1 이 아니면 빈 곳이 섞인 값이다 — 값을 채움으로 나눠 되살리지 않고 AWS 로 간다
        full = _full_mask(fill)
        image = terrarium_encode(value)
        if full.getextrema()[0] < 255:
            aws = terrarium_tile(z, x, y)
            under = (Image.open(io.BytesIO(aws)).convert("RGB") if aws
                     else Image.new("RGB", image.size, (128, 0, 0)))     # AWS 도 없다 — 해수면
            image = Image.composite(image, under, full)
        buf = io.BytesIO()
        image.save(buf, "PNG")
        png = buf.getvalue()
    tilecache.put(key, png or _NONE)
    return png


def _full_mask(fill):
    """채움(F) → 빈 곳이 하나도 섞이지 않은 픽셀만 255 인 L."""
    from PIL import ImageMath
    return ImageMath.lambda_eval(lambda a: a["float"](a["f"] >= 0.999) * 255, f=fill).convert("L")


# ── 3D 의 일본 지형 ──────────────────────────────────────────────────

def japan_terrarium(z: int, x: int, y: int):
    """국토지리원 `dem_png` 를 Terrarium 인코딩으로 옮긴 타일. 일본 밖이면 None.

    빈 칸(바다·자료 밖)은 같은 자리의 AWS 값으로 메운다 — 그대로 두면 3D 에서
    (128,0,0) 이 8 만 m 로 솟는다. 담아 두고 다시 만들지 않는다."""
    key = tilecache.key_text("elev", f"gsi-terrarium/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    data = gsi_tile(z, x, y)
    if not data:
        tilecache.put(key, _NONE)
        return None
    gsi = Image.open(io.BytesIO(data)).convert("RGB")
    fill = None
    out = []
    for index, px in enumerate(_pixels(gsi)):
        value = gsi_value(px)
        if value is None:
            if fill is None:
                aws = terrarium_tile(z, x, y)
                fill = list(_pixels(Image.open(io.BytesIO(aws)).convert("RGB"))) if aws else []
            if not fill:
                out.append((128, 0, 0))                # AWS 도 없다 — 해수면(0 m)
                continue
            out.append(fill[index])
            continue
        out.append(_terrarium_rgb(value))
    image = Image.new("RGB", gsi.size)
    image.putdata(out)
    buf = io.BytesIO()
    image.save(buf, "PNG")
    png = buf.getvalue()
    tilecache.put(key, png)
    return png


# ── 지질도 위에 겹치는 PGC 레이어 — 경사·등고선 (wetherilli 099) ──────────
#
# 배경의 음영(092)은 브라우저가 PGC 를 곧장 부른다. 배경은 맨 밑에 깔려 지질도를 덮으면 보이지 않는다.
# 경사·등고선은 지질도 **위에** 겹쳐 보려는 것이라 레이어로 두고, 다른 레이어처럼 `/wms` 를 거쳐 캐시에 담는다
# (PGC 는 한 장을 그 자리에서 1–2 초에 그린다). NPI 처럼 지역의 투영(3413·3031)으로 곧장 받는다 — 3857 로
# 받아 옮기면 남위 85° 너머(남극점 둘레)가 빈다. 레이어 이름은 레이어군 하나에만 들어 지역마다 따로 둔다.
#
#   draw  그리는 법(`exportImage` 의 renderingRule)
#   read  누른 자리에서 읽는 값의 renderingRule 과 팝업 이름

PGC_IDENTIFY_URL = PGC_URL
PGC_ATTRIBUTION = ('ArcticDEM·REMA © <a href="https://www.pgc.umn.edu/data/" target="_blank" rel="noopener">'
                   'Polar Geospatial Center</a> (CC BY 4.0)')
#: 경사는 평지까지 회색으로 꽉 채운 그림이라 `jpgpng` 로 받는다 — 꽉 차면 JPEG, 빈 자리가 있으면 PNG 가 온다.
#: 512 px 한 장이 png32 370 KB, jpgpng 35 KB 다(2026-09-30). 등고선은 투명해야 해서 png32. "경사 (°)" 는 지층의 경사(dip)라
#: 팝업 이름을 "사면 경사" 로 갈랐다
_SLOPE = {"draw": "Slope Map", "read": ("Slope Degrees", "사면 경사 (°)"), "format": "jpgpng"}
#: 25 m 간격이라 멀리서는 새까맣게 뭉개진다 — 줌 10(3413·3031 에서 한 픽셀 30 m 남짓)부터 그린다.
#: `Contour 25` 보다 매끈하게 다듬은 판이 가까이서 읽기 좋다
_CONTOURS = {"draw": "Contour Smoothed 25", "read": ("Height Orthometric", "높이 (m)"), "min": 10}
PGC_LAYERS = {
    "pgc:greenland_slope": {"service": "arcticdem_latest", "srs": "EPSG:3413", **_SLOPE},
    "pgc:greenland_contours": {"service": "arcticdem_latest", "srs": "EPSG:3413", **_CONTOURS},
    "pgc:svalbard_slope": {"service": "arcticdem_latest", "srs": "EPSG:3413", **_SLOPE},
    "pgc:svalbard_contours": {"service": "arcticdem_latest", "srs": "EPSG:3413", **_CONTOURS},
    "pgc:antarctica_slope": {"service": "rema_latest", "srs": "EPSG:3031", **_SLOPE},
    "pgc:antarctica_contours": {"service": "rema_latest", "srs": "EPSG:3031", **_CONTOURS},
}
_PGC_MAX_SIZE = 1024


def knows_layer(name: str) -> bool:
    return name in PGC_LAYERS


def _pgc_request(params: dict, key: str = "layers") -> tuple:
    """WMS 꼴 → (명세, 투영 번호, bbox, (w, h)). 모르는 것은 ElevationError."""
    name = (params.get(key) or params.get("layers") or "").split(",")[0].strip()
    spec = PGC_LAYERS.get(name)
    if not spec:
        raise ElevationError("PGC 레이어가 아니다")
    code = (params.get("crs") or params.get("srs") or "").upper()
    if code != spec["srs"]:
        raise ElevationError(f"받지 않는 투영이다: {code}")
    try:
        box = [float(v) for v in (params.get("bbox") or "").split(",")]
        w, h = int(params.get("width") or 256), int(params.get("height") or 256)
    except ValueError as exc:
        raise ElevationError("BBOX·크기를 읽지 못했다") from exc
    if len(box) != 4 or not (box[0] < box[2] and box[1] < box[3]):
        raise ElevationError("BBOX 를 읽지 못했다")
    if not (0 < w <= _PGC_MAX_SIZE and 0 < h <= _PGC_MAX_SIZE):
        raise ElevationError("그림이 너무 크다")
    return spec, int(code.split(":")[1]), box, (w, h)


def get_map(params: dict):
    """`GetMap` → PGC `exportImage`. (바이트, content-type)."""
    spec, srs, box, (w, h) = _pgc_request(params)
    r = _get(PGC_EXPORT_URL.format(service=spec["service"]), "pgc", params={
        "bbox": ",".join(repr(v) for v in box), "bboxSR": srs, "imageSR": srs, "size": f"{w},{h}",
        "format": spec.get("format", "png32"), "transparent": "true", "f": "image",
        "renderingRule": json.dumps({"rasterFunction": spec["draw"]})})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise ElevationError(f"PGC 가 그림을 주지 않았다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` → 누른 픽셀 한 점의 값(경사 몇 도·해발). KIGAM 과 같은 꼴(`features`)."""
    spec, srs, box, (w, h) = _pgc_request(params, "query_layers")
    try:
        i = float(params.get("i") if params.get("i") is not None else params.get("x"))
        j = float(params.get("j") if params.get("j") is not None else params.get("y"))
    except (TypeError, ValueError) as exc:
        raise ElevationError("누른 자리를 읽지 못했다") from exc
    x = box[0] + (i + 0.5) / w * (box[2] - box[0])
    y = box[3] - (j + 0.5) / h * (box[3] - box[1])
    rule, label = spec["read"]
    r = _get(PGC_IDENTIFY_URL.format(service=spec["service"]), "pgc", params={
        "geometry": json.dumps({"x": x, "y": y, "spatialReference": {"wkid": srs}}),
        "geometryType": "esriGeometryPoint", "renderingRule": json.dumps({"rasterFunction": rule}),
        "returnGeometry": "false", "returnCatalogItems": "false", "f": "json"})
    if r.status_code != 200:
        raise ElevationError(f"PGC 가 받지 않았다 (status={r.status_code})")
    try:
        value = float(r.json().get("value"))
    except (TypeError, ValueError):
        return {"features": []}                           # "NoData" — 모자이크 밖
    return {"features": [{"id": "pgc", "properties": {label: f"{value:.1f}"}}]}


def get_legend(layer: str):
    """PGC 의 범례는 늘인 값(0–255)뿐이라 싣지 않는다 — 화면은 `noLegend` 로 묻지 않는다."""
    raise ElevationError("PGC 레이어는 범례가 없다")
