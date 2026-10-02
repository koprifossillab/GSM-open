"""맨틀 슬랩 — Müller 2022 OPT1 (wetherilli 106). 원본(206 MB)을 쓰지 않고 VTU 를 손으로 지어 읽는다."""
import base64
import gzip
import json
import struct
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import mantle


def arr(code, values, typ, name=None, comps=None):
    raw = struct.pack(f"<{len(values)}{code}", *values)
    text = base64.b64encode(struct.pack("<Q", len(raw)) + raw).decode()
    attrs = f'type="{typ}" format="binary"' + (f' Name="{name}"' if name else "") + \
        (f' NumberOfComponents="{comps}"' if comps else "")
    return f"<DataArray {attrs}>{text}</DataArray>"


def vtu(points, tris) -> bytes:
    flat = [v for p in points for v in p]
    conn = [i for t in tris for i in t]
    return f"""<VTKFile type="UnstructuredGrid" byte_order="LittleEndian" header_type="UInt64">
<UnstructuredGrid><Piece NumberOfPoints="{len(points)}" NumberOfCells="{len(tris)}">
<Points>{arr("f", flat, "Float32", comps=3)}</Points>
<Cells>{arr("q", conn, "Int64", "connectivity")}{arr("q", [3 * (k + 1) for k in range(len(tris))], "Int64", "offsets")}
{arr("B", [5] * len(tris), "UInt8", "types")}</Cells>
</Piece></UnstructuredGrid></VTKFile>""".encode()


class Frames(SimpleTestCase):
    def test_연대에서_시점(self):
        self.assertEqual([mantle.frame_of(a) for a in (0, 9, 10, 11, 250, 1000, 1500)], [50, 50, 49, 49, 37, 0, 0])
        self.assertEqual(mantle.age_of(50), 0)


class Read(SimpleTestCase):
    def test_삼각형(self):
        pts = [(0.9, 0, 0), (0, 0.9, 0), (0, 0, 0.9)]
        points, conn = mantle.read_piece(vtu(pts, [(0, 1, 2)]), lines=False)
        self.assertEqual(list(conn), [0, 1, 2])
        self.assertAlmostEqual(points[0], 0.9, places=5)

    def test_삼각형이_아니면_멈춘다(self):
        data = vtu([(0.9, 0, 0), (0, 0.9, 0), (0, 0, 0.9)], [(0, 1, 2)]).replace(
            base64.b64encode(struct.pack("<Q", 1) + b"\x05").decode().encode(),
            base64.b64encode(struct.pack("<Q", 1) + b"\x09").decode().encode())
        with self.assertRaises(mantle.MantleError):
            mantle.read_piece(data, lines=False)


class Views(TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gsm-mantle-"))
        (self.dir / "mantle").mkdir()
        data = struct.pack("<9f", 0.9, 0, 0, 0, 0.9, 0, 0, 0, 0.9) + struct.pack("<3I", 0, 1, 2)
        (self.dir / "mantle" / "slabs-50-x.bin").write_bytes(data)
        (self.dir / "mantle" / "slabs-50-x.bin.gz").write_bytes(gzip.compress(data))
        (self.dir / "mantle" / "catalogue.json").write_text(json.dumps({"frames": [
            {"frame": 50, "age_ma": 0, "layers": {"slabs": {"file": "slabs-50-x.bin", "points": 3}}}]}))
        patch = override_settings(EARTH_DIR=str(self.dir))
        patch.enable()
        self.addCleanup(patch.disable)
        mantle._catalogue.cache_clear()
        self.addCleanup(mantle._catalogue.cache_clear)
        self.data = data

    def test_gzip_을_받으면_gzip_으로(self):
        url = reverse("viewer:earth-mantle", args=[50, "slabs"])
        r = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual((r["Content-Encoding"], gzip.decompress(r.content)), ("gzip", self.data))
        self.assertEqual(self.client.get(url).content, self.data)

    def test_목록에_없는_것은_없다(self):
        self.assertEqual(self.client.get(reverse("viewer:earth-mantle", args=[40, "slabs"])).status_code, 404)

    def test_화면에_점_수를_싣는다(self):
        self.assertContains(self.client.get(reverse("viewer:earth")), '"mantle": {"50": {"slabs": 3}}')
