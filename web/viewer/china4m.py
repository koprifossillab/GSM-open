"""중국 지질도 1:400만 (2002) — 좌표 없는 스캔 한 장에 **우리가 좌표를 붙인다** (wetherilli P14·386).

《中国地质图》(第二版) 1:4 000 000. 程裕淇 主编, 中国地质科学院地质研究所 编制, 地质出版社 2002 년 12 월.
자료 기준은 지리 2002 년 말, 지질 2002 년 6 월이다. 원본은 300 dpi JPEG 한 장(14 521 × 10 261)이고 좌표가
없다. 상류가 아니라 **우리 디스크의 파일**이라 문이 아니다 — `requests` 가 없다. `peninsula.py` 와 같은 자리다.

**출판 지도라 이용 조건이 적혀 있지 않다** — 연구실 내부용(`views.LAB_ONLY`)이다. 원본·마스크·잘라 둔 타일
모두 저장소·이미지에 두지 않는다. 원본은 NAS `N:\\GSM\\sources\\china4m\\`.

좌표 — 도곽의 경위선으로 맞췄다
-------------------------------

도곽에 경위선 눈금(위 68°–148°, 아래 100°–124°, 좌우 28°–48°, 4° 간격)이 있고 지도 안에 같은 간격의 경위선이
하늘색 가는 선으로 그려져 있다. 그 선을 따라 짚은 점 24 000 개에 **람베르트 정각원추(표준위선 25°N·47°N)** 와
아핀 하나를 맞췄다. 남는 어긋남은 중앙값 0.06 px, 90 % 가 1.1 px(450 m) 안이다. 알베르스 등적원추로는
2 배 넘게 어긋나 버렸다.

- 표준위선을 풀어 두면 17.5°·53.6° 로 가지만 축척과 맞바꿔질 뿐 맞춤은 같다 — 중국 지도에 흔한 25°·47° 로 둔다
- 중앙경선은 스캔의 기울기와 수학적으로 겹친다(원추를 돌리는 것이 곧 그림을 돌리는 것). 105°E 로 두고
  아핀의 회전이 나머지를 맡는다. 도곽이 반듯한 것으로 보아 원도의 중앙경선은 106°E 쯤이다
- 가로·세로 축척이 같다(투영 평면에서 한 화소 423.3 m, 북위 35° 의 땅 위로 431 m) — 스캔이 찌그러지지 않았다.
  1:400만을 300 dpi 로 읽었다면 339 m 여야 한다 — 원도를 80 % 남짓으로 줄인 판을 스캔한 것이다
- 타원체는 WGS84 로 둔다. 원도가 쓴 크라소프스키와의 차이는 아핀이 흡수하고 남는 것은 화소 아래다

**경위선은 맞지만 그려진 땅은 2–10 km 어긋난다.** 도시 기호 열여섯·해안 곶 열여섯을 대 보니 종이 위 0.5–2.5 mm
— 1:400만 원도가 땅을 일반화해 그린 정도다. 방향이 제각각이라 고무판처럼 펴지 않는다.
"""
import collections
import functools
import io
import json
import math
from pathlib import Path

from django.conf import settings

from . import crs

#: 원도의 투영 — 람베르트 정각원추. 원점 위도 0, 가산 없음, 미터
LAT1, LAT2, LON0 = 25.0, 47.0, 105.0
#: (동, 북)(m) → 원본 화소 (x, y).  x = a·동 + b·북 + c,  y = d·동 + e·북 + f
AFFINE = (0.002362134226172537, 2.43675081303265e-05, 6849.397556505154,
          2.448531433403248e-05, -0.002362136438657049, 15018.075813036525)

#: 원본 그림의 크기. 다르면 다른 스캔이다
SIZE = (14521, 10261)
#: 도곽 안쪽 선 (x0, y0, x1, y1) — 이 밖은 여백·눈금 글자다
NEATLINE = (166, 166, 14352, 9878)
#: 도곽 안이지만 지도가 아닌 것 (x0, y0, x1, y1) — 범례 둘, 남해제도 삽입도(축척이 다르다), 연대표, 제목
NOT_MAP = (
    (0, 6440, 2180, 10261),         # 图例 왼쪽 칸 (지층)
    (2160, 7380, 4990, 10261),      # 图例 오른쪽 칸 (화성암·무늬·부호)
    (12420, 7040, 14521, 10261),    # 南海诸岛 삽입도
    (13040, 4930, 14521, 7110),     # 지질시대 연대표
    (3900, 350, 9100, 1300),        # 제목 "中国地质图"
)

SOURCE = "GeoChina400*.jpg"
MASK = "GeoChina400_mask.png"


def root() -> Path:
    return Path(settings.CHINA4M_DIR)


def source_file():
    """원본 스캔. 여럿이면 이름이 가장 뒤인 것. 없으면 None."""
    found = sorted(root().glob(SOURCE)) if root().is_dir() else []
    return found[-1] if found else None


def mask_file() -> Path:
    return root() / MASK


# ── 좌표 ──────────────────────────────────────────────────────────────

def to_pixel(lon: float, lat: float) -> tuple:
    """위경도 → 원본 화소 (x, y). 화소의 왼쪽 위가 0 이다."""
    east, north = crs.latlon_to_lcc(lat, lon, LON0, LAT1, LAT2)
    a, b, c, d, e, f = AFFINE
    return a * east + b * north + c, d * east + e * north + f


def to_lonlat(x: float, y: float) -> tuple:
    """원본 화소 (x, y) → 위경도 (경도, 위도)."""
    a, b, c, d, e, f = AFFINE
    det = a * e - b * d
    dx, dy = x - c, y - f
    east, north = (e * dx - b * dy) / det, (a * dy - d * dx) / det
    lat, lon = crs.lcc_to_latlon(east, north, LON0, LAT1, LAT2)
    return lon, lat


def on_map(x: float, y: float) -> bool:
    """도곽 안이고 범례·삽입도·제목 자리가 아닌가."""
    x0, y0, x1, y1 = NEATLINE
    if not (x0 <= x < x1 and y0 <= y < y1):
        return False
    return not any(bx0 <= x < bx1 and by0 <= y < by1 for bx0, by0, bx1, by1 in NOT_MAP)


# ── 3857 타일 (wetherilli 387) ───────────────────────────────────────
#
# 원도의 람베르트 격자를 화면에 알리지 않고 **3857 z/x/y 로 다시 굽는다** — 중국 탭(3857)과 3D 가 그대로 쓴다.
# 굽는 데는 Pillow 의 `MESH` 변환만 쓴다. 타일을 8×8 칸으로 나눠 칸의 네 귀만 원본 화소로 옮기고
# 칸 안은 네 귀를 잇는 사변형으로 편다. 한 칸이 32 px 이라 원추의 휨이 칸 안에서 0.01 px 도 안 된다.

NAME = "china4m:geology"
FORMAT = "webp"
TILE = 256
HALF = 20037508.342789244
#: 마지막 줌 — 북위 35° 에서 한 화소 250 m 라 원본(431 m)을 조금 늘린다. 그 위는 화면이 늘린다
MAX_ZOOM = 9
#: 첫 줌 — 온 중국이 네 장
MIN_ZOOM = 3
#: 마스크가 덮는 범위(서, 남, 동, 북)에 반 화소 남짓 — 2026-10-16 의 마스크로 쟀다
BBOX = (72.5, 17.9, 136.5, 54.3)
#: 칸 수 — 한 변을 이만큼 나눠 네 귀만 옮긴다
MESH = 8
#: 화면이 레이어 곁에 적는 출처
ATTRIBUTION = "中国地质科学院地质研究所 · 地质出版社 2002"


def tiles_dir() -> Path:
    return root() / "tiles"


def available() -> bool:
    return tiles_dir().is_dir()


def tile_range(z: int) -> tuple:
    """줌 z 에서 `BBOX` 를 덮는 (x0, y0, x1, y1) — 끝을 넣는다."""
    west, south, east, north = BBOX
    n = 2 ** z

    def col(lon):
        return int((lon + 180.0) / 360.0 * n)

    def row(lat):
        y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        return int((1 - y / math.pi) / 2 * n)

    return col(west), row(north), col(east), row(south)


def valid_tile(z: int, x: int, y: int) -> bool:
    if not MIN_ZOOM <= z <= MAX_ZOOM:
        return False
    x0, y0, x1, y1 = tile_range(z)
    return x0 <= x <= x1 and y0 <= y <= y1


def tile_path(z: int, x: int, y: int) -> Path:
    return tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}"


def read_tile(z: int, x: int, y: int):
    """잘라 둔 타일(바이트). 그 자리가 비어 있으면(중국 밖) None."""
    try:
        return tile_path(z, x, y).read_bytes()
    except FileNotFoundError:
        return None


def merc_to_lonlat(mx: float, my: float) -> tuple:
    return mx / HALF * 180.0, math.degrees(2 * math.atan(math.exp(my / 6378137.0)) - math.pi / 2)


def factor_for(z: int) -> int:
    """줌 z 를 구울 때 원본을 몇 분의 일로 줄여 쓰나 — 2 의 거듭제곱. 줄여 둔 그림에서 펴야 계단이 지지 않는다.
    북위 35° 에서 타일 한 화소가 원본 몇 화소인지로 고른다."""
    ground = 2 * HALF / TILE / 2 ** z * math.cos(math.radians(35))
    ratio = ground / 431.0
    factor = 1
    while factor * 2 <= ratio:
        factor *= 2
    return factor


def mesh(z: int, x: int, y: int, factor: int = 1) -> list:
    """`Image.transform(…, Image.MESH, 이것)` 에 줄 칸 목록 — (타일 안 네모, 원본(줄인 것) 안 네 귀)."""
    size = 2 * HALF / 2 ** z
    west, north = -HALF + x * size, HALF - y * size
    step = TILE // MESH
    corners = {}
    for i in range(MESH + 1):
        for j in range(MESH + 1):
            lon, lat = merc_to_lonlat(west + i * step / TILE * size, north - j * step / TILE * size)
            px, py = to_pixel(lon, lat)
            corners[i, j] = (px / factor, py / factor)
    out = []
    for i in range(MESH):
        for j in range(MESH):
            ul, ll, lr, ur = corners[i, j], corners[i, j + 1], corners[i + 1, j + 1], corners[i + 1, j]
            out.append(((i * step, j * step, (i + 1) * step, (j + 1) * step), (*ul, *ll, *lr, *ur)))
    return out


def cut(level_image, factor: int, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). `level_image` 는 땅 밖이 투명한 원본을 `factor` 배 줄인 것(RGBa, 미리 곱한 것)이다.
    다 투명하면 None."""
    from PIL import Image
    tile = level_image.transform((TILE, TILE), Image.MESH, mesh(z, x, y, factor), Image.BILINEAR)
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile


def encode(tile) -> bytes:
    buf = io.BytesIO()
    tile.save(buf, format="WEBP", quality=82, method=4)
    return buf.getvalue()


# ── 범례와 색 번호 격자 (wetherilli 388) ─────────────────────────────
#
# 범례 173 칸(`data/china4m_legend.json`)의 색으로 원본을 칠해 **색 번호 격자**를 굽는다 — 원본을 반으로 줄여(한 칸 860 m) 칸마다
# 바이트 하나, 37 MB. Pillow 의 `quantize(palette=…)` 가 가장 가까운 색에 매긴다(정확한 최근접과 95 % 같다 — Pillow 는 색 상자로
# 어림한다). 0 은 땅 밖, 1 은 먹(검은 선·글자, 청록 지명 글자도 여기로 접는다), 2 는 물(호수·강의 연한 하늘색), 그다음이 범례 색이다. 범례에서 색이 같은 칸(ΔRGB 3 안)은 한 번호를 함께 쓴다 — 쥐라계 청록과 바다, 원생대 변성
# 칸과 덮개 칸 따위다. 누를 때는 둘레 창에서 먹을 뺀 다수결로 고르고(`unit_at`), 범례는 보는 범위를 표본으로 센다(`extent_legend`).

UNITS = "units.u8"
UNITS_META = "units.json"
#: 색 번호 격자의 줄임 — 원본 두 화소에 한 칸
UNITS_SCALE = 2
OUTSIDE, INK, WATER = 0, 1, 2
#: 먹·물·지명 글자의 색 — 2026-10-16 에 땅 화소 가운데 범례 색에서 먼 것을 셌다(먹이 거의 다다). 청록 지명 글자·도시 기호
#: (32,130,120)와 그 가장자리는 섬록암 δ(0,204,127)·D₁ 으로 끌려가 황토고원에서까지 δ 가 범례 위에 떴다 — 먹으로 접는다
SPECIAL = ((0, 0, 0), (228, 252, 252), (32, 130, 120), (70, 124, 108))
#: 먹으로 접는 팔레트 번호 — 0(땅 밖과 같은 검정)과 지명 글자
_TO_INK = (0, 3, 4)
#: 같은 색으로 묶는 거리(RGB)
SAME = 3

#: 범례 칸의 종류 → (한국어, 영어)
KINDS = {"stratum": ("지층", "stratified unit"), "intrusive": ("관입암", "intrusive rock"),
         "hypabyssal": ("천성암·잠화산암", "hypabyssal rock"), "volcanic": ("화산암", "volcanic rock"),
         "mixed": ("혼잡암", "mélange")}


def legend_path() -> Path:
    return Path(settings.CHINA4M_LEGEND)


@functools.lru_cache(maxsize=1)
def legend() -> dict:
    return json.loads(legend_path().read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def classes() -> list:
    """색 번호 → 범례 칸 id 들. 땅 밖·먹·물·지명 글자는 빈 목록이다. 바다 수심 칸은 넣지 않는다 — 땅 안의 그 색은 쥐라계다."""
    out = [[] for _ in range(len(SPECIAL) + 1)]
    colors = list(SPECIAL)
    for unit in legend()["units"]:
        if unit["kind"] == "ocean" or not unit.get("rgb"):
            continue
        rgb = tuple(unit["rgb"])
        for i, color in enumerate(colors[len(SPECIAL):], start=len(SPECIAL) + 1):
            if max(abs(a - b) for a, b in zip(rgb, color)) <= SAME:
                out[i].append(unit["id"])
                break
        else:
            colors.append(rgb)
            out.append([unit["id"]])
    classes.colors = colors
    return out


def palette() -> list:
    """quantize 에 줄 팔레트 — 번호 0 은 땅 밖(먹과 같은 검정이라 칠한 뒤 다시 1 로 돌린다)."""
    classes()
    return [(0, 0, 0)] + list(classes.colors)


def units_by_id() -> dict:
    return {u["id"]: u for u in legend()["units"]}


def build_units(image, mask):
    """원본(RGB)·마스크(L) → (가로, 세로, 바이트). 원본의 1/`UNITS_SCALE`."""
    from PIL import Image
    w, h = image.size[0] // UNITS_SCALE, image.size[1] // UNITS_SCALE
    small = image.resize((w, h), Image.NEAREST)
    land = mask.resize((w, h), Image.NEAREST)
    pal = palette()
    table = Image.new("P", (1, 1))
    flat = [v for c in pal for v in c]
    table.putpalette(flat + [0] * (768 - len(flat)))
    indexed = small.quantize(palette=table, dither=Image.Dither.NONE)
    # 번호 0 과 1 은 같은 검정 — quantize 는 앞의 0 을 고른다. 땅 안의 0 은 먹(1)으로, 땅 밖은 0 으로
    numbers = Image.frombytes("L", (w, h), indexed.tobytes()).point(lambda v: INK if v in _TO_INK else v)
    numbers = Image.composite(numbers, Image.new("L", (w, h), OUTSIDE), land)
    return w, h, numbers.tobytes()


def units_available() -> bool:
    return (root() / UNITS).exists() and (root() / UNITS_META).exists()


@functools.lru_cache(maxsize=1)
def _units_meta(stamp: float) -> dict:
    return json.loads((root() / UNITS_META).read_text(encoding="utf-8"))


def units_meta() -> dict:
    return _units_meta((root() / UNITS_META).stat().st_mtime)


def _window(cx: int, cy: int, r: int) -> list:
    """색 번호 격자에서 (cx, cy) 둘레 (2r+1)² 칸 — 격자 밖은 0."""
    meta = units_meta()
    w, h = meta["width"], meta["height"]
    out = []
    with open(root() / UNITS, "rb") as f:
        for y in range(cy - r, cy + r + 1):
            if not 0 <= y < h:
                out.extend([OUTSIDE] * (2 * r + 1))
                continue
            x0, x1 = max(cx - r, 0), min(cx + r + 1, w)
            f.seek(y * w + x0)
            row = f.read(max(0, x1 - x0))
            out.extend([OUTSIDE] * (x0 - (cx - r)) + list(row) + [OUTSIDE] * ((cx + r + 1) - x1))
    return out


#: 누른 자리를 고르는 창의 반지름(색 번호 칸, 한 칸 860 m) — 지층 부호 글자(2–3 mm) 하나를 넘는다
RADIUS = 3


def unit_at(lon: float, lat: float):
    """누른 자리의 색 번호와 그 몫 — (번호, 몫) 또는 None(땅 밖). 먹은 세지 않는다."""
    x, y = to_pixel(lon, lat)
    if not on_map(x, y):
        return None
    cx, cy = int(x // UNITS_SCALE), int(y // UNITS_SCALE)
    cells = _window(cx, cy, RADIUS)
    if cells[len(cells) // 2] == OUTSIDE:
        return None
    counts = collections.Counter(v for v in cells if v not in (OUTSIDE, INK))
    if not counts:
        return None
    # 가운데에 가까울수록 무겁게 — 경계에서 옆 칸에 끌려가지 않게
    side = 2 * RADIUS + 1
    weighted = collections.Counter()
    for i, v in enumerate(cells):
        if v in (OUTSIDE, INK):
            continue
        dx, dy = i % side - RADIUS, i // side - RADIUS
        weighted[v] += 1.0 / (1 + dx * dx + dy * dy)
    best, _ = weighted.most_common(1)[0]
    return best, counts[best] / sum(counts.values())


def _pick(unit: dict, field: str, lang: str) -> str:
    return unit.get(f"{field}_{lang}") or unit.get(f"{field}_ko") or ""


def _ma(unit: dict) -> str:
    top, base = unit.get("age_top_ma"), unit.get("age_base_ma")
    if top is None and base is None:
        return ""
    if base is None:
        return f"> {top:g}"
    return f"{top:g}–{base:g}"


def friendly(index: int, lang: str = "ko") -> dict:
    """팝업의 칸 — 범례에서 옮긴 그대로. 색이 같은 칸이 여럿이면 첫 칸을 보이고 나머지는 "같은 색의 칸" 에 적는다."""
    if index == WATER:
        return {"갈래": "물 (호수·강)" if lang == "ko" else "Water (lake, river)"}
    ids = classes()[index] if 0 <= index < len(classes()) else []
    if not ids:
        return {}
    units = units_by_id()
    # 막대(계·대 묶음)보다 세분 칸이 먼저다 — 지도는 대개 세분으로 칠한다
    ordered = sorted(ids, key=lambda i: bool(units[i].get("bar")))
    unit = units[ordered[0]]
    kind = KINDS.get(unit["kind"], ("", ""))[0 if lang == "ko" else 1]
    origin, text = unit.get("desc_zh", ""), _pick(unit, "desc", lang)
    if origin and origin in text:             # 지층 칸의 설명은 "대표 층군: <원문>" 이라 되풀이다
        text = ""
    rows = (("기호", unit["code"]), ("갈래", kind), ("지질시대", _pick(unit, "age", lang)), ("연대 (Ma)", _ma(unit)),
            ("암상", _pick(unit, "lith", lang)), ("대표 층군", origin), ("설명", text),
            ("같은 색의 칸", " · ".join(units[i]["code"] for i in ordered[1:])))
    return {k: v for k, v in rows if v}


def legend_row(index: int, lang: str = "ko") -> dict:
    ids = classes()[index]
    units = units_by_id()
    ordered = sorted(ids, key=lambda i: bool(units[i].get("bar")))
    unit = units[ordered[0]]
    codes = " · ".join(units[i]["code"] for i in ordered)
    what = _pick(unit, "lith", lang) or KINDS.get(unit["kind"], ("", ""))[0 if lang == "ko" else 1]
    r, g, b = classes.colors[index - 1]
    return {"symbol": codes, "lithology": f"{codes} {what}".strip(), "age": _pick(unit, "age", lang),
            "color": f"rgb({r},{g},{b})", "swatch": ""}


#: 범례를 세는 표본 — 범위를 이만큼의 격자로 짚는다
LEGEND_SAMPLES = 90
MAX_LEGEND = 40


def extent_legend(west: float, south: float, east: float, north: float, lang: str = "ko") -> tuple:
    """보는 범위에 든 범례 칸 — (행들, 더 있는 칸 수). 범위를 격자로 짚어 많이 나온 칸부터.
    짚은 땅의 0.3 % 에 못 미치는 칸은 버린다 — 먹·경계 가장자리의 섞인 색이 엉뚱한 칸으로 한두 번씩 잡힌다."""
    meta = units_meta()
    w, h = meta["width"], meta["height"]
    counts = collections.Counter()
    table = classes()
    with open(root() / UNITS, "rb") as f:
        for j in range(LEGEND_SAMPLES):
            lat = south + (north - south) * (j + 0.5) / LEGEND_SAMPLES
            for i in range(LEGEND_SAMPLES):
                lon = west + (east - west) * (i + 0.5) / LEGEND_SAMPLES
                x, y = to_pixel(lon, lat)
                cx, cy = int(x // UNITS_SCALE), int(y // UNITS_SCALE)
                if not (on_map(x, y) and 0 <= cx < w and 0 <= cy < h):
                    continue
                f.seek(cy * w + cx)
                v = f.read(1)[0]
                if v < len(table) and table[v]:
                    counts[v] += 1
    floor = max(2, sum(counts.values()) * 0.003)
    picked = [i for i, n in counts.most_common() if n >= floor]
    return [legend_row(i, lang) for i in picked[:MAX_LEGEND]], max(0, len(picked) - MAX_LEGEND)


# ── 지명 이름표 (wetherilli 389) ─────────────────────────────────────
#
# 원도에 적힌 지명은 그림이라 누를 수 없고, 한자라 못 읽는 사람이 많다. Natural Earth 10 m(퍼블릭 도메인, `data/earth_places.json`)의
# 도시·산맥·사막·분지·강·호수 가운데 **중국 땅(색 번호 격자가 땅이라 하는 곳) 안의 것**을 한국어(영어판이면 영어)와 한자를
# 나란히 적은 이름표로 낸다. 1:400만 원도의 밀도(성도·주요 도시·큰 산맥·분지·강·호수)와 맞는다. 바다 이름은 원도의 바다가 지워져
# 있어(386) 띄우지 않는다. 화면이 순위(scalerank)로 멀리서는 큰 것만 띄우고 겹친 글자를 거른다.

PLACES = "china4m:places"
#: 이름표로 띄우는 Natural Earth 갈래
PLACE_KINDS = {"city", "river", "lake", "Range/mtn", "Plateau", "Desert", "Basin", "Plain", "Peninsula", "Island",
               "Island group", "Valley", "Delta", "Depression", "Lowland", "Foothills", "Gorge", "Wetlands", "Geoarea"}


def _on_land(lon: float, lat: float) -> bool:
    """중국 땅인가 — 색 번호 격자가 있으면 그 칸이 땅 밖(0)이 아닌지, 없으면 `BBOX` 와 도곽만 본다."""
    x, y = to_pixel(lon, lat)
    if not on_map(x, y):
        return False
    if not units_available():
        west, south, east, north = BBOX
        return west <= lon <= east and south <= lat <= north
    return _window(int(x // UNITS_SCALE), int(y // UNITS_SCALE), 1).count(OUTSIDE) < 9


def place_features(lang: str = "ko") -> list:
    """이름표 GeoJSON feature 들 — 속성은 `label`(보일 글)·`kind`·`rank`(작을수록 크다)."""
    from . import naturalearth
    out = []
    for name, ko, kind, lon, lat, rank, *rest in naturalearth.places():
        if kind not in PLACE_KINDS or not _on_land(lon, lat):
            continue
        zh = rest[0] if rest else ""
        shown = (ko or name) if lang == "ko" else name
        label = f"{shown} {zh}" if zh and zh != shown else shown
        out.append({"type": "Feature", "id": len(out), "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"label": label, "kind": kind, "rank": rank}})
    return out


def places_body(lang: str = "ko") -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": place_features(lang)},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class China4mError(RuntimeError):
    pass


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "china4m", "tag": "LAB", "title": "연구실 자료"},
]
