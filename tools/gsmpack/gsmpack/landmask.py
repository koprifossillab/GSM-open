"""한반도 둘레의 육지 마스크 — 칸마다 땅이 얼마인가 (wetherilli 409). 어림(`bake.Plan`)이 바다 칸을 덜어 센다.

`landmask.png` 는 경위도 0.005° 칸의 1 비트 그림이다(Natural Earth 10 m 나라 경계, 공공 도메인 — `scripts/build_landmask.py` 가 굽는다).
해안선이 1 km 남짓 어긋나도 칸 수백 장을 모아 세는 어림에는 넉넉하다. **범위 밖은 모른다 — 다 땅으로 센다**(어림은 넘치는 쪽이 낫다).
상류를 타지 않고 Pillow 하나만 쓴다.
"""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image

from . import grid

EXTENT = (124.0, 32.9, 132.0, 39.0)        # 경위도 (서, 남, 동, 북) — 제주 마라도·독도·휴전선 위까지
STEP = 0.005                               # 칸 한 변(도)
FILE = Path(__file__).with_name("landmask.png")


@lru_cache(maxsize=1)
def _cells():
    """(폭, 높이, 칸마다 0·1 의 bytes). 파일이 없으면 None — 그때는 다 땅이다."""
    try:
        image = Image.open(FILE).convert("L")
    except (OSError, ValueError):
        return None
    return image.size[0], image.size[1], bytes(1 if v else 0 for v in image.tobytes())


def _lonlat(mx: float, my: float) -> tuple:
    return mx * 180 / grid.HALF, math.degrees(2 * math.atan(math.exp(my * math.pi / grid.HALF)) - math.pi / 2)


def fraction(bbox) -> float:
    """경위도 네모 `(서, 남, 동, 북)` 에서 땅의 몫(0–1). 범위 밖의 칸은 땅으로 센다."""
    west, south, east, north = bbox
    loaded = _cells()
    if loaded is None or east <= west or north <= south:
        return 1.0
    width, height, cells = loaded
    x0, y0, x1, y1 = EXTENT
    # 칸의 가운데가 네모 안에 드는 칸만 센다 — 하나도 없으면(네모가 칸보다 작다) 가운데 칸 하나
    c0, c1 = math.ceil((west - x0) / STEP - 0.5), math.floor((east - x0) / STEP - 0.5)
    r0, r1 = math.ceil((y1 - north) / STEP - 0.5), math.floor((y1 - south) / STEP - 0.5)
    if c0 > c1 or r0 > r1:
        c0 = c1 = math.floor(((west + east) / 2 - x0) / STEP)
        r0 = r1 = math.floor((y1 - (south + north) / 2) / STEP)
    total = (c1 - c0 + 1) * (r1 - r0 + 1)
    land = 0
    for r in range(max(r0, 0), min(r1, height - 1) + 1):
        row = r * width
        lo, hi = max(c0, 0), min(c1, width - 1)
        if lo <= hi:
            land += sum(cells[row + lo:row + hi + 1])
    inside = max(0, min(r1, height - 1) - max(r0, 0) + 1) * max(0, min(c1, width - 1) - max(c0, 0) + 1)
    return (land + (total - inside)) / total


def tile_fraction(z: int, x: int, y: int, bbox) -> float:
    """3857 칸 `(z, x, y)`(칸 수 2^z) 가운데 박스 `bbox`(경위도) 안쪽에서 땅의 몫 — 묶음에는 박스로 자른 타일이 들기 때문이다."""
    span = 2 * grid.HALF / 2 ** z
    west, north = _lonlat(-grid.HALF + x * span, grid.HALF - y * span)
    east, south = _lonlat(-grid.HALF + (x + 1) * span, grid.HALF - (y + 1) * span)
    return fraction((max(west, bbox[0]), max(south, bbox[1]), min(east, bbox[2]), min(north, bbox[3])))
