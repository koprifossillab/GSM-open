"""캐나다의 주 판 — 퀘벡 SIGÉOM·유콘 YGS, 그리고 북미 묶음 (wetherilli 210). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import io
import pathlib
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import sigeom, ygs
from viewer.models import Layer

MAPJS = pathlib.Path(__file__).resolve().parents[1] / "static" / "viewer" / "map.js"
#: 퀘벡 GeoServer GetFeatureInfo text/plain — 발도르 둘레(줄였다)
PLAIN = """Results for FeatureType 'http://geoserver-prd/geoserver/SGM:Geologie_regionale':
--------------------------------------------
STRATIGRAPHIE = Formation de Dubuisson 1([narc]du1)
AGE = Néoarchéen
DESC_ZONE_GEOLG = Basalte, basalte magnésien et volcanoclastite mafique
NOM_ABRG_ETQT_LITH = V3B
REF_EXA = <a href="https://sigeom.mines.gouv.qc.ca/signet/classes/I1103_index?l=f" target="_blank">CG-32D01D-2013-01</a>
COUL_REMPL_HEXA = #AAF6AA
GEOMETRIE = [GEOMETRY (MultiPolygon) with 8474 points]
--------------------------------------------
--------------------------------------------
STRATIGRAPHIE = Formation de Héva 6([narc]he6)
AGE = Néoarchéen
GEOMETRIE = [GEOMETRY (MultiPolygon) with 2702 points]
--------------------------------------------
"""
#: 유콘 WMS GetFeatureInfo geo+json 의 한 면(줄였다)
YK = {"UNIT_250K": "MPMC", "FORMATION": "Miles Canyon", "ASSEMBLAGE": "Miles Canyon", "SUPERGROUP": "Null",
      "ERA_MAX": "Cenozoic", "PERIOD_MAX": "Neogene", "EPOCH_MAX": "Miocene", "STAGE_MAX": "Tortonian", "AGE_MAX_MA": "8.4",
      "ERA_MIN": "Cenozoic", "PERIOD_MIN": "Neogene", "EPOCH_MIN": "Pliocene", "STAGE_MIN": "Gelasian", "AGE_MIN_MA": "2.4",
      "ROCK_CLASS": "volcanic", "SHORT_DESCRIPTION": "columnar jointed olivine basalt flows", "TECTONIC_ELEMENT": "Null"}
#: 3978 로 묻는 WMS 변수 — 화면이 보내는 꼴
LCC = {"crs": "EPSG:3978", "bbox": "1450000,200000,1530000,280000", "width": 512, "height": 512}


def answer(text="", body=None, status=200, content=b"\x89PNG", ctype="image/png"):
    r = mock.Mock(status_code=status, content=content, text=text, url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Parse(SimpleTestCase):
    def test_퀘벡_text_plain(self):
        feats = sigeom.parse_plain(PLAIN)
        self.assertEqual(len(feats), 2)
        self.assertEqual(feats[0]["properties"]["AGE"], "Néoarchéen")
        self.assertNotIn("GEOMETRIE", feats[0]["properties"])                       # 기하 줄은 뺀다
        got = sigeom.friendly(feats[0]["properties"])
        self.assertEqual((got["기호"], got["지층"], got["지질시대"]), ("V3B", "Formation de Dubuisson 1([narc]du1)", "Néoarchéen"))

    def test_유콘_시대는_가장_자세한_것(self):
        got = ygs.friendly(YK)
        self.assertEqual((got["기호"], got["지층"], got["연대 (Ma)"]), ("MPMC", "Miles Canyon", "2.4 – 8.4"))
        self.assertEqual(ygs.friendly(YK, "en")["지질시대"], "Tortonian - Gelasian")
        self.assertNotIn("지구조 요소", got)                                          # "Null" 은 뺀다


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-caprov-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for door in (sigeom, ygs):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(door.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_캐나다_지역에_3978_로(self):
        self.assertEqual(Layer.objects.get(name="sigeom:regionale").group.region, "canada")
        self.assertEqual(Layer.objects.get(name="ygs:47").group.region, "canada")
        self.assertEqual((self.layers["sigeom:regionale"]["projection"], self.layers["sigeom:regionale"]["minZoom"]), ("EPSG:3978", 8))
        self.assertEqual(self.layers["ygs:47"]["minZoom"], 7)
        self.assertFalse(self.layers["sigeom:failles"]["queryable"])

    def test_퀘벡은_1_1_1_로_옮기고_Origin_을_보내지_않는다(self):
        with mock.patch.object(sigeom.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "sigeom:regionale", "version": "1.3.0", "request": "GetMap", **LCC})
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["version"], sent["srs"], sent["layers"]), ("1.1.1", "EPSG:3978", "SGM:Geologie_regionale"))
        self.assertNotIn("Origin", get.call_args.kwargs["headers"])

    def test_퀘벡_속성은_text_plain_과_링크(self):
        with mock.patch.object(sigeom.requests, "get", return_value=answer(PLAIN, ctype="text/plain")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "sigeom:regionale", "query_layers": "sigeom:regionale",
                                                                    "i": 256, "j": 256, "request": "GetFeatureInfo", **LCC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["info_format"], sent["x"], sent["y"]), ("text/plain", "256", "256"))
        props = data["features"][0]["props"]
        self.assertEqual(props["원도"]["links"][0]["label"], "CG-32D01D-2013-01")          # `<a>` 는 뷰가 링크로 가른다

    def test_유콘_속성은_geo_json(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": YK}]}
        with mock.patch.object(ygs.requests, "get", return_value=answer(body=body, ctype="application/geo+json")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "ygs:47", "query_layers": "ygs:47", "i": 256, "j": 256,
                                                                    "request": "GetFeatureInfo", **LCC}).json()
        self.assertEqual((get.call_args.kwargs["params"]["layers"], get.call_args.kwargs["params"]["info_format"]),
                         ("47", "application/geo+json"))
        self.assertEqual("토르토나절~젤라절", data["features"][0]["props"]["지질시대"])


class Bundle(SimpleTestCase):
    def test_북미_묶음은_3978(self):
        js = MAPJS.read_text(encoding="utf-8")
        block = js[js.index("    north_america: {"):]
        block = block[:block.index("},") + 2]
        self.assertIn('proj: "EPSG:3978"', block)
        self.assertIn('includes: ["canada", "usa", "mexico"]', block)
        usa = js[js.index("    usa: {"):]
        self.assertIn('proj: "EPSG:3978"', usa[:usa.index("},")])                     # 알래스카가 부풀지 않게
