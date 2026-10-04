"""아시아의 광물 (wetherilli 280) — 인도네시아 광물 잠재력(REST)·필리핀 광물 자원·태국 광물 산지·사우디 MODS·광화대·몽골 희토류(REST).
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import arcwms, dmr, esdm, mgb, mris, sgs

WMS = {"crs": "EPSG:3857", "bbox": "11900000,-760000,11901200,-758800", "width": 101, "height": 101}


def answer(body=None, ctype="image/png", content=b"\x89PNG"):
    r = mock.Mock(status_code=200, content=content, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Rest(SimpleTestCase):
    def test_WMS_꼴을_REST_로(self):
        got = arcwms.rest_export_params(dict(WMS), "0")
        self.assertEqual((got["bboxSR"], got["size"], got["layers"]), ("3857", "101,101", "show:0"))
        idn = arcwms.rest_identify_params(dict(WMS, i=50, j=50), "2,3,4")
        x, y = (float(v) for v in idn["geometry"].split(","))
        self.assertAlmostEqual(x, 11900600, delta=10)
        self.assertAlmostEqual(y, -759400, delta=10)
        self.assertEqual(idn["layers"], "visible:2,3,4")

    def test_인도네시아는_REST(self):
        with mock.patch.object(esdm.requests, "get", return_value=answer()) as get:
            esdm.get_map(dict(WMS, layers="esdm:metal"))
        self.assertTrue(get.call_args.args[0].endswith("/BGD_TU/Potensi_Sumber_Daya_dan_Cadangan_Mineral_Logam/MapServer/export"))
        body = {"results": [{"attributes": {"namobj": "Besi Laterit Mengandung Sari", "jnskom": "Besi Laterit",
                                            "kellgm": "Logam Besi dan Paduan Besi", "remark": "Null"}}]}
        with mock.patch.object(esdm.requests, "get", return_value=answer(body, "application/json")) as get:
            got = esdm.get_feature_info(dict(WMS, layers="esdm:metal", query_layers="esdm:metal", i=50, j=50))
        self.assertTrue(get.call_args.args[0].endswith("/identify"))
        props = esdm.friendly(got["features"][0]["properties"])
        self.assertEqual((props["광종"], props["광종 갈래"]), ("Besi Laterit", "Logam Besi dan Paduan Besi"))
        self.assertNotIn("비고", props)                                      # `Null` 은 뺀다

    def test_몽골_희토류(self):
        body = {"results": [{"attributes": {"Name": "Mushugai", "Ore_genesis": "Carbonatite", "SHEET_REF": "L-48"}}]}
        with mock.patch.object(mris.requests, "get", return_value=answer(body, "application/json")) as get:
            got = mris.get_feature_info(dict(WMS, layers="mris:ree", query_layers="mris:ree", i=50, j=50))
        self.assertIn("/Atlas/12_REE/MapServer/identify", get.call_args.args[0])
        self.assertEqual(mris.friendly(got["features"][0]["properties"]), {"이름": "Mushugai", "성인": "Carbonatite", "도폭": "L-48"})


class Wms(SimpleTestCase):
    def test_서비스마다_주소(self):
        for mod, name, part in ((mgb, "mgb:metallic", "/GDI_Metallic_Mineral_Resources_Public/MapServer/WMSServer"),
                                (dmr, "dmr:critical", "/MINERAL/CRITICAL_MINERAL/MapServer/WMSServer"),
                                (sgs, "sgs:mods", "/Geosciences/MODS/MapServer/WMSServer")):
            with mock.patch.object(mod.requests, "get", return_value=answer()) as get:
                mod.get_map(dict(WMS, layers=name))
            self.assertIn(part, get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "Mineral_Occurrences")

    def test_속성(self):
        self.assertEqual(mgb.friendly({"MINERAL": "Cu,Au", "STATUS": "Prospect", "PROVINCE": "Misamis Oriental"})["광종"], "Cu,Au")
        thai = dmr.friendly({"ชื่อทางการค้า(ภาษาอังกฤษ)": "Limestone", "ชื่อทางการค้า(ภาษาไทย)": "หินปูน", "PROVINCE_T": "เชียงราย"})
        self.assertEqual((thai["광종"], thai["곳"]), ("Limestone", "เชียงราย"))
        mods = sgs.friendly({"MODS": "MODS 0001", "English Name": "JABAL SAYID", "Major Commodity": "Copper",
                             "Occurrence Importance": "Very high"})
        self.assertEqual((mods["이름"], mods["광종"], mods["중요도"]), ("JABAL SAYID", "Copper", "Very high"))
        self.assertEqual(sgs.friendly({"LAYER": "Nabitah Bishah", "TYPE": "Gold Belt", "Lay_Val": "x"}),
                         {"이름": "Nabitah Bishah", "갈래": "Gold Belt"})
