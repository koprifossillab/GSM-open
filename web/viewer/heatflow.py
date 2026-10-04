"""지열류 — IHFC 세계 지열류 자료 2024 판의 9 만 곳을 sqlite 로 굽고 경위도 타일에 점을 찍는다 (wetherilli 267).

원본은 GFZ Data Services 의 `GHFBD-R2024_v.2026-03.zip`(doi:10.5880/fidgeo.2024.014, 18 MB) — 안의 `IHFC_2024_GHFDB_v.2026.03.txt`
(탭 구분, 머리에 `#` 줄과 열 부호·필수 여부·단위 줄 여섯이 붙는다). 묶음 머리가 **CC BY 4.0** 이라 적는다. NAS `N:\\GSM\\sources\\earth\\`
에 두고 `manage.py build_heatflow <zip>` 이 `<EARTH_DIR>/heatflow.sqlite` 로 굽는다. 화면이 부를 때는 이 파일만 읽는다 — 문이 아니다.
지진(`quakes.py`)과 같은 꼴이다.

- **오늘의 레이어다.** 잰 값이라 옛 지구로 돌리지 않는다
- 한 줄이 한 측정(child)이다 — 같은 시추공의 다른 구간이 여러 줄일 수 있다. 자리·값이 같은 줄만 하나로 친다
- 색은 지열류(mW/m²) — 차가운 순상지(40 아래, 파랑)부터 해령·열점(200 넘게, 자홍)까지. 높은 값을 나중에 찍어 위에 온다
"""
import functools
import io
import math
import sqlite3
import time
import zipfile
from pathlib import Path

from django.conf import settings

from . import paleo
from .i18n import msg, t

FILE = "heatflow.sqlite"
RENDERER = "1"
MEMBER_SUFFIX = ".txt"
CREDIT = "IHFC Global Heat Flow Database 2024 (GFZ Data Services, CC BY 4.0)"
DOI = "https://doi.org/10.5880/fidgeo.2024.014"
#: (mW/m² 미만, 색, 범례 글)
CLASSES = (
    (40, "#2b5fa8", msg("40 mW/m² 아래")),
    (60, "#3fa7c9", msg("40–60 mW/m²")),
    (80, "#8fcf6b", msg("60–80 mW/m²")),
    (120, "#f2c14e", msg("80–120 mW/m²")),
    (200, "#e4572e", msg("120–200 mW/m²")),
    (1e9, "#b0207a", msg("200 mW/m² 넘게")),
)


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def colour(q) -> tuple:
    v = 0 if q is None else q
    for below, hexa, _ in CLASSES:
        if v < below:
            break
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko") -> list:
    return [{"color": c, "name": t(name, lang)} for _, c, name in CLASSES]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE hf (n INTEGER PRIMARY KEY, id TEXT, lon REAL, lat REAL, q REAL, q_unc REAL, name TEXT, elevation REAL,
                 environment TEXT, method TEXT, year TEXT, quality TEXT, reference TEXT);
CREATE VIRTUAL TABLE hf_xy USING rtree(id, x0, x1, y0, y1);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def read_rows(lines):
    """IHFC 글 파일의 줄들 → 열 이름을 열쇠로 한 사전. `#` 줄과 머리 앞의 부호 줄은 건너뛴다 — 첫 칸이 `q` 인 줄이 머리다."""
    header = None
    for line in lines:
        line = line.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            if cells[0].strip() == "q" and "lat_NS" in cells:
                header = [c.strip() for c in cells]
            continue
        yield dict(zip(header, cells))
    if header is None:
        raise ValueError("머리 줄(q, q_uncertainty, name, lat_NS …)을 찾지 못했다")


def decode(raw: bytes) -> str:
    """2024 판(v.2026.03)의 글 파일은 UTF-8 이 아니라 cp1252 다(`Búrfell`) — UTF-8 로 풀리면 그대로, 아니면 cp1252"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def build(source, out_path=None, log=print) -> dict:
    """GFZ 의 zip(또는 안의 .txt) → sqlite. 몇 초."""
    src = Path(source)
    out_path = Path(out_path) if out_path else path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as zf:
            member = next((n for n in zf.namelist() if n.endswith(MEMBER_SUFFIX) and "GHFDB" in n), None)
            if member is None:
                raise ValueError("zip 에 IHFC 글 파일(.txt)이 없다")
            text = decode(zf.read(member))
    else:
        text = decode(src.read_bytes())
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, seen, skipped, started = [], set(), 0, time.time()
    for rec in read_rows(text.splitlines()):
        q, lat, lon = _num(rec.get("q")), _num(rec.get("lat_NS")), _num(rec.get("long_EW"))
        if q is None or lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 360):
            skipped += 1
            continue
        lon = ((lon + 180.0) % 360.0) - 180.0
        mark = (round(lon, 5), round(lat, 5), q)
        if mark in seen:
            skipped += 1
            continue
        seen.add(mark)
        g = lambda k: (rec.get(k) or "").strip()              # noqa: E731
        rows.append((len(rows) + 1, g("ID"), lon, lat, q, _num(rec.get("q_uncertainty")), g("name").strip("? ") or "",
                     _num(rec.get("elevation")), g("environment").strip("[]"), g("q_method"), g("Year"),
                     g("Quality_Code_Child"), g("publication_reference")[:400]))
    db.executemany(f"INSERT INTO hf VALUES ({', '.join('?' * 13)})", rows)
    db.executemany("INSERT INTO hf_xy VALUES (?, ?, ?, ?, ?)", [(r[0], r[2], r[2], r[3], r[3]) for r in rows])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))), ("source", DOI), ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  {len(rows):,} 곳 (건너뜀 {skipped:,})")
    return {"rows": len(rows), "skipped": skipped, "seconds": round(time.time() - started)}


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _open(mtime):
    db = sqlite3.connect(f"file:{path()}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def db():
    try:
        return _open(path().stat().st_mtime)
    except (FileNotFoundError, sqlite3.OperationalError):
        return None


def available() -> bool:
    return db() is not None


def built() -> str:
    conn = db()
    return conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()[0] if conn else ""


def points(west: float, south: float, east: float, north: float) -> list:
    conn = db()
    if conn is None:
        return []
    return list(conn.execute("SELECT h.* FROM hf_xy x JOIN hf h ON h.n = x.id "
                             "WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?", (west, east, south, north)))


def _radius(z: int) -> float:
    return 1.3 if z <= 1 else 1.7 if z <= 3 else 2.3 if z <= 5 else 3.0


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 지열류 점을 찍는다 — 낮은 값부터, 높은 값이 위에."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    rad = _radius(z) * k
    pad = rad / scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(r["lon"] + shift, r["lat"], r["q"]) for r in points(w, north - span - pad, e, north + pad)]
    found.sort(key=lambda p: p[2])
    for lon, lat, q in found:
        cx, cy = (lon - west) * scale, (north - lat) * scale
        draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=colour(q) + (215,), outline=(25, 25, 25, 150), width=1)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 측정 — 가까운 것부터. 날짜 바뀜선 너머도."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for r in points(lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius):
            d2 = ((r["lon"] - lon - shift) * cos) ** 2 + (r["lat"] - lat) ** 2
            if d2 <= radius * radius:
                out.append((d2, r))
    out.sort(key=lambda h: h[0])
    return [r for _, r in out[:limit]]
