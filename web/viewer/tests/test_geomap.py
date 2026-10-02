"""남극 지질도 — GeoMAP 을 우리가 그리는 문 (geomap.py).

NAS 의 GeoMAP 파일에 기대지 않는다. 시험마다 `sqlite3` 로 작은 GeoPackage 를
만들어 쓴다 — 표 이름·열·R*Tree 는 v2022-08 과 같은 꼴이다.
"""
import io
import sqlite3
import struct
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import geomap, i18n
from viewer.management.commands import geomap_styles
from viewer.models import Layer, LayerGroup

# ── 기하를 만드는 손 ─────────────────────────────────────────────────


def ring(*pts):
    return struct.pack("<I", len(pts)) + b"".join(struct.pack("<2d", *p) for p in pts)


def wkb_polygon(*rings):
    return struct.pack("<BII", 1, 3, len(rings)) + b"".join(ring(*r) for r in rings)


def wkb_multipolygon(*polys):
    return struct.pack("<BII", 1, 6, len(polys)) + b"".join(wkb_polygon(*p) for p in polys)


def wkb_line(*pts):
    return struct.pack("<BI", 1, 2) + ring(*pts)


def wkb_multiline(*lines):
    return struct.pack("<BII", 1, 5, len(lines)) + b"".join(wkb_line(*l) for l in lines)


def gpkg(wkb, envelope=None):
    """GeoPackage 머리(GP, 판 0, 깃발, SRS) + WKB."""
    flags = 0b1 | ((1 << 1) if envelope else 0)
    head = b"GP" + bytes([0, flags]) + struct.pack("<i", 3031)
    if envelope:
        head += struct.pack("<4d", *envelope)
    return head + wkb


def square(cx, cy, half):
    return [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half),
            (cx - half, cy + half), (cx - half, cy - half)]


# ── 작은 GeoPackage ──────────────────────────────────────────────────

UNITS = "ATA_GeoMAP_geological_units_v2099_01"
FAULTS = "ATA_GeoMAP_faults_v2099_01"
SOURCES = "ATA_GeoMAP_sources_v2099_01"
#: 세종기지 둘레 (3031)
SX, SY = geomap.lonlat_to_3031(-58.78, -62.22)


def build(root: Path) -> Path:
    path = root / "ATA_SCAR_GeoMAP_Geology_v2099_01.gpkg"
    c = sqlite3.connect(path)
    c.executescript(f"""
        CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, min_x REAL, min_y REAL,
                                    max_x REAL, max_y REAL);
        CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT);
        CREATE TABLE {UNITS} (fid INTEGER PRIMARY KEY, geom BLOB, NAME TEXT, MAPSYMBOL TEXT,
            DESCR TEXT, LITHOLOGY TEXT, SIMPCODE INTEGER, SIMPDESC TEXT, GEOLHIST TEXT,
            ABSMIN_MA REAL, ABSMAX_MA REAL, POLYGTYPE TEXT, STRATRANK TEXT, TECTPROV TEXT,
            REGION TEXT, CONFIDENCE TEXT, OBSMETHOD TEXT, POSACC_M INTEGER, RESSCALE INTEGER,
            SOURCE TEXT, LITHCODE TEXT, Shape_Area REAL);
        CREATE VIRTUAL TABLE rtree_{UNITS}_geom USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE {FAULTS} (fid INTEGER PRIMARY KEY, geom BLOB, NAME TEXT, TYPENAME TEXT,
            EXPOSURE TEXT, ACCURACY TEXT, SOURCE TEXT);
        CREATE VIRTUAL TABLE rtree_{FAULTS}_geom USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE {SOURCES} (fid INTEGER PRIMARY KEY, geom BLOB, IDENTIFIER TEXT,
            AUTHORS TEXT, YEAR INTEGER, TITLE TEXT, PUBLICATION TEXT);
    """)
    for table in (UNITS, FAULTS, SOURCES):
        c.execute("INSERT INTO gpkg_contents VALUES (?, 'features', ?, ?, ?, ?)",
                  (table, SX - 50000, SY - 50000, SX + 50000, SY + 50000))
        c.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom')", (table,))

    def unit(fid, rings_, simpcode, name, area):
        xs = [p[0] for p in rings_[0]]
        ys = [p[1] for p in rings_[0]]
        c.execute(f"INSERT INTO {UNITS} (fid, geom, NAME, MAPSYMBOL, SIMPCODE, GEOLHIST, "
                  "ABSMIN_MA, ABSMAX_MA, POLYGTYPE, RESSCALE, SOURCE, POSACC_M, Shape_Area) "
                  "VALUES (?, ?, ?, 'Czw', ?, 'Paleocene to Early Miocene', 5.3, 66.0, 'rock', "
                  "250000, 'Fleming & Thomson 1979', 99, ?)",
                  (fid, gpkg(wkb_multipolygon(rings_)), name, simpcode, area))
        c.execute(f"INSERT INTO rtree_{UNITS}_geom VALUES (?, ?, ?, ?, ?)",
                  (fid, min(xs), max(xs), min(ys), max(ys)))

    # 1: 가운데 구멍이 난 큰 네모 (화산암, SIMPCODE 31 = 빨강)
    unit(1, [square(SX, SY, 10000), square(SX, SY, 3000)], 31, "Barton volcanics", 3.6e8)
    # 2: 구멍 안의 작은 네모 (관입암, SIMPCODE 44)
    unit(2, [square(SX, SY, 1000)], 44, "Barton granodiorite", 4e6)
    # 3: 스타일에 없는 갈래 — 그리지도 묻지도 않는다
    unit(3, [square(SX + 30000, SY, 2000)], 999, "unstyled", 1.6e7)

    c.execute(f"INSERT INTO {FAULTS} VALUES (1, ?, 'Test fault', 'fault', 'exposed', 'accurate', '')",
              (gpkg(wkb_multiline([(SX - 20000, SY + 5000), (SX + 20000, SY + 5000)])),))
    c.execute(f"INSERT INTO rtree_{FAULTS}_geom VALUES (1, ?, ?, ?, ?)",
              (SX - 20000, SX + 20000, SY + 5000, SY + 5000))
    c.execute(f"INSERT INTO {SOURCES} VALUES (1, NULL, 'Fleming & Thomson 1979', "
              "'Fleming E.A., Thomson J.W.', 1979, 'Northern Graham Land', 'BAS 500G Sheet 2')")
    c.commit()
    c.close()
    return path


class WithData:
    """시험마다 새 GeoPackage 를 만든다."""

    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp(prefix="gsm-geomap-"))
        build(self.dir)
        self.cache = tempfile.mkdtemp(prefix="gsm-geomap-cache-")
        patch = override_settings(GEOMAP_DIR=str(self.dir), TILE_CACHE_DIR=self.cache,
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)


# ── WKB ─────────────────────────────────────────────────────────────

class Wkb(SimpleTestCase):
    def test_구멍_난_다각형(self):
        kind, parts = geomap.parse_geometry(gpkg(wkb_polygon(square(0, 0, 2), square(0, 0, 1))))
        self.assertEqual(kind, "polygon")
        self.assertEqual(len(parts), 1)
        self.assertEqual(len(parts[0]), 2)                 # 바깥 + 구멍
        self.assertEqual(parts[0][0][:4], (-2.0, -2.0, 2.0, -2.0))

    def test_멀티폴리곤_envelope_를_건너뛴다(self):
        blob = gpkg(wkb_multipolygon([square(0, 0, 1)], [square(5, 5, 1)]), envelope=(-1, 6, -1, 6))
        kind, parts = geomap.parse_geometry(blob)
        self.assertEqual(kind, "polygon")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1][0][:2], (4.0, 4.0))

    def test_멀티라인(self):
        kind, parts = geomap.parse_geometry(gpkg(wkb_multiline([(0, 0), (1, 1)], [(2, 2), (3, 3), (4, 4)])))
        self.assertEqual(kind, "line")
        self.assertEqual(parts[1], (2.0, 2.0, 3.0, 3.0, 4.0, 4.0))

    def test_Z_는_버린다(self):
        # ISO WKB 의 LineString Z (1002)
        wkb = struct.pack("<BII", 1, 1002, 2) + struct.pack("<6d", 1, 2, 9, 3, 4, 9)
        kind, parts = geomap.parse_geometry(gpkg(wkb))
        self.assertEqual(parts, [(1.0, 2.0, 3.0, 4.0)])

    def test_큰_끝(self):
        wkb = struct.pack(">BI", 0, 1) + struct.pack(">2d", 7.5, -3.25)
        self.assertEqual(geomap.parse_geometry(gpkg(wkb)), ("point", [(7.5, -3.25)]))

    def test_빈_기하(self):
        blob = b"GP" + bytes([0, 0b10001]) + struct.pack("<i", 3031)
        self.assertEqual(geomap.parse_geometry(blob), (None, []))

    def test_GeoPackage_가_아니면_멈춘다(self):
        with self.assertRaises(geomap.GeomapError):
            geomap.parse_geometry(b"XX\x00\x01")


class PointInPolygon(SimpleTestCase):
    RINGS = [sum(square(0, 0, 10), ()), sum(square(0, 0, 3), ())]

    def test_안(self):
        self.assertTrue(geomap.polygon_contains(self.RINGS, 5, 5))

    def test_구멍_안은_밖이다(self):
        self.assertFalse(geomap.polygon_contains(self.RINGS, 0, 0))

    def test_밖(self):
        self.assertFalse(geomap.polygon_contains(self.RINGS, 11, 0))

    def test_오목한_다각형(self):
        u = sum([(0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10), (0, 0)], ())
        self.assertFalse(geomap.ring_contains(u, 5, 6))       # 오목한 틈
        self.assertTrue(geomap.ring_contains(u, 1, 6))

    def test_거리(self):
        self.assertEqual(geomap.distance("polygon", [self.RINGS], 5, 5), 0.0)
        self.assertAlmostEqual(geomap.distance("polygon", [self.RINGS], 13, 0), 3.0)
        self.assertAlmostEqual(geomap.distance("line", [(0.0, 0.0, 10.0, 0.0)], 5, 2), 2.0)


# ── 격자와 도법 ─────────────────────────────────────────────────────

class Grid(SimpleTestCase):
    """화면 쪽과 약속한 격자다. 바뀌면 이 시험이 먼저 깨져야 한다."""

    def test_z0_는_대륙_전체(self):
        self.assertEqual(geomap.tile_bbox(0, 0, 0),
                         (-3333134.0276, -3333134.0276, 3333134.0276, 3333134.0276))
        self.assertAlmostEqual(geomap.resolution(0), 6666268.0552 / 256)

    def test_y_는_위에서_아래로(self):
        min_x, min_y, max_x, max_y = geomap.tile_bbox(1, 0, 0)
        self.assertEqual((min_x, max_y), (-3333134.0276, 3333134.0276))
        self.assertAlmostEqual(min_y, 0.0, places=6)
        self.assertAlmostEqual(geomap.tile_bbox(1, 1, 1)[2], 3333134.0276)

    def test_해상도는_줌마다_반(self):
        self.assertAlmostEqual(geomap.resolution(5) * 2, geomap.resolution(4))

    def test_점이_드는_타일(self):
        for z in (0, 3, 9, 14):
            x, y = geomap.tile_of(z, SX, SY)
            b = geomap.tile_bbox(z, x, y)
            self.assertTrue(b[0] <= SX < b[2] and b[1] <= SY < b[3], z)

    def test_격자_밖(self):
        self.assertFalse(geomap.valid_tile(2, 4, 0))
        self.assertFalse(geomap.valid_tile(-1, 0, 0))
        self.assertTrue(geomap.valid_tile(2, 3, 3))


class Projection(SimpleTestCase):
    def test_EPSG_의_예제(self):
        """EPSG Guidance Note 7-2 의 극 평사도법 B 예제(표준위도 71°S, 원점 경도 70°E,
        75°S 120°E → E 7255380.79, N 7053389.56, 가짜 동·북 6 000 000)."""
        x, y = geomap.lonlat_to_3031(120 - 70, -75)
        self.assertAlmostEqual(x, 7255380.79 - 6e6, places=1)
        self.assertAlmostEqual(y, 7053389.56 - 6e6, places=1)

    def test_극점과_경도_0(self):
        self.assertEqual(geomap.lonlat_to_3031(0, -90), (0.0, 0.0))
        x, y = geomap.lonlat_to_3031(0, -71)
        self.assertAlmostEqual(x, 0)
        self.assertGreater(y, 0)                           # 경도 0 은 위쪽

    def test_되돌리기(self):
        for lon, lat in ((-58.78, -62.22), (164.23, -74.62), (-179.9, -85)):
            back = geomap.xy3031_to_lonlat(*geomap.lonlat_to_3031(lon, lat))
            self.assertAlmostEqual(back[0], lon, places=7)
            self.assertAlmostEqual(back[1], lat, places=7)


class ClickPoint(SimpleTestCase):
    def test_3031(self):
        x, y, tol = geomap.click_point({"crs": "EPSG:3031", "bbox": "0,0,256,256",
                                        "width": "256", "height": "256", "i": "10", "j": "20"})
        self.assertEqual((x, y), (10.5, 235.5))
        self.assertAlmostEqual(tol, geomap.TOLERANCE_PX)

    def test_4326_1_3_0_은_위도가_먼저(self):
        x, y, _ = geomap.click_point({"crs": "EPSG:4326", "version": "1.3.0",
                                      "bbox": "-62.3,-58.9,-62.1,-58.7",
                                      "width": "100", "height": "100", "i": "50", "j": "50"})
        lon, lat = geomap.xy3031_to_lonlat(x, y)
        self.assertAlmostEqual(lon, -58.799, places=2)
        self.assertAlmostEqual(lat, -62.201, places=2)

    def test_3857(self):
        from viewer import tilegrid
        mx, my = tilegrid.lonlat_to_3857(-58.78, -62.22)
        x, y, _ = geomap.click_point({"srs": "EPSG:3857", "bbox": f"{mx-50},{my-50},{mx+50},{my+50}",
                                      "width": "100", "height": "100", "x": "50", "y": "50"})
        self.assertAlmostEqual(x, SX, delta=5)
        self.assertAlmostEqual(y, SY, delta=5)

    def test_자리가_없으면_멈춘다(self):
        with self.assertRaises(geomap.GeomapError):
            geomap.click_point({"crs": "EPSG:3031"})


# ── 스타일 ──────────────────────────────────────────────────────────

class Styles(SimpleTestCase):
    def test_QGIS_필터를_읽는다(self):
        got = geomap_styles.parse_filter(
            "TYPENAME = 'fault' AND EXPOSURE = 'exposed' OR SIMPCODE = 20 OR LITHCODE IS NULL")
        self.assertEqual(got, [{"TYPENAME": "fault", "EXPOSURE": "exposed"},
                               {"SIMPCODE": 20}, {"LITHCODE": None}])

    def test_모르는_식은_멈춘다(self):
        for bad in ("A LIKE 'x%'", "(A = 1)", "A > 3"):
            with self.assertRaises(ValueError):
                geomap_styles.parse_filter(bad)

    def test_뽑아_둔_스타일이_모든_레이어에_있다(self):
        styles = geomap.styles()
        for layer, name in geomap.LAYERS.items():
            self.assertIn(name, styles, layer)
            self.assertTrue(styles[name].rules, layer)

    def test_간추린_지질의_색(self):
        style = geomap.styles()["simple_geology"]
        self.assertEqual(style.rules[style.pick((31,))]["fill"][:3], [255, 0, 0])
        self.assertIsNone(style.pick((999,)))

    def test_IS_NULL_은_빈_글자도_받는다(self):
        style = geomap.styles()["simple_lithology"]
        self.assertEqual(style.pick(("",)), style.pick((None,)))
        self.assertIsNotNone(style.pick(("",)))

    def test_속성_이름은_모두_영어가_있다(self):
        labels = {label for props in geomap.PROPS.values() for _, label in props}
        labels.add(geomap.DATASET_LABEL)
        self.assertEqual(sorted(labels - set(i18n.PROP_EN)), [])

    def test_레이어와_레이어군도_영어가_있다(self):
        for name in geomap.LAYERS:
            self.assertIn(name, i18n.LAYER_EN)
        self.assertIn("GeoMAP 지질도", i18n.GROUP_EN)


PATTERN_QML = """<qgis><renderer-v2 type="RuleRenderer">
 <rules><rule filter="MAPSYMBOL = 'Kg'OR MAPSYMBOL = 'Kd'" symbol="0" label="intrusive rocks"/></rules>
 <symbols><symbol name="0" type="fill">
  <layer class="SimpleFill" enabled="1"><prop k="color" v="255,96,17,0"/><prop k="style" v="solid"/>
   <prop k="outline_style" v="no"/><prop k="outline_color" v="255,96,17,0"/></layer>
  <layer class="LinePatternFill" enabled="1"><prop k="angle" v="45"/><prop k="distance" v="1.5"/>
   <prop k="distance_unit" v="MM"/><prop k="color" v="1,2,3,255"/>
   <symbol name="@0@1" type="line"><layer class="SimpleLine" enabled="1">
    <prop k="line_color" v="137,199,114,255"/><prop k="line_width" v="0.3"/><prop k="line_width_unit" v="MM"/>
   </layer></symbol></layer>
  <layer class="PointPatternFill" enabled="1"><prop k="distance_x" v="2"/><prop k="distance_x_unit" v="MM"/>
   <prop k="distance_y" v="2"/><prop k="distance_y_unit" v="MM"/><prop k="displacement_x" v="1"/>
   <prop k="displacement_x_unit" v="MM"/><prop k="displacement_y" v="0"/>
   <symbol name="@0@2" type="marker"><layer class="SimpleMarker" enabled="1">
    <prop k="name" v="half_square"/><prop k="color" v="190,210,255,255"/><prop k="size" v="1.25"/>
    <prop k="size_unit" v="MM"/><prop k="outline_color" v="190,210,255,255"/>
    <data_defined_properties><Option type="Map"><Option name="name" value="" type="QString"/></Option></data_defined_properties>
   </layer></symbol></layer>
  <layer class="SimpleLine" enabled="1"><prop k="line_color" v="137,199,114,255"/><prop k="line_width" v="0.26"/>
   <prop k="line_width_unit" v="MM"/></layer>
 </symbol></symbols></renderer-v2></qgis>"""


class Patterns(SimpleTestCase):
    """암층 스타일의 무늬 — 빗금(`hatch`)·점 무늬(`dots`)."""

    def parse(self):
        path = Path(tempfile.mkdtemp(prefix="gsm-qml-")) / "litho.qml"
        path.write_text(PATTERN_QML, encoding="utf-8")
        return geomap_styles.parse_qml(path, "units", "fill")

    def test_따옴표에_붙은_OR(self):
        self.assertEqual(geomap_styles.parse_filter("A = 'x'OR A = 'y'"), [{"A": "x"}, {"A": "y"}])

    def test_빗금과_점_무늬를_읽는다(self):
        rule = self.parse()["rules"][0]
        self.assertEqual(rule["when"], [{"MAPSYMBOL": "Kg"}, {"MAPSYMBOL": "Kd"}])
        self.assertIsNone(rule["fill"])                     # 다 투명한 바탕은 칠하지 않는다
        self.assertEqual(rule["outline"], [137, 199, 114, 255])     # 뒤따르는 SimpleLine
        h, = rule["hatch"]
        self.assertEqual((h["angle"], h["color"]), (45.0, [137, 199, 114, 255]))   # 서브심볼의 색
        self.assertAlmostEqual(h["spacing"], 1.5 * 96 / 25.4, places=1)
        d, = rule["dots"]
        self.assertEqual(d["marker"], "half_square")        # data defined 의 빈 name 에 속지 않는다
        self.assertAlmostEqual(d["shift"], 96 / 25.4, places=1)

    def test_무늬가_없는_스타일은_꼴이_그대로다(self):
        for name in ("simple_geology", "simple_lithology", "chronostratigraphic"):
            for rule in geomap.styles()[name].rules:
                self.assertNotIn("hatch", rule)
                self.assertNotIn("dots", rule)

    def test_암층_스타일(self):
        style = geomap.styles()["lithostratigraphic"]
        self.assertTrue(any(r.get("hatch") for r in style.rules))
        self.assertTrue(any(r.get("dots") for r in style.rules))
        self.assertIsNotNone(style.pick(("Czw",)))

    def test_무늬는_이웃_타일에서_이어진다(self):
        rule = self.parse()["rules"][0]
        # 가로로 붙은 두 그림 — 둘째의 원점은 첫째보다 폭만큼 오른쪽이다
        a = geomap._pattern_image(rule, 64, 64, (1000.0, 500.0), ss=2)
        b = geomap._pattern_image(rule, 64, 64, (1064.0, 500.0), ss=2)
        wide = geomap._pattern_image(rule, 128, 64, (1000.0, 500.0), ss=2)
        self.assertEqual(a.tobytes(), wide.crop((0, 0, 64, 64)).tobytes())
        self.assertEqual(b.tobytes(), wide.crop((64, 0, 128, 64)).tobytes())
        self.assertIsNotNone(a.getbbox())


# ── 그리기·속성 ────────────────────────────────────────────────────

def _png(content):
    return Image.open(io.BytesIO(content)).convert("RGBA")


class Render(WithData, SimpleTestCase):
    def bbox(self):
        return (SX - 12000, SY - 12000, SX + 12000, SY + 12000)

    def test_칠하고_구멍은_비운다(self):
        img = _png(geomap.render("geomap_simple_geology", self.bbox(), 240, 240))
        # 100 m/px — 큰 네모는 20..220, 구멍은 90..150, 관입암은 110..130 픽셀
        self.assertEqual(img.getpixel((30, 120))[:3], (255, 0, 0))        # 큰 네모
        self.assertEqual(img.getpixel((120 + 20, 120))[3], 0)            # 구멍 (작은 네모 밖)
        self.assertEqual(img.getpixel((120, 120))[:3], (230, 0, 169))    # 구멍 안의 관입암
        self.assertEqual(img.getpixel((2, 2))[3], 0)                     # 네모 밖

    def test_범위_밖은_비어_있다(self):
        img = _png(geomap.render("geomap_simple_geology", geomap.tile_bbox(3, 7, 7), 64, 64))
        self.assertIsNone(img.getbbox())

    def test_저줌에서는_점으로_찍힌다(self):
        z = 3
        x, y = geomap.tile_of(z, SX, SY)
        img = _png(geomap.render("geomap_simple_geology", geomap.tile_bbox(z, x, y), 256, 256))
        self.assertIsNotNone(img.getbbox())

    def test_단층(self):
        img = _png(geomap.render("geomap_faults", self.bbox(), 240, 240))
        # 단층은 SY+5000 → 위에서 (12000-5000)/100 = 70 째 줄
        self.assertGreater(img.getpixel((120, 70))[3], 0)
        self.assertEqual(img.getpixel((120, 120))[3], 0)

    def test_암층은_무늬로_칠한다(self):
        img = _png(geomap.render("geomap_lithostratigraphic", self.bbox(), 240, 240))
        # 큰 네모(Czw, 신생대 퇴적암)는 가로 빗금이라 칠한 줄과 빈 줄이 번갈아 온다
        column = [img.getpixel((40, y))[3] for y in range(40, 80)]
        self.assertGreater(max(column), 0)
        self.assertEqual(min(column), 0)
        self.assertEqual(img.getpixel((2, 2))[3], 0)

    def test_범례(self):
        for layer in geomap.LAYERS:
            img = _png(geomap.legend(layer))
            self.assertGreater(img.height, 20, layer)


class Query(WithData, SimpleTestCase):
    def test_구멍_안의_관입암(self):
        got = geomap.query("units", SX, SY, 1.0, layer="geomap_simple_geology")
        self.assertEqual([f["properties"]["지질 단위"] for f in got], ["Barton granodiorite"])

    def test_속성을_사람이_읽을_이름으로(self):
        got = geomap.query("units", SX + 5000, SY, 1.0, layer="geomap_simple_geology")[0]["properties"]
        self.assertEqual(got["지질 단위"], "Barton volcanics")
        self.assertEqual(got["연대 (Ma)"], "5.3 – 66")
        self.assertEqual(got["축척"], "1:250,000")
        self.assertEqual(got["출처 문헌"],
                         "Fleming E.A., Thomson J.W. (1979) Northern Graham Land BAS 500G Sheet 2")
        self.assertEqual(got["자료"], geomap.ATTRIBUTION)

    def test_둘레_안의_가까운_것(self):
        got = geomap.query("units", SX + 10500, SY, 1000.0, layer="geomap_simple_geology")
        self.assertEqual(got[0]["properties"]["지질 단위"], "Barton volcanics")
        self.assertEqual(geomap.query("units", SX + 10500, SY, 100.0, layer="geomap_simple_geology"), [])

    def test_그리지_않는_것은_묻지도_않는다(self):
        self.assertEqual(geomap.query("units", SX + 30000, SY, 1.0, layer="geomap_simple_geology"), [])

    def test_단층(self):
        got = geomap.query("faults", SX, SY + 5100, 200.0, layer="geomap_faults")
        self.assertEqual(got[0]["properties"]["단층 갈래"], "fault")


# ── 뷰 ──────────────────────────────────────────────────────────────

class Views(WithData, TestCase):
    def setUp(self):
        super().setUp()
        group = LayerGroup.objects.create(name="GeoMAP 지질도", region="antarctica")
        for i, name in enumerate(geomap.LAYERS):
            Layer.objects.create(name=name, title=name, group=group, upstream="geomap", order=i)

    def info(self, **extra):
        q = {"request": "GetFeatureInfo", "layers": "geomap_simple_geology",
             "query_layers": "geomap_simple_geology", "crs": "EPSG:3031",
             "bbox": f"{SX - 12000},{SY - 12000},{SX + 12000},{SY + 12000}",
             "width": "240", "height": "240", "i": "170", "j": "120"}
        q.update(extra)
        return self.client.get("/GSM/featureinfo/", q)

    def test_속성은_geomap_문으로(self):
        r = self.info()
        self.assertEqual(r.status_code, 200)
        props = r.json()["features"][0]["props"]
        self.assertEqual(props["지질 단위"], "Barton volcanics")
        self.assertEqual(props["자료"], geomap.ATTRIBUTION)

    def test_영어판(self):
        self.client.cookies["gsm_lang"] = "en"
        props = self.info().json()["features"][0]["props"]
        self.assertEqual(props["Geological unit"], "Barton volcanics")
        self.assertEqual(props["Dataset"], geomap.ATTRIBUTION)

    def test_속성은_캐시에_담지_않는다(self):
        self.info()
        self.assertEqual(list(Path(self.cache).rglob("*.json")), [])

    def test_타일(self):
        z = 9
        x, y = geomap.tile_of(z, SX, SY)
        url = f"/GSM/geomap/geomap_simple_geology/{z}/{x}/{y}.png"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(r["X-GSM-Cache"], "miss")
        self.assertIsNotNone(_png(r.content).getbbox())
        self.assertEqual(self.client.get(url)["X-GSM-Cache"], "hit")

    def test_레티나는_512(self):
        r = self.client.get("/GSM/geomap/geomap_faults/0/0/0@2x.png")
        self.assertEqual(_png(r.content).size, (512, 512))

    def test_없는_레이어_없는_타일(self):
        self.assertEqual(self.client.get("/GSM/geomap/nope/0/0/0.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/geomap/geomap_faults/1/2/0.png").status_code, 404)

    def test_WMS_꼴로도(self):
        b = geomap.tile_bbox(0, 0, 0)
        r = self.client.get("/GSM/wms/", {"layers": "geomap_simple_geology", "crs": "EPSG:3031",
                                          "bbox": ",".join(map(str, b)), "width": "64", "height": "64"})
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(_png(r.content).size, (64, 64))

    def test_범례(self):
        r = self.client.get("/GSM/legend/", {"layer": "geomap_faults"})
        self.assertEqual(r["Content-Type"], "image/png")

    def test_카탈로그에_출처와_타일_주소(self):
        groups = self.client.get("/GSM/catalog/").json()["groups"]
        layer = [l for g in groups if g["region"] == "antarctica" for l in g["layers"]][0]
        self.assertEqual(layer["upstream"], "geomap")
        self.assertEqual(layer["attribution"], geomap.ATTRIBUTION)
        # 판이 주소에 든다 — 브라우저가 오래 들고 있어도 판이 바뀌면 새 주소다 (wetherilli 151)
        self.assertEqual(layer["tiles"], f"geomap/{layer['name']}/{{z}}/{{x}}/{{y}}.png?v={geomap.data_version()}"
                                         f"r{geomap.RENDERER}")


class Missing(TestCase):
    """파일이 없어도 뷰어는 돈다 — 안내 타일이 뜨고 속성은 까닭을 말한다."""

    def setUp(self):
        patch = override_settings(GEOMAP_DIR=tempfile.mkdtemp(prefix="gsm-geomap-none-"))
        patch.enable()
        self.addCleanup(patch.disable)
        group = LayerGroup.objects.create(name="GeoMAP 지질도", region="antarctica")
        Layer.objects.create(name="geomap_simple_geology", title="x", group=group, upstream="geomap")

    def test_안내_타일(self):
        r = self.client.get("/GSM/geomap/geomap_simple_geology/0/0/0.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertFalse(geomap.available())

    def test_속성은_503(self):
        r = self.client.get("/GSM/featureinfo/", {"query_layers": "geomap_simple_geology",
                                                  "crs": "EPSG:3031", "bbox": "0,0,1,1",
                                                  "width": "1", "height": "1", "i": "0", "j": "0"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("GeoMAP", r.json()["error"])
