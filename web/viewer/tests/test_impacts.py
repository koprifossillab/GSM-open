"""충돌구·거대 화성암 지대 (wetherilli 283). 상류를 부르지 않는다 — 작은 SPARQL 답과 LIP 를 지어 쓴다."""
import io
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import impacts, paleo

WD = {"results": {"bindings": [
    {"c": {"value": "http://www.wikidata.org/entity/Q55816"}, "coord": {"value": "Point(-89.516666666 21.4)"},
     "diam": {"value": "180"}, "age": {"value": "-66000000-01-01T00:00:00Z"}, "cLabel": {"value": "Chicxulub crater"},
     "countryLabel": {"value": "Mexico"}},
    {"c": {"value": "http://www.wikidata.org/entity/Q55816"}, "coord": {"value": "Point(-89.516666666 21.4)"},
     "cLabel": {"value": "Chicxulub crater"}, "countryLabel": {"value": "Mexico"}},
    {"c": {"value": "http://www.wikidata.org/entity/Q1"}, "coord": {"value": "Point(10 50)"}, "cLabel": {"value": "Q1"}}]}}


class Read(SimpleTestCase):
    def test_위키데이터(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "wd.json")
            p.write_text(json.dumps(WD), encoding="utf-8")
            got = impacts.read_wikidata(p)
        self.assertEqual(len(got), 2)                                            # 같은 항목은 하나로
        self.assertEqual((got[0]["name"], got[0]["km"], got[0]["ma"]), ("Chicxulub crater", 180.0, 66.0))
        self.assertEqual(got[1]["name"], "")                                     # 이름이 번호뿐이면 비운다

    def test_기의_색(self):
        self.assertEqual(impacts.period_of(66)[1], "#7fc64e")
        self.assertEqual(impacts.period_of(250)[1], "#812b92")
        self.assertEqual(impacts.period_of(10)[1], "#f9f97f")


class Repo(TestCase):
    def test_저장소의_파일(self):
        self.assertTrue(impacts.available())
        self.assertEqual(impacts.impact_near(-89.5, 21.4, 0.1)["name"], "Chicxulub crater")
        self.assertIn("DECCAN", impacts.lip_at(74, 19)["name"])
        self.assertIsNone(impacts.lip_at(-150, 0))

    def test_그때의_지구로_옮긴다(self):
        if paleo.model() is None:
            self.skipTest("판 회전이 없다")
        today = impacts.lips_at(0.0)
        then = impacts.lips_at(250.0)                                          # 시베리아 트랩은 251·248 Ma — 250 이면 앞의 것만
        self.assertTrue(then and all(i["ma"] >= 250 and i["pid"] is not None for i, _ in then))
        self.assertLess(len(then), len(today))
        siberia = [polys for i, polys in then if "SIBERIAN" in i["name"]]
        self.assertTrue(siberia)
        lon0 = next(i for i in impacts.data()["lips"] if "SIBERIAN" in i["name"])["polys"][0][0][0]
        self.assertNotAlmostEqual(siberia[0][0][0][0], lon0, delta=1.0)           # 자리가 옮겨졌다

    def test_타일과_주소(self):
        for layer, ma in (("impacts", 0), ("lips", 0), ("lips", 252)):
            tile = Image.open(io.BytesIO(impacts.render_tile(layer, float(ma), 0, 1, 0))).convert("RGBA")
            self.assertTrue(any(p[3] for p in tile.getdata()), (layer, ma))
        self.assertEqual(self.client.get("/GSM/earth/impacts/lips/252/0/1/0.png")["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/GSM/earth/impacts/impacts/10/0/1/0.png").status_code, 404)   # 충돌구는 오늘만
        got = self.client.get("/GSM/earth/impacts/at/", {"lon": -89.5, "lat": 21.4, "z": 6, "layer": "impacts"}).json()
        self.assertEqual(got["name"], "Chicxulub crater")
        self.assertIn('"impacts": {"impacts"', self.client.get("/GSM/earth/").content.decode())
