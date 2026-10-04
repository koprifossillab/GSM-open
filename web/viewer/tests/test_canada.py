"""캐나다 — NRCan 1:500만(Wheeler)·온타리오 OGS (wetherilli 204). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-04 에 받아 본 그대로다 — NRCan GetFeatureInfo 는 GeoJSON(영어·프랑스어 열이 짝으로), OGS 는 REST identify.
"""
import json
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import crs, nrcan, ogs, tilegrid, views


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/", json=lambda: body)


WMS = {"layers": "ogs:3", "query_layers": "ogs:3", "crs": "EPSG:3978", "bbox": "1000000,-200000,1100000,-100000",
       "width": "256", "height": "256", "i": "127", "j": "127", "format": "image/png"}


class Nrcan(SimpleTestCase):
    def test_레이어_이름을_번호로_3978_그대로(self):
        with mock.patch("viewer.nrcan.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            nrcan.get_map({"layers": "nrcan:wheeler", "crs": "EPSG:3978", "bbox": "0,0,1,1", "width": "512", "height": "512"})
        params = get.call_args[1]["params"]
        self.assertEqual((params["layers"], params["crs"], params["version"]), ("0", "EPSG:3978", "1.3.0"))

    def test_모르는_레이어는_묻지_않는다(self):
        with self.assertRaises(nrcan.NrcanError):
            nrcan.get_map({"layers": "nrcan:other"})

    def test_속성은_영어_열만_가장_잘게_가른_시대(self):
        props = {"UNIT": "lS*", "RXTP": "sedimentary rocks", "SUBRXTP": "undivided sedimentary rocks", "ERA": "Paleozoic",
                 "PERIOD": "Silurian", "EPOCH": " ", "GEOLPROV": "Hudson Bay Lowlands", "TPRCH": "roches sédimentaires",
                 "NAME": " ", "OBJECTID": "13439"}
        out = nrcan.friendly(props)
        self.assertEqual(out["지질시대"], "실루리아기")
        self.assertEqual(out["지질구"], "Hudson Bay Lowlands")
        self.assertNotIn("이름", out)
        self.assertNotIn("roches sédimentaires", out.values())
        self.assertEqual(nrcan.friendly(props, "en")["지질시대"], "Silurian")


class Ogs(SimpleTestCase):
    def test_누른_화소를_그_투영의_좌표로_identify(self):
        p = ogs.identify_params(WMS)
        self.assertEqual(p["sr"], "3978")
        self.assertEqual(p["layers"], "all:57")                      # WMS 3 = REST 57
        x, y = (float(v) for v in p["geometry"].split(","))
        self.assertAlmostEqual(x, 1000000 + 127.5 * 100000 / 256, places=3)      # 화소의 가운데
        self.assertAlmostEqual(y, -100000 - 127.5 * 100000 / 256, places=3)
        with self.assertRaises(ogs.OgsError):
            ogs.identify_params(dict(WMS, crs="EPSG:4326"))

    def test_속성(self):
        hit = {"results": [{"layerId": 57, "attributes": {
            "OBJECTID": "16919", "TYPE_P": "28c", "UNITNAME_P": " ", "ROCKTYPE_P": "Lapilli tuff, breccia",
            "STRAT_P": "Whitewater Group; Onaping Formation", "EON_P": "PROTEROZOIC (0.542 Ga to 2.50 Ga)",
            "ERA_P": "PALEOPROTEROZOIC (1.6 Ga to 2.5 Ga)", "PERIOD_P": " ", "PROVINCE_P": "SOUTHERN and SUPERIOR"}}]}
        with mock.patch("viewer.ogs.requests.get", return_value=response(hit)) as get:
            data = ogs.get_feature_info(WMS)
        self.assertTrue(get.call_args[0][0].endswith("/MapServer/identify"))
        props = ogs.friendly(data["features"][0]["properties"])
        self.assertEqual(props["지질시대"], "고원생대 (1.6 Ga to 2.5 Ga)")
        self.assertEqual((props["기호"], props["층서"]), ("28c", "Whitewater Group; Onaping Formation"))
        self.assertNotIn("이름", props)
        quaternary = ogs.friendly({"UNIT_NAME": "Glaciofluvial ice-contact deposits", "AGE": "Pleistocene",
                                   "MATERIAL": "gravel and sand"}, "en")
        self.assertEqual(quaternary, {"이름": "Glaciofluvial ice-contact deposits", "지질시대": "Pleistocene",
                                      "물질": "gravel and sand"})

    def test_상류의_오류(self):
        with mock.patch("viewer.ogs.requests.get", return_value=response({"error": {"message": "bad"}})):
            with self.assertRaises(ogs.OgsError):
                ogs.get_feature_info(WMS)


class Lambert(SimpleTestCase):
    def test_캐나다_람베르트_격자(self):
        self.assertEqual(tilegrid.forward(-95.0, 49.0, "EPSG:3978"), (0.0, 0.0))     # 원점
        x, y = tilegrid.forward(-81.0, 46.6, "EPSG:3978")
        lat, lon = crs.lcc_to_latlon(x, y, -95.0, 49.0, 77.0, lat0=49.0)
        self.assertAlmostEqual((lat, lon)[0], 46.6, places=6)
        box = tilegrid.projected_bbox((-95.16, 41.67, -74.32, 56.86), "EPSG:3978")
        self.assertLess(box[0], 0)
        self.assertGreater(box[2], 1_500_000)


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_캐나다_탭에_3978_로(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name in ("nrcan:wheeler", "ogs:3", "ogs:6"):
            group, layer = rows[name]
            self.assertEqual(group["region"], "canada", name)
            self.assertEqual(layer["projection"], "EPSG:3978", name)
        self.assertEqual(rows["nrcan:wheeler"][1]["upstream"], "nrcan")
        en = {l["name"]: l["title"] for g in views._catalog("en") for l in g["layers"]}
        self.assertEqual(en["ogs:3"], "Ontario bedrock (1:250k)")

    def test_미리_데우기는_3978_격자(self):
        from viewer.management.commands import prewarm
        plan = prewarm.plan_for("nrcan:wheeler", "nrcan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.grid.crs, "EPSG:3978")

    def test_3D_는_3857_로(self):
        self.assertIn("nrcan", views.MAP3D_WMS)
        self.assertIn("ogs", views.MAP3D_WMS)
