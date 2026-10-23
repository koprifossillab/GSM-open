"""격자 꼴 — 3857 은 전과 같은 칸, 3031·Esri 극 격자는 화면의 격자, 극 평사도법에서는 테두리 다각형으로 자른다 (wetherilli 410)."""
import io
import random
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from gsmpack import bake, clip, format, grid

from .helpers import png

SEJONG = (-59.05, -62.30, -58.55, -62.10)


class Grids(unittest.TestCase):
    def test_3857_은_전과_같다(self):
        rnd = random.Random(1)
        for _ in range(2000):
            z = rnd.randint(0, 18)
            x, y = rnd.randrange(2 ** z), rnd.randrange(2 ** z)
            self.assertEqual(grid.MERCATOR.cell_extent(z, x, y), grid.cell_extent(z, x, y))
        for z in (6, 10, 13):
            self.assertEqual(grid.MERCATOR.tiles_for((129.0, 37.0, 129.25, 37.17), z), grid.tiles_for((129.0, 37.0, 129.25, 37.17), z))

    def test_3031_은_타일_크기와_상관없이_같은_칸이다(self):
        """GEOMAP_GRID(256)와 createXYZ(512)는 같은 범위로 지은 격자라 칸이 같다 — 열쇠의 줌만 소스가 정한다"""
        for z in (4, 9, 13):
            self.assertEqual(grid.ANTARCTIC.tiles_for(SEJONG, z), grid.ANTARCTIC.with_tile(512).tiles_for(SEJONG, z))

    def test_극을_품는_박스는_받지_않는다(self):
        """극 평사도법에서 극을 품는 경위도 네모는 테두리가 고리가 아니다 — 자르기가 엉뚱해진다(판 세션이 짚었다)"""
        for bbox in [(-180, -90, 180, -89), (-10, -90, 10, -85), (-180, -70, 180, -60)]:
            with self.assertRaises(ValueError):
                grid.ANTARCTIC.tiles_for(bbox, 1)
        self.assertTrue(grid.MERCATOR.tiles_for((-180, -80, 180, 80), 1))       # 3857 은 상관없다

    def test_esri_격자는_범위_안의_칸만(self):
        self.assertEqual(grid.ESRI_ANTARCTIC.tiles_for((-60, -80, 60, -50), 0), [(0, 0)])
        cells = grid.ESRI_ANTARCTIC.tiles_for(SEJONG, 13)
        self.assertTrue(cells and all(0 <= x < 2 ** 13 and 0 <= y < 2 ** 13 for x, y in cells))

    def test_세종은_3031_의_남서쪽이다(self):
        x, y = grid.lonlat_to_3031(-58.79, -62.22)
        self.assertLess(x, 0)
        self.assertGreater(y, 0)                          # 서경은 3031 의 위쪽 왼편(중앙 경선 0°, 위가 0° 경선)
        self.assertAlmostEqual((x * x + y * y) ** 0.5 / 1000, 3080, delta=60)   # 극에서 3 천 km 남짓


class ClipPolar(unittest.TestCase):
    def test_박스_밖은_비운다(self):
        z = 9
        cells = grid.ANTARCTIC.tiles_for(SEJONG, z)
        kept = {c: clip.clip_tile(png(size=256), z, *c, SEJONG, grid.ANTARCTIC) for c in cells}
        self.assertTrue(any(kept.values()))
        partly = [v for v in kept.values() if v]
        alpha = [Image.open(io.BytesIO(v)).getchannel("A").getextrema() for v in partly]
        self.assertTrue(any(lo == 0 for lo, hi in alpha))                 # 가장자리 칸은 일부를 비웠다
        # 박스에서 먼 칸은 다 비운다
        far = grid.ANTARCTIC.tiles_for((-40, -70, -39, -69), z)[0]
        self.assertEqual(clip.clip_tile(png(size=256), z, *far, SEJONG, grid.ANTARCTIC), b"")

    def test_다_안이면_그대로(self):
        z = 15
        inner = grid.ANTARCTIC.tiles_for((-58.81, -62.21, -58.80, -62.20), z)
        data = png(size=256)
        self.assertTrue(any(clip.clip_tile(data, z, *c, SEJONG, grid.ANTARCTIC) is data for c in inner))


class FakePolar:
    tile_size = 256
    type = "image/png"
    attribution = "시험"
    grid = grid.ANTARCTIC
    kind = "geomap"
    touched = False

    def __init__(self, name):
        self.name = self.title = name

    def grid_zoom(self, screen):
        return screen

    def tiles(self, bbox, z):
        return self.grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return None

    def fetch(self, z, x, y):
        return png(size=256)


class Header(unittest.TestCase):
    def test_머리에_격자를_적는다(self):
        box = {"title": "세종", "region": "antarctica", "bbox": list(SEJONG), "layers": {"geomap_simple_geology": [9, 11]}}
        with tempfile.TemporaryDirectory() as tmp:
            plan = bake.Plan("sejong", box, {"geomap_simple_geology": FakePolar("geomap_simple_geology")})
            done = bake.bake(plan, tmp, bake.NoParts(), log=lambda *a: None)
            head, _ = format.read_header(done["path"])
        self.assertEqual(head["layers"]["geomap_simple_geology"]["grid"], "EPSG:3031")
        for key in head["tiles"]:
            _, z, x, y = key.rsplit("/", 3)
            self.assertIn((int(x), int(y)), grid.ANTARCTIC.tiles_for(SEJONG, int(z)))


if __name__ == "__main__":
    unittest.main()
