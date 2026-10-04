"""오세아니아의 광물·지구물리 (wetherilli 269) — 퀸즐랜드 광산·지구물리 영상, 빅토리아 광상, 남호주 광물 산지, 뉴질랜드 중력.
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import austates, gns


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Queensland(SimpleTestCase):
    def test_광산(self):
        got = austates.gsq_friendly({"Occurrence name": "BANTAM", "Main commodity": "GOLD", "All commodities": "Au(vs)",
                                     "Mine status": "ABANDONED MINE", "Deposit size": "VERY SMALL", "Site locality": "4KM NW OF CEMENT HILL"})
        self.assertEqual((got["이름"], got["광종"], got["광산"]), ("BANTAM", "Gold", "Abandoned mine"))

    def test_지구물리는_단위가_아니다(self):
        self.assertFalse(austates.is_unit("gsq", "gsq:mines"))
        self.assertTrue(austates.queryable("gsq", "gsq:mines"))
        self.assertFalse(austates.queryable("gsq", "gsq:gravity"))
        self.assertTrue(austates.is_unit("gsq", "gsq:state"))


class VictoriaSouthAustralia(SimpleTestCase):
    def test_속성_열은_레이어마다(self):
        with mock.patch.object(austates.requests, "get", return_value=answer({"features": []}, "application/json")) as get:
            austates.GSV.get_feature_info({"layers": "gsv:mineral", "query_layers": "gsv:mineral", "crs": "EPSG:3857",
                                           "bbox": "0,0,1,1", "width": 101, "height": 101, "i": 50, "j": 50})
        self.assertEqual(get.call_args.kwargs["params"]["propertyName"], austates.LAYER_PROPERTIES["gsv:mineral"])

    def test_광상과_광물_산지(self):
        self.assertEqual(austates.gs_friendly({"name": "KOETONG NORTH TINFIELD", "commdsc": "Tin, Tungsten", "resclad": "Minor Deposit"})["광종"],
                         "Tin, Tungsten")
        got = austates.gs_friendly({"name": "DONNAS RUSH SOUTH", "commodity": "Opal", "mineralOccurrenceType": "occurrence",
                                    "source": "https://minerals.sarig.sa.gov.au/MineralDepositDetails.aspx?x=1"})
        self.assertEqual((got["이름"], got["광종"]), ("DONNAS RUSH SOUTH", "Opal"))
        self.assertTrue(got["상세"]["links"][0]["url"].startswith("https://minerals.sarig"))


class NewZealand(SimpleTestCase):
    def test_중력은_GNS_전체_서비스로(self):
        with mock.patch.object(gns.requests, "get", return_value=answer()) as get:
            gns.get_map({"layers": "gns:gravity", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertEqual(get.call_args.args[0], "https://maps.gns.cri.nz/gns/wms")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "gns:NZGravity")
        with mock.patch.object(gns.requests, "get", return_value=answer()) as get:
            gns.get_map({"layers": "gns:NZL_GNS_1M_faults", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertEqual(get.call_args.args[0], "https://maps.gns.cri.nz/geology/wms")
