"""옛 해안선 — PaleoCoastlines v7.1 (Kocsis & Scotese 2021, CC BY 4.0) 을 그때의 지구에 얹는다 (wetherilli P07 §3·097).

`<EARTH_DIR>/paleocoastlines_v7.json`(`manage.py build_paleocoastlines <zip>`)을 읽는다. 상류가 아니라 우리 디스크의
파일이라 문이 아니다. 파일이 없으면 레이어가 비고 나머지는 돈다.

- 해안선은 **이미 옮겨진 좌표**다(81 시점, 0–535 Ma). 돌리지 않고 그대로 그린다
- PaleoDEM 의 해안을 PBDB 해양 화석이 가리키는 **최대 해침면**으로 옮긴 것이다 — 그때 바다가 가장 깊이 들어온 선이다.
  판 조각(대륙)은 그대로 두고 그 위에 바다를 덮어, 물에 잠긴 대륙이 판 조각의 흙빛 위로 비쳐 보이게 칠한다. 뭍은
  옅은 흙빛으로 덮는다 — 판 조각 밖으로 나간 뭍도 사라지지 않게
- 모델은 PALEOMAP v19o 로, 판 조각의 2016 판과 같은 계열의 다른 판이다. 어긋남은 devlog 097 에 쟀다
- 연대는 가장 가까운 시점으로 맞추되 **10 Myr 안**에서만이다(ETT 와 같다). 그 밖은 비운다 — 사이를 메우지 않는다
"""
import functools
import io
import json
from pathlib import Path

from django.conf import settings

from . import paleo

FILE = "paleocoastlines_v7.json"
NEAREST = 10.0                   # Myr — 이보다 먼 시점은 쓰지 않는다
RENDERER = "1"
SEA = (27, 58, 94, 170)          # 대륙 위의 바다 — 판 조각의 흙빛이 비친다
COAST = (20, 16, 10, 235)
LAND = (214, 196, 150, 90)       # 뭍 — 옅게. 판 조각 밖으로 나간 뭍(모델의 판이 달라 91–97% 만 겹친다)도 보이게
CITE = "Kocsis, A. T. & Scotese, C. R. (2021) PaleoCoastlines v7.1, CC BY 4.0"


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


@functools.lru_cache(maxsize=1)
def _load(mtime):
    with open(path(), encoding="utf-8") as fh:
        data = json.load(fh)
    rings = {float(k): v for k, v in data["rings"].items()}
    holes = {float(k): v for k, v in data.get("holes", {}).items()}
    return {"ages": sorted(rings), "rings": rings, "holes": holes, "meta": data.get("meta", {})}


def load():
    """구운 파일. 없으면 None. 다시 구우면(파일이 바뀌면) 다시 읽는다."""
    try:
        return _load(path().stat().st_mtime)
    except FileNotFoundError:
        return None


def ages() -> list:
    data = load()
    return data["ages"] if data else []


def stop(age: float):
    """`age` 에 쓸 시점 — 가장 가까운 것, 10 Myr 안에서만. 없으면 None."""
    best = min(ages(), key=lambda a: abs(a - age), default=None)
    return best if best is not None and abs(best - age) <= NEAREST else None


def render_tile(at: float, z: int, x: int, y: int) -> bytes:
    """시점 `at` 의 해안선 한 장 — 바다를 칠하고 뭍을 도려낸 뒤 해안을 긋는다. 경위도 격자는 `paleo` 와 같다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    image = Image.new("RGBA", (size, size), SEA)
    draw = ImageDraw.Draw(image)
    data = load()
    rings = data["rings"].get(at, []) if data else []
    lines = []
    for ring in rings:
        xs = ring[0::2]
        lo, hi = min(xs), max(xs)
        runs = coast_runs(ring)
        for shift in (-360.0, 0.0, 360.0):
            if hi + shift < west or lo + shift > west + span:
                continue
            def px(lon, lat):
                return ((lon + shift - west) * scale, (north - lat) * scale)
            draw.polygon([px(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)], fill=LAND)   # 뭍 — 옅게 칠한다
            lines += [[px(*p) for p in run] for run in runs]
    # 뭍 안의 구멍(내해·호수)은 다시 바다로
    for ring in (data["holes"].get(at, []) if data else []):
        xs = ring[0::2]
        for shift in (-360.0, 0.0, 360.0):
            if max(xs) + shift < west or min(xs) + shift > west + span:
                continue
            draw.polygon([((ring[i] + shift - west) * scale, (north - ring[i + 1]) * scale)
                          for i in range(0, len(ring), 2)], fill=SEA)
            lines += [[((lon + shift - west) * scale, (north - lat) * scale) for lon, lat in run]
                      for run in coast_runs(ring)]
    for pts in lines:
        draw.line(pts, fill=COAST, width=k + 1)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def coast_runs(ring) -> list:
    """고리를 해안선의 토막들로 — 원본이 경위도 평면에서 자른 변(경도 ±180°, 위도 ±90° 를 따라가는 변)은 뺀다.
    진짜 해안이 아니다. `[[(경도, 위도)…]…]`"""
    pts = [(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)]
    pts.append(pts[0])
    runs, run = [], [pts[0]]
    for a, b in zip(pts, pts[1:]):
        seam = (abs(abs(a[0]) - 180.0) < 1e-6 and abs(a[0] - b[0]) < 1e-6) or \
               (abs(abs(a[1]) - 90.0) < 1e-6 and abs(a[1] - b[1]) < 1e-6)
        if seam:
            if len(run) > 1:
                runs.append(run)
            run = [b]
        else:
            run.append(b)
    if len(run) > 1:
        runs.append(run)
    return runs
