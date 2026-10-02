"""제4기 고생태 산지 — Neotoma 를 번호 묶음으로 받아 굽고, 자료형 칸·연대마다 찍고, 누르면 읽는다 (wetherilli 139).

Neotoma 를 실제로 부르지 않는다. 꼴은 2026-10-02 에 `data/datasets/<번호들>` 로 받은 그대로다.
"""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import neotoma, paleoeco


def entry(siteid, name, geography, datasets):
    return {"site": {"siteid": siteid, "sitename": name, "sitedescription": "Bog.", "altitude": 329,
                     "geography": json.dumps(geography), "datasets": datasets}}


def dataset(no, kind, ranges, pi="McAndrews, John H.", doi="10.21233/n3bc7k"):
    return {"datasetid": no, "datasettype": kind, "database": "North American Pollen Database", "doi": [doi],
            "agerange": ranges, "datasetpi": [{"contactname": pi}]}


PAGE = [
    entry(7, "Three Pines Bog", {"type": "Point", "coordinates": [-80.11667, 47]}, [
        dataset(7, "pollen", [{"units": "Radiocarbon years BP", "ageold": 6485, "ageyoung": -26}]),
        dataset(8, "geochronologic", []),
    ]),
    # 면으로 적힌 산지 — 꼭짓점의 가운데에
    entry(9, "Big Cave", {"type": "Polygon", "coordinates": [[[10, 40], [12, 40], [12, 42], [10, 42], [10, 40]]]}, [
        dataset(20, "vertebrate fauna", [{"units": "Calendar years BP", "ageold": 30000, "ageyoung": 12000}]),
    ]),
    entry(11, "Kettle Lake", {"type": "Point", "coordinates": [179.99, -40]}, [
        dataset(30, "diatom surface sample", []),
        dataset(31, "charcoal", [{"units": "Calendar years AD/BC", "ageold": 1500, "ageyoung": 1900}]),
    ]),
]


def baked(folder) -> Path:
    src = Path(folder) / "n.jsonl"
    rows = neotoma.shrink(PAGE)
    src.write_text("".join(json.dumps(r) + "\n" for r in rows + rows[:1]), encoding="utf-8")   # 겹친 줄 하나
    out = Path(folder) / paleoeco.FILE
    paleoeco.build(src, out, log=lambda *_: None)
    return out


class Shrink(SimpleTestCase):
    def test_자료마다_한_줄(self):
        rows = {r["dataset"]: r for r in neotoma.shrink(PAGE)}
        self.assertEqual(sorted(rows), [7, 8, 20, 30, 31])
        self.assertEqual((rows[7]["old"], rows[7]["young"], rows[7]["pi"]), (6485, -26, "McAndrews, John H."))
        self.assertEqual((rows[20]["lon"], rows[20]["lat"]), (10.8, 40.8))       # 닫는 꼭짓점까지 다섯의 가운데
        self.assertIsNone(rows[8]["old"])
        self.assertEqual((rows[31]["old"], rows[31]["young"]), (450.0, 50.0))     # AD 1500–1900 → 450–50 BP

    def test_자료형_칸(self):
        self.assertEqual([paleoeco.band_of(k) for k in ("pollen", "pollen surface sample", "vertebrate fauna",
                                                         "plant macrofossil", "diatom surface sample", "ostracode",
                                                         "charcoal", "geochronologic")],
                         ["neo_pollen", "neo_pollen", "neo_vert", "neo_plant", "neo_micro", "neo_micro",
                          "neo_other", "neo_other"])


class Build(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-neotoma-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)

    def test_겹친_자료는_하나(self):
        self.assertEqual(paleoeco.db().execute("SELECT COUNT(*) FROM ds").fetchone()[0], 5)

    def test_오늘은_모두_옛_연대는_품은_것만(self):
        everywhere = (-180, -90, 180, 90)
        allbands = list(paleoeco.BANDS)
        self.assertEqual(sorted({p[2] for p in paleoeco.points(allbands, 0, *everywhere)}), [7, 9, 11])
        self.assertEqual({p[2] for p in paleoeco.points(allbands, 0.02, *everywhere)}, {9})      # 20 ka
        self.assertEqual({p[2] for p in paleoeco.points(allbands, 0.005, *everywhere)}, {7})     # 5 ka
        self.assertEqual(paleoeco.points(["neo_vert"], 0.005, *everywhere), [])


class Door(SimpleTestCase):
    def test_번호를_묶어_묻고_빈_묶음이_잇따르면_멈춘다(self):
        dest = Path(tempfile.mkdtemp()) / "n.jsonl"

        def answer(data):
            r = mock.MagicMock(status_code=200)
            r.json.return_value = {"data": data}
            return r
        replies = [answer(PAGE[:1]), answer(PAGE[1:]), answer([]), answer([])]
        with mock.patch.object(neotoma, "EMPTY_STOP", 2), \
             mock.patch.object(neotoma.requests, "get", side_effect=replies) as get, \
             mock.patch.object(neotoma.usage, "record"):
            self.assertEqual(neotoma.download(dest, log_line=lambda *_: None, pause=0, batch=3), 5)
        self.assertEqual(get.call_count, 4)
        self.assertTrue(get.call_args_list[1].args[0].endswith("/datasets/4,5,6"))
        self.assertEqual(len(dest.read_text(encoding="utf-8").splitlines()), 5)

    def test_실패하면_옛_파일을_둔다(self):
        dest = Path(tempfile.mkdtemp()) / "n.jsonl"
        dest.write_text("옛것", encoding="utf-8")
        with mock.patch.object(neotoma.requests, "get", return_value=mock.MagicMock(status_code=502, content=b"")), \
             mock.patch.object(neotoma.usage, "record"):
            with self.assertRaises(neotoma.NeotomaError):
                neotoma.download(dest, log_line=lambda *_: None, pause=0)
        self.assertEqual(dest.read_text(encoding="utf-8"), "옛것")

    def test_굽기만(self):
        folder = tempfile.mkdtemp()
        src = Path(folder) / "n.jsonl"
        src.write_text(json.dumps(neotoma.shrink(PAGE)[0]) + "\n", encoding="utf-8")
        with override_settings(EARTH_DIR=folder), mock.patch.object(neotoma, "download") as download:
            out = io.StringIO()
            call_command("fetch_neotoma", jsonl=str(src), stdout=out)
        download.assert_not_called()
        self.assertIn("산지 1 곳", out.getvalue())


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-neotoma-")
        patch = override_settings(EARTH_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-neotoma-t-"))
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)

    def test_타일(self):
        url = reverse("viewer:earth-neotoma-tile", kwargs={"band": "neo_pollen", "ka": 0, "z": 0, "x": 0, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        self.assertGreater(Image.open(io.BytesIO(first.content)).convert("RGBA").getextrema()[3][1], 150)

    def test_1_Ma_부터는_없다(self):
        r = self.client.get(reverse("viewer:earth-neotoma-tile",
                                    kwargs={"band": "neo_pollen", "ka": 1000, "z": 0, "x": 0, "y": 0}))
        self.assertEqual(r.status_code, 404)

    def test_누르면_산지와_그_연대의_자료(self):
        url = reverse("viewer:earth-neotoma-at")
        data = self.client.get(url, {"lon": -80.12, "lat": 47, "r": 0.2, "bands": "neo_pollen,neo_other"}).json()
        hit = data["hits"][0]
        rows = dict(hit["rows"])
        self.assertEqual((hit["name"], rows["pollen"]), ("Three Pines Bog", "6 485 – -26 BP · North American Pollen Database"))
        self.assertIn("geochronologic", rows)                                   # 오늘은 연대 없는 자료도
        self.assertEqual(rows["연구자"], "McAndrews, John H.")
        self.assertTrue(hit["link"].endswith("siteids=7"))
        rows = dict(self.client.get(url, {"lon": -80.12, "lat": 47, "r": 0.2, "age": 0.005,
                                          "bands": "neo_pollen,neo_other"}).json()["hits"][0]["rows"])
        self.assertNotIn("geochronologic", rows)                                # 옛 연대에는 그 연대를 품은 것만

    def test_날짜_바뀜선_너머도(self):
        data = self.client.get(reverse("viewer:earth-neotoma-at"),
                               {"lon": -179.99, "lat": -40, "r": 0.2, "bands": "neo_micro"}).json()
        self.assertEqual(data["hits"][0]["name"], "Kettle Lake")

    def test_파일이_없으면_목록에_서지_않는다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            page = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertIn('"neotoma": []', page)
