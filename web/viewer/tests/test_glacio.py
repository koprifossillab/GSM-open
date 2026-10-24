"""빙저호(Livingstone 2022)·RAISED 접지선 (wetherilli 420) — 엑셀·셰이프 읽기, 점 레이어, 카탈로그. 상류는 부르지 않는다."""
import io
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from viewer import geomap, i18n, orda, raised, views
from viewer.models import Layer

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def xlsx(sheets: dict) -> bytes:
    """{시트 이름: 행 목록} → 아주 작은 xlsx. 글은 공유 문자열로, 수는 그대로 적는다 — 엑셀이 적는 꼴과 같다."""
    shared, buf = [], io.BytesIO()

    def cell(ref, value):
        if isinstance(value, (int, float)):
            return f'<c r="{ref}"><v>{value}</v></c>'
        shared.append(value)
        return f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>'

    with zipfile.ZipFile(buf, "w") as z:
        entries, rels = [], []
        for i, (name, rows) in enumerate(sheets.items(), start=1):
            body = "".join(f'<row r="{r}">' + "".join(cell(f"{chr(65 + c)}{r}", v) for c, v in enumerate(row) if v is not None)
                           + "</row>" for r, row in enumerate(rows, start=1))
            z.writestr(f"xl/worksheets/sheet{i}.xml", f'<worksheet xmlns="{_MAIN}"><sheetData>{body}</sheetData></worksheet>')
            entries.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="x" Target="worksheets/sheet{i}.xml"/>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{_MAIN}" xmlns:r="{_RELS}"><sheets>{"".join(entries)}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{_MAIN}">' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
    return buf.getvalue()


#: 시트마다 머리줄이 다르다 — 남극은 `Name`, 그린란드는 `Name / Location` 이고 열 차례도 다르다
BOOK = {
    "README": [["Lake fill-drain patterns"]],
    "Antarctica": [
        ["Tally", "Name", "Lat.  oN", "Lon. oE", "Area km2", "Ice thickness m", "Lake Type", "Method of identification", "References"],
        [1, "Lake Vostok", -78.15, 104.5, 14000, 3945, "Stable", "RES", "Oswald and Robin (1973)"],
        [2, "Lake Whillans", -84.24, 206.8, 60, None, "Active", "Ice surface elevation change", "Fricker et al. (2007)"],
        [3, "SPRI-3", -76.57, 124.8, None, 3621, None, "RES", None],
        [4, "좌표 없음", None, None],
    ],
    "Greenland": [
        ["Tally", "Name / Location", "Lat. oN", "Lon. oE", "Area km2", "Ice thickness m", "Lake Type", "Notes", "Method of identification", "References"],
        [1, "L2", 78.005, -68.394, 10, "803 - 815", "Stable", None, "RES", "Palmer et al. (2013)"],
    ],
}


def polyline_shp(lines) -> bytes:
    """선(3) 셰이프파일 — 행마다 한 부분."""
    records = b""
    for n, line in enumerate(lines, start=1):
        xs, ys = [p[0] for p in line], [p[1] for p in line]
        content = struct.pack("<i4d2i", 3, min(xs), min(ys), max(xs), max(ys), 1, len(line)) + struct.pack("<i", 0)
        content += b"".join(struct.pack("<2d", *p) for p in line)
        records += struct.pack(">2i", n, len(content) // 2) + content
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(records)) // 2) + struct.pack("<2i", 1000, 3) + b"\0" * 64
    return head + records


def dbf(rows, fields) -> bytes:
    """글 열만 있는 dBASE III 표."""
    width = {f: max(len(f), *(len(r[f]) for r in rows)) for f in fields}
    head_len, rec_len = 32 + 32 * len(fields) + 1, 1 + sum(width.values())
    out = struct.pack("<B3BIHH20x", 3, 126, 10, 23, len(rows), head_len, rec_len)
    for f in fields:
        out += f.encode().ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([width[f], 0]) + b"\0" * 14
    out += b"\r"
    for r in rows:
        out += b" " + b"".join(r[f].encode().ljust(width[f]) for f in fields)
    return out + b"\x1a"


PRJ = b'PROJCS["WGS_1984_Antarctic_Polar_Stereographic",PROJECTION["Stereographic_South_Pole"]]'


def raised_parts() -> dict:
    a = [geomap.lonlat_to_3031(-60, -70), geomap.lonlat_to_3031(-55, -71)]
    b = [geomap.lonlat_to_3031(170, -76), geomap.lonlat_to_3031(175, -77), geomap.lonlat_to_3031(180, -78)]
    c = [geomap.lonlat_to_3031(100, -66), geomap.lonlat_to_3031(110, -66)]
    rows = [{"Confidence": "Measured", "ScenarioA": "Y", "ScenarioB": "Y", "Age": "20ka"},
            {"Confidence": "Speculative", "ScenarioA": "N", "ScenarioB": "Y", "Age": "20ka"},
            {"Confidence": "Inferred", "ScenarioA": "Y", "ScenarioB": "N", "Age": "5ka"}]
    return {".shp": polyline_shp([a, b, c]), ".dbf": dbf(rows, ("Confidence", "ScenarioA", "ScenarioB", "Age")), ".prj": PRJ}


class Reading(SimpleTestCase):
    def test_엑셀을_openpyxl_없이_읽는다(self):
        sheets = orda.read_xlsx(xlsx(BOOK))
        self.assertEqual(list(sheets), ["README", "Antarctica", "Greenland"])
        self.assertEqual(sheets["Antarctica"][1][1], "Lake Vostok")

    def test_시트마다_머리줄로_열을_찾는다(self):
        lakes = orda.parse(xlsx(BOOK))
        self.assertEqual([l["name"] for l in lakes], ["Lake Vostok", "Lake Whillans", "SPRI-3", "L2"])  # 좌표 없는 줄은 뺀다
        vostok, whillans, spri, l2 = lakes
        self.assertEqual((vostok["kind"], vostok["method"], vostok["area"]), ("stable", "RES", "14000"))
        self.assertEqual(whillans["lon"], -153.2)                      # 동경 206.8° 는 서경으로
        self.assertEqual(spri["kind"], "unknown")
        self.assertEqual((l2["region"], l2["ice"], l2["refs"]), ("Greenland", "803 - 815", "Palmer et al. (2013)"))

    def test_시트가_없으면_멈춘다(self):
        with self.assertRaises(orda.OrdaError):
            orda.parse(xlsx({"Antarctica": BOOK["Antarctica"]}))

    def test_접지선을_위경도로(self):
        doc = raised.convert(raised_parts())
        self.assertEqual([l["age"] for l in doc["lines"]], ["20", "20", "5"])
        lon, lat = doc["lines"][0]["coords"][0]
        self.assertAlmostEqual(lon, -60, places=3)
        self.assertAlmostEqual(lat, -70, places=3)
        self.assertEqual((doc["lines"][1]["a"], doc["lines"][1]["b"]), (False, True))

    def test_다른_투영이면_멈춘다(self):
        with self.assertRaises(raised.RaisedError):
            raised.convert({**raised_parts(), ".prj": b'GEOGCS["GCS_WGS_1984"]'})


class Fetched(SimpleTestCase):
    """받아 둔 파일이 있을 때 — 받기는 figshare 두 번을 흉내 낸다."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.override = override_settings(GLACIO_DIR=cls.tmp.name)
        cls.override.enable()
        meta = {"modified_date": "2025-02-25T08:19:14Z", "license": {"name": "CC BY 4.0"},
                "files": [{"name": "a.zip", "download_url": "https://x/zip"}, {"name": "a.xlsx", "download_url": "https://x/xlsx"}]}
        responses = [mock.Mock(status_code=200, json=lambda: meta, content=b"{}"),
                     mock.Mock(status_code=200, content=xlsx(BOOK))]
        with mock.patch.object(orda.requests, "get", side_effect=responses) as get, \
                mock.patch.object(orda.time, "sleep") as sleep:
            cls.got = orda.download(orda.path())
        cls.calls = [c.args[0] for c in get.call_args_list]
        cls.slept = sleep.call_count
        raised.build(raised_parts(), raised.path())

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_목록을_보고_엑셀만_받는다(self):
        self.assertEqual(self.calls, [orda.API, "https://x/xlsx"])
        self.assertEqual(self.slept, 1)
        self.assertEqual(self.got, {"Antarctica": 3, "Greenland": 1})
        doc = json.loads(orda.path().read_text(encoding="utf-8"))
        self.assertEqual((doc["version"], doc["license"]), ("2025-02-25", "CC BY 4.0"))

    def test_빙저호_점_레이어(self):
        r = self.client.get("/GSM/points/", {"layer": "orda:lakes_antarctica"}, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual([f["properties"]["name"] for f in data["features"]], ["Lake Vostok", "Lake Whillans", "SPRI-3"])
        self.assertEqual(data["features"][1]["properties"]["kind"], "Active subglacial lake (fills and drains)")
        self.assertEqual([row["code"] for row in data["legend"]], ["active", "stable", "unknown"])
        for label in data["labels"].values():
            self.assertIn(label, i18n.PROP_EN)
        greenland = json.loads(self.client.get("/GSM/points/", {"layer": "orda:lakes_greenland"}).content)
        self.assertEqual(len(greenland["features"]), 1)

    def test_접지선_레이어는_연대마다(self):
        data = json.loads(self.client.get("/GSM/points/", {"layer": "raised:20ka"}).content)
        self.assertEqual(len(data["features"]), 2)
        self.assertEqual(data["features"][1]["properties"]["scenario"], "B 만")
        self.assertEqual({row["code"]: row.get("dash") for row in data["legend"]}, {"Measured": None, "Speculative": [2, 4]})
        self.assertEqual({row["color"] for row in data["legend"]}, {raised.COLORS["20"]})
        five = json.loads(self.client.get("/GSM/points/", {"layer": "raised:5ka"}).content)
        self.assertEqual(five["features"][0]["properties"]["scenario"], "A 만")

    def test_카탈로그는_점으로_판을_붙여(self):
        for name, upstream in (("orda:lakes_greenland", "orda"), ("raised:10ka", "raised")):
            spec = views._point_fields(Layer(name=name, upstream=upstream))
            self.assertEqual((spec["kind"], spec["style"]), ("points", "class"))
            self.assertTrue(spec["version"])
            self.assertTrue(spec["attribution"])


class NotFetched(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(GLACIO_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_503_으로_까닭을_말한다(self):
        for layer, command in (("orda:lakes_antarctica", "fetch_subglacial_lakes"), ("raised:15ka", "build_raised")):
            r = self.client.get("/GSM/points/", {"layer": layer})
            self.assertEqual(r.status_code, 503)
            self.assertIn(command, r.json()["error"])


class Seed(SimpleTestCase):
    def test_씨앗에_영어가_있다(self):
        for path in settings.GLACIO_CATALOG_SEEDS:
            seed = json.loads(Path(path).read_text(encoding="utf-8"))
            module = {"orda": orda, "raised": raised}[seed["_상류"]]
            for name in seed["레이어군순서"]:
                self.assertIn(name, i18n.GROUP_EN)
            for layer in seed["레이어"]:
                self.assertTrue(module.knows(layer["name"]))
                self.assertIn(layer["name"], i18n.LAYER_EN)
                self.assertIn(layer["name"], i18n.ABSTRACT_EN)
        self.assertEqual({json.loads(Path(p).read_text(encoding="utf-8"))["_지역"] for p in settings.GLACIO_CATALOG_SEEDS},
                         {"antarctica", "greenland"})
