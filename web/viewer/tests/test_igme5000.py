"""유럽 1:500만 — BGR IGME5000 (wetherilli 217). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import bgr
from viewer.models import Layer

#: 육상 연대(37) GetFeatureInfo 의 한 면 — 우랄 서쪽 가장자리. 줄였다
UNIT = {"OBJECTID": "6173", "AREA": "Null", "symbol older rock age": "T1", "metamorphic rock": "Null", "igneous rock": "Null",
        "marin geology": "Null", "ophiolite complex": "Null", "petrography1": "sandstone", "petrography2": "siltstone",
        "petrography3": "mudstone", "petrography4": "Null", "name older rock age": "Early Triassic", "regional name": "Null",
        "genetic element": "Null", "older rock age": "250", "younger rock age": "241,7"}
FAULT = {"OBJECTID": "4400", "boundary or structure line": "geological boundary", "zone": "onshore"}


def answer(body=None, status=200, ctype="image/png"):
    r = mock.Mock(status_code=status, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Parse(SimpleTestCase):
    def test_이어_부르는_레이어(self):
        self.assertEqual(bgr.split("bgr:igme5000:46+47+48"), ("igme5000", "46,47,48"))
        self.assertEqual(bgr.split("bgr:guek250:7"), ("guek250", "7"))

    def test_속성(self):
        self.assertEqual(bgr.friendly(UNIT), {"기호": "T1", "지질시대": "트라이아스기 전기", "연대 (Ma)": "241.7 – 250",
                                              "암석": "sandstone, siltstone, mudstone"})
        self.assertEqual(bgr.friendly(UNIT, "en")["지질시대"], "Early Triassic")
        self.assertEqual(bgr.friendly(FAULT), {"경계·구조선": "geological boundary"})

    def test_독일_판은_그대로(self):
        self.assertEqual(bgr.friendly({"Legendentext": "Buntsandstein", "Genese": "marin"}),
                         {"지질 단위": "Buntsandstein", "성인": "marin"})


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-igme5000-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(bgr.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_카탈로그(self):
        self.assertEqual(Layer.objects.get(name="bgr:igme5000:37").group.region, "germany")
        row = self.layers["bgr:igme5000:37"]
        self.assertEqual((row["projection"], row.get("lastZoom")), ("EPSG:3857", 11))
        self.assertIn("IGME5000", row["attribution"])
        self.assertIs(row["queryable"], True)
        self.assertIs(self.layers["bgr:igme5000:46+47+48"]["queryable"], False)
        self.assertIn("GÜK250", self.layers["bgr:guek250:7"]["attribution"])

    def test_타일은_판의_주소로_이어서(self):
        with mock.patch.object(bgr.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "bgr:igme5000:46+47+48", "version": "1.3.0", "request": "GetMap",
                                                    "crs": "EPSG:3857", "bbox": "1000000,6600000,1100000,6700000",
                                                    "width": 256, "height": 256, "format": "image/png"})
        self.assertTrue(get.call_args.args[0].endswith("/geologie/igme5000/"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "46,47,48")

    def test_누른_자리(self):
        with mock.patch.object(bgr.requests, "get",
                               return_value=answer({"features": [{"properties": UNIT}]}, ctype="application/geo+json")):
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "bgr:igme5000:37", "query_layers": "bgr:igme5000:37", "request": "GetFeatureInfo", "crs": "EPSG:3857",
                "bbox": "1000000,6600000,1100000,6700000", "width": 256, "height": 256, "i": 128, "j": 128}).json()
        props = data["features"][0]["props"]
        self.assertEqual(props["지질시대"], "트라이아스기 전기")

    def test_유럽_묶음(self):
        js = (bgr.settings.BASE_DIR / "viewer" / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        base = js[js.index("    europe:"):].split("base:", 1)[1].split("]", 1)[0]
        self.assertIn('"bgr:igme5000:37"', base)
