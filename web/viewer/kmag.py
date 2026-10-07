"""다누리 자기장 측정기(KMAG)의 궤적 — 하루치 CSV 를 줄여 sqlite 한 장에 (wetherilli 377). 문이 아니다.

`manage.py fetch_kmag` 이 KPDS(`kpds.py`)에서 Calibrated 하루치(4 초 간격, 21 600 행)를 받아 **32 초마다 한 점**만 남겨
`<KPDS_DIR>/kmag.sqlite` 에 더한다. 화면은 이것만 읽는다.

- 자리는 `X/Y/Z_SEL`(km)에서 푼다. 라벨이 SEL 을 정의하지 않는다 — 달 고정 좌표계(달의 평균 지구 방향이 +X)로 읽었다.
  하루에 궤도 경도가 13° 남짓 서쪽으로 밀려(달의 자전) 그렇게 읽는 것이 맞다. 고도는 1 737.4 km 구 위의 높이다
- 값은 그 자리의 자기장 세기 |B|(nT, SEL 성분에서). **지각 자기 이상이 아니다** — 태양풍·지구 자기권의 바깥 자기장이 섞인 값이라
  화면은 이것으로 궤적을 칠하지 않고 누른 자리에서만 보인다(사용자가 정했다)
- 빈 값(−99999)은 자리만 두고 |B| 를 비운다
- 같은 하루를 두 번 넣지 않는다(`days`). 줄인 간격을 바꾸면 `RENDERER` 를 올리고 다시 모은다
"""
import csv
import functools
import io
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

FILE = "kmag.sqlite"
RENDERER = "1"
STEP = 32                        # 초 — 이 간격마다 한 점. 궤도 속도 1.6 km/s 로 50 km 남짓
GAP = 2 * STEP + 1               # 이보다 벌어지면 궤적을 끊는다
ORBIT = 7200                     # 초 — 궤도 한 바퀴 남짓(고도 100 km 에서 118 분). 넓게 볼 때 궤도를 이 토막으로 솎는다
RADIUS = 1737.4                  # km
FILL = -99999.0
CITE = "KPLO (Danuri) KMAG calibrated magnetic field — KARI KPDS; instrument: Kyung Hee University"
SCHEMA = """
CREATE TABLE IF NOT EXISTS points (id INTEGER PRIMARY KEY, t INTEGER NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL,
                                   alt REAL NOT NULL, b REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS points_idx USING rtree(id, lon0, lon1, lat0, lat1);
CREATE TABLE IF NOT EXISTS days (name TEXT PRIMARY KEY, n INTEGER NOT NULL, added TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS points_t ON points (t);
"""


def path() -> Path:
    return Path(settings.KPDS_DIR) / FILE


def connect(write: bool = False):
    """sqlite 하나. 읽기만 할 때 파일이 없으면 None."""
    p = path()
    if not write and not p.exists():
        return None
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p)
        conn.executescript(SCHEMA)
        return conn
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)


def available() -> bool:
    return path().exists()


def parse(text: str) -> list:
    """하루치 CSV → `[(유닉스 초, 경도, 위도, 고도 km, |B| 또는 None)…]`, `STEP` 초마다 하나."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            t = datetime.strptime(row["UTC"].strip()[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        sec = int(t.timestamp())
        if sec % STEP:
            continue
        try:
            x, y, z = (float(row[k]) for k in ("X_SEL", "Y_SEL", "Z_SEL"))
            bx, by, bz = (float(row[k]) for k in ("Bx_SEL", "By_SEL", "Bz_SEL"))
        except (KeyError, ValueError):
            continue
        r = math.sqrt(x * x + y * y + z * z)
        if not RADIUS < r < RADIUS + 3000:
            continue
        b = None if FILL in (bx, by, bz) else round(math.sqrt(bx * bx + by * by + bz * bz), 2)
        out.append((sec, round(math.degrees(math.atan2(y, x)), 4), round(math.degrees(math.asin(z / r)), 4),
                    round(r - RADIUS, 1), b))
    return out


def add_day(conn, name: str, points: list) -> int:
    """하루치를 더한다. 이미 있으면 0."""
    if conn.execute("SELECT 1 FROM days WHERE name = ?", (name,)).fetchone():
        return 0
    with conn:
        for sec, lon, lat, alt, b in points:
            cur = conn.execute("INSERT INTO points (t, lon, lat, alt, b) VALUES (?, ?, ?, ?, ?)", (sec, lon, lat, alt, b))
            conn.execute("INSERT INTO points_idx VALUES (?, ?, ?, ?, ?)", (cur.lastrowid, lon, lon, lat, lat))
        conn.execute("INSERT INTO days VALUES (?, ?, ?)", (name, len(points), datetime.now(timezone.utc).isoformat()))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),))
    return len(points)


def has_day(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM days WHERE name = ?", (name,)).fetchone() is not None


def stamp() -> str:
    """캐시 열쇠에 넣을 판 — 날이 더해지면 바뀐다."""
    conn = connect()
    if conn is None:
        return ""
    try:
        row = conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()
    finally:
        conn.close()
    return f"{RENDERER}-{row[0] if row else ''}"


def summary() -> dict:
    """`{"days", "points", "first", "last"}` — 모은 것이 없으면 빈 dict."""
    conn = connect()
    if conn is None:
        return {}
    try:
        days, = conn.execute("SELECT COUNT(*) FROM days").fetchone()
        n, lo, hi = conn.execute("SELECT COUNT(*), MIN(t), MAX(t) FROM points").fetchone()
    finally:
        conn.close()
    iso = lambda s: datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%d") if s else None   # noqa: E731
    return {"days": days, "points": n, "first": iso(lo), "last": iso(hi)}


def tracks(west: float, south: float, east: float, north: float, every: int = 1, orbits: int = 1) -> list:
    """네모(달 경위도) 안의 궤적 — `[[(경도, 위도)…]…]`. 시각 차례로 잇고, `GAP` 초가 넘게 벌어지거나 날짜변경선을
    넘으면 끊는다. `every` 는 몇 점에 하나만 쓸지, `orbits` 는 궤도(`ORBIT` 초 토막) 몇에 하나만 쓸지 — 넓게 볼 때."""
    conn = connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT p.t, p.lon, p.lat FROM points p JOIN points_idx i ON i.id = p.id "
            "WHERE i.lon1 >= ? AND i.lon0 <= ? AND i.lat1 >= ? AND i.lat0 <= ? AND (p.t / ?) % ? = 0 "
            "AND (p.t / ?) % ? = 0 ORDER BY p.t",
            (west, east, south, north, STEP, max(1, every), ORBIT, max(1, orbits))).fetchall()
    finally:
        conn.close()
    out, line, last = [], [], None
    gap = GAP * max(1, every)
    for t, lon, lat in rows:
        if line and (t - last > gap or abs(lon - line[-1][0]) > 180):
            if len(line) > 1:
                out.append(line)
            line = []
        line.append((lon, lat))
        last = t
    if len(line) > 1:
        out.append(line)
    return out


def nearest(lon: float, lat: float, reach: float = 0.5):
    """누른 자리에서 가장 가까운 점 — `{"time", "lon", "lat", "alt", "b"}` 또는 None. `reach` 는 도."""
    conn = connect()
    if conn is None:
        return None
    k = max(math.cos(math.radians(lat)), 0.05)
    try:
        rows = conn.execute(
            "SELECT p.t, p.lon, p.lat, p.alt, p.b FROM points p JOIN points_idx i ON i.id = p.id "
            "WHERE i.lon1 >= ? AND i.lon0 <= ? AND i.lat1 >= ? AND i.lat0 <= ?",
            (lon - reach / k, lon + reach / k, lat - reach, lat + reach)).fetchall()
    finally:
        conn.close()
    best = min(rows, key=lambda r: ((r[1] - lon) * k) ** 2 + (r[2] - lat) ** 2, default=None)
    if best is None:
        return None
    t, plon, plat, alt, b = best
    return {"time": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "lon": plon, "lat": plat, "alt": alt, "b": b}


# ── 타일 (wetherilli 378) ────────────────────────────────────────────
#
# 달 화면의 "다누리 자기장 측정기(KMAG) 궤적" — 한 색 가는 선이다. **|B| 로 칠하지 않는다**(바깥 자기장이 섞여 지각 자기 이상처럼
# 읽히면 오해다, 사용자가 정했다). 궤도가 1 만 번 넘게 돌아 다 그으면 온 달이 한 빛으로 덮이므로, 멀리서는 궤도를 솎고(`_orbits`)
# 점도 성기게 긋는다 — 줄 하나하나가 궤적으로 읽히게. 격자는 Trek 의 것(경위도·극 평사도법)이라 지질도와 한 칸도 어긋나지 않는다.
# 그리는 법을 고치면 `DRAW` 를 올린다 — 캐시 열쇠에 `stamp()` 와 함께 든다(`views._kmag_tile`)

DRAW = "1"
TILE = 256
SUPERSAMPLE = 2
COLOR = (110, 214, 255)


def _every(z: int) -> int:
    """줌마다 몇 점에 하나 — 점 사이가 50 km(경위도 1.65°) 남짓이라 가까이서는 다 긋는다"""
    return {0: 8, 1: 8, 2: 4, 3: 2}.get(z, 1)


def _alpha(z: int) -> int:
    return 110 if z <= 3 else 140 if z <= 5 else 180


#: 줌마다 온 달에 긋는 궤도 수의 끝 — 넘으면 궤도를 솎는다. 다 그으면 1 만 번 넘는 궤도가 온 달을 한 빛으로 덮는다
_ORBIT_LINES = {0: 240, 1: 480, 2: 960, 3: 1920, 4: 3840, 5: 7680}


@functools.lru_cache(maxsize=4)
def _orbit_count(stamp_: str) -> int:
    conn = connect()
    if conn is None:
        return 0
    try:
        lo, hi = conn.execute("SELECT MIN(t), MAX(t) FROM points").fetchone()
        days, = conn.execute("SELECT COUNT(*) FROM days").fetchone()
    finally:
        conn.close()
    return days * 86400 // ORBIT if lo is not None else 0


def _orbits(z: int) -> int:
    """이 줌에서 궤도 몇에 하나를 긋나 — 모은 날 수에 따라"""
    top = _ORBIT_LINES.get(z)
    return max(1, round(_orbit_count(stamp()) / top)) if top else 1


def _png(img) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    img.resize((TILE, TILE), Image.Resampling.BOX).save(buf, format="PNG")
    return buf.getvalue()


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장(`trek.tile_bbox`) — 256 px 투명 PNG."""
    from PIL import Image, ImageDraw

    from . import trek
    w, s, e, n = trek.tile_bbox(z, x, y)
    size = TILE * SUPERSAMPLE
    k = size / (e - w)
    pad = 4 / k * _every(z)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    color = COLOR + (_alpha(z),)
    for line in tracks(w - pad, s - pad, e + pad, n + pad, _every(z), _orbits(z)):
        run = []
        for i, (lon, lat) in enumerate(line):
            # 극을 넘는 토막(경도가 크게 뛴다)은 경위도 평면에서 가로지르는 선이 된다 — 거기서 끊는다
            if run and abs(lon - line[i - 1][0]) > 90:
                if len(run) > 1:
                    draw.line(run, fill=color, width=SUPERSAMPLE)
                run = []
            run.append(((lon - w) * k, (n - lat) * k))
        if len(run) > 1:
            draw.line(run, fill=color, width=SUPERSAMPLE)
    return _png(img)


def render_polar_tile(pole: str, z: int, x: int, y: int) -> bytes:
    """극 격자 한 장(`trek.polar_tile_bbox`) — 256 px 투명 PNG. 묻는 네모는 타일 둘레를 경위도로 되짚은 것이다
    (`moonmap.render_polar_tile` 과 같다) — 극을 품거나 날짜변경선에 걸치면 경도를 다 묻는다."""
    from PIL import Image, ImageDraw

    from . import trek
    w, s, e, n = trek.polar_tile_bbox(z, x, y)
    size = TILE * SUPERSAMPLE
    k = size / (e - w)
    edge = [(w + (e - w) * i / 16, yy) for i in range(17) for yy in (n, s)]
    edge += [(xx, s + (n - s) * i / 16) for i in range(17) for xx in (w, e)]
    lls = [trek.polar_to_lonlat(px, py, pole) for px, py in edge]
    lats = [ll[1] for ll in lls]
    inside_pole = w <= 0 <= e and s <= 0 <= n
    lat_lo, lat_hi = (min(lats), 90.0) if pole == "n" else (-90.0, max(lats))
    crosses = inside_pole or (w <= 0 <= e and (n > 0 if pole == "n" else s < 0))
    lon_lo, lon_hi = (-180.0, 180.0) if crosses else (min(ll[0] for ll in lls), max(ll[0] for ll in lls))
    pad = 2.0 * _every(z)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    color = COLOR + (_alpha(z),)
    for line in tracks(lon_lo - pad, max(-90.0, lat_lo - pad), lon_hi + pad, min(90.0, lat_hi + pad), _every(z), _orbits(z)):
        pts = []
        for lon, lat in line:
            px, py = trek.lonlat_to_polar(lon, lat, pole)
            pts.append(((px - w) * k, (n - py) * k))
        draw.line(pts, fill=color, width=SUPERSAMPLE)
    return _png(img)
