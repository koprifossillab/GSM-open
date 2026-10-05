"""평면 격자 타일을 3857 로 다시 펴기 — 3D 가 한반도 지질도를 얹는 길.

원본이 우리 격자의 어디에 떨어지는지만 맞으면 그림이 제자리에 간다. 합성 격자(한 칸이
한 색인 원본)를 펴서, 3857 타일의 한 점이 원본의 알맞은 칸 색을 받는지 본다.
"""
import io
import math

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import warp


def lonlat_tile(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def solid(color):
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), color).save(buf, "PNG")
    return buf.getvalue()


class Render(SimpleTestCase):
    def grid(self):
        """5179 에 원점을 둔 가짜 격자 — 한 픽셀 100 m, 타일 번호마다 다른 색."""
        self.fetched = []
        ox, oy = 900000.0, 2000000.0

        def fetch(level, tx, ty):
            self.fetched.append((level, tx, ty))
            return solid(((tx * 40) % 256, (ty * 40) % 256, 90, 255))

        return warp.Grid(levels=[0], res=lambda level: 100.0, origin=lambda level: (ox, oy),
                         project=warp.to_5179, fetch=fetch)

    def test_한_점이_제_타일의_색을_받는다(self):
        lat, lon, z = 37.5, 127.0, 9
        fx, fy = lonlat_tile(lat, lon, z)
        x, y = int(fx), int(fy)
        png = warp.render(self.grid(), z, x, y)
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        px, py = int((fx - x) * 256), int((fy - y) * 256)
        east, north = warp.to_5179(lat, lon)
        tx, ty = int((east - 900000) // 25600), int((2000000 - north) // 25600)
        self.assertEqual(image.getpixel((px, py))[:2], ((tx * 40) % 256, (ty * 40) % 256))

    def test_원본이_없으면_None(self):
        grid = self.grid()
        grid.fetch = lambda level, tx, ty: None
        self.assertIsNone(warp.render(grid, 9, 436, 199))

    def test_단계는_땅_해상도보다_촘촘한_것_가운데_가장_거친_것(self):
        grid = warp.Grid(levels=range(7, 14), res=lambda l: 2.0 ** (l - 3), origin=None,
                         project=None, fetch=None)
        self.assertEqual(grid.pick(120), 9)        # 64 m
        self.assertEqual(grid.pick(30), 7)         # 16 m
        self.assertEqual(grid.pick(5), 7)          # 가장 촘촘한 것도 모자라면 그것

    def test_카카오_격자는_번호를_뒤집어_넘긴다(self):
        asked = []
        grid = warp.kakao_grid((7, 13), (-30000, -60000), (2, 5),
                               lambda level, x, y: asked.append((level, x, y)))
        grid.fetch(13, 0, 0)                       # 위에서 첫 줄 = 아래에서 다섯째 줄
        self.assertEqual(asked, [(13, 0, 4)])
        self.assertEqual(grid.origin(13), (-30000, -60000 + 5 * 256 * 1024))


class WarpView(TestCase):
    def test_밖에_열면_닫힌다(self):
        with override_settings(PUBLIC=True):
            r = self.client.get("/GSM/warp/peninsula/shaded/10/873/396.png")
        self.assertEqual(r.status_code, 404)

    def test_모르는_레이어와_먼_줌은_404(self):
        self.assertEqual(self.client.get("/GSM/warp/peninsula/nope/10/873/396.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/warp/peninsula/shaded/3/1/1.png").status_code, 404)


class GeomapGrid(SimpleTestCase):
    """남극 GeoMAP(040) — 3031 격자를 3857 로. 512 px 로도 편다."""

    def test_한_점이_제_3031_타일의_색을_받는다(self):
        from viewer import geomap

        def fetch(level, tx, ty):
            return solid(((tx * 40) % 256, (ty * 40) % 256, 90, 255))

        lat, lon, z = -74.62, 164.23, 8          # 장보고기지
        fx, fy = lonlat_tile(lat, lon, z)
        x, y = int(fx), int(fy)
        png = warp.render(warp.geomap_grid(fetch), z, x, y, 512)
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        self.assertEqual(image.size, (512, 512))
        # 고른 단계를 되짚어 그 점이 드는 3031 타일을 센다
        meters = 40075016.686 / 2 ** z / 512 * math.cos(math.radians(lat))
        level = warp.geomap_grid(fetch).pick(meters)
        tx, ty = geomap.tile_of(level, *geomap.lonlat_to_3031(lon, lat))
        px, py = int((fx - x) * 512), int((fy - y) * 512)
        self.assertEqual(image.getpixel((px, py))[:2], ((tx * 40) % 256, (ty * 40) % 256))

    def test_남쪽_끝_위도(self):
        self.assertAlmostEqual(warp.south_of(0, 0), -85.0511, places=3)
        self.assertAlmostEqual(warp.south_of(1, 0), 0.0, places=6)


class GeomapWarpView(TestCase):
    def test_남위_60도_북쪽은_그리지_않고_빈_타일(self):
        r = self.client.get("/GSM/warp/geomap/geomap_simple_geology/5/27/20@2x.png")   # 남위 40° 언저리
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(r.content)).size, (512, 512))
        self.assertIsNone(Image.open(io.BytesIO(r.content)).convert("RGBA").getbbox())

    def test_모르는_레이어와_먼_줌은_404(self):
        self.assertEqual(self.client.get("/GSM/warp/geomap/nope/5/27/28.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/warp/geomap/geomap_faults/2/1/3.png").status_code, 404)


def _io_bytes():
    import io as _io
    return _io.BytesIO()


class PolarMore(TestCase):
    """IBCSO 자료 출처·ADMAP 자력 이상도 3D 에 — GeoMAP 격자의 남극 판을 3857 로 편다 (wetherilli 335)"""
    def setUp(self):
        import tempfile
        from django.test import override_settings
        from PIL import Image as _Image
        root = tempfile.mkdtemp(prefix="gsm-admap-warp-")
        buf = _io_bytes()
        _Image.new("RGBA", (256, 256), (200, 40, 40, 255)).save(buf, "WEBP")
        for z in range(5):                                                       # 펴는 법이 땅 해상도에 맞는 단계를 고른다 — 다 둔다
            for x in range(2 ** z):
                tdir = __import__("pathlib").Path(root) / "tiles" / str(z) / str(x)
                tdir.mkdir(parents=True)
                for y in range(2 ** z):
                    (tdir / f"{y}.webp").write_bytes(buf.getvalue())
        for patch in (override_settings(ADMAP_DIR=root), override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-admap-tc-"))):
            patch.enable()
            self.addCleanup(patch.disable)

    def test_ADMAP_을_편다(self):
        import io as _io
        from PIL import Image as _Image
        got = self.client.get("/GSM/warp/admap/anomaly/2/1/3.png")              # 남극을 덮는 3857 칸
        self.assertEqual(got.status_code, 200)
        px = _Image.open(_io.BytesIO(got.content)).convert("RGBA").getpixel((128, 200))
        self.assertTrue(all(abs(a - b) <= 3 for a, b in zip(px[:3], (200, 40, 40))), px)   # WebP 는 손실 압축이다
        self.assertEqual(self.client.get("/GSM/warp/admap/anomaly/2/1/1.png").content[:8], b"\x89PNG\r\n\x1a\n")   # 북쪽은 빈 타일

    def test_3D_목록에_선다(self):
        from django.core.management import call_command
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        html = self.client.get("/GSM/3d/?region=antarctica").content.decode()
        self.assertIn('value="admap:anomaly"', html)
        self.assertIn('value="ibcso:tid"', html)
        from viewer import views as _views
        self.assertTrue({"ngu", "gtk"} <= set(_views.MAP3D_WMS))
