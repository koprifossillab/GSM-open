"""호주 — Geoscience Australia 지표 지질도 1:250만·1:100만 (wetherilli 212). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import ga, static_tables
from viewer.models import Layer

#: WMS GetFeatureInfo geo+json 의 한 면 — 퍼스 둘레(줄였다)
PROPS = {"OBJECTID": "22470", "mapSymbol": "Cza", "plotSymbol": "Cza", "name": "alluvium 38494",
         "description": "Reworked or incised alluvium in older stream channels", "geologicHistory": "Cenozoic to Quaternary",
         "lithology": "regolith", "bodyMorphology": "Null", "resolutionScale": "1000000"}
RENDERER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "PLOTSYMBOL", "uniqueValueInfos": [
    {"value": "Ag", "symbol": {"color": [230, 120, 120, 255]}}]}}}
STATS = {"features": [{"attributes": {"plotsymbol": "Ac", "name": "chert, banded iron formation 74259", "geolhist": "Archean", "n": 3}},
                      {"attributes": {"plotsymbol": "Ag", "name": "felsic intrusives 74292", "geolhist": "Archean", "n": 49}}]}
MERC = {"crs": "EPSG:3857", "bbox": "13071000,-3990000,13149000,-3912000", "width": 512, "height": 512}


def answer(body=None, status=200, content=b"\x89PNG", ctype="image/png"):
    r = mock.Mock(status_code=status, content=content, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Friendly(SimpleTestCase):
    def test_속성(self):
        got = ga.friendly(PROPS)
        self.assertEqual((got["기호"], got["이름"], got["지질시대"], got["암석"], got["축척"]),
                         ("Cza", "alluvium 38494", "신생대~제4기", "regolith", "1:1,000,000"))
        self.assertEqual(ga.friendly(PROPS, "en")["지질시대"], "Cenozoic - Quaternary")

    def test_범위로_판을_고른다(self):
        self.assertEqual(ga.rest_layer("ga:lithostratigraphy", (110, -45, 155, -10)), 3)       # 대륙 — 1:250만
        self.assertEqual(ga.rest_layer("ga:lithostratigraphy", (117.5, -33.5, 118.2, -33.0)), 10)  # 좁다 — 1:100만


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ga-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ga.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="ga:lithostratigraphy").group.region, "australia")
        self.assertEqual(self.layers["ga:age"]["legend"], "extent")
        self.assertFalse(self.layers["ga:faults"]["queryable"])

    def test_두_판을_함께_묻는다(self):
        with mock.patch.object(ga.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "ga:lithostratigraphy", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(get.call_args.kwargs["params"]["layers"],
                         "AUS_GA_2500k_GUPoly_Lithostratigraphy,AUS_GA_1M_GUPoly_Lithostratigraphy")

    def test_속성은_geo_json(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": PROPS}]}
        with mock.patch.object(ga.requests, "get", return_value=answer(body, ctype="application/geo+json")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "ga:lithostratigraphy", "query_layers": "ga:lithostratigraphy",
                                                                    "i": 256, "j": 256, "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "application/geo+json")
        self.assertEqual(data["features"][0]["props"]["지질시대"], "신생대~제4기")

    def test_보는_범위의_범례(self):
        def get(url, params=None, **kw):
            return answer(STATS if url.endswith("/query") else RENDERER, ctype="application/json")
        with mock.patch.object(ga.requests, "get", side_effect=get) as called:
            rows = self.client.get(reverse("viewer:ga-legend"), {"layer": "ga:lithostratigraphy", "bbox": "117.5,-33.5,118.2,-33.0"}).json()["rows"]
        query = [c for c in called.call_args_list if c.args[0].endswith("/query")][0]
        self.assertTrue(query.args[0].endswith("/10/query"))                                   # 좁은 범위 — 1:100만 판
        self.assertEqual(query.kwargs["params"]["groupByFieldsForStatistics"], "plotsymbol,name,geolhist")
        self.assertEqual([(r["symbol"], r["color"]) for r in rows], [("Ag", "#e67878"), ("Ac", "#cccccc")])
        self.assertEqual(rows[0]["age"], "시생누대")

    def test_정적_판의_표(self):
        table = static_tables.tables()["ga"]
        self.assertEqual(table["layers"]["ga:age"], "AUS_GA_2500k_GUPoly_Age,AUS_GA_1M_GUPoly_Age")


class Other(TestCase):
    """GA 의 다른 서비스 — 지질구·핵심 광물·지구물리 격자 (wetherilli 241)"""
    PROVINCE = {"provinceName": "Arunta Orogen", "type": "tectonic", "subtype": "orogen/fold belt", "rank": "superprovince",
                "olderNameAge": "Paleoproterozoic", "youngerNamedAge": "Carboniferous", "state": "NT, WA", "parentName": "Null"}
    MINE = {"objectid": "2160", "ProjectName": "Yaamba", "STATE": "QLD", "Status": "Operating mine", "Commodities": "Magnesium"}

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ga2-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ga.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_속성(self):
        got = ga.friendly(self.PROVINCE)
        self.assertEqual((got["이름"], got["지질시대"], got["갈래"]),
                         ("Arunta Orogen", "고원생대~석탄기", "tectonic · orogen/fold belt · superprovince"))
        self.assertNotIn("상위 단위", got)
        self.assertEqual(ga.friendly(self.MINE), {"이름": "Yaamba", "광종": "Magnesium", "운영": "Operating mine", "주": "QLD"})

    def test_카탈로그(self):
        self.assertEqual(Layer.objects.get(name="ga:tmi").group.region, "australia")
        self.assertIs(self.layers["ga:tmi"]["queryable"], False)
        self.assertTrue(self.layers["ga:tmi"]["noLegend"])
        self.assertNotIn("noLegend", self.layers["ga:crustal"])

    def test_격자는_png8_로(self):
        with mock.patch.object(ga.requests, "get", return_value=answer(ctype="image/png; mode=8bit")) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "ga:gravity", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertTrue(get.call_args.args[0].endswith("/gis/geophysical-grids/ows"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["format"], sent["layers"]), ("image/png8", "geophys:2019_A4_CBA_wide_linear_color_Hillshade_HSI_GeoTIFF"))
        self.assertEqual(r["Content-Type"], "image/png")

    def test_광산_셋을_한_번에(self):
        with mock.patch.object(ga.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "ga:mines", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertIn("AustralianCriticalMineralsOperatingMinesAndDeposits", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "OperatingMines,DevelopingMines,CareMaintenanceMines")
