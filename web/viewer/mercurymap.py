"""수성 지질도 — USGS 1:500만 도폭 아홉을 이은 합본을 우리가 굽는다 (wetherilli P10·144). 문이 아니다.

화성 옛 지질도(068, `marsmap.py`)의 짝이다. 원본은 Frigeri 외(2008)가 USGS 의 수성 지질도 아홉(I-1199 … I-2048,
1980–1990)을 디지털로 이어 USGS 가 옛 PIGWAD 자리에 둔 것이다 —
`asc-pds-services` 의 `pigpen/mercury/merged_geology/mercuryMerged_geology-1.0.zip`. 마리너 10 의 영상으로 그린
지도라 수성의 반쪽 남짓만 덮는다.

**Trek 의 5M 도폭을 쓰지 않은 까닭**(wetherilli 137) — Trek 의 타일은 비어 있고, 같은 도폭을 MESSENGER 바탕에 맞춘
Hunter(2016) 판은 내려받는 자리가 닫혀 있다(2026-10-02, S3 에 파일이 없다). 이 합본은 **마리너 10 시절의 좌표**라
MESSENGER 영상과 어긋날 수 있다 — 어긋남은 wetherilli 144 에 적었다.

- **색** — 합본의 `GRASSRGB` 열이 원도의 색이다. 우리가 고르지 않는다
- **시대** — 열이 없다. 크레이터 물질의 등급(c1 가장 닳음 … c5 가장 또렷함)은 기호에 있고, 그것을 수성의 지질시대
  이름(톨스토이기·칼로리스기 …)에 잇는 일은 하지 않았다 — 도폭마다 쓰는 법이 조금씩 다르다. 범례는 갈래(평원·
  크레이터·분지·기타)로 묶는다
- **구조선** — 합본의 `mercury_s`(구조)와 `mercury_m`(다중 고리 분지의 고리)에서 넷만 그린다 — 엽상 급사면(수성의
  수축이 남긴 것)·능선·단층과 골·분지 고리. 크레이터 테(4 500 남짓)와 선형 지형은 지질 단위의 경계와 겹쳐 뺐다.
  경계선(`mercury_c`)은 단위를 칠하면 저절로 드러나 뺐다
- **어느 도폭인가** — 속성에 없다. 누른 자리로 가른다(`quad_of`) — 수성 사각형 도폭(H-1 … H-15)의 경계다

한 번 굽고(`manage.py build_mercury_geology <zip>`) 그 뒤로는 sqlite 한 장(`GSM_MERCURY_DIR/mercury_geology.sqlite`)을
읽는다. 담는 법(`moonmap.pack`)·칠하는 법(`geomap`)은 빌려 쓰고 고치지 않는다.

그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import io
import logging
import sqlite3
import threading
import zipfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import geo3al, geomap, moonmap, trek

log = logging.getLogger(__name__)

RENDERER = "1"
FILENAME = "mercury_geology.sqlite"
TILE = 256
SUPERSAMPLE = 2
LAYERS = ("units", "lines")
#: 1:500만 — 줌 7(한 픽셀 약 300 m)이면 선이 다 보인다. 가까이 가도 흐리지 않게 10 까지
MAX_ZOOM = 10
#: 이 줌부터 단위의 경계를 옅게 긋는다
OUTLINE_FROM = 4

CITATION = "Frigeri, Federico, Pauselli & Coradini 2008 (USGS Atlas of Mercury 1:5M geologic series, digital merge)"

#: 원도 — (도폭, 이름, I 번호, 지은이, 해). README 의 표를 옮겼다
QUADS = {
    "H-1": ("Borealis", "I-1660", "Grolier & Boyce", 1984),
    "H-2": ("Victoria", "I-1409", "McGill & King", 1983),
    "H-3": ("Shakespeare", "I-1408", "Guest & Greeley", 1983),
    "H-6": ("Kuiper", "I-1233", "De Hon, Scott & Underwood", 1981),
    "H-7": ("Beethoven", "I-2048", "King & Scott", 1990),
    "H-8": ("Tolstoj", "I-1199", "Schaber & McCauley", 1980),
    "H-11": ("Discovery", "I-1658", "Trask & Dzurisin", 1984),
    "H-12": ("Michelangelo", "I-1659", "Spudis & Prosser", 1984),
    "H-15": ("Bach", "I-2015", "Strom, Malin & Leake", 1990),
}

#: 구조선 갈래 — `CLASS_GLOB` 의 값 → 우리 갈래. 없는 값은 그리지 않는다
LINE_KINDS = {"Scarp": "scarp", "Ridge": "ridge", "Fault": "fault", "Trough or depression": "fault",
              "Basin crestline": "ring", "Ring": "ring"}
#: 갈래 → (색, 굵기, 끊은 선인가, 한국어, 영어)
LINE_STYLES = {
    "scarp": ("#ff5a36", 1.6, False, "급사면 (엽상 급사면 포함)", "Scarp (incl. lobate scarps)"),
    "ridge": ("#ffd34d", 1.2, False, "능선", "Ridge"),
    "fault": ("#c08cff", 1.2, True, "단층·골", "Fault or trough"),
    "ring": ("#ffffff", 1.2, True, "분지 고리", "Basin ring"),
}


class MercuryMapError(RuntimeError):
    pass


# ── 자리 ────────────────────────────────────────────────────────────

def data_file() -> Path:
    return Path(settings.MERCURY_DIR) / FILENAME


def available() -> bool:
    return data_file().is_file()


def knows(layer: str) -> bool:
    return layer in LAYERS


_local = threading.local()


def _conn():
    path = str(data_file())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if not Path(path).is_file():
            raise MercuryMapError("수성 지질도 파일이 없다 — manage.py build_mercury_geology 를 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 읽는 법 ─────────────────────────────────────────────────────────

def rgb(value: str) -> str:
    """`"254:180:185"` → `"#feb4b9"`. 못 읽으면 회색."""
    try:
        r, g, b = (max(0, min(255, int(v))) for v in str(value).split(":"))
    except ValueError:
        return "#9a9a9a"
    return "#%02x%02x%02x" % (r, g, b)


def group_of(symbol: str, ugroup: str) -> str:
    """범례의 갈래 — `plains`·`crater`·`basin`·`other`. 기호와 원도의 무리 이름으로 가른다."""
    g = (ugroup or "").upper()
    if "BASIN" in g or "CALORIS" in g or symbol in ("cm", "cn", "co", "com", "cvl", "cvs", "cfp"):
        return "basin"
    if "PLAINS" in g:
        return "plains"
    if "CRATER" in g or "PEAK" in g:
        return "crater"
    return "other"


#: 갈래 → (한국어, 영어). 범례가 이 차례로 선다
GROUPS = {"plains": ("평원", "Plains"), "basin": ("분지", "Basin materials"),
          "crater": ("크레이터", "Crater materials"), "other": ("기타", "Other")}


def quad_of(lon: float, lat: float) -> str:
    """수성 사각형 도폭 — 경도는 동경(−180–180)으로 받는다. 도폭은 서경으로 나뉜다.
    합본이 덮지 않는 도폭(H-4·5·9·10·13·14)도 이름은 낸다 — 거기에는 단위가 없으므로 부를 일이 없다."""
    west = (-lon) % 360                              # 서경 0–360
    # 경계는 USGS 도폭 목록의 것 — 극 66° 너머, 중위도 22–66°, 적도 띠 ±22° (화면의 도폭 경계 레이어와 같다)
    if lat >= 66:
        return "H-1"
    if lat <= -66:
        return "H-15"
    if abs(lat) < 22:
        return f"H-{6 + min(4, int(west // 72))}"
    base = 2 if lat > 0 else 11
    return f"H-{base + min(3, int(west // 90))}"


def _crater_class(symbol: str) -> str:
    """크레이터 물질의 등급 — `c4`·`cp4`·`sc4` → "4". 없으면 빈 칸."""
    if symbol[:1] in ("c", "s") and symbol[-1:] in "12345":
        return symbol[-1]
    return ""


# ── 굽기 (한 번) ────────────────────────────────────────────────────

def build(source, out_path) -> dict:
    """합본(zip 이나 푼 폴더) → sqlite. `manage.py build_mercury_geology` 가 부른다."""
    src = Path(source)
    names = {}
    if src.is_file():
        zf = zipfile.ZipFile(src)
        for n in zf.namelist():
            names[Path(n).name.lower()] = (zf, n)
    else:
        for p in src.rglob("*"):
            names[p.name.lower()] = (None, p)

    def read(name):
        entry = names.get(name)
        if not entry:
            raise MercuryMapError(f"합본에 {name} 이 없다")
        zf, n = entry
        return zf.read(n) if zf else Path(n).read_bytes()

    out = Path(out_path)
    tmp = out.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, symbol TEXT, ugroup TEXT, description TEXT, color TEXT, geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    shapes, rows = geo3al.read_polygons(read("mercury_g.shp")), geo3al.read_dbf(read("mercury_g.dbf"))
    if len(shapes) != len(rows):
        raise MercuryMapError(f"셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
    counts = {"units": 0, "lines": 0}
    for rings, row in zip(shapes, rows):
        if row is None or not rings:
            continue
        symbol = (row.get("USYM") or "").strip()
        # "No Coverage" 는 도폭 사이의 빈 곳, 기호 없는 검은 조각은 디지털화의 찌꺼기다
        if not symbol or symbol == "No Coverage":
            continue
        polygons = [[moonmap._unwrap(r) for r in poly] for poly in geo3al.group_rings(rings)]
        polygons = [p for p in polygons if p and len(p[0]) >= 6]
        if not polygons:
            continue
        cur = db.execute("INSERT INTO units (symbol, ugroup, description, color, geom) VALUES (?,?,?,?,?)",
                         (symbol, (row.get("UGROUP") or "").strip(), (row.get("DESCRIPTIO") or "").strip(),
                          rgb(row.get("GRASSRGB")), moonmap.pack(polygons)))
        db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox(polygons)))
        counts["units"] += 1
    for stem in ("mercury_s", "mercury_m"):
        for parts, row in zip(moonmap._read_lines(read(stem + ".shp")), geo3al.read_dbf(read(stem + ".dbf"))):
            kind = LINE_KINDS.get(((row or {}).get("CLASS_GLOB") or "").strip())
            flat = [moonmap._unwrap(part) for part in parts if len(part) >= 2]
            if not flat or not kind:
                continue
            cur = db.execute("INSERT INTO lines (kind, geom) VALUES (?,?)", (kind, moonmap.pack([flat])))
            db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox([flat])))
            counts["lines"] += 1
    db.execute("INSERT INTO meta VALUES ('renderer', ?)", (RENDERER,))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    return counts


# ── 그리기 ──────────────────────────────────────────────────────────

def _hex(value: str) -> tuple:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def _select(layer, w, e, s, n):
    """네모에 걸친 모양 `[(경도 옮김, (갈래, 색·종류, 모양))]` — 넣은 차례로. 경도를 이어 적었으므로 네모를 ±360 옮겨
    한 번 더 묻는다(marsmap 과 같다)."""
    table = "units" if layer == "units" else "lines"
    style = "t.color" if table == "units" else "t.kind"
    found = {}
    for shift in (0.0, -360.0, 360.0):
        for row_id, st, blob in _conn().execute(
                f"SELECT t.id, {style}, t.geom FROM {table}_rtree r JOIN {table} t ON t.id = r.id "
                f"WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?", (w + shift, e + shift, s, n)):
            found.setdefault(row_id, (shift, (table, st, blob)))
    return [found[k] for k in sorted(found)]


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """수성 경위도 격자 한 장(Trek 과 같다) — 256 px 투명 PNG."""
    if layer not in LAYERS:
        raise MercuryMapError("수성 지질 레이어가 아니다")
    w, s, e, n = trek.tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    pad = 3 / k
    tr = (w, n, k, k)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for shift, (table, style, blob) in _select(layer, w - pad, e + pad, s - pad, n + pad):
        parts = [[[v - shift if i % 2 == 0 else v for i, v in enumerate(r)] for r in rings]
                 for rings in moonmap.unpack(blob)]
        xs = [v for rings in parts for r in rings for v in r[0::2]]
        ys = [v for rings in parts for r in rings for v in r[1::2]]
        if not xs:
            continue
        size_px = max(max(xs) - min(xs), max(ys) - min(ys)) * k
        if table == "units":
            color = _hex(style)
            if size_px < 1.5 * ss:
                cx, cy = ((min(xs) + max(xs)) / 2 - w) * k, (n - (min(ys) + max(ys)) / 2) * k
                draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=color)
                continue
            rule = {"fill": color, "outline": (0, 0, 0, 90) if z >= OUTLINE_FROM else None, "width": 1}
            for rings in parts:
                geomap._fill_polygon(img, draw, rings, rule, tr, size_px, ss)
        else:
            color, width, dash = LINE_STYLES[style][:3]
            strokes = [{"color": _hex(color), "width": width, "dash": [4, 3] if dash else None}]
            for lines in parts:
                for flat in lines:
                    for run in geomap._clip_runs(geomap._to_px(flat, tr, size_px), size, size, 8 * ss):
                        geomap._stroke(draw, run, strokes, ss)
    buf = io.BytesIO()
    img.resize((TILE, TILE), Image.Resampling.BOX).save(buf, format="PNG")
    return buf.getvalue()


# ── 속성·범례 ───────────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 단위 — `{"unit", "group", "description", "color", "quad", "map", "by", "year", "crater_class"}`."""
    hits = []
    for shift in (0.0, -360.0, 360.0):
        x = lon + shift
        for row in _conn().execute(
                "SELECT t.id, t.symbol, t.ugroup, t.description, t.color, t.geom FROM units_rtree r "
                "JOIN units t ON t.id = r.id WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
                (x, x, lat, lat)):
            if any(geomap.polygon_contains([list(r) for r in rings], x, lat) for rings in moonmap.unpack(row[5])):
                hits.append(row)
    if not hits:
        return None
    # 겹치면 작은 것(크레이터 안의 바닥·봉우리)이 위다 — 넣은 차례가 원도의 그리는 차례를 따르지 않는다.
    # 크기는 모양을 두른 네모의 넓이로 잰다
    def extent(row):
        w, e, s, n = moonmap._bbox(moonmap.unpack(row[5]))
        return (e - w) * (n - s)
    _, symbol, ugroup, description, color, _ = min(hits, key=extent)
    quad = quad_of(lon, lat)
    name, map_id, by, year = QUADS.get(quad, ("", "", "", 0))
    return {"unit": symbol, "group": ugroup, "description": description, "color": color,
            "quad": f"{quad} {name}".strip(), "map": map_id, "by": by, "year": year,
            "crater_class": _crater_class(symbol)}


def legend(lang: str = "ko") -> dict:
    """단위(기호·무리 이름·색 — 이름은 원도의 값이라 옮기지 않는다)를 갈래로 묶은 것과 구조선 갈래."""
    try:
        rows = _conn().execute("SELECT symbol, ugroup, color, COUNT(*) FROM units GROUP BY symbol, color "
                               "ORDER BY symbol").fetchall()
    except (MercuryMapError, sqlite3.Error):
        rows = []
    units, seen = [], set()
    for symbol, ugroup, color, _ in rows:
        if symbol in seen:
            continue
        seen.add(symbol)
        key = group_of(symbol, ugroup)
        units.append({"unit": symbol, "label": (ugroup or symbol).capitalize(), "color": color,
                      "group": GROUPS[key][1 if lang == "en" else 0]})
    order = [v[1 if lang == "en" else 0] for v in GROUPS.values()]
    units.sort(key=lambda u: (order.index(u["group"]), u["unit"]))
    lines = [{"color": c, "dash": d, "label": en if lang == "en" else ko} for c, _, d, ko, en in LINE_STYLES.values()]
    return {"units": units, "lines": lines}
