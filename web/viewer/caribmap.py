"""USGS 대앤틸리스·버진아일랜드 지질도(SIM 3534 의 옛 판, OFR 2019-1036) — 우리 디스크의 파일을 읽어 3857 타일을 굽는다 (wetherilli 254).

상류가 아니라 **파일**이다 — `moonmap.py`·`geomap.py` 처럼 문이 아니다. 웹서비스가 없고(ScienceBase 403, 2026-10-05) 옛 판의 셰이프 zip
(`pubs.usgs.gov/of/2019/1036/ofr20191036_spatialdata.zip`, 196 MB)만 받을 수 있다. 원본은 NAS `N:\\GSM\\sources\\caribbean\\` 에 두고,
**한 번 굽고(`manage.py build_caribbean <zip>`) 그 뒤로는 sqlite 한 장을 읽는다**(`GSM_CARIBBEAN_DIR`, 기본 `<DB 옆>/caribbean`).
파일이 없어도 뷰어는 돌고 그 자리에 안내가 뜬다.

- 덮는 곳: 쿠바·이스파니올라(아이티·도미니카공화국)·자메이카·푸에르토리코·버진아일랜드·케이맨 — 1:30만 급(나라마다 원도의 축척이 다르다).
  #236 의 카리브 1:250만(`usgscarib.py`)보다 훨씬 자세하다
- 좌표: 셰이프는 "Caribbean_Lambert_Conformal_Conic"(WGS84, 표준위선 17.5°·22.5°, 중앙 경선 −73.5°, 가짜 동·북 500 km)이다. 굽을 때
  `crs.lcc_to_latlon` 으로 경위도로 옮기고 **3857 미터로 담는다** — 타일을 그릴 때 옮기지 않으려고. float32 라 서경 80° 에서도 0.5 m 다
- 색: 면의 `GA_SYMBOL` 은 USGS 지질도 표준 CMYK 채움(`wpgcmykg.style`)의 번호다. 스타일 파일의 직렬화에서 CMYK 를 읽어 둔 표
  `data/usgs_wpg_colors.json` 으로 칠한다(127 기호가 다 든다)
- 설명: zip 의 `supplemental_databases/CSV/GAdescrp.csv` 를 `GAclass` 로 붙인다(영어, 옮기지 않는다)
- 레이어 둘 — 단위(면 2 만 3 천, 물은 뺀다)와 단층(호 8 만 가운데 단층 4 만 남짓 — 접촉선은 면의 테두리가 그린다)
- 조건: **공공 도메인**(USGS). 인용 Wilson & Labay 2025(SIM 3534) — 옛 판은 French & Schenk 가 아니라 Wilson 외 2019(OFR 2019-1036)
그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import csv
import io
import json
import math
import sqlite3
import threading
import zipfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import crs, geo3al, geomap
from .i18n import msg
from .moonmap import pack, unpack

PREFIX = "sim3534:"
LAYERS = {"sim3534:units": "units", "sim3534:faults": "lines"}
FILENAME = "sim3534.sqlite"
RENDERER = 1
TILE = 256
SUPERSAMPLE = 2
MAX_ZOOM = 15
ATTRIBUTION = ('<a href="https://doi.org/10.3133/ofr20191036" target="_blank" rel="noopener">USGS — Geologic map of the Greater '
               'Antilles and the Virgin Islands</a> (Wilson et al. 2019, OFR 2019-1036 · SIM 3534, public domain)')
#: 셰이프의 람베르트 정각원추(`GAgeol_poly.prj`)
LCC = {"lon0": -73.5, "lat1": 17.5, "lat2": 22.5, "lat0": 17.5, "fe": 500000.0, "fn": 500000.0}
#: 물 — 그리지 않는다(`GACLASS` 102, 기호 300)
WATER = {"102"}
#: 단층의 갈래 — `LINE_TYPE` 에 이 말이 들면. 차례대로 먼저 맞는 것
FAULTS = (("thrust", "Thrust"), ("normal", "Normal"), ("strike", "lateral"), ("concealed", "Concealed"), ("fault", "ault"))
#: 단층 갈래의 이름 — 범례
FAULT_NAMES = {"thrust": msg("드러스트"), "normal": msg("정단층"), "strike": msg("주향이동단층"), "concealed": msg("덮인 단층"),
               "fault": msg("단층 (변위 모름)")}
LINE_STYLES = {
    "thrust": {"color": "#b2182b", "width": 1.6},
    "normal": {"color": "#2166ac", "width": 1.4},
    "strike": {"color": "#762a83", "width": 1.4},
    "concealed": {"color": "#333333", "width": 1.0, "dash": [4, 4]},
    "fault": {"color": "#1a1a1a", "width": 1.2},
}
HALF = 20037508.342789244


class CaribMapError(RuntimeError):
    pass


def data_dir() -> Path:
    return Path(settings.CARIBBEAN_DIR)


def data_file() -> Path:
    return data_dir() / FILENAME


def available() -> bool:
    return data_file().is_file()


def knows(layer: str) -> bool:
    return layer in LAYERS


def sheet_of(layer: str) -> str:
    return layer[len(PREFIX):]


_local = threading.local()


def _conn():
    path = str(data_file())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if not Path(path).is_file():
            raise CaribMapError("카리브 지질도 파일이 없다 — manage.py build_caribbean 을 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 좌표 ────────────────────────────────────────────────────────────

def lonlat_to_merc(lon: float, lat: float) -> tuple:
    lat = max(-85.0, min(85.0, lat))
    return lon * HALF / 180.0, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137.0


def merc_to_lonlat(x: float, y: float) -> tuple:
    return x / HALF * 180.0, math.degrees(2 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2)


def lcc_to_merc(east: float, north: float) -> tuple:
    lat, lon = crs.lcc_to_latlon(east, north, LCC["lon0"], LCC["lat1"], LCC["lat2"], LCC["lat0"], LCC["fe"], LCC["fn"])
    return lonlat_to_merc(lon, lat)


def tile_bbox(z: int, x: int, y: int) -> tuple:
    size = 2 * HALF / 2 ** z
    return -HALF + x * size, HALF - (y + 1) * size, -HALF + (x + 1) * size, HALF - y * size


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


# ── 색 ──────────────────────────────────────────────────────────────

_palette = None


def palette() -> dict:
    global _palette
    if _palette is None:
        path = Path(settings.BASE_DIR).parent / "data" / "usgs_wpg_colors.json"
        _palette = json.loads(path.read_text(encoding="utf-8"))["colors"]
    return _palette


def _hex(value: str, alpha: int = 255) -> tuple:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def fault_kind(line_type: str) -> str | None:
    text = str(line_type or "")
    if "ault" not in text:
        return None
    return next(kind for kind, word in FAULTS if word in text)


def fault_legend(lang: str = "ko") -> list:
    """단층 범례 — 갈래 다섯, 선 색을 견본 칸으로"""
    from . import i18n
    return [{"color": LINE_STYLES[k]["color"], "symbol": "", "swatch": "", "age": "",
             "lithology": i18n.t(FAULT_NAMES[k], lang)} for k in LINE_STYLES]


# ── 굽기 (한 번) ────────────────────────────────────────────────────

def _bbox(polygons) -> tuple:
    xs = [v for rings in polygons for ring in rings for v in ring[0::2]]
    ys = [v for rings in polygons for ring in rings for v in ring[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def _descriptions(text: str) -> dict:
    """`GAdescrp.csv` → GAclass 마다 (이름, 시대, 설명, 암상 갈래). 같은 GAclass 가 여럿이면 첫 줄."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = str(row.get("GAclass") or "").strip()
        if key and key not in out:
            out[key] = ((row.get("Unit_name") or "").strip(), (row.get("Age_range") or "").strip(),
                        (row.get("Description") or "").strip(), (row.get("Lith_type") or "").strip())
    return out


def build(source, out_path) -> dict:
    """USGS zip(또는 푼 폴더) → sqlite. `manage.py build_caribbean` 이 부른다."""
    src = Path(source)
    names = {}
    if src.is_file():
        zf = zipfile.ZipFile(src)
        for n in zf.namelist():
            if "__macosx" not in n.lower():
                names[n.lower()] = n
        read = lambda n: zf.read(n)                  # noqa: E731
    else:
        for p in src.rglob("*"):
            if "__macosx" not in str(p).lower():
                names[str(p.relative_to(src)).lower()] = p
        read = lambda p: Path(p).read_bytes()       # noqa: E731

    def find(suffix):
        for low, real in names.items():
            if low.endswith(suffix.lower()):
                return real
        raise CaribMapError(f"zip 에 {suffix} 가 없다")

    colors = palette()
    descr = _descriptions(read(find("csv/gadescrp.csv")).decode("cp1252"))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, label TEXT, name TEXT, age TEXT, gaclass TEXT, color TEXT, geom BLOB);
        CREATE TABLE descr (gaclass TEXT PRIMARY KEY, text TEXT, lith TEXT);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    shapes = geo3al.read_polygons(read(find("shapefiles/gageol_poly.shp")))
    rows = geo3al.read_dbf(read(find("shapefiles/gageol_poly.dbf")))
    if len(shapes) != len(rows):
        raise CaribMapError(f"면 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
    counts = {"units": 0, "faults": 0}
    for rings, row in zip(shapes, rows):
        if row is None or not rings:
            continue
        gaclass = str(row.get("GACLASS") or "").strip()
        if gaclass in WATER:
            continue
        polygons = []
        for poly in geo3al.group_rings(rings):
            conv = []
            for ring in poly:
                flat = []
                for x, y in ring:
                    flat += lcc_to_merc(x, y)
                if len(flat) >= 6:
                    conv.append(flat)
            if conv:
                polygons.append(conv)
        if not polygons:
            continue
        symbol = str(row.get("GA_SYMBOL") or "").strip()
        name, age, _, _ = descr.get(gaclass, ("", "", "", ""))
        cur = db.execute(
            "INSERT INTO units (label, name, age, gaclass, color, geom) VALUES (?,?,?,?,?,?)",
            ((row.get("GA_LABEL") or "").strip(), (row.get("GA_UNITNAM") or name).strip(),
             (row.get("AGE_RANGE") or age).strip(), gaclass, colors.get(symbol, "#cccccc"), pack(polygons)))
        db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *_bbox(polygons)))
        counts["units"] += 1

    # 설명은 GAclass 마다 한 번 — 면마다 적으면 2 만 3 천 번 되풀이된다(76 MB 가 된다)
    db.executemany("INSERT INTO descr VALUES (?,?,?)", [(key, text, lith) for key, (_, _, text, lith) in descr.items()])
    from .moonmap import _read_lines
    lines = _read_lines(read(find("shapefiles/gageol_arc.shp")))
    lrows = geo3al.read_dbf(read(find("shapefiles/gageol_arc.dbf")))
    for parts, row in zip(lines, lrows):
        kind = fault_kind((row or {}).get("LINE_TYPE"))
        if kind is None or not parts:
            continue
        flat = []
        for part in parts:
            if len(part) >= 2:
                seg = []
                for x, y in part:
                    seg += lcc_to_merc(x, y)
                flat.append(seg)
        if not flat:
            continue
        cur = db.execute("INSERT INTO lines (kind, geom) VALUES (?,?)", (kind, pack([flat])))
        db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *_bbox([flat])))
        counts["faults"] += 1
    db.execute("INSERT INTO meta VALUES ('renderer', ?)", (str(RENDERER),))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    return counts


# ── 타일 ────────────────────────────────────────────────────────────

def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """3857 z/x/y 한 장 — 256 px 투명 PNG."""
    if layer not in LAYERS or not valid_tile(z, x, y):
        raise CaribMapError("그런 타일은 없다")
    w, s, e, n = tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 3 / k
    tr = (w, n, k, k)
    conn = _conn()
    if LAYERS[layer] == "units":
        rows = conn.execute(
            "SELECT t.id, r.minx, r.maxx, r.miny, r.maxy, t.color, t.geom FROM units_rtree r JOIN units t ON t.id = r.id "
            "WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ? ORDER BY t.id",
            (w - pad, e + pad, s - pad, n + pad)).fetchall()
        outline = (60, 40, 30, 110) if z >= 9 else None
        for _, x0, x1, y0, y1, color, blob in rows:
            size_px = max(x1 - x0, y1 - y0) * k
            fill = _hex(color)
            if size_px < 1.5 * ss:
                cx, cy = ((x0 + x1) / 2 - w) * k, (n - (y0 + y1) / 2) * k
                draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=fill)
                continue
            rule = {"fill": fill, "outline": outline, "width": 1}
            for rings in unpack(blob):
                geomap._fill_polygon(img, draw, [list(r) for r in rings], rule, tr, size_px, ss)
    else:
        rows = conn.execute(
            "SELECT t.kind, r.minx, r.maxx, r.miny, r.maxy, t.geom FROM lines_rtree r JOIN lines t ON t.id = r.id "
            "WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?",
            (w - pad, e + pad, s - pad, n + pad)).fetchall()
        for kind, x0, x1, y0, y1, blob in rows:
            style = LINE_STYLES[kind]
            strokes = [{"color": _hex(style["color"]), "width": style["width"], "dash": style.get("dash")}]
            size_px = max(x1 - x0, y1 - y0) * k
            for parts in unpack(blob):
                for flat in parts:
                    for run in geomap._clip_runs(geomap._to_px(list(flat), tr, size_px), size, size, 8 * ss):
                        geomap._stroke(draw, run, strokes, ss)
    out = img.resize((TILE, TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# ── 누른 자리·범례 ──────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 단위. 겹치면 나중에 그린 것(번호가 큰 것)이 이긴다."""
    x, y = lonlat_to_merc(lon, lat)
    hits = []
    for row in _conn().execute(
            "SELECT t.id, t.label, t.name, t.age, d.text, d.lith, t.color, t.geom FROM units_rtree r JOIN units t ON t.id = r.id "
            "LEFT JOIN descr d ON d.gaclass = t.gaclass "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?", (x, x, y, y)):
        if any(geomap.polygon_contains([list(r) for r in rings], x, y) for rings in unpack(row[7])):
            hits.append(row)
    if not hits:
        return None
    _, label, name, age, descr, lith, color, _ = max(hits, key=lambda r: r[0])
    return {"label": label, "name": name, "age": age, "description": descr, "lithology": lith, "color": color}


#: 팝업에 싣는 설명의 글자 수 끝
DESCR_MAX = 600


def friendly(unit: dict, lang: str = "ko") -> dict:
    """팝업의 칸 — 값은 영어 그대로, 시대만 옮긴다."""
    from . import i18n
    age = unit.get("age") or ""
    text = unit.get("description") or ""
    if len(text) > DESCR_MAX:                 # 설명이 몇 천 자인 단위가 있다 — 팝업에는 앞만
        text = text[:DESCR_MAX].rsplit(" ", 1)[0] + " …"
    rows = (("기호", unit.get("label")), ("이름", unit.get("name")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("암상", unit.get("lithology")),
            ("설명", text))
    return {k: v for k, v in rows if v}


#: 범례를 뜨는 가장 넓은 범위(°)와 칸 수
LEGEND_SPAN = 8.0
MAX_LEGEND = 60


def extent_legend(west: float, south: float, east: float, north: float, lang: str = "ko") -> list:
    """범위(위경도)에 걸친 단위 — `[{"symbol", "lithology", "color", "age", "count"}]`, 면이 많은 것부터. R*Tree 의 네모로 센다."""
    from . import i18n
    x0, y0 = lonlat_to_merc(west, south)
    x1, y1 = lonlat_to_merc(east, north)
    rows = {}
    for label, name, age, color in _conn().execute(
            "SELECT t.label, t.name, t.age, t.color FROM units_rtree r JOIN units t ON t.id = r.id "
            "WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?", (x0, x1, y0, y1)):
        row = rows.setdefault((label, name), {"symbol": label, "lithology": f"{label} {name}".strip(), "color": color,
                                              "swatch": "", "age": i18n.age_ko(age) if lang == "ko" and age else age,
                                              "count": 0})
        row["count"] += 1
    return sorted(rows.values(), key=lambda r: -r["count"])
