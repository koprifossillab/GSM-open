"""캐나다 주 판 둘째 — 사스카치원·노바스코샤·앨버타 (wetherilli 235). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import ags, nsgs, skgs
from viewer.models import Layer

SK = {"OBJECTID": "33", "ROCK_CODE_1M": "PAMd", "LITHOLOGY": "Clay-intraclast-rich quartz arenite > siltstone + mudstone",
      "STRAT_LEV1": "Precambrian Sedimentary Rocks", "STRAT_LEV2": "Athabasca Supergroup", "STRAT_LEV3": "Manitou Falls Group",
      "STRAT_LEV4": "Null", "Geological_Region_1M": "Athabasca Supergroup", "EON": "Proterozoic", "ERA": "Paleoproterozoic",
      "PERIOD": "Statherian", "Age_Ma": "1814"}
NS = {"UNIT_NAME": "Halifax Formation", "UNIT_RANK": "formation", "PARENT": "Meguma Group", "AGE_DESC": "Cambrian - Ordovician",
      "TXT_LABEL": "COMh", "UNIT_DESC": "slope-outer shelf slate, siltstone, minor sandstone"}
AB = {"Unit_Name": "Horseshoe Canyon Formation", "Lithology": "Sandstone, siltstone, and mudstone",
      "Environ": "Marginal marine to nonmarine", "Age": "Upper Cretaceous", "GeolRegion": "Plains"}
LCC = {"crs": "EPSG:3978", "bbox": "-1220358,645308,-1160358,705308", "width": 256, "height": 256}


def answer(body=None, status=200, ctype="image/png"):
    r = mock.Mock(status_code=status, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Parse(SimpleTestCase):
    def test_사스카치원(self):
        got = skgs.friendly(SK)
        self.assertEqual((got["기호"], got["지질시대"], got["연대 (Ma)"]), ("PAMd", "스타테로스기", "1814"))
        self.assertEqual(got["층서"], "Athabasca Supergroup · Manitou Falls Group")             # "Null" 은 뺀다

    def test_노바스코샤(self):
        got = nsgs.friendly(NS)
        self.assertEqual((got["지층"], got["상위 단위"], got["지질시대"]), ("Halifax Formation", "Meguma Group", "캄브리아기~오르도비스기"))

    def test_앨버타_Upper_는_후기(self):
        self.assertEqual(ags.friendly(AB)["지질시대"], "백악기 후기")
        self.assertEqual(ags.friendly(AB, "en")["지질시대"], "Upper Cretaceous")


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ca2-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for door in (skgs, nsgs, ags):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(door.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_카탈로그(self):
        for name in ("skgs:2", "nsgs:11", "ags:bedrock"):
            self.assertEqual(Layer.objects.get(name=name).group.region, "canada")
        self.assertEqual(self.layers["skgs:2"]["projection"], "EPSG:3978")
        self.assertIs(self.layers["skgs:11"]["queryable"], False)
        self.assertEqual(self.layers["nsgs:9"]["minZoom"], 9)          # 1:200만까지 (wetherilli 310)
        self.assertTrue(self.layers["ags:bedrock"]["tiles"].endswith("/MapServer/tile/{z}/{y}/{x}"))

    def test_사스카치원_WMS_번호(self):
        with mock.patch.object(skgs.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "skgs:2", "version": "1.3.0", "request": "GetMap", **LCC})
        self.assertEqual((get.call_args.kwargs["params"]["layers"], get.call_args.kwargs["params"]["crs"]), ("2", "EPSG:3978"))

    def test_노바스코샤는_REST_export(self):
        with mock.patch.object(nsgs.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "nsgs:11", "version": "1.3.0", "request": "GetMap", **LCC})
        self.assertTrue(get.call_args.args[0].endswith("/MapServer/export"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["bboxSR"], sent["layers"], sent["size"]), ("3978", "show:11", "256,256"))

    def test_앨버타는_가운데_점으로_query(self):
        with mock.patch.object(ags.requests, "get",
                               return_value=answer({"features": [{"attributes": AB}]}, ctype="application/json")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "ags:bedrock", "query_layers": "ags:bedrock", "request": "GetFeatureInfo", "i": 50, "j": 50, **LCC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["inSR"], sent["geometry"]), ("3978", "-1190358.0,675308.0"))
        self.assertEqual(data["features"][0]["props"]["지층"], "Horseshoe Canyon Formation")

    def test_캐나다_탭(self):
        js = (skgs.settings.BASE_DIR / "viewer" / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        base = js[js.index("    canada:"):].split("base:", 1)[1].split("]", 1)[0]
        for name in ("ags:bedrock", "skgs:2", "nsgs:11"):
            self.assertIn(f'"{name}"', base)
        self.assertIn("ags: { source: gsiTileSource, info: pointInfoUrl }", js)


class AlbertaMinerals(TestCase):
    """앨버타 광물 산지 (wetherilli 321) — 피처 서비스를 한 덩이로, 갈래마다 색"""
    def setUp(self):
        import tempfile
        from django.test import override_settings
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ags-occ-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_덩이(self):
        from unittest import mock
        from viewer import ags
        page = {"features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
             "properties": {"site_name": "Clearwater", "commodity": "Lithium", "geo_age": "Lower Cretaceous",
                            "feature_layer_source": '<a href="x">Lithium Content in Groundwater and Formation Water (DIG 2019-0029)</a>'}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-114.0, 55.0]},
             "properties": {"site_name": "Unknown kind", "feature_layer_source": "something else"}}]}
        ok = mock.Mock(status_code=200, url="u", content=b"{}", json=lambda: page, elapsed=None)
        with mock.patch.object(ags.requests, "get", return_value=ok) as get, mock.patch.object(ags.usage, "paused", return_value=0):
            body = json.loads(ags.points_body("ags:minocc", "ko"))
            again = json.loads(ags.points_body("ags:minocc", "en"))
        self.assertEqual(get.call_count, 1)                                         # 한 쪽(2 000 밑)이면 한 번, 그 뒤는 캐시
        self.assertEqual([f["properties"]["code"] for f in body["features"]], ["lithium"])
        self.assertEqual(body["legend"][0]["label"], "리튬 (지하수·지층수)")
        self.assertEqual(again["legend"][0]["label"], "Lithium (groundwater and formation water)")
        self.assertEqual(body["style"], "class")
