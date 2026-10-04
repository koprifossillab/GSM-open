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


# ── 같은 서버의 다른 서비스 (wetherilli 219) ─────────────────────────
#: 지질 연대 측정 점의 identify — 캄페체 해변. 줄였다
EDAD = {"OBJECTID": "20861", "Edad": "Neógeno-Mioceno", "Muestra": "ATA1.", "Estado": "Campeche", "Tipo de roca": "Sedimento",
        "Roca": "Granos de arena", "Método": "U-Pb", "Mineral": "Zircones detríticos", "Edad (millones de años)": "10.43",
        "Error": "9.4", "Tipo de edad": "Edades de procedencia", "Referencia": "Armstrong-Altrin et al., 2018", "Unidad": " ",
        "Localidad": "Playa Atasta", "Informe": " "}
PALEO = {"OBJECTID": "1", "Localidad": "La Guadalupe", "Formación": "Guzmantla", "Estado": "Oaxaca",
         "Municipio": "San José Chiltepec", "Carta INEGI": "E14-D19", "No de fósiles": "5",
         "Ver fotos": "https://www.sgm.gob.mx/PaleontologiaWeb/PaleWLocalidad.jsp?idPal=1"}
MINA = {"Nombre": "ALAMBRADA", "Sustancia": "Au, Fe", "Tipo de operación": "MANIFESTACION PEQUEÑA DE MINERAL IN SITU",
        "Tipo": "MINAS", "Origen": "SE DESCONOCE", "Estructura": "SE DESCONOCE", "Tipo de mineralización": "SE DESCONOCE",
        "Alteración": "Se Desconoce", "Escala": "Esc:1:250,000"}
EDAD_STATS = {"features": [{"attributes": {"DES_CLAV": "Cretácico Superior-Maastrichtiano", "N": 3}},
                           {"attributes": {"DES_CLAV": "Triásico Superior", "N": 7}}]}
EDAD_RENDERER = {"drawingInfo": {"renderer": {"field1": "DES_CLAV", "uniqueValueInfos": [
    {"value": "Triásico Superior", "symbol": {"color": [180, 120, 200, 255]}}]}}}


class OtherParse(SimpleTestCase):
    def test_서비스_주소(self):
        self.assertTrue(sgm._base("sgm:edades:0").endswith("/rest/services/SGM/SunEdadesGeocronologicas/MapServer"))
        self.assertTrue(sgm._base("sgm:8").endswith("/SGM/SUNGeologiaContinuoMineDatosEs/MapServer"))

    def test_지질_연대_점(self):
        got = sgm.friendly(EDAD)
        self.assertEqual((got["지질시대"], got["연대 (Ma)"], got["측정법"]), ("마이오세", "10.43 ± 9.4", "U-Pb · Zircones detríticos"))
        self.assertNotIn("단위", got)                                        # 빈칸(" ")은 뺀다
        self.assertEqual(sgm.friendly(EDAD, "en")["지질시대"], "Miocene")

    def test_고생물_광산(self):
        self.assertEqual(sgm.friendly(PALEO)["사진"]["links"][0]["url"], PALEO["Ver fotos"])
        self.assertEqual(sgm.friendly(MINA), {"이름": "ALAMBRADA", "광종": "Au, Fe",
                                              "운영": "MANIFESTACION PEQUEÑA DE MINERAL IN SITU"})     # "모른다" 는 뺀다

    def test_에스파냐어_세부_시대(self):
        self.assertEqual(i18n.age_es("Triásico Superior"), "Late Triassic")
        self.assertEqual(i18n.age_es("Neoarqueano"), "Neoarchean")
        self.assertEqual(sgm.edad("Jurásico Superior-Titoniano"), "티토누스절")


class OtherViews(Views):
    def test_다른_서비스의_씨앗(self):
        self.assertEqual(Layer.objects.get(name="sgm:paleo:0").group.region, "mexico")
        self.assertEqual(self.layers["sgm:yac:0"]["minZoom"], 8)
        self.assertEqual(self.layers["sgm:edades:0"]["legend"], "extent")
        self.assertTrue(self.layers["sgm:paleo:0"]["noLegend"])
        self.assertNotIn("queryable", {k for k, v in self.layers["sgm:yac:3"].items() if v is False})

    def test_다른_서비스의_타일(self):
        with mock.patch.object(sgm.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "sgm:yac:3", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertTrue(get.call_args.args[0].endswith("/SGM/SUNYacimientosMinerales250/MapServer/export"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:3")

    def test_지질_연대_범례(self):
        def get(url, params=None, **kw):
            return answer(EDAD_STATS if url.endswith("/query") else EDAD_RENDERER, ctype="application/json")
        with mock.patch.object(sgm.requests, "get", side_effect=get) as called:
            rows = self.client.get(reverse("viewer:sgm-legend"),
                                   {"layer": "sgm:edades:0", "bbox": "-110,20,-95,30"}).json()["rows"]
        self.assertIn("/SGM/SunEdadesGeocronologicas/MapServer/0/query", called.call_args_list[0].args[0])
        self.assertEqual([(r["lithology"], r["color"]) for r in rows],
                         [("트라이아스기 후기", "#b478c8"), ("마스트리히트절", "#cccccc")])
