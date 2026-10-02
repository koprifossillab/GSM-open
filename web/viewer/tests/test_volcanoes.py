"""홀로세 화산 — GVP 를 받아 줄여 적고, 타일에 찍고, 누르면 읽는다 (wetherilli 134).

GVP 를 실제로 부르지 않는다. GeoJSON 의 꼴은 2026-10-02 에 `Smithsonian_VOTW_Holocene_Volcanoes` 를 WFS 로 받은 그대로다.
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

from viewer import gvp, volcanoes


def feature(no, name, lon, lat, last):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"Volcano_Number": no, "Volcano_Name": name, "Primary_Volcano_Type": "Stratovolcano",
                           "Volcanic_Landform": "Composite", "Last_Eruption_Year": last, "Country": "Japan",
                           "Region": "Japan, Taiwan, Marianas", "Subregion": "Honshu", "Elevation": 3776,
                           "Tectonic_Setting": "Subduction zone", "Evidence_Category": "Eruption Observed",
                           "Major_Rock_Type": "Basalt / Picro-Basalt", "Geological_Summary": "…",
                           "Primary_Photo_Link": "https://volcano.si.edu/gallery/photos/x.jpg"}}


COLLECTION = {"type": "FeatureCollection", "features": [
    feature(283030, "Fujisan", 138.7306, 35.3606, 1707),
    feature(305020, "Baekdusan", 128.077, 41.998, 1903),
    feature(1, "날짜 바뀜선", 179.99, 0.0, -2000),
    feature(2, "모름", 10.0, 10.0, None),
    {"type": "Feature", "geometry": None, "properties": {"Volcano_Number": 3}},
]}


def written(folder) -> Path:
    dest = Path(folder) / volcanoes.FILE
    dest.write_text(json.dumps({"fetched": "2026-10-02", "volcanoes": gvp.shrink(COLLECTION)}), encoding="utf-8")
    return dest


class Shrink(SimpleTestCase):
    def test_좌표_없는_것과_사진은_뺀다(self):
        rows = gvp.shrink(COLLECTION)
        self.assertEqual([r["no"] for r in rows], [283030, 305020, 1, 2])
        self.assertEqual((rows[0]["lon"], rows[0]["lat"], rows[0]["last"]), (138.7306, 35.3606, 1707))
        self.assertNotIn("Primary_Photo_Link", json.dumps(rows))

    def test_마지막_분화의_칸(self):
        self.assertEqual([volcanoes.era(y) for y in (2026, 1900, 1707, 1, -9540, None)], [0, 0, 1, 2, 3, 4])
        self.assertEqual(volcanoes.legend("en")[-1]["name"], "No recorded eruption")


class Door(SimpleTestCase):
    def test_받아_줄여_적는다(self):
        folder = tempfile.mkdtemp()
        answer = mock.MagicMock(status_code=200, url="https://webservices.volcano.si.edu/…")
        answer.json.return_value = COLLECTION
        with override_settings(EARTH_DIR=folder), \
             mock.patch.object(gvp.requests, "get", return_value=answer) as get, \
             mock.patch.object(gvp.usage, "record"):
            out = io.StringIO()
            call_command("fetch_gvp", stdout=out)
        self.assertIn("화산 4 곳", out.getvalue())
        self.assertEqual(get.call_args.kwargs["params"]["typeName"], gvp.LAYER)
        self.assertNotIn("key", get.call_args.kwargs["params"])
        data = json.loads((Path(folder) / volcanoes.FILE).read_text(encoding="utf-8"))
        self.assertEqual(len(data["volcanoes"]), 4)

    def test_실패하면_옛_파일을_두고_멈춘다(self):
        folder = tempfile.mkdtemp()
        old = written(folder).read_text(encoding="utf-8")
        with override_settings(EARTH_DIR=folder), \
             mock.patch.object(gvp.requests, "get", return_value=mock.MagicMock(status_code=503, content=b"")), \
             mock.patch.object(gvp.usage, "record"):
            with self.assertRaises(Exception):
                call_command("fetch_gvp", stdout=io.StringIO())
        self.assertEqual((Path(folder) / volcanoes.FILE).read_text(encoding="utf-8"), old)

    def test_화산_쪽(self):
        self.assertEqual(gvp.volcano_url(283030), "https://volcano.si.edu/volcano.cfm?vn=283030")


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-gvp-")
        patch = override_settings(EARTH_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gvp-t-"))
        patch.enable()
        self.addCleanup(patch.disable)
        written(self.dir)

    def test_타일(self):
        url = reverse("viewer:earth-volcano-tile", kwargs={"z": 0, "x": 1, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        im = Image.open(io.BytesIO(first.content)).convert("RGBA")
        self.assertGreater(im.getextrema()[3][1], 200)            # 세모가 찍혔다

    def test_누르면_화산(self):
        data = self.client.get(reverse("viewer:earth-volcano-at"), {"lon": 138.73, "lat": 35.36, "r": 0.2}).json()
        rows = dict(data["hits"][0]["rows"])
        self.assertEqual((rows["화산"], rows["마지막 분화"], rows["표고 (m)"]), ("Fujisan", "1707 년", "3,776"))
        self.assertTrue(data["hits"][0]["link"].endswith("vn=283030"))

    def test_날짜_바뀜선_너머도_찾는다(self):
        data = self.client.get(reverse("viewer:earth-volcano-at"), {"lon": -179.99, "lat": 0, "r": 0.2}).json()
        self.assertEqual(dict(data["hits"][0]["rows"])["마지막 분화"], "기원전 2000 년")

    def test_영어판(self):
        data = self.client.get(reverse("viewer:earth-volcano-at"), {"lon": 138.73, "lat": 35.36, "r": 0.2},
                               HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertEqual(dict(data["hits"][0]["rows"])["Last eruption"], "1707 CE")

    def test_화면이_범례를_받는다(self):
        page = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertIn("분화 기록이 없다", page)

    def test_파일이_없으면_빈_타일·목록에_서지_않는다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            r = self.client.get(reverse("viewer:earth-volcano-tile", kwargs={"z": 0, "x": 0, "y": 0}))
            page = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertEqual(Image.open(io.BytesIO(r.content)).convert("RGBA").getextrema()[3], (0, 0))
        self.assertIn('"volcanoes": []', page)
