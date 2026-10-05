"""대조가 건너뛰던 갈래 (wetherilli 311) — 점·모양 덩이, 화면이 곧장 부르는 타일, 우리가 자른 타일, VWorld 칸."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from viewer import ags, bas, grportal, vmme, views
from viewer.management.commands import verify_layers
from viewer.models import Layer


def png():
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), (200, 30, 30, 255)).save(buf, "PNG")
    return buf.getvalue()


class Other(TestCase):
    def setUp(self):
        for patch in (override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-vm-")),
                      override_settings(KOPRI_DIR=tempfile.mkdtemp(prefix="gsm-vm-kopri-"), VWORLD_KEY="")):
            patch.enable()
            self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def one(self, name):
        with mock.patch.object(verify_layers.time, "sleep"):
            return verify_layers.Command()._one(Layer.objects.get(name=name), set(), 1.0)

    def test_화면이_곧장_부르는_타일은_문이_한_장(self):
        ok = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=png(), elapsed=None)
        with mock.patch.object(ags.requests, "get", return_value=ok) as get, mock.patch.object(ags.usage, "paused", return_value=0):
            kind, note, remote = self.one("ags:bedrock")
        self.assertEqual((kind, remote), ("그림", True))
        self.assertIn("/MapServer/tile/", get.call_args[0][0])

    def test_content_type_이_틀려도_바이트로(self):
        odd = mock.Mock(status_code=200, headers={"content-type": "application/octet-stream"}, content=png(), url="u", elapsed=None)
        with mock.patch.object(bas.requests, "get", return_value=odd), mock.patch.object(bas.usage, "paused", return_value=0):
            self.assertEqual(self.one("bas:bedmap3_bed")[0], "그림")

    def test_점_덩이(self):
        feature = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-57, -22], [-56, -22], [-56, -21], [-57, -22]]]},
                   "properties": {"Cod_": "Q1", "Descrip_": "x"}}
        with mock.patch.object(vmme, "units", return_value=[feature]):
            kind, note, _ = self.one("vmme:geology")
        self.assertEqual((kind, note), ("그림", "points 모양 1"))

    def test_모아_둘_자료가_없으면_건너뜀(self):
        self.assertEqual(self.one("kopri:rock_antarctica")[:2], ("건너뜀", "points 자료 파일이 서버에 없다"))

    def test_VWorld_열쇠가_없으면_건너뜀(self):
        self.assertEqual(self.one("lt_l_gimsfault")[:2], ("건너뜀", "VWorld 인증키가 없다"))

    def test_격자를_받은_타일의_칸(self):
        layer = Layer.objects.get(name="bas:bedmap3_bed")
        z, x, y = verify_layers.tile_for(layer, views._layer_extra(layer))
        self.assertEqual(z, 4)                                                       # Bedmap3 격자의 처음 줌, 남극점을 품은 칸
        self.assertTrue(0 < x < 2 ** 8 and 0 < y < 2 ** 8)


class Companies(TestCase):
    def test_회사_탐사_자료는_링크_열을_묻지_않는다(self):
        self.assertNotIn("link", grportal.LAYERS["grportal:geochem_companies"]["fields"])
        self.assertIn("link", grportal.LAYERS["grportal:geochem_soil"]["fields"])
