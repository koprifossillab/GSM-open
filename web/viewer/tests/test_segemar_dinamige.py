"""남미 — 아르헨티나 SEGEMAR·우루과이 DINAMIGE (wetherilli 196). 상류를 부르지 않는다 — 속성·범례의 꼴은 2026-10-04 에 받은 그대로다."""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import dinamige, segemar
from viewer.models import Layer

#: 멘도사 둘레 — 1:250만(propertyName 을 붙여 받은 것)과 1:25만
AR_PROPS = {"sigla": "Qa", "nombre": "Depósitos pedemontanos", "ambiente": "Continental aluvial", "edad_inf": "Holoceno",
            "edad_sup": "Holoceno", "litologia": "Gravas, arenas", "region": "Región IV: Cordillera Principal"}
AR250_PROPS = {"cod_ulito": 33692020, "nro_hoja": "3369-II", "nom_hoja": "MENDOZA",
               "nombre": "Río Mendoza. Depósitos de conos aluviales",
               "descrip_litologica": "Conglomerados inconsolidados, gravas gruesas, arenas, arcillas y limos",
               "edad_inf": "Pleistoceno inferior", "edad_sup": "Pleistoceno superior", "jerarquia": "Unidad"}
#: 몬테비데오 둘레
UY_PROPS = {"OBJECTID": "2108", "CODIGO DE UNIDAD GEOLOGICA": "7", "NOMBRE DE UNIDAD": "COMPLEJO BASAL",
            "NOMBRE DEL GRUPO": "Null", "CODIGO": "PP_cb", "EON": "Proterozoico", "ERA": "Null", "SISTEMA": "Null",
            "SERIE": "Null", "LITOLOGIA": "Neises moscovíticos", "ORIGEN": "Igneo Metamórfico", "COMENTARIOS": "Null"}
UY_LEGEND = {"layers": [
    {"layerId": 0, "layerName": "Filones", "legend": [{"label": "", "imageData": "AAA", "contentType": "image/png"}]},
    {"layerId": 2, "layerName": "Unidades Geologicas COLOR Y TRAMA", "legend": [
        {"label": "FORMACION DOLORES - Cuaternario Pleistoceno", "imageData": "iVBOR", "contentType": "image/png"},
        {"label": "ACTUAL - Cuaternario Holoceno", "imageData": "iVBOQ", "contentType": "image/png"}]}]}
MERC = {"crs": "EPSG:3857", "bbox": "-7700000,-3900000,-7500000,-3700000", "width": 256, "height": 256}


class Friendly(SimpleTestCase):
    def test_아르헨티나_시대는_아래_위를_잇는다(self):
        self.assertEqual(segemar.friendly(AR_PROPS)["지질시대"], "Holoceno")
        got = segemar.friendly(AR250_PROPS)
        self.assertEqual(got["지질시대"], "Pleistoceno inferior - Pleistoceno superior")
        self.assertEqual(got["도폭"], "3369-II MENDOZA")
        self.assertEqual(got["암석"], "Conglomerados inconsolidados, gravas gruesas, arenas, arcillas y limos")

    def test_우루과이는_가장_잘게_가른_시대(self):
        got = dinamige.friendly(UY_PROPS)
        self.assertEqual(got, {"기호": "PP_cb", "이름": "COMPLEJO BASAL", "암석": "Neises moscovíticos",
                               "성인": "Igneo Metamórfico", "지질시대": "Proterozoico"})

    def test_이름(self):
        self.assertTrue(dinamige.knows("dinamige:2"))
        self.assertFalse(dinamige.knows("dinamige:9"))
        self.assertEqual(segemar.upstream_name("segemar:e2.5M.UnidadesGeologicas"), "e2.5M.UnidadesGeologicas")


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ar-uy-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for mod in (segemar, dinamige):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="segemar:e2.5M.UnidadesGeologicas").group.region, "argentina")
        self.assertEqual(Layer.objects.get(name="dinamige:0").group.region, "uruguay")
        self.assertEqual(self.layers["segemar:e250K_UnidadGeologica"]["minZoom"], 9)       # 간행 도폭만 — 가까이서
        self.assertEqual(self.layers["dinamige:0"]["legend"], "list")              # WMS 0 이 지질 단위다
        self.assertIs(self.layers["dinamige:2"]["noLegend"], True)
        self.assertIn("SEGEMAR", self.layers["segemar:e2.5M.Estructuras"]["attribution"])

    def test_아르헨티나_타일은_워크스페이스를_붙여_3857(self):
        with mock.patch.object(segemar.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "segemar:e2.5M.UnidadesGeologicas", "version": "1.3.0",
                                                         "request": "GetMap", **MERC})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"]), ("sigam:e2.5M.UnidadesGeologicas", "EPSG:3857"))
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], "GSM/0.1")

    def test_아르헨티나_속성은_열만(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": AR_PROPS}]}
        with mock.patch.object(segemar.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "segemar:e2.5M.UnidadesGeologicas", "query_layers": "segemar:e2.5M.UnidadesGeologicas",
                "i": 128, "j": 128, "request": "GetFeatureInfo", **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["info_format"], "application/json")
        self.assertIn("edad_inf", sent["propertyName"])                     # 기하를 떼고 받는다
        self.assertEqual(data["features"][0]["props"]["이름"], "Depósitos pedemontanos")

    def test_우루과이_타일과_속성(self):
        with mock.patch.object(dinamige.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "dinamige:0", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertIn("MapaBaseUnidadesGeologicasGeoS/MapServer/WMSServer", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "0")
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": UY_PROPS}]}
        with mock.patch.object(dinamige.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "dinamige:0", "query_layers": "dinamige:0", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "application/geo+json")
        self.assertEqual(data["features"][0]["props"]["기호"], "PP_cb")

    def test_우루과이_범례는_목록(self):
        with mock.patch.object(dinamige.requests, "get",
                               return_value=answer(json=lambda: UY_LEGEND, content=json.dumps(UY_LEGEND).encode())) as get:
            rows = self.client.get(reverse("viewer:dinamige-legend"), {"layer": "dinamige:0"}).json()["rows"]   # REST 2
            self.client.get(reverse("viewer:dinamige-legend"), {"layer": "dinamige:0"})
        self.assertEqual(get.call_count, 1)                                  # 캐시
        self.assertIn("/rest/services/", get.call_args.args[0])
        self.assertEqual((rows[0]["lithology"], rows[0]["age"]), ("FORMACION DOLORES", "Cuaternario Pleistoceno"))
        self.assertTrue(rows[0]["swatch"].startswith("data:image/png;base64,"))
        self.assertEqual(self.client.get(reverse("viewer:dinamige-legend"), {"layer": "dinamige:2"}).status_code, 400)

    def test_3D_에도_선다(self):
        html = self.client.get(reverse("viewer:map3d")).content.decode()
        self.assertIn("segemar:e2.5M.UnidadesGeologicas", html)
        self.assertIn("dinamige:0", html)
