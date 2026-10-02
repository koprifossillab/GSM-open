"""지각 두께 — CRUST 2.0 (wetherilli 101). 저장소의 `data/crust2_thickness.json` 을 그대로 읽는다."""
import io
import tempfile

from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import crust
from viewer.management.commands import build_crust


class Grid(SimpleTestCase):
    def test_자리마다(self):
        self.assertGreater(crust.at(88, 32), 65)          # 티베트 — 가장 두껍다
        self.assertLess(crust.at(-150, 0), 10)             # 태평양 — 바다 지각
        self.assertIsNone(crust.at(0, -89.5))               # 남극점 둘레는 빈 칸
        self.assertEqual(crust.at(-180, 10), crust.at(180, 10))

    def test_색은_얇은_파랑에서_두꺼운_갈색으로(self):
        self.assertEqual(crust.colour(0), (8, 48, 107))
        self.assertEqual(crust.colour(100), (102, 37, 6))
        self.assertEqual(len(crust.legend()), 8)


class FakeZ:
    """h5py 데이터셋처럼 `[j, 슬라이스]` 로 읽히는 2 분 격자."""
    shape = (5401, 10801)

    def __getitem__(self, key):
        j, cols = key
        return [float("nan") if j < 30 else 7.25] * len(range(*cols.indices(10801)))


class Build(SimpleTestCase):
    def test_1도_칸의_가운데를_뽑는다(self):
        lat = [-90 + k / 30 for k in range(5401)]
        lon = [-180 + k / 30 for k in range(10801)]
        rows = build_crust.sample(FakeZ(), lat, lon)
        self.assertEqual((len(rows), len(rows[0])), (180, 360))
        self.assertEqual(rows[0][0], 72)                    # 북쪽 줄부터, 0.1 km
        self.assertIsNone(rows[-1][0])                      # 남쪽 끝 줄은 비었다

    def test_격자의_꼴이_다르면_멈춘다(self):
        with self.assertRaises(CommandError):
            build_crust.sample(FakeZ(), [0] * 5401, [0] * 10801)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-crust-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_타일(self):
        r = self.client.get(reverse("viewer:earth-crust-tile", args=[0, 1, 0]))
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        self.assertEqual(im.getpixel((10, 10))[3], 255)
        self.assertEqual(self.client.get(reverse("viewer:earth-crust-tile", args=[6, 0, 0])).status_code, 404)

    def test_누르면_두께(self):
        data = self.client.get(reverse("viewer:earth-crust-at"), {"lon": 88, "lat": 32}).json()
        self.assertTrue(data["text"].startswith("약 7"), data["text"])
        self.assertEqual(self.client.get(reverse("viewer:earth-crust-at"), {"lon": 0, "lat": -89.5}).json()["km"], None)

    def test_화면에_범례를_싣는다(self):
        self.assertContains(self.client.get(reverse("viewer:earth")), '"crust": [{"name": "0–10 km"')
