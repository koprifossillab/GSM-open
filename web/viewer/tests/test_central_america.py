"""중앙아메리카·카리브 — 니카라과 INETER·도미니카공화국 SGN(IGME 서버), 미국 탭의 푸에르토리코를 빌리는 묶음 (wetherilli 242). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-05 에 받아 본 그대로다.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import igme, ineter, views

WMS = {"crs": "EPSG:3857", "bbox": "-9602000,1360000,-9582000,1380000", "width": "256", "height": "256", "i": "10", "j": "20"}

MANAGUA = {"nomencla": "BQiv", "sistema": "Cuaternario", "serie": "Holoceno", "formacion": "ningun nombre",
           "litologia": "Rocas volcanicas: lavas, tobas, cenizas"}
DR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<FeatureInfoResponse version="1.3.0" xmlns:esri_wms="http://www.esri.com/wms" xmlns="http://www.esri.com/wms">
<FeatureInfoCollection layername="DOM SGN 1:250k GeologicalUnits"><FeatureInfo>
<Field><FieldName>FID</FieldName><FieldValue>416</FieldValue></Field>
<Field><FieldName>ID_UC250k</FieldName><FieldValue>13</FieldValue></Field>
<Field><FieldName>Descriptio</FieldName><FieldValue>Igneous rocks and volcanic-sedimentary (type Formations Tireo and Duarte)</FieldValue></Field>
<Field><FieldName>System</FieldName><FieldValue>Cretaceous</FieldValue></Field>
<Field><FieldName>Series</FieldName><FieldValue>Lower Cretaceous-Upper Cretaceous</FieldValue></Field>
</FeatureInfo></FeatureInfoCollection></FeatureInfoResponse>"""


def response(body=None, *, status=200, ctype="application/json", content=None, text=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body, text=text if text is not None else content.decode("utf-8", "ignore"))


class Nicaragua(SimpleTestCase):
    def test_열을_골라_묻고_시대를_옮긴다(self):
        with mock.patch("viewer.ineter.requests.get", return_value=response({"features": [{"properties": MANAGUA}]})) as get:
            data = ineter.get_feature_info(dict(WMS, layers="ineter:geology", query_layers="ineter:geology"))
        self.assertIn("litologia", get.call_args[1]["params"]["propertyName"])
        out = ineter.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["지질시대"]), ("BQiv", "홀로세"))
        self.assertNotIn("이름", out)                                          # "ningun nombre" 은 이름이 아니다

    def test_붙여_쓴_시대(self):
        self.assertEqual(ineter.age("Mioceno Medio-Superior"), "Middle Miocene – Late Miocene")
        self.assertEqual(ineter.age("Plioceno-Pleistoceno"), "Pliocene – Pleistocene")
        self.assertEqual(ineter.age("", "Neogeno"), "Neogene")

    def test_단층은_누르지_않는다(self):
        with self.assertRaises(ineter.IneterError):
            ineter.get_feature_info(dict(WMS, layers="ineter:faults", query_layers="ineter:faults"))


class DominicanRepublic(SimpleTestCase):
    def test_다른_폴더의_판(self):
        with mock.patch("viewer.igme.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            igme.get_map(dict(WMS, layers="igme:sgnrd:0,igme:sgnrd:1", format="image/png"))
        self.assertTrue(get.call_args[0][0].endswith("/gis/services/PSysmin/IGME_SGN_EN_Geology/MapServer/WMSServer"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "0,1")

    def test_ESRI_XML_과_ICS(self):
        with mock.patch("viewer.igme.requests.get", return_value=response(content=DR_XML.encode(), ctype="text/xml", text=DR_XML)):
            data = igme.get_feature_info(dict(WMS, layers="igme:sgnrd:0", query_layers="igme:sgnrd:0"))
        out = igme.friendly(data["features"][0]["properties"])
        self.assertEqual(out["지질시대"], "백악기 전기~후기")
        self.assertTrue(out["암상"].startswith("Igneous rocks"))
        self.assertNotIn("세", out)


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_나라_탭과_묶음(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name, region in (("ineter:geology", "nicaragua"), ("igme:sgnrd:0", "dominican_republic"), ("mrdata:pr:geol", "usa")):
            group, layer = rows[name]
            self.assertEqual((group["region"], layer["projection"]), (region, "EPSG:3857"), name)
        self.assertEqual(rows["igme:sgnrd:0"][1]["legend"], "list")          # 칠하기 규칙 77 칸을 목록으로 (wetherilli 357)
        self.assertTrue(rows["igme:sgnrd:1"][1]["noLegend"])
        self.assertFalse(rows["ineter:faults"][1]["queryable"])
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        ca = re.search(r'central_america: \{ title: "중미·카리브".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        self.assertEqual(ca.replace(" ", ""), '"nicaragua","panama","dominican_republic","caribbean"')   # 카리브 248·파나마 253
        # 푸에르토리코는 미국 탭의 것을 빌린다 — 같은 레이어를 두 번 두지 않는다(wetherilli 238·242)
        self.assertIn('borrow: { usa: ["mrdata:pr:"] }', re.search(r'central_america: \{.*?\},\n', js, re.S).group(0))

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for("ineter:geology", "ineter"))
        self.assertIn("ineter", views.MAP3D_WMS)
