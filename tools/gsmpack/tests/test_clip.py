"""타일·지층 면을 박스로 잘라 낸다 — 도폭 하나를 구우면 묶음도 그 도폭만이다 (wetherilli 385)."""
import io
import unittest

from PIL import Image

from gsmpack import clip, grid

from .helpers import png


class Clip(unittest.TestCase):
    def test_타일(self):
        bbox = (129.0, 37.0, 129.25, 37.17)
        tile = png()
        # 도폭 안쪽의 깊은 타일은 그대로
        x, y = grid.tiles_for((129.1, 37.1, 129.1, 37.1), 14)[0]
        self.assertEqual(clip.clip_tile(tile, 14, x, y, bbox), tile)
        # 박스 밖의 타일은 버린다
        x, y = grid.tiles_for((127.0, 36.0, 127.0, 36.0), 14)[0]
        self.assertEqual(clip.clip_tile(tile, 14, x, y, bbox), b"")
        # 얕은 줌의 넓은 타일은 박스 밖이 투명하다
        x, y = grid.tiles_for((129.1, 37.1, 129.1, 37.1), 7)[0]
        image = Image.open(io.BytesIO(clip.clip_tile(tile, 7, x, y, bbox))).convert("RGBA")
        alpha = image.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertLess(sum(1 for v in alpha.getdata() if v) / (512 * 512), 0.01)     # 2.8° 타일에 0.25° 도폭

    def test_지층_면(self):
        box = (129.0, 37.0, 129.1, 37.1)
        inside = {"type": "Polygon", "coordinates": [[[129.02, 37.02], [129.05, 37.02], [129.05, 37.05], [129.02, 37.02]]]}
        self.assertEqual(clip.clip_polygons(inside, box)["coordinates"][0][0], [129.02, 37.02])
        across = {"type": "MultiPolygon", "coordinates": [
            [[[128.9, 37.05], [129.05, 37.05], [129.05, 37.2], [128.9, 37.2], [128.9, 37.05]]],
            [[[130.0, 38.0], [130.1, 38.0], [130.1, 38.1], [130.0, 38.0]]]]}             # 둘째 면은 다 밖
        got = clip.clip_polygons(across, box)
        self.assertEqual(got["type"], "Polygon")
        xs = [p[0] for p in got["coordinates"][0]]
        ys = [p[1] for p in got["coordinates"][0]]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (129.0, 129.05, 37.05, 37.1))
        outside = {"type": "Polygon", "coordinates": [[[130.0, 38.0], [130.1, 38.0], [130.1, 38.1], [130.0, 38.0]]]}
        self.assertIsNone(clip.clip_polygons(outside, box))

    def test_빈_타일(self):
        self.assertTrue(clip.is_blank(png(alpha=0)))
        self.assertFalse(clip.is_blank(png()))
        self.assertFalse(clip.is_blank(b"\xff\xd8 jpeg"))

    def test_좌표_줄이기(self):
        self.assertEqual(clip.round_coords([[129.0123456789, 37.0]]), [[129.01235, 37.0]])
