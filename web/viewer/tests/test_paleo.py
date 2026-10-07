"""그때 그 자리 — PALEOMAP 2016 판 회전 (wetherilli 087).

저장소의 `data/paleomap2016.json` 을 그대로 읽는다(125 KB). 기대값은 2026-09-30 에 EarthThruTime3D 의
`scripts/rotation_model.py` 로 원본 `.rot` 을 읽어 셈한 것과 맞춘 값이다(차이 0.01° 안).
"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import macrostrat, paleo, paleodem
from viewer.management.commands import build_paleomap


class Carry(SimpleTestCase):
    def setUp(self):
        self.m = paleo.model()

    def test_오늘은_그대로(self):
        got = self.m.carry(126.98, 37.57, 0)
        self.assertEqual((got["lon"], got["lat"]), (126.98, 37.57))

    def test_서울은_250_Ma_에(self):
        got = self.m.carry(126.98, 37.57, 250)
        self.assertAlmostEqual(got["lon"], 105.01, delta=0.02)
        self.assertAlmostEqual(got["lat"], 30.58, delta=0.02)
        self.assertEqual((got["pid"], got["reach"]), (604, 1100.0))

    def test_런던의_판은_600_Ma_까지(self):
        got = self.m.carry(-0.13, 51.5, 800)
        self.assertEqual((got["reason"], got["reach"]), ("beyond", 600.0))
        self.assertIn("lon", self.m.carry(-0.13, 51.5, 500))

    def test_바다_밑은_옮기지_못한다(self):
        self.assertEqual(self.m.carry(-150, 0, 100)["reason"], "ocean")

    def test_남극점_가까이도(self):
        # 극을 두른 다각형 — 경위도로 재면 틀리는 자리다
        self.assertEqual(self.m.plate_at(0, -85)["pid"], 802)


class Inside(SimpleTestCase):
    def test_날짜변경선을_넘는_고리(self):
        ring = [170, -10, -170, -10, -170, 10, 170, 10]
        self.assertTrue(paleo.inside(179.5, 0, ring))
        self.assertTrue(paleo.inside(-179.5, 0, ring))
        self.assertFalse(paleo.inside(100, 0, ring))
        # 대척점은 감김으로 못 가른다 — 대륙의 가운데를 바라보는지로 가른다
        self.assertTrue(paleo.inside(0, 0, ring))
        self.assertFalse(paleo.holds({"rings": [ring]}, 0, 0))
        self.assertTrue(paleo.holds({"rings": [ring]}, 179.5, 0))

    def test_극을_두른_고리(self):
        ring = [lon for k in range(0, 360, 30) for lon in (k - 180, -70)]
        self.assertTrue(paleo.inside(45, -89, ring))
        self.assertFalse(paleo.inside(45, -60, ring))


GPML = """<gml:featureMember><gpml:UnclassifiedFeature>
<gpml:reconstructionPlateId><gpml:ConstantValue><gpml:value>604</gpml:value></gpml:ConstantValue></gpml:reconstructionPlateId>
<gml:validTime><gml:TimePeriod><gml:begin><gml:TimeInstant><gml:timePosition>4500</gml:timePosition></gml:TimeInstant></gml:begin>
<gml:end><gml:TimeInstant><gml:timePosition gml:frame="http://gplates.org/TRS/flat">http://gplates.org/times/distantFuture</gml:timePosition></gml:TimeInstant></gml:end></gml:TimePeriod></gml:validTime>
<gml:posList gml:dimension="2">30 120 30 130 40 130 40 120 30 120</gml:posList>
</gpml:UnclassifiedFeature></gml:featureMember>
<gml:featureMember><gpml:UnclassifiedFeature>
<gpml:reconstructionPlateId><gpml:ConstantValue><gpml:value>999</gpml:value></gpml:ConstantValue></gpml:reconstructionPlateId>
<gml:validTime><gml:TimePeriod><gml:begin><gml:TimeInstant><gml:timePosition>0</gml:timePosition></gml:TimeInstant></gml:begin>
<gml:end><gml:TimeInstant><gml:timePosition>0</gml:timePosition></gml:TimeInstant></gml:end></gml:TimePeriod></gml:validTime>
<gml:posList gml:dimension="2">-80 -180 -80 180 80 180 80 -180 -80 -180</gml:posList>
</gpml:UnclassifiedFeature></gml:featureMember>"""
ROT = "604 0.0 90.0 0.0 0.0 000 !\n604 100.0 10.0 20.0 30.0 000 !\n604 100.0 10.0 20.0 30.0 000 ! 거듭\n"


class Build(SimpleTestCase):
    def test_GPML_은_위도가_먼저(self):
        f = list(build_paleomap.features(GPML))[0]
        self.assertEqual((f["pid"], f["from"], f["to"]), (604, 4500.0, -1e9))
        self.assertEqual(f["rings"][0][:4], [120.0, 30.0, 130.0, 30.0])

    def test_거듭_적힌_때는_하나만(self):
        self.assertEqual(build_paleomap.rotations(ROT), {"604:0": [0.0, 90.0, 0.0, 0.0, 100.0, 10.0, 20.0, 30.0]})

    def test_0_Ma_에만_있는_다각형은_버린다(self):
        # 온 지구를 덮는 순간의 다각형 — 두면 바다 밑도 판을 얻는다
        out = Path(tempfile.mkdtemp()) / "pm.json"
        zpath = Path(tempfile.mkdtemp()) / "a.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr(build_paleomap.ROTATION, ROT)
            zf.writestr(build_paleomap.POLYGONS, GPML)
        with mock.patch.dict(build_paleomap.SHA256, {build_paleomap.ROTATION: __import__("hashlib").sha256(ROT.encode()).hexdigest()}):
            call_command("build_paleomap", str(zpath), out=str(out), stdout=io.StringIO())
        self.assertEqual([f["pid"] for f in json.loads(out.read_text())["features"]], [604])

    def test_확인값이_다르면_멈춘다(self):
        zpath = Path(tempfile.mkdtemp()) / "a.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr(build_paleomap.ROTATION, ROT)
            zf.writestr(build_paleomap.POLYGONS, GPML)
        with self.assertRaises(CommandError):
            call_command("build_paleomap", str(zpath), out=str(zpath) + ".json", stdout=io.StringIO())


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-paleo-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_옛_위치(self):
        data = self.client.get(reverse("viewer:earth-paleo"), {"lon": 126.98, "lat": 37.57, "age": 250}).json()
        self.assertTrue(data["text"].startswith("북위 30.5"), data["text"])
        self.assertEqual(data["model"], "Scotese 2016 PALEOMAP")
        self.assertEqual(self.client.get(reverse("viewer:earth-paleo"), {"lon": 1}).status_code, 400)

    def test_누르면_단위의_연대마다_한_줄(self):
        seoul = {"source_id": 154, "name": "Precambrian crystalline metamorphic rocks", "b_int_name": "Precambrian",
                 "t_int_name": "Precambrian", "b_age": 4000, "t_age": 541, "color": "#F04370"}
        hit = {"units": [macrostrat.unit_row(seoul, "tiny")], "refs": {}}
        with mock.patch.object(macrostrat, "identify", return_value=hit):
            unit = self.client.get(reverse("viewer:earth-info"), {"lon": 126.98, "lat": 37.57, "z": 8}).json()["units"][0]
        rows = dict(unit["rows"])
        self.assertTrue(rows["그때의 자리 (541 Ma)"].startswith("북위 13."))
        self.assertEqual(rows["그때의 자리 (4000 Ma)"], "이 판은 1100 Ma 까지만 거슬러 옮긴다")
        # 옮겨진 연대만 — 화면이 그 연대로 EarthThruTime3D 링크를 단다 (wetherilli 088)
        self.assertEqual(unit["then"], [541.0])

    def test_파일이_없으면_그_줄_없이(self):
        paleo.model.cache_clear()
        self.addCleanup(paleo.model.cache_clear)
        with override_settings(PALEOMAP_FILE="/nonexistent/pm.json"):
            self.assertEqual(self.client.get(reverse("viewer:earth-paleo"),
                                             {"lon": 1, "lat": 1, "age": 1}).status_code, 503)


class Then(SimpleTestCase):
    """그때의 지구 (wetherilli 091) — 판을 돌려 칠하고, 누른 자리를 오늘로 되돌린다."""

    def setUp(self):
        self.m = paleo.model()

    def test_연대마다_그때_있던_조각만(self):
        now, then = self.m.reconstruct(0), self.m.reconstruct(250)
        self.assertGreater(len(now), len(then))
        self.assertTrue(all(p["from"] >= 250 for p in then))

    def test_옮긴_자리를_누르면_오늘로_돌아온다(self):
        got = self.m.carry(126.98, 37.57, 250)
        hit = self.m.plate_then(got["lon"], got["lat"], 250)
        self.assertEqual(hit["pid"], 604)
        self.assertAlmostEqual(hit["today_lon"], 126.98, delta=0.02)
        self.assertAlmostEqual(hit["today_lat"], 37.57, delta=0.02)
        self.assertIsNone(self.m.plate_then(-150, 0, 250))      # 판다랏사 한가운데

    def test_날짜변경선을_넘는_고리는_이어서_편다(self):
        poly = paleo.plane([170, -10, -170, -10, -170, 10, 170, 10])
        self.assertEqual([x for x, _ in poly], [170, 190, 190, 170])

    def test_극을_두른_고리는_극까지_막는다(self):
        ring = [lon for k in range(0, 360, 30) for lon in (k - 180, -70)]
        poly = paleo.plane(ring)
        self.assertEqual(poly[-1], (-180, -90.0))
        self.assertEqual(poly[-2][1], -90.0)
        self.assertAlmostEqual(poly[-2][0] - poly[0][0], 360.0)

    @override_settings(EARTH_DIR=tempfile.mkdtemp(prefix="gsm-nodem-"))
    def test_타일(self):
        from PIL import Image
        im = Image.open(io.BytesIO(paleo.render_tile(0.0, "land", 0, 1, 0))).convert("RGBA")
        self.assertEqual(im.size, (256, 256))
        self.assertGreater(im.getpixel((150, 60))[3], 200)        # 동경 105°·북위 48° — 몽골은 땅
        self.assertLess(im.getpixel((250, 128))[3], 20)          # 동경 176°·적도 — 태평양은 비었다
        self.assertGreater(im.getpixel((128, 254))[3], 200)       # 남극점 둘레 — 극까지 칠했다


class Relief(SimpleTestCase):
    """그때의 땅과 바다 밑 (wetherilli 375) — 구운 PaleoDEM 그림을 깔고, 없는 연대는 판 조각을 칠한다."""

    def setUp(self):
        from PIL import Image
        self.dir = tempfile.mkdtemp(prefix="gsm-dem-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        folder = Path(self.dir) / paleodem.DIR
        folder.mkdir()
        image = Image.new("RGB", (360, 180), (0, 0, 200))           # 서반구는 파랑, 동반구는 빨강
        image.paste((200, 0, 0), (180, 0, 360, 180))
        image.save(folder / "2500.webp", "WEBP", lossless=True)
        (folder / "index.json").write_text(json.dumps({"ages": [250.0], "meta": {"built": "t"}}))

    def test_가까운_시점은_2_5_Myr_안에서만(self):
        self.assertEqual(paleodem.stop(252), 250.0)
        self.assertIsNone(paleodem.stop(253))
        self.assertIsNone(paleodem.stop(700))

    def test_그림을_깔고_판_경계를_얹는다(self):
        from PIL import Image
        west = Image.open(io.BytesIO(paleo.render_tile(250.0, "land", 0, 0, 0))).convert("RGBA")
        east = Image.open(io.BytesIO(paleo.render_tile(250.0, "land", 0, 1, 0))).convert("RGBA")
        r, g, b, a = west.getpixel((10, 128))                        # 서경 173° — 판다랏사
        self.assertEqual(a, 255)
        self.assertGreater(b, 150)
        self.assertGreater(east.getpixel((250, 128))[0], 150)     # 동경 176°

    def test_시점이_없는_연대는_판_조각만(self):
        from PIL import Image
        im = Image.open(io.BytesIO(paleo.render_tile(700.0, "land", 0, 0, 0))).convert("RGBA")
        self.assertLess(im.getpixel((240, 128))[3], 20)                # 서경 11°·적도 — 그때는 바다

    def test_다시_구우면_타일의_판이_바뀐다(self):
        from viewer import views
        before = views.paleo_version()
        index = Path(self.dir) / paleodem.DIR / "index.json"
        index.write_text(json.dumps({"ages": [250.0], "meta": {"built": "u"}}))
        __import__("os").utime(index, (1, 1))
        self.assertNotEqual(views.paleo_version(), before)


class ThenViews(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-then-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_판_조각_타일(self):
        url = reverse("viewer:earth-paleo-tile", kwargs={"style": "land", "age": 250, "z": 0, "x": 0, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        bad = reverse("viewer:earth-paleo-tile", kwargs={"style": "land", "age": 250, "z": 0, "x": 2, "y": 0})
        self.assertEqual(self.client.get(bad).status_code, 404)

    def test_그때의_지구를_누르면(self):
        data = self.client.get(reverse("viewer:earth-paleo-at"), {"lon": 105.01, "lat": 30.58, "age": 250}).json()
        self.assertEqual(data["pid"], 604)
        self.assertEqual(dict(data["rows"])["판"], "604")
        sea = self.client.get(reverse("viewer:earth-paleo-at"), {"lon": -150, "lat": 0, "age": 250}).json()
        self.assertNotIn("rows", sea)

    def test_점묶음을_그때의_자리로(self):
        from viewer.models import Point, PointSet
        ps = PointSet.objects.create(name="시험", body="earth")
        Point.objects.create(pointset=ps, label="서울", lat=37.57, lon=126.98)
        Point.objects.create(pointset=ps, lat=0, lon=-150, props={})
        feats = self.client.get(reverse("viewer:pointset-paleo", args=[ps.pk]), {"age": 250}).json()["features"]
        seoul, sea = feats
        self.assertAlmostEqual(seoul["geometry"]["coordinates"][0], 105.01, delta=0.02)
        self.assertEqual(seoul["properties"]["_today"], [126.98, 37.57])
        self.assertIn("바다 밑", sea["properties"]["_paleo"])
