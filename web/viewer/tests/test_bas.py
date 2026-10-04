"""남극 — BAS 의 Bedmap3 타일·범례 (wetherilli 261). 상류를 부르지 않는다."""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import bas

LEGEND = {"layers": [{"layerId": 0, "legend": [
    {"label": "-4,999.999999 - -4,000", "imageData": "AAAA", "contentType": "image/png"},
    {"label": "2,000.000001 - 4,700", "imageData": "BBBB", "contentType": "image/png"},
    {"label": "no image"}]}]}


class Door(SimpleTestCase):
    def test_칸_이름을_다듬는다(self):
        self.assertEqual(bas.tidy_label("-4,999.999999 - -4,000"), "-5,000 – -4,000 m")
        self.assertEqual(bas.tidy_label("1.001 - 500"), "1 – 500 m")
        self.assertEqual(bas.tidy_label("Water"), "Water")

    def test_격자는_Esri_극_격자(self):
        g = bas.grid("bas:bedmap3_bed")
        self.assertEqual(len(g["resolutions"]), 14)                       # 줌 0–13
        self.assertAlmostEqual(g["resolutions"][13] * 2 ** 13, bas.RESOLUTION0)
        self.assertEqual(g["origin"], [-30635955.4472718, 30635955.4472718])
        self.assertEqual(g["minZoom"], 4)                                  # 그 밑은 캐시가 없다
        self.assertTrue(bas.tile_url("bas:bedmap3_surface").endswith("/Bedmap3_surface/MapServer/tile/{z}/{y}/{x}"))

    def test_범례는_한_번_받아_담는다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(bas.requests, "get", return_value=mock.Mock(status_code=200, json=lambda: LEGEND,
                                                                                content=b"{}", url="u")) as get:
            rows = bas.legend_rows("bas:bedmap3_bed")
            again = bas.legend_rows("bas:bedmap3_bed")
        self.assertEqual([r["lithology"] for r in rows], ["-5,000 – -4,000 m", "2,000 – 4,700 m"])
        self.assertEqual(rows[0]["swatch"], "data:image/png;base64,AAAA")
        self.assertEqual(rows, again)
        self.assertLessEqual(get.call_count, 2)


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def test_남극_탭에_선다(self):
        from viewer import views
        rows = {l["name"]: dict(l, region=g["region"]) for g in views._catalog("ko") for l in g["layers"]}
        row = rows["bas:bedmap3_bed"]
        self.assertEqual(row["region"], "antarctica")
        self.assertTrue(row["tiles"].startswith("https://tiles.arcgis.com/"))
        self.assertEqual((row["queryable"], row["legend"], row["legendUrl"]), (False, "list", "list/legend/"))
        self.assertIn("grid", row)

    def test_목록_범례(self):
        with mock.patch.object(bas, "legend_rows", return_value=[{"symbol": "", "lithology": "0 – 500 m", "age": "",
                                                                  "color": "transparent", "swatch": "data:x"}]):
            got = self.client.get("/GSM/list/legend/", {"layer": "bas:bedmap3_thickness"}).json()
        self.assertEqual(got["rows"][0]["lithology"], "0 – 500 m")

    def test_화면의_손(self):
        js = (Path(__file__).resolve().parents[1] / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        self.assertIn("bas: { source: esriGridSource, info: null }", js)
