"""화성의 고운 지형 — 착륙지 HiRISE 따위를 줌 9 너머에서 (wetherilli 274). 상류는 바꿔 끼운다."""
import io
from unittest import mock

from django.test import SimpleTestCase
from PIL import Image

from viewer import trek, views


def tile_at(lon: float, lat: float, z: int) -> tuple:
    step = 180 / 2 ** z
    return z, int((lon + 180) // step), int((90 - lat) // step)


def tiff(values) -> bytes:
    image = Image.new("F", (trek.DEM_SIZE, trek.DEM_SIZE))
    image.putdata(values)
    buf = io.BytesIO()
    image.save(buf, "TIFF")
    return buf.getvalue()


class Parts(SimpleTestCase):
    def test_자리와_줌으로_고른다(self):
        gale = tile_at(137.4, -4.6, 15)
        self.assertEqual(trek.mars_dem_part(*gale)[0], "Gale_DEM_SMG_1m")
        self.assertIsNone(trek.mars_dem_part(*tile_at(137.4, -4.6, 9)))          # 줌 9 까지는 200 m 판
        insight = tile_at(135.0, 4.5, 14)
        self.assertIsNone(trek.mars_dem_part(*insight))                          # 20 m 판의 줌 끝은 13
        self.assertEqual(trek.mars_dem_part(*tile_at(135.0, 4.5, 13))[0][:7], "InSight")
        self.assertIsNone(trek.mars_dem_part(*tile_at(0.0, 0.0, 12)))            # 판이 없는 자리
        self.assertNotIn("DEM_1m_VictoriaCrater", [p[0] for p in trek.MARS_DEM_PARTS])

    def test_빈_칸은_200_m_판으로(self):
        z, x, y = tile_at(137.4, -4.6, 15)
        fine = [-4000.0] * (trek.DEM_SIZE ** 2)
        fine[0] = -3.4e38                                                        # 자료 밖
        base = [-4100.0] * (trek.DEM_SIZE ** 2)
        calls = []

        def fake(path, params):
            calls.append(path)
            r = mock.Mock(status_code=200, headers={"content-type": "image/tiff"})
            r.content = tiff(fine if path.startswith("Gale_") else base)
            return r
        with mock.patch.object(trek, "_mars", side_effect=fake), mock.patch.object(trek, "_image", side_effect=lambda r: r.content):
            png = trek.mars_dem_tile(z, x, y)
        self.assertEqual([c.split("/")[0] for c in calls], ["Gale_DEM_SMG_1m", trek.MARS_DEM])
        px = Image.open(io.BytesIO(png)).convert("RGB").load()
        decode = lambda p: p[0] * 256 + p[1] + p[2] / 256 - 32768                # noqa: E731
        self.assertAlmostEqual(decode(px[0, 0]), -4100.0, delta=1)
        self.assertAlmostEqual(decode(px[1, 0]), -4000.0, delta=1)


class Route(SimpleTestCase):
    def test_판_밖의_깊은_줌은_404(self):
        z, x, y = tile_at(0.0, 0.0, 12)
        self.assertEqual(self.client.get(f"/GSM/mars/dem/{z}/{x}/{y}.png").status_code, 404)

    def test_열쇠는_판마다(self):
        self.assertNotEqual(views.mars_dem_key(*tile_at(137.4, -4.6, 15)), views.mars_dem_key(15, 0, 0))
        self.assertTrue(views.mars_dem_key(3, 4, 2))
