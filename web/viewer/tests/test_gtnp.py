"""GTN-P 영구동토 시추공 (wetherilli 422) — 받아 줄이기, 북극·남극 레이어, 받지 않았을 때. 상류는 부르지 않는다."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from viewer import gtnp, i18n

YEARS = ",".join(gtnp.YEARS)
HEAD = ("FID,country_name,site_name,borehole_id,borehole_name,responsible_person_name,gtnp_code,permafrost_zone,"
        "vegetation_name,borehole_drilled_depth,slope,aspect,longitude,latitude,elevation,metadata_completeness,"
        f"{YEARS},timeseries_lenght,year_count,first_year,last_year,min_magt_depth,max_magt_depth,range_magt_depth,"
        "magt_2004_2009,magt_2010_2015,tsp_2016,data_completeness,timeseries_slope,geom_ref")


def line(bid, name, lon, lat, values=None, zone="Continuous", country="Russia", first="", last="", count="",
         lo="", hi="", slope="", depth="10"):
    temps = [""] * len(gtnp.YEARS)
    for year, value in (values or {}).items():
        temps[gtnp.YEARS.index(str(year))] = str(value)
    return ",".join([f"magt.{bid}", country, "Site", str(bid), name, "A.  Person ", f"RU {bid}", zone, "Tundra",
                     depth, "0", "0", str(lon), str(lat), "12.4", "50", *temps, "", count, first, last, lo, hi, "",
                     "", "", "", "", slope, f"POINT ({lon} {lat})"])


CSV = "\n".join([
    HEAD,
    line(1, "Barrow 2", -156.6541, 71.3105, {2008: -9.06, 2010: -9, 2015: -8.72}, first="2008", last="2015",
         count="5", lo="20", hi="20", slope="0.0485"),
    line(2, "Fildes 1. King George Island", -58.97, -62.2036, {2012: -0.4}, zone="No Permafrost",
         country="Antarctica", first="2012", last="2012", count="1", lo="2", hi="5"),
    line(3, "Mongolia 1", 106.9, 47.9, {2010: 0.5}, country="Mongolia"),
    line(4, "Svalbard 9", 15.6, 78.2, zone="isolated patches", country="Svalbard"),
    line(5, "자리 없음", "", ""),
])


class Parse(SimpleTestCase):
    def test_줄이고_마지막_해의_지온을_남긴다(self):
        rows = {r["id"]: r for r in gtnp.parse(CSV)}
        self.assertEqual(sorted(rows), [1, 2, 3, 4])                    # 자리가 없는 줄은 뺀다
        barrow = rows[1]
        self.assertEqual((barrow["magt"], barrow["magt_year"], barrow["magt_depth"]), (-8.72, 2015, "20"))
        self.assertEqual(barrow["years"], "2008–2015")
        self.assertEqual(barrow["trend"], 0.049)                        # 세 해가 넘어야 추세를 싣는다
        self.assertEqual(barrow["pi"], "A. Person")
        self.assertEqual(rows[2]["magt_depth"], "2–5")
        self.assertNotIn("trend", rows[2])
        self.assertEqual(rows[2]["zone"], "No permafrost")              # 대소문자로 갈린 것을 하나로
        self.assertEqual(rows[4]["zone"], "Isolated patches")
        self.assertNotIn("magt", rows[4])

    def test_지온의_구간(self):
        self.assertEqual([gtnp.class_of(v) for v in (-9, -5, -3, -0.4, 0.5, None)],
                         ["cold", "cold", "cool", "near", "warm", "none"])


class Fetched(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.override = override_settings(GTNP_DIR=cls.tmp.name)
        cls.override.enable()
        with mock.patch.object(gtnp, "_get", return_value=CSV), mock.patch.object(gtnp.usage, "paused", return_value=0):
            cls.got = gtnp.download(gtnp.path())

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        gtnp._memo.clear()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_받은_수(self):
        self.assertEqual(self.got, {"boreholes": 4, "magt": 3})
        self.assertEqual(json.loads(gtnp.path().read_text(encoding="utf-8"))["license"], "CC BY 3.0")

    def test_북극_레이어는_북위_50도_너머만(self):
        r = self.client.get("/GSM/points/", {"layer": "gtnp:boreholes_arctic"})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(sorted(f["id"] for f in data["features"]), [1, 4])      # 몽골(47.9°)은 실을 탭이 없다
        props = {f["id"]: f["properties"] for f in data["features"]}
        self.assertEqual(props[1]["code"], "cold")
        self.assertEqual(props[1]["gtnp"], "RU 1")
        self.assertEqual(props[4]["code"], "none")
        self.assertEqual([(row["code"], row["count"]) for row in data["legend"]], [("cold", 1), ("none", 1)])
        self.assertEqual(data["style"], "class")

    def test_남극_레이어(self):
        data = json.loads(self.client.get("/GSM/points/", {"layer": "gtnp:boreholes_antarctica"}).content)
        self.assertEqual([f["properties"]["name"] for f in data["features"]], ["Fildes 1. King George Island"])
        self.assertEqual(data["features"][0]["properties"]["code"], "near")


class NotFetched(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(GTNP_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_503_으로_까닭을_말한다(self):
        r = self.client.get("/GSM/points/", {"layer": "gtnp:boreholes_arctic"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_gtnp", r.json()["error"])

    def test_CSV_가_아니면_멈춘다(self):
        fake = mock.Mock(status_code=200, text="<ServiceExceptionReport/>", url=gtnp.WFS, content=b"")
        with mock.patch.object(gtnp.requests, "get", return_value=fake), mock.patch.object(gtnp.usage, "record"):
            with self.assertRaises(gtnp.GtnpError):
                gtnp._get()


class Seed(SimpleTestCase):
    def test_씨앗에_영어가_있고_레이어가_문과_맞다(self):
        names = []
        for path in settings.GTNP_CATALOG_SEEDS:
            seed = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(seed["_상류"], "gtnp")
            for group in seed["레이어군순서"]:
                self.assertIn(group, i18n.GROUP_EN)
            for layer in seed["레이어"]:
                names.append(layer["name"])
                self.assertIn(layer["name"], i18n.LAYER_EN)
                self.assertIn(layer["name"], i18n.ABSTRACT_EN)
        self.assertEqual(sorted(names), sorted(gtnp.LAYERS))

    def test_팝업과_범례의_말에_영어가_있다(self):
        for label in gtnp.LABELS.values():
            self.assertIn(label, i18n.client_table("en"))
        for _, label, _ in gtnp.CLASSES:
            self.assertIn(label, i18n.EN)
