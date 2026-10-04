"""인도 GSI 1:200만 (wetherilli 226). 상류는 바꿔 끼운다.

그림은 BGS 의 OneGeology WMS, 속성은 GSI 의 ArcGIS Online 피처 서비스 — 2026-10-04 에 받아 본 꼴 그대로다.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import gsiindia, views

WMS = {"crs": "EPSG:3857", "bbox": "8000000,3000000,8100000,3100000", "width": "256", "height": "256", "i": "10", "j": "20"}

#: 델리 남서 — 아라발리 산맥의 아잡가르 층군
DELHI = {"INDEX_": "AJABGARH Gp.( DELHI SGp.)", "AGE": "PALAEOPROTEROZOIC - MESOPROTEROZOIC", "SUPERGROUP": "DELHI",
         "GROUP_": "AJABGARH"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Door(SimpleTestCase):
    def test_그림은_BGS(self):
        with mock.patch("viewer.gsiindia.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            gsiindia.get_map(dict(WMS, layers="gsiindia:geology,gsiindia:faults", format="image/png"))
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertIn("ogc.bgs.ac.uk", url)
        self.assertEqual((params["layers"], params["srs"]), ("IND_GSI_2M_Geology,IND_GSI_2M_Faults", "EPSG:3857"))

    def test_누른_화소를_피처_서비스의_점으로(self):
        x, y = gsiindia.point_of(WMS)
        self.assertAlmostEqual(x, 8000000 + 10.5 * 100000 / 256, places=3)
        self.assertAlmostEqual(y, 3100000 - 20.5 * 100000 / 256, places=3)
        with mock.patch("viewer.gsiindia.requests.get",
                        return_value=response({"features": [{"attributes": DELHI}]})) as get:
            data = gsiindia.get_feature_info(dict(WMS, layers="gsiindia:geology", query_layers="gsiindia:geology"))
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/FeatureServer/7/query"))
        self.assertEqual((params["inSR"], params["returnGeometry"]), ("3857", "false"))
        self.assertEqual(data["features"][0]["properties"]["GROUP_"], "AJABGARH")

    def test_선은_누르지_않는다(self):
        with self.assertRaises(gsiindia.GsiIndiaError):
            gsiindia.get_feature_info(dict(WMS, layers="gsiindia:faults", query_layers="gsiindia:faults"))


class Friendly(SimpleTestCase):
    def test_시대를_옮긴다(self):
        out = gsiindia.friendly(DELHI)
        self.assertEqual((out["이름"], out["층군"], out["초층군"]), ("AJABGARH Gp.( DELHI SGp.)", "AJABGARH", "DELHI"))
        self.assertEqual(out["지질시대"], "고원생대~중원생대")
        self.assertEqual(gsiindia.friendly(DELHI, "en")["지질시대"], "Paleoproterozoic – Mesoproterozoic")

    def test_TO_로_이은_시대(self):
        self.assertEqual(gsiindia.age("LATE CRETACEOUS - PALAEOCENE"), "백악기 후기~팔레오세")
        self.assertEqual(gsiindia.age("MESOPROTEROZOIC TO NEOPROTEROZOIC"), "중원생대~신원생대")
        self.assertEqual(gsiindia.age("MESOPROTEROZOIC - NEOPROTEOZOIC"), "중원생대~신원생대")      # 상류의 오탈자
        self.assertEqual(gsiindia.age("Unmapped Area"), "")


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_인도_탭(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["gsiindia:geology"]
        self.assertEqual((group["region"], layer["projection"], layer["noLegend"]), ("india", "EPSG:3857", True))
        self.assertFalse(rows["gsiindia:thrusts"][1]["queryable"])
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        self.assertTrue(re.search(r'india: \{ title: "인도", proj: "EPSG:3857"', js))

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for("gsiindia:geology", "gsiindia"))
        self.assertIn("gsiindia", views.MAP3D_WMS)
