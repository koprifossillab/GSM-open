"""브리티시컬럼비아 BCGS·캘리포니아 CGS (wetherilli 231). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-04 에 받아 본 그대로다 — BC 는 GeoServer JSON(열을 골라), 캘리포니아는 REST identify.
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import bcgs, calgs, views

WMS = {"crs": "EPSG:3978", "bbox": "-1900000,500000,-1880000,520000", "width": "512", "height": "512", "i": "10", "j": "20"}

NICOLA = {"STRATIGRAPHIC_UNIT_CODE": "uTrNsf", "STRATIGRAPHIC_NAME": "Nicola Group",
          "ROCK_TYPE_DESCRIPTION": "mudstone, siltstone, shale fine clastic sedimentary rocks", "MAXIMUM_AGE_NAME": "Upper Triassic",
          "MINIMUM_AGE_NAME": "Upper Triassic", "MAXIMUM_AGE_VALUE": 235, "MINIMUM_AGE_VALUE": 208, "TERRANE_NAME": "Quesnel",
          "MORPHOTECTONIC_BELT": "Intermontane", "AUTHOR_NAMES": "P. Schiarizza and B. N. Church"}
YOSEMITE = {"PTYPE": "grMz", "GENERAL_LITHOLOGY": "plutonic rocks", "AGE": "Mesozoic",
            "DESCRIPTION": "Mesozoic granite, quartz monzonite, granodiorite, and quartz diorite."}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class BritishColumbia(SimpleTestCase):
    def test_3978_로_곧장_열을_골라(self):
        with mock.patch("viewer.bcgs.requests.get", return_value=response({"features": [{"properties": NICOLA}]})) as get:
            data = bcgs.get_feature_info(dict(WMS, layers="bcgs:bedrock", query_layers="bcgs:bedrock"))
        params = get.call_args[1]["params"]
        self.assertEqual((params["srs"], params["query_layers"]), ("EPSG:3978", "pub:WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW"))
        self.assertIn("STRATIGRAPHIC_NAME", params["propertyName"])               # 모양째 80 KB 를 피한다
        out = bcgs.friendly(data["features"][0]["properties"])
        self.assertEqual((out["이름"], out["지질시대"], out["연대"], out["지구조 구역"]),
                         ("Nicola Group", "트라이아스기 후기", "235–208 Ma", "Quesnel · Intermontane"))


class California(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-calgs-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_3978_export(self):
        with mock.patch("viewer.calgs.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            calgs.get_map(dict(WMS, layers="calgs:geology", format="image/png"))
        path, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(path.endswith("/MapServer/export"))
        self.assertEqual((params["bboxSR"], params["imageSR"]), ("3978", "3978"))
        with self.assertRaises(calgs.CalgsError):
            calgs.get_map(dict(WMS, crs="EPSG:4326", layers="calgs:geology"))

    def test_속성(self):
        with mock.patch("viewer.calgs.requests.get", return_value=response({"results": [{"attributes": YOSEMITE}]})) as get:
            data = calgs.get_feature_info(dict(WMS, layers="calgs:geology", query_layers="calgs:geology"))
        self.assertEqual((get.call_args[1]["params"]["layers"], get.call_args[1]["params"]["sr"]), ("all:12", "3978"))
        out = calgs.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["지질시대"]), ("grMz", "중생대"))

    def test_면_범례에_이름과_시대를_붙인다(self):
        legend = {"layers": [{"layerId": 12, "legend": [{"label": "grMz", "imageData": "GR", "contentType": "image/png"}]},
                             {"layerId": 8, "legend": [{"label": "fault, certain", "imageData": "FL", "contentType": "image/png"}]}]}
        units = {"features": [{"attributes": {"PTYPE": "grMz", "GENERAL_LITHOLOGY": "plutonic rocks", "AGE": "Mesozoic"}},
                              {"attributes": {"PTYPE": "Q", "GENERAL_LITHOLOGY": "sedimentary rocks", "AGE": "Quaternary"}}]}

        def fake(path, params=None, **kw):
            return response(legend if path.endswith("/legend") else units)
        with mock.patch("viewer.calgs.requests.get", side_effect=fake):
            got = self.client.get("/GSM/list/legend/", {"layer": "calgs:geology"}).json()
        self.assertEqual([(r["symbol"], r["lithology"], r["age"]) for r in got["rows"]],
                         [("Q", "sedimentary rocks", "제4기"), ("grMz", "plutonic rocks", "중생대"), ("", "fault, certain", "")])
        self.assertTrue(got["rows"][1]["swatch"].endswith("base64,GR"))


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_캐나다_탭과_미국_탭에(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["bcgs:bedrock"]
        self.assertEqual((group["region"], layer["projection"], layer["minZoom"]), ("canada", "EPSG:3978", 11))
        group, layer = rows["calgs:geology"]
        self.assertEqual((group["region"], layer["projection"], layer["maxZoom"]), ("usa", "EPSG:3978", 12))

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        for name, up in (("bcgs:bedrock", "bcgs"), ("calgs:geology", "calgs")):
            self.assertIsNotNone(prewarm.plan_for(name, up), name)
            self.assertIn(up, views.MAP3D_WMS)
