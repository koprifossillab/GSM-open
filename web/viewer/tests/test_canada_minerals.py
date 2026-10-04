"""캐나다 주의 광물 산지 (wetherilli 288) — BC·유콘 MINFILE, 온타리오 MDI, 퀘벡 가동 광산·사업, 사스카치원 SMDI(REST).
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import bcgs, ogs, sigeom, skgs, ygs

LCC = {"crs": "EPSG:3978", "bbox": "-1475622,433471,-1474622,434471", "width": 101, "height": 101}


def answer(body=None, ctype="image/png", text=""):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", text=text, headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Doors(SimpleTestCase):
    def test_BC_는_레이어마다_주소(self):
        with mock.patch.object(bcgs.requests, "get", return_value=answer({"features": []}, "application/json")) as get:
            bcgs.get_feature_info(dict(LCC, layers="bcgs:minfile", query_layers="bcgs:minfile", i=50, j=50))
        self.assertIn("/pub/WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE/ows", get.call_args.args[0])
        self.assertIn("MINFILE_NUMBER", get.call_args.kwargs["params"]["propertyName"])
        with mock.patch.object(bcgs.requests, "get", return_value=answer()) as get:
            bcgs.get_map(dict(LCC, layers="bcgs:bedrock"))
        self.assertIn("GEOL_BEDROCK_UNIT_POLY_SVW", get.call_args.args[0])

    def test_사스카치원은_REST(self):
        with mock.patch.object(skgs.requests, "get", return_value=answer()) as get:
            skgs.get_map(dict(LCC, layers="skgs:smdi"))
        self.assertTrue(get.call_args.args[0].endswith("/rest/services/Economy/Mineral_Exploration/MapServer/export"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:5")
        self.assertTrue(skgs.queryable("skgs:smdi"))

    def test_온타리오_MDI_는_REST_46(self):
        self.assertEqual(ogs.identify_params(dict(LCC, layers="ogs:11", i=50, j=50))["layers"], "all:46")


class Friendly(SimpleTestCase):
    def test_속성(self):
        bc = bcgs.friendly({"MINFILE_NUMBER": "082KNE005", "MINFILE_NAME1": "FORSTER   ", "COMMODITY_DESCRIPTION1": "Uranium   ",
                            "COMMODITY_DESCRIPTION2": "Niobium", "MINFILE_SUMMARY_URL": "http://minfile.gov.bc.ca/Summary.aspx?minfilno=082KNE005"})
        self.assertEqual((bc["이름"], bc["광종"]), ("FORSTER", "Uranium, Niobium"))
        yk = ygs.friendly({"minfile_number": "106D 025", "minfile_name": "Dublin Gulch", "main_commodity": "gold, silver", "producer_ind": "Y"})
        self.assertEqual((yk["이름"], yk["생산"]), ("Dublin Gulch", "Y"))
        on = ogs.friendly({"MDI Identifier": "MDI31C12NE00109", "Name": "Ricketts", "Primary Commodities": "Iron, Titanium", "Secondary Commodities": "Null"})
        self.assertEqual((on["이름"], on["광종"]), ("Ricketts", "Iron, Titanium"))
        self.assertNotIn("딸린 광종", on)
        sk = skgs.friendly({"SMDI": "0003", "NAME": "M.J. Moreau", "PrimaryCommodities": "Iron", "Grouping": "Iron", "AssociatedCommodities": "Null"})
        self.assertEqual((sk["광종"], sk["갈래"]), ("Iron", "Iron"))
        qc = sigeom.friendly({"NOM_MINE_PROJE": "Niobec", "SIGN_MINR": "Niobium", "SIGN_STAT_MINE_PROJE": "Mine active", "NOM_SOCIE": "Magris Resources inc."})
        self.assertEqual((qc["이름"], qc["개발 단계"], qc["회사"]), ("Niobec", "Mine active", "Magris Resources inc."))
