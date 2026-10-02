"""화성 크레이터 목록(Robbins & Hynek 2012) — 우리 디스크의 파일을 읽어 타일을 굽는다 (devlog 067). 문이 아니다.

지름 1 km 넘는 크레이터 384 345 개다. THEMIS 낮 적외선(빈 곳은 Viking)에서 테두리를 짚어 원을 맞추고,
MOLA 로 깊이를 재고, 안쪽·분출물 형태와 보존 상태를 매겼다. 원본은 USGS 가 옛 PIGWAD 자리에 그대로 둔
`RobbinsCraterDatabase_20121016.tab.zip`(`asc-pds-services` 의 `pigpen/mars/crater_consortium/`)이다.
NASA Mars Trek 은 이것을 주지 않는다(2026-09-30).

**한 번 굽고(`manage.py build_mars_craters`) 그 뒤로는 sqlite 한 장을 읽는다.** 38 만 개를 브라우저로
보낼 수 없어 서버가 타일로 그린다(달 원도 039 와 같은 길).

- **R*Tree 는 3 차원이다** — 경도·위도에 지름을 더했다. 멀리서 보는 타일은 "그 줌에서 몇 px 넘는 것" 만
  묻는다. 2 차원이면 줌 0 한 장이 38 만 줄을 다 읽는다
- 경도는 ±180 을 넘을 수 있다(원의 네모가 날짜 변경선을 넘으면) — 타일은 네모를 ±360 옮겨 한 번 더 묻는다
- 원은 평균 반지름의 구(`trek.MARS_RADIUS`) 위의 원이다. 등거리 원통에서는 가로로 1/cos φ 늘린 타원으로,
  극 평면(065)에서는 원으로 그린다(평사도법은 모양을 지킨다)
- 색은 보존 상태다 — 1(많이 닳았다)–4(갓 생긴 듯). 크기 5–20 km 에서 깊이/지름의 가운데값이 1 부터
  0.018·0.036·0.076·0.096 으로 커져 4 가 싱싱한 쪽임을 자료로 확인했다. 매기지 않은 것(대개 3 km 밑)은 흰색이다

그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import csv
import io
import math
import sqlite3
import threading
import zipfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import trek

RENDERER = "1"
FILENAME = "mars_craters.sqlite"
TILE = 256
SUPERSAMPLE = 2
#: 이만큼(px, 한 배 크기) 넘는 것만 그린다 — 더 작으면 점이 되어 배경을 덮는다
MIN_PX = 5.0
#: 이보다 적게 읽히면 원본이 잘못된 것이다 — 굽지 않는다
MIN_ROWS = 300000
M_PER_DEG = math.pi * trek.MARS_RADIUS / 180

#: 보존 상태 → (색, 한국어, 영어). 빈 것은 매기지 않았다
STATES = {
    "4": ("#6fe3ff", "4 — 갓 생긴 듯하다", "4 — fresh"),
    "3": ("#5b9dff", "3", "3"),
    "2": ("#a47bff", "2", "2"),
    "1": ("#e070c8", "1 — 많이 닳았다", "1 — heavily degraded"),
    "": ("#ffffff", "매기지 않음", "not classified"),
}

#: 원본의 열 → 우리 칸
COLUMNS = {
    "CRATER_ID": "cid", "LATITUDE_CIRCLE_IMAGE": "lat", "LONGITUDE_CIRCLE_IMAGE": "lon",
    "DIAM_CIRCLE_IMAGE": "d_km", "DEPTH_RIMFLOOR_TOPOG": "depth_km", "MORPHOLOGY_CRATER_1": "morph",
    "MORPHOLOGY_EJECTA_1": "ejecta", "NUMBER_LOBES": "lobes", "DEGRADATION_STATE": "state",
    "CRATER_NAME": "name",
}


class MarsCraterError(RuntimeError):
    pass


def data_file() -> Path:
    return Path(settings.MARS_DIR) / FILENAME


def available() -> bool:
    return data_file().is_file()


_local = threading.local()


def _conn():
    """스레드마다 연결 하나(034). 읽기만 한다."""
    path = str(data_file())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if not Path(path).is_file():
            raise MarsCraterError("크레이터 파일이 없다 — manage.py build_mars_craters 를 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 굽기 ────────────────────────────────────────────────────────────

def _rows(text):
    """원본 표(탭, 줄 끝이 CR 뿐인 옛 맥 꼴) → 우리 칸의 사전들."""
    reader = csv.reader(io.StringIO(text, newline=None), delimiter="\t")
    head = next(reader)
    index = {name: head.index(src) for src, name in COLUMNS.items()}
    for row in reader:
        if len(row) < len(head) - 1:
            continue
        get = lambda k: row[index[k]].strip() if index[k] < len(row) else ""    # noqa: E731
        try:
            lat, lon, d = float(get("lat")), float(get("lon")), float(get("d_km"))
        except ValueError:
            continue
        try:
            depth = float(get("depth_km"))
        except ValueError:
            depth = None
        yield {"cid": get("cid"), "lon": lon, "lat": lat, "d_km": d, "depth_km": depth,
               "morph": get("morph"), "ejecta": get("ejecta"), "lobes": get("lobes"),
               "state": get("state"), "name": get("name")}


def half_width(lat: float, d_km: float) -> tuple:
    """원의 반폭 (경도°, 위도°)."""
    r = d_km * 500 / M_PER_DEG
    return r / max(0.01, math.cos(math.radians(lat))), r


def build(source, out_path) -> int:
    """`RobbinsCraterDatabase_*.tab.zip`(또는 풀어 둔 .tab) → sqlite. 넣은 크레이터 수."""
    source = Path(source)
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as z:
            name = next((n for n in z.namelist() if n.endswith(".tab")), None)
            if not name:
                raise MarsCraterError("zip 에 .tab 이 없다")
            text = z.read(name).decode("latin-1")
    else:
        text = source.read_text(encoding="latin-1")
    out_path = Path(out_path)
    tmp = out_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript("""
        CREATE TABLE craters (id INTEGER PRIMARY KEY, cid TEXT, lon REAL, lat REAL, d_km REAL, depth_km REAL,
                              morph TEXT, ejecta TEXT, lobes TEXT, state TEXT, name TEXT);
        CREATE VIRTUAL TABLE craters_rtree USING rtree(id, minx, maxx, miny, maxy, mind, maxd);
    """)
    n = 0
    for n, c in enumerate(_rows(text), 1):
        conn.execute("INSERT INTO craters VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (n, c["cid"], c["lon"], c["lat"], c["d_km"], c["depth_km"], c["morph"], c["ejecta"],
                      c["lobes"], c["state"], c["name"]))
        dx, dy = half_width(c["lat"], c["d_km"])
        conn.execute("INSERT INTO craters_rtree VALUES (?,?,?,?,?,?,?)",
                     (n, c["lon"] - dx, c["lon"] + dx, c["lat"] - dy, c["lat"] + dy, c["d_km"], c["d_km"]))
    if n < MIN_ROWS:
        conn.close()
        tmp.unlink()
        raise MarsCraterError(f"크레이터가 {n} 개뿐이다 — 원본이 맞나")
    conn.commit()
    conn.close()
    tmp.replace(out_path)
    return n


# ── 그리기 ──────────────────────────────────────────────────────────

def _query(conn, w, e, s, n, min_d):
    rows = {}
    for shift in (0.0, -360.0, 360.0):
        for row in conn.execute(
                "SELECT t.id, t.lon, t.lat, t.d_km, t.state FROM craters_rtree r JOIN craters t ON t.id = r.id "
                "WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ? AND r.maxd >= ?",
                (w + shift, e + shift, s, n, min_d)):
            rows[row[0]] = (row[1] - shift, row[2], row[3], row[4])
    # 큰 것부터 그린다 — 작은 것이 큰 것의 테두리 위에 보이게
    return sorted(rows.values(), key=lambda r: -r[2])


def _rgba(state: str) -> tuple:
    color = STATES.get(state, STATES[""])[0]
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (235,)


def _width(z: int) -> int:
    """선 굵기(두 배 크기 px) — 멀리서는 1 px, 가까이서는 1.5 px."""
    return SUPERSAMPLE if z < 6 else SUPERSAMPLE * 3 // 2


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.resize((TILE, TILE), Image.Resampling.BOX).save(buf, format="PNG")
    return buf.getvalue()


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장(Trek 과 같다) — 256 px 투명 PNG."""
    w, s, e, n = trek.tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)                                   # px / 도
    min_d = MIN_PX / (k / ss) * M_PER_DEG / 1000         # km — 이보다 작으면 그리지 않는다
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    width = _width(z)
    for lon, lat, d, state in _query(_conn(), w, e, s, n, min_d):
        dx, dy = half_width(lat, d)
        cx, cy = (lon - w) * k, (n - lat) * k
        box = (cx - dx * k, cy - dy * k, cx + dx * k, cy + dy * k)
        if box[2] - box[0] > 40 * size:                  # 극 둘레에서 가로로 한없이 늘어난 것
            continue
        draw.ellipse(box, outline=_rgba(state), width=width)
    return _png(img)


def render_polar_tile(pole: str, z: int, x: int, y: int) -> bytes:
    """화성 극 격자 한 장(`trek.mars_polar_tile_bbox`, 065) — 원은 원으로 그린다."""
    if pole not in ("n", "s"):
        raise MarsCraterError("극이 아니다")
    w, s, e, n = trek.mars_polar_tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)                                   # px / 극 평면 m
    # 둘레를 경위도로 되짚어 묻는 네모를 잡는다 — 극을 품거나 날짜 변경선에 걸치면 경도를 다 묻는다
    edge = [(w + (e - w) * i / 8, yy) for i in range(9) for yy in (s, n)] + \
           [(xx, s + (n - s) * i / 8) for i in range(9) for xx in (w, e)]
    lls = [trek.mars_polar_to_lonlat(px, py, pole) for px, py in edge]
    lats = [ll[1] for ll in lls]
    inside = w <= 0 <= e and s <= 0 <= n
    crosses = inside or (w <= 0 <= e and (n > 0 if pole == "n" else s < 0))
    lon_lo, lon_hi = (-180.0, 180.0) if crosses else (min(ll[0] for ll in lls), max(ll[0] for ll in lls))
    lat_lo, lat_hi = (min(lats), 90.0) if pole == "n" else (-90.0, max(lats))
    ratio = trek.MARS_POLAR_RADIUS / trek.MARS_RADIUS
    # 한 px 이 땅에서 몇 m 인가 — 타일 안에서 극에서 가장 먼 곳(가장 크게 그려지는 곳)의 것으로 잡는다
    near = min(abs(lat) for lat in lats)
    ground_per_px = (1 + math.sin(math.radians(near))) / 2 / ratio / (k / ss)
    min_d = MIN_PX * ground_per_px / 1000
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    width = _width(z)
    for lon, lat, d, state in _query(_conn(), lon_lo, lon_hi, lat_lo - 0.5, lat_hi + 0.5, min_d):
        px, py = trek.mars_lonlat_to_polar(lon, lat, pole)
        r = d * 500 * ratio * 2 / (1 + math.sin(math.radians(abs(lat))))
        cx, cy, rr = (px - w) * k, (n - py) * k, r * k
        if cx + rr < 0 or cx - rr > size or cy + rr < 0 or cy - rr > size:
            continue
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=_rgba(state), width=width)
    return _png(img)


# ── 속성 ────────────────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """누른 자리를 품은 크레이터 가운데 가장 작은 것 — 큰 분지 안의 작은 크레이터를 누르면 작은 것."""
    conn = _conn()
    best = None
    for shift in (0.0, -360.0, 360.0):
        x = lon + shift
        for row in conn.execute(
                "SELECT t.cid, t.lon, t.lat, t.d_km, t.depth_km, t.morph, t.ejecta, t.lobes, t.state, t.name "
                "FROM craters_rtree r JOIN craters t ON t.id = r.id "
                "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?", (x, x, lat, lat)):
            cid, clon, clat, d, depth, morph, ejecta, lobes, state, name = row
            dist = _distance_km(lon, lat, clon - shift, clat)
            if dist <= d / 2 and (best is None or d < best["d_km"]):
                best = {"id": cid, "lon": clon - shift, "lat": clat, "d_km": d, "depth_km": depth,
                        "morph": morph, "ejecta": ejecta, "lobes": lobes, "state": state, "name": name}
    return best


def _distance_km(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * trek.MARS_RADIUS / 1000 * math.asin(min(1.0, math.sqrt(a)))
