"""지각 응력 — World Stress Map 2025 의 10 만 측정을 sqlite 로 굽고, 최대 수평 응력(S_Hmax) 방향 막대를 응력 체제의 색으로 긋는다 (wetherilli 273).

원본은 GFZ Data Services `WSM_Database_2025.csv`(Heidbach 외, doi:10.5880/WSM.2025.001, 14 MB) — **CC BY 4.0**(누리집의 SPDX 칸).
NAS `N:\\GSM\\sources\\earth\\` 에 두고 `manage.py build_stress <csv>` 가 `<EARTH_DIR>/stress.sqlite` 로 굽는다. 화면이 부를 때는 이 파일만
읽는다 — 문이 아니다. 지열류(`heatflow.py`)·지진과 같은 꼴이다.

- **품질 A–D 만 싣는다.** E 는 "믿을 만한 방향이 없다" 는 등급이라 막대를 그을 수 없다 — WSM 지도도 E 를 그리지 않는다. 방향(`AZI`)이 999 인
  것도 뺀다
- 막대는 누른 자리를 가운데로 S_Hmax 방향(북에서 시계 방향, 축이라 180° 대칭)으로 긋고, 길이는 품질(A 가장 길게 … D 가장 짧게)이다 —
  WSM 지도의 관례다. 5만 지질도의 방향 기호(wetherilli 223)와 같은 생각이다
- 색은 응력 체제(`REGIME`) — 정단층(NF) 빨강·정단층+주향이동(NS) 주황·주향이동(SS) 초록·역단층+주향이동(TS) 하늘·역단층(TF) 파랑·모름(U) 검정.
  WSM 의 색이다
- **오늘의 레이어다**
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

FILE = "stress.sqlite"
RENDERER = "1"
CREDIT = "World Stress Map 2025 (Heidbach et al., GFZ Data Services, CC BY 4.0)"
DOI = "https://doi.org/10.5880/WSM.2025.001"
#: 체제 → (색, 범례 글)
REGIMES = {
    "NF": ("#e31a1c", msg("정단층형")),
    "NS": ("#ff8c1a", msg("정단층·주향이동형")),
    "SS": ("#1a9e4b", msg("주향이동형")),
    "TS": ("#3fa7e0", msg("역단층·주향이동형")),
    "TF": ("#1f3fbf", msg("역단층형")),
    "U": ("#222222", msg("체제 모름")),
}
#: 품질 → 막대 반길이 비(가장 긴 것이 1)
QUALITY_LENGTH = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4}
#: 측정법 부호(`TYPE`) → 이름. WSM 의 갈래
TYPES = {
    "FMS": msg("단일 지진 초점 메커니즘"), "FMA": msg("평균 초점 메커니즘"), "FMF": msg("초점 메커니즘 역산"),
    "BO": msg("시추공 붕락"), "BOC": msg("시추공 붕락 (캘리퍼)"), "BOT": msg("시추공 붕락 (영상)"), "BS": msg("시추공 미끄럼"),
    "DIF": msg("시추 유도 인장 균열"), "HF": msg("수압 파쇄"), "HFG": msg("수압 파쇄 (지구물리)"), "HFM": msg("수압 파쇄 (탄성 역산)"),
    "HFP": msg("수압 파쇄 (기존 균열)"), "OC": msg("코어 덧씌워 떼기"), "GFI": msg("지질 — 단층 미끄럼 역산"), "GFM": msg("지질 — 단층 미끄럼"),
    "GFS": msg("지질 — 단층 미끄럼 (단일)"), "GVA": msg("지질 — 화산 배열"), "SWB": msg("횡파 분리"),
}


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


def colour(regime: str) -> tuple:
    hexa = REGIMES.get(regime, REGIMES["U"])[0]
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko") -> list:
    return [{"color": c, "name": t(name, lang)} for c, name in REGIMES.values()]


# ── 굽기 ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE sh (n INTEGER PRIMARY KEY, id TEXT, lon REAL, lat REAL, azi REAL, type TEXT, depth REAL, quality TEXT, regime TEXT,
                 locality TEXT, country TEXT, date TEXT, mag TEXT, ref TEXT);
CREATE VIRTUAL TABLE sh_xy USING rtree(id, x0, x1, y0, y1);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _num(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def build(csv_path, out_path=None, log=print) -> dict:
    """WSM CSV → sqlite. 몇 초."""
    out_path = Path(out_path) if out_path else path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows, skipped, started = [], {"품질 E": 0, "방향 없음": 0, "자리 없음": 0}, time.time()
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for rec in csv.DictReader(fh):
            lat, lon, azi = _num(rec.get("LAT")), _num(rec.get("LON")), _num(rec.get("AZI"))
            quality = (rec.get("QUALITY") or "").strip().upper()
            if lat is None or lon is None:
                skipped["자리 없음"] += 1
                continue
            if quality not in QUALITY_LENGTH:
                skipped["품질 E"] += 1
                continue
            if azi is None or not 0 <= azi <= 360:
                skipped["방향 없음"] += 1
                continue
            g = lambda k: (rec.get(k) or "").strip()          # noqa: E731
            rows.append((len(rows) + 1, g("ID"), ((lon + 180.0) % 360.0) - 180.0, lat, azi % 180.0, g("TYPE"), _num(rec.get("DEPTH")),
                         quality, g("REGIME") or "U", g("LOCALITY"), g("COUNTRY"), g("DATE"),
                         " ".join(x for x in (g("EQ_MAG"), g("MAG_TYPE")) if x), g("REF1")))
    db.executemany(f"INSERT INTO sh VALUES ({', '.join('?' * 14)})", rows)
    db.executemany("INSERT INTO sh_xy VALUES (?, ?, ?, ?, ?)", [(r[0], r[2], r[2], r[3], r[3]) for r in rows])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))), ("source", DOI), ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    log(f"  {len(rows):,} 곳 (뺀 것 {skipped})")
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
    return list(conn.execute("SELECT s.* FROM sh_xy x JOIN sh s ON s.n = x.id "
                             "WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?", (west, east, south, north)))


def _half(z: int) -> float:
    """품질 A 막대의 반길이(화소)"""
    return 4.0 if z <= 1 else 5.5 if z <= 3 else 7.5 if z <= 5 else 10.0


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장에 S_Hmax 막대를 긋는다. 경위도 격자는 동서로 늘어나 있어 방향을 그 늘림만큼 고쳐 긋는다 —
    화면(구·평면)이 이 타일을 다시 펴면 북에서 잰 방향이 된다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    reach = _half(z) * k
    pad = reach / scale * 3
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(r["lon"] + shift, r["lat"], r["azi"], r["quality"], r["regime"])
                  for r in points(w, max(-90.0, north - span - pad), e, min(90.0, north + pad))]
    found.sort(key=lambda p: "DCBA".index(p[3]))            # 좋은 품질이 위에
    for lon, lat, azi, quality, regime in found:
        cx, cy = (lon - west) * scale, (north - lat) * scale
        stretch = 1.0 / max(0.05, math.cos(math.radians(lat)))   # 경위도 격자의 동서 늘림
        a = math.radians(azi)
        dx, dy = math.sin(a) * stretch, -math.cos(a)
        norm = math.hypot(dx, dy)
        half = reach * QUALITY_LENGTH[quality]
        ux, uy = dx / norm * half, dy / norm * half
        draw.line((cx - ux, cy - uy, cx + ux, cy + uy), fill=colour(regime) + (235,), width=max(2, round(1.3 * k)))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 측정 — 가까운 것부터."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for r in points(lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius):
            d2 = ((r["lon"] - lon - shift) * cos) ** 2 + (r["lat"] - lat) ** 2
            if d2 <= radius * radius:
                out.append((d2, "ABCD".index(r["quality"]), r))
    out.sort(key=lambda h: (h[0], h[1]))
    return [r for _, _, r in out[:limit]]
