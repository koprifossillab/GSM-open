"""독일·스페인·아일랜드 — BGR·IGME·GSI·GSNI (wetherilli 147). 상류를 부르지 않는다 — 속성의 꼴은 2026-10-02 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import bgr, bgs, gsi, igme
from viewer.models import Layer

ESRI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<FeatureInfoResponse version="1.3.0" xmlns:esri_wms="http://www.esri.com/wms" xmlns="http://www.esri.com/wms">
<FeatureInfoCollection layername="Litologias color Geologico 1M"><FeatureInfo>
<Field><FieldName>OBJECTID</FieldName><FieldValue>16934</FieldValue></Field>
<Field><FieldName>Litologíagenérica</FieldName><FieldValue>Conglomerados; gravas; arenas y limos</FieldValue></Field>
<Field><FieldName>Litologíaespecífica</FieldName><FieldValue>Gravas, arenas, arcillas y limos</FieldValue></Field>
<Field><FieldName>Sistema</FieldName><FieldValue>CUATERNARIO</FieldValue></Field>
</FeatureInfo></FeatureInfoCollection></FeatureInfoResponse>"""
GSNI_XML = ESRI_XML.replace("Litologíagenérica", "LEX_D").replace("Conglomerados; gravas; arenas y limos",
                                                                  "LOWER BASALT FORMATION")
MERC = {"crs": "EPSG:3857", "bbox": "1050000,6660000,1060000,6670000", "width": 512, "height": 512}


class Parse(SimpleTestCase):
    def test_이름을_판과_번호로(self):
        self.assertEqual(bgr.split("bgr:guek250:7"), ("guek250", "7"))
        self.assertEqual(igme.split("igme:magna50:0,igme:magna50:2"), ("magna50", "0,2"))
        with self.assertRaises(bgr.BgrError):
            bgr.split("bgr:guek250:7,bgr:gk1000:0")        # 판이 다르면 한 번에 묻지 않는다

    def test_esri_xml_쌍반점이_든_값도_온전히(self):
        props = igme.parse_esri_xml(ESRI_XML)[0]["properties"]
        self.assertEqual(props["Litologíagenérica"], "Conglomerados; gravas; arenas y limos")
        self.assertEqual(igme.friendly(props), {"암상": "Gravas, arenas, arcillas y limos",
                                               "암석 갈래": "Conglomerados; gravas; arenas y limos",
                                               "지질시대": "CUATERNARIO"})

    def test_bgr_gsi_열(self):
        self.assertEqual(bgr.friendly({"Legendentext": "Holozän", "Stratigraphie - gesamt": "Holozän", "OBJECTID": "1"}),
                         {"지질 단위": "Holozän", "지질시대": "Holozän"})
        self.assertEqual(gsi.friendly({"Rock Unit Name": "Lucan Formation", "Description": "Dark limestone & shale"}),
                         {"지질 단위": "Lucan Formation", "암석": "Dark limestone & shale"})


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-europe-more-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for mod in (bgr, igme, gsi, bgs):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="bgr:guek250:7").group.region, "germany")
        self.assertEqual(Layer.objects.get(name="igme:magna50:0").group.region, "spain")
        self.assertEqual(Layer.objects.get(name="gsni:5").group.region, "ireland")
        self.assertEqual(Layer.objects.get(name="gsni:5").group, Layer.objects.get(name="gsi:1m:IE_GSI_GSNI_Faults_1M_IE32_ITM").group)

    def test_투영과_줌(self):
        self.assertEqual(self.layers["igme:geologico1m:0"]["projection"], "EPSG:4326")
        self.assertEqual(self.layers["igme:magna50:0"]["minZoom"], 11)
        guek = self.layers["bgr:guek250:7"]
        self.assertEqual((guek["minZoom"], guek["lastZoom"]), (10, 14))
        self.assertNotIn("minZoom", self.layers["gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM"])

    def test_bgr_타일은_판의_주소로(self):
        with mock.patch.object(bgr.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "bgr:guek250:7", "version": "1.3.0",
                                                         "request": "GetMap", **MERC})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(get.call_args.args[0].endswith("/guek250/"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "7")

    def test_igme_1m_은_1_3_0_의_4326_범위를_뒤집는다(self):
        with mock.patch.object(igme.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "igme:geologico1m:0", "version": "1.3.0", "crs": "EPSG:4326",
                                                     "bbox": "39.375,-5.625,42.1875,-2.8125", "width": 512, "height": 512,
                                                     "request": "GetMap"})
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["version"], sent["bbox"]), ("1.1.1", "-5.625,39.375,-2.8125,42.1875"))

    def test_igme_1m_속성은_esri_xml(self):
        with mock.patch.object(igme.requests, "get", return_value=answer(text=ESRI_XML)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "igme:geologico1m:0", "query_layers": "igme:geologico1m:0", "crs": "EPSG:4326",
                "bbox": "-3.8,40.3,-3.6,40.5", "width": 256, "height": 256, "i": 128, "j": 128,
                "request": "GetFeatureInfo"}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "application/vnd.esri.wms_featureinfo_xml")
        self.assertIn("IGME_Geologico_1M", get.call_args.args[0])
        self.assertEqual(data["features"][0]["props"]["지질시대"], "CUATERNARIO")

    def test_gsni_는_bgs_서버로(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer(text=GSNI_XML)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gsni:5", "query_layers": "gsni:5", "i": 128, "j": 128, "request": "GetFeatureInfo", **MERC}).json()
        self.assertIn("GeoIndex_GSNI", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["query_layers"], "5")
        self.assertEqual(data["features"][0]["props"]["지층명"], "LOWER BASALT FORMATION")


class BgsGeoIndex(SimpleTestCase):
    """영국 GeoIndex — 자력·중력·광산·광물 산지 (wetherilli 258). 꼴은 2026-10-05 에 받은 그대로"""

    def test_서비스_주소와_레이어(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer(content=b"\x89PNG", ctype="image/png")) as get:
            bgs.geoindex_get_map({"layers": "bgsgi:magnetic", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertTrue(get.call_args.args[0].endswith("/arcgis/services/GeoIndex_Onshore/geophysics/MapServer/WMSServer"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "Magnetic.anomalies.colour.shaded")

    def test_지구물리는_누르지_않는다(self):
        with mock.patch.object(bgs.requests, "get") as get:
            self.assertEqual(bgs.geoindex_get_feature_info({"layers": "bgsgi:gravity"}), {"features": []})
        get.assert_not_called()

    def test_광산과_광물_산지(self):
        self.assertEqual(bgs.geoindex_friendly({"PIT_NAME": "Mullion Gravel Pit", "PIT_STATUS": "C", "EASTING": "167795", "NORTHING": "19141"}),
                         {"이름": "Mullion Gravel Pit", "운영": "Ceased", "영국 격자": "E 167795 · N 19141"})
        self.assertEqual(bgs.geoindex_friendly({"OCCURRENCE": "Trenance", "COMMODITY": "Copper", "EASTING": "167400", "NORTHING": "17300"})["광종"],
                         "Copper")
