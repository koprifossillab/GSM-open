"""세계 빙하 — RGI 7.0 빙하 속성 (wetherilli 289). 상류를 부르지 않는다 — 작은 CSV 를 지어 굽는다."""
import io
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from PIL import Image

from viewer import glaciers

CSV = ('"rgi_id","o1region","o2region","cenlon","cenlat","area_km2","surge_type","term_type","glac_name","zmin_m","zmax_m","zmed_m","slope_deg","aspect_deg","src_date"\n'
       '"RGI2000-v7.0-G-01-1","01","01-05",-139.5,60.0,3000.0,0,1,"Hubbard Glacier",0,4800,1500,8.2,180,"2010-08-01T00:00:00"\n'
       '"RGI2000-v7.0-G-01-2","01","01-05",-139.45,60.02,0.2,0,9,"",900,1100,1000,20,90,"2010-08-01T00:00:00"\n'
       '"RGI2000-v7.0-G-11-3","11","11-01",7.9,46.5,80.0,3,9,"Grosser Aletsch,",1500,4100,3000,10,170,"2003-01-01T00:00:00"\n'
       '"bad","11","11-01",,,1,0,9,"",,,,,,""\n')


class Glaciers(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "g.csv").write_text(CSV, encoding="utf-8")
        self.patch = override_settings(EARTH_DIR=self.tmp.name)
        self.patch.enable()
        self.got = glaciers.build(Path(self.tmp.name, "g.csv"), log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽기(self):
        self.assertEqual((self.got["rows"], self.got["skipped"]), (3, 1))

    def test_큰_빙하_위를_누르면_그것이_먼저(self):
        hits = glaciers.near(-139.45, 60.02, 0.01)
        self.assertEqual(hits[0]["name"], "Hubbard Glacier")             # 작은 빙하의 가운데가 더 가까워도 큰 빙하의 원 안이다

    def test_줌_3_밑은_빈_타일(self):
        blank = Image.open(io.BytesIO(glaciers.render_tile(2, 1, 0))).convert("RGBA")
        self.assertFalse(any(p[3] for p in blank.getdata()))
        tile = Image.open(io.BytesIO(glaciers.render_tile(3, 1, 1))).convert("RGBA")   # 알래스카
        self.assertTrue(any(p[3] for p in tile.getdata()))

    def test_주소와_화면(self):
        got = self.client.get("/GSM/earth/glaciers/at/", {"lon": 7.9, "lat": 46.5, "z": 8}).json()
        first = got["hits"][0]
        self.assertEqual(first["name"], "Grosser Aletsch")                # 끝의 쉼표를 뗀다
        self.assertIn(["서지", "서지 관측"], first["rows"])
        self.assertEqual(self.client.get("/GSM/earth/glaciers/tiles/3/1/1.png")["Content-Type"], "image/png")
        self.assertIn('"glaciers": [{"color"', self.client.get("/GSM/earth/").content.decode())
