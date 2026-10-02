"""지구의 높이 그래프 (wetherilli 109). 타일을 받지 않는다 — `_from_tiles` 를 갈아 끼운다."""
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import crs, elevation


class GreatCircle(SimpleTestCase):
    def test_고르게_꼭짓점을_지나며(self):
        pts = crs.great_circle_points([(0, 0), (1, 0), (1, 1)], 21)
        self.assertEqual(pts[0][:2], (0.0, 0.0))
        self.assertAlmostEqual(pts[-1][0], 1.0, places=6)
        self.assertAlmostEqual(pts[-1][1], 1.0, places=6)
        self.assertTrue(any(abs(lon - 1) < 1e-9 and abs(lat) < 1e-9 for lon, lat, _ in pts))   # 꺾인 자리
        self.assertAlmostEqual(pts[-1][2], 2 * 111194.9, delta=5)                            # 1° 둘
        self.assertEqual(len(pts), 21)


class Profile(SimpleTestCase):
    def test_일본은_국토지리원_나머지는_AWS(self):
        def fake(points, z, fetch, decode):
            return {k: (1000.0 if fetch is elevation.gsi_tile else 100.0) for k in points}
        with mock.patch.object(elevation, "_from_tiles", side_effect=fake) as tiles:
            got = elevation.profile([(135.0, 35.0), (127.0, 37.5)], 64)
        self.assertEqual(got["elev"][0], 1000.0)          # 교토 둘레
        self.assertEqual(got["elev"][-1], 100.0)          # 서울
        self.assertEqual(len(got["dist"]), 64)
        zooms = {c.args[1] for c in tiles.call_args_list}
        self.assertTrue(all(z <= elevation.GSI_ZOOM for z in zooms))

    def test_85도_너머는_비운다(self):
        with mock.patch.object(elevation, "_from_tiles", side_effect=lambda pts, *a: {k: 1.0 for k in pts}):
            got = elevation.profile([(0, 86), (10, 86)], 8)
        self.assertEqual(set(got["elev"]), {None})


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-prof-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_선(self):
        with mock.patch.object(elevation, "_from_tiles", side_effect=lambda pts, *a: {k: 5.0 for k in pts}):
            data = self.client.get(reverse("viewer:elevation-profile"),
                                   {"line": "126.9,37.5;127.0,37.6", "n": 16}).json()
        self.assertEqual(data["elev"], [5.0] * 16)
        self.assertEqual(self.client.get(reverse("viewer:elevation-profile"), {"line": "126.9,37.5"}).status_code, 400)


class PlanetProfiles(TestCase):
    """화성·수성의 높이 그래프 (wetherilli 148) — 달(100)의 틀에 몸만 바꿨다. Trek 을 부르지 않는다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-planet-prof-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_몸마다_반지름과_표고(self):
        from viewer import trek
        for body, radius, read, source in (("mars", trek.MARS_RADIUS, "mars_values", trek.MARS_ELEV_SOURCE),
                                           ("mercury", trek.MERCURY_RADIUS, "mercury_values", trek.MERCURY_ELEV_SOURCE)):
            with self.subTest(body=body), mock.patch.object(trek, read, side_effect=lambda pts: {k: -100.0 for k in pts}):
                got = trek.profile([(0, 0), (1, 0)], 11, body)
            self.assertEqual(got["source"], source)
            self.assertEqual(got["elev"], [-100.0] * 11)
            # 1° 는 그 몸의 반지름으로 잰 거리다
            self.assertAlmostEqual(got["dist"][-1], radius * 3.141592653589793 / 180, delta=1)

    def test_주소(self):
        from viewer import trek
        with mock.patch.object(trek, "mercury_values", side_effect=lambda pts: {k: 300.0 for k in pts}) as read:
            url = reverse("viewer:mercury-profile")
            data = self.client.get(url, {"line": "-31.5,-11.3;-30,-10", "n": 8}).json()
            self.client.get(url, {"line": "-31.5,-11.3;-30,-10", "n": 8})
        self.assertEqual(data["elev"], [300.0] * 8)
        self.assertEqual(read.call_count, 1)                          # 같은 선은 캐시가 낸다
        with mock.patch.object(trek, "mars_values", side_effect=lambda pts: {}):
            data = self.client.get(reverse("viewer:mars-profile"), {"line": "137.4,-4.6;137.5,-4.5", "n": 4}).json()
        self.assertEqual(data["elev"], [None] * 4)
        self.assertEqual(self.client.get(reverse("viewer:mars-profile"), {"line": "137.4,-4.6"}).status_code, 400)
