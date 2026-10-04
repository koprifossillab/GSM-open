"""판 경계·세계 지질구 — Hasterok 2022 (wetherilli 272). 상류를 부르지 않는다."""
import io
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import tectonics


class Simplify(SimpleTestCase):
    def test_곧은_선의_가운데를_덜어_낸다(self):
        pts = [(0, 0), (1, 0.001), (2, 0), (3, 1)]
        self.assertEqual(tectonics.simplify(pts, 0.01), [(0, 0), (2, 0), (3, 1)])
        self.assertEqual(tectonics.simplify([(0, 0), (1, 1)]), [(0, 0), (1, 1)])

    def test_닫힌_고리가_너무_작으면_버린다(self):
        self.assertEqual(tectonics._flat([(0, 0), (0.001, 0), (0, 0)], True), [])


class Repo(SimpleTestCase):
    def test_저장소의_파일(self):
        self.assertTrue(tectonics.available())
        doc = tectonics.data()
        self.assertGreater(len(doc["provinces"]), 900)
        self.assertTrue({b["type"] for b in doc["boundaries"]} <= set(tectonics.BOUNDARY_TYPES))
        self.assertTrue({p["type"] for p in doc["provinces"]} - {""} <= set(tectonics.PROVINCE_TYPES))

    def test_누른_자리(self):
        got = tectonics.province_at(127.0, 37.5)
        self.assertEqual(got["name"], "Gyeonggi Massif")
        self.assertIn(["갈래", "조산대"], got["rows"])
        self.assertEqual(tectonics.province_at(127.0, 37.5, "en")["rows"][0], [got_en_key(), "Orogenic belt"])

    def test_타일(self):
        for layer in ("provinces", "boundaries"):
            tile = Image.open(io.BytesIO(tectonics.render_tile(layer, 0, 1, 0))).convert("RGBA")
            self.assertTrue(any(p[3] for p in tile.getdata()), layer)


def got_en_key():
    from viewer import i18n
    return i18n.PROP_EN.get("갈래", "갈래")


class Views(TestCase):
    def test_주소와_화면(self):
        r = self.client.get("/GSM/earth/tectonics/tbound/0/0/0.png")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
        self.assertEqual(self.client.get("/GSM/earth/tectonics/plates/0/0/0.png").status_code, 404)
        got = self.client.get("/GSM/earth/tectonics/at/", {"lon": 127, "lat": 37.5}).json()
        self.assertEqual(got["province"]["name"], "Gyeonggi Massif")
        page = self.client.get("/GSM/earth/").content.decode()
        self.assertIn('"tectonics": {"boundaries"', page)
        with tempfile.TemporaryDirectory() as tmp, override_settings(TECTONICS_FILE=str(Path(tmp, "x.json"))):
            tectonics.data.cache_clear()
            try:
                self.assertNotIn('"tectonics": {"boundaries"', self.client.get("/GSM/earth/").content.decode())
            finally:
                tectonics.data.cache_clear()
