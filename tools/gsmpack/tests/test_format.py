"""꼴 쓰고 읽기 (wetherilli 381) — Django 없이 돈다."""
import struct
import tempfile
import unittest
from pathlib import Path

from gsmpack import format


class Pack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "box-2026-10-09.gsmpack"

    def tearDown(self):
        self.tmp.cleanup()

    def test_쓰고_읽기(self):
        tiles = [("L/12/3510/1580", b"\x89PNG-a"), ("L/12/3511/1580", b""), ("vworld:Base/8/218/98", b"jpeg"),
                 ("L/12/3510/1580", b"dup")]
        head = format.write(self.path, {"box": "box", "title": "장성"}, tiles)
        self.assertEqual(head["tiles"], {"L/12/3510/1580": [0, 6], "vworld:Base/8/218/98": [6, 4]})
        raw = self.path.read_bytes()
        self.assertEqual(raw[:8], b"GSMPACK1")
        (n,) = struct.unpack("<I", raw[8:12])
        self.assertEqual(raw[12 + n:], b"\x89PNG-ajpeg")
        opened = format.read_header(self.path)
        self.assertEqual(opened[0]["title"], "장성")
        self.assertEqual(format.read_tile(self.path, "vworld:Base/8/218/98", opened), b"jpeg")
        self.assertIsNone(format.read_tile(self.path, "L/12/3511/1580"))        # 빈 타일은 넣지 않는다

    def test_꼴이_아니면(self):
        self.path.write_bytes(b"PK\x03\x04 nope")
        with self.assertRaises(ValueError):
            format.read_header(self.path)

    def test_목록(self):
        format.write(Path(self.tmp.name) / "a-20261010.gsmpack", {"box": "a", "title": "가", "bbox": [1, 2, 3, 4]}, [("L/1/0/0", b"x")])
        (Path(self.tmp.name) / "b-20261010.gsmpack").write_bytes(b"nope")              # 읽지 못하는 것은 뺀다
        got = format.listing(self.tmp.name)
        self.assertEqual([(p["box"], p["title"], p["tiles"]) for p in got], [("a", "가", 1)])
