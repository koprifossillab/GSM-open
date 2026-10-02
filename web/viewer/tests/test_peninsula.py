"""한반도 지질도 음영판·민판 — 좌표가 붙은 그림을 잘라 둔 5179 타일 (devlog 027·028).

진짜 PDF(43 MB)·PNG(13 MB)는 쓰지 않는다. QGIS 가 쓴 꼴을 작게 흉내 낸 것으로 읽기를 보고,
자르기는 작은 그림으로 본다.
"""
import dataclasses
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import crs, peninsula, views
from viewer.models import Layer, LayerGroup

#: QGIS 가 2026-07-21 에 쓴 PDF 의 /Measure 그대로 (위도, 경도)
GPTS = ("43.027818232915287 123.7779980300178551 33.8656210961218775 124.2220314233305345 "
        "33.8710270424568023 130.5682070076305763 43.0353218492508205 130.9839624426587079")


def fake_pdf(jpeg: bytes, gpts: str = GPTS, epsg: int = 5179) -> bytes:
    return (b"%PDF-1.4\n7 0 obj\n<<\n/Type /XObject\n/Subtype /Image\n/Width 4\n/Height 4\n"
            b"/Length 8 0 R\n/Filter /DCTDecode\n>>\nstream\n" + jpeg + b"\nendstream\nendobj\n"
            b"8 0 obj\n" + str(len(jpeg)).encode() + b"\nendobj\n"
            b"14 0 obj\n<< /GCS 15 0 R /GPTS [ " + gpts.encode() + b" ] /Subtype /GEO /Type /Measure >>\n"
            b"endobj\n15 0 obj\n<< /EPSG " + str(epsg).encode() + b" /Type /PROJCS >>\nendobj\n%%EOF\n")


def jpeg_bytes(size=(4, 4), color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


#: 민판의 월드파일 그대로 (2026-09-22)
PGW = ("84.7841827002628\n0.0000000000000\n0.0000000000000\n-84.7841827002628\n"
       "615892.2621782021597\n2563280.4801902757026\n")

SHADED, PLAIN = peninsula.SHADED, peninsula.PLAIN


class Grid(SimpleTestCase):
    def test_z7_이_음영판의_원본_해상도다(self):
        self.assertAlmostEqual(SHADED.resolution(7), 58.776, places=2)
        self.assertEqual(SHADED.grid_size(7), (39, 68))
        self.assertEqual(SHADED.grid_size(0), (1, 1))

    def test_z6_이_민판의_원본_해상도다(self):
        self.assertAlmostEqual(PLAIN.resolution(6), 84.558, places=2)
        self.assertEqual(PLAIN.grid_size(6), (35, 49))
        self.assertEqual(PLAIN.grid_size(0), (1, 1))

    def test_격자_밖은_없다(self):
        self.assertTrue(SHADED.valid_tile(7, 38, 67))
        self.assertFalse(SHADED.valid_tile(7, 39, 0))
        self.assertFalse(SHADED.valid_tile(8, 0, 0))
        self.assertFalse(PLAIN.valid_tile(7, 0, 0))

    def test_타일의_범위는_왼쪽_위에서_센다(self):
        x0, x1, y0, y1 = SHADED.extent
        west, south, east, north = SHADED.tile_bbox(0, 0, 0)
        self.assertEqual((west, north), (x0, y1))
        self.assertGreater(east, x1)
        self.assertLess(south, y0)

    def test_화면에_알리는_격자(self):
        grid = SHADED.grid()
        self.assertEqual(len(grid["resolutions"]), 8)
        self.assertGreater(grid["resolutions"][0], grid["resolutions"][-1])
        self.assertEqual(len(PLAIN.grid()["resolutions"]), 7)


class ReadPdf(SimpleTestCase):
    def test_그림과_좌표를_꺼낸다(self):
        jpeg = jpeg_bytes()
        got, epsg, corners = peninsula.read_pdf(fake_pdf(jpeg))
        self.assertEqual(got, jpeg)
        self.assertEqual(epsg, 5179)
        self.assertEqual(len(corners), 4)
        peninsula.check_corners(SHADED, epsg, corners)  # 음영판의 범위와 맞는다

    def test_모서리가_4326_에서도_반듯한_사각형이다(self):
        """5179 로 옮긴 네 모서리가 서로 1 m 안에서 맞는다 — 그림의 격자가 곧 5179 격자다."""
        _, _, corners = peninsula.read_pdf(fake_pdf(jpeg_bytes()))
        (xa, ya), (xb, yb), (xc, yc), (xd, yd) = (crs.from_latlon("5179", *c) for c in corners)
        self.assertAlmostEqual(xa, xb, delta=1)
        self.assertAlmostEqual(xc, xd, delta=1)
        self.assertAlmostEqual(ya, yd, delta=1)
        self.assertAlmostEqual(yb, yc, delta=1)

    def test_다른_판이면_멈춘다(self):
        shifted = GPTS.replace("123.7779980300178551", "123.9")
        _, epsg, corners = peninsula.read_pdf(fake_pdf(jpeg_bytes(), shifted))
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.check_corners(SHADED, epsg, corners)
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.check_corners(SHADED, 5186, corners)
        with self.assertRaises(peninsula.PeninsulaError):    # 다른 판의 범위
            peninsula.check_corners(PLAIN, 5179, peninsula.read_pdf(fake_pdf(jpeg_bytes()))[2])

    def test_좌표가_없으면_멈춘다(self):
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.read_pdf(fake_pdf(jpeg_bytes()).split(b"14 0 obj")[0])


class ReadWorld(SimpleTestCase):
    def test_원점은_화소의_가운데다(self):
        (x0, y0), (_, y1), (x1, _), _ = peninsula.world_corners(PGW, (PLAIN.width, PLAIN.height))
        self.assertAlmostEqual(x0, 615892.2622 - 84.7842 / 2, places=3)
        self.assertAlmostEqual(y1, 2563280.4802 + 84.7842 / 2, places=3)
        self.assertAlmostEqual(x1 - x0, 8865 * 84.7841827, places=2)
        self.assertAlmostEqual(y1 - y0, 12403 * 84.7841827, places=2)
        peninsula.check_world(PLAIN, PGW, (PLAIN.width, PLAIN.height))

    def test_고친_범위는_해안선_쪽으로_줄었다(self):
        """월드파일은 가로 0.267%·세로 0.137% 늘어나 있었다 (028)."""
        sx0, sx1, sy0, sy1 = PLAIN.stated
        x0, x1, y0, y1 = PLAIN.extent
        self.assertAlmostEqual((x1 - x0) / (sx1 - sx0), 1 - 0.002667, places=5)
        self.assertAlmostEqual((y1 - y0) / (sy1 - sy0), 1 - 0.001367, places=5)

    def test_다른_판이나_돌림이면_멈춘다(self):
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.check_world(PLAIN, PGW, (8000, 12403))
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.check_world(SHADED, PGW, (PLAIN.width, PLAIN.height))
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.world_corners(PGW.replace("0.0000000000000\n0.0", "0.5\n0.0", 1), (1, 1))
        with self.assertRaises(peninsula.PeninsulaError):
            peninsula.world_corners("1 2 3", (1, 1))

    def test_월드파일이_없으면_멈춘다(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "map.png"
            Image.new("RGB", (4, 4)).save(png)
            with self.assertRaises(peninsula.PeninsulaError):
                peninsula.open_source(PLAIN, png)
            png.with_suffix(".pgw").write_text(PGW)
            with self.assertRaises(peninsula.PeninsulaError):     # 크기가 다르다
                peninsula.open_source(PLAIN, png)


class Cut(SimpleTestCase):
    def test_흰_바탕은_투명하다(self):
        image = Image.new("RGB", (4, 1), (255, 255, 255))
        image.putpixel((1, 0), (250, 249, 251))        # JPEG 가 흔든 바탕
        image.putpixel((2, 0), (250, 200, 200))        # 옅은 분홍 — 땅이다
        image.putpixel((3, 0), (120, 120, 120))
        alpha = list(peninsula.transparent_white(image).getchannel("A").getdata())
        self.assertEqual(alpha, [0, 0, 255, 255])

    def test_그림_밖은_투명하고_다_비면_없다(self):
        x0, _, _, y1 = SHADED.extent
        res = SHADED.res
        sheet = dataclasses.replace(SHADED, width=512, height=512, max_zoom=1,
                                    extent=(x0, x0 + 512 * res, y1 - 512 * res, y1))
        land = Image.new("RGBA", (512, 512), (10, 120, 60, 255)).convert("RGBa")
        tile = peninsula.cut(sheet, land, 1, 1, 1, 1)
        self.assertEqual(tile.size, (256, 256))
        self.assertEqual(tile.getpixel((128, 128))[3], 255)
        whole = peninsula.cut(sheet, land.reduce(2), 2, 0, 0, 0)
        self.assertEqual(whole.getpixel((10, 10))[3], 255)
        sea = Image.new("RGBA", (512, 512), (0, 0, 0, 0)).convert("RGBa")
        self.assertIsNone(peninsula.cut(sheet, sea, 1, 1, 0, 0))


class TileView(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(PENINSULA_DIR=self.tmp.name)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_잘라_둔_것이_없으면_안내_타일(self):
        response = self.client.get("/GSM/peninsula/shaded/3/1/2.webp")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_잘라_둔_타일을_내준다(self):
        target = Path(self.tmp.name) / "tiles" / "3" / "1" / "2.webp"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"RIFF fake webp")
        response = self.client.get("/GSM/peninsula/shaded/3/1/2.webp")
        self.assertEqual(response.content, b"RIFF fake webp")
        self.assertEqual(response["Content-Type"], "image/webp")
        # 바다(잘라 두지 않은 자리)는 투명한 빈 타일
        response = self.client.get("/GSM/peninsula/shaded/3/0/0.webp")
        self.assertEqual(response.content, views.tiles.blank_tile(256, 256))

    def test_격자_밖과_모르는_레이어는_없다(self):
        (Path(self.tmp.name) / "tiles").mkdir()
        self.assertEqual(self.client.get("/GSM/peninsula/shaded/0/1/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/peninsula/other/0/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/peninsula/plain/7/0/0.webp").status_code, 404)

    def test_판마다_제_폴더에서_낸다(self):
        target = Path(self.tmp.name) / "tiles-plain" / "6" / "1" / "2.webp"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"RIFF plain")
        self.assertEqual(self.client.get("/GSM/peninsula/plain/6/1/2.webp").content, b"RIFF plain")
        # 음영판은 아직 잘라 두지 않았다 — 안내 타일
        self.assertEqual(self.client.get("/GSM/peninsula/shaded/6/1/2.webp")["Content-Type"], "image/png")

    def test_범례는_KIGAM_에_묻지_않는다(self):
        with mock.patch.object(views.kigam, "get_legend") as legend:
            response = self.client.get("/GSM/legend/", {"layer": "peninsula:shaded"})
        self.assertEqual(response.status_code, 404)
        legend.assert_not_called()

    def test_카탈로그가_격자와_투영을_알린다(self):
        group = LayerGroup.objects.create(name="커스텀 지질도", region="korea")
        Layer.objects.create(name="peninsula:shaded", title="한반도 지질도 (음영)", group=group,
                             upstream="peninsula")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        row = rows["peninsula:shaded"]
        self.assertEqual(row["projection"], "EPSG:5179")
        self.assertEqual(row["tiles"], "peninsula/shaded/{z}/{x}/{y}.webp")
        self.assertEqual(row["grid"]["extent"][0], SHADED.extent[0])
        self.assertFalse(row["queryable"])
        self.assertTrue(row["noLegend"])
