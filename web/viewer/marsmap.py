"""USGS 화성 옛 지질도·지역 지질도 — 우리 디스크의 파일을 읽어 화성 경위도·극 타일을 굽는다 (devlog 068). 문이 아니다.

달 원도(039, `moonmap.py`)의 짝이다. 화면이 지금 쓰는 전 지구 지질도(SIM 3292, 2014, Trek)와 따로, USGS 가 옛
PIGWAD 자리(`asc-pds-services` 의 `pigpen/mars/geology/`)에 둔 GIS 묶음을 굽는다. Trek 은 이것들을 주지 않는다.

| 판 | 덮는 곳 | 축척 | 그리는 차례 |
|---|---|---|---|
| I-1802-A·B·C (1986–87) | 전 지구 — 서쪽 적도·동쪽 적도·극 세 장을 Skinner 외(2006)가 이었다 | 1:1500만 | 맨 아래 |
| SIM 2888 (2005) | 북부 평원 (위도 30°N 남짓 위) | 1:1500만 | 그 위 |
| I-2650 (2001) | 타우마시아 | 1:500만 | 그 위 |
| MTM 지역도 열하나 (1980–90 년대) | 망갈라·카세이·마하 계곡, 올림푸스 몬스, 아폴리나리스 | 1:50만 남짓 | 맨 위 |

**좁은 판이 넓은 판 위에 그려진다** — 겹친 곳에서는 더 자세한 것이 보이고, 누르면 맨 위의 판을 읽는다.

**한 번 굽고(`manage.py build_mars_originals`) 그 뒤로는 sqlite 한 장을 읽는다.** 짜임은 달 원도와 같다 —
고리를 `moonmap.pack` 으로 담고 R*Tree 를 딸린다. 굽는 도구(`moonmap` 의 담기·선 읽기, `geomap` 의 칠하기)는
빌려 쓰고 고치지 않는다. 판을 더할 때는 `MAPS` 에 한 줄과 읽는 함수 하나를 더한다.

- **시대** — I-2650 만 시대 열이 있다. 나머지는 단위 기호의 앞머리가 시대다: 첫 글자(A·H·N)가 시대, 둘째 글자가
  더 오래된 시대면 걸친 것이다(`HNu` 헤스페리아기–노아키스기). SIM 2888 은 둘째 글자가 지형구(province)라
  (`HAa` = 헤스페리아기·알바 지형구) 거꾸로 선 쌍(`HA`)은 걸친 것으로 읽지 않는다. 앞머리가 없는 크레이터 물질(`c`·`s`)은
  시대를 매기지 않는다
- **색** — USGS 가 둔 색표다. I-1802·SIM 2888 은 RGB 표(csv), I-2650 은 ArcView 범례(.avl)에서 뽑았다
  (`data/mars_original_styles.json`). MTM 지역도에는 색표가 없다 — 같은 기호가 I-1802·I-2650·SIM 2888 에
  있으면 그 색, 없으면 시대의 색에 기호로 흔든 색이다
- **구조선** — 판마다 갈래 이름이 다르다. 그라벤·주름 능선·수로·급사면·칼데라 다섯 갈래로 모았다(`LINE_KINDS`).
  MTM 지역도의 구조선은 숫자 부호뿐이고 그 뜻(범례)이 파일에 없어 넣지 않았다
- **뺀 것** — I-2001(올림푸스 절벽)은 경계선만 있고 다각형이 없다. 크리세 평원(1995)은 단위가 번호뿐("Chryse
  unit 4")이다. SIM 3177 은 1.9 GB 다
- 어느 장(A·B·C)에서 왔는지는 I-1802 의 속성에 없다. 누른 자리로 가른다 — 위도 57° 너머 C, 서경 A, 동경 B

그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import colorsys
import csv
import hashlib
import io
import json
import logging
import re
import sqlite3
import threading
import zipfile
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import geo3al, geomap, moonmap, trek

log = logging.getLogger(__name__)

RENDERER = "3"
FILENAME = "mars_originals.sqlite"
TILE = 256
SUPERSAMPLE = 2
LAYERS = ("orig-units", "orig-lines")

#: 판 — 그리는 차례(아래부터). `files` 는 묶음 속 셰이프파일 이름(소문자, 확장자 없이)의 끝
MAPS = {
    "I-1802": {"ko": "화성 전 지구 (바이킹)", "by": "Scott & Tanaka 1986; Greeley & Guest 1987; Tanaka & Scott 1987 "
               "(digital: Skinner et al. 2006)", "scale": "1:15,000,000",
               "files": {"units": "i1802abc_mars2000_sphere/geo_units_oc_dd",
                         "lines": ["i1802abc_mars2000_sphere/geo_structure_oc_dd"]},
               "sheets": {"A": "서쪽 적도", "B": "동쪽 적도", "C": "극지"}},
    "SIM 2888": {"ko": "북부 평원", "by": "Tanaka, Skinner & Hare 2005", "scale": "1:15,000,000",
                 "files": {"units": "sim2888_mars2000_sphere/sim2888_geology_ocentric",
                           "lines": ["sim2888_mars2000_sphere/sim2888_grabens_ocentric",
                                     "sim2888_mars2000_sphere/sim2888_ridges_ocentric",
                                     "sim2888_mars2000_sphere/sim2888_scarps_ocentric",
                                     "sim2888_mars2000_sphere/sim2888_channels_ocentric"]}},
    "I-2650": {"ko": "타우마시아", "by": "Dohm, Tanaka & Hare 2001", "scale": "1:5,000,000", "lines_from": 5,
               "files": {"units": "i-2650_dd/i-2650_geo",
                         "lines": ["i-2650_dd/i-2650_fg_riff", "i-2650_dd/i-2650_ms", "i-2650_dd/i-2650_ch",
                                   "i-2650_dd/i-2650_depr"]}},
}
#: `lines_from` — 이 줌(경위도 격자)부터 구조선을 그린다. I-2650 은 단층·그라벤이 14 000 개라 멀리서는 새까맣게
#: 뭉친다. 극 격자는 한 장이 두 배 남짓 넓어 두 줌 낮춰 센다
#: MTM 지역도 — (판, 제목). 제목은 셰이프파일에 딸린 메타데이터에서 옮겼다. 셋(1696·1697·1962)은 메타데이터가
#: 다른 판의 것을 베껴 두어 MTM 사각형 이름만 적었다
_MTM = (
    ("I-1696", "MTM −10147, Mangala Valles"), ("I-1697", "MTM −15147, Mangala Valles"),
    ("I-1962", "MTM −05147, Mangala Valles"), ("I-2087", "MTM −08157, West Mangala Valles"),
    ("I-2107", "MTM 25072, North Kasei Valles"), ("I-2203", "MTM 20057, Maja Valles"),
    ("I-2208", "MTM 25057·25052, Kasei Valles"), ("I-2294", "MTM −05152·−10152, Mangala Valles"),
    ("I-2310", "MTM −20147, Mangala Valles"), ("I-2327", "Olympus Mons region"),
    ("I-2351", "Apollinaris Patera region"),
)
for _id, _title in _MTM:
    _stem = _id.lower()
    MAPS[_id] = {"ko": _title, "by": f"USGS {_id}", "scale": "", "mtm": True,
                 "files": {"units": f"{_stem}_g_dd", "lines": []}}

_PERIODS = {"A": "Amazonian", "H": "Hesperian", "N": "Noachian"}
_ORDER = "AHN"                                     # 젊은 것부터

#: 구조선 갈래 — 판마다 다른 이름을 다섯으로 모은다. (판, 파일 이름 끝, 속성의 값) → 갈래
LINE_KINDS = ("graben", "ridge", "channel", "scarp", "caldera")


def line_kind(map_id: str, stem: str, row: dict) -> str:
    """판·파일·속성 → 우리 갈래. 모르는 것은 ""(그리지 않는다)."""
    value = " ".join(str(v) for k, v in (row or {}).items()
                     if k.upper() in ("SRUCTYPE", "TYPE", "DESC")).lower()
    if stem.endswith("channels_ocentric") or stem.endswith("i-2650_ch") or "channel" in value:
        return "channel"
    if stem.endswith("grabens_ocentric") or "graben" in value or "fault" in value:
        return "graben"
    if stem.endswith("ridges_ocentric") or "ridge" in value:
        return "ridge"
    if stem.endswith("i-2650_depr") or "caldera" in value or "depression" in value:
        return "caldera"
    if "scarp" in value or stem.endswith("scarps_ocentric"):
        return "scarp"
    return ""


class MarsMapError(RuntimeError):
    pass


# ── 자리 ────────────────────────────────────────────────────────────

def data_file() -> Path:
    return Path(settings.MARS_DIR) / FILENAME


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
            raise MarsMapError("옛 지질도 파일이 없다 — manage.py build_mars_originals 를 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 색·이름 ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def styles() -> dict:
    return json.loads(Path(settings.MARS_ORIGINAL_STYLES_FILE).read_text(encoding="utf-8"))


def unit_color(map_id: str, symbol: str, age: str = "") -> str:
    """판의 색표 → (MTM 이면) 다른 판의 같은 기호 → 시대의 색을 기호로 흔든 것."""
    tables = styles()["units"]
    own = tables.get(map_id, {})
    if symbol in own:
        return own[symbol]
    if MAPS.get(map_id, {}).get("mtm"):
        for other in ("I-1802", "I-2650", "SIM 2888"):
            if symbol in tables.get(other, {}):
                return tables[other][symbol]
    return _age_color(symbol, age)


def _age_color(symbol: str, age: str) -> str:
    hues = {"Amazonian": 0.06, "Hesperian": 0.14, "Noachian": 0.80}
    period = trek.mars_period(age)
    digest = hashlib.md5(symbol.encode()).digest()
    if period not in hues:
        return "#%02x%02x%02x" % ((170 + digest[0] % 40,) * 3)
    h = hues[period] + (digest[0] / 255 - 0.5) * 0.08
    r, g, b = colorsys.hls_to_rgb(h % 1, 0.55 + (digest[1] / 255 - 0.5) * 0.2, 0.55 + digest[2] / 255 * 0.3)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def line_style(kind: str) -> dict:
    for rule in styles()["lines"]:
        if rule["key"] == kind:
            return rule
    return styles()["lines"][-1]


def age_of(symbol: str) -> str:
    """단위 기호 앞머리 → 시대. 첫 글자가 시대, 둘째 글자가 더 오래된 시대면 걸친 것.
    `HNu` → "Hesperian and Noachian", `Api` → "Amazonian", `HAa`(SIM 2888, 알바 지형구) → "Hesperian", `cs` → ""."""
    if not symbol or symbol[0] not in _PERIODS:
        return ""
    head = symbol[0]
    if len(symbol) > 1 and symbol[1] in _PERIODS and _ORDER.index(symbol[1]) > _ORDER.index(head):
        head += symbol[1]
    return " and ".join(_PERIODS[c] for c in head)


def sheet_of(map_id: str, lon: float, lat: float) -> str:
    if map_id != "I-1802":
        return ""
    return "C" if abs(lat) >= 57 else "A" if lon < 0 else "B"


def read_avl_colors(text: str) -> dict:
    """ArcView 범례(.avl) → {라벨: "#rrggbb"}. 범례의 `Symbol:` 과 `Class:` 를 차례대로 짝짓는다."""
    objs = {m.group(1): m.group(2) for m in re.finditer(r"\((\w+\.\d+)\n(.*?)\n\)", text, re.S)}
    by_num = {k.split(".")[1]: (k.split(".")[0], v) for k, v in objs.items()}
    legend = next((v for k, v in objs.items() if k.startswith("Legend.")), "")
    symbols = re.findall(r"Symbol:\s+(\d+)", legend)
    classes = re.findall(r"Class:\s+(\d+)", legend)
    out = {}
    for sym, cls in zip(symbols, classes):
        body = by_num.get(sym, ("", ""))[1]
        color = re.search(r"\bColor:\s+(\d+)", body)
        label = re.search(r'Label:\s+"([^"]*)"', by_num.get(cls, ("", ""))[1])
        if not (color and label):
            continue
        tclr = by_num.get(color.group(1), ("", ""))[1]
        rgb = [re.search(rf"{c}:\s+0x([0-9a-f]+)", tclr) for c in ("Red", "Green", "Blue")]
        out[label.group(1)] = "#%02x%02x%02x" % tuple(int(m.group(1), 16) >> 8 if m else 0 for m in rgb)
    return out


def read_rgb_csv(text: str) -> dict:
    return {r["Unit"].strip(): "#%02x%02x%02x" % (int(r["R"]), int(r["G"]), int(r["B"]))
            for r in csv.DictReader(io.StringIO(text))}


# ── 굽기 (한 번) ────────────────────────────────────────────────────

def _unit_fields(map_id: str, row: dict) -> tuple:
    """(기호, 이름, 시대, 덧말) — 판마다 열이 다르다."""
    if map_id == "I-1802":
        symbol, name, note = row.get("UnitSymbol"), row.get("UnitName"), ""
    elif map_id == "SIM 2888":
        symbol, name, note = row.get("unit_symbo"), row.get("unit_name"), row.get("geologic_p")
    else:                                            # I-2650 과 MTM — 기호뿐(I-2650 은 시대 열이 있다)
        symbol, name, note = row.get("UNAME"), "", ""
    symbol = (symbol or "").strip()
    age = (row.get("AGE") or "").strip() if map_id == "I-2650" else age_of(symbol)
    return symbol, (name or "").strip(), age, (note or "").strip()


def build(sources, out_path) -> dict:
    """USGS 묶음들(zip 이나 푼 폴더) → sqlite. `manage.py build_mars_originals` 가 부른다.
    없는 판은 건너뛴다 — 적어도 I-1802 는 있어야 한다."""
    names = {}
    for source in ([sources] if isinstance(sources, (str, Path)) else sources):
        src = Path(source)
        if src.is_file():
            zf = zipfile.ZipFile(src)
            for n in zf.namelist():
                names[n.lower()] = (zf, n)
        else:
            for p in src.rglob("*"):
                names[str(p.relative_to(src)).lower()] = (None, p)

    def read(entry):
        zf, n = entry
        return zf.read(n) if zf else Path(n).read_bytes()

    def find(stem, suffix):
        for low, entry in names.items():
            if low.endswith(stem + suffix):
                return entry
        return None

    out = Path(out_path)
    tmp = out.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, map TEXT, draw INTEGER, symbol TEXT, name TEXT, age TEXT,
                            note TEXT, color TEXT, geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, map TEXT, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    counts = {}
    for draw, (map_id, spec) in enumerate(MAPS.items()):
        shp, dbf = find(spec["files"]["units"], ".shp"), find(spec["files"]["units"], ".dbf")
        if not shp or not dbf:
            if map_id == "I-1802":
                raise MarsMapError("I-1802 의 지질 셰이프파일이 없다")
            continue
        shapes, rows = geo3al.read_polygons(read(shp)), geo3al.read_dbf(read(dbf))
        if len(shapes) != len(rows):
            raise MarsMapError(f"{map_id}: 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
        n = 0
        for rings, row in zip(shapes, rows):
            if row is None or not rings:
                continue
            polygons = [[moonmap._unwrap(r) for r in poly] for poly in geo3al.group_rings(rings)]
            polygons = [p for p in polygons if p and len(p[0]) >= 6]
            symbol, name, age, note = _unit_fields(map_id, row)
            if not polygons or not symbol:
                continue
            cur = db.execute("INSERT INTO units (map, draw, symbol, name, age, note, color, geom) "
                             "VALUES (?,?,?,?,?,?,?,?)",
                             (map_id, draw, symbol, name, age, note, unit_color(map_id, symbol, age),
                              moonmap.pack(polygons)))
            db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox(polygons)))
            n += 1
        counts[map_id] = n
        for stem in spec["files"]["lines"]:
            lshp, ldbf = find(stem, ".shp"), find(stem, ".dbf")
            if not (lshp and ldbf):
                continue
            for parts, row in zip(moonmap._read_lines(read(lshp)), geo3al.read_dbf(read(ldbf))):
                kind = line_kind(map_id, stem, row)
                flat = [moonmap._unwrap(part) for part in parts if len(part) >= 2]
                if not flat or not kind:
                    continue
                cur = db.execute("INSERT INTO lines (map, kind, geom) VALUES (?,?,?)",
                                 (map_id, kind, moonmap.pack([flat])))
                db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox([flat])))
    db.execute("INSERT INTO meta VALUES ('renderer', ?)", (RENDERER,))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    return counts


# ── 그리기 ──────────────────────────────────────────────────────────

def _hex(value: str) -> tuple:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def _strokes(kind: str) -> list:
    rule = line_style(kind)
    return [{"color": _hex(rule["color"]), "width": rule.get("width", 1), "dash": rule.get("dash")}]


def _draw_rows(img, draw, rows, project, tr, size, ss, outline):
    """행(모양)마다 칠하거나 긋는다. `project` 는 경위도 납작한 목록 → 타일 평면 납작한 목록."""
    w, n, k, _ = tr
    for table, style, blob in rows:
        parts = [[project(list(r)) for r in rings] for rings in moonmap.unpack(blob)]
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
            rule = {"fill": color, "outline": (0, 0, 0, 90) if outline else None, "width": 1}
            for rings in parts:
                geomap._fill_polygon(img, draw, rings, rule, tr, size_px, ss)
        else:
            for lines in parts:
                for flat in lines:
                    for run in geomap._clip_runs(geomap._to_px(flat, tr, size_px), size, size, 8 * ss):
                        geomap._stroke(draw, run, _strokes(style), ss)


def _hidden_maps(layer: str, z: int) -> set:
    """이 줌에서 구조선을 그리지 않는 판."""
    if layer != "orig-lines":
        return set()
    return {m for m, spec in MAPS.items() if z < spec.get("lines_from", 0)}


def _select(layer, w, e, s, n, hide=frozenset()):
    """네모에 걸친 모양 `[(경도 옮김, (갈래, 색·종류, 모양))]` — 그리는 차례(판, 번호)로.
    경도를 이어 적었으므로 네모를 ±360 옮겨 한 번 더 묻는다(039 와 같다)."""
    table = "units" if layer == "orig-units" else "lines"
    style, draw = ("t.color", "t.draw") if table == "units" else ("t.kind", "0")
    found = {}
    for shift in (0.0, -360.0, 360.0):
        for row_id, st, blob, order, map_id in _conn().execute(
                f"SELECT t.id, {style}, t.geom, {draw}, t.map FROM {table}_rtree r JOIN {table} t ON t.id = r.id "
                f"WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?", (w + shift, e + shift, s, n)):
            if map_id not in hide:
                found.setdefault(row_id, (order, shift, (table, st, blob)))
    return [(shift, row) for _, (order, shift, row) in sorted(found.items(), key=lambda kv: (kv[1][0], kv[0]))]


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.resize((TILE, TILE), Image.Resampling.BOX).save(buf, format="PNG")
    return buf.getvalue()


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """화성 경위도 격자 한 장(Trek 과 같다) — 256 px 투명 PNG."""
    if layer not in LAYERS:
        raise MarsMapError("옛 지질도 레이어가 아니다")
    w, s, e, n = trek.tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    pad = 3 / k
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for shift, row in _select(layer, w - pad, e + pad, s - pad, n + pad, _hidden_maps(layer, z)):
        # 경도를 이어 적었으므로 ±360 옮겨 물은 것은 그만큼 되돌려 그린다
        project = (lambda flat, sh=shift: [v - sh if i % 2 == 0 else v for i, v in enumerate(flat)])
        _draw_rows(img, draw, [row], project, (w, n, k, k), size, ss, z >= 5)
    return _png(img)


def render_polar_tile(layer: str, pole: str, z: int, x: int, y: int) -> bytes:
    """화성 극 격자 한 장(`trek.mars_polar_tile_bbox`, 065) — 경위도의 모양을 극 평사도법으로 옮겨 그린다."""
    if layer not in LAYERS or pole not in ("n", "s"):
        raise MarsMapError("옛 지질도 레이어가 아니다")
    w, s, e, n = trek.mars_polar_tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    edge = [(w + (e - w) * i / 16, yy) for i in range(17) for yy in (s, n)] + \
           [(xx, s + (n - s) * i / 16) for i in range(17) for xx in (w, e)]
    lls = [trek.mars_polar_to_lonlat(px, py, pole) for px, py in edge]
    lats = [ll[1] for ll in lls]
    inside = w <= 0 <= e and s <= 0 <= n
    crosses = inside or (w <= 0 <= e and (n > 0 if pole == "n" else s < 0))
    lon_lo, lon_hi = (-180.0, 180.0) if crosses else (min(ll[0] for ll in lls), max(ll[0] for ll in lls))
    lat_lo, lat_hi = (min(lats), 90.0) if pole == "n" else (-90.0, max(lats))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def project(flat):
        # 경위도의 곧은 변은 극 평면에서 굽는다 — 1° 넘는 변은 쪼개 옮긴다(위도선을 따라 한 바퀴 도는 변이
        # 점 둘뿐이면 고리가 선으로 찌그러진다)
        out = []
        for i in range(0, len(flat), 2):
            lon, lat = flat[i], flat[i + 1]
            if i:
                plon, plat = flat[i - 2], flat[i - 1]
                steps = int(max(abs(lon - plon), abs(lat - plat)))
                for k in range(1, steps):
                    t = k / steps
                    out += trek.mars_lonlat_to_polar(plon + (lon - plon) * t, plat + (lat - plat) * t, pole)
            out += trek.mars_lonlat_to_polar(lon, lat, pole)
        return out

    for _, row in _select(layer, lon_lo, lon_hi, lat_lo, lat_hi, _hidden_maps(layer, z + 2)):
        _draw_rows(img, draw, [row], project, (w, n, k, k), size, ss, z >= 3)
    return _png(img)


# ── 속성·범례 ───────────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 단위. 겹치면 위에 그린 판(더 좁고 자세한 것)이 이긴다."""
    hits = []
    for shift in (0.0, -360.0, 360.0):
        x = lon + shift
        for row in _conn().execute(
                "SELECT t.id, t.map, t.draw, t.symbol, t.name, t.age, t.note, t.color, t.geom FROM units_rtree r "
                "JOIN units t ON t.id = r.id WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
                (x, x, lat, lat)):
            if any(geomap.polygon_contains([list(r) for r in rings], x, lat) for rings in moonmap.unpack(row[8])):
                hits.append(row)
    if not hits:
        return None
    _, map_id, _, symbol, name, age, note, color, _ = max(hits, key=lambda r: (r[2], r[0]))
    spec, sheet = MAPS[map_id], sheet_of(map_id, lon, lat)
    return {"map": map_id + (f"-{sheet}" if sheet else ""),
            "map_ko": spec.get("sheets", {}).get(sheet, "") or spec["ko"],
            "citation": spec["by"], "scale": spec["scale"], "unit": symbol, "name": name, "age": age,
            "note": note, "color": color}


def legend(lang: str = "ko") -> dict:
    """단위(기호·이름·색·시대 — 이름은 원문 값이라 옮기지 않는다)와 구조선 갈래.
    같은 기호가 여러 판에 있으면 이름이 있는 것(넓은 판)을 앞세워 하나만 싣는다."""
    try:
        rows = _conn().execute("SELECT symbol, name, age, color, draw FROM units GROUP BY map, symbol "
                               "ORDER BY symbol, name = '', draw").fetchall()
    except (MarsMapError, sqlite3.Error):
        rows = []
    units, seen = [], set()
    for symbol, name, age, color, _ in rows:
        if symbol in seen:
            continue
        seen.add(symbol)
        period = trek.mars_period(age)
        units.append({"unit": symbol, "label": name or symbol, "color": color,
                      "age": (period if lang == "en" else trek.MARS_PERIODS_KO.get(period, "")) if period else ""})
    lines = [{"color": r["color"], "dash": bool(r.get("dash")), "label": r["en"] if lang == "en" else r["ko"]}
             for r in styles()["lines"]]
    return {"units": units, "lines": lines}
