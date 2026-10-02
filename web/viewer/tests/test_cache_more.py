"""디스크·브라우저 캐시의 빈 곳과 prewarm 의 Trek·KOPRI (wetherilli 158). 상류를 부르지 않는다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import geomap, kopri, tilecache, trek, views, warp
from viewer.management.commands import prewarm


@override_settings(TILE_CACHE_SECONDS=86400)
class Browser(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-cachemore-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_속성_JSON_은_하루와_언어로_가른다(self):
        with mock.patch.object(trek, "unit_at", return_value=[], create=True), \
             mock.patch.object(views, "_cached_json", return_value={"features": []}):
            r = self.client.get("/GSM/featureinfo/", {"layers": "L_250K_Geology_Map", "request": "GetFeatureInfo",
                                                      "bbox": "0,0,1,1", "width": 256, "height": 256, "i": 1, "j": 1,
                                                      "crs": "EPSG:3857"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "public, max-age=86400")
        self.assertIn("Cookie", r["Vary"])
        self.assertIn("Accept-Language", r["Vary"])

    def test_오류는_오래_들지_않는다(self):
        r = self.client.get("/GSM/gsj/legend/", {"layer": "nope"})
        self.assertNotEqual(r.status_code, 200)
        self.assertNotIn("max-age=86400", r.get("Cache-Control", ""))

    def test_AWS_로_넘기는_302_도_하루(self):
        r = self.client.get("/GSM/dem/5/27/12.png")         # 위도 60° 안쪽·일본 밖 — AWS 로 넘긴다
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Cache-Control"], "public, max-age=86400")


class Warp(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-warpcache-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_GeoMAP_편_것은_담아_두고_다시_펴지_않는다(self):
        layer = next(iter(geomap.LAYERS))
        with mock.patch.object(geomap, "available", return_value=True), \
             mock.patch.object(geomap, "data_version", return_value="2022-08"), \
             mock.patch.object(views, "_geomap_png", return_value=(b"x", True)), \
             mock.patch.object(warp, "render", return_value=b"\x89PNG warped") as render:
            first = self.client.get(f"/GSM/warp/geomap/{layer}/5/27/28.png")
            again = self.client.get(f"/GSM/warp/geomap/{layer}/5/27/28.png")
        self.assertEqual(render.call_count, 1)
        self.assertEqual(again.content, b"\x89PNG warped")
        self.assertEqual(again["X-GSM-Cache"], "hit")
        self.assertEqual(first.status_code, 200)

    def test_판이_바뀌면_새로_편다(self):
        with mock.patch.object(geomap, "available", return_value=True), \
             mock.patch.object(geomap, "data_version", return_value="2022-08"):
            old = views._warp_key("geomap_simple_geology", "geomap", 8, 1, 2, 256)
        with mock.patch.object(geomap, "available", return_value=True), \
             mock.patch.object(geomap, "data_version", return_value="2024-01"):
            new = views._warp_key("geomap_simple_geology", "geomap", 8, 1, 2, 256)
        self.assertNotEqual(old, new)

    def test_스캔판과_판을_모르는_것은_담지_않는다(self):
        self.assertIsNone(views._warp_key("phyloserver:geology", "phyloserver", 8, 1, 2, 256))
        with mock.patch.object(geomap, "available", return_value=False):
            self.assertIsNone(views._warp_key("geomap_simple_geology", "geomap", 8, 1, 2, 256))


class Prewarm(SimpleTestCase):
    def test_달_격자는_가로_두_장부터(self):
        plan = prewarm.NOT_LAYERS["moon:units"]()
        self.assertEqual(list(plan.tiles_for((-180, -90, 180, 90), 0)), [(0, 0, 0), (0, 1, 0)])
        tiles = list(plan.tiles_for((20, 0, 40, 30), 3))       # 한 장이 22.5°
        self.assertEqual({(x, y) for _, x, y in tiles}, {(8, 2), (8, 3), (9, 2), (9, 3)})
        self.assertEqual(list(plan.tiles_for((20, 0, 40, 30), trek.MAX_ZOOM + 1)), [])

    def test_열쇠는_뷰와_같은_함수(self):
        plan = prewarm.NOT_LAYERS["moon:dem"]()
        self.assertEqual(plan.key(5, 10, 3), views.moon_dem_key(5, 10, 3))
        self.assertEqual(prewarm.NOT_LAYERS["mars:units"]().key(4, 2, 1), views.mars_tile_key("units", 4, 2, 1))
        self.assertEqual(prewarm.NOT_LAYERS["moon:contacts"]().key(4, 2, 1), views.moon_tile_key("contacts", 4, 2, 1))

    def test_받은_것을_뷰의_열쇠로_담는다(self):
        plan = prewarm.NOT_LAYERS["mars:dem"]()
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
             mock.patch.object(trek, "mars_dem_tile", return_value=b"terrarium") as fetch:
            plan.fetch_block(3, 4, 2, 1)
            self.assertEqual(tilecache.get(views.mars_dem_key(3, 4, 2)), b"terrarium")
        fetch.assert_called_once_with(3, 4, 2)

    def test_KOPRI_WMS_는_지역의_투영으로(self):
        name = next(iter(kopri.WMS))
        plan = prewarm.plan_for(name, "kopri")
        self.assertIsInstance(plan, prewarm.WmsPlan)
        self.assertEqual(plan.grid.crs, kopri.wms_projection(name))
        self.assertIsNone(prewarm.plan_for("kopri:rock_samples", "kopri"))     # 점이다



class PrewarmCommand(TestCase):
    def test_명령이_달_이름을_안다(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp):
            call_command("prewarm", "--bbox", "20,0,40,30", "--zooms", "3", "--layers", "moon:units,moon:dem",
                         "--dry-run", stdout=out)
        self.assertIn("받을 것 8", out.getvalue())
