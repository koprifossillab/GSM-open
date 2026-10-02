"""지명·강·호수·빙하 — Natural Earth 10 m (wetherilli 102). 저장소의 `data/earth_*.json` 을 그대로 읽는다."""
import io
import struct
import tempfile

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import naturalearth
from viewer.management.commands import build_natural_earth as build


class Search(SimpleTestCase):
    def test_한국어로(self):
        top = naturalearth.search("바이칼")[0]
        self.assertEqual((top["title"], top["kind"]), ("바이칼호", "호수"))

    def test_영어로도_찾고_괄호로_곁들인다(self):
        self.assertEqual(naturalearth.search("nile")[0]["title"], "나일강 (Nile)")
        self.assertEqual(naturalearth.search("nile", "en")[0]["title"], "Nile")

    def test_이름표는_큰_것부터(self):
        rows = naturalearth.labels()
        self.assertEqual(rows[0][3], 0)
        self.assertIn("알프스산맥", [r[0] for r in rows])
        self.assertNotIn("서울특별시", [r[0] for r in rows])          # 도시는 찾기만 한다


class Parse(SimpleTestCase):
    def test_dbf(self):
        head = struct.pack("<4xIHH20x", 1, 32 + 32 + 1, 1 + 5)
        field = b"NAME".ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([5]) + b"\0" * 15
        data = head + field + b"\x0d" + b" Alps\0"[:6]
        self.assertEqual(build.dbf(data), [{"name": "Alps"}])

    def test_이름표_자리는_고리_안(self):
        # ㄷ 자 고리 — 무게중심이 고리 밖에 선다. 가까운 꼭짓점으로 옮긴다
        ring = [(0, 0), (0, 10), (10, 10), (10, 8), (2, 8), (2, 2), (10, 2), (10, 0)]
        lon, lat = build.anchor([ring])
        self.assertIn((lon, lat), ring)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ne-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_찾기(self):
        got = self.client.get(reverse("viewer:earth-places"), {"q": "알프스"}).json()["results"]
        self.assertEqual(got[0]["title"], "알프스산맥")

    def test_빙하_타일(self):
        r = self.client.get(reverse("viewer:earth-ne-tile", args=["ice", 0, 0, 0]))
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        self.assertGreater(im.getpixel((200, 250))[3], 150)       # 남극 대륙
        self.assertEqual(im.getpixel((100, 128))[3], 0)            # 대서양
        self.assertEqual(self.client.get(reverse("viewer:earth-ne-tile", args=["ice", 8, 0, 0])).status_code, 404)

    def test_강_타일(self):
        r = self.client.get(reverse("viewer:earth-ne-tile", args=["water", 1, 3, 0]))
        self.assertGreater(Image.open(io.BytesIO(r.content)).convert("RGBA").getextrema()[3][1], 200)

    def test_이름표(self):
        rows = self.client.get(reverse("viewer:earth-labels"), HTTP_ACCEPT_LANGUAGE="ko").json()["labels"]
        self.assertTrue(rows)
