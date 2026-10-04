"""페루 — INGEMMET 1:5만·1:10만 통합판 (wetherilli 195), 따로 켜는 단층·습곡 (222). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 리마 둘레에서 받은 그대로다."""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import ingemmet, tilecache, views
from viewer.management.commands import prewarm
from viewer.models import Layer

#: REST `query`(outFields=*) 의 한 면 — 리마 남쪽 칠카층
POINT = {"OBJECTID": 30709, "CODI": 2867, "ETIQUETA": "Ki-chil3", "UNIDAD": "Grupo Casma - Formación Chilca",
         "TIPO_UNIDAD": "Volcanosedimentaria", "CTG_UNIDAD": "Formación", "LITOLOGIA": "Toba, brecha tobácea, arenisca tobácea",
         "LITO4": " ", "DESCRIP": "Tobas líticas y vítricas", "GROSOR_M": " ", "REFERENCIA": "Leon, W. & De la Cruz, O. (2003)",
         "HOJA": "25j", "E_MAX_MA": 113, "E_MIN_MA": 93.9, "PISO_MAX": "Albiano", "SERIE_MAX": "Cretácico inferior",
         "SISTEMA_MAX": "Cretácico", "SISTEMA_MIN": "Cretácico", "COMP_MINE": "<Null>"}
#: 통계 질의(`groupByFieldsForStatistics`) — 개수 열은 큰 글자 `N` 으로 온다
STATS = {"features": [
    {"attributes": {"CODI": 2871, "ETIQUETA": "Ki-sf3", "UNIDAD": "Grupo Morro Solar - Formación Salto del Fraile",
                    "SISTEMA_MAX": "Cretácico", "SISTEMA_MIN": "Cretácico", "N": 9}},
    {"attributes": {"CODI": 69, "ETIQUETA": "Q-alfl", "UNIDAD": "Depósito aluvial, fluvial",
                    "SISTEMA_MAX": "Cuaternario", "SISTEMA_MIN": "Cuaternario", "N": 40}},
    {"attributes": {"CODI": 2747, "ETIQUETA": "Ki-v3", "UNIDAD": "Grupo Puente Piedra - Formación Ventanilla",
                    "SISTEMA_MAX": "Jurásico", "SISTEMA_MIN": "Cretácico", "N": 3}},
]}
RENDERER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "CODI", "uniqueValueInfos": [
    {"value": "69", "symbol": {"color": [255, 255, 190, 255]}},
    {"value": "2871", "symbol": {"color": [140, 200, 90, 255]}},
]}}}


def answer(status=200, content=b"\x89PNG", ctype="image/png", body=None):
    r = mock.Mock(status_code=status, content=content, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Friendly(SimpleTestCase):
    def test_속성(self):
        got = ingemmet.friendly(POINT)
        self.assertEqual((got["기호"], got["이름"], got["위계"], got["지질시대"], got["연대 (Ma)"], got["도폭"]),
                         ("Ki-chil3", "Grupo Casma - Formación Chilca", "Formación", "백악기", "93.9–113", "25j"))
        self.assertNotIn("COMP_MINE", got)                                 # `<Null>`·빈칸은 뺀다
        self.assertEqual(ingemmet.friendly(POINT, "en")["지질시대"], "Cretaceous")

    def test_에스파냐어_시대(self):
        self.assertEqual(ingemmet.age_en("Jurásico"), "Jurassic")
        self.assertEqual(ingemmet.age_en("Cuaternario"), "Quaternary")
        self.assertEqual(ingemmet._span("Jurásico", "Cretácico", "en"), "Jurassic - Cretaceous")

    def test_1_10만은_열이_적다(self):
        self.assertEqual(ingemmet.friendly({"NAME": "Ki-ca", "UNIDAD": "Formación Carhuaz", "HOJA": "20h", "DESCRIP": " "}),
                         {"기호": "Ki-ca", "이름": "Formación Carhuaz", "도폭": "20h"})


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ingemmet-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ingemmet.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="ingemmet:50k").group.region, "peru")
        row = self.layers["ingemmet:50k"]
        self.assertEqual((row["tiles"], row["maxZoom"], row["legend"], row["legendUrl"]),
                         ("ingemmet/50k/{z}/{x}/{y}.png", 13, "extent", "ingemmet/legend/"))
        self.assertEqual(self.layers["ingemmet:100k"]["maxZoom"], 16)
        self.assertIn("CC BY-NC-SA", row["attribution"])

    def test_타일은_REST_캐시를_z_y_x_로(self):
        url = reverse("viewer:ingemmet-tile", kwargs={"sheet": "50k", "z": 12, "x": 1171, "y": 2186})
        with mock.patch.object(ingemmet.requests, "get", return_value=answer()) as get:
            first, again = self.client.get(url), self.client.get(url)
        get.assert_called_once()
        self.assertTrue(get.call_args.args[0].endswith(
            "/SERV_GEOLOGIA_50K_INTEGRADA/MapServer/tile/12/2186/1171"))         # 줄 먼저 — ArcGIS 의 차례
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))

    def test_캐시_밖은_빈_타일을_담는다(self):
        url = reverse("viewer:ingemmet-tile", kwargs={"sheet": "100k", "z": 16, "x": 1, "y": 1})
        with mock.patch.object(ingemmet.requests, "get", return_value=answer(404, b"no", "text/html")) as get:
            r = self.client.get(url)
            self.client.get(url)
        get.assert_called_once()
        self.assertEqual(r.content, views.tiles.blank_tile(256, 256))
        # 캐시가 없는 줌은 묻지도 않는다
        self.assertEqual(self.client.get(reverse("viewer:ingemmet-tile", kwargs={"sheet": "50k", "z": 14, "x": 0,
                                                                              "y": 0})).status_code, 404)

    def test_누른_자리(self):
        body = {"features": [{"attributes": POINT}]}
        with mock.patch.object(ingemmet.requests, "get", return_value=answer(body=body, ctype="application/json")) as get:
            data = self.client.get(reverse("viewer:ingemmet-info"), {"layer": "ingemmet:50k", "lat": -12.4, "lon": -76.7}).json()
        self.assertTrue(get.call_args.args[0].endswith("/SERV_GEOLOGIA_50K_INTEGRADA/MapServer/7/query"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["geometry"], sent["returnGeometry"], sent["inSR"]), ("-76.7,-12.4", "false", "4326"))
        self.assertEqual(data["features"][0]["props"]["지질시대"], "백악기")

    def test_보는_범위의_범례(self):
        def get(url, params=None, **kw):
            return answer(body=STATS if url.endswith("/query") else RENDERER, ctype="application/json")
        with mock.patch.object(ingemmet.requests, "get", side_effect=get) as called:
            first = self.client.get(reverse("viewer:ingemmet-legend"), {"layer": "ingemmet:50k", "bbox": "-77.35,-12.35,-76.65,-11.65"}).json()
            self.client.get(reverse("viewer:ingemmet-legend"), {"layer": "ingemmet:50k", "bbox": "-77.35,-12.35,-76.65,-11.65"})
        self.assertEqual(called.call_count, 2)                     # 질의 한 번·칠하기 규칙 한 번, 두 번째는 다 담아 둔 것
        stats = [c for c in called.call_args_list if c.args[0].endswith("/query")][0].kwargs["params"]
        self.assertEqual(stats["groupByFieldsForStatistics"], "CODI,ETIQUETA,UNIDAD,SISTEMA_MAX,SISTEMA_MIN")
        rows = first["rows"]
        self.assertEqual([r["symbol"] for r in rows], ["Q-alfl", "Ki-sf3", "Ki-v3"])     # 면이 많은 것부터
        self.assertEqual((rows[0]["color"], rows[0]["age"]), ("#ffffbe", "제4기"))
        self.assertEqual(rows[2]["color"], "#cccccc")                                    # 규칙에 없는 값
        self.assertEqual(rows[2]["age"], "쥐라기~백악기")

    def test_너무_넓으면_묻지_않는다(self):
        with mock.patch.object(ingemmet.requests, "get") as get:
            r = self.client.get(reverse("viewer:ingemmet-legend"), {"layer": "ingemmet:50k", "bbox": "-80,-18,-70,-5"})
        self.assertEqual(r.status_code, 422)
        get.assert_not_called()

    def test_단층_습곡은_따로_켠다(self):
        row = self.layers["ingemmet:faults_50k"]
        self.assertEqual((row["tiles"], row["minZoom"], row["maxZoom"], row["queryable"], row["noLegend"]),
                         ("ingemmet/faults_50k/{z}/{x}/{y}.png", 9, 18, False, True))
        self.assertNotIn("minZoom", self.layers["ingemmet:faults_1m"])
        self.assertEqual(Layer.objects.get(name="ingemmet:folds_100k").group.region, "peru")

    def test_단층_습곡은_export_를_타일_칸만큼(self):
        url = reverse("viewer:ingemmet-tile", kwargs={"sheet": "folds_50k", "z": 12, "x": 1171, "y": 2186})
        with mock.patch.object(ingemmet.requests, "get", return_value=answer()) as get:
            first, again = self.client.get(url), self.client.get(url)
        get.assert_called_once()
        self.assertTrue(get.call_args.args[0].endswith("/SERV_GEOLOGIA_FALLAS/MapServer/export"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["size"], sent["bboxSR"], sent["transparent"]), ("show:6", "256,256", 3857, "true"))
        west, south, east, north = (float(v) for v in sent["bbox"].split(","))
        self.assertAlmostEqual(east - west, 2 * 20037508.342789244 / 2 ** 12, places=2)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        # 단층·습곡은 지질도가 아니다 — 누른 자리·범례를 묻지 않는다
        self.assertEqual(self.client.get(reverse("viewer:ingemmet-info"),
                                         {"layer": "ingemmet:faults_50k", "lat": -12, "lon": -77}).status_code, 400)


class Prewarm(SimpleTestCase):
    def test_캐시가_있는_줌까지_뷰의_열쇠로(self):
        plan = prewarm.plan_for("ingemmet:50k", "ingemmet")
        self.assertIsInstance(plan, prewarm.IngemmetPlan)
        lima = (-77.1, -12.1, -77.0, -12.0)
        self.assertEqual(list(plan.tiles_for(lima, 14)), [])
        self.assertIn((12, 1171, 2186), list(plan.tiles_for(lima, 12)))
        self.assertEqual(plan.key(12, 1171, 2186), views.ingemmet_tile_key("ingemmet:50k", 12, 1171, 2186))
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(ingemmet, "get_tile", return_value=None):
            plan.fetch_block(12, 1171, 2186, 1)
            self.assertEqual(tilecache.get(plan.key(12, 1171, 2186)), views.tiles.blank_tile(256, 256))

    def test_단층_습곡은_화면이_그리는_줌부터(self):
        plan = prewarm.plan_for("ingemmet:faults_100k", "ingemmet")
        lima = (-77.1, -12.1, -77.0, -12.0)
        self.assertEqual(list(plan.tiles_for(lima, 7)), [])
        self.assertTrue(list(plan.tiles_for(lima, 15)))
