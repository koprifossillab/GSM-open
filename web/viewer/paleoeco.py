"""제4기 고생태 산지 — Neotoma 의 자료를 sqlite 로 굽고, 자료형 칸·연대마다 그 산지에 점을 찍는다 (wetherilli 139).

`manage.py fetch_neotoma` 가 문(`neotoma.py`)으로 받은 JSON Lines 를 여기서 `<EARTH_DIR>/neotoma.sqlite` 로 굽는다. 화면이
부를 때는 이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다.

- **자료형 칸 다섯**(`BANDS`)이 따로 레이어다 — 꽃가루·척추동물·식물 큰화석·규조와 작은 생물·그 밖(숯·지화학·연대 측정 …)
- **오늘(0)** 은 모든 산지. **1 Ma 안쪽**은 그 연대를 품은 자료가 있는 산지만(화석 산지와 같다, 098). 1 Ma 부터는 화면이 끈다 —
  제4기 산지라 판을 돌릴 만큼 옛 것이 거의 없다
- 연대는 1950 년 앞 햇수(BP)로 담는다. 방사성탄소 연대는 보정하지 않고 그대로 견준다 — 2 만 년 안팎에서 수천 년 어긋날 수 있다.
  연대 범위가 없는 자료(표층 시료·수질 따위)는 오늘에만 뜬다
"""
import functools
import io
import json
import math
import sqlite3
import time
from pathlib import Path

from django.conf import settings

from . import paleo
from .i18n import msg, t

FILE = "neotoma.sqlite"
RENDERER = "1"

#: 자료형 칸 — 레이어 이름 → (색, 범례 글)
BANDS = {
    "neo_pollen": ("#e6b422", msg("꽃가루")),
    "neo_vert": ("#c0504d", msg("척추동물")),
    "neo_plant": ("#4f9a4a", msg("식물 큰화석")),
    "neo_micro": ("#3f8fc4", msg("규조·작은 생물")),
    "neo_other": ("#9b7bb8", msg("그 밖 (숯·지화학·연대 측정 …)")),
}
_MICRO = ("diatom", "ostracode", "testate amoebae", "chironomid", "cladocera", "dinoflagellates", "insect",
          "macroinvertebrate", "gastropod")


def band_of(kind: str) -> str:
    """Neotoma 의 자료형(`datasettype`) → `BANDS` 의 칸."""
    k = (kind or "").lower()
    if k.startswith("pollen"):
        return "neo_pollen"
    if k == "vertebrate fauna":
        return "neo_vert"
    if k == "plant macrofossil":
        return "neo_plant"
    if k.startswith(_MICRO):
        return "neo_micro"
    return "neo_other"


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def legend(lang: str = "ko") -> list:
    return [{"band": b, "color": c, "name": t(name, lang)} for b, (c, name) in BANDS.items()]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE site (site INTEGER PRIMARY KEY, name TEXT, desc TEXT, alt REAL, lon REAL, lat REAL);
CREATE VIRTUAL TABLE site_xy USING rtree(id, x0, x1, y0, y1);
CREATE TABLE ds (dataset INTEGER PRIMARY KEY, site INTEGER, band TEXT, type TEXT, db TEXT, old REAL, young REAL,
                 pi TEXT, doi TEXT);
CREATE INDEX ds_site ON ds(site, band);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def build(jsonl_path, out_path, log=print) -> dict:
    """`neotoma.download` 의 JSON Lines → sqlite. 같은 자료가 두 번 오면 하나만."""
    out_path = Path(out_path)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    sites, datasets, started = {}, {}, time.time()
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("dataset") is None:
                continue
            sites.setdefault(r["site"], (r["site"], r["name"], r["desc"], r["alt"], r["lon"], r["lat"]))
            datasets[r["dataset"]] = (r["dataset"], r["site"], band_of(r["type"]), r["type"], r["db"], r["old"],
                                      r["young"], r["pi"], r["doi"])
    db.executemany("INSERT INTO site VALUES (?, ?, ?, ?, ?, ?)", sites.values())
    db.executemany("INSERT INTO site_xy VALUES (?, ?, ?, ?, ?)", [(s[0], s[4], s[4], s[5], s[5]) for s in sites.values()])
    db.executemany("INSERT INTO ds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", datasets.values())
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("sites", str(len(sites))), ("datasets", str(len(datasets))),
        ("source", "api.neotomadb.org v2.0 data/datasets"), ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  산지 {len(sites):,} 곳 · 자료 {len(datasets):,} 건")
    return {"sites": len(sites), "datasets": len(datasets), "seconds": round(time.time() - started)}


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


def _age_sql(age: float) -> tuple:
    """연대(Ma) → 자료를 거르는 조건. 0 이면 모두."""
    if age <= 0:
        return "", []
    bp = age * 1e6
    return " AND d.young <= ? AND d.old >= ?", [bp, bp]


def points(bands, age: float, west: float, south: float, east: float, north: float) -> list:
    """그 네모 안에서, 고른 칸의 자료가 그 연대를 품은 산지 — `(경도, 위도, 산지, 칸)`. 한 산지가 칸마다 한 번."""
    conn = db()
    if conn is None or not bands:
        return []
    cond, args = _age_sql(age)
    marks = ",".join("?" * len(bands))
    sql = ("SELECT DISTINCT s.lon, s.lat, s.site, d.band FROM site_xy x JOIN site s ON s.site = x.id "
           "JOIN ds d ON d.site = s.site WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ? "
           f"AND d.band IN ({marks})" + cond)
    return [tuple(r) for r in conn.execute(sql, [west, east, south, north, *bands, *args])]


def render_tile(band: str, age: float, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 그 칸의 산지를 찍는다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    radius = (1.5 if z <= 1 else 2.0 if z <= 3 else 2.8 if z <= 5 else 3.6) * k
    pad = radius / scale
    hexa = BANDS[band][0]
    fill = tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5)) + (230,)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        for lon, lat, _, _ in points([band], age, w, north - span - pad, e, north + pad):
            cx, cy = (lon + shift - west) * scale, (north - lat) * scale
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill,
                         outline=(25, 25, 25, 210), width=max(1, k // 2))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(bands, age: float, lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 산지 — 가까운 것부터. `(산지 행, [그 연대·칸의 자료 행])`."""
    conn = db()
    if conn is None:
        return []
    cos = max(0.05, math.cos(math.radians(lat)))
    hits = {}
    for shift in (-360.0, 0.0, 360.0):
        for plon, plat, site, _ in points(bands, age, lon + shift - radius / cos, lat - radius,
                                          lon + shift + radius / cos, lat + radius):
            d2 = ((plon - lon - shift) * cos) ** 2 + (plat - lat) ** 2
            if d2 <= radius * radius:
                hits[site] = min(d2, hits.get(site, d2))
    cond, args = _age_sql(age)
    marks = ",".join("?" * len(bands))
    out = []
    for site in sorted(hits, key=hits.get)[:limit]:
        row = conn.execute("SELECT * FROM site WHERE site = ?", (site,)).fetchone()
        ds = conn.execute(f"SELECT * FROM ds d WHERE d.site = ? AND d.band IN ({marks})" + cond + " ORDER BY d.dataset",
                          [site, *bands, *args]).fetchall()
        out.append((row, ds))
    return out


def span_text(old, young) -> str:
    """연대 범위 → `12 400 – 150 BP`. 없으면 빈 글."""
    if old is None:
        return ""
    def fmt(v):
        return f"{round(v):,}".replace(",", " ")
    return fmt(old) + (f" – {fmt(young)}" if young is not None and round(young) != round(old) else "") + " BP"
