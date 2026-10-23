"""남극·그린란드 — GIBS 의 MEaSUREs 빙하 속도 (wetherilli 413). 상류를 부르지 않는다."""
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import basemaps

PNG = b"\x89PNG\r\n\x1a\nfake"


class Door(SimpleTestCase):
    def test_아는_타일만(self):
        self.assertTrue(basemaps.knows_gibs_overlay("3031", "MEaSUREs_Ice_Velocity_Antarctica", 4, 31, 31))
        self.assertFalse(basemaps.knows_gibs_overlay("3031", "MEaSUREs_Ice_Velocity_Antarctica", 5, 0, 0))   # 500m 은 줌 4 까지
        self.assertFalse(basemaps.knows_gibs_overlay("3031", "MEaSUREs_Ice_Velocity_Antarctica", 1, 4, 0))   # 줌 1 은 4×4
        self.assertFalse(basemaps.knows_gibs_overlay("3413", "MEaSUREs_Ice_Velocity_Antarctica", 0, 0, 0))   # 투영이 다르다
        self.assertFalse(basemaps.knows_gibs_overlay("3031", "BlueMarble_ShadedRelief_Bathymetry", 0, 0, 0))

    def test_받는_주소에_시점이_든다(self):
        got = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=PNG, url="u",
                        elapsed=mock.Mock(total_seconds=lambda: 0.1))
        with mock.patch.object(basemaps.requests, "get", return_value=got) as get:
            basemaps.gibs_overlay_tile("3413", "MEaSUREs_Ice_Velocity_Greenland", 2, 3, 1)
        self.assertTrue(get.call_args[0][0].endswith(
            "/wmts/epsg3413/best/MEaSUREs_Ice_Velocity_Greenland/default/2008-12-01/500m/2/1/3.png"))
        self.assertEqual(basemaps.gibs_overlay_direct("gibs:ice_velocity_greenland").format(z=2, y=1, x=3),
                         get.call_args[0][0])

    def test_격자는_Blue_Marble_과_같다(self):
        g = basemaps.gibs_overlay_grid()
        self.assertEqual((g["tileSize"], g["resolutions"][0], len(g["resolutions"])), (512, 8192, 5))


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def rows(self):
        from viewer import views
        return {l["name"]: dict(l, region=g["region"]) for g in views._catalog("ko") for l in g["layers"]}

    def test_남극과_그린란드_탭에_선다(self):
        rows = self.rows()
        south, north = rows["gibs:ice_velocity_antarctica"], rows["gibs:ice_velocity_greenland"]
        self.assertEqual((south["region"], south["projection"]), ("antarctica", "EPSG:3031"))
        self.assertEqual((north["region"], north["projection"]), ("greenland", "EPSG:3413"))
        self.assertEqual(south["tiles"], "gibs/3031/MEaSUREs_Ice_Velocity_Antarctica/{z}/{y}/{x}.png")
        self.assertTrue(south["legendImg"].endswith("/legends/MEaSUREs_Ice_Velocity_Antarctica_H.svg"))
        self.assertFalse(south["queryable"])
        self.assertIn("10.5067/D7GK8F5J8M8R", south["attribution"])

    def test_타일은_한_번_받아_담는다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(basemaps, "_get", return_value=PNG) as get:
            url = "/GSM/gibs/3031/MEaSUREs_Ice_Velocity_Antarctica/1/1/2.png"
            first = self.client.get(url)
            again = self.client.get(url)
        self.assertEqual((first.status_code, again.status_code), (200, 200))
        self.assertEqual(first["X-GSM-Cache"], "miss")
        self.assertEqual(again.content, PNG)
        self.assertEqual(get.call_count, 1)

    def test_못_받은_칸은_투명하게(self):
        """겹쳐 그리는 레이어라 안내 타일이 아래 지도를 가리지 않게 — 담지 않는다"""
        from viewer import tiles
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(basemaps, "_get", side_effect=basemaps.BasemapError("닿지 못했다")):
            got = self.client.get("/GSM/gibs/3413/MEaSUREs_Ice_Velocity_Greenland/1/1/2.png")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, tiles.blank_tile(512, 512))
        self.assertEqual(got["Cache-Control"], "no-store")

    def test_모르는_타일은_404(self):
        self.assertEqual(self.client.get("/GSM/gibs/3031/MEaSUREs_Ice_Velocity_Antarctica/5/0/0.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/gibs/3031/BlueMarble_NextGeneration/0/0/0.png").status_code, 404)

    def test_대조는_격자의_한가운데_칸(self):
        from viewer import views
        from viewer.management.commands import verify_layers
        from viewer.models import Layer
        layer = Layer.objects.get(name="gibs:ice_velocity_antarctica")
        self.assertEqual(verify_layers.tile_for(layer, views._layer_extra(layer)), (0, 1, 1))

    def test_화면의_손(self):
        js = (Path(__file__).resolve().parents[1] / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        self.assertIn("gibs: { source: gibsOverlaySource, info: null }", js)
