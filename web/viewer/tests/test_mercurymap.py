"""수성 지질도 — USGS 1:500만 도폭 합본을 우리가 굽는다 (wetherilli 144).

원본(9 MB)을 시험에 들고 오지 않는다. 합본과 같은 열·같은 꼴의 작은 셰이프파일을 손으로 만들어 굽고 그리고 읽는다.
"""
import io
import struct
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import mercurymap


def _shp(records, kind):
    """셰이프파일 하나 — `kind` 5(다각형)는 행마다 고리 목록, 3(선)은 행마다 선 목록. 고리·선은 [(경도, 위도), …]."""
    bodies = []
    for number, parts in enumerate(records, 1):
        points = [p for part in parts for p in part]
        starts, at = [], 0
        for part in parts:
            starts.append(at)
            at += len(part)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        content = struct.pack("<i4d2i", kind, min(xs), min(ys), max(xs), max(ys), len(parts), len(points))
        content += struct.pack(f"<{len(parts)}i", *starts)
        content += b"".join(struct.pack("<2d", *p) for p in points)
        bodies.append(struct.pack(">2i", number, len(content) // 2) + content)
    total = 100 + sum(len(b) for b in bodies)
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, total // 2) + struct.pack("<2i", 1000, kind)
    header += struct.pack("<8d", 0, 0, 0, 0, 0, 0, 0, 0)
    return header + b"".join(bodies)


def _dbf(fields, rows):
    width = 1 + sum(size for _, size in fields)
    header_len = 32 + 32 * len(fields) + 1
    out = struct.pack("<B3BIHH20x", 3, 99, 9, 28, len(rows), header_len, width)
    for name, size in fields:
        out += name.encode().ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([size, 0]) + b"\0" * 14
    out += b"\r"
    for row in rows:
        out += b" " + b"".join(str(row.get(name, "")).encode().ljust(size)[:size] for name, size in fields)
    return out + b"\x1a"


def box(w, s, e, n):
    """시계 방향으로 닫은 네모 — 셰이프파일의 바깥 고리."""
    return [(w, s), (w, n), (e, n), (e, s), (w, s)]


UNIT_FIELDS = [("DESCRIPTIO", 80), ("UGROUP", 40), ("GRASSRGB", 12), ("USYM", 12)]
LINE_FIELDS = [("CLASS", 40), ("CLASS_GLOB", 40)]


def tiny_zip(path):
    """평원 한 판(서경 40–20°) 안에 c4 크레이터 하나, 도폭 사이의 빈 곳 하나, 급사면·크레이터 테·분지 고리."""
    units = [
        ([box(-40, -10, -20, 10)], {"DESCRIPTIO": "Widespread throughout map area", "UGROUP": "SMOOTH PLAINS MATERIAL",
                                    "GRASSRGB": "254:180:185", "USYM": "ps"}),
        ([box(-32, -2, -28, 2)], {"DESCRIPTIO": "Material of craters with continuous, slightly subdued rim crest",
                                  "UGROUP": "CRATER MATERIALS", "GRASSRGB": "136:199:84", "USYM": "c4"}),
        ([box(-60, -10, -50, 10)], {"GRASSRGB": "255:0:0", "USYM": "No Coverage"}),
    ]
    structures = [([[(-39, 5), (-21, 5)]], {"CLASS": "Lobate scarp", "CLASS_GLOB": "Scarp"}),
                  ([[(-39, -5), (-21, -5)]], {"CLASS": "Crater rim crest", "CLASS_GLOB": "Crater rim"})]
    rings = [([[(-39, 8), (-21, 8)]], {"CLASS": "Multiring basin ring", "CLASS_GLOB": "Ring"})]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mercury_geology-1.0/mercury_g.shp", _shp([u[0] for u in units], 5))
        zf.writestr("mercury_geology-1.0/mercury_g.dbf", _dbf(UNIT_FIELDS, [u[1] for u in units]))
        for stem, rows in (("mercury_s", structures), ("mercury_m", rings)):
            zf.writestr(f"mercury_geology-1.0/{stem}.shp", _shp([r[0] for r in rows], 3))
            zf.writestr(f"mercury_geology-1.0/{stem}.dbf", _dbf(LINE_FIELDS, [r[1] for r in rows]))


class Reading(SimpleTestCase):

    def test_색은_합본의_RGB(self):
        self.assertEqual(mercurymap.rgb("254:180:185"), "#feb4b9")
        self.assertEqual(mercurymap.rgb(""), "#9a9a9a")

    def test_갈래는_무리_이름과_기호로(self):
        self.assertEqual(mercurymap.group_of("ps", "SMOOTH PLAINS MATERIAL"), "plains")
        self.assertEqual(mercurymap.group_of("c4", "CRATER MATERIALS"), "crater")
        self.assertEqual(mercurymap.group_of("cvs", "CALORIS GROUP, VAN EYCK FORMATION, SECONDARY CRATER FACIES"),
                         "basin")
        self.assertEqual(mercurymap.group_of("cm", "BASIN MATERIALS"), "basin")
        self.assertEqual(mercurymap.group_of("tr", "ROUGH TERRA MATERIAL"), "other")

    def test_도폭은_서경으로_나뉜다(self):
        self.assertEqual(mercurymap.quad_of(-31.5, -11.3), "H-6")        # 쿠이퍼 크레이터
        self.assertEqual(mercurymap.quad_of(-163.5, -16.3), "H-8")       # 톨스토이 분지
        self.assertEqual(mercurymap.quad_of(170.0, 30.0), "H-4")          # 칼로리스 둘레 — 서경 190°
        self.assertEqual(mercurymap.quad_of(-30.0, 40.0), "H-2")
        self.assertEqual(mercurymap.quad_of(-120.0, -40.0), "H-12")
        self.assertEqual(mercurymap.quad_of(0.0, 80.0), "H-1")
        self.assertEqual(mercurymap.quad_of(0.0, -80.0), "H-15")

    def test_크레이터_등급(self):
        self.assertEqual(mercurymap._crater_class("c4"), "4")
        self.assertEqual(mercurymap._crater_class("cp5"), "5")
        self.assertEqual(mercurymap._crater_class("sc3"), "3")
        self.assertEqual(mercurymap._crater_class("ps"), "")
        self.assertEqual(mercurymap._crater_class("cs"), "")


class Built(TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gsm-mercurymap-"))
        tiny_zip(self.dir / "merged.zip")
        patch = override_settings(MERCURY_DIR=str(self.dir), TILE_CACHE_DIR=str(self.dir / "tiles"))
        patch.enable()
        self.addCleanup(patch.disable)
        self.counts = mercurymap.build(self.dir / "merged.zip", mercurymap.data_file())

    def test_빈_곳과_크레이터_테는_뺀다(self):
        # 단위 셋 가운데 "No Coverage" 는 빠진다. 선 셋 가운데 크레이터 테는 빠진다
        self.assertEqual(self.counts, {"units": 2, "lines": 2})

    def test_작은_것이_위다(self):
        hit = mercurymap.identify(-30.0, 0.0)
        self.assertEqual((hit["unit"], hit["crater_class"], hit["color"]), ("c4", "4", "#88c754"))
        self.assertEqual((hit["map"], hit["quad"]), ("I-1233", "H-6 Kuiper"))
        self.assertEqual(mercurymap.identify(-38.0, 0.0)["unit"], "ps")
        self.assertIsNone(mercurymap.identify(-55.0, 0.0))

    def test_타일은_원도의_색으로(self):
        # 줌 3 — 한 장이 22.5°. 서경 45–22.5°·북위 0–22.5° 의 장(x=6, y=3)에 평원이 든다
        img = Image.open(io.BytesIO(mercurymap.render_tile("units", 3, 6, 3))).convert("RGBA")
        colors = {c for _, c in img.getcolors(1 << 16) if c[3] == 255}
        self.assertIn((254, 180, 185, 255), colors)
        empty = Image.open(io.BytesIO(mercurymap.render_tile("units", 3, 12, 3))).convert("RGBA")
        self.assertEqual(empty.getextrema()[3], (0, 0))

    def test_범례는_갈래로_묶는다(self):
        data = mercurymap.legend("ko")
        self.assertEqual([(u["unit"], u["group"]) for u in data["units"]], [("ps", "평원"), ("c4", "크레이터")])
        self.assertEqual(len(data["lines"]), len(mercurymap.LINE_STYLES))
        self.assertEqual(mercurymap.legend("en")["units"][0]["group"], "Plains")

    def test_뷰(self):
        url = reverse("viewer:mercury-tile", args=["units", 3, 6, 3])
        first = self.client.get(url)
        self.assertEqual(first["X-GSM-Cache"], "miss")
        self.assertEqual(self.client.get(url).content, first.content)
        self.assertEqual(self.client.get(reverse("viewer:mercury-tile", args=["craters", 0, 0, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:mercury-tile", args=["units", 11, 0, 0])).status_code, 404)
        data = self.client.get(reverse("viewer:mercury-info"), {"lon": -30, "lat": 0}).json()
        rows = dict(data["rows"])
        self.assertEqual(rows["단위"], "c4")
        self.assertEqual(rows["크레이터 등급"], "c4 — c1 가장 닳음, c5 가장 또렷함")
        self.assertTrue(rows["원도"].startswith("I-1233 (H-6 Kuiper)"))
        en = self.client.get(reverse("viewer:mercury-info"), {"lon": -30, "lat": 0},
                             HTTP_ACCEPT_LANGUAGE="en", cookies={}).json()
        self.assertIn("rows", en)
        none = self.client.get(reverse("viewer:mercury-info"), {"lon": 100, "lat": 0}).json()
        self.assertEqual(none["rows"], [])
        self.assertTrue(none["note"])
        self.assertEqual(len(self.client.get(reverse("viewer:mercury-legend")).json()["units"]), 2)


@override_settings(MERCURY_DIR="/nonexistent/gsm-mercury")
class Missing(TestCase):

    def test_파일이_없으면_안내(self):
        r = self.client.get(reverse("viewer:mercury-tile", args=["units", 0, 0, 0]))
        self.assertEqual(r.status_code, 200)
        data = self.client.get(reverse("viewer:mercury-info"), {"lon": -30, "lat": 0}).json()
        self.assertEqual(data["rows"], [])
        self.assertEqual(self.client.get(reverse("viewer:mercury-legend")).json()["units"], [])
