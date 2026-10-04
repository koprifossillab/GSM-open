"""아프리카 — CGMW–BRGM 1:1000만(brgm.py 의 CGMW)·BGS 지하수 지도책 나라별 1:500만(bgs.py 의 AGA) (wetherilli 207).
상류를 부르지 않는다 — 속성의 꼴은 2026-10-04 에 나이로비 둘레에서 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import bgs, brgm
from viewer.models import Layer

CGMW_GML = """<?xml version="1.0" encoding="UTF-8"?>
<msGMLOutput xmlns:gml="http://www.opengis.net/gml">
 <AFR_CGMW_BRGM_10M_GeologicUnits_layer><gml:name>AFR CGMW-BRGM 1:10M Geological units</gml:name>
  <AFR_CGMW_BRGM_10M_GeologicUnits_feature>
   <gml:boundedBy><gml:Box srsName="EPSG:3857"><gml:coordinates>1,2 3,4</gml:coordinates></gml:Box></gml:boundedBy>
   <CODE>149.000000</CODE><STRATI>Paleogene to Pleistocene</STRATI><AGE>66 - 0.012 Ma</AGE><NOTATION>Nv</NOTATION><LITHO>Volcanic</LITHO>
  </AFR_CGMW_BRGM_10M_GeologicUnits_feature>
 </AFR_CGMW_BRGM_10M_GeologicUnits_layer>
</msGMLOutput>"""
AGA_XML = ('<?xml version="1.0" encoding="UTF-8"?><FeatureInfoResponse xmlns:esri_wms="http://www.esri.com/wms" '
           'xmlns="http://www.esri.com/wms"><FIELDS KenGLG="Igneous Volcanic" KenHGComb="I-M" OBJECTID="95"></FIELDS>'
           '</FeatureInfoResponse>')
MERC = {"crs": "EPSG:3857", "bbox": "3600000,-650000,4600000,350000", "width": 256, "height": 256}


class Parse(SimpleTestCase):
    def test_CGMW_GML_과_시대(self):
        props = brgm.parse_ms_gml(CGMW_GML)[0]["properties"]
        self.assertNotIn("{http://www.opengis.net/gml}boundedBy", props)
        self.assertEqual(brgm.cgmw_friendly(props), {"기호": "Nv", "지질시대": "고진기~플라이스토세", "연대": "66 - 0.012 Ma",
                                                    "암석": "Volcanic"})
        self.assertEqual(brgm.cgmw_friendly(props, "en")["지질시대"], "Paleogene - Pleistocene")

    def test_지도책은_나라마다_다른_GLG_열(self):
        props = bgs.parse_fields_xml(AGA_XML)[0]["properties"]
        self.assertEqual(bgs.aga_friendly(props), {"암상": "Igneous Volcanic"})
        self.assertEqual(bgs.aga_friendly({"EthGLG": "Sedimentary"}), {"암상": "Sedimentary"})

    def test_나라_서른여덟(self):
        names = bgs.AGA_LAYERS["aga:geology"]
        self.assertEqual(len(names), 38)
        self.assertIn("SDN_BGS_5M_BedrockGeology", names)                  # 기반암·표층으로 갈린 나라는 기반암
        self.assertIn("KEN_BGS_5M_Geology", names)


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
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-africa-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for mod in (bgs, brgm):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="cgmw:AFR_CGMW_BRGM_10M_GeologicUnits").group.region, "africa")
        self.assertEqual(Layer.objects.get(name="aga:geology").group.region, "africa")
        self.assertIn("CGMW", self.layers["cgmw:AFR_CGMW_BRGM_10M_Faults"]["attribution"])
        self.assertIn("CC BY-SA", self.layers["aga:geology"]["attribution"])

    def test_CGMW_타일과_GML_속성(self):
        with mock.patch.object(brgm.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "cgmw:AFR_CGMW_BRGM_10M_GeologicUnits", "version": "1.3.0",
                                                     "request": "GetMap", **MERC})
        self.assertIn("IGC35_CGMW_BRGM_Africa_Geology", get.call_args.args[0])
        self.assertEqual((get.call_args.kwargs["params"]["layers"], get.call_args.kwargs["params"]["srs"]),
                         ("AFR_CGMW_BRGM_10M_GeologicUnits", "EPSG:3857"))
        with mock.patch.object(brgm.requests, "get", return_value=answer(text=CGMW_GML)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "cgmw:AFR_CGMW_BRGM_10M_GeologicUnits", "query_layers": "cgmw:AFR_CGMW_BRGM_10M_GeologicUnits",
                "i": 128, "j": 128, "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "application/vnd.ogc.gml")
        self.assertEqual(data["features"][0]["props"]["기호"], "Nv")

    def test_CGMW_범례는_정적_PNG(self):
        with mock.patch.object(brgm.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:legend"), {"layer": "cgmw:AFR_CGMW_BRGM_10M_Faults"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.args[0], "https://mapsref.brgm.fr/legendes/ogg/cgmwafrica_fgeol_legend.png")

    def test_지도책은_나라_레이어를_이어_묻는다(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "aga:geology", "version": "1.3.0", "request": "GetMap", **MERC})
        sent = get.call_args.kwargs["params"]["layers"].split(",")
        self.assertEqual(len(sent), 38)
        self.assertIn("AGA/BGS_Groundwater", get.call_args.args[0])
        with mock.patch.object(bgs.requests, "get", return_value=answer(text=AGA_XML)):
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "aga:geology", "query_layers": "aga:geology", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        self.assertEqual(data["features"][0]["props"], {"암상": "Igneous Volcanic"})

    def test_3D_에도_선다(self):
        html = self.client.get(reverse("viewer:map3d")).content.decode()
        self.assertIn("cgmw:AFR_CGMW_BRGM_10M_GeologicUnits", html)
        self.assertIn("aga:geology", html)
