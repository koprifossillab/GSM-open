"""이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo (wetherilli 211). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-04 에 받아 본 그대로다 — ISPRA 는 GeoJSON, LNEG 는 ESRI XML, swisstopo 는 geo.admin.ch identify.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import ispra, lneg, swisstopo, views


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body, text=content.decode("utf-8", "ignore"))


WMS = {"crs": "EPSG:3857", "bbox": "1000000,5000000,1100000,5100000", "width": "256", "height": "256", "i": "10", "j": "20"}

LNEG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<FeatureInfoResponse version="1.3.0" xmlns:esri_wms="http://www.esri.com/wms" xmlns="http://www.esri.com/wms">
<FeatureInfoCollection layername="Geologia do Continente"><FeatureInfo>
<Field><FieldName>OBJECTID</FieldName><FieldValue>28</FieldValue></Field>
<Field><FieldName>Código</FieldName><FieldValue>CBP</FieldValue></Field>
<Field><FieldName>Descrição</FieldName><FieldValue>Formação de Perais: turbiditos</FieldValue></Field>
<Field><FieldName>Descrição1</FieldName><FieldValue>Complexo Xisto-Grauváquico-Grupo das Beiras</FieldValue></Field>
<Field><FieldName>Zona</FieldName><FieldValue>Zona Centro Ibérica</FieldValue></Field>
<Field><FieldName>IntrusõesPlutónicas</FieldName><FieldValue>Null</FieldValue></Field>
</FeatureInfo></FeatureInfoCollection></FeatureInfoResponse>"""


class Ispra(SimpleTestCase):
    def test_판과_번호를_가른다(self):
        with mock.patch("viewer.ispra.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            ispra.get_map(dict(WMS, layers="ispra:100k:1", format="image/png"))
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertIn("/servizi/carta_geologica_100k/MapServer/WMSServer", url)
        self.assertEqual(params["layers"], "1")
        with self.assertRaises(ispra.IspraError):
            ispra.get_map(dict(WMS, layers="ispra:1m:0,ispra:100k:1"))         # 판이 다르다

    def test_속성(self):
        out = ispra.friendly({"Genetica": "Rocce Sedimentarie", "Ambiente": "Depositi continentali e paralici",
                              "Descrizione": "Depositi deltizi", "eta_inf": "Pliocene", "eta_sup": "Olocene",
                              "Litho1": "sand", "Litho2": "Conglomerate"})
        self.assertEqual(out["지질시대"], "Pliocene – Olocene")
        self.assertEqual(out["암석"], "sand, Conglomerate")
        out = ispra.friendly({"NOME_FORMAZIONE": "tufi grigi granulari", "ETA_FORMAZIONE": "pleistocene medio",
                              "LEGENDA": "Tufi (impropr. detto &quot;peperino&quot;)"})
        self.assertEqual((out["이름"], out["지질시대"]), ("tufi grigi granulari", "pleistocene medio"))
        self.assertIn('"peperino"', out["설명"])


class Lneg(SimpleTestCase):
    def test_기호_레이어_0_은_모른다(self):
        self.assertTrue(lneg.knows("lneg:500k:2"))
        self.assertFalse(lneg.knows("lneg:500k:0"))

    def test_ESRI_XML_속성(self):
        with mock.patch("viewer.lneg.requests.get", return_value=response(content=LNEG_XML.encode(), ctype="text/xml")) as get:
            data = lneg.get_feature_info(dict(WMS, layers="lneg:500k:2", query_layers="lneg:500k:2"))
        self.assertEqual(get.call_args[1]["params"]["info_format"], "application/vnd.esri.wms_featureinfo_xml")
        out = lneg.friendly(data["features"][0]["properties"])
        self.assertEqual(out, {"기호": "CBP", "설명": "Formação de Perais: turbiditos",
                               "층군": "Complexo Xisto-Grauváquico-Grupo das Beiras", "지구조 구역": "Zona Centro Ibérica"})


class Swisstopo(SimpleTestCase):
    def test_누른_화소를_identify_로(self):
        p = swisstopo.identify_params(dict(WMS, query_layers="swisstopo:geocover"))
        self.assertEqual((p["sr"], p["layers"]), ("3857", "all:ch.swisstopo.geologie-geocover"))
        x, y = (float(v) for v in p["geometry"].split(","))
        self.assertAlmostEqual(x, 1000000 + 10.5 * 100000 / 256, places=3)
        self.assertAlmostEqual(y, 5100000 - 20.5 * 100000 / 256, places=3)

    def test_속성(self):
        hit = {"results": [{"featureId": 1, "attributes": {"litho_de": "Alluvion, undifferenziert", "chrono_de": "Holozän",
                                                            "tecto_de": "-", "litho_fr": "alluvions",
                                                            "orig_description_de": "Jüngste Alluvionen"}}]}
        with mock.patch("viewer.swisstopo.requests.get", return_value=response(hit)):
            data = swisstopo.get_feature_info(dict(WMS, layers="swisstopo:geocover"))
        self.assertEqual(swisstopo.friendly(data["features"][0]["properties"]),
                         {"암석": "Alluvion, undifferenziert", "지질시대": "Holozän", "원 설명": "Jüngste Alluvionen"})


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_나라_탭과_유럽_묶음(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name, region in (("ispra:1m:0", "italy"), ("lneg:500k:2", "portugal"), ("swisstopo:geocover", "switzerland")):
            group, layer = rows[name]
            self.assertEqual((group["region"], layer["projection"]), (region, "EPSG:3857"), name)
        self.assertEqual(rows["ispra:100k:1"][1]["minZoom"], 10)
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        europe = re.search(r'europe: \{ title: "유럽".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        for key in ("italy", "portugal", "switzerland"):
            self.assertIn(f'"{key}"', europe)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        for name, up in (("ispra:1m:0", "ispra"), ("lneg:500k:2", "lneg"), ("swisstopo:geocover", "swisstopo")):
            self.assertIsNotNone(prewarm.plan_for(name, up), name)
            self.assertIn(up, views.MAP3D_WMS)
