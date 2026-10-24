"""PANGAEA 극지 현장 자료 (wetherilli 421) — 받아 줄이기, 주제 가르기, 점 레이어, 씨앗. 상류는 부르지 않는다."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from viewer import i18n, pangaea, views
from viewer.models import Layer

XML = ('<md:MetaData><md:license id="license21">\n<md:label>CC-BY-4.0</md:label>\n'
       '<md:name>Creative Commons Attribution 4.0 International</md:name></md:license></md:MetaData>')


def hit(id_, title, lat, lon, topics=None, project=None, authors=("Kuhn, Gerhard",), xml=XML, hidden=False):
    src = {"URI": f"https://doi.org/10.1594/PANGAEA.{id_}", "meanPosition": {"lat": lat, "lon": lon},
           "agg-author": list(authors) if len(authors) > 1 else authors[0], "agg-pubYear": 2022,
           "sp-lastModified": "2025-10-21T11:26:55.000Z", "sp-hidden": hidden, "xml": xml,
           "xml-thumb": f"<md:SearchResult><md:citation><md:title>{title}</md:title></md:citation></md:SearchResult>"}
    if topics:
        src["agg-topic"] = topics
    if project:
        src["agg-project"] = project
    return {"_id": str(id_), "_source": src}


#: 현장 다섯의 검색 응답 — 세종은 두 쪽에 나눠 준다
SEJONG = [hit(1, "Pore water data of short sediment cores from Potter Cove &amp; Maxwell Bay", -62.229388, -58.66, ["Lithosphere", "Chemistry"],
              authors=("Aromokeye, DA", "Willis-Poratti, G", "Wunder, LC", "Henkel, S")),
          hit(2, "Seal tracks", -62.2, -58.7, ["Ecology"]),
          hit(3, "숨긴 자료", -62.2, -58.7, ["Ecology"], hidden=True)]
DASAN = [hit(10, "Ozone measurements from station Ny-Ålesund (2000-12)", 78.9227, 11.9273, project="BSRN", xml=""),
         hit(11, "Video In Situ Snowfall Sensor (VISSS) data for Ny-Ålesund", 78.92, 11.93),
         hit(12, "Physical oceanography in the Kongsfjorden from CTD KF1991_N1", 78.95, 11.9, project="NIPR"),
         hit(13, "Photographs of the glacier", 78.9, 12.0)]


def page(hits, total):
    return {"hits": {"total": total, "hits": hits}}


class Topic(SimpleTestCase):
    def test_꼬리표가_먼저_그다음_사업_그다음_제목(self):
        self.assertEqual(pangaea.topic_of(["Chemistry", "Lithosphere"]), "litho")       # 주제가 여럿이면 표의 차례
        self.assertEqual(pangaea.topic_of(["Ecology"]), "bio")
        self.assertEqual(pangaea.topic_of([], "AC3 · AWI_Meteo"), "atmo")
        self.assertEqual(pangaea.topic_of([], "", "Physical oceanography from CTD 3"), "ocean")
        self.assertEqual(pangaea.topic_of([], "", "Sediment core PS1545"), "litho")
        self.assertEqual(pangaea.topic_of([], "", "Photographs of Potter Cove"), "other")

    def test_한_건_줄이기(self):
        rec = pangaea.record(SEJONG[0], "sejong")
        self.assertEqual(rec["t"], "Pore water data of short sediment cores from Potter Cove & Maxwell Bay")
        self.assertEqual(rec["lic"], "CC-BY-4.0")
        self.assertEqual((rec["lat"], rec["lon"]), (-62.22939, -58.66))
        self.assertNotIn("xml", json.dumps(rec))                     # 큰 XML 은 버린다
        self.assertIsNone(pangaea.record(SEJONG[2], "sejong"))        # 숨긴 자료
        self.assertIsNone(pangaea.record({"_id": "9", "_source": {"URI": "x"}}, "sejong"))   # 자리 없음


class Fetched(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.override = override_settings(PANGAEA_DIR=cls.tmp.name)
        cls.override.enable()
        replies = [page(SEJONG[:2], 3), page(SEJONG[2:], 3),      # 세종 — 두 쪽
                   page([], 0),                                    # 장보고 — 없다
                   page(DASAN, len(DASAN)),                        # 다산
                   page([], 0), {"hits": {"total": {"value": 0}, "hits": []}}]   # 그린란드 둘 — 새 판의 total 꼴도
        with mock.patch.object(pangaea, "PAGE", 2), mock.patch.object(pangaea, "_post", side_effect=replies) as got, \
                mock.patch.object(pangaea.time, "sleep") as slept:
            cls.counts = pangaea.download()
        cls.bodies = [c.args[0] for c in got.call_args_list]
        cls.slept = slept.call_count

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_현장마다_쪽을_넘기며_받고_사이에_쉰다(self):
        self.assertEqual(self.counts, {"sejong": 2, "jangbogo": 0, "dasan": 4, "disko": 0, "zackenberg": 0})
        self.assertEqual([b["from"] for b in self.bodies], [0, 2, 0, 0, 0, 0])
        self.assertEqual(self.slept, len(self.bodies) - 1)          # 부를 때마다 사이에 1 초
        box = self.bodies[0]["query"]["bool"]["filter"][0]["geo_bounding_box"]["meanPosition"]
        self.assertEqual(box, {"top_left": {"lat": -61.9, "lon": -59.1}, "bottom_right": {"lat": -62.3, "lon": -57.5}})

    def test_주제마다_탭마다_레이어(self):
        r = self.client.get("/GSM/points/", {"layer": "pangaea:litho_antarctica"})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["style"], "class")
        self.assertEqual([f["id"] for f in data["features"]], ["1"])
        props = data["features"][0]["properties"]
        self.assertEqual(props["authors"], "Aromokeye, DA; Willis-Poratti, G; Wunder, LC et al.")
        self.assertEqual(props["doi"], "https://doi.org/10.1594/PANGAEA.1")
        self.assertEqual(props["area"], "킹조지섬 (세종 기지)")
        self.assertEqual(data["legend"][0]["count"], 1)
        self.assertEqual(data["links"], ["doi"])
        for key in data["labels"].values():
            self.assertIn(key, {**i18n.EN, **i18n.PROP_EN})          # 팝업 이름은 화면이 옮긴다

    def test_영어판은_현장_이름을_옮긴다(self):
        self.client.cookies[i18n.COOKIE] = "en"
        r = self.client.get("/GSM/points/", {"layer": "pangaea:litho_antarctica"})
        self.assertEqual(json.loads(r.content)["features"][0]["properties"]["area"], "King George Island (King Sejong Station)")

    def test_다산은_대기가_많다(self):
        ids = lambda name: [f["id"] for f in json.loads(pangaea.file_body(name))["features"]]
        self.assertEqual(sorted(ids("pangaea:atmo_svalbard")), ["10", "11"])
        self.assertEqual(ids("pangaea:ocean_svalbard"), ["12"])
        self.assertEqual(ids("pangaea:other_svalbard"), ["13"])
        self.assertEqual(ids("pangaea:atmo_antarctica"), [])
        self.assertEqual(json.loads(pangaea.file_body("pangaea:atmo_antarctica"))["legend"], [])


class NotFetched(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(PANGAEA_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_503_으로_까닭을_말한다(self):
        r = self.client.get("/GSM/points/", {"layer": "pangaea:bio_svalbard"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_pangaea", r.json()["error"])

    def test_상류가_못_주면_앞의_파일을_두고_멈춘다(self):
        with mock.patch.object(pangaea, "_post", side_effect=pangaea.PangaeaError("x")), \
                mock.patch.object(pangaea.time, "sleep"):
            with self.assertRaises(pangaea.PangaeaError):
                pangaea.download()
        self.assertFalse(pangaea.available())


class Seed(SimpleTestCase):
    def test_씨앗의_레이어는_문이_알고_영어가_있다(self):
        for path in settings.PANGAEA_CATALOG_SEEDS:
            seed = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(seed["_상류"], "pangaea")
            for name in seed["레이어군순서"]:
                self.assertIn(name, i18n.GROUP_EN)
            for layer in seed["레이어"]:
                self.assertTrue(pangaea.knows(layer["name"]), layer["name"])
                self.assertEqual(pangaea.LAYERS[layer["name"]]["tab"], seed["_지역"])
                self.assertIn(layer["name"], i18n.LAYER_EN)
                self.assertIn(layer["name"], i18n.ABSTRACT_EN)

    def test_화면에는_점_레이어로(self):
        spec = views._point_fields(Layer(name="pangaea:litho_svalbard", upstream="pangaea"))
        self.assertEqual(spec["kind"], "points")
        self.assertEqual(spec["style"], "class")
        self.assertEqual(spec["source"], pangaea.HOME)

    def test_현장_이름과_범례에_영어가_있다(self):
        for _, label, _ in pangaea.AREAS.values():
            self.assertIn(str(label), i18n.EN)
        for _, label, _, _ in pangaea.TOPICS:
            self.assertIn(label, i18n.EN)
