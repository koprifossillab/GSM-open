"""세계 활성단층 — GEM Global Active Faults (wetherilli 279). 상류를 부르지 않는다 — 작은 GeoJSON 을 지어 굽는다."""
import io
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import faults

GEO = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[-122.3, 37.8], [-122.2, 37.9], [-122.1, 38.0]]},
     "properties": {"name": "Hayward", "slip_type": "Dextral", "average_dip": "(82,,)", "average_rake": "(180.0,,)",
                    "net_slip_rate": "(8.29,6.52,9.77)", "upper_seis_depth": "(0.0,,)", "lower_seis_depth": "(11.1000003814697,,)",
                    "catalog_name": "UCERF3", "dip_dir": "E"}},
    {"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [[[10, 10], [11, 11]], [[12, 12], [13, 13]]]},
     "properties": {"name": None, "slip_type": "Anticline"}},
    {"type": "Feature", "geometry": None, "properties": {"name": "empty"}}]}


class Kinds(SimpleTestCase):
    def test_갈래와_세_값(self):
        self.assertEqual(faults.kind_of("Subduction_Thrust"), "reverse")
        self.assertEqual(faults.kind_of("Dextral_Transform"), "strike")
        self.assertEqual(faults.kind_of("Sinistral-Normal"), "oblique")
        self.assertEqual(faults.kind_of(None), "other")
        self.assertEqual(faults._triple("(8.29,6.52,9.77)"), "8.29 (6.52–9.77)")
        self.assertEqual(faults._triple("(11.1000003814697,,)"), "11.1")


class Built(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        src = Path(self.tmp.name, "g.geojson")
        src.write_text(json.dumps(GEO), encoding="utf-8")
        out = Path(self.tmp.name, "earth_faults.json")
        out.write_text(json.dumps(faults.build(src)), encoding="utf-8")
        self.patch = override_settings(FAULTS_FILE=str(out))
        self.patch.enable()
        faults.data.cache_clear()

    def tearDown(self):
        self.patch.disable()
        faults.data.cache_clear()
        self.tmp.cleanup()

    def test_굽고_찾는다(self):
        doc = faults.data()
        self.assertEqual(len(doc["faults"]), 2)                                  # 기하가 없는 것은 빠진다
        self.assertEqual(len(doc["faults"][1]["parts"]), 2)
        got = faults.near(-122.2, 37.9, 0.05)
        self.assertEqual(got["name"], "Hayward")
        self.assertIn(["지진 발생 깊이 (km)", "0–11.1"], got["rows"])
        self.assertIsNone(faults.near(0, 0, 0.05))
        self.assertEqual(faults.near(10.5, 10.5, 0.05)["name"], "이름 없는 단층")

    def test_타일과_주소(self):
        tile = Image.open(io.BytesIO(faults.render_tile(3, 2, 2))).convert("RGBA")
        self.assertTrue(any(p[3] for p in tile.getdata()))
        got = self.client.get("/GSM/earth/faults/at/", {"lon": -122.2, "lat": 37.9, "z": 8}).json()
        self.assertEqual(got["fault"]["name"], "Hayward")
        self.assertEqual(self.client.get("/GSM/earth/faults/tiles/0/0/0.png")["Content-Type"], "image/png")
        self.assertIn('"faults": [{"color"', self.client.get("/GSM/earth/").content.decode())
