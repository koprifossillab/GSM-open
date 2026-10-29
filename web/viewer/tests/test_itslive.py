"""ITS_LIVE 빙하 유속 — COG 머리 읽기·Range 묶기·색·내주기 (wetherilli 433). 상류를 부르지 않는다."""
import io
import json
import struct
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import itslive


def bigtiff(levels) -> bytes:
    """[(w, h, offsets, counts)] → 그 겹들을 IFD 로 적은 BigTIFF 머리. 첫 겹에만 좌표(120 m, 왼쪽 위 (1000, 9000))"""
    out = bytearray(b"II+\x00" + struct.pack("<HHQ", 8, 0, 16))
    extra = []                                               # (자리를 적을 곳, 바이트)
    for k, (w, h, offsets, counts) in enumerate(levels):
        tags = [(256, 16, (w,)), (257, 16, (h,)), (258, 3, (32,)), (259, 3, (5,)), (317, 3, (1,)),
                (322, 3, (512,)), (323, 3, (512,)), (324, 16, offsets), (325, 16, counts), (339, 3, (3,))]
        if k == 0:
            tags += [(33550, 12, (120.0, 120.0, 0.0)), (33922, 12, (0.0, 0.0, 0.0, 1000.0, 9000.0, 0.0))]
        tags.sort()
        start = len(out)
        out += struct.pack("<Q", len(tags))
        for tag, typ, values in tags:
            fmt, size = itslive._TYPES[typ]
            raw = struct.pack(f"<{len(values)}{fmt}", *values)
            out += struct.pack("<HHQ", tag, typ, len(values))
            if len(raw) <= 8:
                out += raw.ljust(8, b"\0")
            else:
                extra.append((len(out), raw))
                out += b"\0" * 8
        nxt = len(out)
        out += b"\0" * 8
        levels_left = k < len(levels) - 1
        for at, raw in extra:
            struct.pack_into("<Q", out, at, len(out))
            out += raw
        extra = []
        if levels_left:
            struct.pack_into("<Q", out, nxt, len(out))
        del start
    return bytes(out)


class Head(SimpleTestCase):
    def test_겹과_좌표(self):
        head = bigtiff([(1024, 600, (100, 200, 300, 400), (10, 10, 0, 10)), (512, 300, (500,), (20,))])
        levels = itslive.parse_ifds(head)
        self.assertEqual([(l["w"], l["res"]) for l in levels], [(1024, 120.0), (512, 240.0)])
        self.assertEqual((levels[1]["x0"], levels[1]["ytop"], levels[0]["counts"]), (1000.0, 9000.0, (10, 10, 0, 10)))

    def test_짧은_머리(self):
        head = bigtiff([(1024, 600, (100, 200, 300, 400), (10, 10, 0, 10))])
        with self.assertRaisesRegex(itslive.ItsLiveError, "짧다"):
            itslive.parse_ifds(head[:60])
        with self.assertRaises(itslive.ItsLiveError):
            itslive.parse_ifds(b"II*\x00" + head[4:])

    def test_붙은_타일을_묶는다(self):
        groups = itslive._ranges([(0, 1000, 100), (1, 1100, 50), (2, 10 ** 7, 30)])
        self.assertEqual([(a, b, len(items)) for a, b, items in groups], [(1000, 1149, 2), (10 ** 7, 10 ** 7 + 29, 1)])

    def test_LZW_타일을_푼다(self):
        try:
            from PIL import features
            if not features.check("libtiff"):
                self.skipTest("libtiff 가 없다")
        except ImportError:
            self.skipTest("PIL.features 가 없다")
        src = Image.new("F", (512, 512), 42.5)
        buf = io.BytesIO()
        src.save(buf, format="TIFF", compression="tiff_lzw", strip_size=512 * 512 * 4)   # 띠 하나
        raw = buf.getvalue()
        strip = Image.open(io.BytesIO(raw))
        off, count = strip.tag_v2[273][0], strip.tag_v2[279][0]
        got = itslive._decode(raw[off:off + count], 512, 512)
        self.assertEqual(got.getpixel((7, 9)), 42.5)


class Colour(SimpleTestCase):
    def test_GIBS_색표와_같은_눈금(self):
        self.assertEqual(itslive.index_of(0), 1)
        self.assertEqual(itslive.index_of(10 ** 6), 255)
        pal = itslive.palette()
        # GIBS MEaSUREs 색표의 10 m/년 칸은 (5, 154, 249), 100 은 (151, 255, 96) — 같은 jet·log 눈금이라 한 채널 30 단계 안에 든다
        for v, rgb in ((10, (5, 154, 249)), (100, (151, 255, 96)), (1000, (255, 99, 0))):
            i = itslive.index_of(v)
            self.assertLess(max(abs(a - b) for a, b in zip(pal[3 * i:3 * i + 3], rgb)), 30, v)

    def test_3413(self):
        x, y = itslive.lonlat_to_3413(-45.0, 90.0)
        self.assertAlmostEqual(x, 0.0, places=3)
        x, y = itslive.lonlat_to_3413(-45.0, 70.0)           # 중앙 경선 위 — 아래쪽(y < 0)
        self.assertAlmostEqual(x, 0.0, places=3)
        self.assertLess(y, -2_000_000)


class Serve(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = override_settings(ITSLIVE_DIR=self.tmp.name)
        self.patch.enable()
        region = Path(self.tmp.name) / "svalbard"
        # 줌 2 칸 하나 — 스발바르의 칸. 아래 반은 투명
        x, y = itslive.lonlat_to_3413(15.0, 78.5)
        span = 512 * itslive.resolution(2)
        self.tx, self.ty = int((x + itslive.ORIGIN) // span), int((itslive.ORIGIN - y) // span)
        tile = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        tile.paste((255, 0, 0, 255), (0, 0, 512, 256))
        target = region / "tiles" / "2" / str(self.tx) / f"{self.ty}.webp"
        target.parent.mkdir(parents=True)
        tile.save(target, format="WEBP", lossless=True)
        # 값 — 3×2 칸(한 칸 100 km), 가운데 칸만 빈 곳
        left, top = x - 150000, y + 100000
        (region / "base.i16").write_bytes(struct.pack("<6h", 10, -32768, 30, 40, 50, 60))
        (region / "meta.json").write_text(json.dumps({"region": "svalbard", "epsg": "3413", "base_zoom": 2, "pieces": [
            {"file": "base.i16", "name": "base", "x0": left, "ytop": top, "res": 100000.0, "ne": 3, "nv": 2}]}))

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_누른_자리(self):
        self.assertEqual(itslive.value_at("svalbard", 78.5, 15.0), 50)          # 아래 줄 가운데
        self.assertIsNone(itslive.value_at("svalbard", 60.0, 15.0))
        self.assertIsNone(itslive.value_at("greenland", 70.0, -40.0))            # 굽지 않았다
        got = self.client.get("/GSM/itslive/info/", {"layer": "itslive:svalbard", "lat": 78.5, "lon": 15.0}).json()
        self.assertEqual(got["features"][0]["props"], {"빙하 유속 (m/년)": 50})
        self.assertEqual(self.client.get("/GSM/itslive/info/", {"layer": "x", "lat": 1, "lon": 1}).status_code, 400)

    def test_가까우면_윗_타일을_늘린다(self):
        self.assertIsNotNone(itslive.read_tile("svalbard", 2, self.tx, self.ty))
        top = itslive.read_tile("svalbard", 3, 2 * self.tx, 2 * self.ty)                 # 위 반의 왼쪽 — 빨강
        r, g, b, _ = Image.open(io.BytesIO(top)).convert("RGBA").getpixel((256, 256))
        self.assertTrue(r > 250 and g < 5 and b < 5, (r, g, b))                      # 빨강 (WebP 라 한두 단계 어긋난다)
        self.assertIsNone(itslive.read_tile("svalbard", 3, 2 * self.tx, 2 * self.ty + 1))  # 아래 반 — 투명
        self.assertIsNone(itslive.read_tile("svalbard", 4, 0, 0))

    def test_주소와_카탈로그(self):
        r = self.client.get(f"/GSM/itslive/svalbard/3/{2 * self.tx}/{2 * self.ty}.webp")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/webp"))
        self.assertEqual(self.client.get("/GSM/itslive/svalbard/9/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/itslive/mars/0/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/itslive/greenland/0/0/0.webp").status_code, 200)       # 안내 타일
        from viewer import views
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        row = rows["itslive:svalbard"]
        self.assertEqual((row["projection"], row["grid"]["tileSize"], len(row["grid"]["resolutions"])), ("EPSG:3413", 512, 7))
        self.assertEqual(row["grid"]["origin"], [-4194304.0, 4194304.0])
        self.assertTrue(row["tiles"].startswith("itslive/svalbard/{z}/{x}/{y}.webp"))
        self.assertTrue(row["legendImg"].endswith("MEaSUREs_Ice_Velocity_Greenland_H.svg"))
        self.assertEqual(rows["itslive:antarctica"]["projection"], "EPSG:3031")


class Fetch(SimpleTestCase):
    def test_206_이_아니면_멈춘다(self):
        resp = mock.Mock(status_code=200, content=b"x" * 10)
        with mock.patch.object(itslive.requests, "get", return_value=resp), mock.patch.object(itslive.usage, "record"):
            with self.assertRaisesRegex(itslive.ItsLiveError, "200"):
                itslive._get("https://example.invalid/a.tif", 0, 9)
