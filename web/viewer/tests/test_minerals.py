"""세계 광상 — USGS MRDS·세계 광상 표 (wetherilli 276). 상류를 부르지 않는다 — 작은 zip 을 지어 굽는다."""
import io
import json
import tempfile
import zipfile
from pathlib import Path

from django.test import TestCase, override_settings
from PIL import Image

from viewer import minerals

MRDS = ("dep_id,url,mrds_id,mas_id,site_name,latitude,longitude,region,country,state,county,com_type,commod1,commod2,commod3,oper_type,"
        "dep_type,prod_size,dev_stat,ore,hrock_type\n"
        '1,"https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id=1",,,"Chuquicamata",-22.29,-68.9,SA,Chile,Antofagasta,,M,"Copper, Silver",'
        "Molybdenum,,Surface,Porphyry Cu,L,Producer,Chalcopyrite,Porphyry\n"
        "2,,,,Gold Hill,-22.3,-68.91,SA,Chile,,,M,Gold,,,,,,Past Producer,,\n"
        "3,,,,Quarry,40,-100,NA,United States,,,N,Sand and Gravel,,,,,,Producer,,\n"
        "4,,,,Nowhere,0,0,NA,United States,,,M,Gold,,,,,,Producer,,\n"
        "5,,,,Mica pit,35,-80,NA,United States,,,N,Mica,,,,,,Occurrence,,\n")
PORCU = ("rec_id,depname,country,stprov,latitude,longitude,agemy,depage,oreton,cugrd,mogrd,augrd,aggrd,deptype,rockdep\n"
         "1,Chuquicamata,Chile,Antofagasta,-22.29,-68.9,33,Oligocene,21277,0.592,0.04,0.013,5,17,porphyry\n")
SEDZNPB = ("rec_id,depname,country,stprov,latitude,longitude,oreton,zngrd,pbgrd,deptype,prevtype,hostrock\n"
           "1,Red Dog,United States,Alaska,68.07,-162.83,165,16.6,4.6,CAam,SEDEX,shale\n")


class Minerals(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for name, member, text in (("mrds", "mrds.csv", MRDS), ("porcu", "porcu/main.csv", PORCU), ("sedznpb", "sedznpb/main.csv", SEDZNPB)):
            with zipfile.ZipFile(root / f"{name}-csv.zip", "w") as zf:
                zf.writestr(member, text)
        self.patch = override_settings(EARTH_DIR=str(root))
        self.patch.enable()
        self.got = minerals.build(root, log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_골재는_빼고_칸을_가른다(self):
        self.assertEqual(self.got["counts"], {"mrds": 3, "porcu": 1, "sedznpb": 1})      # 모래·자갈과 (0, 0) 은 빠진다
        self.assertEqual(minerals.band_of("Copper, Silver"), "min_cu")
        self.assertEqual(minerals.band_of("Tin"), "min_crit")
        self.assertEqual(minerals.band_of("Mica"), "min_ind")
        self.assertIsNone(minerals.band_of("Sand and Gravel"))

    def test_무겁고_가까운_것부터(self):
        hits = minerals.near(["min_cu", "min_au"], -68.9, -22.29, 0.1)
        self.assertEqual([(h["src"], h["name"]) for h in hits][:2], [("mrds", "Chuquicamata"), ("porcu", "Chuquicamata")])
        rows = dict(json.loads(hits[1]["rows"]))
        self.assertEqual(rows["품위"], "Cu % 0.592, Mo % 0.04, Au g/t 0.013, Ag g/t 5")
        self.assertNotIn("광상 유형", rows)                                              # 반암동의 번호뿐인 유형은 뺀다
        red = minerals.near(["min_pbzn"], -162.83, 68.07, 0.1)[0]
        self.assertEqual(dict(json.loads(red["rows"]))["광상 유형"], "SEDEX")
        self.assertTrue(red["url"].endswith("show-sedznpb.php?rec_id=1"))

    def test_타일(self):
        tile = Image.open(io.BytesIO(minerals.render_tile("min_cu", 0, 0, 0))).convert("RGBA")
        self.assertTrue(any(p[3] for p in tile.getdata()))

    def test_주소와_화면(self):
        got = self.client.get("/GSM/earth/minerals/at/", {"lon": -68.9, "lat": -22.29, "r": 0.1, "bands": "min_cu"}).json()
        self.assertEqual(dict(got["hits"][0]["rows"])["생산 규모"], "대규모")
        en = self.client.get("/GSM/earth/minerals/at/", {"lon": -68.9, "lat": -22.29, "r": 0.1, "bands": "min_cu"},
                             HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertIn("hits", en)
        self.assertEqual(self.client.get("/GSM/earth/minerals/tiles/min_au/0/0/0.png")["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/GSM/earth/minerals/tiles/min_xx/0/0/0.png").status_code, 404)
        self.assertIn('"minerals": [{"band": "min_cu"', self.client.get("/GSM/earth/").content.decode())
