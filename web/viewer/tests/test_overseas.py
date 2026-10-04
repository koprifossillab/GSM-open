"""프랑스 해외 영토 — 누벨칼레도니 Géorep, BRGM 의 앤틸리스·폴리네시아·레위니옹·마요트·생피에르 미클롱 스캔 (wetherilli 260).

꼴은 2026-10-05 에 받아 본 그대로다. 상류는 바꿔 끼운다.
"""
import json
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import georep, views

WMS = {"crs": "EPSG:3857", "bbox": "18520000,-2550000,18530000,-2540000", "width": "256", "height": "256", "i": "128", "j": "128"}
HIT = {"results": [{"layerId": 23, "attributes": {
    "OBJECTID": "19195", "Unité": "Flysch éocène", "Lithologie": "Flysch gréseux volcanoclastique", "Code": "e7(4)",
    "Province": "Ride de Norfolk", "Cycle": "Crétacé supérieur - Oligocène", "Période": "Paléocène - Eocène",
    "Etage": "Bartonien - Priabonien", "Etage NZ": " "}}]}


def response(body=None, *, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=200, headers={"content-type": ctype}, content=content, url="https://x/", json=lambda: body)


class NewCaledonia(SimpleTestCase):
    def test_세_축척을_한_레이어로(self):
        with mock.patch("viewer.georep.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            georep.get_map(dict(WMS, layers="georep:geology", format="image/png"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "22,23,15,17,18,2,3,4")      # WMS 번호는 REST 와 거꾸로

    def test_속성은_REST_identify(self):
        with mock.patch("viewer.georep.requests.get", return_value=response(HIT)) as get:
            data = georep.get_feature_info(dict(WMS, layers="georep:geology", query_layers="georep:geology"))
        params = get.call_args[1]["params"]
        self.assertTrue(get.call_args[0][0].endswith("/rest/services/geologie_nc/MapServer/identify"))
        self.assertEqual((params["sr"], params["layers"]), ("3857", "visible:2,9,23"))
        out = georep.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["단위"], out["지질시대"]), ("e7(4)", "Flysch éocène", "바턴절~프리아보나절"))


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def setUp(self):
        self.rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}

    def test_영토마다_지역(self):
        for name, region in (("georep:geology", "new_caledonia"), ("brgm:GEOL_MART", "caribbean"),
                             ("brgm:GEOL_PYF_6S", "french_polynesia"), ("brgm:GEOL_REU_50K", "africa"),
                             ("brgm:GEOL_SPM_50K", "canada")):
            self.assertEqual(self.rows[name][0]["region"], region, name)

    def test_스캔은_줌이_좁고_누르지_않는다(self):
        mart = self.rows["brgm:GEOL_MART"][1]
        self.assertEqual((mart["minZoom"], mart["queryable"]), (12, False))
        self.assertEqual(self.rows["brgm:GEOL_REU_100K"][1]["lastZoom"], 12)
        self.assertNotIn("brgm:GEOL_GUYTest", self.rows)                                   # 기아나는 빈 그림이라 두지 않는다


class NewCaledoniaLegend(SimpleTestCase):
    def test_목록_범례(self):
        import tempfile
        from django.test import override_settings
        data = {"layers": [{"layerId": 9, "legend": [{"label": "Alluvions", "imageData": "AAA", "contentType": "image/png"}]},
                           {"layerId": 2, "legend": [{"label": "Alluvions", "imageData": "BBB"},
                                                     {"label": "Basaltes alcalins", "imageData": "CCC"}]}]}
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-georep-")), \
                mock.patch("viewer.georep.requests.get", return_value=response(data)):
            rows = georep.legend_rows(georep.NAME)
        self.assertEqual([r["lithology"] for r in rows], ["Alluvions", "Basaltes alcalins"])   # 1:20만 먼저, 겹치면 하나
        self.assertTrue(rows[0]["swatch"].startswith("data:image/png;base64,AAA"))
