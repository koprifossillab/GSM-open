"""남미의 광물·지구물리 (wetherilli 265) — 브라질 SGB 광물 산출, 콜롬비아 SGC 금속광상도·지구물리, 아르헨티나 SEGEMAR 광상·자력.
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import segemar, sgb, sgc


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Brazil(SimpleTestCase):
    def test_광물_산출(self):
        got = sgb.friendly({"toponimia": "Morro do Ouro", "municipio": "Paracatu", "uf": "MG", "substancias": "Ouro",
                            "status_economico": "Mina", "importancia": "Depósito", "situacao_mina": "Em atividade"})
        self.assertEqual((got["광종"], got["곳"], got["광산"]), ("Ouro", "Morro do Ouro, Paracatu, MG", "Em atividade"))
        self.assertEqual(sgb.zooms("sgb:mineral_occurrences")[0], 6)


class Colombia(SimpleTestCase):
    def test_금속광상도_주소와_번호(self):
        self.assertEqual(sgc.split("sgc:met:11"), ("met", "11"))
        with mock.patch.object(sgc.requests, "get", return_value=answer()) as get:
            sgc.get_map({"layers": "sgc:geof:8", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertIn("Geofisica/Anomalias_Geofisicas_V2022/MapServer/WMSServer", get.call_args.args[0])

    def test_광상(self):
        got = sgc.friendly({"ID_NOM_DEP": "Cementos El Cairo S.A.", "D_PR_PAL1": "Calizas", "D_PR_PAL2": "Sin información",
                            "D_TIP_DEP1": "Marga", "IG_EST": "Productor - Cielo abierto", "D_ED_ERA": "Desconocida"})
        self.assertEqual(got, {"이름": "Cementos El Cairo S.A.", "광종": "Calizas", "광상 형태": "Marga", "운영": "Productor - Cielo abierto"})

    def test_정적_판에는_콜롬비아_1_50만만(self):
        self.assertFalse(sgc.static_ok("sgc:met:11"))


class Argentina(SimpleTestCase):
    def test_광상_속성은_열을_골라(self):
        self.assertIn("commodity", segemar.PROPERTIES["e250K.DepositMetalif"])
        got = segemar.friendly({"nombre": "Bajo de la Alumbrera", "commodity": "Cu, Au", "modelo": "Pórfido de cobre", "tamaño": "Grande"})
        self.assertEqual((got["이름"], got["광종"], got["광상 형태"], got["광상 규모"]), ("Bajo de la Alumbrera", "Cu, Au", "Pórfido de cobre", "Grande"))
