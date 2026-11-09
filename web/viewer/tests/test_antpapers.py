"""남극 논문 두 편의 벡터 레이어 (wetherilli 435). 저장소의 파일만 읽는다 — 상류를 부르지 않는다."""
import json
import math
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import antpapers, doors


class Bake(SimpleTestCase):
    def test_xyz_의_선(self):
        text = "/Line Costa\n -69.8 73.4\n -69.7 73.5\nLine AUR_1_E\n-80.6 124.1\n-80.5 124.0\n\nLine X\n-1 2\n"
        got = antpapers.read_xyz_lines(text)
        self.assertEqual([n for n, _ in got], ["Costa", "AUR_1_E"])          # 점 하나뿐인 선은 버린다
        self.assertEqual(got[1][1][0], [124.1, -80.6])                       # 경도, 위도

    def test_소원의_반지름은_중앙값(self):
        pole = (-84.0, 130.0)
        pts = [antpapers._dest(*pole, az, 10.0) for az in range(0, 90, 5)]
        line, km = antpapers.small_circle(pole, pts, pad=0)
        self.assertAlmostEqual(km, math.radians(10) * 6371, delta=2)
        self.assertAlmostEqual(antpapers._dist_az(*pole, line[-1][1], line[-1][0])[0], 10.0, places=3)

    def test_등고선(self):
        n = 20
        z = [[100.0 - math.hypot(c - 10, r - 10) * 10 for c in range(n)] for r in range(n)]   # 가운데가 솟은 원뿔
        lines = antpapers.contour(z, 52.5)
        self.assertEqual(len(lines), 1)
        ring = lines[0]
        self.assertAlmostEqual(ring[0][0], ring[-1][0], places=6)            # 닫힌 고리
        for c, r in ring:
            self.assertAlmostEqual(math.hypot(c - 10, r - 10), 4.75, delta=0.3)
        self.assertLess(len(antpapers.simplify(ring, 0.3)), len(ring))

    def test_빈칸은_건너뛴다(self):
        z = [[0.0, 0.0, None], [0.0, 10.0, None], [0.0, 0.0, None]]
        self.assertTrue(all(c <= 1.5 for line in antpapers.contour(z, 5.0) for c, _ in line))

    def test_fig2a(self):
        doc = {"features": [{"geometry": {"type": "MultiLineString", "coordinates": [[[1, -70], [2, -71]], [[3, -70], [4, -70]]]},
                             "properties": {"name": "Fan6S", "kind": "fan"}},
                            {"geometry": {"type": "LineString", "coordinates": [[1, -70], [2, -71]]},
                             "properties": {"name": "?", "kind": "모름"}}]}
        rows = antpapers.convert_fig2a(json.dumps(doc).encode())["antpapers:eafbp_fig2a"]
        self.assertEqual([r[0] for r in rows], ["fan", "fan", "other"])
        with self.assertRaises(antpapers.AntPapersError):
            antpapers.convert_fig2a(b'{"features": []}')

    def test_zip_이_아니면_멈춘다(self):
        with self.assertRaises(antpapers.AntPapersError):
            antpapers.convert_eafbp(b"not a zip")


class Serve(TestCase):
    def test_저장소의_파일(self):
        doc = json.loads(antpapers.path().read_text(encoding="utf-8"))
        self.assertTrue(set(doc["layers"]) <= set(antpapers.CLASSES))
        self.assertEqual(len(doc["layers"]["antpapers:eafbp_faults"]), 289)
        self.assertLess(antpapers.path().stat().st_size, 1_200_000)

    def test_씨앗의_레이어는_다_파일에_있다(self):
        from django.conf import settings
        seed = json.loads(settings.ANTPAPERS_CATALOG_SEED.read_text(encoding="utf-8"))
        names = [r["name"] for r in seed["레이어"]]
        self.assertEqual(len(names), 16)
        self.assertTrue(all(antpapers.available(n) for n in names))

    def test_분지_이름표(self):
        body = json.loads(self.client.get("/GSM/points/?layer=antpapers:eafbp_basins").content)
        self.assertEqual(body["labelBy"], "basin")
        self.assertEqual({r["code"] for r in body["legend"]}, {"single", "bisect"})
        self.assertEqual(body["features"][0]["properties"]["basin"], "AUR_1")

    def test_오일러_극(self):
        body = json.loads(self.client.get("/GSM/points/?layer=antpapers:eafbp_poles").content)
        self.assertEqual([f["geometry"]["coordinates"] for f in body["features"]][0], [129.9, -86.4])
        self.assertEqual(body["legend"][0]["shape"], "star")

    def test_고지형_등고선(self):
        body = json.loads(self.client.get("/GSM/points/?layer=antpapers:gernon_34ma").content)
        codes = {f["properties"]["code"] for f in body["features"]}
        self.assertEqual(codes, {"0", "1000", "1500", "2000"})
        self.assertEqual(body["features"][0]["properties"]["age"], "34 Ma")
        self.client.cookies["gsm_lang"] = "en"
        en = json.loads(self.client.get("/GSM/points/?layer=antpapers:gernon_34ma").content)
        self.assertIn("1,500 m — threshold for ice-cap growth", [r["label"] for r in en["legend"]])

    def test_파일이_없으면_503(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(ANTARCTIC_PAPERS_FILE=Path(tmp) / "none.json"):
            self.assertEqual(self.client.get("/GSM/points/?layer=antpapers:eafbp_faults").status_code, 503)

    def test_문이_아니다(self):
        self.assertTrue(doors.specs()["antpapers"].local)
