"""과학 해양 시추공 (wetherilli 418) — IODP 목록을 줄이고, 극지 탭의 점 레이어로 낸다. 상류는 부르지 않는다."""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import earthpoints, iodp, views

CSV = (
    "﻿leg,expedition,site,hole,latitude,longitude,arrival,water_depth,core_penetrated,core_recovered,url_core,url_log,url_vcd,url_xct\n"
    "28,,268,,-63.9498,105.1557,,,474.5,65.6,http://www.ngdc.noaa.gov/mgg/geology/dsdp/data/28/268/index.htm,"
    "https://mlp.ldeo.columbia.edu/data/dsdp/leg28/268/,,\n"
    "178,,1097,A,-66.3975,-70.7505,2/14/98,551.4,436.6,59.2,http://web.iodp.tamu.edu/OVERVIEW/?&exp=178&site=1097,,,\n"
    ",403,U1624,B,77.58770833,10.09399833,07/18/2024 09:30,1319.81,258,223.05,https://web.iodp.tamu.edu/OVERVIEW/?&exp=403&site=U1624,,,\n"
    ",301,1026,B,47.76261833,-127.7591367,01/00/1900 00:00,,,,,,,\n"
    ",,,,10,10,,,,,,,,\n"
)


class Shrink(SimpleTestCase):
    def test_프로그램은_레그와_항차로_가른다(self):
        self.assertEqual([iodp.program("28", ""), iodp.program("178", ""), iodp.program("", "403")], ["dsdp", "odp", "iodp"])

    def test_도착_일시의_여러_꼴(self):
        self.assertEqual(iodp.day("07/18/2024 04:00"), "2024-07-18")
        self.assertEqual(iodp.day("9/7/05"), "2005-09-07")
        self.assertEqual(iodp.day("2/14/98"), "1998-02-14")
        self.assertEqual(iodp.day("11/2005"), "2005-11")
        self.assertEqual(iodp.day("01/00/1900 00:00"), "")
        self.assertEqual(iodp.day(""), "")

    def test_줄인다(self):
        rows = [dict(zip(iodp.COLUMNS, r)) for r in iodp.shrink(CSV)]
        self.assertEqual([r["hole"] for r in rows], ["268", "1097A", "U1624B", "1026B"])     # 항차가 없는 줄은 버린다
        dsdp, odp = rows[0], rows[1]
        self.assertEqual(dsdp["core"], "")                                 # NCEI 의 DSDP 쪽은 죽었다
        self.assertTrue(dsdp["log"].startswith("https://mlp.ldeo"))
        self.assertTrue(odp["core"].startswith("https://web.iodp.tamu.edu/"))
        self.assertEqual((odp["cruise"], odp["water"], odp["date"]), ("Leg 178", 551.4, "1998-02-14"))
        self.assertEqual(rows[2]["cruise"], "Exp. 403")

    def test_손으로_더한_시추공에는_출처가_있다(self):
        holes = json.loads(iodp.EXTRA.read_text(encoding="utf-8"))["holes"]
        self.assertEqual({h["hole"] for h in holes} >= {"AND-1B", "AND-2A", "CRP-1", "CIROS-1"}, True)
        for h in holes:
            self.assertTrue(h["source"].startswith("https://doi.org/10.1594/PANGAEA."), h["hole"])
            self.assertLess(h["lat"], -60)


def gathered(folder) -> Path:
    path = Path(folder) / "iodp_holes.json"
    path.write_text(json.dumps({"holes": iodp.shrink(CSV)}), encoding="utf-8")
    return path


class Body(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-iodp-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        gathered(self.dir)
        earthpoints._body.cache_clear()

    def body(self, name, lang="ko"):
        return json.loads(earthpoints.body(name, lang))

    def test_남극은_네모_안과_손으로_더한_것(self):
        d = self.body("earth:iodp_antarctica")
        names = [f["properties"]["name"] for f in d["features"]]
        self.assertIn("1097A", names)
        self.assertIn("AND-2A", names)
        self.assertIn("268", names)                                         # 남위 63.9° — 남극 탭은 60° 남쪽
        self.assertNotIn("1026B", names)
        self.assertEqual({row["code"] for row in d["legend"]}, {"dsdp", "odp", "shelf"})
        andrill = next(f for f in d["features"] if f["properties"]["name"] == "AND-2A")
        self.assertEqual(andrill["properties"]["code"], "shelf")
        self.assertIn("PANGAEA", andrill["properties"]["link"])
        self.assertEqual(d["links"], ["link", "log"])

    def test_북극(self):
        d = self.body("earth:iodp_arctic", "en")
        [hole] = d["features"]
        p = hole["properties"]
        self.assertEqual((p["name"], p["program"], p["water"], p["date"]), ("U1624B", "IODP (2003–)", "1,319.81", "2024-07-18"))

    def test_극지_밖에는_없다(self):
        self.assertFalse(earthpoints.knows("earth:iodp_europe"))
        self.assertTrue(earthpoints.knows("earth:iodp_arctic"))


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_남극_북극해의_시추_레이어군(self):
        found = {}
        for group in views._catalog("ko"):
            for layer in group["layers"]:
                if layer["name"].startswith("earth:iodp_"):
                    found[layer["name"]] = (group["region"], layer["kind"], layer["style"])
        self.assertEqual(found, {"earth:iodp_antarctica": ("antarctica", "points", "class"),
                                 "earth:iodp_arctic": ("arctic_ocean", "points", "class")})

    def test_받지_않았으면_명령을_적는다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp(prefix="gsm-iodp-none-")):
            r = self.client.get(reverse("viewer:points"), {"layer": "earth:iodp_antarctica"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_iodp_holes", r.json()["error"])
