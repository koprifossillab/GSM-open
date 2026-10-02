"""미리 데우기와 호출 세기.

`tilegrid` 의 요점은 **브라우저와 한 글자까지 같은 타일**을 셈하는 것이다.
아래 `BBOX` 는 2026-09-27 에 브라우저(OpenLayers 9.2.4)가 실제로 부른 값이다.
옆 타일의 오른쪽 끝(`…706`)과 이 타일의 왼쪽 끝(`…704`)이 끝자리가 다르다 —
곱하는 차례가 달라서다. 그 차이까지 맞아야 캐시가 맞는다.
"""
from django.test import SimpleTestCase, TestCase

from viewer import tilegrid, usage


class Grid(SimpleTestCase):
    SEEN = {
        (9, 436, 200): "14088873.053523686,4304933.433021126,14167144.570487706,4383204.9499851465",
        (10, 874, 401): "14167144.570487704,4304933.433021126,14206280.328969715,4344069.191503136",
        (8, 218, 101): "14088873.053523686,4070118.8821290657,14245416.087451726,4226661.916057107",
    }

    def test_브라우저가_부른_범위와_한_글자까지_같다(self):
        for (z, x, y), bbox in self.SEEN.items():
            self.assertEqual(tilegrid.wms_params("L", z, x, y)["bbox"], bbox, (z, x, y))

    def test_정수는_점을_붙이지_않는다(self):
        """자바스크립트는 0 을 `0` 으로 적는다. 파이썬은 `0.0` 이다."""
        self.assertEqual(tilegrid.js_number(0.0), "0")
        self.assertEqual(tilegrid.js_number(-20037508.342789244), "-20037508.342789244")
        z, x, y = 1, 1, 0                                   # 왼쪽 끝이 정확히 0
        self.assertTrue(tilegrid.wms_params("L", z, x, y)["bbox"].startswith("0,"))

    def test_범위를_덮는_타일(self):
        tiles = list(tilegrid.tiles_for((127.25, 36.33, 127.5, 36.5), 13))
        self.assertTrue(tiles)
        self.assertTrue(all(z == 13 for z, _, _ in tiles))
        # 대전(127.36, 36.37) 을 품은 타일이 들어 있다
        self.assertIn(13, {z for z, _, _ in tiles})

    def test_브라우저와_같은_변수(self):
        p = tilegrid.wms_params("L_50K_Geology_Map", 12, 3490, 1600)
        self.assertEqual((p["version"], p["crs"], p["width"], p["transparent"]),
                         ("1.3.0", "EPSG:3857", "512", "true"))


class PolarGrid(SimpleTestCase):
    """NPI 는 지역의 투영(3413·3031)으로 받는다. 아래 `BBOX` 는 2026-09-28 에 같은 판의
    OpenLayers(`vendor/ol.js`)를 node 로 돌려 `npolarSource` 와 같은 격자에서 뽑은 값이다."""
    SEEN = {
        ("EPSG:3413", 6, 37, 20): "655360,1441792,786432,1572864",
        ("EPSG:3031", 7, 70, 45): "312481.3150875,937443.9452625001,364561.53426875005,989524.16444375",
        ("EPSG:3031", 3, 1, 5): "-2499850.5207,-1666567.0138000003,-1666567.0138000003,-833283.5069000003",
    }

    def test_브라우저와_한_글자까지_같다(self):
        for (crs, z, x, y), bbox in self.SEEN.items():
            p = tilegrid.PolarGrid(crs).wms_params("L", z, x, y)
            self.assertEqual((p["crs"], p["bbox"]), (crs, bbox))

    def test_남극_투영은_GeoMAP_의_식과_같다(self):
        from viewer import geomap
        for lon, lat in ((0, -80), (120, -70), (-60, -65)):
            a = tilegrid.polar_forward(lon, lat, "EPSG:3031")
            b = geomap.lonlat_to_3031(lon, lat)
            self.assertAlmostEqual(a[0], b[0], places=6)
            self.assertAlmostEqual(a[1], b[1], places=6)

    def test_북극_중앙_경선은_아래로(self):
        x, y = tilegrid.polar_forward(-45, 70, "EPSG:3413")
        self.assertAlmostEqual(x, 0, places=6)
        self.assertLess(y, 0)

    def test_스발바르를_덮는_타일(self):
        grid = tilegrid.PolarGrid("EPSG:3413")
        tiles = list(grid.tiles_for((10, 76, 30, 81), 6))
        # 롱위에아르뷔엔(15.6, 78.2) 을 품은 타일이 들어 있다
        px, py = tilegrid.polar_forward(15.6, 78.2, "EPSG:3413")
        span = 512 * grid.resolution(6)
        want = (6, int((px + 4194304) // span), int((4194304 - py) // span))
        self.assertIn(want, tiles)


class Blocked(SimpleTestCase):
    def setUp(self):
        usage.reset()
        self.addCleanup(usage.reset)

    def test_차단의_얼굴(self):
        self.assertTrue(usage.looks_blocked(429))
        self.assertTrue(usage.looks_blocked(403))
        self.assertTrue(usage.looks_blocked(400, b"<H1>Request Blocked</H1>"))
        self.assertFalse(usage.looks_blocked(400, b"bad bbox"))
        self.assertFalse(usage.looks_blocked(500))

    def test_차단_조짐이_이어지면_쉰다(self):
        for _ in range(usage.BLOCK_LIMIT - 1):
            usage.record("kigam", ok=False, blocked=True)
        self.assertFalse(usage.paused())
        usage.record("kigam", ok=False, blocked=True)
        self.assertGreater(usage.paused(), 0)

    def test_쉬는_동안은_상류에_묻지_않는다(self):
        from unittest import mock

        from django.test import override_settings

        from viewer import kigam
        for _ in range(usage.BLOCK_LIMIT):
            usage.record("kigam", ok=False, blocked=True)
        with override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False), \
                mock.patch.object(kigam.requests, "get") as get:
            with self.assertRaises(kigam.UpstreamError):
                kigam.get_map({"layers": "a"})
        get.assert_not_called()


class Counting(TestCase):
    def test_날마다_센다(self):
        from viewer.models import UpstreamDay
        usage.record("kigam", ok=True)
        usage.record("kigam", ok=True)
        usage.record("kigam", ok=False)
        usage.record("vworld", ok=True, count=4)
        usage.reset()
        rows = {r.upstream: r for r in UpstreamDay.objects.all()}
        self.assertEqual((rows["kigam"].ok, rows["kigam"].fail), (2, 1))
        self.assertEqual(rows["vworld"].ok, 4)


class PrewarmPlans(TestCase):
    """미리 데우기가 상류마다 브라우저와 같은 열쇠로 담는지."""

    def test_상류마다_받는_꼴(self):
        from viewer.management.commands import prewarm
        from viewer.models import Layer, LayerGroup
        group = LayerGroup.objects.create(name="시험")
        Layer.objects.create(name="lt_l_gimsfault", title="단층", group=group, upstream="vworld", kind="vector")
        self.assertIsInstance(prewarm.plan_for("L_50K_Geology_Map", "kigam"), prewarm.WmsPlan)
        npi = prewarm.plan_for("npolar:svalbard_units", "npolar")
        self.assertEqual(npi.grid.crs, "EPSG:3413")
        self.assertIsInstance(prewarm.plan_for("gsj:geology", "gsj"), prewarm.GsjPlan)
        self.assertIsNone(prewarm.plan_for("lt_l_gimsfault", "vworld"))       # 모양이다
        self.assertIsNone(prewarm.plan_for("npolar:rock_archive", "npolar"))   # 점이다
        self.assertIsNone(prewarm.plan_for("geo3al:age", "geo3al"))

    def test_GSJ_는_줌_밖을_묻지_않는다(self):
        from viewer.management.commands import prewarm
        plan = prewarm.plan_for("gsj:faults", "gsj")                          # 줌 10 부터
        self.assertEqual(list(plan.tiles_for((139.5, 35.5, 139.8, 35.8), 9)), [])
        self.assertTrue(list(plan.tiles_for((139.5, 35.5, 139.8, 35.8), 10)))

    def test_열쇠는_화면이_부르는_것과_같다(self):
        from viewer import kigam, tilecache, views
        from viewer.management.commands import prewarm
        npi = prewarm.plan_for("npolar:svalbard_units", "npolar")
        params = tilegrid.PolarGrid("EPSG:3413").wms_params("npolar:svalbard_units", 6, 37, 20)
        self.assertEqual(npi.key(6, 37, 20), tilecache.key_for("map", kigam.clean_params(params)))
        self.assertEqual(prewarm.plan_for("gsj:geology", "gsj").key(9, 1, 2),
                         views.gsj_tile_key("gsj:geology", 9, 1, 2))


class PrewarmDem(SimpleTestCase):
    """3D 의 극지 지형을 미리 받는다(`--layers dem`, 034) — 3D 가 서버에 묻는 타일만, 4×4 네모째."""

    def test_위도_60_너머_줌_11_부터만(self):
        from viewer.management.commands import prewarm
        plan = prewarm.NOT_LAYERS["dem"]()
        dasan = (11.9, 78.9, 12.0, 78.95)
        self.assertEqual(list(plan.tiles_for(dasan, 10)), [])
        self.assertTrue(list(plan.tiles_for(dasan, 11)))
        self.assertEqual(list(plan.tiles_for(dasan, 16)), [])
        self.assertEqual(list(plan.tiles_for((127.0, 37.0, 127.1, 37.1), 12)), [])   # 한국은 AWS 다
        self.assertTrue(list(plan.tiles_for((164.2, -74.65, 164.3, -74.6), 12)))     # 장보고기지
        self.assertEqual(plan.block(4), 4)

    def test_열쇠는_3D_가_부르는_것과_같고_다_있으면_묻지_않는다(self):
        from unittest import mock
        from viewer import elevation
        from viewer.management.commands import prewarm
        plan = prewarm.NOT_LAYERS["dem"]()
        self.assertEqual(plan.key(12, 2200, 300), elevation.polar_key(12, 2200, 300))
        with mock.patch.object(elevation, "_polar_block", return_value={(0, 0): None}) as block, \
                mock.patch.object(elevation.tilecache, "get", return_value=b"png"):
            self.assertEqual(plan.fetch_block(12, 550, 75, 4), 0)
        block.assert_not_called()
        with mock.patch.object(elevation, "_polar_block", return_value={(i, 0): None for i in range(16)}) as block, \
                mock.patch.object(elevation.tilecache, "get", return_value=None):
            self.assertEqual(plan.fetch_block(12, 550, 75, 4), 16)
        block.assert_called_once_with(12, 2200, 300, 4)
