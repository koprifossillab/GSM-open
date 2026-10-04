"""남극 자력 이상 ADMAP-2 — Geosoft 격자 읽기·굽기·누른 자리 (wetherilli 262). 상류를 부르지 않는다 — 작은 격자를 지어 굽는다."""
import io
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import admap, geomap

NE, NV, RES = 40, 41, 150000.0
X0, Y0 = -(NE - 1) / 2 * RES, -(NV - 1) / 2 * RES        # 가운데가 극


def _values():
    """줄은 아래에서 위로. 왼쪽 아래 넷째 칸까지는 빈 곳, 위쪽 절반은 +300, 아래쪽은 −100"""
    out = []
    for row in range(NV):
        for col in range(NE):
            out.append(-1e32 if row == 0 and col < 4 else (300.0 if row >= NV // 2 else -100.0))
    return out


def grd(compressed=True) -> bytes:
    head = bytearray(512)
    struct.pack_into("<5i", head, 0, 1028 if compressed else 4, 2, NE, NV, 1)
    struct.pack_into("<7d", head, 20, RES, RES, X0, Y0, 0.0, 0.0, 1.0)
    raw = struct.pack(f"<{NE * NV}f", *_values())
    if not compressed:
        return bytes(head) + raw
    per = 7                                                    # 덩이마다 줄 수
    blocks = [raw[i:i + 4 * NE * per] for i in range(0, len(raw), 4 * NE * per)]
    comp = [b"\x0f\x0e\xff\xfe" + b"\x00" * 12 + zlib.compress(b) for b in blocks]
    table = 16 + 12 * len(blocks)
    offs, at = [], 512 + table
    for c in comp:
        offs.append(at)
        at += len(c)
    pre = struct.pack("<Ii2i", 0xF8E7D8C7, 2, len(blocks), per) + struct.pack(f"<{len(blocks)}q", *offs) \
        + struct.pack(f"<{len(blocks)}i", *(len(c) for c in comp))
    return bytes(head) + pre + b"".join(comp)


class Read(SimpleTestCase):
    def test_압축판과_민판이_같다(self):
        a, b = admap.read_grd(grd(True)), admap.read_grd(grd(False))
        self.assertEqual((a["ne"], a["nv"], a["de"], a["x0"]), (NE, NV, RES, X0))
        self.assertEqual(list(a["values"]), list(b["values"]))
        self.assertLess(a["values"][0], admap.DUMMY)

    def test_모르는_격자는_거절(self):
        bad = bytearray(grd(False))
        struct.pack_into("<i", bad, 4, 1)                      # 부호 있는 정수
        with self.assertRaises(admap.AdmapError):
            admap.read_grd(bytes(bad))

    def test_칠하기(self):
        self.assertEqual(admap.index_of(0), 128)
        self.assertEqual(admap.index_of(10 ** 4), 255)
        self.assertEqual(admap.index_of(-10 ** 4), 1)
        self.assertLess(admap.index_of(-50), admap.index_of(50))
        self.assertEqual(len(admap.palette()), 256 * 3)
        rows = admap.legend()["groups"][0]["rows"]
        self.assertEqual([r["label"] for r in rows][:2], ["-600 nT", "-300 nT"])
        self.assertEqual(rows[4]["label"], "0 nT")


class Build(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        with zipfile.ZipFile(root / "grid.zip", "w") as zf:
            zf.writestr("grid/ADMAP_2B_2017_s.grd", b"other")
            zf.writestr("grid/ADMAP_2B_2017.grd", grd())
        self.patch = override_settings(ADMAP_DIR=str(root / "out"))
        self.patch.enable()
        self.stats = admap.build(root / "grid.zip", log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽고_누른다(self):
        self.assertEqual((self.stats["cells"], self.stats["min"], self.stats["max"]), (NE * NV - 4, -100, 300))
        self.assertTrue(admap.available())
        self.assertEqual(admap.value_at(-81.0, 0.0), 300)            # 3031 에서 경도 0° 가 위(y > 0) — 위쪽 절반
        self.assertEqual(admap.value_at(-81.0, 180.0), -100)
        self.assertIsNone(admap.value_at(10.0, 0.0))                  # 격자 밖
        tile = Image.open(io.BytesIO(admap.read_tile(0, 0, 0))).convert("RGBA")
        self.assertGreater(sum(1 for p in tile.getdata() if p[3]), 10000)

    def test_주소(self):
        r = self.client.get("/GSM/admap/0/0/0.webp")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/webp"))
        self.assertEqual(self.client.get("/GSM/admap/9/0/0.webp").status_code, 404)
        got = self.client.get("/GSM/admap/info/", {"lat": -81, "lon": 0}).json()
        self.assertEqual(got["features"][0]["props"]["자력 이상 (nT)"], 300)
        self.assertEqual(self.client.get("/GSM/admap/info/", {"lat": 10, "lon": 0}).json(), {"features": []})
        from viewer import views
        row = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}["admap:anomaly"]
        self.assertEqual((row["projection"], row["maxZoom"]), ("EPSG:3031", admap.MAX_ZOOM))
        self.assertTrue(row["tiles"].startswith("admap/{z}/{x}/{y}.webp"))
        self.assertIn("groups", row["classLegend"])


class Missing(SimpleTestCase):
    def test_파일이_없어도_돈다(self):
        from django.test import Client
        with tempfile.TemporaryDirectory() as tmp, override_settings(ADMAP_DIR=tmp):
            self.assertEqual(Client().get("/GSM/admap/0/0/0.webp").status_code, 200)     # 안내 타일
            self.assertIsNone(admap.value_at(-80.0, 0.0))
