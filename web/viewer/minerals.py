"""세계 광상 — USGS 의 광물 자원 자료 여섯을 sqlite 한 장으로 굽고 광종 칸마다 경위도 타일에 점을 찍는다 (wetherilli 276).

원본은 USGS Mineral Resources Data(mrdata.usgs.gov)의 CSV 묶음이다 — **공공 도메인**.

- `mrds-csv.zip` — MRDS(Mineral Resources Data System) 30 만 곳. 미국이 9 할이지만 온 세계를 싣는다
- Global Mineral Resource Assessment 의 세계 광상 표 — 광량·품위가 붙은 "이름난" 광상이다
  `porcu-csv.zip`(반암동, Singer 외 2008, OFR 2008-1155)·`sedcu-csv.zip`(퇴적암 호스트 구리, Cox 외 2003, OFR 03-107)·
  `vms-csv.zip`(화산성 괴상 황화물, Mosier 외 2009, OFR 2009-1034)·`podchrome-csv.zip`(포디폼 크로마이트, SIR 2012-5157)·
  `ree-csv.zip`(희토류, Orris & Grauch 2002, OFR 02-189)·`sedznpb-csv.zip`(퇴적암 호스트 납·아연 — MVT·SEDEX, Taylor 외 2009)

NAS `N:\\GSM\\sources\\earth\\usgs_minerals\\` 에 두고 `manage.py build_minerals <폴더>` 가 `<EARTH_DIR>/minerals.sqlite` 로 굽는다.
화면이 부를 때는 이 파일만 읽는다 — 문이 아니다. 지진(`quakes.py`)처럼 칸마다 레이어가 따로다.

- **오늘의 레이어다.** 옛 지구로 돌리지 않는다
- 광종 칸은 **첫 광종**이 정한다(MRDS 의 `commod1` 은 주 광종을 중요한 차례로 적는다). 세계 광상 표는 표마다 칸이 정해져 있다
  (VMS 만은 구리와 납·아연 가운데 품위가 큰 쪽)
- 모래·자갈·석재·점토·지열처럼 광상이라 하기 어려운 것은 싣지 않는다(`SKIP`) — MRDS 의 3 할 남짓이다
- 점의 크기는 무게 — 세계 광상 표와 MRDS 의 대규모(`prod_size=L`)는 마름모, 생산한 적이 있는 곳은 중간 원, 산지·탐사지는 작은 원.
  넓게 볼 때(줌 3 까지)는 작은 원을 찍지 않는다 — 미국이 칠로 덮인다
"""
import csv
import functools
import io
import json
import math
import sqlite3
import time
import zipfile
from pathlib import Path

from django.conf import settings

from . import paleo
from .i18n import msg, t

FILE = "minerals.sqlite"
RENDERER = "1"
CREDIT = "U.S. Geological Survey Mineral Resources Data (MRDS · Global Mineral Resource Assessment), public domain"
LINK = "https://mrdata.usgs.gov/"
#: 칸 — (레이어 이름, 색, 이름)
BANDS = {
    "min_cu": ("#d0652b", msg("구리")),
    "min_au": ("#e5b40f", msg("금·은·백금족")),
    "min_pbzn": ("#5b78b5", msg("납·아연")),
    "min_fe": ("#8a4f3a", msg("철·합금 금속")),
    "min_crit": ("#2f9e6b", msg("핵심·에너지 광물")),
    "min_ind": ("#9b62b8", msg("산업 광물")),
}
#: 첫 광종 → 칸. 소문자로 앞머리를 맞춘다. 여기 없고 `SKIP` 에도 없으면 산업 광물이다
COMMODITY = {
    "min_cu": ("copper",),
    "min_au": ("gold", "silver", "platinum", "palladium", "pge", "rhodium", "iridium", "osmium", "ruthenium"),
    "min_pbzn": ("lead", "zinc", "cadmium"),
    "min_fe": ("iron", "manganese", "chromium", "nickel", "cobalt", "molybdenum", "tungsten", "vanadium", "titanium"),
    "min_crit": ("uranium", "thorium", "ree", "rare earth", "lithium", "niobium", "tantalum", "tin", "beryllium", "antimony",
                 "bismuth", "mercury", "aluminum", "gallium", "germanium", "indium", "tellurium", "selenium", "zirconium",
                 "cesium", "rubidium", "scandium", "yttrium", "hafnium", "arsenic", "graphite", "magnesium", "helium"),
}
#: 싣지 않는 첫 광종 — 골재·석재·흔한 점토·지열·물
SKIP = ("sand and gravel", "construction", "stone", "crushed/broken", "dimension", "general", "geothermal", "clay",
        "common clay", "limestone", "gravel", "sand", "water", "pumice", "cinder", "scoria", "volcanic materials", "aggregate",
        "marble", "granite", "slate", "sandstone", "basalt", "quartzite", "shale", "")
#: MRDS 의 생산 규모 부호
SIZES = {"L": msg("대규모"), "M": msg("중규모"), "S": msg("소규모")}
#: 세계 광상 표 — (파일 앞머리, 표 이름, 칸)
TABLES = {
    "porcu": (msg("USGS 세계 반암동 광상"), "min_cu"),
    "sedcu": (msg("USGS 세계 퇴적암 호스트 구리 광상"), "min_cu"),
    "vms": (msg("USGS 세계 화산성 괴상 황화물(VMS) 광상"), None),
    "podchrome": (msg("USGS 세계 포디폼 크로마이트 광상"), "min_fe"),
    "ree": (msg("USGS 세계 희토류 광상"), "min_crit"),
    "sedznpb": (msg("USGS 세계 퇴적암 호스트 납·아연 광상"), "min_pbzn"),
}
#: 값을 화면의 말로 옮겨야 하는 줄 — 굽는 때는 한국어 원문을 적고, 내줄 때 `i18n.t` 로 옮긴다
TRANSLATED = ("자료", "생산 규모")
#: 표마다 상세 쪽이 있는 것 — `rec_id` 로 연다 (vms 는 400 이라 뺐다, 2026-10-05)
SHOW = {"porcu", "sedcu", "podchrome", "ree", "sedznpb"}
SMALL_UNTIL = 3


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def band_of(commodity: str):
    """첫 광종 → 칸 이름. 싣지 않을 것이면 None"""
    first = (commodity or "").split(",")[0].strip().lower()
    if first in SKIP:
        return None
    for band, names in COMMODITY.items():
        if any(first.startswith(n) for n in names):
            return band
    return "min_ind"


def legend(lang: str = "ko") -> list:
    """`[{band, color, name}]` — 칸마다 하나. 화면이 레이어와 범례를 함께 짓는다"""
    return [{"band": b, "color": c, "name": t(name, lang)} for b, (c, name) in BANDS.items()]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE dep (n INTEGER PRIMARY KEY, src TEXT, rid TEXT, band TEXT, weight INTEGER, lon REAL, lat REAL, name TEXT,
                  country TEXT, commodity TEXT, status TEXT, kind TEXT, rows TEXT, url TEXT);
CREATE VIRTUAL TABLE dep_xy USING rtree(id, x0, x1, y0, y1);
CREATE INDEX dep_band ON dep(band);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _text(raw: bytes) -> str:
    """USGS 의 CSV 는 대개 UTF-8 이지만 옛 표에 cp1252 가 섞여 있다(`6\\x965` — 반암동의 연대 범위)"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _g(value) -> str:
    """`5.5` → `5.5`, `0` 은 값이 없는 것 — 세계 광상 표는 모르는 품위를 0 으로 적는다"""
    f = _num(value)
    return "" if f is None or f == 0 else f"{f:g}"


def _clean(v) -> str:
    """cp1252 의 줄표(`\x96`)가 UTF-8 글 안에 섞여 있다. 겹친 빈칸(`Agua  Rica`)도 하나로"""
    return " ".join(str(v or "").replace("\x96", "–").split())


def _rows(pairs) -> str:
    return json.dumps([[k, _clean(v)] for k, v in pairs if v and _clean(v)], ensure_ascii=False)


def _mrds(rec: dict):
    band = band_of(rec.get("commod1"))
    if band is None:
        return None
    size, status = rec.get("prod_size") or "", rec.get("dev_stat") or ""
    weight = 2 if size == "L" else 1 if status in ("Producer", "Past Producer") else 0
    first = (rec.get("commod1") or "").split(",")
    rows = _rows((("광종", rec.get("commod1")), ("딸린 광종", rec.get("commod2")), ("개발 단계", status),
                  ("생산 규모", size in SIZES and SIZES[size].template), ("광상 유형", rec.get("dep_type") or rec.get("model")),
                  ("광석 광물", rec.get("ore")), ("모암", rec.get("hrock_type")), ("곳", ", ".join(
                      x for x in (rec.get("county"), rec.get("state")) if x))))
    return ("mrds", rec.get("dep_id"), band, weight, rec.get("site_name"), rec.get("country"), first[0].strip(), status,
            "MRDS", rows, rec.get("url") or "")


def _table(src: str, rec: dict):
    title, band = TABLES[src]
    grades = []
    for col, label in (("cugrd", "Cu %"), ("zngrd", "Zn %"), ("pbgrd", "Pb %"), ("mogrd", "Mo %"), ("cogrd", "Co %"),
                       ("crgrd", "Cr₂O₃ %"), ("augrd", "Au g/t"), ("aggrd", "Ag g/t")):
        if _g(rec.get(col)):
            grades.append(f"{label} {_g(rec.get(col))}")
    if src == "vms":
        cu, znpb = _num(rec.get("cugrd")) or 0, (_num(rec.get("zngrd")) or 0) + (_num(rec.get("pbgrd")) or 0)
        band = "min_pbzn" if znpb > cu else "min_cu"
    commodity = {"porcu": "Copper", "sedcu": "Copper", "podchrome": "Chromium", "ree": "REE", "sedznpb": "Zinc"}.get(
        src, "Zinc" if band == "min_pbzn" else "Copper")
    kind = rec.get("prevtype") or rec.get("deptype") or ""       # 납·아연은 `prevtype`(MVT·SEDEX)이 읽히는 이름이다
    kind = "" if kind.isdigit() else kind            # 반암동의 `deptype` 은 번호뿐이다
    rows = _rows((("자료", title.template), ("광상 유형", kind), ("개발 단계", rec.get("status")),
                  ("총 광량 (Mt)", _g(rec.get("oreton"))), ("품위", ", ".join(grades)),
                  ("연대 (Ma)", _g(rec.get("agemy"))), ("지질시대", rec.get("depage") or rec.get("age_info")),
                  ("모암", rec.get("hostrock") or rec.get("rockdep")), ("곳", rec.get("stprov"))))
    url = f"https://mrdata.usgs.gov/{src}/show-{src}.php?rec_id={rec.get('rec_id')}" if src in SHOW else ""
    return (src, rec.get("rec_id"), band, 2, rec.get("depname"), rec.get("country"), commodity, rec.get("status") or "",
            src, rows, url)


def build(folder, out_path=None, log=print) -> dict:
    """`<폴더>/mrds-csv.zip`·`porcu-csv.zip` … → sqlite. 없는 묶음은 건너뛴다. 1 분 남짓."""
    folder = Path(folder)
    out_path = Path(out_path) if out_path else path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, counts, skipped, started = [], {}, 0, time.time()

    def add(item, lon, lat):
        nonlocal skipped
        lon, lat = _num(lon), _num(lat)
        if item is None or lon is None or lat is None or not (-90 <= lat <= 90 and -180 <= lon <= 360) or (lon == 0 and lat == 0):
            skipped += 1
            return
        lon = ((lon + 180.0) % 360.0) - 180.0
        src, rid, band, weight, name, country, commodity, status, kind, extra, url = item
        rows.append((len(rows) + 1, src, str(rid or ""), band, weight, lon, lat, _clean(name), _clean(country),
                     commodity, status, str(kind), extra, url))
        counts[src] = counts.get(src, 0) + 1

    mrds = folder / "mrds-csv.zip"
    if mrds.exists():
        with zipfile.ZipFile(mrds) as zf, zf.open("mrds.csv") as f:
            for rec in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace")):
                add(_mrds(rec), rec.get("longitude"), rec.get("latitude"))
    for src in TABLES:
        z = folder / f"{src}-csv.zip"
        if not z.exists():
            continue
        with zipfile.ZipFile(z) as zf:
            member = next(n for n in zf.namelist() if n.endswith("/main.csv"))
            for rec in csv.DictReader(io.StringIO(_text(zf.read(member)))):
                add(_table(src, rec), rec.get("longitude"), rec.get("latitude"))
    if not rows:
        db.close()
        tmp.unlink(missing_ok=True)
        raise ValueError(f"{folder} 에 USGS 광물 자료 묶음(mrds-csv.zip·porcu-csv.zip …)이 없다")
    db.executemany(f"INSERT INTO dep VALUES ({', '.join('?' * 14)})", rows)
    db.executemany("INSERT INTO dep_xy VALUES (?, ?, ?, ?, ?)", [(r[0], r[5], r[5], r[6], r[6]) for r in rows])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))), ("source", LINK), ("license", "public domain"),
        ("counts", json.dumps(counts))])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  {len(rows):,} 곳 {counts} (건너뜀 {skipped:,})")
    return {"rows": len(rows), "counts": counts, "skipped": skipped, "seconds": round(time.time() - started)}


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


def points(bands, west: float, south: float, east: float, north: float, least: int = 0) -> list:
    conn = db()
    bands = [b for b in bands if b in BANDS]
    if conn is None or not bands:
        return []
    marks = ", ".join("?" * len(bands))
    return list(conn.execute(f"SELECT d.* FROM dep_xy x JOIN dep d ON d.n = x.id WHERE x.x0 >= ? AND x.x1 <= ? "
                             f"AND x.y0 >= ? AND x.y1 <= ? AND d.band IN ({marks}) AND d.weight >= ?",
                             (west, east, south, north, *bands, least)))


def _radius(z: int, weight: int) -> float:
    base = 1.2 if z <= 1 else 1.6 if z <= 3 else 2.2 if z <= 5 else 2.9
    return base * (1.9 if weight == 2 else 1.3 if weight == 1 else 1.0)


def render_tile(band: str, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 한 칸의 광상을 찍는다 — 가벼운 것부터, 마름모가 위에."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    pad = _radius(z, 2) * k / scale
    least = 1 if z <= SMALL_UNTIL else 0
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colour = tuple(int(BANDS[band][0][i:i + 2], 16) for i in (1, 3, 5))
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(r["lon"] + shift, r["lat"], r["weight"]) for r in points([band], w, north - span - pad, e, north + pad, least)]
    found.sort(key=lambda p: p[2])
    for lon, lat, weight in found:
        cx, cy = (lon - west) * scale, (north - lat) * scale
        rad = _radius(z, weight) * k
        if weight == 2:
            draw.polygon(((cx, cy - rad), (cx + rad, cy), (cx, cy + rad), (cx - rad, cy)), fill=colour + (235,),
                         outline=(20, 20, 20, 210))
        else:
            draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=colour + (200 if weight else 150,),
                         outline=(25, 25, 25, 140 if weight else 90), width=1)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(bands, lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """켠 칸에서 누른 자리 `radius`° 안의 광상 — 무거운 것, 가까운 것부터. 날짜 바뀜선 너머도."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for r in points(bands, lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius):
            d2 = ((r["lon"] - lon - shift) * cos) ** 2 + (r["lat"] - lat) ** 2
            if d2 <= radius * radius:
                out.append((-r["weight"], d2, r))
    out.sort(key=lambda h: h[:2])
    return [r for *_, r in out[:limit]]
