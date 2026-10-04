"""지각 응력 — World Stress Map 2025 (wetherilli 273). 상류를 부르지 않는다 — 작은 CSV 를 지어 굽는다."""
import io
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from PIL import Image

from viewer import stress

CSV = ("﻿ID,ISC_ID,SITE,LAT,LON,AZI,TYPE,DEPTH,QUALITY,REGIME,LOCALITY,COUNTRY,DATE,TIME,NUMBER,SD,TOT_LEN,VENT,TOP,BOT,"
       "ANISOTROPY,METHOD,S1AZ,S1PL,S2AZ,S2PL,S3AZ,S3PL,MAG_TYPE,EQ_MAG,CRUST,REF1,REF2,REF3,REF4,REF5,REF6,COMMENT,PLATE,DIST\n"
       "wsm1,,S,36.0,138.0,95,FMS,10.0,C,TF,Chubu,Japan,20110311,,,,,,,,,,,,,,,,Mw,6.1,True,AAA2011,,,,,,,PA,1\n"
       "wsm2,,S,36.0,138.02,20,BO,2.5,A,SS,Well X,Japan,,,,,,,,,,,,,,,,,,,True,BBB2000,,,,,,,PA,1\n"
       "wsm3,,S,10.0,10.0,999,FMS,5,C,U,,,,,,,,,,,,,,,,,,,,,True,,,,,,,,AF,1\n"
       "wsm4,,S,11.0,11.0,45,HF,0.3,E,NF,,,,,,,,,,,,,,,,,,,,,True,,,,,,,,AF,1\n")


class Stress(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "w.csv").write_text(CSV, encoding="utf-8")
        self.patch = override_settings(EARTH_DIR=self.tmp.name)
        self.patch.enable()
        self.got = stress.build(Path(self.tmp.name, "w.csv"), log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_E_와_방향_없는_것은_뺀다(self):
        self.assertEqual(self.got["rows"], 2)
        self.assertEqual(self.got["skipped"]["품질 E"], 1)
        self.assertEqual(self.got["skipped"]["방향 없음"], 1)

    def test_누른_자리는_가깝고_좋은_것부터(self):
        hits = stress.near(138.0, 36.0, 0.1)
        self.assertEqual([h["id"] for h in hits], ["wsm1", "wsm2"])
        self.assertEqual((hits[0]["azi"], hits[0]["regime"], hits[0]["mag"]), (95.0, "TF", "6.1 Mw"))

    def test_막대(self):
        tile = Image.open(io.BytesIO(stress.render_tile(4, 28, 4))).convert("RGBA")
        self.assertTrue(any(p[3] for p in tile.getdata()))
        self.assertEqual(stress.colour("SS"), (0x1a, 0x9e, 0x4b))

    def test_주소와_화면(self):
        got = self.client.get("/GSM/earth/stress/at/", {"lon": 138.0, "lat": 36.0, "r": 0.1}).json()
        first = dict(got["hits"][0]["rows"])
        self.assertEqual((first["최대 수평 응력 방향"], first["응력 체제"], first["측정법"]), ("N95°E", "역단층형", "단일 지진 초점 메커니즘"))
        self.assertEqual(self.client.get("/GSM/earth/stress/tiles/0/0/0.png")["Content-Type"], "image/png")
        self.assertIn('"stress": [{"color"', self.client.get("/GSM/earth/").content.decode())
