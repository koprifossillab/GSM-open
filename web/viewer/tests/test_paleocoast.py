"""옛 해안선 — PaleoCoastlines v7.1 (wetherilli 097).

원본(88 MB)을 쓰지 않고 셰이프파일을 손으로 지어 굽는다. 뭍 하나(시계 방향)와 그 안의 호수 하나(반시계).
"""
import hashlib
import io
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import paleocoast
from viewer.management.commands import build_paleocoastlines as build


def shp(rings) -> bytes:
    """면 셰이프파일 한 레코드(고리 여럿)."""
    pts = [p for ring in rings for p in ring]
    starts, n = [], 0
    for ring in rings:
        starts.append(n)
        n += len(ring)
    body = struct.pack("<i4d2i", 5, 0, 0, 0, 0, len(rings), len(pts)) + struct.pack(f"<{len(rings)}i", *starts)
    body += b"".join(struct.pack("<2d", *p) for p in pts)
    record = struct.pack(">2i", 1, len(body) // 2) + body
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(record)) // 2) + struct.pack("<2i4d4d", 1000, 5, -180, -90, 180, 90, 0, 0, 0, 0)
    return header + record


# 동경 0–40°·북위 0–40° 의 뭍(시계 방향), 그 가운데 호수(반시계)
LAND = [(0, 0), (0, 40), (40, 40), (40, 0), (0, 0)]
LAKE = [(15, 15), (25, 15), (25, 25), (15, 25), (15, 15)]


def archive(folder) -> Path:
    path = Path(folder) / "PaleoCoastlines_v7.1.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for age in (0, 250, 255):
            zf.writestr(f"Data/CS/{age}Ma_CS_v7.shp", shp([LAND, LAKE]))
        zf.writestr("Data/CM/250Ma_CM_v7.shp", shp([LAND]))           # 대륙 가장자리 — 읽지 않는다
    return path


class Build(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-coast-")
        self.zip = archive(self.dir)

    def test_뭍과_구멍을_가른다(self):
        out = Path(self.dir) / "c.json"
        with mock.patch.object(build, "SHA256", hashlib.sha256(self.zip.read_bytes()).hexdigest()):
            call_command("build_paleocoastlines", str(self.zip), out=str(out), stdout=io.StringIO())
        data = json.loads(out.read_text())
        self.assertEqual(sorted(data["rings"], key=float), ["0.0", "250.0", "255.0"])
        self.assertEqual((len(data["rings"]["250.0"]), len(data["holes"]["250.0"])), (1, 1))
        self.assertEqual(data["rings"]["250.0"][0][:4], [0, 0, 0, 40])

    def test_확인값이_다르면_멈춘다(self):
        with self.assertRaises(CommandError):
            call_command("build_paleocoastlines", str(self.zip), out=str(Path(self.dir) / "c.json"), stdout=io.StringIO())

    def test_잘린_변은_긋지_않는다(self):
        # 날짜변경선(경도 180°)을 따라 잘린 변과 남극점(위도 −90°)을 따라가는 변은 해안이 아니다
        ring = [170, 10, 180, 10, 180, -90, 170, -90]
        runs = paleocoast.coast_runs(ring)
        self.assertEqual(runs, [[(170, 10), (180, 10)], [(170, -90), (170, 10)]])


class Stops(SimpleTestCase):
    def test_가까운_시점_10_Myr_안에서만(self):
        with mock.patch.object(paleocoast, "ages", return_value=[0.0, 250.0, 535.0]):
            self.assertEqual(paleocoast.stop(253), 250.0)
            self.assertIsNone(paleocoast.stop(300))
            self.assertIsNone(paleocoast.stop(700))


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-coast-")
        zpath = archive(self.dir)
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-coast-t-"), EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        with mock.patch.object(build, "SHA256", hashlib.sha256(zpath.read_bytes()).hexdigest()):
            call_command("build_paleocoastlines", str(zpath), stdout=io.StringIO())

    def tile(self, age):
        url = reverse("viewer:earth-paleo-tile", kwargs={"style": "coast", "age": age, "z": 0, "x": 1, "y": 0})
        return self.client.get(url)

    def test_타일은_바다를_칠하고_뭍은_옅게(self):
        im = Image.open(io.BytesIO(self.tile(252).content)).convert("RGBA")
        sea, land, lake = im.getpixel((200, 200)), im.getpixel((10, 100)), im.getpixel((28, 100))
        self.assertEqual(sea[3], paleocoast.SEA[3])
        self.assertLess(land[3], 120)                  # 뭍은 옅게 — 밑의 판 조각이 비친다
        self.assertEqual(lake[3], paleocoast.SEA[3])   # 뭍 안의 호수는 다시 바다

    def test_시점이_없으면_빈_타일(self):
        im = Image.open(io.BytesIO(self.tile(400).content)).convert("RGBA")
        self.assertEqual(im.getextrema()[3], (0, 0))

    def test_화면에_시점을_싣는다(self):
        self.assertContains(self.client.get(reverse("viewer:earth")), '"coast": [0.0, 250.0, 255.0]')
