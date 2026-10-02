"""지각 두께 — CRUST 2.0 (Laske, Masters & Reif 2000) 을 오늘의 지구에 칠한다 (wetherilli P07 §3·101).

`data/crust2_thickness.json`(`manage.py build_crust <zip>`, 1° 칸 180 × 360, 0.1 km)을 읽는다. 저장소의 파일이라 문이 아니다.

- **모형이지 관측이 아니다.** 2° 칸의 모형을 1° 로 뽑았을 뿐이다 — 칸 안은 한 값이다. 누르면 그렇게 적는다
- 원본은 두께에 물·얼음을 넣는지, 어느 면에서 재는지를 밝히지 않는다(EarthThruTime3D `docs/crust.md`). 그래서 "지각 두께"
  한 값만 적고 모호면의 깊이로 옮기지 않는다
- **오늘에만 뜬다.** 오늘의 두께를 옛 연대로 돌리지 않는다
- 색은 얇은 바다 지각(파랑)에서 두꺼운 대륙 지각(갈색)으로. 빈 칸(1 448 칸, 남극점 둘레 따위)은 칠하지 않는다
"""
import functools
import io
import json

from django.conf import settings

from . import paleo

RENDERER = "1"
MAX_ZOOM = 5                     # 180/2⁵/256 ≈ 0.02° — 1° 칸이라 그 너머는 늘려 쓴다
#: (km, 색) — 사이는 섞는다. 바다 지각 5–10 km, 대륙 30–45 km, 티베트·안데스 60–75 km
STOPS = ((0, "#08306b"), (8, "#2171b5"), (15, "#6baed6"), (22, "#c7e9c0"), (30, "#fee391"), (40, "#fec44f"),
         (50, "#fe9929"), (60, "#cc4c02"), (75, "#662506"))
CITE = "CRUST 2.0 (Laske, Masters & Reif 2000) · EarthByte GPlates 2.3 · CC BY 4.0"


@functools.lru_cache(maxsize=1)
def grid():
    """`rows[북에서 j][서에서 i]` (0.1 km 또는 None). 파일이 없으면 None."""
    try:
        with open(settings.CRUST_FILE, encoding="utf-8") as fh:
            return json.load(fh)["rows"]
    except FileNotFoundError:
        return None


def at(lon: float, lat: float):
    """누른 자리의 두께(km). 빈 칸이면 None."""
    rows = grid()
    if rows is None:
        return None
    j = min(179, max(0, int(90.0 - lat)))
    i = int((((lon + 180.0) % 360.0) + 360.0) % 360.0) % 360
    v = rows[j][i]
    return None if v is None else v / 10.0


def _rgb(hexa):
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def colour(km: float) -> tuple:
    if km <= STOPS[0][0]:
        return _rgb(STOPS[0][1])
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if km <= b:
            f = (km - a) / (b - a)
            return tuple(round(x + (y - x) * f) for x, y in zip(_rgb(ca), _rgb(cb)))
    return _rgb(STOPS[-1][1])


def legend() -> list:
    """범례의 칸 — `[{"name": "0–10 km", "color": "#…"}…]`. 칸 가운데의 색이다."""
    out = []
    for lo in range(0, 80, 10):
        r, g, b = colour(lo + 5)
        out.append({"name": f"{lo}–{lo + 10} km", "color": f"#{r:02x}{g:02x}{b:02x}"})
    return out


@functools.lru_cache(maxsize=1)
def _image():
    """온 지구 한 장(360 × 180, 칸마다 한 점)."""
    from PIL import Image
    rows = grid()
    im = Image.new("RGBA", (360, 180), (0, 0, 0, 0))
    px = im.load()
    for j, row in enumerate(rows):
        for i, v in enumerate(row):
            if v is not None:
                px[i, j] = colour(v / 10.0) + (255,)
    return im


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장 — 칸을 늘려 그린다. 칸의 가장자리가 흐리지 않게 가장 가까운 점으로."""
    from PIL import Image
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    box = (west + 180.0, 90.0 - north, west + 180.0 + span, 90.0 - north + span)
    tile = _image().transform((paleo.TILE, paleo.TILE), Image.Transform.EXTENT, box, Image.Resampling.NEAREST)
    buf = io.BytesIO()
    tile.save(buf, "PNG", optimize=True)
    return buf.getvalue()
