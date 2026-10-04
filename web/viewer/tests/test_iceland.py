"""아이슬란드 NÍ (wetherilli 216). 상류는 바꿔 끼운다.

속성의 꼴은 2026-10-04 에 받아 본 그대로다 — 1:60만은 부호뿐, 1:10만은 영어 열이 있다.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import natt, views

UNIT = "ni:ni_j600v_berg_2_jardlog_2utg_fl"
WEST = "ni:ni_j100v_vesturgosbelti_berggrunnur_1utg_fl"
WMS = {"crs": "EPSG:3413", "bbox": "1100000,-2500000,1200000,-2400000", "width": "256", "height": "256", "i": "10", "j": "20"}

#: 1:60만 — 헤클라 둘레의 역사 시대 현무암
J600 = {"objectid": 1408, "flokkur": "bnew", "jardmLandmBerg": "hra", "magnKisiloxids": "basisur", "jardsogulegurAldur": "H_iss",
        "heimild": "Haukur Jóhannesson, Kristján Sæmundsson. Jarðfræðikort 1:500.000", "nakvaemniXY": 500}
#: 1:10만 — 에이릭스요쿨
J100 = {"objectid": 511, "myndunKodi": "mob", "myndunIS": "Móberg", "myndunEN": "Hyaloclastite", "nafnfitju": "Eiríksjökull",
        "eldstodnafn": None, "aldur": "49 Ka", "jardsogulegurAldur": "Kp_wei", "segultimatal": "BRUN",
        "alduris": "Pleistósen, Weichselian", "heimild": "Sveinn P. Jakobsson"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Door(SimpleTestCase):
    def test_아는_레이어만_부른다(self):
        self.assertTrue(natt.knows(UNIT))
        self.assertTrue(natt.knows(f"{UNIT},{WEST}"))
        self.assertFalse(natt.knows("NATT:v_nest"))                    # 같은 서버의 새 둥지 — 지질이 아니다
        with self.assertRaises(natt.NattError):
            natt.get_map(dict(WMS, layers="NATT:v_nest"))

    def test_3413_으로_곧장(self):
        with mock.patch("viewer.natt.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            natt.get_map(dict(WMS, layers=UNIT, format="image/png"))
        params = get.call_args[1]["params"]
        self.assertEqual((params["srs"], params["layers"], params["version"]), ("EPSG:3413", UNIT, "1.1.1"))

    def test_속성은_geojson(self):
        with mock.patch("viewer.natt.requests.get", return_value=response({"features": [{"properties": J600}]})) as get:
            data = natt.get_feature_info(dict(WMS, layers=UNIT, query_layers=UNIT))
        params = get.call_args[1]["params"]
        self.assertEqual((params["info_format"], params["x"], params["y"]), ("application/json", "10", "20"))
        self.assertEqual(data["features"][0]["properties"]["flokkur"], "bnew")


class Friendly(SimpleTestCase):
    def test_1_60만은_부호를_범례_이름으로(self):
        out = natt.friendly(J600)
        self.assertEqual(out["암석"], "Historic basic and intermediate lavas, younger than 871 AD")
        self.assertEqual(out["지질시대"], "홀로세")
        self.assertIn("Haukur", out["출처"])
        self.assertEqual(natt.friendly(J600, "en")["지질시대"], "Holocene")

    def test_관입암은_연대를_보지_않는다(self):
        self.assertEqual(natt.unit_name({"jardmLandmBerg": "inn03", "magnKisiloxids": "sur"}), "Acid intrusions")
        self.assertEqual(natt.unit_name({"jardmLandmBerg": "xxx"}), "")

    def test_1_10만은_영어_열(self):
        out = natt.friendly(J100)
        self.assertEqual((out["이름"], out["암석"], out["연대"], out["고지자기"]), ("Eiríksjökull", "Hyaloclastite", "49 Ka", "BRUN"))
        self.assertEqual(out["지질시대"], "플라이스토세 후기")

    def test_모르는_연대_부호(self):
        self.assertEqual(natt.age_name("Kp_xyz"), "Pleistocene")       # 앞 글자로
        self.assertEqual(natt.friendly({"jardsogulegurAldur": "?", "alduris": "Nútími"})["지질시대"], "Nútími")


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_아이슬란드_탭과_북극_묶음(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows[UNIT]
        self.assertEqual((group["region"], layer["projection"]), ("iceland", "EPSG:3413"))
        self.assertTrue(layer["queryable"])
        self.assertFalse(rows["ni:ni_j600v_berg_2_brotalina_1utg_li"][1]["queryable"])
        self.assertEqual(set(natt.LAYERS), {n for n, (g, _) in rows.items() if g["region"] == "iceland"})
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        arctic = re.search(r'arctic: \{ title: "북극".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        self.assertIn('"iceland"', arctic)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for(UNIT, "natt"))
        self.assertIn("natt", views.MAP3D_WMS)
