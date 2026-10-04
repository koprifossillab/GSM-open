"""화석 산지 — PBDB 의 산지 27 만 곳을 sqlite 로 굽고, 연대마다 그 자리에 점을 찍는다 (wetherilli P07 §3·098).

`manage.py fetch_pbdb` 가 문(`pbdb.py`)으로 CSV 를 받아 여기서 `<EARTH_DIR>/pbdb.sqlite` 로 굽는다. 화면이 부를 때는
이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다.

- **오늘(0)** 은 모든 산지를 오늘의 자리에. **1 Ma 안쪽**은 그 연대를 품은 산지(`min_ma ≤ 연대 ≤ max_ma`)를 오늘의
  자리에. **1 Ma 부터**는 그 산지를 우리 판 회전(`paleo.py`)으로 그때의 자리에 — 판 조각과 같은 셈이라 점이 대륙 위에 선다
- PBDB 도 옛 좌표를 준다(`pgm=scotese`, 연대의 가운데에서). 함께 담아 팝업에 나란히 적는다. 셈이 같은 계열이라 대개
  가깝지만 PBDB 는 GPlates 의 PALEOMAP 판으로, 연대의 가운데에서만 옮긴다
- 판은 연대와 상관없어 구울 때 한 번 찾는다(`plate_at`). 바다 밑(판 조각 밖)의 산지는 오늘만 뜨고 옛 연대에는 뜨지 않는다
- 점의 색은 산지 연대의 가운데가 드는 **기(period)의 ICS 색**이다
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

FILE = "pbdb.sqlite"
RENDERER = "1"
PALEO_FROM = 1.0                 # Ma — 이 연대부터 판을 돌린다 (화면의 `PALEO_FROM` 과 같다)

#: ICS 국제층서표 v2024/12 의 기(period) — (밑 연대 Ma, 색). 선캄브리아는 누대의 색 하나
PERIODS = (
    (2.58, "#F9F97F"), (23.03, "#FFE619"), (66.0, "#FD9A52"), (145.0, "#7FC64E"), (201.4, "#34B2C9"),
    (251.902, "#812B92"), (298.9, "#F04028"), (358.9, "#67A599"), (419.2, "#CB8C37"), (443.8, "#B3E1B6"),
    (485.4, "#009270"), (538.8, "#7FA056"), (1e9, "#F74370"),
)


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def colour(mid: float) -> tuple:
    for base, hexa in PERIODS:
        if mid <= base:
            return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return (247, 67, 112)


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE coll (no INTEGER PRIMARY KEY, lon REAL, lat REAL, max_ma REAL, min_ma REAL, name TEXT, formation TEXT,
                   early TEXT, late TEXT, env TEXT, n_occs INTEGER, cc TEXT, ref TEXT,
                   pid INTEGER, flon REAL, flat REAL, reach REAL, pb_lon REAL, pb_lat REAL);
CREATE VIRTUAL TABLE coll_xy USING rtree(id, x0, x1, y0, y1);
CREATE INDEX coll_age ON coll(min_ma, max_ma);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(csv_path, out_path, log=print) -> dict:
    """PBDB 의 `colls/list.csv` → sqlite. 판을 붙이는 셈이 산지마다 1 ms 안이라 몇 분 걸린다."""
    m = paleo.model()
    out_path = Path(out_path)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, skipped, plated, started = 0, 0, 0, time.time()
    csv.field_size_limit(1 << 24)
    with open(csv_path, encoding="utf-8", newline="") as fh:
        batch = []
        for rec in csv.DictReader(fh):
            lon, lat = _num(rec.get("lng")), _num(rec.get("lat"))
            old, young = _num(rec.get("max_ma")), _num(rec.get("min_ma"))
            if lon is None or lat is None or old is None:
                skipped += 1
                continue
            young = old if young is None else young
            plate = m.plate_at_cached(lon, lat) if m else None
            if plate:
                plated += 1
            batch.append((int(rec["collection_no"]), lon, lat, old, young, rec.get("collection_name", ""),
                          rec.get("formation", ""), rec.get("early_interval", ""), rec.get("late_interval", ""),
                          rec.get("environment", ""), int(_num(rec.get("n_occs")) or 0), rec.get("cc", ""),
                          rec.get("primary_reference", ""),
                          plate["pid"] if plate else None, plate["lon"] if plate else None,
                          plate["lat"] if plate else None, plate["reach"] if plate else None,
                          _num(rec.get("paleolng")), _num(rec.get("paleolat"))))
            rows += 1
            if len(batch) >= 5000:
                _flush(db, batch)
                batch = []
                if rows % 50000 == 0:
                    log(f"  {rows:,} 곳 ({time.time() - started:.0f} 초)")
        _flush(db, batch)
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(rows)), ("source", "paleobiodb.org data1.2 colls/list"),
        ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    return {"rows": rows, "skipped": skipped, "plated": plated, "seconds": round(time.time() - started)}


def _flush(db, batch):
    db.executemany("INSERT OR REPLACE INTO coll VALUES (" + ",".join("?" * 19) + ")", batch)
    db.executemany("INSERT OR REPLACE INTO coll_xy VALUES (?, ?, ?, ?, ?)",
                   [(r[0], r[1], r[1], r[2], r[2]) for r in batch])


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


@functools.lru_cache(maxsize=6)
def _moved(age: float) -> tuple:
    """1 Ma 부터 — 그 연대를 품은 산지를 그때의 자리로. `(경도, 위도, 번호, 가운데 연대)` 의 목록.
    판마다 회전을 한 번 셈하고 산지마다 돌리기만 한다. 판이 닿지 않는 연대(`reach`)의 산지는 뺀다."""
    m, conn = paleo.model(), db()
    out, turns = [], {}
    for r in conn.execute("SELECT no, flon, flat, pid, reach, max_ma, min_ma FROM coll "
                          "WHERE min_ma <= ? AND max_ma >= ? AND pid IS NOT NULL", (age, age)):
        if age > r["reach"] + 1e-9:
            continue
        q = turns.get(r["pid"], 0)
        if q == 0:
            q = turns[r["pid"]] = m.rotations.rotation(r["pid"], age)
        if q is None:
            continue
        lon, lat = paleo.turn(q, r["flon"], r["flat"])
        out.append((lon, lat, r["no"], (r["max_ma"] + r["min_ma"]) / 2))
    return tuple(out)


def points(age: float, west: float, south: float, east: float, north: float) -> list:
    """그 연대에 그 네모 안에 찍히는 점 `(경도, 위도, 번호, 가운데 연대)`."""
    conn = db()
    if conn is None:
        return []
    if age >= PALEO_FROM:
        return [p for p in _moved(round(age)) if west <= p[0] <= east and south <= p[1] <= north]
    sql = ("SELECT c.no, c.lon, c.lat, c.max_ma, c.min_ma FROM coll_xy x JOIN coll c ON c.no = x.id "
           "WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?")
    args = [west, east, south, north]
    if age > 0:
        sql += " AND c.min_ma <= ? AND c.max_ma >= ?"
        args += [age, age]
    return [(r["lon"], r["lat"], r["no"], (r["max_ma"] + r["min_ma"]) / 2) for r in conn.execute(sql, args)]


def render_tile(age: float, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 점을 찍는다. 오래된 것을 먼저 — 젊은 것이 위에 온다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    radius = (1.6 if z <= 1 else 2.2 if z <= 3 else 3.0 if z <= 5 else 3.8) * k
    pad = radius / scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(lon + shift, lat, mid) for lon, lat, _, mid in points(age, w, north - span - pad, e, north + pad)]
    found.sort(key=lambda p: -p[2])
    for lon, lat, mid in found:
        cx, cy = (lon - west) * scale, (north - lat) * scale
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=colour(mid) + (235,),
                     outline=(20, 20, 20, 220), width=max(1, k // 2))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(age: float, lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 산지 — 가까운 것부터. 행(sqlite3.Row)과 찍힌 자리."""
    conn = db()
    if conn is None:
        return []
    cos = max(0.05, math.cos(math.radians(lat)))
    box = points(age, lon - radius / cos, lat - radius, lon + radius / cos, lat + radius)
    hits = sorted(((((p[0] - lon) * cos) ** 2 + (p[1] - lat) ** 2, p) for p in box), key=lambda h: h[0])
    out = []
    for d2, p in hits[:limit]:
        if d2 > radius * radius:
            break
        row = conn.execute("SELECT * FROM coll WHERE no = ?", (p[2],)).fetchone()
        out.append((row, (p[0], p[1])))
    return out


def search(query: str, limit: int = 8, formations: int = 5) -> tuple:
    """`query` 가 이름에 든 산지와 지층 (wetherilli 187). 화면의 찾기 칸이 지명과 섞는다.

    27 만 줄을 `LIKE` 로 훑어도 0.1–0.2 초다(2026-10-04). 따로 색인(FTS5)을 굽지 않았다 — 구운 파일을 다시 구워야 하고, 이 빠르기면
    찾기 칸(200 ms 쉬고 묻는다)에 넉넉하다. 지층은 산지마다 적혀 있어 이름으로 묶고, 화석이 가장 많은 산지의 자리를 그 지층의 자리로 쓴다.
    돌려주는 것은 (산지 행들, 지층 행들) — 지층 행은 `formation`·`n`(산지 수)·`lon`·`lat`·`early`·`late`."""
    q = (query or "").strip()
    conn = db()
    if conn is None or len(q) < 2:
        return [], []
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    # 같은 이름 → 앞이 같은 것 → 들어 있는 것, 같으면 화석이 많은 것
    sites = conn.execute(
        "SELECT no, name, formation, early, late, lon, lat, n_occs FROM coll WHERE name LIKE ? ESCAPE '\\' "
        "ORDER BY (lower(name) = lower(?)) DESC, (lower(name) LIKE lower(?) || '%') DESC, n_occs DESC LIMIT ?",
        (like, q, q, limit)).fetchall()
    # 묶음 안의 맨 열(lon·lat 따위)은 max(n_occs) 를 낸 줄의 것이다 — sqlite 의 약속
    forms = conn.execute(
        "SELECT formation, count(*) AS n, max(n_occs) AS top, lon, lat, early, late FROM coll "
        "WHERE formation LIKE ? ESCAPE '\\' GROUP BY formation "
        "ORDER BY (lower(formation) = lower(?)) DESC, (lower(formation) LIKE lower(?) || '%') DESC, n DESC LIMIT ?",
        (like, q, q, formations)).fetchall()
    return sites, forms
