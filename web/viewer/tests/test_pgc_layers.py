"""PGC 경사·등고선 레이어 (wetherilli 099) — 극지 지질도 위에 겹치는 타일과 누른 자리의 값.

망 없이 돈다. PGC 는 가짜 응답으로 바꾼다. 응답의 꼴은 2026-09-30 에 받아 본 그대로다.
"""
import json
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import elevation, views
from viewer.models import Layer, LayerGroup

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
BOX = "-245000,-2305000,-235000,-2295000"


def resp(content=b"", ctype="image/png", status=200, data=None):
    return mock.Mock(status_code=status, content=content if data is None else json.dumps(data).encode(),
                     headers={"content-type": ctype}, json=lambda: data)


def wms(name="pgc:greenland_slope", crs="EPSG:3413", **extra):
    return {"layers": name, "crs": crs, "bbox": BOX, "width": "512", "height": "512", **extra}


class Door(SimpleTestCase):
    def test_지역의_투영으로_그리는_법을_붙여_부른다(self):
        with mock.patch.object(elevation.requests, "get", return_value=resp(JPEG, "image/jpeg")) as get, \
                mock.patch.object(elevation.usage, "record"):
            content, ctype = elevation.get_map(wms())
        self.assertEqual((content, ctype), (JPEG, "image/jpeg"))
        url, sent = get.call_args.args[0], get.call_args.kwargs["params"]
        self.assertIn("/arcticdem_latest/ImageServer/exportImage", url)
        self.assertEqual((sent["bboxSR"], sent["imageSR"], sent["size"]), (3413, 3413, "512,512"))
        self.assertEqual(json.loads(sent["renderingRule"]), {"rasterFunction": "Slope Map"})
        self.assertEqual(sent["format"], "jpgpng")                  # 경사는 꽉 찬 그림이라 JPEG 로 줄인다

    def test_등고선은_투명한_PNG(self):
        with mock.patch.object(elevation.requests, "get", return_value=resp(PNG)) as get, \
                mock.patch.object(elevation.usage, "record"):
            elevation.get_map(wms("pgc:antarctica_contours", "EPSG:3031"))
        sent = get.call_args.kwargs["params"]
        self.assertIn("/rema_latest/", get.call_args.args[0])
        self.assertEqual(sent["format"], "png32")
        self.assertEqual(json.loads(sent["renderingRule"])["rasterFunction"], "Contour Smoothed 25")

    def test_다른_투영은_묻지_않는다(self):
        with mock.patch.object(elevation.requests, "get") as get:
            with self.assertRaises(elevation.ElevationError):
                elevation.get_map(wms(crs="EPSG:3857"))
        get.assert_not_called()

    def test_누른_픽셀의_자리에서_값을_읽는다(self):
        value = {"objectId": 0, "name": "Pixel", "value": "19.9222"}
        with mock.patch.object(elevation.requests, "get", return_value=resp(data=value)) as get, \
                mock.patch.object(elevation.usage, "record"):
            got = elevation.get_feature_info(wms(query_layers="pgc:greenland_slope", i="0", j="511"))
        self.assertEqual(got["features"][0]["properties"], {"사면 경사 (°)": "19.9"})
        sent = get.call_args.kwargs["params"]
        point = json.loads(sent["geometry"])
        # 왼쪽 아래 픽셀의 가운데 — 한 픽셀이 10 000 / 512 m
        self.assertAlmostEqual(point["x"], -245000 + 0.5 * 10000 / 512)
        self.assertAlmostEqual(point["y"], -2305000 + 0.5 * 10000 / 512)
        self.assertEqual(point["spatialReference"], {"wkid": 3413})
        self.assertEqual(json.loads(sent["renderingRule"])["rasterFunction"], "Slope Degrees")

    def test_모자이크_밖은_속성이_없다(self):
        with mock.patch.object(elevation.requests, "get", return_value=resp(data={"value": "NoData"})), \
                mock.patch.object(elevation.usage, "record"):
            got = elevation.get_feature_info(wms(query_layers="pgc:greenland_contours", i="1", j="1"))
        self.assertEqual(got, {"features": []})


class View(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-pgc-"), TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        group = LayerGroup.objects.create(name="지형 (PGC)", region="greenland")
        for name in ("pgc:greenland_slope", "pgc:greenland_contours"):
            Layer.objects.create(name=name, title=name, group=group, upstream="pgc")

    def test_카탈로그는_투영과_줌을_적고_범례를_묻지_않게(self):
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows["pgc:greenland_slope"]["projection"], "EPSG:3413")
        self.assertTrue(rows["pgc:greenland_slope"]["noLegend"])
        self.assertNotIn("minZoom", rows["pgc:greenland_slope"])
        self.assertEqual(rows["pgc:greenland_contours"]["minZoom"], 10)

    def test_받은_JPEG_는_캐시에서_꺼내도_JPEG(self):
        params = dict(wms(), service="WMS", version="1.3.0", request="GetMap", format="image/png")
        with mock.patch.object(elevation.requests, "get", return_value=resp(JPEG, "image/jpeg")) as get, \
                mock.patch.object(elevation.usage, "record"):
            first = self.client.get("/GSM/wms/", params)
            again = self.client.get("/GSM/wms/", params)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first["Content-Type"], "image/jpeg")
        self.assertEqual((again["X-GSM-Cache"], again["Content-Type"]), ("hit", "image/jpeg"))

    def test_씨앗과_문이_짝이_맞다(self):
        for path in views.settings.PGC_CATALOG_SEEDS:
            seed = json.loads(path.read_text(encoding="utf-8"))
            for row in seed["레이어"]:
                self.assertTrue(elevation.knows_layer(row["name"]), row["name"])
