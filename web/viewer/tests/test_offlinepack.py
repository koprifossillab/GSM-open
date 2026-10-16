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
                                 "layers": {"L_50K_Geology_Map": [10, 12], "vworld:Base": [10, 12]},
                                 "units": ["L_50K_Geology_Map"], "budget_mb": 200}}

UNITS = {"features": [
    {"id": "l_50k_geology_litho_latest.7", "geometry": {"type": "MultiPolygon", "coordinates": [[[
        [129.0, 37.0], [129.05, 37.0], [129.05, 37.05], [129.0, 37.05], [129.0, 37.0]]]]},
     "properties": {"시대": "현생누대 고생대 캄브리아기", "지층": "풍촌석회암층", "기호": "CEp", "설명": None,
                    "도폭": '장성[1967]<a href="https://doi.org/10.22747/x">(수치지질도)</a>'}},
    {"id": "l_50k_geology_litho_latest.8", "geometry": {"type": "Polygon", "coordinates": [
        [[129.0123456789, 37.0], [129.02, 37.0], [129.02, 37.01], [129.0123456789, 37.0]]]},
     "properties": {"지층": "화절층", "기호": "CEw"}},
    {"id": "l_50k_geology_boundary_latest.1", "geometry": {"type": "MultiLineString", "coordinates": [[[129, 37], [129.1, 37]]]},
     "properties": {"유형": "지질경계"}}]}


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
        self.info_calls = []
        patches = [
            mock.patch.object(build_offline_pack.KigamSource, "fetch", lambda s, z, x, y: self.kigam_calls.append(z) or png()),
            # 바다처럼 자료 밖(투명)도 하나 섞는다 — 넣지 않아야 한다
            mock.patch.object(vworld, "get_wmts_tile", lambda layer, z, y, x: None if (x + y) % 5 == 0 else (b"\x89PNG-vw" * 100, "image/png")),
            mock.patch.object(kigam, "has_key", lambda: True),
            mock.patch.object(kigam, "describe_layer", lambda name: ["geoOpen:l_50k_geology_litho_latest",
                                                                      "geoOpen:l_50k_geology_fault_latest"]),
            mock.patch.object(kigam, "wfs_in_bbox", lambda t, bbox: self.info_calls.append((t, bbox)) or UNITS),
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
        # 작은 박스라 타일이 다 가장자리다 — 박스 밖은 비우고 안은 받은 그림 그대로 (wetherilli 385)
        image = Image.open(io.BytesIO(offlinepack.read_tile(packs[0], key))).convert("RGBA")
        self.assertIn((200, 100, 50, 255), [c for _, c in image.getcolors(512 * 512)])
        # 자료 밖의 VWorld 칸은 넣지 않는다
        for k in head["tiles"]:
            if k.startswith("vworld:Base/"):
                z, x, y = (int(v) for v in k.split("/")[1:])
                self.assertNotEqual((x + y) % 5, 0)
        # 다 구우면 받다 둔 VWorld 를 지운다
        self.assertEqual(list(Path(settings.OFFLINE_DIR).glob(".*parts*")), [])

    def test_지층_면을_담는다(self):
        """누른 자리의 속성은 박스 범위의 지층 면(WFS)으로 — 면만, 속성은 서버처럼 추려서 (wetherilli 384)"""
        self.build()
        path = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        head, base = offlinepack.read_header(path)
        units = head["units"]["L_50K_Geology_Map"]
        self.assertEqual(units["key"], "@units/L_50K_Geology_Map")
        self.assertEqual(units["types"], ["geoOpen:l_50k_geology_litho_latest"])          # 지층(litho)만 — 단층은 아니다
        self.assertEqual(self.info_calls, [("geoOpen:l_50k_geology_litho_latest", (129.0, 37.0, 129.05, 37.05))])
        shapes = json.loads(offlinepack.read_tile(path, units["key"], (head, base)))
        self.assertEqual(len(shapes["features"]), 2)                                       # 선은 버린다
        first = shapes["features"][0]["properties"]
        self.assertEqual(first["props"]["지층"], "풍촌석회암층")
        self.assertNotIn("설명", first["props"])                                            # 빈 값은 버린다
        self.assertEqual(first["props"]["도폭"]["links"][0]["url"], "https://doi.org/10.22747/x")   # 링크는 갈라 둔다
        self.assertIn("props_en", first)
        self.assertEqual(shapes["features"][1]["geometry"]["coordinates"][0][0], [129.01235, 37.0])   # 소수 다섯 자리

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
        path = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        _, base = offlinepack.read_header(path)
        self.assertLessEqual(path.stat().st_size - base, 0.05 * 1024 * 1024)   # 지층 면까지 쳐서 예산 안이다


class Clip(SimpleTestCase):
    """타일·지층 면을 박스로 잘라 낸다 — 도폭 하나를 구우면 묶음도 그 도폭만이다 (wetherilli 385)"""

    def test_타일(self):
        from viewer import tilegrid
        bbox = (129.0, 37.0, 129.25, 37.17)
        tile = png()
        # 도폭 안쪽의 깊은 타일은 그대로
        _, x, y = next(tilegrid.tiles_for((129.1, 37.1, 129.1, 37.1), 14))
        self.assertEqual(build_offline_pack.clip_tile(tile, 14, x, y, bbox), tile)
        # 박스 밖의 타일은 버린다
        _, x, y = next(tilegrid.tiles_for((127.0, 36.0, 127.0, 36.0), 14))
        self.assertEqual(build_offline_pack.clip_tile(tile, 14, x, y, bbox), b"")
        # 얕은 줌의 넓은 타일은 박스 밖이 투명하다
        _, x, y = next(tilegrid.tiles_for((129.1, 37.1, 129.1, 37.1), 7))
        image = Image.open(io.BytesIO(build_offline_pack.clip_tile(tile, 7, x, y, bbox))).convert("RGBA")
        alpha = image.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertLess(sum(1 for v in alpha.getdata() if v) / (512 * 512), 0.01)     # 2.8° 타일에 0.25° 도폭

    def test_지층_면(self):
        box = (129.0, 37.0, 129.1, 37.1)
        inside = {"type": "Polygon", "coordinates": [[[129.02, 37.02], [129.05, 37.02], [129.05, 37.05], [129.02, 37.02]]]}
        self.assertEqual(build_offline_pack.clip_polygons(inside, box)["coordinates"][0][0], [129.02, 37.02])
        across = {"type": "MultiPolygon", "coordinates": [
            [[[128.9, 37.05], [129.05, 37.05], [129.05, 37.2], [128.9, 37.2], [128.9, 37.05]]],
            [[[130.0, 38.0], [130.1, 38.0], [130.1, 38.1], [130.0, 38.0]]]]}             # 둘째 면은 다 밖
        got = build_offline_pack.clip_polygons(across, box)
        self.assertEqual(got["type"], "Polygon")
        xs = [p[0] for p in got["coordinates"][0]]
        ys = [p[1] for p in got["coordinates"][0]]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (129.0, 129.05, 37.05, 37.1))
        outside = {"type": "Polygon", "coordinates": [[[130.0, 38.0], [130.1, 38.0], [130.1, 38.1], [130.0, 38.0]]]}
        self.assertIsNone(build_offline_pack.clip_polygons(outside, box))


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
