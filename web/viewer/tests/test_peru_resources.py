"""페루 INGEMMET 의 광물·지구물리 (wetherilli 277) — 광물 산지·광상·사업·금속 광화대·부게 이상·항공 자력.
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import ingemmet

AZUCA = {"UNIDAD": "Azúca", "ELE_PRINC": "Au,Ag", "ESTADO": "Exploracion", "COD_TIPO": "Proyecto",
         "ST_YACIM": "Epitermales de intermedia sulfuración", "FRANJAMET": "XXI-A",
         "RECURSO": "(2022) ,19 Mt @244.00 g/t Ag; 0.77 g/t Au (Medido).", "ALTITUD": "5290", "HOJA": "30-r", "LOCALIDAD": " "}
CAMPANA = {"NOMBRE": "Cerro Campana Ragra", "ELEMENTO": "Zn - Cu", "TIPO_DEPOS": "Hidrotermal (filoniano)", "EDAD": "Ki",
           "FORMACION": "Gpo. Goyllarisquizga", "FRANJA": "Franja 4", "LINK": "https://es.calameo.com/read/000820129f8c549058f43"}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Door(SimpleTestCase):
    def test_서비스마다_export(self):
        with mock.patch.object(ingemmet.requests, "get", return_value=answer()) as get:
            ingemmet.get_tile("ingemmet:deposits", 7, 37, 66)
        self.assertTrue(get.call_args.args[0].endswith("/SERV_METALOGENETICO/MapServer/export"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:1")
        with mock.patch.object(ingemmet.requests, "get", return_value=answer()) as get:
            ingemmet.get_tile("ingemmet:aeromag", 7, 37, 66)
        self.assertTrue(get.call_args.args[0].endswith("/SERV_AEROMAGNETIICO/ImageServer/exportImage"))
        self.assertEqual(get.call_args.kwargs["params"]["noData"], "255,255,255")      # 흰 바탕을 비운다

    def test_점은_둘레의_네모로_가까운_것부터(self):
        body = {"features": [{"attributes": {"NOMBRE": "먼 곳"}, "geometry": {"x": -77.0, "y": -10.0}},
                             {"attributes": CAMPANA, "geometry": {"x": -77.19, "y": -10.011}}]}
        with mock.patch.object(ingemmet.requests, "get", return_value=answer(body, "application/json")) as get:
            rows = ingemmet.resource_attributes("ingemmet:occ_metal", -10.0112, -77.1902, 0.02)
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["geometryType"], "esriGeometryEnvelope")
        self.assertNotIn("resultRecordCount", sent)                                      # 페이지 나눔을 받지 않는다
        self.assertEqual(rows[0]["NOMBRE"], "Cerro Campana Ragra")

    def test_광화대는_그_점으로(self):
        with mock.patch.object(ingemmet.requests, "get", return_value=answer({"features": []}, "application/json")) as get:
            ingemmet.resource_attributes("ingemmet:belts", -14.5, -72.5, 0.02)
        self.assertEqual(get.call_args.kwargs["params"]["geometryType"], "esriGeometryPoint")

    def test_속성(self):
        got = ingemmet.resource_friendly("ingemmet:deposits", AZUCA)
        self.assertEqual((got["이름"], got["광종"], got["광화 지역"]), ("Azúca", "Au,Ag", "XXI-A"))
        self.assertNotIn("곳", got)                                                       # 빈칸은 뺀다
        occ = ingemmet.resource_friendly("ingemmet:occ_metal", CAMPANA)
        self.assertEqual(occ["상세"]["links"][0]["url"], CAMPANA["LINK"])


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-peru-res-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ingemmet.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_카탈로그(self):
        self.assertEqual(self.layers["ingemmet:deposits"]["tiles"], "ingemmet/deposits/{z}/{x}/{y}.png")
        self.assertEqual(self.layers["ingemmet:deposits"]["minZoom"], 7)
        self.assertTrue(self.layers["ingemmet:bouguer"]["queryable"])     # 화소 값으로 누른다 (wetherilli 336)
        self.assertTrue(self.layers["ingemmet:belts"]["noLegend"])

    def test_누른_자리(self):
        body = {"features": [{"attributes": AZUCA, "geometry": {"x": -72.47, "y": -14.57}}]}
        with mock.patch.object(ingemmet.requests, "get", return_value=answer(body, "application/json")):
            data = self.client.get(reverse("viewer:ingemmet-info"), {"layer": "ingemmet:deposits", "lat": -14.5737,
                                                                     "lon": -72.4728, "r": 0.01}).json()
        self.assertEqual(data["features"][0]["props"]["이름"], "Azúca")
