"""중국 지질도(USGS geo3al) — 우리 디스크의 셰이프파일을 위경도 GeoJSON 으로 준다 (devlog 025).

진짜 파일을 쓰지 않는다(이용 조건이 재배포를 막는다). 람베르트로 적힌 작은
셰이프파일·dBASE 를 임시 자리에 만든다.
"""
import json
import struct
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import crs, geo3al, i18n, views
from viewer.models import Layer, LayerGroup

#: 받은 파일의 `.prj` 그대로
PRJ = ('PROJCS["WGS_1984_Lambert_Conformal_Conic",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
       'SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
       'UNIT["Degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic"],'
       'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
       'PARAMETER["Central_Meridian",120.0],PARAMETER["Standard_Parallel_1",31.0],'
       'PARAMETER["Standard_Parallel_2",-29.0],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')
PROJ = geo3al.projection(PRJ)


def lcc(lon, lat):
    return crs.latlon_to_lcc(lat, lon, **PROJ)


def ring(points, clockwise=True):
    """위경도 꼭짓점 → 닫힌 람베르트 고리. 셰이프파일의 바깥 고리는 시계 방향이다."""
    pts = [lcc(*p) for p in points]
    if (geo3al._area(pts + pts[:1]) > 0) == clockwise:
        pts.reverse()
    return pts + pts[:1]


def square(west, south, size, clockwise=True):
    return ring([(west, south), (west + size, south), (west + size, south + size), (west, south + size)],
                clockwise)


def write_shp(path, records):
    """다각형 셰이프파일 하나. records 는 행마다 고리 목록."""
    bodies = []
    for number, rings in enumerate(records, 1):
        points = [p for r in rings for p in r]
        starts, at = [], 0
        for r in rings:
            starts.append(at)
            at += len(r)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        content = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), len(rings), len(points))
        content += struct.pack(f"<{len(rings)}i", *starts)
        content += b"".join(struct.pack("<2d", *p) for p in points)
        bodies.append(struct.pack(">2i", number, len(content) // 2) + content)
    total = 100 + sum(len(b) for b in bodies)
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, total // 2) + struct.pack("<2i", 1000, 5)
    header += struct.pack("<8d", 0, 0, 0, 0, 0, 0, 0, 0)
    path.write_bytes(header + b"".join(bodies))


def write_dbf(path, rows):
    fields = [("AREA", "N", 19), ("PERIMETER", "N", 19), ("TYPE", "C", 5), ("GLG", "C", 5), ("GEN_GLG", "C", 5)]
    width = 1 + sum(f[2] for f in fields)
    header_len = 32 + 32 * len(fields) + 1
    out = struct.pack("<B3BIHH20x", 3, 99, 9, 28, len(rows), header_len, width)
    for name, kind, size in fields:
        out += name.encode().ljust(11, b"\0") + kind.encode() + b"\0" * 4 + bytes([size, 0]) + b"\0" * 14
    out += b"\r"
    for row in rows:
        out += b" " + b"".join(str(row.get(name, "")).encode().ljust(size)[:size] for name, _, size in fields)
    path.write_bytes(out + b"\x1a")


class Lambert(SimpleTestCase):
    def test_스나이더의_예제(self):
        # Snyder (1987) Map Projections — A Working Manual, 15 장의 풀이 예
        clarke = (6378206.4, 1 / 294.9786982)
        x, y = crs.latlon_to_lcc(35, -75, -96, 33, 45, 23, ellipsoid=clarke)
        self.assertAlmostEqual(x, 1894410.9, delta=0.1)
        self.assertAlmostEqual(y, 1564649.5, delta=0.1)

    def test_되짚으면_제자리(self):
        for lon, lat in ((73.5, 39.5), (126.53, 33.38), (148.9, 53.6), (100.0, 16.1)):
            back = crs.lcc_to_latlon(*lcc(lon, lat), **PROJ)
            self.assertAlmostEqual(back[0], lat, places=9)
            self.assertAlmostEqual(back[1], lon, places=9)

    def test_중앙_경선은_동_0(self):
        east, _ = lcc(120.0, 35.0)
        self.assertAlmostEqual(east, 0.0, places=6)

    def test_prj_에서_변수를_읽는다(self):
        self.assertEqual((PROJ["lon0"], PROJ["lat1"], PROJ["lat2"], PROJ["lat0"]), (120.0, 31.0, -29.0, 0.0))

    def test_다른_투영이면_멈춘다(self):
        with self.assertRaises(geo3al.Geo3alError):
            geo3al.projection(PRJ.replace("Lambert_Conformal_Conic", "Albers"))
        with self.assertRaises(geo3al.Geo3alError):
            geo3al.projection(PRJ.replace("298.257223563", "299.1528128"))


class Rings(SimpleTestCase):
    def test_구멍은_품은_바깥_고리에_붙는다(self):
        outer, hole = square(100, 30, 2), square(100.5, 30.5, 0.5, clockwise=False)
        island = square(110, 30, 1)
        polygons = geo3al.group_rings([outer, island, hole])
        self.assertEqual([len(p) for p in polygons], [2, 1])
        self.assertIs(polygons[0][1], hole)

    def test_바깥_고리가_둘이면_다각형도_둘(self):
        rows = [{"TYPE": "", "GLG": "K", "GEN_GLG": "K"}]
        features = geo3al.convert([[square(100, 30, 1), square(105, 30, 1)]], rows, PROJ)
        self.assertEqual(features[0]["geometry"]["type"], "MultiPolygon")


class Serve(TestCase):
    ROWS = [
        {"TYPE": "", "GLG": "JK", "GEN_GLG": "KJ"},
        {"TYPE": "i", "GLG": "K", "GEN_GLG": "K"},
        {"TYPE": "", "GLG": "H2O", "GEN_GLG": "H2O"},     # 물 — 싣지 않는다
        {"TYPE": "", "GLG": "PZu", "GEN_GLG": "Pzu"},
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / geo3al.DATASET
        root.mkdir()
        write_shp(root / "geo3al.shp", [[square(100 + 2 * i, 30, 1)] for i in range(len(self.ROWS))])
        write_dbf(root / "geo3al.dbf", self.ROWS)
        (root / "geo3al.prj").write_text(PRJ, encoding="latin-1")
        geo3al._memo.clear()
        geo3al._bodies.clear()

    def tearDown(self):
        self.tmp.cleanup()
        geo3al._memo.clear()
        geo3al._bodies.clear()

    def get(self, layer, lang="ko"):
        with override_settings(USGS_DIR=self.tmp.name):
            return self.client.get("/GSM/points/", {"layer": layer, "lang": lang},
                                   HTTP_COOKIE=f"gsm_lang={lang}")

    def test_밖에_열면_내부용은_404(self):
        with override_settings(PUBLIC=True):
            r = self.get("geo3al:age")
        self.assertEqual(r.status_code, 404)

    def test_밖에_열면_목록에서_빠진다(self):
        from viewer import views
        from viewer.models import Layer, LayerGroup
        group = LayerGroup.objects.create(name="중국 시험", region="china")
        for name in ("geo3al:age", "phyloserver:dikes", "peninsula:shaded", "L_250K_Geology_Map"):
            Layer.objects.create(name=name, title=name, group=group, upstream=name.split(":")[0]
                                 if ":" in name else "kigam")
        names = lambda: {l["name"] for g in views._catalog() for l in g["layers"]}
        self.assertIn("geo3al:age", names())
        with override_settings(PUBLIC=True):
            self.assertEqual(names() & {"geo3al:age", "phyloserver:dikes", "peninsula:shaded",
                                        "L_250K_Geology_Map"}, {"L_250K_Geology_Map"})

    def test_시대_레이어는_물을_빼고_다_싣는다(self):
        r = self.get("geo3al:age")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["style"], "unit")
        self.assertEqual(len(data["features"]), 3)
        first = data["features"][0]["properties"]
        self.assertEqual((first["code"], first["age"], first["glg"]), ("KJ", "쥐라기~백악기", "JK"))
        self.assertEqual(first["color"], geo3al.AGE_BY_CODE["KJ"][1])
        # 꼭짓점이 위경도로 돌아온다
        ring0 = data["features"][0]["geometry"]["coordinates"][0]
        self.assertAlmostEqual(min(p[0] for p in ring0), 100.0, places=3)
        self.assertAlmostEqual(min(p[1] for p in ring0), 30.0, places=3)

    def test_범례는_젊은_것부터_있는_것만(self):
        legend = json.loads(self.get("geo3al:age").content)["legend"]
        self.assertEqual([r["code"] for r in legend], ["K", "KJ", "Pzu"])
        self.assertEqual(legend[0]["count"], 1)

    def test_암종_레이어는_TYPE_이_있는_면만(self):
        data = json.loads(self.get("geo3al:rock").content)
        self.assertEqual(len(data["features"]), 1)
        props = data["features"][0]["properties"]
        self.assertEqual((props["code"], props["rock"], props["glg"]), ("i", "관입 화성암", "K · i"))

    def test_영어판은_시대와_암종을_옮긴다(self):
        data = json.loads(self.get("geo3al:age", "en").content)
        ages = [f["properties"]["age"] for f in data["features"]]
        self.assertEqual(ages, ["Jurassic – Cretaceous", "Cretaceous", "Late Paleozoic"])
        self.assertEqual(data["features"][1]["properties"]["rock"], "Intrusive igneous rock")
        self.assertEqual(data["legend"][2]["label"], "Late Paleozoic")

    def test_파일이_없으면_503_으로_까닭을(self):
        with override_settings(USGS_DIR=str(Path(self.tmp.name) / "없는곳")):
            r = self.client.get("/GSM/points/", {"layer": "geo3al:age"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("geo3al", json.loads(r.content)["error"])

    def test_셰이프와_속성의_수가_다르면_500(self):
        write_dbf(Path(self.tmp.name) / geo3al.DATASET / "geo3al.dbf", self.ROWS[:2])
        self.assertEqual(self.get("geo3al:age").status_code, 500)


class Tables(SimpleTestCase):
    def test_시대_이름은_모두_영어로_옮겨진다(self):
        for name in list(geo3al.GLG.values()) + [label for _, label, _ in geo3al.AGE_CLASSES]:
            self.assertNotEqual(i18n.age_en(name), name, name)

    def test_팝업_이름은_영어가_있다(self):
        for label in geo3al.LABELS.values():
            self.assertIn(label, i18n.PROP_EN)


class Catalog(TestCase):
    def test_씨앗이_중국_지역에_들어간다(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        group = LayerGroup.objects.get(name="중국·동아시아 지질 (USGS)")
        self.assertEqual(group.region, "china")
        names = set(Layer.objects.filter(upstream="geo3al").values_list("name", flat=True))
        self.assertEqual(names, set(geo3al.LAYERS))
        for name in names:
            self.assertIn(name, i18n.LAYER_EN)
        self.assertIn(group.name, i18n.GROUP_EN)

    def test_카탈로그의_행은_점_길을_타고_한_장으로_그린다(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: l for g in views._catalog() for l in g["layers"] if l["upstream"] == "geo3al"}
        age = rows["geo3al:age"]
        self.assertEqual((age["kind"], age["style"], age["render"]), ("points", "unit", "image"))
        self.assertEqual(age["opacity"], 0.75)
        self.assertIn("no redistribution", age["attribution"])
        self.assertTrue(age["verified"])
        self.assertEqual(age["bbox"], [73.46, 16.09, 148.93, 53.6])
