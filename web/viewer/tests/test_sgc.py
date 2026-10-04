"""남미 — SGC 남미 1:500만(CGMW)·콜롬비아 1:50만 (wetherilli 188). 상류를 부르지 않는다 — 속성의 꼴은 2026-10-04 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import sgc
from viewer.models import Layer

#: 보고타 둘레 한 자리 — 2026-10-04 에 받은 GetFeatureInfo(geo+json) 그대로
SA_PROPS = {"Object ID": "2011", "Unit code": "Es1", "Unit number": "261", "The oldest eon": "Phanerozoic",
            "The oldest era": "Cenozoic", "The oldest period": "Paleogene", "The youngest eon": "Phanerozoic",
            "The youngest era": "Cenozoic", "The youngest period": "Paleogene", "Rock type": "Sedimentary",
            "Rock classification": "Siliciclastic", "Shape": "Polygon", "SHAPE.AREA": "0.019448"}
CO_PROPS = {"OBJECTID": "5241", "Shape": "Polygon", "Símbolo UC": "Q-ca",
            "Descripción": "Abanicos aluviales y depósitos coluviales", "Edad": "Cuaternario", "Comentarios": "Null",
            "Codigo UC": "187"}
MERC = {"crs": "EPSG:3857", "bbox": "-8300000,450000,-8200000,550000", "width": 256, "height": 256}


class Parse(SimpleTestCase):
    def test_이름을_판과_번호로(self):
        self.assertEqual(sgc.split("sgc:sa:8"), ("sa", "8"))
        self.assertEqual(sgc.split("sgc:co:3,sgc:co:60"), ("co", "3,60"))
        with self.assertRaises(sgc.SgcError):
            sgc.split("sgc:sa:8,sgc:co:3")              # 판이 다르면 한 번에 묻지 않는다
        with self.assertRaises(sgc.SgcError):
            sgc.split("sgc:xx:1")

    def test_남미_판의_시대는_옮긴다(self):
        self.assertEqual(sgc.friendly(SA_PROPS), {"기호": "Es1", "지질시대": "고진기", "암석": "Sedimentary",
                                                 "암석 분류": "Siliciclastic"})
        self.assertEqual(sgc.friendly(SA_PROPS, "en")["지질시대"], "Paleogene")

    def test_가장_오랜과_젊은이_다르면_잇는다(self):
        props = dict(SA_PROPS, **{"The oldest period": "Cretaceous"})
        self.assertEqual(sgc.friendly(props, "en")["지질시대"], "Cretaceous - Paleogene")

    def test_콜롬비아_판은_에스파냐어_그대로(self):
        self.assertEqual(sgc.friendly(CO_PROPS), {"기호": "Q-ca", "암석": "Abanicos aluviales y depósitos coluviales",
                                                 "지질시대": "Cuaternario"})


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-sgc-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(sgc.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        # 콜롬비아 지역에 둘 다 둔다 — 남미 1:500만은 브라질 탭이 빌린다 (wetherilli 191)
        self.assertEqual(Layer.objects.get(name="sgc:sa:8").group.region, "colombia")
        self.assertEqual(Layer.objects.get(name="sgc:co:3").group.region, "colombia")
        self.assertNotEqual(Layer.objects.get(name="sgc:sa:8").group, Layer.objects.get(name="sgc:co:3").group)
        self.assertEqual(self.layers["sgc:co:3"]["projection"], "EPSG:3857")
        self.assertIn("CGMW", self.layers["sgc:sa:8"]["attribution"])

    def test_타일은_판의_주소로_3857(self):
        with mock.patch.object(sgc.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "sgc:co:3", "version": "1.3.0", "request": "GetMap",
                                                         **MERC})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Mapa_Geologico_Colombia_V2023/MapServer/WMSServer", get.call_args.args[0])
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"], sent["version"]), ("3", "EPSG:3857", "1.1.1"))
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], "GSM/0.1")

    def test_속성은_geo_json(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": SA_PROPS}]}
        with mock.patch.object(sgc.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "sgc:sa:8", "query_layers": "sgc:sa:8", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["info_format"], sent["query_layers"], sent["x"]), ("application/geo+json", "8", "128"))
        self.assertIn("GeologicalMapSouthAmerican", get.call_args.args[0])
        self.assertEqual(data["features"][0]["props"]["지질시대"], "고진기")
