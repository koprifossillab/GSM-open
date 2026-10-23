"""SCAR 남극 통합 지명사전 (wetherilli 412) — 받아 묶기, 남극 탭의 찾기, 이름표. 상류는 부르지 않는다."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from viewer import i18n, scar, views


def row(cid, gaz, name, kind="Island", lat=-65.08, lon=-64.0):
    return {"scar_common_id": cid, "gazetteer": gaz, "place_name_mapping": name, "feature_type_name": kind,
            "latitude": lat, "longitude": lon}


#: WFS 가 주는 행의 꼴 — 한 줄이 한 나라의 이름 하나
ROWS = [
    row(1, "ARG", "Booth, isla"), row(1, "DEU", "Boothinsel"), row(1, "USA", "Booth Island", lat=-65.0833),
    row(1, "GBR", "Booth Island"), row(1, "BEL", "Wandel, Ile"),
    row(2, "USA", "King Sejong Station", "Station", -62.2233, -58.7892),
    row(3, "KOR", "Sejong Cape", "Cape", -62.2239, -58.7981), row(3, "USA", "Sejong Point", "Cape", -62.224, -58.798),
    row(4, "USA", "Ross Ice Shelf", "Ice shelf", -81.5, 175.0), row(4, "NZL", "Ross Ice Shelf", "Ice shelf", -81.5, 175.0),
    row(4, "RUS", "Rossa, shel'fovyy lednik", "Ice shelf", -81.5, 175.0),
    row(5, "USA", "Maxwell Bay", "Bay", -62.25, -58.85),
    row(6, "NOR", "Jutulsessen", "Mountain", -72.0, 2.5),
    row(None, "USA", "번호 없음"), row(7, "USA", ""),
]


class Group(SimpleTestCase):
    def test_지형마다_묶고_보일_이름은_한국_다음_영어(self):
        places = {p[0]: p for p in scar.group(ROWS)}
        self.assertEqual(sorted(places), [1, 2, 3, 4, 5, 6])          # 번호·이름이 없는 줄은 뺀다
        self.assertEqual(places[1][4][0], ["USA", "Booth Island"])
        self.assertEqual(places[1][2], -65.0833)                       # 자리는 보일 이름의 줄의 것
        self.assertEqual(len(places[1][4]), 5)                         # 나라마다의 이름을 다 남긴다
        self.assertEqual(places[3][4][0], ["KOR", "Sejong Cape"])

    def test_이름표의_크기와_생김(self):
        self.assertEqual(scar.rank("Ice shelf", 3), 2)
        self.assertEqual(scar.rank("Island", 5), 4)
        self.assertEqual(scar.rank("Station", 1), 4)
        self.assertEqual(scar.rank("Rock", 1), 8)
        self.assertEqual(scar.label_kind("Station"), "city")
        self.assertEqual(scar.label_kind("Bay"), "lake")


class Fetched(SimpleTestCase):
    """받아 둔 파일이 있을 때 — 받기도 한 번 흉내 낸다(두 쪽)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.override = override_settings(SCAR_DIR=cls.tmp.name)
        cls.override.enable()
        pages = [{"numberMatched": len(ROWS), "features": [{"properties": r} for r in ROWS[:8]]},
                 {"numberMatched": len(ROWS), "features": [{"properties": r} for r in ROWS[8:]]}]
        with mock.patch.object(scar, "PAGE", 8), mock.patch.object(scar, "_page", side_effect=pages) as got, \
                mock.patch.object(scar.time, "sleep") as slept, mock.patch.object(scar.usage, "paused", return_value=0):
            cls.got = scar.download(scar.path())
        cls.calls = [c.args[0] for c in got.call_args_list]
        cls.slept = slept.call_count

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        scar._load.cache_clear()
        scar.place_index_cached.cache_clear()
        scar.label_body.cache_clear()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_쪽을_넘기며_받고_사이에_쉰다(self):
        self.assertEqual(self.calls, [0, 8])
        self.assertEqual(self.slept, 1)
        self.assertEqual(self.got, {"names": len(ROWS), "places": 6})
        head = json.loads(scar.path().read_text(encoding="utf-8"))
        self.assertEqual(head["license"], "CC BY")

    def test_상류가_쪽을_작게_묶어도_끝까지_받는다(self):
        # 8 개를 달라 했는데 5 개씩만 준다. 전체 수가 없으면 빈 쪽이 올 때까지
        pages = [{"features": [{"properties": r} for r in ROWS[i:i + 5]]} for i in range(0, len(ROWS), 5)] + [{"features": []}]
        out = Path(self.tmp.name) / "small.json"
        with mock.patch.object(scar, "PAGE", 8), mock.patch.object(scar, "_page", side_effect=pages) as got, \
                mock.patch.object(scar.time, "sleep"), mock.patch.object(scar.usage, "paused", return_value=0):
            result = scar.download(out)
        self.assertEqual(result["names"], len(ROWS))
        self.assertEqual([c.args[0] for c in got.call_args_list], [0, 5, 10, 15])

    def test_나라마다의_이름으로_찾는다(self):
        with mock.patch.object(views, "point_features", side_effect=views.npolar.NpolarError("x")):
            data = self.client.get("/GSM/placenames/", {"q": "boothinsel", "region": "antarctica"}).json()
        self.assertEqual(data["results"][0]["title"], "Booth Island (Boothinsel)")
        self.assertEqual(data["results"][0]["sub"], "Island · USA·GBR·ARG·DEU·BEL")   # 앞세울 나라 다음은 받은 차례

    def test_기지를_앞세운다(self):
        with mock.patch.object(views, "point_features", side_effect=views.npolar.NpolarError("x")):
            data = self.client.get("/GSM/placenames/", {"q": "sejong", "region": "antarctica"}).json()
        titles = [h["title"] for h in data["results"]]
        self.assertEqual(titles[0], "Sejong Cape")
        self.assertIn("King Sejong Station", titles)

    def test_드로닝모드랜드와_겹치면_하나만(self):
        npi = json.dumps([{"geometry": {"coordinates": [2.51, -72.01]},
                           "properties": {"name": "Jutulsessen", "area": "Dronning Maud Land"}}]).encode()
        views._place_index.pop("npolar:dml_place_names", None)
        try:
            with mock.patch.object(views, "point_features", return_value=npi):
                data = self.client.get("/GSM/placenames/", {"q": "jutulsessen", "region": "antarctica"}).json()
        finally:
            views._place_index.pop("npolar:dml_place_names", None)
        self.assertEqual([h["title"] for h in data["results"]], ["Jutulsessen"])

    def test_이름표_레이어(self):
        r = self.client.get("/GSM/points/", {"layer": scar.PLACES})
        self.assertEqual(r.status_code, 200)
        features = {f["id"]: f["properties"] for f in json.loads(r.content)["features"]}
        self.assertEqual(features[4], {"label": "Ross Ice Shelf", "kind": "Ice shelf", "rank": 2})
        self.assertEqual(features[2]["kind"], "city")


class NotFetched(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(SCAR_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_이름표는_503_으로_까닭을_말한다(self):
        r = self.client.get("/GSM/points/", {"layer": scar.PLACES})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_scar_gazetteer", r.json()["error"])

    def test_찾기는_드로닝모드랜드만으로도_돈다(self):
        npi = json.dumps([{"geometry": {"coordinates": [2.5, -72.0]},
                           "properties": {"name": "Jutulsessen", "area": "Dronning Maud Land"}}]).encode()
        views._place_index.pop("npolar:dml_place_names", None)
        try:
            with mock.patch.object(views, "point_features", return_value=npi):
                r = self.client.get("/GSM/placenames/", {"q": "jutul", "region": "antarctica"})
        finally:
            views._place_index.pop("npolar:dml_place_names", None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"][0]["title"], "Jutulsessen")


class Seed(SimpleTestCase):
    def test_씨앗에_영어가_있다(self):
        seed = json.loads(Path(settings.SCAR_CATALOG_SEED).read_text(encoding="utf-8"))
        self.assertEqual(seed["_상류"], "scar")
        for name in seed["레이어군순서"]:
            self.assertIn(name, i18n.GROUP_EN)
        for layer in seed["레이어"]:
            self.assertEqual(layer["name"], scar.PLACES)
            self.assertIn(layer["name"], i18n.LAYER_EN)
            self.assertIn(layer["name"], i18n.ABSTRACT_EN)
