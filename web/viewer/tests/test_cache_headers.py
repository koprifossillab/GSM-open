"""브라우저 캐시 — ETag·304 와 판이 든 주소의 immutable (wetherilli 151). 상류를 부르지 않는다."""
import tempfile
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import geomap, kigam, tilecache, views

GEOMAP_LAYER = next(iter(geomap.LAYERS))


@override_settings(TILE_CACHE_SECONDS=86400, TILE_IMMUTABLE_SECONDS=31536000)
class Immutable(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_판이_맞을_때만_길게(self):
        resp = views._immutable(self.rf.get("/x", {"v": "2022-08r1"}), views._tile(b"png"), "2022-08r1")
        self.assertEqual(resp["Cache-Control"], "public, max-age=31536000, immutable")

    def test_판이_없거나_옛_판이면_하루(self):
        for query in ({}, {"v": "2021-01r1"}):
            resp = views._immutable(self.rf.get("/x", query), views._tile(b"png"), "2022-08r1")
            self.assertEqual(resp["Cache-Control"], "public, max-age=86400")

    def test_안내_타일은_그대로_no_store(self):
        resp = views._immutable(self.rf.get("/x", {"v": "a"}), views._tile(b"png", store=False), "a")
        self.assertEqual(resp["Cache-Control"], "no-store")

    def test_판을_모르면_길게_하지_않는다(self):
        resp = views._immutable(self.rf.get("/x", {"v": ""}), views._tile(b"png"), "")
        self.assertEqual(resp["Cache-Control"], "public, max-age=86400")


@override_settings(TILE_CACHE_SECONDS=86400, TILE_IMMUTABLE_SECONDS=31536000)
class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-cachehdr-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def _cached_wms(self, extra=None):
        """캐시에 든 상류 타일 한 장 — 상류를 타지 않는다."""
        params = {"layers": "L_250K_Geology_Map", "bbox": "14000000,4500000,14100000,4600000", "width": "256",
                  "height": "256", "crs": "EPSG:3857", "request": "GetMap"}
        clean = kigam.clean_params(params)
        clean.setdefault("format", "image/png")
        clean.setdefault("transparent", "true")
        tilecache.put(tilecache.key_for("map", clean), b"\x89PNG upstream tile")
        return self.client.get(reverse("viewer:wms"), {**params, **(extra or {})})

    def test_상류_타일은_ETag_와_하루(self):
        resp = self._cached_wms()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Cache-Control"], "public, max-age=86400")
        self.assertTrue(resp.has_header("ETag"))

    def test_되물으면_304(self):
        etag = self._cached_wms()["ETag"]
        again = self._cached_wms()
        self.assertEqual(again["ETag"], etag)
        resp = self.client.get(reverse("viewer:wms"), {
            "layers": "L_250K_Geology_Map", "bbox": "14000000,4500000,14100000,4600000", "width": "256",
            "height": "256", "crs": "EPSG:3857", "request": "GetMap"}, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(resp.status_code, 304)
        self.assertEqual(resp.content, b"")

    def test_상류_타일은_v_를_붙여도_길어지지_않는다(self):
        # 캐시 열쇠는 상류에 넘길 것만 본다 — v 는 상류 인자가 아니어서 따로 담긴다. 길어지지만 않으면 된다
        with mock.patch.object(kigam, "has_key", return_value=False):
            resp = self._cached_wms({"v": "anything"})
        self.assertNotIn("immutable", resp["Cache-Control"])

    def test_안내_타일에는_ETag_가_없다(self):
        with mock.patch.object(kigam, "has_key", return_value=False):
            resp = self.client.get(reverse("viewer:wms"), {
                "layers": "L_1M_Geology_Map", "bbox": "0,0,1,1", "width": "256", "height": "256",
                "crs": "EPSG:3857", "request": "GetMap"})
        self.assertEqual(resp["Cache-Control"], "no-store")
        self.assertFalse(resp.has_header("ETag"))

    def test_GeoMAP_은_판이_맞으면_immutable(self):
        with mock.patch.object(geomap, "available", return_value=True), \
             mock.patch.object(geomap, "data_version", return_value="2022-08"), \
             mock.patch.object(views, "_geomap_png", return_value=(b"\x89PNG geomap", True)):
            url = reverse("viewer:geomap-tile", kwargs={"layer": GEOMAP_LAYER, "z": 0, "x": 0, "y": 0})
            now = self.client.get(url, {"v": views.geomap_version()})
            old = self.client.get(url, {"v": "2021-01r1"})
        self.assertEqual(views.geomap_version(), "")      # 파일이 없으면 판도 없다 — 길게 두지 않는다
        self.assertIn("immutable", now["Cache-Control"])
        self.assertEqual(old["Cache-Control"], "public, max-age=86400")


@override_settings(TILE_CACHE_SECONDS=86400, TILE_IMMUTABLE_SECONDS=31536000)
class JsTiles(TestCase):
    """화면(JS)이 주소를 짓는 우리 타일 (wetherilli 183) — 판을 화면에 알리고, 그 판이면 길게. 파일을 다시 구우면 판이 바뀐다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-jstiles-"))
        patch.enable()
        self.addCleanup(patch.disable)
        self.dir = tempfile.mkdtemp(prefix="gsm-jstiles-data-")

    def test_판의_조각이_비면_빈_판(self):
        self.assertEqual(views._stamp("1", ""), "")
        self.assertEqual(len(views._stamp("1", "a")), 10)

    def test_저장소_파일은_내용으로(self):
        import os
        from pathlib import Path
        path = Path(self.dir) / "data.json"
        path.write_text("{}")
        first = views._content_stamp(path)
        os.utime(path, (1, 1))                       # 이미지를 새로 구우면 고친 때만 바뀐다
        self.assertEqual(views._content_stamp(path), first)
        path.write_text('{"a": 1}')
        self.assertNotEqual(views._content_stamp(path), first)

    def test_수성_지질도는_다시_구우면_주소와_캐시가_바뀐다(self):
        from pathlib import Path
        from viewer import mercurymap
        data = Path(self.dir) / "mercury.sqlite"
        data.write_bytes(b"one")
        url = reverse("viewer:mercury-tile", kwargs={"layer": "units", "z": 0, "x": 0, "y": 0})
        with mock.patch.object(mercurymap, "available", return_value=True), \
             mock.patch.object(mercurymap, "data_file", return_value=data), \
             mock.patch.object(mercurymap, "render_tile", side_effect=[b"\x89PNG one", b"\x89PNG two"]) as render:
            first = views.mercurymap_version()
            now = self.client.get(url, {"v": first})
            data.write_bytes(b"rebuilt")
            second = views.mercurymap_version()
            again = self.client.get(url, {"v": first})          # 옛 화면 — 새 그림을 하루짜리로
        self.assertIn("immutable", now["Cache-Control"])
        self.assertNotEqual(first, second)
        self.assertEqual(again.content, b"\x89PNG two")          # 캐시 열쇠에도 판이 들어 다시 굽는다
        self.assertEqual(again["Cache-Control"], "public, max-age=86400")
        self.assertEqual(render.call_count, 2)

    def test_화산은_받은_날과_파일이_판이다(self):
        from pathlib import Path
        from viewer import volcanoes
        data = Path(self.dir) / "gvp.json"
        data.write_text("{}")
        url = reverse("viewer:earth-volcano-tile", kwargs={"z": 0, "x": 0, "y": 0})
        with mock.patch.object(volcanoes, "available", return_value=True), \
             mock.patch.object(volcanoes, "fetched", return_value="2026-10-01"), \
             mock.patch.object(volcanoes, "path", return_value=data), \
             mock.patch.object(volcanoes, "render_tile", return_value=b"\x89PNG v"):
            resp_v = views.tile_versions("earth")["volcanoes"]
            resp = self.client.get(url, {"v": resp_v})
            data.write_text('{"again": 1}')                       # 같은 날 다시 받아도 판이 바뀐다
            self.assertNotEqual(views.tile_versions("earth")["volcanoes"], resp_v)
        self.assertIn("immutable", resp["Cache-Control"])

    def test_달_원도만_판이_있고_Trek_은_없다(self):
        from viewer import moonmap
        with mock.patch.object(moonmap, "data_file", return_value=None):
            self.assertEqual(views.tile_versions("moon"), {"orig": ""})
        self.assertEqual(set(views.tile_versions("map")), {"bed", "ice"})

    def test_화면이_판을_싣는다(self):
        page = self.client.get(reverse("viewer:map")).content.decode()
        self.assertIn('<script id="tile-versions" type="application/json">', page)
