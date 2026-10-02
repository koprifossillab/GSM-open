"""해류 — ECCO2 의 문(`ecco.py`)과 굽기(`ocean.py`), 그리고 주소 (koprifossillab 014).

상류를 부르지 않는다. netCDF classic 머리와 Range 의 답을 흉내 낸다. 굽기는 numpy 가 있어야 돈다 — CI 는
`requirements-wind.txt` 를 깔고, 없는 곳에서는 건너뛴다.
"""
import importlib.util
import json
import struct
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django.test import SimpleTestCase, override_settings

from viewer import ecco, ocean

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
W, H = ocean.WIDTH, ocean.HEIGHT


def _name(text: str) -> bytes:
    raw = text.encode()
    return struct.pack(">I", len(raw)) + raw + b"\0" * ((4 - len(raw) % 4) % 4)


def classic_header(var: str, begin: int) -> bytes:
    """`var(TIME, DEPTH_T, LATITUDE_T, LONGITUDE_T)` 하나뿐인 CDF-1 머리. 속성 하나(units)를 끼워 건너뛰기를 본다."""
    dims = [("TIME", 1), ("DEPTH_T", 50), ("LATITUDE_T", H), ("LONGITUDE_T", W)]
    out = b"CDF\x01" + struct.pack(">I", 0)
    out += struct.pack(">II", 10, len(dims)) + b"".join(_name(n) + struct.pack(">I", size) for n, size in dims)
    out += struct.pack(">II", 0, 0)                                   # 전역 속성 없음
    out += struct.pack(">II", 11, 1) + _name(var) + struct.pack(">I", 4) + struct.pack(">4I", 0, 1, 2, 3)
    out += struct.pack(">II", 12, 1) + _name("units") + struct.pack(">II", 2, 3) + b"m/s\0"
    out += struct.pack(">III", 5, W * H * 50 * 4, begin)
    return out


class HeaderTests(SimpleTestCase):
    def test_parse(self):
        head = ecco.parse_header(classic_header("VVEL", 9804))
        self.assertEqual(head["VVEL"]["begin"], 9804)
        self.assertEqual(head["VVEL"]["type"], 5)
        self.assertEqual([n for _, n in head["VVEL"]["dims"]], [1, 50, H, W])

    def test_not_classic(self):
        with self.assertRaises(ecco.EccoError):
            ecco.parse_header(b"\x89HDF\r\n\x1a\n")


class SurfaceTests(SimpleTestCase):
    """머리를 읽고 표층만 묻는다 — 시작 자리는 변수마다 다르다."""

    def test_asks_first_level_only(self):
        asked = []
        size = W * H * 4

        def fake_get(url, byte_range=None, timeout=120):
            asked.append(byte_range)
            if byte_range[0] == 0:
                return classic_header("UVEL", 9800)
            return b"\0" * size
        with mock.patch.object(ecco, "_get", side_effect=fake_get):
            body = ecco.surface("UVEL", "20060617")
        self.assertEqual(len(body), size)
        self.assertEqual(asked[1], (9800, 9800 + size - 1))

    def test_rejects_other_vars(self):
        with self.assertRaises(ecco.EccoError):
            ecco.surface("THETA", "20060617")


class ReadTests(SimpleTestCase):
    """NAS 포털은 큰 Range 의 끝 바이트를 빼고 보낸다 — 끝을 한 바이트 더 묻고 쓸 만큼만 읽는다."""

    def test_reads_only_wanted(self):
        raw = mock.Mock()
        raw.read.return_value = b"x" * 10
        r = mock.Mock(status_code=206, raw=raw)
        self.assertEqual(ecco._read(r, (0, 9)), b"x" * 10)
        raw.read.assert_called_once_with(10, decode_content=True)

    def test_short_body_fails(self):
        raw = mock.Mock()
        raw.read.return_value = b"x" * 3
        with self.assertRaises(Exception):
            ecco._read(mock.Mock(status_code=206, raw=raw), (0, 9))


@skipUnless(HAS_NUMPY, "numpy 가 없다 — 굽기는 호스트에서만 돈다")
class EncodeTests(SimpleTestCase):
    def fields(self):
        import numpy as np
        u = np.zeros((H, W), dtype=">f4")
        v = np.zeros((H, W), dtype=">f4")
        # 머리의 경도로 0.125°(열 0), 위도 −0.125°(줄 359) 인 바다 한 칸 — 자료는 430 열 밀려 있으니 거기서 와야 한다
        u[360, (0 - 430) % W] = 0.5
        v[360, (0 - 429) % W] = -0.25
        u[0, 5] = 3e35                               # 남극 안쪽의 쓰레기
        return u.tobytes(), v.tobytes()

    def test_shift_mask_and_frame(self):
        import io
        import numpy as np
        from PIL import Image
        png, scale = ocean.encode(*self.fields())
        img = np.array(Image.open(io.BytesIO(png)))
        self.assertEqual(img.shape, (H, W, 3))
        sea = np.argwhere(img[..., 2] == 255)
        self.assertEqual(len(sea), 1)
        row, col = sea[0]
        # 북쪽 줄부터·경도 −180 부터 — 위도 −0.125 는 줄 360, 경도 0.125 는 열 720
        self.assertEqual((row, col), (360, 720))
        self.assertEqual(scale, {"u": [0.5, 0.5], "v": [-0.25, -0.25]})

    def test_write_and_index(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(OCEAN_DIR=tmp):
            entry = ocean.write_time("ecco2", "20060617", *self.fields())
            ocean.write_index("ecco2", [entry])
            self.assertTrue(ocean.png_path("ecco2", "20060617").exists())
            index = ocean.read_index("ecco2")
        self.assertEqual(index["times"][0]["t"], "20060617")
        self.assertEqual(index["width"], W)


class ViewTests(SimpleTestCase):
    def test_index_and_png(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(OCEAN_DIR=tmp):
            Path(tmp, "ecco2", "20060617").mkdir(parents=True)
            Path(tmp, "ecco2", "20060617", "surface.png").write_bytes(b"\x89PNG fake")
            ocean.write_index("ecco2", [{"t": "20060617", "u": [-1, 1], "v": [-1, 1]}])
            index = self.client.get("/GSM/earth/ocean/").json()
            png = self.client.get("/GSM/earth/ocean/ecco2/20060617/surface.png")
            missing = self.client.get("/GSM/earth/ocean/ecco2/20060620/surface.png")
        self.assertEqual(index["ecco2"]["times"][0]["t"], "20060617")
        self.assertEqual(png.status_code, 200)
        self.assertEqual(missing.status_code, 404)

    def test_module_has_no_numpy_at_top(self):
        """운영 이미지에는 numpy 가 없다 — 굽기 함수 안에서만 부른다."""
        text = Path(ocean.__file__).read_text(encoding="utf-8")
        self.assertNotIn("\nimport numpy", text)
        self.assertNotIn("\nfrom numpy", text)


class MonthlyTests(SimpleTestCase):
    """달마다 15 일에 가장 가까운 3 일 평균 하나 (koprifossillab 015)."""

    def test_pick_nearest_mid_month(self):
        from viewer.management.commands.build_ecco2 import monthly
        days = ["19920105", "19920108", "19920114", "19920117", "19920202", "19920216", "19920228"]
        self.assertEqual(monthly(days), ["19920114", "19920216"])

    def test_tie_takes_earlier(self):
        from viewer.management.commands.build_ecco2 import monthly
        self.assertEqual(monthly(["20060613", "20060617"]), ["20060613"])
