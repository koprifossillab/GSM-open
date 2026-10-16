"""중국 지질도 1:400만 스캔 — 경위선으로 맞춘 좌표 (wetherilli 386).

진짜 스캔(45 MB)은 쓰지 않는다. 좌표는 2026-10-16 에 스캔의 경위선 위에서 짚은 점으로 본다 — 맞춘 모형이 낸 값이
아니라 그림에서 잰 값이라, 상수를 잘못 옮기면 깨진다.
"""
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import china4m, views
from viewer.models import Layer, LayerGroup

#: (경선이면 'lon'·위선이면 'lat', 도, 원본 화소 x, y) — 하늘색 경위선의 가운데를 짚은 것
GRATICULE = [
    ("lon", 76, 805.4, 4768.6),
    ("lon", 104, 6810.4, 1846.6),
    ("lon", 124, 10787.0, 4203.1),
    ("lon", 140, 14115.1, 3905.1),
    ("lat", 20, 8455.4, 9295.7),
    ("lat", 32, 13144.7, 5334.7),
    ("lat", 44, 8040.4, 3076.6),
    ("lat", 52, 7107.0, 986.4),
]
#: 한 화소(423 m)를 넘지 않게 — 위도 1° 는 111 km, 경도 1° 는 여기서 70–105 km
TOLERANCE_DEG = 0.004


class Coordinates(SimpleTestCase):
    def test_graticule(self):
        for kind, value, x, y in GRATICULE:
            lon, lat = china4m.to_lonlat(x, y)
            got = lon if kind == "lon" else lat
            with self.subTest(kind=kind, value=value):
                self.assertAlmostEqual(got, value, delta=TOLERANCE_DEG)

    def test_round_trip(self):
        for lon, lat in ((75.0, 40.0), (105.0, 35.0), (121.5, 25.0), (135.0, 48.0)):
            x, y = china4m.to_pixel(lon, lat)
            back = china4m.to_lonlat(x, y)
            self.assertAlmostEqual(back[0], lon, places=7)
            self.assertAlmostEqual(back[1], lat, places=7)

    def test_scale(self):
        """투영 평면의 한 화소는 423 m, 북위 35° 의 땅 위로는 431 m — 두 표준위선 사이라 축척 계수가 1 보다 작다."""
        x0, y0 = china4m.to_pixel(105.0, 35.0)
        x1, y1 = china4m.to_pixel(105.0, 36.0)
        self.assertAlmostEqual(111_000 / ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 431, delta=3)

    def test_on_map(self):
        self.assertTrue(china4m.on_map(*china4m.to_pixel(104.0, 30.7)))       # 청두
        self.assertFalse(china4m.on_map(*china4m.to_pixel(112.0, 10.0)))      # 남해제도 — 삽입도 자리 밖
        self.assertFalse(china4m.on_map(1000, 8000))                          # 범례
        self.assertFalse(china4m.on_map(100, 100))                            # 도곽 밖


@unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "numpy 가 없다 — 마스크는 호스트에서만 굽는다")
class MaskColours(SimpleTestCase):
    def test_classes(self):
        import numpy as np
        from viewer.management.commands.build_china4m_mask import background
        rgb = np.array([[[214, 230, 230], [229, 255, 254], [254, 126, 254], [254, 254, 202], [176, 255, 255]]])
        grey, sea, white, pink, teal, river = background(rgb)
        self.assertEqual(grey[0].tolist(), [True, False, False, False, False])
        self.assertEqual(pink[0].tolist(), [False, False, True, False, False])
        # 노란 제4계는 바탕이 아니다. 쥐라계 J3 의 청록은 바다 수심 색과 같다 — 그래서 색이 아니라 이어짐으로 가른다
        self.assertFalse((grey | sea | white | pink)[0, 3])
        self.assertTrue(sea[0, 4])


class Grid(SimpleTestCase):
    def test_range(self):
        self.assertTrue(china4m.valid_tile(3, 6, 3))                  # 온 중국이 든 z3 의 한 장
        self.assertFalse(china4m.valid_tile(2, 2, 1))                 # 첫 줌 밑
        self.assertFalse(china4m.valid_tile(10, 800, 400))            # 마지막 줌 위 — 화면이 늘린다
        self.assertFalse(china4m.valid_tile(5, 0, 0))                 # 범위 밖

    def test_factor(self):
        """원본 한 화소(431 m)보다 타일 한 화소가 두 배 넘게 거칠면 줄인 원본에서 편다."""
        self.assertEqual(china4m.factor_for(9), 1)
        self.assertEqual(china4m.factor_for(8), 1)
        self.assertEqual(china4m.factor_for(7), 2)
        self.assertEqual(china4m.factor_for(3), 32)


class Cut(SimpleTestCase):
    def test_땅_밖은_투명하고_다_비면_없다(self):
        """원본을 1/32 로 줄인 크기의 가짜 그림 — 오른쪽 반만 칠했다. z3 에서 서쪽(신장) 장은 비고 동쪽 장은 찬다."""
        w, h = china4m.SIZE[0] // 32 + 1, china4m.SIZE[1] // 32 + 1
        level = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        level.paste((200, 100, 50, 255), (w // 2, 0, w, h))
        level = level.convert("RGBa")
        west = china4m.tile_range(3)[0]
        self.assertIsNone(china4m.cut(level, 32, 3, west, 3))
        tile = china4m.cut(level, 32, 3, west + 1, 3)
        self.assertEqual(tile.size, (256, 256))
        self.assertEqual(tile.getpixel((255, 128)), (200, 100, 50, 255))


class TileView(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(CHINA4M_DIR=self.tmp.name, PUBLIC=False)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_잘라_둔_것이_없으면_안내_타일(self):
        response = self.client.get("/GSM/china4m/3/6/3.webp")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_잘라_둔_타일을_내준다(self):
        target = Path(self.tmp.name) / "tiles" / "3" / "6" / "3.webp"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"RIFF fake webp")
        response = self.client.get("/GSM/china4m/3/6/3.webp")
        self.assertEqual(response.content, b"RIFF fake webp")
        self.assertEqual(response["Content-Type"], "image/webp")
        # 중국 밖(잘라 두지 않은 자리)은 투명한 빈 타일
        self.assertEqual(self.client.get("/GSM/china4m/3/5/3.webp").content, views.tiles.blank_tile(256, 256))
        self.assertEqual(self.client.get("/GSM/china4m/3/0/0.webp").status_code, 404)

    def test_밖에_열면_닫는다(self):
        (Path(self.tmp.name) / "tiles").mkdir()
        with override_settings(PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/china4m/3/6/3.webp").status_code, 404)

    def test_카탈로그가_타일을_알린다(self):
        group = LayerGroup.objects.create(name="중국 지질도 1:400만 (2002)", region="china")
        Layer.objects.create(name=china4m.NAME, title="중국 지질도 1:400만 (스캔)", group=group, upstream="china4m")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        row = rows[china4m.NAME]
        self.assertEqual(row["projection"], "EPSG:3857")
        self.assertEqual(row["tiles"], "china4m/{z}/{x}/{y}.webp")
        self.assertEqual(row["maxZoom"], 9)
        with override_settings(PUBLIC=True):
            rows = {l["name"] for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
            self.assertNotIn(china4m.NAME, rows)


def _index_of(code):
    return next(i for i, ids in enumerate(china4m.classes()) if code in ids)


class Legend(SimpleTestCase):
    def test_색이_같은_칸은_한_번호를_쓴다(self):
        self.assertEqual(_index_of("Nh"), _index_of("Pt3²"))
        self.assertNotEqual(_index_of("J3"), _index_of("J2"))

    def test_바다_수심_칸은_넣지_않는다(self):
        """땅 안의 그 청록은 쥐라계다 — 바다 칸이 있으면 쓰촨 분지를 눌러 '수심 200–1000 m' 가 뜬다."""
        self.assertFalse(any(i.startswith("sea_") for ids in china4m.classes() for i in ids))

    def test_지층의_설명은_되풀이하지_않는다(self):
        props = china4m.friendly(_index_of("J3"))
        self.assertEqual(props["기호"], "J3")
        self.assertEqual(props["지질시대"], "쥐라기 후기")
        self.assertNotIn("설명", props)
        props = china4m.friendly(_index_of("γ5³"), "en")
        self.assertEqual(props["암상"], "granite")

    def test_같은_색의_칸을_적는다(self):
        props = china4m.friendly(_index_of("Nh"))
        self.assertIn("같은 색의 칸", props)

    def test_색_번호를_매긴다(self):
        """범례 색 → 그 번호, 검정·청록 지명 글자 → 먹, 마스크 밖 → 0."""
        from viewer.management.commands.build_china4m import Command  # noqa: F401 — 명령이 import 되는지도 본다
        j3 = tuple(next(u["rgb"] for u in china4m.legend()["units"] if u["id"] == "J3"))
        colors = [j3, (0, 0, 0), (32, 130, 120), (228, 252, 252), j3]
        image = Image.new("RGB", (10, 2))
        for i, c in enumerate(colors):
            image.paste(c, (2 * i, 0, 2 * i + 2, 2))
        mask = Image.new("L", (10, 2), 255)
        mask.paste(0, (8, 0, 10, 2))
        w, h, data = china4m.build_units(image, mask)
        self.assertEqual((w, h), (5, 1))
        self.assertEqual(list(data), [_index_of("J3"), china4m.INK, china4m.INK, china4m.WATER, china4m.OUTSIDE])


class UnitGrid(TestCase):
    """색 번호 격자(37 MB)는 성긴 파일로 흉내 낸다 — 0(땅 밖)이 거의 다고 짚은 자리만 쓴다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(CHINA4M_DIR=self.tmp.name, PUBLIC=False)
        patch.enable()
        self.addCleanup(patch.disable)
        self.w, self.h = china4m.SIZE[0] // 2, china4m.SIZE[1] // 2
        root = Path(self.tmp.name)
        (root / china4m.UNITS_META).write_text(f'{{"width": {self.w}, "height": {self.h}, "scale": 2}}')
        with open(root / china4m.UNITS, "wb") as f:
            f.truncate(self.w * self.h)

    def paint(self, lon, lat, value, r=6, centre=None):
        x, y = china4m.to_pixel(lon, lat)
        cx, cy = int(x // 2), int(y // 2)
        with open(Path(self.tmp.name) / china4m.UNITS, "r+b") as f:
            for yy in range(cy - r, cy + r + 1):
                f.seek(yy * self.w + cx - r)
                f.write(bytes([value]) * (2 * r + 1))
            if centre is not None:
                f.seek(cy * self.w + cx)
                f.write(bytes([centre]))

    def test_먹을_빼고_고른다(self):
        self.paint(105.5, 30.5, _index_of("J3"), centre=china4m.INK)
        index, share = china4m.unit_at(105.5, 30.5)
        self.assertEqual(index, _index_of("J3"))
        self.assertEqual(share, 1.0)
        self.assertIsNone(china4m.unit_at(110.0, 35.0))           # 칠하지 않은 자리 — 땅 밖

    def test_속성_주소(self):
        self.paint(105.5, 30.5, _index_of("J3"))
        response = self.client.get("/GSM/china4m/info/", {"layer": china4m.NAME, "lat": 30.5, "lon": 105.5})
        props = response.json()["features"][0]["props"]
        self.assertEqual(props["기호"], "J3")
        self.client.cookies["gsm_lang"] = "en"
        props = self.client.get("/GSM/china4m/info/", {"layer": china4m.NAME, "lat": 30.5, "lon": 105.5}).json()["features"][0]["props"]
        self.assertEqual(props["Geologic age"], "Late Jurassic")
        self.assertEqual(self.client.get("/GSM/china4m/info/", {"layer": "x", "lat": 1, "lon": 1}).status_code, 400)

    def test_보는_범위의_범례(self):
        self.paint(105.5, 30.5, _index_of("J3"), r=30)
        rows = self.client.get("/GSM/china4m/legend/", {"layer": china4m.NAME, "bbox": "105,30,106,31"}).json()["rows"]
        self.assertEqual([r["symbol"] for r in rows], ["J3"])
        self.assertEqual(self.client.get("/GSM/china4m/legend/", {"layer": china4m.NAME}).status_code, 400)

    def test_격자가_없으면_503(self):
        (Path(self.tmp.name) / china4m.UNITS).unlink()
        response = self.client.get("/GSM/china4m/info/", {"layer": china4m.NAME, "lat": 30.5, "lon": 105.5})
        self.assertEqual(response.status_code, 503)


class Places(TestCase):
    """지명 이름표 (wetherilli 389) — Natural Earth 지명 가운데 중국 땅 안의 것, 한국어(영어)와 한자."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(CHINA4M_DIR=self.tmp.name, PUBLIC=False)
        patch.enable()
        self.addCleanup(patch.disable)

    def labels(self, lang="ko"):
        return {f["properties"]["label"] for f in china4m.place_features(lang)}

    def test_한국어와_한자를_나란히(self):
        self.assertIn("시안시 西安", self.labels())
        self.assertIn("Lanzhou 兰州", self.labels("en"))

    def test_땅_밖은_뺀다(self):
        """색 번호 격자가 없으면 범위만 본다 — 서울도 든다. 격자가 있으면 땅 밖(0)이라 빠진다."""
        self.assertTrue(any(label.startswith("서울") for label in self.labels()))
        w, h = china4m.SIZE[0] // 2, china4m.SIZE[1] // 2
        root = Path(self.tmp.name)
        (root / china4m.UNITS_META).write_text(f'{{"width": {w}, "height": {h}, "scale": 2}}')
        with open(root / china4m.UNITS, "wb") as f:
            f.truncate(w * h)
        self.assertEqual(self.labels(), set())

    def test_점_주소와_카탈로그(self):
        response = self.client.get("/GSM/points/", {"layer": china4m.PLACES})
        self.assertEqual(response["Content-Type"], "application/geo+json")
        self.assertGreater(len(response.json()["features"]), 400)
        group = LayerGroup.objects.create(name="중국 지질도 1:400만 (2002)", region="china")
        Layer.objects.create(name=china4m.PLACES, title="지명 (Natural Earth)", group=group, upstream="china4m")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows[china4m.PLACES]["style"], "label")
        with override_settings(PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/points/", {"layer": china4m.PLACES}).status_code, 404)
