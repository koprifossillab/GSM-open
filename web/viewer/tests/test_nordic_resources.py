"""북유럽의 광물·지구물리 (wetherilli 270) — 핀란드 GTK 지구물리 영상, 북유럽 광상 FODD, 스웨덴 SGU 산지·자력 이상.
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import gtk, sgu, static_tables

FODD = {"OBJECTID": "7005", "NAME": "Outokumpu", "COUNTRY": "Finland", "STATUS": "Closed mine", "WHEN_MINED": "1910-1989",
        "MAIN_COMMODITIES": "Cu,Co", "OTHER_COMMODITES": "Zn,Ni,Au,Ag", "SIZE_CATEGORY": "Large", "TOTAL_TONNAGE_MT": "29",
        "RESERVE_MT": "Null", "AGE_OF_MINERALISATION": "Palaeoproterozoic (2500-1600 Ma)"}
MORA = {"SGU Id-code": "ORED07183", "Name": "Moragruvan", "Commodity": "Ag;", "Main commodity": "Pb; Zn;",
        "Main type of deposit": "Sulphide", "Economic status": "closed mine/quarry", "Alteration": "",
        "Age of deposit": "Palaeoproterozoic", "Municipality": "Ludvika", "Tonnage (Mton)": None}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Gtk(SimpleTestCase):
    def test_서비스마다_주소(self):
        for name, url in (("gtk:fennoscandia_mineral_deposit", "kokoavaWMS"), ("gtk:aeromagneettinen_anomaliakartta", "GTK_Geofysiikka_WMS"),
                          ("gtk:kalliopera_1m_kivilajiseurueet", "GTK_Kalliopera_WMS")):
            with mock.patch.object(gtk.requests, "get", return_value=answer()) as get:
                gtk.get_map({"layers": name, "crs": "EPSG:3413", "bbox": "0,0,1,1", "width": 256, "height": 256})
            self.assertIn(f"/{url}/", get.call_args.args[0])
            self.assertEqual(get.call_args.kwargs["params"]["layers"], name[len("gtk:"):])

    def test_FODD_속성(self):
        with mock.patch.object(gtk.requests, "get", return_value=answer({"features": [{"properties": FODD}]}, "application/geo+json")) as get:
            got = gtk.get_feature_info({"layers": "gtk:fennoscandia_mineral_deposit", "query_layers": "gtk:fennoscandia_mineral_deposit",
                                        "crs": "EPSG:3413", "bbox": "0,0,1,1", "width": 101, "height": 101, "i": 50, "j": 50})
        self.assertIn("/kokoavaWMS/", get.call_args.args[0])
        props = gtk.friendly(got["features"][0]["properties"])
        self.assertEqual((props["이름"], props["광종"], props["나라"], props["총 광량 (Mt)"]), ("Outokumpu", "Cu,Co", "Finland", "29"))
        self.assertNotIn("매장량", props)


class Sgu(SimpleTestCase):
    def test_워크스페이스를_붙여_뿌리로(self):
        self.assertEqual(sgu.upstream_names("sgu:magnetic"), "fysik:SE.GOV.SGU.MAGNET")
        self.assertEqual(sgu.upstream_names("sgu:minerals"), "berg:SE.GOV.SGU.MALM.MINERALRESURSER_VY")

    def test_산지와_자력(self):
        got = sgu.friendly(MORA)
        self.assertEqual((got["이름"], got["광종"], got["딸린 광종"], got["광화 시기"]), ("Moragruvan", "Pb; Zn", "Ag", "고원생대"))
        self.assertNotIn("변질", got)
        self.assertEqual(sgu.friendly({"mag_anom": -296.9979248046875}), {"자력 이상 (nT)": "-297"})

    def test_정적_판의_표(self):
        pairs = static_tables.tables()["sgu"]["friendly"]
        self.assertIn(["Main commodity", "광종"], pairs)
        self.assertIn(["mag_anom", "자력 이상 (nT)"], pairs)
