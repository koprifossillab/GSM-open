"""일본 셋째 판 — 지구화학도의 나머지 원소, 지질도Navi 의 공중 자력 편집도 셋 (wetherilli 266). 상류는 바꿔 끼운다."""
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import gsj, views


class Door(SimpleTestCase):
    def test_원소_53_가지(self):
        names = [n for n in gsj.GSJOWS_LAYERS if n.startswith("gsjows:geochem:")]
        self.assertEqual(len(names), 53)
        self.assertEqual(len(set(gsj.GEOCHEM) | set(gsj.GEOCHEM_MORE)), 53)

    def test_자력은_Navi_타일과_범례_그림(self):
        self.assertEqual(gsj.gsjows_tiles("gsjows:magnetic_japan"),
                         "https://tiles.gsj.jp/tiles/geomap/TH_23magne/{z}/{x}/{y}.png")
        self.assertEqual(gsj.gsjows_tiles("gsjows:geochem:Cu"), "")
        jpeg = mock.Mock(status_code=200, headers={"content-type": "image/jpeg"}, content=b"jpg", url="…")
        with mock.patch.object(gsj.requests, "get", return_value=jpeg) as get, \
             mock.patch.object(gsj.usage, "record"), mock.patch.object(gsj.usage, "paused", return_value=0):
            content, ctype = gsj.gsjows_get_legend("gsjows:magnetic_japan")
        self.assertEqual((content, ctype), (b"jpg", "image/jpeg"))
        self.assertTrue(get.call_args.args[0].endswith("/pict_data/orgsize_816_legend_1088.jpg"))


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        self.rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}

    def test_자력은_브라우저가_곧장(self):
        group, layer = self.rows["gsjows:magnetic_japan"]
        self.assertEqual(group["region"], "japan")
        self.assertTrue(layer["tiles"].startswith("https://tiles.gsj.jp/"))
        self.assertEqual((layer["maxZoom"], layer["queryable"]), (8, False))

    def test_지구화학도는_WMS(self):
        layer = self.rows["gsjows:geochem:Zr"][1]
        self.assertEqual((layer["projection"], layer.get("tiles")), ("EPSG:3857", None))

    @override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-jp-more-"))
    def test_범례_길(self):
        jpeg = mock.Mock(status_code=200, headers={"content-type": "image/jpeg"}, content=b"jpg", url="…")
        with mock.patch.object(gsj.requests, "get", return_value=jpeg), \
             mock.patch.object(gsj.usage, "record"), mock.patch.object(gsj.usage, "paused", return_value=0):
            got = self.client.get("/GSM/legend/", {"layer": "gsjows:magnetic_japan"})
        self.assertEqual((got.status_code, got["Content-Type"]), (200, "image/jpeg"))
