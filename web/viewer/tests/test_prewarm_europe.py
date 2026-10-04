"""prewarm 이 지역의 투영으로 받는 유럽·북극 상류를 안다 (wetherilli 182). 상류를 부르지 않는다.

아래 주소·BBOX 는 2026-10-04 에 같은 판의 OpenLayers(`vendor/ol.js`)를 node 로 돌려 `npolarSource` 와 같은 격자
(`createXYZ({extent: 투영의 범위, tileSize: 512})`)에서 뽑은 것이다 — 브라우저가 부르는 글자 그대로다.
"""
import io
import tempfile
from unittest import mock

from PIL import Image

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import igme, ngu, tilecache, tilegrid
from viewer.management.commands import prewarm
from viewer.models import Layer, LayerGroup

#: 브라우저가 부른 주소의 물음표 뒤 — (투영, 레이어, 상류, z, x, y) → 질의
BROWSER = {
    ("EPSG:3575", "ngu:Berggrunn_nasjonal_bergartsenheter", "ngu", 9, 256, 350):
        "REQUEST=GetMap&SERVICE=WMS&VERSION=1.3.0&FORMAT=image%2Fpng&STYLES=&TRANSPARENT=true"
        "&LAYERS=ngu%3ABerggrunn_nasjonal_bergartsenheter&TILED=true&WIDTH=512&HEIGHT=512&CRS=EPSG%3A3575"
        "&BBOX=0%2C-3343541.6101562493%2C35195.17484375%2C-3308346.4353124993",
    ("EPSG:4326", "igme:geologico1m:0", "igme", 8, 125, 35):
        "REQUEST=GetMap&SERVICE=WMS&VERSION=1.3.0&FORMAT=image%2Fpng&STYLES=&TRANSPARENT=true"
        "&LAYERS=igme%3Ageologico1m%3A0&TILED=true&WIDTH=512&HEIGHT=512&CRS=EPSG%3A4326"
        "&BBOX=39.375%2C-4.21875%2C40.78125%2C-2.8125",
    ("EPSG:3857", "bgs:BGS.50k.Bedrock", "bgs", 12, 2043, 1362):
        "REQUEST=GetMap&SERVICE=WMS&VERSION=1.3.0&FORMAT=image%2Fpng&STYLES=&TRANSPARENT=true"
        "&LAYERS=bgs%3ABGS.50k.Bedrock&TILED=true&WIDTH=512&HEIGHT=512&CRS=EPSG%3A3857"
        "&BBOX=-48919.698102511466%2C6701998.640044253%2C-39135.7584820089%2C6711782.579664756",
}


def png(width, height):
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), (200, 100, 50, 255)).save(buf, format="PNG")
    return buf.getvalue()


class Grids(SimpleTestCase):
    SEEN = {
        ("EPSG:3575", 3, 4, 5): "0,-4504982.380000001,2252491.19,-2252491.190000001",
        ("EPSG:3575", 12, 2055, 2801): "30795.7779882811,-3317145.229023438,35195.17484374985,-3312745.832167969",
        ("EPSG:4326", 0, 0, 0): "-270,-180,90,180",
        ("EPSG:4326", 11, 1002, 282): "40.25390625,-3.8671875,40.4296875,-3.69140625",
        ("EPSG:4326", 7, 58, 22): "25.3125,-16.875,28.125,-14.0625",
    }

    def test_브라우저와_한_글자까지_같다(self):
        for (crs, z, x, y), bbox in self.SEEN.items():
            p = tilegrid.Grid(crs).wms_params("L", z, x, y)
            self.assertEqual((p["crs"], p["bbox"]), (crs, bbox))

    def test_4326_은_줄이_칸의_반(self):
        grid = tilegrid.Grid("EPSG:4326")
        self.assertEqual(grid.last(0), (0, 0))
        self.assertEqual(grid.last(1), (1, 0))
        self.assertEqual(grid.last(8), (255, 127))
        self.assertEqual(list(grid.tiles_for((-180, -90, 180, 90), 1)), [(1, 0, 0), (1, 1, 0)])

    def test_마드리드를_덮는_타일(self):
        self.assertIn((8, 125, 35), list(tilegrid.Grid("EPSG:4326").tiles_for((-3.8, 40.3, -3.6, 40.5), 8)))

    def test_람베르트_는_proj4_와_같다(self):
        # proj4.js 로 옮긴 오슬로 (+proj=laea +lat_0=90 +lon_0=10, WGS84)
        x, y = tilegrid.forward(10.75, 59.9, "EPSG:3575")
        self.assertAlmostEqual(x, 43465.04963007223, places=4)
        self.assertAlmostEqual(y, -3320295.545950203, places=4)
        self.assertIn((9, 256, 350), list(tilegrid.Grid("EPSG:3575").tiles_for((10.6, 59.8, 10.9, 60.0), 9)))


class Plans(TestCase):
    def setUp(self):
        groups = {region: LayerGroup.objects.create(name=f"시험 {region}", region=region)
                  for region in ("arctic_ocean", "uk", "norway", "finland", "spain", "france", "svalbard", "antarctica")}
        rows = [("ngu:Berggrunn_nasjonal_bergartsenheter", "ngu", "norway"),
                ("gtk:kalliopera_1m_kivilajiseurueet", "gtk", "finland"),
                ("emodnet:cp_wp4_pre_quaternary_geology_age", "emodnet", "arctic_ocean"),
                ("emodnet:bgr:quaternary_age", "emodnet", "uk"),
                ("igme:geologico1m:0", "igme", "spain"), ("igme:magna50:0", "igme", "spain"),
                ("bgs:BGS.50k.Bedrock", "bgs", "uk"), ("brgm:SCAN_F_GEOL1M", "brgm", "france"),
                ("pgc:svalbard_slope", "pgc", "svalbard"), ("pgc:antarctica_contours", "pgc", "antarctica")]
        for name, upstream, region in rows:
            Layer.objects.create(name=name, title=name, group=groups[region], upstream=upstream)

    def crs(self, name, upstream):
        plan = prewarm.plan_for(name, upstream)
        self.assertIsInstance(plan, prewarm.WmsPlan)
        return plan.grid.crs if plan.grid else "EPSG:3857"

    def test_카탈로그_행의_투영으로(self):
        self.assertEqual(self.crs("ngu:Berggrunn_nasjonal_bergartsenheter", "ngu"), "EPSG:3575")
        self.assertEqual(self.crs("gtk:kalliopera_1m_kivilajiseurueet", "gtk"), "EPSG:3413")
        # 같은 상류도 레이어군마다 — 북극해는 3413, 유럽 바다는 3857
        self.assertEqual(self.crs("emodnet:cp_wp4_pre_quaternary_geology_age", "emodnet"), "EPSG:3413")
        self.assertEqual(self.crs("emodnet:bgr:quaternary_age", "emodnet"), "EPSG:3857")
        # 같은 상류도 판마다 — 1:100만은 4326, MAGNA 는 3857
        self.assertEqual(self.crs("igme:geologico1m:0", "igme"), "EPSG:4326")
        self.assertEqual(self.crs("igme:magna50:0", "igme"), "EPSG:3857")
        self.assertIsNone(prewarm.plan_for("bgs:없는것", "bgs"))

    def test_PGC_경사·등고선도_지역의_투영으로(self):
        """wetherilli 182 가 남긴 것 (203) — 화면은 `npolarSource` 로 3413·3031 에서 받는다"""
        self.assertEqual(self.crs("pgc:svalbard_slope", "pgc"), "EPSG:3413")
        self.assertEqual(self.crs("pgc:antarctica_contours", "pgc"), "EPSG:3031")

    def test_화면이_그리지_않는_줌은_묻지_않는다(self):
        london = (-0.2, 51.45, -0.1, 51.55)
        bgs = prewarm.plan_for("bgs:BGS.50k.Bedrock", "bgs")                 # 화면 줌 13 부터 — 격자 줌 11 부터
        self.assertEqual(list(bgs.tiles_for(london, 10)), [])
        self.assertTrue(list(bgs.tiles_for(london, 11)))
        paris = (2.3, 48.8, 2.4, 48.9)
        scan = prewarm.plan_for("brgm:SCAN_F_GEOL1M", "brgm")                # 화면 줌 6–11
        self.assertTrue(list(scan.tiles_for(paris, 11)))
        self.assertEqual(list(scan.tiles_for(paris, 12)), [])

    def test_화면이_부른_타일을_prewarm_이_안다(self):
        """브라우저가 `/wms/` 로 부른 것이 캐시에 앉은 열쇠를 prewarm 이 같은 줌·칸으로 짓는다"""
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp):
            for (crs, name, upstream, z, x, y), query in BROWSER.items():
                door = {"ngu": ngu, "igme": igme, "bgs": prewarm.views.bgs}[upstream]
                with mock.patch.object(door, "get_map", return_value=(png(512, 512), "image/png")):
                    r = self.client.get(reverse("viewer:wms") + "?" + query)
                self.assertEqual(r.status_code, 200)
                plan = prewarm.plan_for(name, upstream)
                self.assertIsNotNone(tilecache.get(plan.key(z, x, y)), (crs, name))

    def test_4326_큰_그림은_위도_먼저(self):
        plan = prewarm.plan_for("igme:geologico1m:0", "igme")
        asked = []

        def get_map(params):
            asked.append(params)
            return png(int(params["width"]), int(params["height"])), "image/png"
        plan.get_map = get_map
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp):
            self.assertEqual(plan.fetch_block(1, 0, 0, 2), 2)            # 줌 1 은 한 줄 — 두 장
            self.assertIsNotNone(tilecache.get(plan.key(1, 1, 0)))
        self.assertEqual((asked[0]["bbox"], asked[0]["width"], asked[0]["height"]), ("-90,-180,90,180", "1024", "512"))
