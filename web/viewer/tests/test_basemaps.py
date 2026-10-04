"""조건이 열린 배경(NASA GIBS·GEBCO)을 서버가 받아 담는다 (wetherilli 184). 상류를 부르지 않는다."""
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import basemaps

STATIC = Path(__file__).resolve().parents[1] / "static" / "viewer"
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg"
PNG = b"\x89PNG\r\n\x1a\n" + b"png"


def answer(content, ctype, status=200):
    r = mock.MagicMock(status_code=status, content=content, url="https://upstream/x")
    r.headers = {"content-type": ctype}
    return r


class Grid(TestCase):
    def test_GIBS_격자(self):
        self.assertEqual(basemaps.gibs_tile_count("4326", 0), (2, 1))       # 288° 한 장 — 가로 둘, 세로 하나
        self.assertEqual(basemaps.gibs_tile_count("4326", 3), (10, 5))
        self.assertEqual(basemaps.gibs_tile_count("3413", 0), (2, 2))
        self.assertTrue(basemaps.knows_gibs_tile("3031", "BlueMarble_ShadedRelief_Bathymetry", 4, 31, 31))
        self.assertFalse(basemaps.knows_gibs_tile("3031", "BlueMarble_ShadedRelief_Bathymetry", 5, 0, 0))   # 500 m 판은 4 까지
        self.assertFalse(basemaps.knows_gibs_tile("4326", "BlueMarble_ShadedRelief_Bathymetry", 0, 0, 1))
        self.assertFalse(basemaps.knows_gibs_tile("4326", "MODIS_Terra_CorrectedReflectance_TrueColor", 1, 0, 0))


class Views(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = override_settings(TILE_CACHE_DIR=tmp.name, TILE_CACHE_SECONDS=86400)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_GIBS_타일은_브라우저가_부르던_주소로_받아_담는다(self):
        url = reverse("viewer:gibs-tile", kwargs={"epsg": "3413", "layer": "BlueMarble_ShadedRelief_Bathymetry",
                                                  "z": "2", "y": "1", "x": "3"})
        with mock.patch.object(basemaps.requests, "get", return_value=answer(JPEG, "image/jpeg")) as get:
            first = self.client.get(url)
            second = self.client.get(url)
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://gibs.earthdata.nasa.gov/wmts/epsg3413/best/"
                                                "BlueMarble_ShadedRelief_Bathymetry/default/500m/2/1/3.jpeg")
        self.assertEqual((first["X-GSM-Cache"], second["X-GSM-Cache"]), ("miss", "hit"))
        self.assertEqual((second["Content-Type"], second.content), ("image/jpeg", JPEG))

    def test_GEBCO_는_브라우저의_변수_그대로(self):
        # 지역 탭의 `gebcoLayer`(OpenLayers TileWMS, 1.1.1)가 부르는 꼴
        query = ("SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&FORMAT=image%2Fpng&STYLES=&TRANSPARENT=true&LAYERS=GEBCO_LATEST"
                 "&TILED=true&WIDTH=512&HEIGHT=512&SRS=EPSG%3A3857"
                 "&BBOX=13775786.985667605%2C3757032.814272985%2C14401959.121379772%2C4383204.9499851465")
        with mock.patch.object(basemaps.requests, "get", return_value=answer(PNG, "image/png")) as get:
            self.assertEqual(self.client.get(reverse("viewer:gebco-wms") + "?" + query)["X-GSM-Cache"], "miss")
            self.assertEqual(self.client.get(reverse("viewer:gebco-wms") + "?" + query)["X-GSM-Cache"], "hit")
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://wms.gebco.net/mapserv")
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"], sent["bbox"], sent["version"], sent["transparent"]),
                         ("GEBCO_LATEST", "EPSG:3857",
                          "13775786.985667605,3757032.814272985,14401959.121379772,4383204.9499851465", "1.1.1", "true"))

    def test_구의_GIBS_WMS(self):
        # 온 지구의 Cesium `WebMapServiceImageryProvider` 가 부르는 꼴
        params = {"service": "WMS", "version": "1.1.1", "request": "GetMap", "styles": "", "format": "image/jpeg",
                  "transparent": "false", "layers": "BlueMarble_NextGeneration", "srs": "EPSG:4326",
                  "bbox": "0,0,45,45", "width": "256", "height": "256"}
        with mock.patch.object(basemaps.requests, "get", return_value=answer(JPEG, "image/jpeg")) as get:
            r = self.client.get(reverse("viewer:gibs-wms"), params)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.args[0], "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi")

    def test_화면이_부르지_않는_것은_묻지_않는다(self):
        with mock.patch.object(basemaps.requests, "get") as get:
            for params in ({"request": "GetMap", "layers": "남의_레이어", "width": "512", "height": "512", "bbox": "0,0,1,1"},
                           {"request": "GetFeatureInfo", "layers": "GEBCO_LATEST", "width": "512", "height": "512",
                            "bbox": "0,0,1,1"},
                           {"request": "GetMap", "layers": "GEBCO_LATEST", "width": "8000", "height": "512",
                            "bbox": "0,0,1,1"}):
                self.assertEqual(self.client.get(reverse("viewer:gebco-wms"), params).status_code, 404)
            self.assertEqual(self.client.get("/GSM/gibs/3413/BlueMarble_ShadedRelief/9/0/0.jpeg").status_code, 404)
        get.assert_not_called()

    def test_그림이_아니면_담지_않고_안내_타일(self):
        url = reverse("viewer:gibs-tile", kwargs={"epsg": "4326", "layer": "BlueMarble_ShadedRelief", "z": "0", "y": "0",
                                                  "x": "1"})
        with mock.patch.object(basemaps.requests, "get", return_value=answer(b"<xml/>", "text/xml")) as get:
            first = self.client.get(url)
            self.client.get(url)
        self.assertEqual(first["Cache-Control"], "no-store")
        self.assertEqual(get.call_count, 2)                     # 안내 타일은 담지 않았다 — 다시 묻는다


class Script(TestCase):
    def code(self, name):
        """주석 줄을 뺀 줄들 — 주소 안의 `//` 를 주석으로 읽지 않게 줄 머리만 본다"""
        lines = (STATIC / name).read_text(encoding="utf-8").splitlines()
        return "\n".join(l for l in lines if not re.match(r"\s*(//|/?\*)", l))

    def test_서버를_거치고_정적_판만_곧장(self):
        js = self.code("map.js")
        for line in (l for l in js.splitlines() if "gibs.earthdata" in l or "wms.gebco" in l):
            self.assertIn("STATIC ?", line)
        self.assertIn('BASE + "gebco/wms/"', js)
        self.assertIn('BASE + "gibs/" + epsg', js)

    def test_온_지구는_늘_서버로(self):
        js = self.code("earth.js")
        self.assertNotIn("gibs.earthdata", js)
        self.assertNotIn("wms.gebco", js)
