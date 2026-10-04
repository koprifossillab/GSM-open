"""아르헨티나 SEGEMAR 의 다른 판 — 지역 지질도·제4기 변형·화산 위험도 (wetherilli 220). 상류를 부르지 않는다.

속성의 꼴은 2026-10-04 에 받은 GetFeatureInfo 그대로다(북서부 살타 서쪽, 코리엔테스, 멘도사, 포클랜드(말비나스), 라닌 화산).
"""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import segemar
from viewer.models import Layer

MERC = {"crs": "EPSG:3857", "bbox": "-7700000,-3900000,-7500000,-3700000", "width": 256, "height": 256}


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Friendly(SimpleTestCase):
    def test_북서부는_DOS_코드를_되돌린다(self):
        got = segemar.friendly({"unidad": "Mmv", "edad": "Cret\xa0cico ( 130-80 Ma )",
                                "tipoderoca": "Rocas volc\xa0nicas mesosil¡cicas; Dep¢sitos fluviales"})
        self.assertEqual(got, {"기호": "Mmv", "암석": "Rocas volcánicas mesosilícicas; Depósitos fluviales",
                               "지질시대": "Cretácico ( 130-80 Ma )"})

    def test_북서부의_n_a_는_뺀다(self):
        self.assertNotIn("지질시대", segemar.friendly({"unidad": "X", "edad": "n/a", "tipoderoca": "y"}))

    def test_다른_판의_글은_그대로(self):
        got = segemar.friendly({"sigla": "PlQs", "edad": "PLIOCENO-CUATERNARIO",
                                "litologÍa": "Depósitos fluviales, aluviales, coluviales eólicos y glaciarios"})
        self.assertEqual(got["암석"], "Depósitos fluviales, aluviales, coluviales eólicos y glaciarios")
        self.assertEqual(got["지질시대"], "PLIOCENO-CUATERNARIO")

    def test_코리엔테스는_오랜_것부터(self):
        got = segemar.friendly({"sigla_unid": "K1_beta_sg", "nom_unidad": "SERRA GERAL + BOTUCATU, INDIFERENCIADO",
                                "litotipo1": "BASALTO", "ambiente1": "PLATEAU BASALTICO", "period_max": "JURASICO",
                                "period_min": "CRETACICO", "idade_max": 190, "idade_min": 125, "jerarquia": "FORMACION",
                                "prov_tect": "CUENCA CHACOPARANENSE"})
        self.assertEqual(got, {"기호": "K1_beta_sg", "이름": "SERRA GERAL + BOTUCATU, INDIFERENCIADO", "암석": "BASALTO",
                               "퇴적 환경": "PLATEAU BASALTICO", "층서 단위": "FORMACION", "지구조 구역": "CUENCA CHACOPARANENSE",
                               "지질시대": "JURASICO - CRETACICO", "연대 (Ma)": "125–190"})

    def test_제4기_변형(self):
        got = segemar.friendly({"id_estructura": "AR-0030", "nombre": "Falla Cerro La Cal", "tipo_estructura": "Fallas (Sin Secciones)",
                                "tipo_traza": "Inversa", "actividad": "Comprobada", "edad_ultimo_mov": "Histórico",
                                "tasa": "1-5 mm/año", "recurrencia": "1000 - 5000"})
        self.assertEqual(list(got), ["번호", "이름", "갈래", "구조 갈래", "활동성", "마지막 움직임", "움직임 속도", "재발 간격 (년)"])
        self.assertEqual(got["갈래"], "Inversa")

    def test_화산_위험도(self):
        got = segemar.friendly({"codigo": 35, "nombre": "Lanín", "indice_peligrosidad": 11, "nivel_de_peligrosidad": "Alto",
                                "observaciones": "", "fecha": "03-04-2024",
                                "referencia": "https://repositorio.segemar.gov.ar/handle/308849217/4417"})
        self.assertEqual(got, {"이름": "Lanín", "위험도": "Alto", "위험 지수": "11", "평가일": "03-04-2024",
                               "문헌": "https://repositorio.segemar.gov.ar/handle/308849217/4417"})


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ar-more-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(segemar.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗(self):
        for name in ("segemar:e1M.NOA.Geol", "segemar:e750K.ProvMendozaGeol", "segemar:e500K.Front.ArCh.Geol",
                     "segemar:e250K.IslasMalvinasGeol", "segemar:DeformacionesCuaternarias_250K",
                     "segemar:e2.5M.VolcanesEvaluacionPeligrosidad"):
            self.assertEqual(Layer.objects.get(name=name).group.region, "argentina")
        self.assertIs(self.layers["segemar:e750K.ProvEstr"]["noLegend"], True)
        self.assertNotIn("noLegend", self.layers["segemar:e750K.ProvMendozaGeol"])

    def test_주별_구조선은_여섯을_한_번에(self):
        with mock.patch.object(segemar.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "segemar:e750K.ProvEstr", "version": "1.3.0",
                                                     "request": "GetMap", **MERC})
        layers = get.call_args.kwargs["params"]["layers"].split(",")
        self.assertEqual(len(layers), 6)
        self.assertIn("sigam:e750K.ProvChubutEstruct", layers)
        with self.assertRaises(segemar.SegemarError):
            segemar.get_legend("segemar:e750K.ProvEstr")

    def test_코리엔테스_속성은_열만(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None,
                                                           "properties": {"sigla_unid": "K1_beta_sg"}}]}
        with mock.patch.object(segemar.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "segemar:e1M.SH21.Geol", "query_layers": "segemar:e1M.SH21.Geol",
                "i": 128, "j": 128, "request": "GetFeatureInfo", **MERC}).json()
        self.assertIn("period_max", get.call_args.kwargs["params"]["propertyName"])     # 안 붙이면 한 번에 0.8 MB
        self.assertEqual(data["features"][0]["props"]["기호"], "K1_beta_sg")
