"""세계 빙하 — Randolph Glacier Inventory 7.0 의 빙하 27 만 개를 sqlite 로 굽고 경위도 타일에 넓이만 한 점을 찍는다 (wetherilli 289).

원본은 RGI 7.0(RGI Consortium 2023, NSIDC-0770 doi:10.5067/f6jmovy5navz, **CC BY 4.0**)의 빙하 속성 표 `RGI2000-v7.0-G-global-attributes.csv`
(274 531 줄, 71 MB) — 빙하마다 가운데·넓이·높이·경사·끝의 갈래가 든다. NSIDC 의 내려받기는 NASA Earthdata 로그인이 있어야 해서, 같은 판을 그대로
올려 둔 OGGM(브레멘대) 거울에서 받았다. NAS `N:\\GSM\\sources\\earth\\rgi7\\` 에 두고 `manage.py build_glaciers <csv>` 가 `<EARTH_DIR>/glaciers.sqlite`
로 굽는다. 화면이 부를 때는 이 파일만 읽는다 — 문이 아니다. 지열류(`heatflow.py`)와 같은 꼴이다.

- **윤곽이 아니라 점이다** — 윤곽(셰이프)은 Earthdata 로그인 뒤에만 받힌다(TODOs). 점의 크기를 빙하의 넓이만 한 원으로 해서, 가까이 보면
  큰 빙하는 제 크기로, 작은 빙하는 한 점으로 선다
- **줌 3 부터 그린다** — 그 밑은 Natural Earth 의 빙하·빙붕(`ice`)이 맡는다. 27 만 점이 온 지구 한 장에 몰리면 산맥이 파랗게 칠해질 뿐이다
- 색은 바다로 끝나는(조수) 빙하만 진하게 — RGI 7.0 이 끝의 갈래로 가린 것은 그것 하나다(나머지는 "가리지 않음")
- **오늘의 레이어다** — RGI 는 2000 년 무렵의 한 장(snapshot)이다
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

FILE = "glaciers.sqlite"
RENDERER = "1"
MIN_ZOOM = 3
CREDIT = "Randolph Glacier Inventory 7.0 (RGI Consortium 2023, CC BY 4.0)"
DOI = "https://doi.org/10.5067/f6jmovy5navz"
#: 끝의 갈래(`term_type`) → (색, 범례 글). RGI 7.0 은 바다로 끝나는 빙하(1)만 가려 두었고 나머지는 모두 9(가리지 않음)다(2026-10-05,
#: 1 561 / 272 970) — 땅·호수·빙붕(0·2·3)은 RGI 6.0 에만 있다. 쓰지 않는 갈래는 범례에 두지 않는다
TERMINUS = {
    1: ("#08306b", msg("바다에서 끝난다 (조수 빙하)")),
    9: ("#6baed6", msg("빙하 (끝의 갈래를 가리지 않았다)")),
}
SURGE = {1: msg("서지 가능"), 2: msg("서지 그럴듯"), 3: msg("서지 관측")}


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def colour(term) -> tuple:
    hexa = TERMINUS.get(term, TERMINUS[9])[0]
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko") -> list:
    return [{"color": c, "name": t(name, lang)} for c, name in TERMINUS.values()]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE g (n INTEGER PRIMARY KEY, id TEXT, lon REAL, lat REAL, area REAL, name TEXT, region TEXT, term INTEGER, surge INTEGER,
                zmin REAL, zmax REAL, zmed REAL, slope REAL, aspect REAL, date TEXT);
CREATE VIRTUAL TABLE g_xy USING rtree(id, x0, x1, y0, y1);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _int(v, default=None):
    f = _num(v)
    return default if f is None else int(f)


def build(csv_path, out_path=None, log=print) -> dict:
    """RGI 7.0 의 빙하 속성 CSV → sqlite. 몇 초."""
    out_path = Path(out_path) if out_path else path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, skipped, started = [], 0, time.time()
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            lon, lat, area = _num(rec.get("cenlon")), _num(rec.get("cenlat")), _num(rec.get("area_km2"))
            if lon is None or lat is None or area is None:
                skipped += 1
                continue
            rows.append((len(rows) + 1, (rec.get("rgi_id") or "").strip(), ((lon + 180.0) % 360.0) - 180.0, lat, area,
                         (rec.get("glac_name") or "").strip(), (rec.get("o2region") or "").strip(), _int(rec.get("term_type"), 9),
                         _int(rec.get("surge_type"), 0), _num(rec.get("zmin_m")), _num(rec.get("zmax_m")), _num(rec.get("zmed_m")),
                         _num(rec.get("slope_deg")), _num(rec.get("aspect_deg")), (rec.get("src_date") or "")[:10]))
    db.executemany(f"INSERT INTO g VALUES ({', '.join('?' * 15)})", rows)
    db.executemany("INSERT INTO g_xy VALUES (?, ?, ?, ?, ?)", [(r[0], r[2], r[2], r[3], r[3]) for r in rows])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))), ("source", DOI), ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  {len(rows):,} 개 (건너뜀 {skipped:,})")
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
    return list(conn.execute("SELECT g.* FROM g_xy x JOIN g ON g.n = x.id "
                             "WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?", (west, east, south, north)))


def radius_deg(area_km2: float, lat: float) -> tuple:
    """넓이만 한 원의 반지름(위도 °, 경도 °)"""
    r_km = math.sqrt(max(area_km2, 0.0) / math.pi)
    return r_km / 111.32, r_km / (111.32 * max(0.05, math.cos(math.radians(lat))))


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장 — 빙하마다 넓이만 한 타원(경위도 격자의 늘림을 따른다), 작으면 한 점. 큰 것부터, 작은 것이 위에."""
    from PIL import Image, ImageDraw
    k = 2
    size = paleo.TILE * k
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if z >= MIN_ZOOM:
        span = 180.0 / 2 ** z
        west, north = -180.0 + x * span, 90.0 - y * span
        scale = size / span
        dot = (1.0 if z <= 4 else 1.4 if z <= 6 else 2.0) * k
        pad = 0.5                                        # 가장 큰 빙하(세베르니 섬의 만 km²)도 반지름 1° 안이다
        draw = ImageDraw.Draw(image)
        found = []
        for shift in (-360.0, 0.0, 360.0):
            w, e = west - shift - pad, west + span - shift + pad
            if e < -180 or w > 180:
                continue
            found += [(r["lon"] + shift, r["lat"], r["area"], r["term"])
                      for r in points(w, max(-90.0, north - span - pad), e, min(90.0, north + pad))]
        found.sort(key=lambda p: -p[2])
        for lon, lat, area, term in found:
            cx, cy = (lon - west) * scale, (north - lat) * scale
            ry, rx = radius_deg(area, lat)
            rx, ry = max(dot, rx * scale), max(dot, ry * scale)
            if cx + rx < 0 or cx - rx > size or cy + ry < 0 or cy - ry > size:
                continue
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=colour(term) + (215,),
                         outline=(255, 255, 255, 120) if rx > 3 * k else None)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(lon: float, lat: float, radius: float, limit: int = 3) -> list:
    """누른 자리가 든 빙하(넓이의 원 안) 또는 `radius`° 안의 빙하 — 가까운 것부터."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for r in points(lon + shift - radius / cos - 0.5, lat - radius - 0.5, lon + shift + radius / cos + 0.5, lat + radius + 0.5):
            d = math.hypot((r["lon"] - lon - shift) * cos, r["lat"] - lat)
            reach = radius_deg(r["area"], r["lat"])[0]
            if d <= max(radius, reach):
                # 넓이의 원이 누른 자리를 품는 빙하가 먼저(큰 것부터) — 큰 빙하 위를 누르면 둘레의 작은 빙하보다 그것이 뜬다
                out.append(((0, -r["area"]) if d <= reach else (1, d), r))
    out.sort(key=lambda h: h[0])
    return [r for _, r in out[:limit]]
