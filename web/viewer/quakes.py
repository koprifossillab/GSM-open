"""지진 — USGS 의 M5 이상 10 만 곳 남짓을 sqlite 로 굽고, 규모의 칸마다 경위도 타일에 원을 찍는다 (wetherilli 138).

`manage.py fetch_quakes` 가 문(`usgs.py`)으로 CSV 를 받아 여기서 `<EARTH_DIR>/quakes.sqlite` 로 굽는다. 화면이 부를 때는
이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다.

- **오늘의 레이어다.** 1900 년부터의 기록이라 판을 돌린 옛 지구에는 얹지 않는다 — 화면이 1 Ma 부터 끈다
- **규모로 세 레이어**(`BANDS`) — M6 이상·M5.5–6·M5–5.5. 따로 켜고 끈다. 작은 것까지 다 켜면 판 경계가 빽빽이 메워진다
- 원의 크기는 규모, 색은 **진원 깊이**(얕은 0–70 km·중간 70–300·깊은 300 km 넘게). 큰 것을 먼저 찍어 작은 것이 위에 온다
"""
import csv
import functools
import io
import math
import sqlite3
import time
from pathlib import Path

from django.conf import settings

from . import paleo
from .i18n import msg, t

FILE = "quakes.sqlite"
RENDERER = "1"

#: 규모의 칸 — 레이어 이름 → (이상, 미만)
BANDS = {"quake6": (6.0, 99.0), "quake55": (5.5, 6.0), "quake5": (5.0, 5.5)}
#: 진원 깊이 — (km 미만, 색, 범례 글)
DEPTHS = (
    (70, "#e4572e", msg("얕은 지진 (0–70 km)")),
    (300, "#f2c14e", msg("중간 깊이 (70–300 km)")),
    (1e9, "#3b7dd8", msg("깊은 지진 (300 km 넘게)")),
)


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def colour(depth) -> tuple:
    d = 0 if depth is None else depth
    for below, hexa, _ in DEPTHS:
        if d < below:
            break
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko") -> list:
    """범례 — `[{color, name}]`."""
    return [{"color": c, "name": t(name, lang)} for _, c, name in DEPTHS]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE quake (n INTEGER PRIMARY KEY, id TEXT, time TEXT, lon REAL, lat REAL, depth REAL, mag REAL,
                    mag_type TEXT, place TEXT);
CREATE VIRTUAL TABLE quake_xy USING rtree(id, x0, x1, y0, y1);
CREATE INDEX quake_mag ON quake(mag);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(csv_path, out_path, log=print) -> dict:
    """USGS FDSN 의 CSV → sqlite. 몇 초."""
    out_path = Path(out_path)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, skipped, started, seen = [], 0, time.time(), set()
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            lon, lat, mag = _num(rec.get("longitude")), _num(rec.get("latitude")), _num(rec.get("mag"))
            if lon is None or lat is None or mag is None or rec.get("id") in seen:
                skipped += 1
                continue
            seen.add(rec.get("id"))
            rows.append((len(rows) + 1, rec.get("id", ""), rec.get("time", ""), lon, lat, _num(rec.get("depth")), mag,
                         rec.get("magType", ""), rec.get("place", "")))
    db.executemany("INSERT INTO quake VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    db.executemany("INSERT INTO quake_xy VALUES (?, ?, ?, ?, ?)", [(r[0], r[3], r[3], r[4], r[4]) for r in rows])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))),
        ("source", "earthquake.usgs.gov fdsnws/event/1 M5+"), ("license", "public domain")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  {len(rows):,} 곳")
    return {"rows": len(rows), "skipped": skipped, "seconds": round(time.time() - started)}


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _open(mtime):
    db = sqlite3.connect(f"file:{path()}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def db():
    """구운 파일. 없으면 None."""
    try:
        return _open(path().stat().st_mtime)
    except (FileNotFoundError, sqlite3.OperationalError):
        return None


def available() -> bool:
    return db() is not None


def built() -> str:
    conn = db()
    return conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()[0] if conn else ""


def points(bands, west: float, south: float, east: float, north: float) -> list:
    """그 네모 안의, 고른 규모 칸(`BANDS` 의 이름들)의 지진 행."""
    conn = db()
    if conn is None or not bands:
        return []
    ranges = [BANDS[b] for b in bands]
    where = " OR ".join("(q.mag >= ? AND q.mag < ?)" for _ in ranges)
    args = [west, east, south, north] + [v for r in ranges for v in r]
    return list(conn.execute(
        "SELECT q.* FROM quake_xy x JOIN quake q ON q.n = x.id "
        f"WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ? AND ({where})", args))


def _radius(z: int, mag: float) -> float:
    base = 1.4 if z <= 1 else 1.9 if z <= 3 else 2.6 if z <= 5 else 3.4
    return base * (1 + max(0.0, mag - 5.0) * 0.55)


def render_tile(band: str, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 그 규모 칸의 지진을 찍는다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    pad = _radius(z, 9.5) * k / scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(r["lon"] + shift, r["lat"], r["mag"], r["depth"])
                  for r in points([band], w, north - span - pad, e, north + pad)]
    found.sort(key=lambda p: -p[2])
    for lon, lat, mag, depth in found:
        cx, cy, rad = (lon - west) * scale, (north - lat) * scale, _radius(z, mag) * k
        draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=colour(depth) + (200,),
                     outline=(25, 25, 25, 200), width=max(1, k // 2))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(bands, lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 지진 — 가까운 것부터. 날짜 바뀜선 너머도."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for r in points(bands, lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius):
            d2 = ((r["lon"] - lon - shift) * cos) ** 2 + (r["lat"] - lat) ** 2
            if d2 <= radius * radius:
                out.append((d2, -r["mag"], r))
    out.sort(key=lambda h: (h[0], h[1]))
    return [r for _, _, r in out[:limit]]
