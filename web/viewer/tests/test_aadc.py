"""남극 특별보호구역 ASPA 2024 (wetherilli 423) — 파일마다 받기, 셰이프 읽기, 남극 탭의 한 덩이. 상류는 부르지 않는다."""
import json
import struct
import tempfile
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import aadc, geomap, i18n, views

PRJ = (b'PROJCS["WGS_1984_Antarctic_Polar_Stereographic",GEOGCS["GCS_WGS_1984"],PROJECTION["Stereographic_South_Pole"],'
       b'PARAMETER["Standard_Parallel_1",-71.0],UNIT["Meter",1.0]]')
FIELDS = ("ASPA_No", "NAME", "Propon", "DesigInstr", "Area_km", "PrimProtDe", "Marine", "ACBR")
ROWS = [
    {"ASPA_No": "171", "NAME": "Narebski Point, Barton Peninsula, KGI", "Propon": "Korea (ROK)", "DesigInstr": "Measure 13",
     "Area_km": "1.0382", "PrimProtDe": "C", "Marine": "0", "ACBR": "3"},
    {"ASPA_No": "179", "NAME": "Site A, Tanngarden, Western Sør Rondane", "Propon": "Belgium", "DesigInstr": "Measure 18 (2023)",
     "Area_km": "3.132", "PrimProtDe": "B", "Marine": "1", "ACBR": "NA"},
]


def dbf(rows, fields=FIELDS, width=60) -> bytes:
    """dBASE III — 글자 열만, UTF-8 로 적는다(ASPA 의 `.cpg`)"""
    head = struct.pack("<BBBBIHH20x", 3, 124, 1, 1, len(rows), 32 + 32 * len(fields) + 1, 1 + width * len(fields))
    desc = b"".join(struct.pack("<11sc4xB15x", f.encode(), b"C", width) for f in fields) + b"\r"
    body = b"".join(b" " + b"".join(r[f].encode("utf-8").ljust(width)[:width] for f in fields) for r in rows)
    return head + desc + body + b"\x1a"


def shp(kind: int, records: list) -> bytes:
    """셰이프파일 — 점(1)이면 [(x, y)], 다각형(5)이면 [[고리…]]"""
    out = b""
    for number, rec in enumerate(records, 1):
        if kind == 1:
            content = struct.pack("<i2d", 1, *rec)
        else:
            points = [p for ring in rec for p in ring]
            starts, at = [], 0
            for ring in rec:
                starts.append(at)
                at += len(ring)
            content = (struct.pack("<i4d2i", 5, 0, 0, 0, 0, len(rec), len(points)) + struct.pack(f"<{len(rec)}i", *starts)
                       + b"".join(struct.pack("<2d", *p) for p in points))
        out += struct.pack(">2i", number, len(content) // 2) + content
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(out)) // 2) + struct.pack("<2i4d4d", 1000, kind, 0, 0, 0, 0, 0, 0, 0, 0)
    return head + out


def square(lon, lat, size=200.0):
    """그 자리 둘레의 시계 방향 네모(3031 미터) — 셰이프파일의 바깥 고리"""
    x, y = geomap.lonlat_to_3031(lon, lat)
    return [[(x, y), (x, y + size), (x + size, y + size), (x + size, y), (x, y)]]


def files() -> dict:
    out = {"LICENSE": b"CC BY 4.0", "README": b"readme"}
    for stem, kind, recs in ((aadc.SHAPES["polygons"], 5, [square(-58.77, -62.238), square(22.94, -72.03)]),
                             (aadc.SHAPES["points"], 1, [geomap.lonlat_to_3031(-58.768, -62.234), geomap.lonlat_to_3031(22.94, -72.026)])):
        out.update({stem + ".shp": shp(kind, recs), stem + ".shx": b"", stem + ".dbf": dbf(ROWS),
                    stem + ".prj": PRJ, stem + ".cpg": b"UTF-8"})
    return out


class Read(SimpleTestCase):
    def test_면과_점을_위경도로_옮기고_글자를_UTF8_로(self):
        baked = aadc.convert(files())
        self.assertEqual(len(baked["polygons"]), 2)
        self.assertEqual(len(baked["points"]), 2)
        first = baked["polygons"][0]
        self.assertEqual(first["geometry"]["type"], "MultiPolygon")
        lon, lat = first["geometry"]["coordinates"][0][0][0]
        self.assertAlmostEqual(lon, -58.77, places=4)
        self.assertAlmostEqual(lat, -62.238, places=4)
        self.assertEqual(first["properties"], {"code": "land", "no": "171", "name": "Narebski Point, Barton Peninsula, KGI",
                                               "by": "Korea (ROK)", "measure": "Measure 13", "area": 1.0382, "acbr": "3"})
        second = baked["points"][1]["properties"]
        self.assertEqual(second["name"], "Site A, Tanngarden, Western Sør Rondane")
        self.assertEqual((second["code"], second["marine"]), ("marine", "예"))
        self.assertNotIn("acbr", second)                     # "NA" 는 싣지 않는다
        self.assertNotIn("PrimProtDe", json.dumps(baked))     # 뜻을 모르는 부호는 싣지 않는다

    def test_투영이나_글자가_다르면_멈춘다(self):
        broken = files()
        broken[aadc.SHAPES["points"] + ".prj"] = b'PROJCS["WGS 84 / UTM zone 21S"]'
        with self.assertRaises(aadc.AadcError):
            aadc.convert(broken)
        broken = files()
        broken[aadc.SHAPES["polygons"] + ".cpg"] = b"1252"
        with self.assertRaises(aadc.AadcError):
            aadc.convert(broken)

    def test_점_셰이프가_아니면_멈춘다(self):
        with self.assertRaises(aadc.AadcError):
            aadc.read_points(shp(5, [square(0, -70)]))


class Download(SimpleTestCase):
    def setUp(self):
        p = mock.patch.object(aadc.usage, "record")
        p.start()
        self.addCleanup(p.stop)

    def answer(self, status=200, content=b"\x00shape"):
        return mock.Mock(status_code=status, content=content, elapsed=None)

    def test_파일마다_이메일_없이_받고_사이에_쉰다(self):
        with mock.patch.object(aadc.requests, "get", return_value=self.answer()) as get, \
                mock.patch.object(aadc.time, "sleep") as slept:
            got = aadc.download()
        self.assertEqual(len(got), 2 * len(aadc.PARTS) + len(aadc.EXTRA))
        self.assertIn("ASPAs_polygons_v5_2024.dbf", got)
        url = get.call_args_list[0].args[0]
        self.assertTrue(url.startswith(f"{aadc.EDS}/{aadc.ASPA_UUID}/object/download?prefix="))
        self.assertIn("AAS_4296_Updated_ASPAs_2024%2FASPAs_polygons_v5_2024%2FASPAs_polygons_v5_2024.shp", url)
        self.assertNotIn("email", json.dumps([c.kwargs for c in get.call_args_list], default=str))
        self.assertEqual(slept.call_count, len(got) - 1)

    def test_화면이나_오류가_오면_멈춘다(self):
        for answer in (self.answer(content=b"<!DOCTYPE html><html>"), self.answer(status=404, content=b"no")):
            with mock.patch.object(aadc.requests, "get", return_value=answer), mock.patch.object(aadc.time, "sleep"), \
                    self.assertRaises(aadc.AadcError):
                aadc.download()


class Layer(SimpleTestCase):
    def test_없으면_까닭을_말한다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(AADC_DIR=tmp):
            r = self.client.get("/GSM/points/", {"layer": aadc.POLYGONS})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_aspa", r.json()["error"])

    def test_면과_점의_한_덩이(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(AADC_DIR=tmp):
            aadc.write(aadc.convert(files()))
            polygons = self.client.get("/GSM/points/", {"layer": aadc.POLYGONS}).json()
            self.client.cookies[i18n.COOKIE] = "en"
            points = self.client.get("/GSM/points/", {"layer": aadc.POINTS}).json()
        self.assertEqual(polygons["style"], "class")
        self.assertEqual([r["code"] for r in polygons["legend"]], ["land", "marine"])
        self.assertEqual(polygons["labels"]["no"], "ASPA 번호")
        self.assertEqual(polygons["features"][0]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(points["features"][1]["geometry"]["type"], "Point")
        self.assertEqual(points["features"][1]["properties"]["marine"], "yes")

    def test_영어가_있다(self):
        for label in list(aadc.LABELS.values()):
            self.assertIn(label, i18n.PROP_EN)
        for _, label, _, _ in aadc.CLASSES[1:]:
            self.assertIn(label, i18n.EN)
        for name in aadc.LAYERS:
            self.assertIn(name, i18n.LAYER_EN)
            self.assertIn(name, i18n.ABSTRACT_EN)

    def test_카탈로그는_점_레이어로(self):
        row = mock.Mock(upstream="aadc")
        row.name = aadc.POLYGONS
        spec = views._point_fields(row)
        self.assertEqual((spec["kind"], spec["style"], spec["license"]), ("points", "class", "CC BY 4.0"))
