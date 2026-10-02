"""시료 고도를 국가기준점과 견주는 명령 (P03 §7, wetherilli 170). 상류를 타지 않는다."""
import io
import json
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase

from viewer.management.commands import check_elevation as ce


class CheckElevationTests(SimpleTestCase):
    def test_기준점_파일은_표고와_자리를_갖는다(self):
        data = json.loads((settings.REPO_DIR / "data" / "ngii_benchmarks.json").read_text(encoding="utf-8"))
        self.assertIn("국토지리정보원", data["meta"]["source"])
        self.assertGreaterEqual(len(data["points"]), 20)
        for p in data["points"]:
            self.assertTrue(33 < p["lat"] < 39 and 124 < p["lon"] < 132, p["no"])
            self.assertIsInstance(p["height"], float)

    def test_둘레는_사방으로_같은_거리(self):
        north, south, east, west = ce.ring(37.0, 127.0, 100.0)
        self.assertAlmostEqual((north[0] - south[0]) * 111320 / 2, 100.0, places=3)
        self.assertAlmostEqual(east[1] - 127.0, 127.0 - west[1])
        self.assertGreater(east[1] - 127.0, north[0] - 37.0)            # 경도 1° 가 더 짧다

    def test_셈은_평지를_따로(self):
        s = ce.summarize([(3.0, 2.0), (-4.0, 5.0), (-20.0, 30.0)])
        self.assertEqual(s["all"]["n"], 3)
        self.assertEqual(s["all"]["within"], 2)
        self.assertEqual(s["all"]["worst"], -20.0)
        self.assertEqual(s["flat"]["n"], 2)
        self.assertAlmostEqual(s["flat"]["rms"], (12.5) ** 0.5)

    def test_명령은_읽은_값으로_차를_적는다(self):
        def fake(points):
            return {k: (100.0 if "#" not in k else 101.0, "aws-terrarium-z12") for k in points}
        out = io.StringIO()
        with mock.patch.object(ce.elevation, "elevations", side_effect=fake):
            call_command("check_elevation", stdout=out)
        text = out.getvalue()
        self.assertIn("전부: ±15 m 안", text)
        self.assertIn("aws-terrarium-z12", text)
