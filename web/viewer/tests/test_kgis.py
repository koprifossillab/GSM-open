"""SCAR KGIS 킹조지섬 지형 DB — 받아 둔 셰이프 zip 을 한 덩이씩 (wetherilli 424).

진짜 zip(다 합쳐 6.5 MB) 대신 같은 꼴의 작은 셰이프를 지어 읽는다. 셰이프·dBASE 를 짓는 것은 카리브 시험의 것을 빌리고,
점 셰이프만 여기서 짓는다. 상류는 부르지 않는다 — 받기는 `requests.get` 을 갈아 끼운다.
"""
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import i18n, kgis
from viewer.tests.test_caribmap import _dbf, _shp

SEJONG = (-58.787, -62.223)


def _points(xys):
    recs = b""
    for i, (x, y) in enumerate(xys, 1):
        content = struct.pack("<i2d", 1, x, y)
        recs += struct.pack(">2i", i, len(content) // 2) + content
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(recs)) // 2) + struct.pack("<2i4d4d", 1000, 1, *[0] * 8)
    return head + recs


def _utf8(text):
    """KGIS 의 dBASE 는 UTF-8 이다 — 시험의 `_dbf` 가 latin-1 로 적으니 미리 비틀어 둔다"""
    return text.encode("utf-8").decode("latin-1")


def _square(x, y, d=0.0005):
    return [(x, y), (x, y + d), (x + d, y + d), (x + d, y), (x, y)]


#: 셰이프 → (갈래, 열, 행, 모양)
SHAPES = {
    "Contour_010": (3, [("ELEVATION", 10)], [{"ELEVATION": "50"}, {"ELEVATION": "70"}],
                    [[[(-58.79, -62.22), (-58.78, -62.21)]], [[(-58.80, -62.23), (-58.79, -62.22)]]]),
    "Coastline": (3, [("SURFACE", 10)], [{"SURFACE": "Ice"}, {"SURFACE": "Rock"}],
                  [[[(-58.9, -62.2), (-58.8, -62.2)]], [[(-58.8, -62.2), (-58.7, -62.25)]]]),
    "Station": (1, [("NAME", 60), ("JURISDICTI", 20), ("LO_CODE", 10), ("STATUS", 20)],
                [{"NAME": "King Sejong Station", "JURISDICTI": "Korea", "LO_CODE": "AGKSG", "STATUS": "Operational"},
                 {"NAME": _utf8("Estação Antartica Comandante Ferraz"), "JURISDICTI": "Brazil", "STATUS": "Unknown"}],
                [SEJONG, (-58.39, -62.08)]),
    "Building": (5, [("JURISDICTI", 20), ("BUILDING_P", 20), ("SCAR_GAZ_I", 11)],
                 [{"JURISDICTI": "South Korea", "BUILDING_P": "Living", "SCAR_GAZ_I": "***********"}],
                 [[_square(*SEJONG)]]),
    "Protected": (5, [("PA_TYPE", 4), ("ATN", 4), ("DESCRIPTIO", 80), ("DATE_ESTAB", 8)],
                  [{"PA_TYPE": "ASPA", "ATN": "171", "DESCRIPTIO": "Narebski Point", "DATE_ESTAB": "20090101"}],
                  [[_square(-58.78, -62.24, 0.01)]]),
}


def write(root: Path, stems=None):
    for stem in stems or kgis.FILES:
        kind, fields, rows, shapes = SHAPES.get(stem, (1, [("NAME", 10)], [], []))
        shp = _points(shapes) if kind == 1 else _shp(kind, shapes) if shapes else _points([])
        with zipfile.ZipFile(root / f"{stem}.zip", "w") as zf:
            zf.writestr(f"{stem}/{stem}.shp", shp)
            zf.writestr(f"{stem}/{stem}.dbf", _dbf(fields, rows))


class Read(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        write(self.root)
        o = override_settings(KGIS_DIR=str(self.root))
        o.enable()
        self.addCleanup(o.disable)
        kgis._cache.clear()

    def body(self, name):
        return json.loads(kgis.body(name))

    def test_등고선은_50_m_마다_주곡선(self):
        got = self.body("kgis:contours")
        self.assertEqual([f["properties"]["code"] for f in got["features"]], ["index", "contour"])
        self.assertEqual(got["features"][0]["properties"]["elevation"], "50 m")
        self.assertEqual([r["code"] for r in got["legend"]], ["index", "contour"])
        self.assertEqual(got["legend"][0]["shape"], "stroke")

    def test_해안선은_얼음과_암석을_가른다(self):
        self.assertEqual([f["properties"]["code"] for f in self.body("kgis:coastline")["features"]], ["ice", "rock"])

    def test_시설은_기지·건물을_한_덩이로_갈래의_번호를_덮지_않는다(self):
        got = self.body("kgis:facilities")
        by = {f["properties"]["code"]: f for f in got["features"] if f["properties"]["code"] != "station"}
        stations = [f["properties"] for f in got["features"] if f["properties"]["code"] == "station"]
        self.assertEqual(stations[0]["name"], "King Sejong Station")
        self.assertEqual(stations[0]["number"], "AGKSG")             # 기지 부호는 `code` 가 아니라 `number`
        self.assertEqual(stations[1]["name"], "Estação Antartica Comandante Ferraz")   # UTF-8 로 되돌린다
        self.assertNotIn("status", stations[1])                       # Unknown 은 적지 않는다
        self.assertEqual(by["building"]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(by["building"]["properties"], {"code": "building", "jurisdiction": "South Korea", "use": "Living"})
        self.assertEqual({r["code"] for r in got["legend"]}, {"building", "station"})

    def test_보호구역은_번호와_지정일(self):
        props = self.body("kgis:protected")["features"][0]["properties"]
        self.assertEqual((props["code"], props["number"], props["established"], props["name"]),
                         ("aspa", "ASPA 171", "2009-01-01", "Narebski Point"))

    def test_팝업과_범례의_이름은_영어가_있다(self):
        self.assertEqual([v for v in kgis.LABELS.values() if v not in i18n.PROP_EN], [])
        self.assertEqual([str(c[0]) for c in kgis.CLASSES.values() if str(c[0]) not in i18n.EN], [])

    def test_파일이_바뀌면_다시_읽고_깨지면_멈춘다(self):
        self.body("kgis:routes")
        held = kgis._cache["kgis:routes"]
        self.body("kgis:routes")
        self.assertIs(kgis._cache["kgis:routes"], held)
        (self.root / "Road.zip").write_bytes(b"not a zip")
        with self.assertRaises(kgis.KgisError):
            self.body("kgis:routes")


class Download(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        o = override_settings(KGIS_DIR=str(self.root))
        o.enable()
        self.addCleanup(o.disable)
        for name, value in (("record", None), ("looks_blocked", False)):
            p = mock.patch.object(kgis.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_핸들을_차례로_풀어_받고_있는_것은_건너뛴다(self):
        (self.root / "Building.zip").write_bytes(b"PK old")
        answer = mock.Mock(status_code=200, content=b"PK\x03\x04zip", headers={"content-type": "application/zip"}, url="x")
        with mock.patch.object(kgis.requests, "get", return_value=answer) as get, mock.patch.object(kgis.time, "sleep"):
            got = kgis.download(log_line=lambda line: None)
        self.assertEqual((got["got"], got["skipped"]), (15, 1))
        self.assertEqual(get.call_args_list[0].args[0], "https://hdl.handle.net/10013/epic.44322.d002")    # Coastline
        self.assertEqual(get.call_args_list[-1].args[0], "https://hdl.handle.net/10013/epic.44322.d016")   # Waterstorage
        self.assertEqual((self.root / "Building.zip").read_bytes(), b"PK old")
        self.assertEqual((self.root / "Waterstorage.zip").read_bytes(), b"PK\x03\x04zip")

    def test_zip_이_아니면_멈추고_반쪽을_남기지_않는다(self):
        answer = mock.Mock(status_code=200, content=b"<html>", headers={"content-type": "text/html"}, url="x")
        with mock.patch.object(kgis.requests, "get", return_value=answer), self.assertRaises(kgis.KgisError):
            kgis.download(log_line=lambda line: None)
        self.assertEqual(list(self.root.iterdir()), [])


@override_settings(KGIS_DIR="/nonexistent/kgis")
class Route(TestCase):
    def test_파일이_없으면_503_으로_까닭을(self):
        r = self.client.get("/GSM/points/", {"layer": "kgis:facilities"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("KGIS", r.json()["error"])

    def test_있으면_한_덩이(self):
        root = Path(tempfile.mkdtemp())
        write(root)
        kgis._cache.clear()
        with override_settings(KGIS_DIR=str(root)):
            r = self.client.get("/GSM/points/", {"layer": "kgis:facilities"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["style"], "class")
        self.assertEqual(len(r.json()["features"]), 3)
