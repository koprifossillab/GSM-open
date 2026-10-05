"""호주의 주 판 — 퀸즐랜드 GSQ·빅토리아 GSV·남호주 GSSA (wetherilli 225). 상류를 부르지 않는다.

속성·범례의 꼴은 2026-10-04 에 받은 그대로다(브리즈번 둘레의 identify, 멜버른 서쪽·애들레이드 둘레의 GetFeatureInfo JSON, 빅토리아의
`hideEmptyRules` 범례).
"""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import austates, i18n
from viewer.models import Layer

QLD = {"Rock Unit Key (Surface)": "217", "Rock Unit Name": "Bunya Phyllite", "Map Symbol": "DCy",
       "Lithological Summary": "Slate, phyllite, arenite, metabasalt", "Dominant Rock": "PELITE",
       "Rock Type": "STRATIFIED UNIT (INCLUDING VOLCANIC AND METAMORPHIC)", "Age": "DEVONIAN - CARBONIFEROUS",
       "Rock Unit Key (Solid)": "-999", "OBJECTID": "124344"}
VIC = {"name": "Castlemaine Group - Bendigonian( Ocb): generic", "description": "Sandstone, mudstone, black shale",
       "rank": "Formation [biostratigraphic]", "lithology": " mudstone (significant); shale (significant)",
       "geologichistory": "Bendigonian to Bendigonian (water [process] - hemipelagic)",
       "representativeage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician",
       "representativelowerage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician",
       "representativeupperage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician"}
SA = {"name": "Pleistocene calcrete", "description": "Undifferentiated Pleistocene calcrete.", "rank": "palaeosol",
      "lithology": "calcareous carbonate sedimentary material", "geologicHistory": "Unnamed event",
      "numericOlderAge": 1.66, "numericYoungerAge": 0.011,
      "representativeOlderAge_uri": "http://resource.geosciml.org/classifier/ics/ischart/Pleistocene",
      "representativeYoungerAge_uri": "http://resource.geosciml.org/classifier/ics/ischart/Pleistocene"}
LEGEND = {"Legend": [{"layerName": "sg_geological_unit_250k", "rules": [
    {"name": "Bullengarook Gravel (Nxu)", "title": "Bullengarook Gravel (Nxu) (1)",
     "symbolizers": [{"Polygon": {"fill": "#FEEF00"}}]},
    {"name": "Bacchus Marsh Formation (Pxb)", "title": "Bacchus Marsh Formation (Pxb) (17)",
     "symbolizers": [{"Polygon": {"fill": "#92D0FE", "fill-opacity": "1.0"}}]},
    {"name": "", "title": "(3)", "symbolizers": [{"Polygon": {"fill": "#FFFFFF"}}]},
]}]}
MERC = {"crs": "EPSG:3857", "bbox": "17000000,-3200000,17040000,-3160000", "width": 256, "height": 256}


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Friendly(SimpleTestCase):
    def test_퀸즐랜드(self):
        got = austates.gsq_friendly(QLD)
        self.assertEqual(got, {"기호": "DCy", "이름": "Bunya Phyllite", "암석": "Slate, phyllite, arenite, metabasalt",
                               "주 암석": "Pelite", "갈래": "Stratified unit (including volcanic and metamorphic)",
                               "지질시대": "데본기~석탄기"})
        self.assertEqual(austates.gsq_friendly(QLD, "en")["지질시대"], "Devonian - Carboniferous")

    def test_빅토리아는_ICS_주소에서_시대를(self):
        got = austates.gs_friendly(VIC)
        self.assertEqual(got["지질시대"], "오르도비스기 전기")                    # LowerOrdovician → Early Ordovician
        self.assertEqual(got["암석"], "mudstone (significant); shale (significant)")
        self.assertEqual(got["위계"], "Formation [biostratigraphic]")

    def test_남호주는_낙타_꼴_열과_숫자_연대(self):
        got = austates.gs_friendly(SA)
        self.assertEqual((got["이름"], got["지질시대"], got["연대 (Ma)"]), ("Pleistocene calcrete", "플라이스토세", "0.011–1.66"))

    def test_ICS_주소의_꼬리(self):
        self.assertEqual(austates.age_of_uri("http://x/ischart/UpperDevonian"), "Late Devonian")
        self.assertEqual(austates.age_of_uri("http://x/ischart/Pleistocene"), "Pleistocene")
        self.assertEqual(austates.age_of_uri(""), "")


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-austates-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(austates.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        for name, upstream in (("gsq:state", "gsq"), ("gsv:250k", "gsv"), ("gssa:units", "gssa")):
            layer = Layer.objects.get(name=name)
            self.assertEqual((layer.group.region, layer.upstream), ("australia", upstream))
        self.assertEqual(self.layers["gsq:detailed"]["minZoom"], 9)
        self.assertNotIn("minZoom", self.layers["gsq:state"])
        self.assertEqual((self.layers["gsv:250k"]["legend"], self.layers["gsv:250k"]["legendUrl"]), ("extent", "austates/legend/"))
        self.assertEqual(self.layers["gssa:units"]["legendUrl"], "austates/legend/")
        self.assertIn("CC BY 4.0", self.layers["gssa:units"]["attribution"])

    def test_퀸즐랜드는_REST_export(self):
        with mock.patch.object(austates.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "gsq:detailed", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(get.call_args.args[0].endswith("/GeologyDetailed/MapServer/export"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["bboxSR"], sent["size"]), ("show:15", 3857, "256,256"))

    def test_퀸즐랜드_속성은_identify(self):
        body = {"results": [{"layerId": 15, "attributes": QLD}]}
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gsq:detailed", "query_layers": "gsq:detailed", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        self.assertTrue(get.call_args.args[0].endswith("/identify"))
        self.assertEqual(data["features"][0]["props"]["이름"], "Bunya Phyllite")

    def test_빅토리아_남호주는_GeoServer_에_열만(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": "x", "properties": SA}]}
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gssa:units", "query_layers": "gssa:units", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((get.call_args.args[0], sent["query_layers"]),
                         ("https://sarigdata.pir.sa.gov.au/geoserver/ows", "gsmlp:GeologicUnitView"))
        self.assertIn("numericOlderAge", sent["propertyName"])
        self.assertEqual(data["features"][0]["props"]["지질시대"], "플라이스토세")
        with mock.patch.object(austates.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "gsv:50k", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "open-data-platform:sg_geological_unit_50k")

    def test_빅토리아_범례는_보는_범위의_칸(self):
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: LEGEND)) as get:
            first = self.client.get(reverse("viewer:austates-legend"), {"layer": "gsv:250k", "bbox": "144.1,-37.7,144.5,-37.3"}).json()
            self.client.get(reverse("viewer:austates-legend"), {"layer": "gsv:250k", "bbox": "144.1,-37.7,144.5,-37.3"})
        get.assert_called_once()                                                  # 두 번째는 담아 둔 것
        self.assertEqual(get.call_args.kwargs["params"]["legend_options"], "countMatched:true;hideEmptyRules:true")
        self.assertEqual([(r["lithology"], r["color"]) for r in first["rows"]],
                         [("Bacchus Marsh Formation (Pxb)", "#92D0FE"), ("Bullengarook Gravel (Nxu)", "#FEEF00")])
        wide = self.client.get(reverse("viewer:austates-legend"), {"layer": "gsv:250k", "bbox": "141,-39,150,-34"})
        self.assertEqual(wide.status_code, 422)
        self.assertEqual(self.client.get(reverse("viewer:austates-legend"), {"layer": "gssa:faults", "bbox": "1,1,2,2"}).status_code, 400)


QLD_RENDERER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "RU_NAME", "field2": "MAP_SYMBOL", "fieldDelimiter": ":",
    "uniqueValueInfos": [{"value": "Quaternary alluvium and lacustrine deposits:Qa",
                          "symbol": {"type": "esriSFS", "color": [255, 255, 230, 255]}}]}}}
QLD_STATS = {"features": [
    {"attributes": {"ru_name": "Quaternary alluvium and lacustrine deposits", "map_symbol": "Qa", "age": "QUATERNARY", "n": 12}},
    {"attributes": {"ru_name": "Bunya Phyllite, Neranleigh-Fernvale beds", "map_symbol": "DCn", "age": "DEVONIAN - CARBONIFEROUS", "n": 30}}]}
SA_SLD = """<sld:StyledLayerDescriptor><sld:Rule><sld:Name>GSSA GL Colour 244</sld:Name><ogc:Filter><ogc:PropertyIsEqualTo>
<ogc:PropertyName>gsmlp:genericSymbolizer</ogc:PropertyName>
<ogc:Literal>244</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter><sld:PolygonSymbolizer><sld:Fill>
<sld:CssParameter name="fill">#F7E39B</sld:CssParameter></sld:Fill></sld:PolygonSymbolizer></sld:Rule></sld:StyledLayerDescriptor>"""
SA_WFS = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {"name": "Fulham Sand", "genericSymbolizer": "244"}},
    {"type": "Feature", "geometry": None, "properties": {"name": "Fulham Sand", "genericSymbolizer": "244"}},
    {"type": "Feature", "geometry": None, "properties": {"name": "Hindmarsh Clay", "genericSymbolizer": "9"}}]}


class LegendsAndStructures(TestCase):
    """퀸즐랜드·남호주의 범례와 구조선 (wetherilli 232)."""

    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-austates2-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(austates.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_구조선은_누르지_않고_범례가_없다(self):
        for name, first in (("gsq:state_structure", 7), ("gsq:faults", 9), ("gsq:folds", 9), ("gssa:faults", 10)):
            row = self.layers[name]
            self.assertEqual((row["queryable"], row["noLegend"], row["minZoom"]), (False, True, first))
        with mock.patch.object(austates.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "gsq:state_structure", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertTrue(get.call_args.args[0].endswith("/GeologyState/MapServer/export"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:3,4")

    def test_퀸즐랜드_범례는_통계와_칠하기_규칙(self):
        def get(url, params=None, **kw):
            return answer(json=lambda: QLD_STATS if url.endswith("/query") else QLD_RENDERER)
        with mock.patch.object(austates.requests, "get", side_effect=get) as called:
            rows = self.client.get(reverse("viewer:austates-legend"), {"layer": "gsq:state", "bbox": "150,-29,154,-25"}).json()["rows"]
        stats = [c for c in called.call_args_list if c.args[0].endswith("/query")][0].kwargs["params"]
        self.assertEqual(stats["groupByFieldsForStatistics"], "ru_name,map_symbol,age")
        self.assertEqual([r["lithology"] for r in rows], ["DCn Bunya Phyllite, Neranleigh-Fernvale beds",
                                                          "Qa Quaternary alluvium and lacustrine deposits"])
        self.assertEqual((rows[1]["color"], rows[0]["color"]), ("#ffffe6", "#cccccc"))       # 규칙에 없는 값은 회색
        self.assertEqual(rows[0]["age"], "데본기~석탄기")

    def test_남호주_범례는_WFS_와_SLD(self):
        def get(url, params=None, **kw):
            if params.get("request") == "GetStyles":
                return answer(text=SA_SLD, content=SA_SLD.encode())
            return answer(json=lambda: SA_WFS)
        with mock.patch.object(austates.requests, "get", side_effect=get) as called:
            rows = self.client.get(reverse("viewer:austates-legend"), {"layer": "gssa:units", "bbox": "138.5,-35.0,138.7,-34.8"}).json()["rows"]
        wfs = [c for c in called.call_args_list if c.kwargs["params"].get("service") == "WFS"][0]
        self.assertTrue(wfs.args[0].endswith("/geoserver/wfs"))
        self.assertEqual((wfs.kwargs["params"]["bbox"], wfs.kwargs["params"]["propertyName"]),
                         ("138.5,-35.0,138.7,-34.8,EPSG:4326", "gsmlp:name,gsmlp:genericSymbolizer"))
        self.assertEqual([(r["lithology"], r["color"], r["count"]) for r in rows],
                         [("Fulham Sand", "#F7E39B", 2), ("Hindmarsh Clay", "#cccccc", 1)])
        wide = self.client.get(reverse("viewer:austates-legend"), {"layer": "gssa:units", "bbox": "138,-35,139,-34"})
        self.assertEqual(wide.status_code, 422)


class VictoriaGeophysics(TestCase):
    """빅토리아 중력 측점·지구물리 선형 (wetherilli 302)"""
    def test_중력_측점은_열을_골라_묻고_범례가_없다(self):
        sent = []
        body = {"features": [{"id": "g.1", "properties": {"surveyid": 199930, "station_no": 1999301593, "elev_ahd": 121.17,
                                                           "freeair": 30.43, "comp_ba": -104.78}}]}

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, url=url, content=b"{}", json=lambda: body, elapsed=None)
        with mock.patch.object(austates.requests, "get", side_effect=fake), mock.patch.object(austates.usage, "paused", return_value=0):
            got = austates.GSV.get_feature_info({"layers": "gsv:gravity", "crs": "EPSG:3857", "bbox": "0,0,1,1",
                                                  "width": 256, "height": 256, "i": 1, "j": 1})
        self.assertIn("comp_ba", sent[0]["propertyName"])
        self.assertEqual(austates.gs_friendly(got["features"][0]["properties"]),
                         {"측점": "1999301593", "조사": "199930", "표고 (m)": "121.17", "프리에어 이상 (mGal)": "30.43", "부게 이상 (mGal)": "-104.78"})
        self.assertFalse(austates.is_unit("gsv", "gsv:gravity"))
        self.assertFalse(austates.queryable("gsv", "gsv:lin_tmi"))


class TasmaniaNsw(TestCase):
    """태즈메이니아 지질(theLIST REST)·뉴사우스웨일스 광물 산지·광산(GSNSW GeoServer) (wetherilli 318)"""
    def test_태즈메이니아는_REST_export_identify(self):
        sent = []
        body = {"results": [{"attributes": {"OBJECTID": "5718", "SYMBOL": "Ts", "REGION": "Cenozoic cover sequences", "GROUP": "Null",
                                            "FORMATION": "Null", "PERIOD": "Cretaceous - Quaternary",
                                            "DESCRIPTION": "Dominantly non-marine sequences of gravel, sand"}}]}

        def fake(url, params=None, **kw):
            sent.append((url, params))
            if url.endswith("/export"):
                return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=b"png", url=url, elapsed=None)
            return mock.Mock(status_code=200, url=url, content=b"{}", json=lambda: body, elapsed=None)
        q = {"layers": "mrt:250k", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256, "i": 1, "j": 1}
        with mock.patch.object(austates.requests, "get", side_effect=fake), mock.patch.object(austates.usage, "paused", return_value=0):
            austates.TAS.get_map(q)
            got = austates.TAS.get_feature_info(q)
        self.assertEqual((sent[0][1]["layers"], sent[1][1]["layers"]), ("show:16,15", "visible:16"))
        self.assertEqual(austates.tas_friendly(got["features"][0]["properties"]),
                         {"기호": "Ts", "지역": "Cenozoic cover sequences", "지질시대": i18n.age_ko("Cretaceous - Quaternary"),
                          "설명": "Dominantly non-marine sequences of gravel, sand"})
        self.assertFalse(austates.is_unit("mrt", "mrt:250k"))                       # 범위 범례를 뜨지 않는다
        self.assertEqual(austates.first_zoom("mrt", "mrt:250k"), 11)

    def test_뉴사우스웨일스_광물(self):
        props = {"name": "Pegmatite K", "commodity": "feldspar", "mineName": "Unnamed", "observationMethod": "50K mapping",
                 "positionalAccuracy": "50 metres"}
        self.assertEqual(austates.gs_friendly(props),
                         {"이름": "Pegmatite K", "광종": "feldspar", "조사 방법": "50K mapping", "위치 정확도": "50 metres"})
        mine = {"name": "South Mine Thompsons Shaft", "status": "None", "observationMethod": "50K", "positionalAccuracy": "50"}
        self.assertEqual(austates.gs_friendly(mine), {"이름": "South Mine Thompsons Shaft", "조사 방법": "50K", "위치 정확도": "50"})
        self.assertFalse(austates.is_unit("gsnsw", "gsnsw:minocc"))
