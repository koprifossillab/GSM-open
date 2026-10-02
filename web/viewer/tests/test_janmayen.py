"""얀마옌 지질도(NPI NP_J250_Geologi) — 우리 디스크의 GeoJSON 을 위경도로 옮겨 준다 (devlog 022).

진짜 파일을 쓰지 않는다. UTM 29N 으로 적힌 작은 GeoJSON 을 임시 자리에 만든다.
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import crs, i18n, janmayen, views
from viewer.models import Layer, LayerGroup

#: 베렌베르크 꼭대기 분화구의 분출 중심 — 원본 `NP_J250_Geologi_p.geojson` 의 한 점
BEERENBERG_UTM = (530321.4735623545, 7887049.659185712)


def utm(lat, lon):
    return list(crs.latlon_to_utm(29, lat, lon))


def collection(features, crs_name="urn:ogc:def:crs:EPSG::25829"):
    return {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": crs_name}},
            "features": features}


def unit(fid=1, code=1161, name="youngest basalt flows and tephra", rgb="230, 235, 8"):
    ring = [utm(71.00, -8.50), utm(71.00, -8.40), utm(71.05, -8.40), utm(71.00, -8.50)]
    return {"type": "Feature",
            "properties": {"fid": fid, "np2": 4, "geo_code": code, "Name": name + " ",
                           "Navn": "yngste basalt lavastrømmer og tefra", "part_of": 1160, "rgb": rgb,
                           "path": "Lithostratigraphy-->Quaternary volcanic rocks of Jan Mayen-->"
                                   "Inndalen Formation (Holocene), undifferentiated -->" + name},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def vent(code=501, name="Eruptive centre"):
    return {"type": "Feature",
            "properties": {"ogc_fid": 7, "np2": 1, "geo_code": code, "comment": None, "Name": name,
                           "Navn": "Erupsjonssentrum", "part_of": 500},
            "geometry": {"type": "Point", "coordinates": list(BEERENBERG_UTM)}}


def fissure():
    return {"type": "Feature",
            "properties": {"ogc_fid": 1, "fid": 12, "Name": "Eruptive fissure", "Navn": "Erupsjonsspalte",
                           "rgb": None, "geo_code": 502, "part_of": 500},
            "geometry": {"type": "LineString", "coordinates": [utm(70.9, -8.9), utm(70.95, -8.8)]}}


class Utm(SimpleTestCase):
    def test_중앙_경선은_동_500000(self):
        east, _ = crs.latlon_to_utm(29, 71.0, -9.0)
        self.assertAlmostEqual(east, 500000.0, places=3)

    def test_되짚으면_제자리(self):
        for lat, lon in ((70.83, -9.07), (71.16, -7.93), (71.0, -8.4)):
            back = crs.utm_to_latlon(29, *crs.latlon_to_utm(29, lat, lon))
            self.assertAlmostEqual(back[0], lat, places=9)
            self.assertAlmostEqual(back[1], lon, places=9)

    def test_베렌베르크(self):
        # 베렌베르크 꼭대기(Haakon VII Topp)는 71°05′N 8°10′W 둘레다. 원본 파일의
        # 꼭대기 분화구 분출 중심이 그 둘레 1 km 안에 떨어져야 한다
        lat, lon = crs.utm_to_latlon(29, *BEERENBERG_UTM)
        self.assertAlmostEqual(lat, 71.0847, delta=0.001)
        self.assertAlmostEqual(lon, -8.1619, delta=0.001)
        self.assertLess(abs(lat - 71.0833) * 111.0, 1.0)
        self.assertLess(abs(lon + 8.1667) * 111.0 * 0.324, 1.0)

    def test_우리나라_UTM_52N_과_같은_셈(self):
        # 29N 을 따로 셈하지 않는다 — 고르개의 32652(52N)와 같은 식이어야 한다
        lat, lon = crs.utm_to_latlon(52, 400000, 4000000)
        self.assertEqual((lat, lon), crs.to_latlon("32652", 400000, 4000000))


class Convert(SimpleTestCase):
    def test_면을_위경도로_옮기고_속성을_줄인다(self):
        out = janmayen.convert(collection([unit()]))
        f = out["features"][0]
        ring = f["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], [-8.5, 71.0])
        self.assertEqual(ring[2], [-8.4, 71.05])
        p = f["properties"]
        self.assertEqual(p["name"], "youngest basalt flows and tephra")      # 끝 빈칸을 뗀다
        self.assertEqual(p["color"], "#e6eb08")
        self.assertEqual(p["age"], "홀로세")
        self.assertEqual(p["path"], "Quaternary volcanic rocks of Jan Mayen › "
                                    "Inndalen Formation (Holocene), undifferentiated › "
                                    "youngest basalt flows and tephra")

    def test_범례는_있는_단위만_차례대로(self):
        out = janmayen.convert(collection([
            unit(1, 1180, "Havhestberget Formation (late Pleistocene): hyaloclastic lava, tuff", "202, 128, 78"),
            unit(2), unit(3)]))
        legend = out["legend"]
        self.assertEqual([r["code"] for r in legend], [1161, 1180])     # 젊은 것이 먼저
        self.assertEqual(legend[0]["count"], 2)
        self.assertEqual(legend[1]["color"], "#ca804e")

    def test_선과_점은_스타일_표의_색(self):
        lines = janmayen.convert(collection([fissure()]))
        self.assertEqual(lines["features"][0]["properties"]["color"], "#ed2322")
        self.assertEqual(lines["legend"][0]["width"], 1.8)
        points = janmayen.convert(collection([vent(531, "Fumarole")]))
        self.assertEqual(points["legend"][0]["shape"], "star")
        self.assertNotIn("age", points["features"][0]["properties"])      # 시대를 지어내지 않는다

    def test_다른_좌표계면_멈춘다(self):
        with self.assertRaises(janmayen.JanMayenError):
            janmayen.convert(collection([unit()], "urn:ogc:def:crs:EPSG::32633"))

    def test_팝업_이름은_영어가_있다(self):
        for label in janmayen.LABELS.values():
            self.assertIn(label, i18n.PROP_EN)

    def test_지질시대는_ICS_이름으로_옮겨진다(self):
        for age in set(janmayen.AGES.values()):
            self.assertNotEqual(i18n.age_en(age), age)
        self.assertEqual(i18n.age_en("플라이스토세 후기"), "Late Pleistocene")


class Serve(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / janmayen.DATASET
        root.mkdir()
        (root / "NP_J250_Geologi_f.geojson").write_text(json.dumps(collection([unit()])), encoding="utf-8")
        (root / "NP_J250_Geologi_l.geojson").write_text(json.dumps(collection([fissure()])), encoding="utf-8")
        (root / "NP_J250_Geologi_p.geojson").write_text(json.dumps(collection([vent()])), encoding="utf-8")
        janmayen._memo.clear()

    def tearDown(self):
        self.tmp.cleanup()
        janmayen._memo.clear()

    def test_한_덩이로_준다(self):
        with override_settings(NPOLAR_DIR=self.tmp.name):
            r = self.client.get("/GSM/points/", {"layer": "janmayen:units"})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["style"], "unit")
        self.assertEqual(data["labels"]["navn"], "노르웨이어 이름")
        self.assertEqual(data["legend"][0]["code"], 1161)
        self.assertEqual(len(data["features"]), 1)

    def test_영어판은_지질시대만_옮긴다(self):
        with override_settings(NPOLAR_DIR=self.tmp.name):
            r = self.client.get("/GSM/points/", {"layer": "janmayen:units", "lang": "en"},
                                HTTP_COOKIE="gsm_lang=en")
        props = json.loads(r.content)["features"][0]["properties"]
        self.assertEqual(props["age"], "Holocene")
        self.assertEqual(props["navn"], "yngste basalt lavastrømmer og tefra")

    def test_파일이_없으면_503_으로_까닭을(self):
        with override_settings(NPOLAR_DIR=str(Path(self.tmp.name) / "없는곳")):
            r = self.client.get("/GSM/points/", {"layer": "janmayen:vents"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("얀마옌", json.loads(r.content)["error"])

    def test_파일이_바뀌면_다시_읽는다(self):
        with override_settings(NPOLAR_DIR=self.tmp.name):
            first = json.loads(janmayen.body("janmayen:vents"))
            path = janmayen.data_file("janmayen:vents")
            path.write_text(json.dumps(collection([vent(), vent(531, "Fumarole")])), encoding="utf-8")
            second = json.loads(janmayen.body("janmayen:vents"))
        self.assertEqual((len(first["features"]), len(second["features"])), (1, 2))


class Catalog(TestCase):
    def test_씨앗이_얀마옌_지역에_들어간다(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        group = LayerGroup.objects.get(name="얀마옌 지질 (NPI)")
        self.assertEqual(group.region, "jan_mayen")
        names = set(Layer.objects.filter(upstream="janmayen").values_list("name", flat=True))
        self.assertEqual(names, set(janmayen.LAYERS))
        for name in names:
            self.assertIn(name, i18n.LAYER_EN)
        self.assertIn(group.name, i18n.GROUP_EN)

    def test_카탈로그의_행은_점_길을_탄다(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: l for g in views._catalog() for l in g["layers"] if l["upstream"] == "janmayen"}
        self.assertEqual(rows["janmayen:units"]["kind"], "points")
        self.assertEqual(rows["janmayen:units"]["style"], "unit")
        self.assertEqual(rows["janmayen:units"]["opacity"], 0.75)
        self.assertIn("Norsk Polarinstitutt", rows["janmayen:lines"]["attribution"])
        self.assertTrue(rows["janmayen:vents"]["verified"])
