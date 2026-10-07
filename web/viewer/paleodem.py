"""그때의 땅과 바다 밑 — PALEOMAP PaleoDEM (Scotese & Wright 2018, CC BY 4.0) 을 칠한 그림으로 (wetherilli 375).

판 조각만 칠하면 그때의 지구가 흙빛 조각을 늘어놓은 것으로 보였다. WegenersDream 이 배경으로 쓰는 고도 격자(같은 PALEOMAP
틀, 0–540 Ma, 5 Myr 간격 109 시점)를 받아 **고도로 칠하고(바다는 깊이, 뭍은 높이) 북서쪽 빛의 음영을 얹는다** — 색 고리와
음영은 WegenersDream `pipeline/relief.py` 의 것 그대로다. 두 화면이 같은 연대를 같은 빛으로 보이게.

- 문이 아니다. `<EARTH_DIR>/paleodem/` 의 구운 것을 읽는다 — `<0.1 Myr 네 자리>.webp`(3 600 × 1 800, 경위도 칸 0.1°)와
  `index.json`. 굽기는 `manage.py build_paleodem <6분 격자 zip>` 이고 **호스트에서만 돈다** — 원본이 NetCDF-4(HDF5)라 h5py 를,
  음영에 numpy 를 쓴다(`wind.py` 와 같다, `/srv/GSM/scripts/run.sh build_paleodem …`). 저장소에 두지 않는다 — 40 MB 남짓이다
- 연대는 가장 가까운 시점으로, **2.5 Myr 안**에서만이다(간격의 절반). 540 Ma 너머는 격자가 없어 판 조각을 칠하던 대로 돌아간다
- 판 조각의 경계는 그 위에 가는 선으로 얹는다 — 칠한 그림의 해안은 그 시점의 것이고, 판은 고른 연대의 것이다
"""
import functools
import io
import json
import re
from pathlib import Path

from django.conf import settings

DIR = "paleodem"
RENDERER = "1"                   # 굽는 법을 고치면 올린다 — 다시 구워야 한다
NEAREST = 2.5                    # Myr — 간격(5 Myr)의 절반
WIDTH = 3600                     # 0.1° 칸 — 원본 6 분 격자(3 601 × 1 801 격자점)와 같은 촘촘함
QUALITY = 88
CITE = "Scotese, C. R. & Wright, N. M. (2018) PALEOMAP PaleoDEMs for the Phanerozoic, Zenodo 5460860, CC BY 4.0"

# (고도 m, RGB). 사이는 선형으로 섞는다. 0 m 에서 바다 쪽과 뭍 쪽이 따로 선다 — WegenersDream relief.py 와 같다
SEA = ((-9000, (6, 22, 48)), (-5000, (18, 52, 96)), (-2500, (36, 86, 138)),
       (-500, (82, 140, 186)), (-100, (134, 186, 214)), (0, (170, 214, 230)))
LAND = ((0, (112, 150, 96)), (250, (150, 172, 106)), (800, (196, 184, 124)),
        (1800, (176, 138, 96)), (3200, (150, 120, 104)), (4500, (206, 198, 190)),
        (6500, (250, 250, 250)))

# 예: "Map88_PALEOMAP_1deg_Cambrian_Precambrian boundary_540Ma.nc", "Map48_PALEOMAP_6min_Middle_Devonian_385Ma.nc"
NAME = re.compile(r"_(?:1deg|6min)_(?P<label>.+?)_(?P<age>\d+(?:\.\d+)?)\s*Ma\.nc$")


def root() -> Path:
    return Path(settings.EARTH_DIR) / DIR


def key(age: float) -> str:
    """시점을 파일 이름으로 — 0.1 Myr 단위 네 자리(385.2 Ma 가 385 Ma 와 부딪히지 않게)."""
    return f"{round(age * 10):04d}"


@functools.lru_cache(maxsize=2)
def _index(path: str, mtime: float):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def index():
    """구운 목록 `{"ages": [...], "meta": {...}}`. 없으면 None. 다시 구우면 다시 읽는다."""
    path = root() / "index.json"
    try:
        return _index(str(path), path.stat().st_mtime)
    except FileNotFoundError:
        return None


def ages() -> list:
    data = index()
    return sorted(data["ages"]) if data else []


def stop(age: float):
    """`age` 에 쓸 시점 — 가장 가까운 것, 2.5 Myr 안에서만. 없으면 None."""
    best = min(ages(), key=lambda a: abs(a - age), default=None)
    return best if best is not None and abs(best - age) <= NEAREST else None


def stamp() -> str:
    """캐시 열쇠에 넣을 판 — 다시 구우면 바뀐다."""
    data = index()
    return f"{RENDERER}-{data['meta'].get('built', '')}" if data else "none"


@functools.lru_cache(maxsize=4)
def _image(path: str, mtime: float):
    from PIL import Image
    with Image.open(path) as im:
        return im.convert("RGB")


def crop(age: float, west: float, north: float, span: float, size: int):
    """그 시점의 그림에서 경위도 네모 하나를 `size`² 로. 시점이 없으면 None."""
    from PIL import Image
    at = stop(age)
    if at is None:
        return None
    path = root() / f"{key(at)}.webp"
    try:
        image = _image(str(path), path.stat().st_mtime)
    except FileNotFoundError:
        return None
    k = image.width / 360.0
    box = ((west + 180.0) * k, (90.0 - north) * k, (west + span + 180.0) * k, (90.0 - north + span) * k)
    return image.resize((size, size), Image.BICUBIC if span * k < size else Image.LANCZOS, box=box)


# ── 굽기 — 호스트에서만 (numpy·h5py) ───────────────────────────────────

def read_grid(data: bytes):
    """NetCDF-4 한 장 → 행은 북→남, 열은 −180→180 인 고도(m) 배열."""
    import h5py
    import numpy as np
    with h5py.File(io.BytesIO(data), "r") as h:
        lat = np.asarray(h["lat" if "lat" in h else "latitude"][:], dtype=float)   # 1° 판은 lat, 6 분 판은 latitude
        z = np.asarray(h["z"][:], dtype=float)
    return z[::-1] if lat[0] < lat[-1] else z


def _ramp(z, stops):
    import numpy as np
    heights = np.array([h for h, _ in stops], dtype=float)
    colours = np.array([c for _, c in stops], dtype=float)
    return np.stack([np.interp(z, heights, colours[:, i]) for i in range(3)], axis=-1)


def _resample(z, width):
    """격자점(극에서 극, −180 에서 180) → 칸 가운데. 쌍선형."""
    import numpy as np
    height = width // 2
    rows = (np.arange(height) + 0.5) / height * (z.shape[0] - 1)
    cols = (np.arange(width) + 0.5) / width * (z.shape[1] - 1)
    r0 = np.clip(np.floor(rows).astype(int), 0, z.shape[0] - 2)
    c0 = np.clip(np.floor(cols).astype(int), 0, z.shape[1] - 2)
    fr = (rows - r0)[:, None]
    fc = (cols - c0)[None, :]
    a, b = z[r0][:, c0], z[r0][:, c0 + 1]
    c, d = z[r0 + 1][:, c0], z[r0 + 1][:, c0 + 1]
    return (a * (1 - fc) + b * fc) * (1 - fr) + (c * (1 - fc) + d * fc) * fr


def _hillshade(z, azimuth=315.0, altitude=45.0, exaggeration=12.0):
    """0..1 음영. 경도 방향 칸 너비를 위도에 맞춰 줄여, 극 가까이 음영이 눕지 않게 한다."""
    import numpy as np
    height, width = z.shape
    cell = 40_075_000.0 / width
    lat = np.radians(90.0 - (np.arange(height) + 0.5) / height * 180.0)
    dx = np.maximum(np.cos(lat), 0.05)[:, None] * cell
    gy, gx = np.gradient(z * exaggeration)
    gx = gx / dx
    gy = gy / cell
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(360.0 - azimuth + 90.0), np.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0.0, 1.0)


def render(z, width=WIDTH):
    """고도 배열 → 칠하고 음영을 얹은 RGB 그림(Pillow)과 뭍의 비율."""
    import numpy as np
    from PIL import Image
    fine = _resample(z, width)
    colour = np.where((fine > 0)[..., None], _ramp(fine, LAND), _ramp(np.minimum(fine, 0), SEA))
    shade = _hillshade(fine)
    # 뭍은 음영을 세게, 바다는 약하게 — 해저 지형이 뭍보다 눈에 띄지 않게 한다
    strength = np.where(fine > 0, 0.55, 0.25)[..., None]
    lit = colour * (1.0 - strength + strength * 1.35 * shade[..., None])
    return Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8), "RGB"), float((fine > 0).mean())
