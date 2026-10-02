"""USGS 달 지질도 원도 6 장 — 우리 디스크의 파일을 읽어 달 경위도 타일을 굽는다 (devlog 039).

상류가 아니라 **파일**이다 — `geomap.py`·`geo3al.py` 처럼 문이 아니다. 원본은 USGS 의
"Lunar Geologic GIS Renovation" (Fortezzo·Hare, 2013) — 1971–1979 년에 나온 1:500만 원도 6 장을
디지털로 옮긴 것이다. NASA Moon Trek 은 이것을 주지 않는다(2026-09-29). 달 화면이 지금 쓰는
통합 지질도(2020, `trek.py`)는 이 여섯 장을 이어 다듬은 것이다 — 원도는 **다듬기 전의 원래 단위**를
본다(단위 195 가지, 원문 이름·설명, 구조선).

| 원도 | 덮는 곳 | 좌표 |
|---|---|---|
| I-703 | 앞면 (경도 ±70°, 위도 ±64°) | 달 경위도(도) |
| I-948 | 동쪽 (50–140°E) | 〃 |
| I-1034 | 서쪽 (50–140°W) | 〃 |
| I-1047 | 뒷면 가운데 (140°E–140°W) | 〃 |
| I-1062 | 북쪽 (북위 45° 위) | 달 북극 평사도법(미터) |
| I-1162 | 남쪽 (남위 45° 아래) | 달 남극 평사도법(미터) |

**한 번 굽고(`manage.py build_moon_originals`) 그 뒤로는 sqlite 한 장을 읽는다.** 셰이프파일을 읽어
극지 두 장을 경위도로 옮기고, R*Tree 를 딸려 `moon_originals.sqlite` 로 둔다. GDAL 을 쓰지 않는다.

- **경도는 이어 적는다.** 고리를 따라 경도가 ±180° 에서 끊기지 않게 360 을 더하거나 빼 둔다 —
  I-1047 은 날짜 변경선을 가로지른다. 그래서 한 고리의 경도가 180 을 넘을 수 있고, 타일을 구울
  때는 네모를 ±360 옮겨 한 번 더 묻는다
- **극을 두르는 고리는 극으로 닫는다.** 극 평사도법의 고리가 극을 품으면 경위도에서는 경도가 한 바퀴
  돌 뿐 닫히지 않는다 — 끝에서 극(±90°)으로 내려갔다 처음으로 돌아오게 두 점을 더한다
- 원도끼리 겹치는 곳(위도 45–64°)은 적도 쪽 원도가 위에 그려진다

색은 `data/moon_original_styles.json` — 단위 195 가지를 29 갈래로 묶은 것이다(Eleanor Lutz, GPL-3.0).
그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import io
import json
import logging
import math
import sqlite3
import struct
import threading
import zipfile
from array import array
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import geo3al, geomap, trek

log = logging.getLogger(__name__)

RENDERER = "1"
FILENAME = "moon_originals.sqlite"
R = 1737400.0
TILE = 256
MAX_ZOOM = 12

#: 원도 — 그리는 차례(아래부터). 극지를 먼저 깔고 적도 쪽을 위에 얹는다
MAPS = {
    "I-1062": {"title": "Geologic Map of the North Side of the Moon", "by": "Lucchitta", "year": 1978,
               "pole": 1, "ko": "북쪽"},
    "I-1162": {"title": "Geologic Map of the South Side of the Moon", "by": "Wilhelms, Howard & Wilshire",
               "year": 1979, "pole": -1, "ko": "남쪽"},
    "I-1047": {"title": "Geologic Map of the Central Far Side of the Moon", "by": "Stuart-Alexander",
               "year": 1978, "ko": "뒷면 가운데"},
    "I-1034": {"title": "Geologic Map of the West Side of the Moon", "by": "Scott, McCauley & West",
               "year": 1977, "ko": "서쪽"},
    "I-948": {"title": "Geologic Map of the East Side of the Moon", "by": "Wilhelms & El-Baz",
              "year": 1977, "ko": "동쪽"},
    "I-703": {"title": "Geologic Map of the Near Side of the Moon", "by": "Wilhelms & McCauley",
              "year": 1971, "ko": "앞면"},
}
#: 원도 번호 → zip 안의 폴더 이름(네 자리)
_FOLDER = {k: "I-" + k[2:].zfill(4) for k in MAPS}

LAYERS = ("orig-units", "orig-lines")
ATTRIBUTION = ("USGS 1:5M lunar geologic maps (1971–1979), digital renovation by Fortezzo & Hare (2013); "
               "unit colors after E. Lutz, Atlas of Space (GPL-3.0)")


class MoonMapError(RuntimeError):
    pass


# ── 자리 ────────────────────────────────────────────────────────────

def data_dir() -> Path:
    return Path(settings.MOON_DIR)


def data_file() -> Path:
    return data_dir() / FILENAME


def available() -> bool:
    return data_file().is_file()


def knows(layer: str) -> bool:
    return layer in LAYERS


_local = threading.local()


def _conn():
    """스레드마다 연결 하나(034 — 워커가 스레드를 쓴다). 읽기만 한다."""
    path = str(data_file())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if not Path(path).is_file():
            raise MoonMapError("원도 파일이 없다 — manage.py build_moon_originals 를 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 색 ──────────────────────────────────────────────────────────────

_styles = None


def styles() -> dict:
    global _styles
    if _styles is None:
        path = Path(settings.BASE_DIR).parent / "data" / "moon_original_styles.json"
        _styles = json.loads(path.read_text(encoding="utf-8"))
    return _styles


def _hex(value: str, alpha: int = 255) -> tuple:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def unit_color(map_id: str, symbol: str) -> str:
    """원도·기호 → 색. 표에 없으면 회색 — 드물다(195 가운데 한둘)."""
    return styles()["units"].get(f"{_FOLDER.get(map_id, map_id)}/{symbol}", "#9a9a9a")


def line_style(kind: str) -> dict:
    text = (kind or "").lower()
    for rule in styles()["lines"]:
        if not rule["match"] or any(word in text for word in rule["match"].split("|")):
            return rule
    return styles()["lines"][-1]


# ── 시대 ────────────────────────────────────────────────────────────
#
# 원도의 시대는 "Imbrian and Nectarian Systems" 처럼 낱말을 짠 것이다. 한국어판은 낱말째 옮긴다 —
# 달 통합 지질도의 `trek.AGES_KO` 와 같은 이름에 "계"(System)를 붙인다

_SYSTEM_KO = (("pre-nectarian", "선넥타리스"), ("pre-imbrian", "선임브리움"), ("copernican", "코페르니쿠스"),
              ("eratosthenian", "에라토스테네스"), ("imbrian", "임브리움"), ("nectarian", "넥타리스"))


def epoch_ko(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    low = raw.lower().replace("systems", "").replace("system", "").replace("/", " or ")
    joiner = " 또는 " if " or " in low else "·"
    names, rest = [], low
    while rest.strip():
        rest = rest.strip(" ,")
        for en, ko in _SYSTEM_KO:
            if rest.startswith(en):
                names.append(ko + "계")
                rest = rest[len(en):]
                break
        else:
            if rest.startswith("and "):
                rest = rest[4:]
            elif rest.startswith("or "):
                rest = rest[3:]
            else:
                return raw                        # 모르는 낱말 — 옮기지 않는다
    return joiner.join(names) if names else raw


# ── 기하 꾸리기 ─────────────────────────────────────────────────────
#
# 한 모양 = 다각형 목록, 다각형 = 고리 목록(첫째가 바깥). 고리는 float32 경도·위도 쌍이다 —
# 1e-7° 는 달에서 3 mm 이다

def pack(polygons) -> bytes:
    out = [struct.pack("<I", len(polygons))]
    for rings in polygons:
        out.append(struct.pack("<I", len(rings)))
        for ring in rings:
            out.append(struct.pack("<I", len(ring) // 2))
            out.append(array("f", ring).tobytes())
    return b"".join(out)


def unpack(blob: bytes) -> list:
    at = 4
    polygons = []
    for _ in range(struct.unpack_from("<I", blob, 0)[0]):
        nrings = struct.unpack_from("<I", blob, at)[0]
        at += 4
        rings = []
        for _ in range(nrings):
            n = struct.unpack_from("<I", blob, at)[0]
            at += 4
            ring = array("f")
            ring.frombytes(blob[at:at + 8 * n])
            at += 8 * n
            rings.append(ring)
        polygons.append(rings)
    return polygons


def stereo_to_lonlat(x: float, y: float, pole: int) -> tuple:
    """달 극 평사도법(구, 극에서 축척 1, 가짜 동거 0) → 경위도."""
    rho = math.hypot(x, y)
    c = 2 * math.atan2(rho, 2 * R)
    lat = pole * (90.0 - math.degrees(c))
    lon = math.degrees(math.atan2(x, -y if pole > 0 else y))
    return lon, lat


def _unwrap(points, pole=0) -> list:
    """[(lon, lat)] → 경도를 이어 적은 납작한 고리. 극을 두르면 극으로 닫는다."""
    flat, prev, total = [], None, 0.0
    first = None
    for lon, lat in points:
        if prev is not None:
            d = lon - prev
            while d > 180:
                lon -= 360
                d -= 360
            while d < -180:
                lon += 360
                d += 360
            total += d
        if first is None:
            first = lon
        flat += [lon, lat]
        prev = lon
    if pole and abs(total) > 300 and flat:
        # 극을 한 바퀴 두른 고리 — 극으로 내려갔다 처음 경도로 돌아와 닫는다
        flat += [flat[-2], 90.0 * pole, first, 90.0 * pole, flat[0], flat[1]]
    return flat


def _bbox(polygons) -> tuple:
    xs = [v for rings in polygons for ring in rings for v in ring[0::2]]
    ys = [v for rings in polygons for ring in rings for v in ring[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def _read_lines(data: bytes) -> list:
    """선 셰이프파일(3) → 행마다 선 목록(평면 좌표)."""
    if struct.unpack("<i", data[32:36])[0] != 3:
        raise MoonMapError("선 셰이프파일이 아니다")
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        parts = []
        if struct.unpack("<i", data[body:body + 4])[0] == 3:
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            for a, b in zip(starts, starts[1:]):
                parts.append([(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)])
        out.append(parts)
        at = body + words * 2
    return out


# ── 굽기 (한 번) ────────────────────────────────────────────────────

def build(source, out_path) -> dict:
    """USGS zip(또는 푼 폴더) → sqlite. `manage.py build_moon_originals` 가 부른다."""
    src = Path(source)
    names = {}
    if src.is_file():
        zf = zipfile.ZipFile(src)
        for n in zf.namelist():
            names[n.lower()] = n
        read = lambda n: zf.read(n)                  # noqa: E731
    else:
        for p in src.rglob("*"):
            names[str(p.relative_to(src)).lower()] = p
        read = lambda p: Path(p).read_bytes()       # noqa: E731

    def find(folder, *suffixes):
        for low, real in names.items():
            if f"/{folder.lower()}/shapefiles/" in "/" + low and low.endswith(suffixes):
                return real
        return None

    out = Path(out_path)
    tmp = out.with_suffix(".part")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, map TEXT, draw INTEGER, symbol TEXT, name TEXT,
                            grp TEXT, epoch TEXT, descr TEXT, color TEXT, geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, map TEXT, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    counts = {}
    for draw, (map_id, spec) in enumerate(MAPS.items()):
        folder, pole = _FOLDER[map_id], spec.get("pole", 0)
        shp = find(folder, "geology.shp")
        dbf = find(folder, "geology.dbf")
        if not shp or not dbf:
            raise MoonMapError(f"{map_id} 의 지질 셰이프파일이 없다")
        shapes = geo3al.read_polygons(read(shp))
        rows = geo3al.read_dbf(read(dbf))
        if len(shapes) != len(rows):
            raise MoonMapError(f"{map_id}: 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")

        def conv(ring):
            pts = [stereo_to_lonlat(x, y, pole) for x, y in ring] if pole else ring
            return _unwrap(pts, pole)

        n = 0
        for rings, row in zip(shapes, rows):
            if row is None or not rings:
                continue
            # 바깥·구멍은 원래 좌표에서 가른다 — 극 평사도법에서 경위도로 옮기면 고리의 방향이 뒤집힌다
            polygons = [[conv(r) for r in poly] for poly in geo3al.group_rings(rings)]
            polygons = [p for p in polygons if p and len(p[0]) >= 6]
            if not polygons:
                continue
            symbol = (row.get("UnitSymbol") or "").strip()
            cur = db.execute(
                "INSERT INTO units (map, draw, symbol, name, grp, epoch, descr, color, geom) VALUES (?,?,?,?,?,?,?,?,?)",
                (map_id, draw, symbol, (row.get("UnitName") or row.get("UnitName_1") or "").strip(),
                 (row.get("MajorGroup") or "").strip(), (row.get("Epoch") or row.get("Epoch_1") or "").strip(),
                 (row.get("UnitDescri") or "").strip(), unit_color(map_id, symbol), pack(polygons)))
            db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *_bbox(polygons)))
            n += 1
        counts[map_id] = n

        lshp = find(folder, "structure.shp", "structures.shp")
        ldbf = find(folder, "structure.dbf", "structures.dbf")
        if lshp and ldbf:
            lines = _read_lines(read(lshp))
            lrows = geo3al.read_dbf(read(ldbf))
            for parts, row in zip(lines, lrows):
                if row is None or not parts:
                    continue
                flat = [conv(part) for part in parts if len(part) >= 2]
                if not flat:
                    continue
                cur = db.execute("INSERT INTO lines (map, kind, geom) VALUES (?,?,?)",
                                 (map_id, (row.get("StructureT") or "").strip(), pack([flat])))
                db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *_bbox([flat])))
    db.execute("INSERT INTO meta VALUES ('renderer', ?)", (RENDERER,))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    return counts


# ── 굽기 (타일) ─────────────────────────────────────────────────────

SUPERSAMPLE = 2


def valid_tile(z: int, x: int, y: int) -> bool:
    return trek.valid_tile(z, x, y, MAX_ZOOM)


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장(Trek 과 같다) — 256 px 투명 PNG."""
    if layer not in LAYERS:
        raise MoonMapError("원도 레이어가 아니다")
    w, s, e, n = trek.tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    conn = _conn()
    pad = 3 / k
    table = "units" if layer == "orig-units" else "lines"
    for shift in (0.0, -360.0, 360.0):
        # 경도를 이어 적었으므로 네모를 ±360 옮겨 한 번 더 묻는다
        qw, qe = w + shift, e + shift
        order = "ORDER BY t.draw, t.id" if table == "units" else "ORDER BY t.id"
        cols = "t.color" if table == "units" else "t.kind"
        rows = conn.execute(
            f"SELECT t.id, r.minx, r.maxx, r.miny, r.maxy, {cols}, t.geom FROM {table}_rtree r "
            f"JOIN {table} t ON t.id = r.id WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ? "
            f"{order}", (qw - pad, qe + pad, s - pad, n + pad)).fetchall()
        tr = (qw, n, k, k)
        for _, x0, x1, y0, y1, style, blob in rows:
            size_px = max(x1 - x0, y1 - y0) * k
            if table == "units":
                color = _hex(style)
                if size_px < 1.5 * ss:
                    cx, cy = ((x0 + x1) / 2 - qw) * k, (n - (y0 + y1) / 2) * k
                    draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=color)
                    continue
                # 가까이서는 단위 사이에 가는 선을 둔다 — 같은 색이 맞닿아도 경계가 보이게
                outline = (0, 0, 0, 90) if z >= 5 else None
                rule = {"fill": color, "outline": outline, "width": 1}
                for rings in unpack(blob):
                    geomap._fill_polygon(img, draw, [list(r) for r in rings], rule, tr, size_px, ss)
            else:
                rule = line_style(style)
                strokes = [{"color": _hex(rule["color"]), "width": rule.get("width", 1),
                            "dash": rule.get("dash")}]
                for parts in unpack(blob):
                    for flat in parts:
                        for run in geomap._clip_runs(geomap._to_px(list(flat), tr, size_px), size, size, 8 * ss):
                            geomap._stroke(draw, run, strokes, ss)
    out = img.resize((TILE, TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def render_polar_tile(layer: str, pole: str, z: int, x: int, y: int) -> bytes:
    """극 격자 한 장(`trek.polar_tile_bbox`, 052) — 256 px 투명 PNG.

    경위도로 옮겨 둔 모양을 다시 극 평사도법으로 옮겨 그린다. 극을 두른 고리는 `_unwrap` 이 극점으로
    닫아 두었으므로 옮기면 극점(0, 0)을 지나 제대로 닫힌다. 묻는 네모는 타일 둘레를 경위도로 되짚은
    것이다 — 극을 품거나 날짜 변경선에 걸치면 경도를 다 묻는다."""
    if layer not in LAYERS:
        raise MoonMapError("원도 레이어가 아니다")
    w, s, e, n = trek.polar_tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    # 둘레를 경위도로 — 한 변에 16 점
    edge = [(w + (e - w) * i / 16, n) for i in range(17)] + [(w + (e - w) * i / 16, s) for i in range(17)]
    edge += [(w, s + (n - s) * i / 16) for i in range(17)] + [(e, s + (n - s) * i / 16) for i in range(17)]
    lls = [trek.polar_to_lonlat(px, py, pole) for px, py in edge]
    lats = [ll[1] for ll in lls]
    inside_pole = w <= 0 <= e and s <= 0 <= n
    lat_lo, lat_hi = (min(lats), 90.0) if pole == "n" else (-90.0, max(lats))
    lons = [ll[0] for ll in lls]
    # 날짜 변경선(극 아래로 뻗는 반직선)에 걸치거나 극을 품으면 경도를 다 묻는다
    crosses = inside_pole or (w <= 0 <= e and (n > 0 if pole == "n" else s < 0))
    lon_lo, lon_hi = (-180.0, 180.0) if crosses else (min(lons), max(lons))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    conn = _conn()
    table = "units" if layer == "orig-units" else "lines"
    cols = "t.color, t.draw" if table == "units" else "t.kind, 0"
    seen = set()
    tr = (w, n, k, k)

    def project(flat):
        out = []
        for i in range(0, len(flat), 2):
            out += trek.lonlat_to_polar(flat[i], flat[i + 1], pole)
        return out

    rows = []
    for shift in (0.0, -360.0, 360.0):
        rows += conn.execute(
            f"SELECT t.id, {cols}, t.geom FROM {table}_rtree r "
            f"JOIN {table} t ON t.id = r.id WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?",
            (lon_lo + shift, lon_hi + shift, lat_lo, lat_hi)).fetchall()
    rows.sort(key=lambda row: (row[2], row[0]))          # 세 번 물은 것을 그리는 차례(원도, 번호)로
    for row_id, style, _, blob in rows:
        if row_id in seen:
            continue
        seen.add(row_id)
        parts = [[project(list(r)) for r in rings] for rings in unpack(blob)]
        xs = [v for rings in parts for r in rings for v in r[0::2]]
        ys = [v for rings in parts for r in rings for v in r[1::2]]
        if not xs or max(xs) < w or min(xs) > e or max(ys) < s or min(ys) > n:
            continue
        size_px = max(max(xs) - min(xs), max(ys) - min(ys)) * k
        if table == "units":
            color = _hex(style)
            if size_px < 1.5 * ss:
                cx, cy = ((min(xs) + max(xs)) / 2 - w) * k, (n - (min(ys) + max(ys)) / 2) * k
                draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=color)
                continue
            outline = (0, 0, 0, 90) if z >= 3 else None
            rule = {"fill": color, "outline": outline, "width": 1}
            for rings in parts:
                geomap._fill_polygon(img, draw, rings, rule, tr, size_px, ss)
        else:
            rule = line_style(style)
            strokes = [{"color": _hex(rule["color"]), "width": rule.get("width", 1), "dash": rule.get("dash")}]
            for lines in parts:
                for flat in lines:
                    for run in geomap._clip_runs(geomap._to_px(flat, tr, size_px), size, size, 8 * ss):
                        geomap._stroke(draw, run, strokes, ss)
    out = img.resize((TILE, TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# ── 속성 ────────────────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 원도 단위. 겹치는 곳은 위에 그린 것(적도 쪽)이 이긴다."""
    conn = _conn()
    hits = []
    for shift in (0.0, -360.0, 360.0):
        x = lon + shift
        for row in conn.execute(
                "SELECT t.id, t.map, t.draw, t.symbol, t.name, t.grp, t.epoch, t.descr, t.color, t.geom "
                "FROM units_rtree r JOIN units t ON t.id = r.id "
                "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?", (x, x, lat, lat)):
            if any(geomap.polygon_contains([list(r) for r in rings], x, lat) for rings in unpack(row[9])):
                hits.append(row)
    if not hits:
        return None
    _, map_id, _, symbol, name, grp, epoch, descr, color, _ = max(hits, key=lambda r: (r[2], r[0]))
    spec = MAPS[map_id]
    return {"map": map_id, "citation": f"{map_id} · {spec['by']} ({spec['year']})", "map_ko": spec["ko"],
            "title": spec["title"], "unit": symbol, "name": name, "group": grp, "epoch": epoch,
            "description": descr, "color": color}


def legend(lang: str = "ko") -> dict:
    s = styles()
    return {
        "units": [{"color": c["color"], "label": c["en"] if lang == "en" else c["ko"]} for c in s["categories"]],
        "lines": [{"color": r["color"], "dash": bool(r.get("dash")), "label": r["en"] if lang == "en" else r["ko"]}
                  for r in s["lines"]],
    }
