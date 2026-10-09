"""오프라인 묶음(.gsmpack) — 꼴 쓰고 읽기, 박스 굽기, 목록·내려받기 (wetherilli 381). 상류를 부르지 않는다."""
import io
import json
import struct
import tempfile
from pathlib import Path
from unittest import mock

from PIL import Image

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import kigam, offlinepack, vworld
from viewer.management.commands import build_offline_pack
from viewer.models import Layer, LayerGroup


class Pack(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "box-2026-10-09.gsmpack"

    def tearDown(self):
        self.tmp.cleanup()

    def test_쓰고_읽기(self):
        tiles = [("L/12/3510/1580", b"\x89PNG-a"), ("L/12/3511/1580", b""), ("vworld:Base/8/218/98", b"jpeg"),
                 ("L/12/3510/1580", b"dup")]
        head = offlinepack.write(self.path, {"box": "box", "title": "장성"}, tiles)
        self.assertEqual(head["tiles"], {"L/12/3510/1580": [0, 6], "vworld:Base/8/218/98": [6, 4]})
        raw = self.path.read_bytes()
        self.assertEqual(raw[:8], b"GSMPACK1")
        (n,) = struct.unpack("<I", raw[8:12])
        self.assertEqual(raw[12 + n:], b"\x89PNG-ajpeg")
        opened = offlinepack.read_header(self.path)
        self.assertEqual(opened[0]["title"], "장성")
        self.assertEqual(offlinepack.read_tile(self.path, "vworld:Base/8/218/98", opened), b"jpeg")
        self.assertIsNone(offlinepack.read_tile(self.path, "L/12/3511/1580"))        # 빈 타일은 넣지 않는다

    def test_꼴이_아니면(self):
        self.path.write_bytes(b"PK\x03\x04 nope")
        with self.assertRaises(ValueError):
            offlinepack.read_header(self.path)


def png(alpha=255, size=512):
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), (200, 100, 50, alpha)).save(buf, format="PNG")
    return buf.getvalue()


BOX = {"_note": "시험", "tiny": {"title": "작은 박스", "region": "korea", "bbox": [129.0, 37.0, 129.05, 37.05],
                                 "layers": {"L_50K_Geology_Map": [10, 12], "vworld:Base": [10, 12]}, "budget_mb": 200}}


class Build(TestCase):
    """가짜 타일로 굽고 다시 읽는다 — 상류를 부르지 않는다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.boxes = root / "boxes.json"
        self.boxes.write_text(json.dumps(BOX), encoding="utf-8")
        group = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만 지질도", group=group, upstream="kigam")
        self.settings = override_settings(OFFLINE_BOXES_FILE=self.boxes, OFFLINE_DIR=str(root / "offline"),
                                          TILE_CACHE_DIR=str(root / "tiles"), VWORLD_KEY="SECRET-VW", KIGAM_KEY="SECRET-KG")
        self.settings.enable()
        self.kigam_calls = []
        patches = [
            mock.patch.object(build_offline_pack.KigamSource, "fetch", lambda s, z, x, y: self.kigam_calls.append(z) or png()),
            # 바다처럼 자료 밖(투명)도 하나 섞는다 — 넣지 않아야 한다
            mock.patch.object(vworld, "get_wmts_tile", lambda layer, z, y, x: None if (x + y) % 5 == 0 else (b"\x89PNG-vw" * 100, "image/png")),
            mock.patch.object(kigam, "has_key", lambda: True),
            mock.patch.object(build_offline_pack.time, "sleep", lambda s: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.settings.disable()
        self.tmp.cleanup()

    def build(self, *args):
        out = io.StringIO()
        call_command("build_offline_pack", "tiny", *args, stdout=out, stderr=io.StringIO())
        return out.getvalue()

    def test_굽고_다시_읽기(self):
        self.build()
        packs = list(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        self.assertEqual(len(packs), 1)
        head, _ = offlinepack.read_header(packs[0])
        self.assertEqual(head["layers"]["L_50K_Geology_Map"]["zooms"], [9, 11])     # 512 px 격자 — 화면 줌보다 하나 작다
        self.assertEqual(head["layers"]["L_50K_Geology_Map"]["tile_size"], 512)
        self.assertEqual(head["layers"]["vworld:Base"]["zooms"], [10, 12])
        self.assertEqual(head["dropped"], {})
        key = next(k for k in head["tiles"] if k.startswith("L_50K_Geology_Map/11/"))
        self.assertEqual(offlinepack.read_tile(packs[0], key), png())
        # 자료 밖의 VWorld 칸은 넣지 않는다
        for k in head["tiles"]:
            if k.startswith("vworld:Base/"):
                z, x, y = (int(v) for v in k.split("/")[1:])
                self.assertNotEqual((x + y) % 5, 0)
        # 다 구우면 받다 둔 VWorld 를 지운다
        self.assertEqual(list(Path(settings.OFFLINE_DIR).glob(".*parts*")), [])

    def test_머리에_키가_없다(self):
        self.build()
        raw = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack")).read_bytes()
        self.assertNotIn(b"SECRET", raw)

    def test_어림만(self):
        text = self.build("--dry-run")
        self.assertIn("어림", text)
        self.assertEqual(self.kigam_calls, [])
        self.assertFalse(Path(settings.OFFLINE_DIR).exists() and any(Path(settings.OFFLINE_DIR).iterdir()))

    def test_예산을_넘으면_뒤의_레이어부터_줌을_던다(self):
        BOX_SMALL = json.loads(json.dumps(BOX))
        BOX_SMALL["tiny"]["budget_mb"] = 0.05           # 50 KB 남짓 — 줌을 덜어야 한다
        self.boxes.write_text(json.dumps(BOX_SMALL), encoding="utf-8")
        self.build()
        head, _ = offlinepack.read_header(next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack")))
        self.assertIn("vworld:Base", head["dropped"])                     # 뒤의 것(VWorld)부터
        self.assertLess(head["layers"]["vworld:Base"]["zooms"][1], 12)


class FitBudget(SimpleTestCase):
    def test_차례(self):
        zooms, dropped, total = build_offline_pack.fit_budget(
            ["a", "b"], {"a": [5, 8], "b": [5, 8]}, lambda n, z: 4 ** (z - 5), 30)
        self.assertEqual(zooms, {"a": [5, 7], "b": [5, 5]})             # b 를 처음 줌까지 내린 뒤에야 a 를 던다
        self.assertEqual(dropped, {"b": 6, "a": 8})
        self.assertLessEqual(total, 30)

    def test_빈_타일(self):
        self.assertTrue(build_offline_pack.is_blank(png(alpha=0)))
        self.assertFalse(build_offline_pack.is_blank(png()))
        self.assertFalse(build_offline_pack.is_blank(b"\xff\xd8 jpeg"))


class Page(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        offlinepack.write(Path(self.tmp.name) / "jangseong-20261010.gsmpack",
                          {"box": "jangseong", "title": "장성 도폭 (태백)", "built": "2026-10-10", "bbox": [129, 37, 129.25, 37.17]},
                          [("L/1/0/0", b"abc")])

    def test_목록과_내려받기(self):
        with override_settings(OFFLINE_DIR=self.tmp.name, PUBLIC=False):
            page = self.client.get("/GSM/offline/")
            self.assertContains(page, "장성 도폭 (태백)")
            self.assertEqual(self.client.get("/GSM/offline/?format=json").json()["packs"][0]["tiles"], 1)
            got = self.client.get("/GSM/offline/jangseong-20261010.gsmpack")
            self.assertEqual(got.status_code, 200)
            self.assertTrue(b"".join(got.streaming_content).startswith(b"GSMPACK1"))
            got.close()
            self.assertEqual(self.client.get("/GSM/offline/nope-20261010.gsmpack").status_code, 404)

    def test_밖에_연_판에서는_닫는다(self):
        with override_settings(OFFLINE_DIR=self.tmp.name, PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/offline/").status_code, 404)
            self.assertEqual(self.client.get("/GSM/offline/jangseong-20261010.gsmpack").status_code, 404)
