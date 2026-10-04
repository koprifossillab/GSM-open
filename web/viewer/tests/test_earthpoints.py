"""지역 탭의 지구 자료 점 (wetherilli 185) — 화석 산지·홀로세 화산·지진·고생태 산지를 지역의 네모만큼 점 레이어로.

자료는 각 시험(`test_fossils`·`test_volcanoes`·`test_quakes`·`test_neotoma`)이 쓰는 굽기 함수로 임시 폴더에 만든다.
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import earthpoints, fossils, gvp, neotoma, paleoeco, quakes, views, volcanoes
from viewer.tests import test_fossils, test_neotoma, test_quakes, test_volcanoes

FOSSILS = [
    '1,126.98,37.57,서울 산지,"Pyeongan Sup.",Changhsingian,Induan,254.1,249.9,KR,12,105.0,30.6,"marginal marine",Kim 2001\n',
    "2,15.6,78.2,롱이어비엔 산지,Firkanten,Paleocene,,66.0,56.0,NO,40,,,coastal,Smith 1990\n",
    "3,-60.0,-75.0,남극 산지,,Maastrichtian,,72.1,66.0,AQ,3,,,marine,\n",
    "4,-150,0,해저 산지,,Maastrichtian,,72.1,66.0,,3,,,deep subtidal,\n",
]
QUAKES = [
    '2016-09-12T11:32:54.000Z,35.77,129.19,12,5.4,mww,,,,,us,us10006p1f,2016-09-13T00:00:00.000Z,'
    '"8 km SSW of Gyeongju, South Korea",earthquake,,,,,reviewed,us,us\n',
    '2020-01-01T00:00:00.000Z,-20.0,179.99,580,5.2,mb,,,,,us,us_deep,2020-01-02T00:00:00.000Z,"Fiji Islands region",'
    'earthquake,,,,,reviewed,us,us\n',
]
VOLCANOES = {"type": "FeatureCollection", "features": [
    test_volcanoes.feature(305020, "Baekdusan", 128.077, 41.998, 1903),
    test_volcanoes.feature(372070, "Hekla", -19.7, 63.98, 2000),
    test_volcanoes.feature(390020, "Erebus", 167.17, -77.53, None),
]}
SITES = [test_neotoma.entry(5, "Korean Bog", {"type": "Point", "coordinates": [127.5, 36.5]}, [
    test_neotoma.dataset(50, "diatom", []), test_neotoma.dataset(51, "diatom", []),
    test_neotoma.dataset(52, "pollen", [{"units": "Calendar years BP", "ageold": 9000, "ageyoung": 0}]),
])]


def gathered(folder) -> Path:
    folder = Path(folder)
    (folder / "c.csv").write_text(test_fossils.HEAD + "".join(FOSSILS), encoding="utf-8")
    fossils.build(folder / "c.csv", folder / fossils.FILE, log=lambda *_: None)
    (folder / "q.csv").write_text(test_quakes.HEAD + "".join(QUAKES), encoding="utf-8")
    quakes.build(folder / "q.csv", folder / quakes.FILE, log=lambda *_: None)
    (folder / volcanoes.FILE).write_text(
        json.dumps({"fetched": "2026-10-04", "volcanoes": gvp.shrink(VOLCANOES)}), encoding="utf-8")
    (folder / "n.jsonl").write_text("".join(json.dumps(r) + "\n" for r in neotoma.shrink(SITES)), encoding="utf-8")
    paleoeco.build(folder / "n.jsonl", folder / paleoeco.FILE, log=lambda *_: None)
    return folder


class Body(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-earthpoints-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        gathered(self.dir)
        earthpoints._body.cache_clear()

    def read(self, name, lang="ko"):
        return json.loads(earthpoints.body(name, lang))

    def test_지역의_네모만_자른다(self):
        self.assertEqual([f["properties"]["name"] for f in self.read("earth:pbdb_korea")["features"]], ["서울 산지"])
        self.assertEqual([f["properties"]["name"] for f in self.read("earth:pbdb_arctic")["features"]], ["롱이어비엔 산지"])
        self.assertEqual([f["properties"]["name"] for f in self.read("earth:pbdb_antarctica")["features"]], ["남극 산지"])
        # 한국 탭은 반도 북쪽 끝까지 — 백두산이 든다
        self.assertEqual([f["properties"]["name"] for f in self.read("earth:gvp_korea")["features"]], ["Baekdusan"])
        self.assertEqual([f["properties"]["name"] for f in self.read("earth:gvp_antarctica")["features"]], ["Erebus"])

    def test_화석_산지는_기의_색과_링크(self):
        data = self.read("earth:pbdb_korea")
        props = data["features"][0]["properties"]
        self.assertEqual(props["code"], "p6")                                  # 252 Ma — 페름기
        self.assertEqual(data["legend"], [{"code": "p6", "label": "페름기", "color": "#F04028", "shape": "dot",
                                           "count": 1}])
        self.assertEqual(props["link"], "https://paleobiodb.org/classic/displayCollectionDetails?collection_no=1")
        self.assertEqual(data["style"], "class")
        self.assertEqual(data["links"], ["link"])
        self.assertEqual(data["labels"]["formation"], "지층")

    def test_화산은_세모_지진은_깊이의_색(self):
        volcano = self.read("earth:gvp_arctic")
        self.assertEqual(volcano["legend"][0]["shape"], "triangle")
        self.assertEqual(volcano["features"][0]["properties"]["code"], "e0")   # 2000 년 — 1900 년부터
        quake = self.read("earth:quakes_korea")["features"][0]["properties"]
        self.assertEqual((quake["code"], quake["mag"], quake["depth"]), ("d0", "5.4 mww", "12"))
        self.assertTrue(quake["link"].endswith("us10006p1f"))

    def test_고생태_산지는_많은_자료형의_색(self):
        props = self.read("earth:neotoma_korea")["features"][0]["properties"]
        self.assertEqual(props["code"], "neo_micro")                           # 규조 둘 > 꽃가루 하나
        self.assertIn("pollen", props["types"])

    def test_영어판은_시대를_옮기지_않는다(self):
        self.assertEqual(self.read("earth:pbdb_korea", "en")["features"][0]["properties"]["age"], "Changhsingian – Induan")


@override_settings(TILE_CACHE_SECONDS=0)
class PointsView(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-earthpoints-v-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        earthpoints._body.cache_clear()

    def test_점_레이어로_낸다(self):
        gathered(self.dir)
        r = self.client.get(reverse("viewer:points"), {"layer": "earth:quakes_korea"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/geo+json")
        self.assertEqual(len(r.json()["features"]), 1)

    @override_settings(TILE_CACHE_SECONDS=86400, TILE_IMMUTABLE_SECONDS=31536000)
    def test_판이_맞으면_오래_둔다(self):
        gathered(self.dir)
        version = earthpoints.version("earth:quakes_korea")
        url = reverse("viewer:points")
        same = self.client.get(url, {"layer": "earth:quakes_korea", "v": version})
        self.assertIn("immutable", same["Cache-Control"])
        old = self.client.get(url, {"layer": "earth:quakes_korea", "v": "0-old"})
        self.assertNotIn("immutable", old["Cache-Control"])

    def test_자료가_없으면_명령을_적는다(self):
        r = self.client.get(reverse("viewer:points"), {"layer": "earth:pbdb_antarctica"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_pbdb", r.json()["error"])

    def test_모르는_이름은_404(self):
        self.assertEqual(self.client.get(reverse("viewer:points"), {"layer": "earth:pbdb_mars"}).status_code, 404)


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def layer(self, name):
        for group in views._catalog("ko"):
            for layer in group["layers"]:
                if layer["name"] == name:
                    return group, layer
        return None, None

    def test_한국_남극_북극해에_선다(self):
        for name, region in (("earth:pbdb_korea", "korea"), ("earth:gvp_antarctica", "antarctica"),
                             ("earth:neotoma_arctic", "arctic_ocean")):
            group, layer = self.layer(name)
            self.assertEqual(group["region"], region, name)
            self.assertEqual((layer["kind"], layer["style"], layer["upstream"]), ("points", "class", "earth"))
        _, volcano = self.layer("earth:gvp_korea")
        self.assertIn("비상업", volcano["sourceLabel"])
        self.assertTrue(volcano["version"].startswith(earthpoints.RENDERER + "-"))

    def test_정적_판에는_싣지_않는다(self):
        spec = {"regions": ["korea", "antarctica", "arctic_ocean"], "upstreams": ["kigam", "kopri", "emodnet"]}
        with override_settings(STATIC_SITE=spec):
            names = [l["name"] for g in views._static_catalog(views._catalog("ko")) for l in g["layers"]]
        self.assertFalse([n for n in names if n.startswith("earth:")])
