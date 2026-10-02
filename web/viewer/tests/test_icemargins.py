"""최근 빙기의 빙상 가장자리 — NADI-1·DATED-1 (wetherilli 104). 저장소의 `data/ice_margins.json` 을 그대로 읽는다."""
import io
import tempfile

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import crs, icemargins


class Laea(SimpleTestCase):
    def test_되짚으면_제자리(self):
        for lat, lon in ((60, 10), (75, -40), (52, 100)):
            x, y = crs.latlon_to_laea_north(lat, lon)
            back = crs.laea_north_to_latlon(x, y)
            self.assertAlmostEqual(back[0], lat, places=6)
            self.assertAlmostEqual(back[1], lon, places=6)

    def test_축(self):
        # 본초 자오선은 아래(−y), 동경 90° 는 오른쪽(+x) — ESRI 의 North_Pole_Lambert_Azimuthal_Equal_Area 와 같다
        x, y = crs.latlon_to_laea_north(60, 0)
        self.assertAlmostEqual(x, 0, places=3)
        self.assertLess(y, 0)
        self.assertGreater(crs.latlon_to_laea_north(60, 90)[0], 0)


class Pick(SimpleTestCase):
    def test_반_조각_간격_안에서만(self):
        self.assertEqual(icemargins.pick(20), {"nadi": 20.0, "dated": 20.0})
        self.assertEqual(icemargins.pick(12.3), {"nadi": 12.5, "dated": 12.0})
        self.assertEqual(icemargins.pick(5), {"nadi": 5.0})          # 유라시아는 10 ka 보다 젊은 조각이 없다
        self.assertEqual(icemargins.pick(30), {})

    def test_조각(self):
        s = icemargins.stops()
        self.assertEqual((len(s["nadi"]), len(s["dated"])), (49, 16))


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ice-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_타일(self):
        r = self.client.get(reverse("viewer:earth-icemargin-tile", args=[20, 1, 0, 0]))
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        self.assertGreater(im.getpixel((170, 60))[3], 150)       # 허드슨만 둘레 — 20 ka 에는 얼음 밑이다
        self.assertEqual(r["X-GSM-Cache"], "miss")

    def test_조각이_없으면_빈_타일(self):
        r = self.client.get(reverse("viewer:earth-icemargin-tile", args=[40, 1, 0, 0]))
        self.assertEqual(Image.open(io.BytesIO(r.content)).convert("RGBA").getextrema()[3], (0, 0))
