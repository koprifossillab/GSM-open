"""브라질 — SGB GeoServer 의 1:250만(2025)·1:100만·1:25만 (wetherilli 191), 노두·연대측정·화석 산지 점 (215). 상류를 부르지 않는다.

속성과 범례의 꼴은 2026-10-04 에 브라질리아 둘레에서 받은 그대로다(`propertyName` 을 붙인 GetFeatureInfo, `hideEmptyRules` 를 단
GetLegendGraphic JSON).
"""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import sgb
from viewer.models import Layer

PROPS_1M = {"sigla": "NP3C_cortado_btm", "hierarquia": "Formação", "nome": "Formação Três Marias",
            "legenda": "Arcóseos acinzentados, quando frescos", "litotipos": "Arcóseo, Arenito, Siltito",
            "idade_min": 486, "idade_max": 635, "era_min": "Paleozóico", "era_max": "Neoproterozóico",
            "sistema_min": "Cambriano", "sistema_max": "Ediacarano", "ambiente_tectonico": "Bacias de ambiente híbrido",
            "mapa": "Carta geológica da folha Brasília"}
PROPS_2500K = {"sigla_unid": "NPC_cortado_b", "nome_unida": "Bambuí", "hierarquia": "Grupo", "idade_max": "1000",
               "idade_min": "542.1", "era_maxima": "Neoproterozóico", "periodo_ma": "Toniano", "era_minima": "Paleozóico",
               "periodo_mi": "Cambriano", "litotipo1": None, "litotipo2": "Calcário, Pelito, Calcilutito, Calcarenito",
               "classe_r_1": "Sedimentar"}
LEGEND = {"Legend": [{"layerName": "litoestratigrafia_1m", "title": "Unidades", "rules": [
    {"name": "CPsf", "title": "CPsf (44)", "filter": "[sigla = 'CPsf']",
     "symbolizers": [{"Polygon": {"fill": "#69B5D7", "fill-opacity": "1.0"}}]},
    {"title": "sigla is '' (166)", "symbolizers": [{"Polygon": {"fill": "#FFFFFF"}}]},
    {"name": "NP3C_cortado_btm", "title": "NP3C_cortado_btm (120)",
     "symbolizers": [{"Polygon": {"fill": "#C9D98B"}}, {"Line": {"stroke": "#000000"}}]},
]}]}
MERC = {"crs": "EPSG:3857", "bbox": "-5322463,-1878516,-5009377,-1565430", "width": 512, "height": 512}


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Friendly(SimpleTestCase):
    def test_1_100만(self):
        self.assertEqual(sgb.friendly(PROPS_1M), {
            "기호": "NP3C_cortado_btm", "이름": "Formação Três Marias", "위계": "Formação",
            "지질시대": "에디아카라기~캄브리아기", "연대 (Ma)": "486–635", "암석": "Arcóseo, Arenito, Siltito",
            "설명": "Arcóseos acinzentados, quando frescos", "지구조 환경": "Bacias de ambiente híbrido",
            "도폭": "Carta geológica da folha Brasília"})
        self.assertEqual(sgb.friendly(PROPS_1M, "en")["지질시대"], "Ediacaran - Cambrian")

    def test_1_250만(self):
        got = sgb.friendly(PROPS_2500K)
        self.assertEqual((got["기호"], got["이름"], got["지질시대"], got["암석"], got["연대 (Ma)"]),
                         ("NPC_cortado_b", "Bambuí", "토노스기~캄브리아기", "Calcário, Pelito, Calcilutito, Calcarenito",
                          "542.1–1000"))

    def test_포르투갈어_시대(self):
        self.assertEqual(sgb.age_en("Neoproterozóico"), "Neoproterozoic")
        self.assertEqual(sgb.age_en("Neogeno"), "Neogene")              # 덧붙임표가 빠져 와도
        self.assertEqual(sgb.age_en("Inferior"), "Inferior")            # 모르면 그대로

    def test_구조선(self):
        self.assertEqual(sgb.friendly({"nmestrutur": None, "tipo_estru": "Zona de cisalhamento"}),
                         {"갈래": "Zona de cisalhamento"})


class PointFriendly(SimpleTestCase):
    """점 레이어(wetherilli 215) — 2026-10-04 에 받은 GetFeatureInfo 의 꼴 그대로"""

    def test_노두(self):
        got = sgb.friendly({"numero_campo": "CA 441", "toponimia": "Saída de Zabelê", "municipio": "Zabelê", "uf": "PB",
                            "tipo_afloramento": "Corte de estrada", "rochas": "Xisto", "descricao": "Rocha com  granada.",
                            "projeto": "Geologia da Folha Sertânia", "folha": "Sertânia", "codigo_folha": "SC.24-X-B-I"})
        self.assertEqual(got, {"야외 번호": "CA 441", "노두 갈래": "Corte de estrada", "암석": "Xisto",
                               "설명": "Rocha com granada.", "장소": "Saída de Zabelê", "지자체": "Zabelê, PB",
                               "과제": "Geologia da Folha Sertânia", "도폭": "Sertânia (SC.24-X-B-I)"})

    def test_연대측정(self):
        got = sgb.friendly({"amostra": "Nanuque", "rocha": "Enderbito", "metodos": "Sm-Nd - Idade modelo",
                            "materiais_analisados": "Rocha total", "toponimia": None, "nivel_acesso": "Acesso restrito"})
        self.assertEqual(list(got), ["시료 번호", "암석", "측정법", "분석 재료", "자료 공개"])

    def test_화석의_시대는_원문을_편다(self):
        got = sgb.friendly({"identificacao": "CPDG000009", "sistematica": "Icnofóssil", "taxon": None, "material": "pegadas",
                            "unidade_cronoestratigrafica": "ERA CENOZOICO  \r\nPERIODO TERCIARIO\r\nEPOCA PLIOCENO",
                            "litologia": "Arenito", "observacao": "null"})
        self.assertEqual(got, {"번호": "CPDG000009", "분류": "Icnofóssil", "재료": "pegadas",
                               "층서 시대": "ERA CENOZOICO PERIODO TERCIARIO EPOCA PLIOCENO", "암석": "Arenito"})

    def test_점_레이어는_범례가_없고_노두만_가까이서(self):
        self.assertEqual([sgb.zooms(n)[0] for n in ("sgb:outcrops", "sgb:geochronology", "sgb:fossils")], [8, None, None])
        self.assertFalse({"sgb:outcrops", "sgb:geochronology", "sgb:fossils"} & set(sgb.legend_layers()))


class Views(TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="gsm-sgb-")
        patch = override_settings(TILE_CACHE_DIR=tmp, SGB_DIR=tmp)
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(sgb.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="sgb:2500k").group.region, "brazil")
        row = self.layers["sgb:1m"]
        self.assertEqual((row["projection"], row["minZoom"], row["legend"], row["legendUrl"]),
                         ("EPSG:3857", 6, "extent", "sgb/legend/"))
        self.assertTrue(self.layers["sgb:2500k_structures"]["noLegend"])
        self.assertIn("CC BY-NC", row["attribution"])

    def test_타일은_그_판의_서버로(self):
        with mock.patch.object(sgb.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "sgb:2500k", "version": "1.3.0", "request": "GetMap", **MERC})
            self.client.get(reverse("viewer:wms"), {"layers": "sgb:1m", "version": "1.3.0", "request": "GetMap", **MERC})
        (a_url,), a = get.call_args_list[0]
        (b_url,), b = get.call_args_list[1]
        self.assertEqual((a_url, a["params"]["layers"]), ("https://opendata.sgb.gov.br/geoserver/ows",
                                                         "geonode:mgbrasil_litoestratigrafia_escala_1_2500000"))
        self.assertEqual((b_url, b["params"]["layers"], b["params"]["crs"]),
                         ("https://geoservicos.sgb.gov.br/geoserver/ows", "geosgb:litoestratigrafia_1m", "EPSG:3857"))

    def test_속성에는_propertyName(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": PROPS_1M}]}
        with mock.patch.object(sgb.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "sgb:1m", "query_layers": "sgb:1m", "i": 256, "j": 256, "request": "GetFeatureInfo",
                **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["info_format"], sent["query_layers"]), ("application/json", "geosgb:litoestratigrafia_1m"))
        self.assertIn("sigla", sent["propertyName"].split(","))
        self.assertNotIn("geom", sent["propertyName"])
        self.assertEqual(data["features"][0]["props"]["이름"], "Formação Três Marias")

    def test_점_레이어(self):
        self.assertEqual(Layer.objects.get(name="sgb:fossils").group.region, "brazil")
        self.assertEqual(self.layers["sgb:outcrops"]["minZoom"], 8)
        self.assertTrue(self.layers["sgb:geochronology"]["noLegend"])
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None,
                                                           "properties": {"identificacao": "CPDG000009", "taxon": "Mesosaurus"}}]}
        with mock.patch.object(sgb.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "sgb:fossils", "query_layers": "sgb:fossils", "i": 256, "j": 256, "request": "GetFeatureInfo",
                **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["query_layers"], "geosgb:ocorrencias_fossiliferas")
        self.assertIn("taxon", sent["propertyName"].split(","))
        self.assertEqual(data["features"][0]["props"]["분류군"], "Mesosaurus")

    def test_보는_범위의_범례(self):
        Path(sgb.units_path()).write_text(json.dumps({"layers": {"sgb:1m": {
            "NP3C_cortado_btm": ["Formação Três Marias", "Ediacarano", "Cambriano"]}}}), encoding="utf-8")
        with mock.patch.object(sgb.requests, "get", return_value=answer(json=lambda: LEGEND)) as get:
            first = self.client.get(reverse("viewer:sgb-legend"), {"layer": "sgb:1m", "bbox": "-48,-16,-45,-14"}).json()
            again = self.client.get(reverse("viewer:sgb-legend"), {"layer": "sgb:1m", "bbox": "-48,-16,-45,-14"}).json()
        get.assert_called_once()                                            # 두 번째는 캐시에서
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["request"], sent["format"], sent["srs"]), ("GetLegendGraphic", "application/json", "EPSG:3857"))
        self.assertIn("hideEmptyRules:true", sent["legend_options"])
        self.assertEqual(first, again)
        # 많이 칠해진 것부터, 기호가 빈 규칙은 뺀다. 이름표에 있는 기호만 이름·시대가 붙는다
        self.assertEqual([(r["symbol"], r["color"]) for r in first["rows"]], [("NP3C_cortado_btm", "#C9D98B"), ("CPsf", "#69B5D7")])
        self.assertEqual(first["rows"][0]["lithology"], "NP3C_cortado_btm Formação Três Marias")
        self.assertEqual(first["rows"][0]["age"], "에디아카라기~캄브리아기")
        self.assertEqual((first["rows"][1]["lithology"], first["rows"][1]["age"]), ("CPsf", ""))

    def test_너무_넓으면_범례를_묻지_않는다(self):
        with mock.patch.object(sgb.requests, "get") as get:
            r = self.client.get(reverse("viewer:sgb-legend"), {"layer": "sgb:250k", "bbox": "-60,-30,-40,-10"})
            self.assertEqual(r.status_code, 422)
            self.assertEqual(self.client.get(reverse("viewer:sgb-legend"),
                                             {"layer": "sgb:2500k_structures", "bbox": "-48,-16,-45,-14"}).status_code, 400)
        get.assert_not_called()


class Units(SimpleTestCase):
    def test_쪽마다_받아_기호마다_하나(self):
        pages = [{"features": [{"properties": {"sigla_unid": "A", "nome_unida": "Alfa", "periodo_ma": "Toniano",
                                               "periodo_mi": None, "era_maxima": "x", "era_minima": "Paleozóico"}},
                               {"properties": {"sigla_unid": "A", "nome_unida": "Alfa 2"}}]},
                 {"features": [{"properties": {"sigla_unid": "B", "nome_unida": "Beta"}}]}]
        with mock.patch.object(sgb, "PAGE", 2), mock.patch.object(sgb.usage, "record"), \
                mock.patch.object(sgb.usage, "paused", return_value=0), mock.patch("time.sleep"), \
                mock.patch.object(sgb.requests, "get", side_effect=[answer(json=lambda p=p: p) for p in pages]) as get:
            units = sgb.fetch_units("sgb:2500k", log_line=lambda *_: None)
        self.assertEqual(units, {"A": ["Alfa", "Toniano", "Paleozóico"], "B": ["Beta", "", ""]})
        self.assertEqual([c.kwargs["params"]["startIndex"] for c in get.call_args_list], ["0", "2"])

    def test_1_초보다_잦게는_묻지_않는다(self):
        with self.assertRaises(CommandError):
            call_command("fetch_sgb_units", pause=0.5, stdout=io.StringIO())
