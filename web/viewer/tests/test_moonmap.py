"""달 지질도 원도 6 장 — 우리가 굽는 파일 (devlog 039).

원본(293 MB)을 시험에 들고 오지 않는다. 굽는 표와 같은 꼴의 작은 sqlite 를 손으로 만들어 굽기·읽기를
본다. 투영·경도 잇기·극 닫기·시대 옮기기는 함수째로 본다.
"""
import io
import math
import sqlite3
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import i18n, moonmap


def square(lon0, lat0, lon1, lat1):
    """시계 방향 바깥 고리(셰이프파일과 같다)의 납작한 좌표."""
    return [lon0, lat0, lon0, lat1, lon1, lat1, lon1, lat0, lon0, lat0]


def tiny_db(path, units, lines=()):
    """`units`: [(map, symbol, name, epoch, color, [[ring, …], …])]."""
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, map TEXT, draw INTEGER, symbol TEXT, name TEXT,
                            grp TEXT, epoch TEXT, descr TEXT, color TEXT, geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, map TEXT, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    draw = {m: i for i, m in enumerate(moonmap.MAPS)}
    for map_id, symbol, name, epoch, color, polygons in units:
        cur = db.execute("INSERT INTO units (map, draw, symbol, name, grp, epoch, descr, color, geom) "
                         "VALUES (?,?,?,?,?,?,?,?,?)",
                         (map_id, draw[map_id], symbol, name, "Dark Materials", epoch, f"{name}, {epoch}",
                          color, moonmap.pack(polygons)))
        db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox(polygons)))
    for map_id, kind, flat in lines:
        cur = db.execute("INSERT INTO lines (map, kind, geom) VALUES (?,?,?)", (map_id, kind, moonmap.pack([[flat]])))
        db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox([[flat]])))
    db.commit()
    db.close()


class Geometry(SimpleTestCase):

    def test_극_평사도법_극과_45도(self):
        lon, lat = moonmap.stereo_to_lonlat(0.0, 0.0, 1)
        self.assertAlmostEqual(lat, 90.0)
        # 극에서 축척 1 — 위도 45° 는 극에서 2R·tan(22.5°) 떨어진다
        rho = 2 * moonmap.R * math.tan(math.radians(22.5))
        lon, lat = moonmap.stereo_to_lonlat(0.0, -rho, 1)
        self.assertAlmostEqual(lat, 45.0, places=6)
        self.assertAlmostEqual(lon, 0.0, places=6)
        lon, lat = moonmap.stereo_to_lonlat(rho, 0.0, -1)
        self.assertAlmostEqual((lon, lat), (90.0, -45.0), places=6)

    def test_경도를_이어_적는다(self):
        flat = moonmap._unwrap([(179.0, 0.0), (-179.0, 0.0), (-178.0, 1.0)])
        self.assertEqual(flat[0::2], [179.0, 181.0, 182.0])

    def test_극을_두르는_고리는_극으로_닫는다(self):
        ring = [(lon, 80.0) for lon in range(-180, 181, 30)]
        flat = moonmap._unwrap(ring, pole=1)
        self.assertEqual(flat[-6:-2], [flat[-8], 90.0, -180.0, 90.0])
        self.assertEqual(flat[-2:], flat[:2])

    def test_꾸리고_풀기(self):
        polygons = [[square(0, 0, 1, 1), square(0.2, 0.2, 0.4, 0.4)]]
        back = moonmap.unpack(moonmap.pack(polygons))
        self.assertEqual(len(back), 1)
        self.assertEqual(len(back[0]), 2)
        self.assertEqual(list(back[0][0]), [float(v) for v in square(0, 0, 1, 1)])


class Epoch(SimpleTestCase):

    def test_낱말째_옮긴다(self):
        self.assertEqual(moonmap.epoch_ko("Imbrian System"), "임브리움계")
        self.assertEqual(moonmap.epoch_ko("Imbrian and Nectarian Systems"), "임브리움계·넥타리스계")
        self.assertEqual(moonmap.epoch_ko("Imbrian, Nectarian, and pre-Nectarian Systems"),
                         "임브리움계·넥타리스계·선넥타리스계")
        self.assertEqual(moonmap.epoch_ko("Eratosthenian or Imbrian System"), "에라토스테네스계 또는 임브리움계")
        self.assertEqual(moonmap.epoch_ko("Pre-Imbrian / Imbrian  System"), "선임브리움계 또는 임브리움계")

    def test_모르는_낱말은_그대로(self):
        self.assertEqual(moonmap.epoch_ko("Lower Imbrian Series"), "Lower Imbrian Series")
        self.assertEqual(moonmap.epoch_ko(""), "")


class Styles(SimpleTestCase):

    def test_색표는_29_갈래(self):
        s = moonmap.styles()
        self.assertEqual(len(s["categories"]), 29)
        self.assertIn("Lutz", s["about"])
        self.assertEqual(moonmap.unit_color("I-703", "Im"), "#f6b8bb")      # 바다 — I-703 은 표에 I-0703
        self.assertEqual(moonmap.unit_color("I-703", "없는기호"), "#9a9a9a")

    def test_구조선_모양(self):
        self.assertEqual(moonmap.line_style("Crest of basin ring structure, inferred")["ko"], "분지 고리 마루 (추정)")
        self.assertEqual(moonmap.line_style("Crest of basin ring structure")["ko"], "분지 고리 마루")
        self.assertEqual(moonmap.line_style("Buried crater rim crest")["ko"], "묻힌 크레이터 테")
        self.assertEqual(moonmap.line_style("Apollo 15 lunar altimetry")["ko"], "그 밖의 선")


class Read(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-moonmap-")
        patch = override_settings(MOON_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mm-cache-"))
        patch.enable()
        self.addCleanup(patch.disable)
        moonmap._local.__dict__.clear()
        self.addCleanup(moonmap._local.__dict__.clear)
        tiny_db(Path(self.dir) / moonmap.FILENAME, [
            ("I-703", "Im", "Mare Material", "Imbrian System", "#f6b8bb", [[square(-20, 10, -10, 30)]]),
            # 날짜 변경선을 가로지르는 뒷면 단위 — 경도를 이어 적어 170…190
            ("I-1047", "Nc", "Crater Material", "Nectarian System", "#97922e", [[square(170, -10, 190, 10)]]),
            # 극지 원도가 밑에, 앞면 원도가 위에 — 겹치는 곳은 앞면이 이긴다
            ("I-1062", "pNc", "Subdued Crater", "pre-Nectarian System", "#97922e", [[square(-30, 5, 0, 35)]]),
            # 남극을 두른 모자 — 경도 한 바퀴를 극으로 닫았다 (052)
            ("I-1162", "Ip", "Plains Material", "Imbrian System", "#123456",
             [[moonmap._unwrap([(lon, -88.0) for lon in range(-180, 181, 10)], pole=-1)]]),
        ], lines=[("I-1034", "Rille", [-100.0, 0.0, -90.0, 5.0])])

    def test_누른_자리의_단위(self):
        hit = moonmap.identify(-15, 20)
        self.assertEqual((hit["map"], hit["unit"]), ("I-703", "Im"))
        self.assertIn("Wilhelms & McCauley (1971)", hit["citation"])

    def test_날짜_변경선_너머(self):
        self.assertEqual(moonmap.identify(-175, 0)["unit"], "Nc")
        self.assertEqual(moonmap.identify(175, 0)["unit"], "Nc")

    def test_빈_자리(self):
        self.assertIsNone(moonmap.identify(100, -60))

    def test_타일을_굽는다(self):
        png = moonmap.render_tile("orig-units", 0, 0, 0)
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        # 경도 -15, 위도 20 → 서반구 한 장(180°·180°)의 가운데 근처
        x = int((-15 + 180) / 180 * 256)
        y = int((90 - 20) / 180 * 256)
        self.assertEqual(image.getpixel((x, y))[:3], (246, 184, 187))
        self.assertEqual(image.getpixel((5, 250))[3], 0)                 # 남쪽 끝은 비었다
        lines = Image.open(io.BytesIO(moonmap.render_tile("orig-lines", 0, 0, 0))).convert("RGBA")
        self.assertGreater(sum(1 for p in lines.getdata() if p[3]), 0)

    def test_극_타일을_굽는다(self):
        """극 평면(052) — 경위도로 옮겨 둔 모양을 극 평사도법으로 다시 옮긴다. 극을 두른 고리는 극점을 채운다."""
        image = Image.open(io.BytesIO(moonmap.render_polar_tile("orig-units", "s", 0, 0, 0))).convert("RGBA")
        self.assertEqual(image.getpixel((128, 128))[:3], (0x12, 0x34, 0x56))    # 남극점
        rho = 2 * moonmap.R * math.tan(math.radians(0.5))                       # 남위 89°
        px = 128 + rho / (2 * 1095930.0) * 256
        self.assertEqual(image.getpixel((int(px), 128))[:3], (0x12, 0x34, 0x56))
        self.assertEqual(image.getpixel((5, 5))[3], 0)                          # 모자 밖
        north = Image.open(io.BytesIO(moonmap.render_polar_tile("orig-units", "n", 0, 0, 0))).convert("RGBA")
        self.assertEqual(north.getpixel((128, 128))[3], 0)                      # 북극에는 없다

    def test_극_타일_경로(self):
        tile = self.client.get(reverse("viewer:moon-polar-tile", args=["s", "orig-units", 0, 0, 0]))
        self.assertEqual((tile.status_code, tile["X-GSM-Cache"]), (200, "miss"))
        again = self.client.get(reverse("viewer:moon-polar-tile", args=["s", "orig-units", 0, 0, 0]))
        self.assertEqual(again["X-GSM-Cache"], "hit")
        self.assertEqual(self.client.get("/GSM/moon/ptiles/s/orig-units/0/1/0.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/moon/ptiles/s/nope/0/0/0.png").status_code, 404)

    def test_경로(self):
        tile = self.client.get(reverse("viewer:moon-tile", args=["orig-units", 0, 0, 0]))
        self.assertEqual((tile.status_code, tile["X-GSM-Cache"]), (200, "miss"))
        self.assertEqual(self.client.get(reverse("viewer:moon-tile", args=["orig-units", 0, 0, 0]))["X-GSM-Cache"], "hit")
        ko = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20, "layer": "orig"}).json()
        self.assertIn(["시대", "임브리움계"], ko["rows"])
        self.assertEqual(ko["color"], "#f6b8bb")
        self.client.cookies[i18n.COOKIE] = "en"
        en = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20, "layer": "orig"}).json()
        self.assertIn(["Age", "Imbrian System"], en["rows"])
        self.assertIn(["Source map", "I-703 · Wilhelms & McCauley (1971)"], en["rows"])
        legend = self.client.get(reverse("viewer:moon-legend"), {"layer": "orig"}).json()
        self.assertEqual(len(legend["units"]), 29)
        self.assertEqual(legend["units"][0]["label"], "Crater material")


@override_settings(MOON_DIR="/nonexistent/gsm-moon")
class Missing(TestCase):

    def test_파일이_없으면_안내_타일과_안내(self):
        moonmap._local.__dict__.clear()
        tile = self.client.get(reverse("viewer:moon-tile", args=["orig-units", 0, 0, 0]))
        self.assertEqual((tile.status_code, tile["Cache-Control"]), (200, "no-store"))
        info = self.client.get(reverse("viewer:moon-info"), {"lon": 0, "lat": 0, "layer": "orig"}).json()
        self.assertEqual(info["rows"], [])
        self.assertTrue(info["note"])
