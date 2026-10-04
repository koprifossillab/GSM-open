"""에콰도르 — IIGE 일반 지질도 (wetherilli 198). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import arcpoints, iige
from viewer.models import Layer

#: REST `query` 의 한 면 — 쿠엥카 둘레의 단구
PROPS = {"OBJECTID": "569", "LIT": " ", "TXT_12__15": " ", "COD_OK": "13.3", "ENT_GEOL": "Terraza aluvial",
         "INT_ECO": "Materiales de construcción",
         "LITOLOGIA": "Son depósitos que forman una serie de superficies niveladas en un arroyo o valle de un río"}
#: ArcGIS Pro 로 올린 새 꼴의 칠하기 규칙(`uniqueValueGroups`) — 줄였다
RENDERER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "COD_OK", "uniqueValueGroups": [
    {"heading": "COD_CAT", "classes": [
        {"label": "12.100", "symbol": {"color": [39, 180, 229, 255]}, "values": [["12.100"]]},
        {"label": "13.3", "symbol": {"color": [255, 255, 160, 255]}, "values": [["13.3"]]}]}]}}}
STATS = {"features": [{"attributes": {"COD_OK": "12.100", "ENT_GEOL": "Unidad Macuchi", "N": 4}},
                      {"attributes": {"COD_OK": "13.3", "ENT_GEOL": "Terraza aluvial", "N": 11}},
                      {"attributes": {"COD_OK": " ", "ENT_GEOL": " ", "N": 2}}]}


def answer(body=None, status=200, content=b"\x89PNG", ctype="image/png"):
    r = mock.Mock(status_code=status, content=content, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Parse(SimpleTestCase):
    def test_속성(self):
        self.assertEqual(iige.friendly(PROPS), {"이름": "Terraza aluvial", "설명": PROPS["LITOLOGIA"],
                                               "경제적 쓰임": "Materiales de construcción", "기호": "13.3"})

    def test_칠하기_규칙은_두_꼴_다(self):
        new = arcpoints.renderer_colors(RENDERER["drawingInfo"]["renderer"])
        self.assertEqual(new, {"12.100": "#27b4e5", "13.3": "#ffffa0"})
        old = arcpoints.renderer_colors({"uniqueValueInfos": [{"value": 69, "symbol": {"color": [255, 255, 190, 255]}},
                                                              {"value": "x", "symbol": {}}]})
        self.assertEqual(old, {"69": "#ffffbe"})


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-iige-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(iige.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="iige:geologia_general").group.region, "ecuador")
        row = self.layers["iige:geologia_general"]
        self.assertEqual((row["projection"], row["legend"], row["legendUrl"]), ("EPSG:3857", "extent", "iige/legend/"))

    def test_타일은_WMS_0_으로(self):
        with mock.patch.object(iige.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "iige:geologia_general", "version": "1.3.0", "request": "GetMap",
                                                    "crs": "EPSG:3857", "bbox": "-8766409,-78271,-8688138,0",
                                                    "width": 512, "height": 512})
        self.assertTrue(get.call_args.args[0].endswith("/arcgis/services/Geologia_General/MapServer/WMSServer"))
        self.assertEqual((get.call_args.kwargs["params"]["layers"], get.call_args.kwargs["params"]["crs"]), ("0", "EPSG:3857"))

    def test_보는_범위의_범례(self):
        def get(url, params=None, **kw):
            return answer(STATS if url.endswith("/query") else RENDERER, ctype="application/json")
        with mock.patch.object(iige.requests, "get", side_effect=get):
            rows = self.client.get(reverse("viewer:iige-legend"),
                                   {"layer": "iige:geologia_general", "bbox": "-79.5,-3.5,-78.5,-2.5"}).json()["rows"]
        self.assertEqual([(r["lithology"], r["color"]) for r in rows],
                         [("Terraza aluvial", "#ffffa0"), ("Unidad Macuchi", "#27b4e5")])      # 많은 것부터, 빈 값은 뺀다

    def test_남미_묶음(self):
        js = (iige.settings.BASE_DIR / "viewer" / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        self.assertIn('includes: ["colombia", "ecuador", "peru", "brazil", "uruguay", "argentina"]', js)
        first = js[js.index("    south_america:"):].split("first:", 1)[1].split("]", 1)[0]
        self.assertTrue(first.strip().startswith('["sgc:sa:8"'))                  # 대륙 바탕이 맨 밑
        self.assertNotIn("iige:", first)                                           # 에콰도르는 처음에 켜지 않는다
