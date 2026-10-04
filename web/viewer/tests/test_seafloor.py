"""바다 밑 — 해양 지각 연대·퇴적층 두께 (wetherilli 264). 상류를 부르지 않는다 — 작은 NetCDF-3·글 격자를 지어 굽는다."""
import io
import struct
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import seafloor


def _pad(b: bytes) -> bytes:
    return b + b"\x00" * (-len(b) % 4)


def netcdf3(lon, lat, z, fill=None) -> bytes:
    """2 차원 실수 격자 하나를 가진 NetCDF-3 고전판 — GMT 의 .grd 와 같은 꼴(lon·lat·z)."""
    def name(s):
        b = s.encode()
        return struct.pack(">I", len(b)) + _pad(b)

    dims = struct.pack(">II", 10, 2) + name("lon") + struct.pack(">I", len(lon)) + name("lat") + struct.pack(">I", len(lat))
    gatts = struct.pack(">II", 0, 0)
    vars_ = []
    sizes = [8 * len(lon), 8 * len(lat), 4 * len(z)]
    payloads = [struct.pack(f">{len(lon)}d", *lon), struct.pack(f">{len(lat)}d", *lat), struct.pack(f">{len(z)}f", *z)]

    def var(vname, ids, typ, vsize, begin, atts=b""):
        att = (struct.pack(">II", 12, 1) + atts) if atts else struct.pack(">II", 0, 0)
        return name(vname) + struct.pack(">I", len(ids)) + b"".join(struct.pack(">I", i) for i in ids) + att + \
            struct.pack(">III", typ, vsize, begin)

    fill_att = name("_FillValue") + struct.pack(">II", 5, 1) + struct.pack(">f", fill) if fill is not None else b""
    head_len = 0
    for _ in range(2):                                  # 자리(begin)는 머리 길이를 알아야 한다 — 두 번 짓는다
        begin = head_len
        vars_ = [var("lon", [0], 6, sizes[0], begin), var("lat", [1], 6, sizes[1], begin + sizes[0]),
                 var("z", [1, 0], 5, sizes[2], begin + sizes[0] + sizes[1], fill_att)]
        head = b"CDF\x01" + struct.pack(">I", 0) + dims + gatts + struct.pack(">II", 11, 3) + b"".join(vars_)
        head_len = len(head)
    return head + b"".join(payloads)


class Read(SimpleTestCase):
    def test_NetCDF3_를_읽고_줄을_북에서_남으로(self):
        lon, lat = [-180.0, 0.0, 180.0], [-90.0, 0.0, 90.0]          # 남→북으로 적힌 것(GMT 흔한 꼴)
        z = [1.0, 2.0, 3.0, 4.0, -9.0, 6.0, 7.0, 8.0, 9.0]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "a.grd")
            p.write_bytes(netcdf3(lon, lat, z, fill=-9.0))
            g = seafloor.read_age(p)
        self.assertEqual((g["w"], g["h"], g["lon0"], g["lat0"], g["dx"], g["dy"]), (3, 3, -180.0, 90.0, 180.0, 90.0))
        self.assertEqual(list(g["values"][:3]), [7.0, 8.0, 9.0])               # 북쪽 줄이 먼저
        self.assertNotEqual(g["values"][4], g["values"][4])                    # 채움 값은 NaN

    def test_글_격자(self):
        rows = [f"{lon}\t{lat}\t{v}" for lat, vals in ((90, (1, 2, 3)), (0, ("NaN", 5, 6)), (-90, (7, 8, 9)))
                for lon, v in zip((-180, 0, 180), vals)]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "s.xyz")
            p.write_text("\n".join(rows) + "\n")
            g = seafloor.read_xyz(p, 3, 3)
        self.assertEqual((g["lon0"], g["lat0"], g["dx"], g["dy"]), (-180.0, 90.0, 180.0, 90.0))
        self.assertEqual(list(g["values"])[-1], 9.0)

    def test_범례(self):
        rows = seafloor.legend("age")
        self.assertEqual(rows[0]["name"], "0–10 Ma")
        self.assertEqual(seafloor.legend("sediment")[-1]["name"], "7,000–12,000 m")


class Build(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = override_settings(EARTH_DIR=self.tmp.name)
        self.patch.enable()
        w, h = 37, 19                                      # 10° 격자점
        values = [float("nan") if (j == 9 and i == 18) else float(i * 5) for j in range(h) for i in range(w)]
        self.info = seafloor.build("age", {"w": w, "h": h, "lon0": -180.0, "lat0": 90.0, "dx": 10.0, "dy": 10.0,
                                           "values": values})

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽고_누르고_그린다(self):
        self.assertTrue(seafloor.available("age"))
        self.assertEqual(self.info["max"], 180.0)
        self.assertEqual(seafloor.at("age", -180.0, 50.0), 0.0)
        self.assertEqual(seafloor.at("age", 10.0, 10.0), 95.0)            # i=19 → 95 Ma
        self.assertIsNone(seafloor.at("age", 0.0, 0.0))                     # 빈 칸
        tile = Image.open(io.BytesIO(seafloor.render_tile("age", 0, 1, 0))).convert("RGBA")
        self.assertGreater(sum(1 for p in tile.getdata() if p[3]), 60000)

    def test_주소(self):
        from django.test import Client
        c = Client()
        r = c.get("/GSM/earth/seafloor/seaage/0/0/0.png")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
        got = c.get("/GSM/earth/seafloor/at/", {"layer": "seaage", "lon": 10, "lat": 10}).json()
        self.assertEqual(got["value"], 95.0)
        self.assertIn("95.0 Ma", got["text"])
        self.assertEqual(c.get("/GSM/earth/seafloor/at/", {"layer": "x", "lon": 0, "lat": 0}).status_code, 400)
        self.assertEqual(c.get("/GSM/earth/seafloor/sediment/0/0/0.png").status_code, 200)           # 안내 타일


class Page(TestCase):
    def test_구운_것이_있을_때만_레이어가_선다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(EARTH_DIR=tmp):
            self.assertNotIn('"seafloor": {"age"', self.client.get("/GSM/earth/").content.decode())
            seafloor.build("sediment", {"w": 2, "h": 2, "lon0": -180.0, "lat0": 90.0, "dx": 360.0, "dy": 180.0,
                                        "values": [1.0, 2.0, 3.0, 4.0]})
            page = self.client.get("/GSM/earth/").content.decode()
        self.assertIn('"seafloor": {"sediment"', page)
        self.assertIn('"sediment": "', page)                                   # 타일 주소의 판
