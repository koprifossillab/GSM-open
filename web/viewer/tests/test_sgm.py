"""멕시코 — SGM 1:25만·1:5만 (wetherilli 206). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 사카테카스 둘레에서 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import i18n, sgm
from viewer.models import Layer

#: REST identify — 별칭 열로 온다
IDENTIFY = {"results": [{"layerId": 8, "layerName": "Litología esc. 1:250,000", "attributes": {
    "Clave": "TpaeCgp", "Litología": "Conglomerado poligénico", "Roca": "Sedimentaria", "Formación": "Indeterminado",
    "Era": "Cenozoico", "Periodo": "Terciario", "Edad inicial": "Paleoceno", "Edad final": "Eoceno",
    "Tipo de unidad": "Unidad Estratigráfica", "Simbolo": "205", "ObjectId": "45326", "Shape": "Polygon"}}]}
STATS = {"features": [
    {"attributes": {"CLAVE_SGM": "TpaeCgp", "LITOLOGIA": "Conglomerado poligénico", "FORMACION": "Indeterminado",
                    "PERIODO": "Terciario", "N": 12}},
    {"attributes": {"CLAVE_SGM": "KapCz", "LITOLOGIA": "Caliza", "FORMACION": "Cuesta del Cura", "PERIODO": "Cretácico", "N": 30}}]}
RENDERER = {"drawingInfo": {"renderer": {"field1": "CLAVE_SGM", "uniqueValueInfos": [
    {"value": "KapCz", "symbol": {"color": [140, 200, 240, 255]}}]}}}
MERC = {"crs": "EPSG:3857", "bbox": "-11427734.26,2583961.0,-11349462.75,2662232.52", "width": 512, "height": 512}


def answer(body=None, status=200, content=b"\x89PNG", ctype="image/png"):
    r = mock.Mock(status_code=status, content=content, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Parse(SimpleTestCase):
    def test_속성(self):
        got = sgm.friendly(IDENTIFY["results"][0]["attributes"])
        self.assertEqual((got["기호"], got["암석"], got["갈래"], got["지질시대"]),
                         ("TpaeCgp", "Conglomerado poligénico", "Sedimentaria", "제3기 · 팔레오세~에오세"))
        self.assertNotIn("지층", got)                                       # Indeterminado 는 뺀다

    def test_에스파냐어_절_이름(self):
        self.assertEqual(i18n.age_es("Valanginiano"), "Valanginian")
        self.assertEqual(i18n.age_es("Cretácico"), "Cretaceous")
        self.assertEqual(i18n.age_es("Indeterminado"), "Indeterminado")


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-sgm-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(sgm.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="sgm:8").group.region, "mexico")
        self.assertEqual((self.layers["sgm:8"]["legend"], self.layers["sgm:7"]["minZoom"]), ("extent", 10))
        self.assertFalse(self.layers["sgm:6"]["queryable"])

    def test_타일은_REST_export_로(self):
        with mock.patch.object(sgm.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "sgm:8", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertTrue(get.call_args.args[0].endswith("/MapServer/export"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["bboxSR"], sent["size"], sent["f"]), ("show:8", "3857", "512,512", "image"))

    def test_누르면_identify(self):
        with mock.patch.object(sgm.requests, "get", return_value=answer(IDENTIFY, ctype="application/json")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "sgm:8", "query_layers": "sgm:8", "i": 256,
                                                                    "j": 256, "request": "GetFeatureInfo", **MERC}).json()
        self.assertTrue(get.call_args.args[0].endswith("/MapServer/identify"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["sr"], sent["imageDisplay"]), ("all:8", "3857", "512,512,96"))
        x, y = (float(v) for v in sent["geometry"].split(","))
        self.assertAlmostEqual(x, -11388598.5, delta=200)
        self.assertEqual(data["features"][0]["props"]["기호"], "TpaeCgp")

    def test_보는_범위의_범례(self):
        def get(url, params=None, **kw):
            return answer(STATS if url.endswith("/query") else RENDERER, ctype="application/json")
        with mock.patch.object(sgm.requests, "get", side_effect=get):
            rows = self.client.get(reverse("viewer:sgm-legend"), {"layer": "sgm:8", "bbox": "-103,22.5,-102.3,23.1"}).json()["rows"]
        self.assertEqual([(r["symbol"], r["color"]) for r in rows], [("KapCz", "#8cc8f0"), ("TpaeCgp", "#cccccc")])
        self.assertEqual(rows[0]["age"], "백악기")
        self.assertIn("Cuesta del Cura", rows[0]["lithology"])
