"""영국·프랑스·유럽 — BGS·BRGM·EGDI (wetherilli 143). 상류를 부르지 않는다 — 속성의 꼴은 2026-10-02 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import bgs, brgm, egdi
from viewer.models import Layer

BGS_PROPS = {
    "OBJECTID": "63228", "LEX_D": "Pennine Lower Coal Measures Formation", "RCS_D": "Mudstone, siltstone and sandstone",
    "TYPE_D": "sedimentary bedrock", "MAX_PERIOD": "Carboniferous", "MAX_EPOCH": "Early Pennsylvanian",
    "MAX_TIME_D": "Langsettian Substage", "MIN_TIME_D": "Langsettian Substage", "GP_EQ_D": "Pennine Coal Measures Group",
    "SUBGP_EQ_D": "No Parent", "SETTING_D": "swamps, estuaries and deltas", "MAP_SRC": "ew070_Leeds",
    "LEX_WEB": "https://webapps.bgs.ac.uk/lexicon/lexicon.cfm?pub=PLCM", "FLTNAME_D": "Not Applicable",
    "BGSRED": "224",
}
BRGM_PLAIN = """GetFeatureInfo results:

Layer 'LITHO_1M_SIMPLIFIEE'
  Feature 1245:
    OBJECTID = '2025'
    CODE_GEOL = '2'
    DESCR = 'Calcaires, marnes et gypse'
    TYPE = 'Roches Sédimentaires'
    C_FOND = '55'
"""
MERC = {"crs": "EPSG:3857", "bbox": "250000,6230000,270000,6250000", "width": 512, "height": 512}


class Friendly(SimpleTestCase):
    def test_bgs_열을_추리고_시대를_옮긴다(self):
        got = bgs.friendly(BGS_PROPS)
        self.assertEqual(list(got)[:3], ["지층명", "암석", "갈래"])
        self.assertEqual(got["지질시대"], "석탄기")
        self.assertNotIn("단층 이름", got)                   # Not Applicable 은 빈 칸이다
        self.assertEqual(bgs.friendly(BGS_PROPS, "en")["지질시대"], "Carboniferous")

    def test_brgm_암상(self):
        feature = brgm.parse_plain(BRGM_PLAIN)[0]
        self.assertEqual(brgm.friendly(feature["properties"]), {"암상": "Calcaires, marnes et gypse",
                                                                "갈래": "Roches Sédimentaires"})

    def test_접두사를_뗀다(self):
        self.assertEqual(bgs.upstream_name("bgs:BGS.50k.Bedrock"), "BGS.50k.Bedrock")
        self.assertEqual(egdi.upstream_name("egdi:GeologicUnitView_Age"), "GeologicUnitView_Age")


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-europe-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for mod in (bgs, brgm, egdi):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="bgs:BGS.50k.Bedrock").group.region, "uk")
        self.assertEqual(Layer.objects.get(name="egdi:GeologicUnitView_Age").group.region, "uk")
        self.assertEqual(Layer.objects.get(name="brgm:SCAN_F_GEOL1M").group.region, "france")

    def test_줌과_누르기를_화면에_알린다(self):
        self.assertEqual(self.layers["bgs:BGS.50k.Bedrock"]["minZoom"], 13)
        scan = self.layers["brgm:SCAN_F_GEOL250"]
        self.assertEqual((scan["minZoom"], scan["lastZoom"], scan["queryable"]), (11, 12, False))
        self.assertNotIn("lastZoom", self.layers["brgm:SCAN_H_GEOL50"])
        self.assertIs(self.layers["egdi:GeologicUnitView_Age"]["queryable"], True)   # 속성을 켰다 (wetherilli 177)

    def test_bgs_타일은_접두사를_떼고(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "bgs:BGS.50k.Bedrock", "version": "1.3.0",
                                                         "request": "GetMap", **MERC})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"]), ("BGS.50k.Bedrock", "EPSG:3857"))

    def test_bgs_속성은_geojson(self):
        body = {"type": "FeatureCollection", "features": [{"properties": BGS_PROPS}]}
        with mock.patch.object(bgs.requests, "get", return_value=answer(json=mock.Mock(return_value=body))) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "bgs:BGS.50k.Bedrock", "query_layers": "bgs:BGS.50k.Bedrock", "i": 256, "j": 256,
                "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "application/geo+json")
        self.assertEqual(data["features"][0]["props"]["지층명"], "Pennine Lower Coal Measures Formation")

    def test_brgm_속성은_text_plain(self):
        with mock.patch.object(brgm.requests, "get",
                               return_value=answer(text=BRGM_PLAIN, headers={"content-type": "text/plain"})):
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "brgm:LITHO_1M_SIMPLIFIEE", "query_layers": "brgm:LITHO_1M_SIMPLIFIEE", "i": 256, "j": 256,
                "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(data["features"][0]["props"]["암상"], "Calcaires, marnes et gypse")

    def egdi_info(self, response):
        with mock.patch.object(egdi.requests, "get", return_value=response) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "egdi:GeologicUnitView_Age", "query_layers": "egdi:GeologicUnitView_Age", "i": 256, "j": 256,
                "request": "GetFeatureInfo", **MERC}).json()
        return data, get

    def test_egdi_속성은_암상_판에_묻는다(self):
        # 2026-10-04 에 파리 한복판에서 받은 꼴 — 모양은 줄였다 (wetherilli 177)
        body = {"type": "FeatureCollection", "features": [{"id": "GeologicUnitView.FR-BRGM.1960.70078",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "properties": {"name": "gu.gsml.1960", "lithology": "clay",
                           "identifier": "https://geoserver.geo-zs.si/egdi-surface-geology/id/gsmlp/GeologicUnitView/FR-BRGM.1960.70078",
                           "representativeAge_uri": "http://inspire.ec.europa.eu/codelist/GeochronologicEraValue/ionian",
                           "representativeOlderAge_uri": "http://www.opengis.net/def/nil/OGC/0/unknown"}}]}
        data, get = self.egdi_info(answer(json=mock.Mock(return_value=body)))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["query_layers"], sent["info_format"]), ("GeologicUnitView_Lithology", "application/json"))
        self.assertEqual(data["features"][0]["props"], {"암상": "clay", "지질시대": "지바절", "제공 기관": "FR-BRGM"})

    def test_egdi_시대는_통과_위아래를_옮긴다(self):
        self.assertEqual(egdi.friendly({"representativeOlderAge_uri": "x/lowerCretaceous",
                                        "representativeYoungerAge_uri": "x/upperCretaceous"}, "en"),
                         {"지질시대": "Early Cretaceous - Late Cretaceous"})

    def test_egdi_상류_예외는_오류로(self):
        data, _ = self.egdi_info(answer(json=mock.Mock(side_effect=ValueError)))
        self.assertEqual(data["features"], [])
        self.assertIn("error", data)
