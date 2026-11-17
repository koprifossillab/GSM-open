"""남극 접지선·빙붕·유역 MEaSUREs (wetherilli 460). 상류를 부르지 않는다 — 작은 gpkg·셰이프를 지어 굽는다."""
import io
import sqlite3
import struct
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import antbounds, geomap

PRJ = b'PROJCS["WGS_84_Antarctic_Polar_Stereographic",PROJECTION["Stereographic_South_Pole"]]'


def _dbf(fields, rows) -> bytes:
    width = 1 + sum(size for _, size in fields)
    head = struct.pack("<4xIHH20x", len(rows), 32 + 32 * len(fields) + 1, width)
    desc = b"".join(name.encode().ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([size]) + b"\0" * 15 for name, size in fields)
    body = b"".join(b" " + b"".join(str(row.get(name, "")).encode().ljust(size) for name, size in fields) for row in rows)
    return head + desc + b"\r" + body


def _shp(polygons) -> bytes:
    """다각형(5) 셰이프 — polygons 는 고리(평면 좌표) 하나씩"""
    recs = b""
    for i, ring in enumerate(polygons, 1):
        xy = b"".join(struct.pack("<2d", x, y) for x, y in ring)
        content = struct.pack("<i4d2i", 5, 0, 0, 0, 0, 1, len(ring)) + struct.pack("<i", 0) + xy
        recs += struct.pack(">2i", i, len(content) // 2) + content
    head = struct.pack(">i20xi", 9994, (100 + len(recs)) // 2) + struct.pack("<2i4d4d", 1000, 5, 0, 0, 0, 0, 0, 0, 0, 0)
    return head + recs


def _square(lon, lat, half=50000.0):
    x, y = geomap.lonlat_to_3031(lon, lat)
    return [(x - half, y - half), (x - half, y + half), (x + half, y + half), (x + half, y - half), (x - half, y - half)]


def _gpkg(path: Path):
    db = sqlite3.connect(path)
    db.execute("create table gpkg_contents (table_name text, data_type text)")
    db.execute("insert into gpkg_contents values ('gl', 'features')")
    db.execute("create table gl (fid integer, geom blob, Glac_Name text, Sensor text, Year integer, Date_1 text)")
    x, y = geomap.lonlat_to_3031(-100.0, -75.0)
    pts = [(x + k * 1000.0, y) for k in range(5)]
    wkb = struct.pack("<BII", 1, 5, 1) + struct.pack("<BII", 1, 2, len(pts)) + b"".join(struct.pack("<2d", *p) for p in pts)
    blob = b"GP\0\0" + struct.pack("<i", 3031) + wkb                 # envelope 없음
    db.execute("insert into gl values (1, ?, 'Pine Island', 'Sentinel-1', 2018, '2018-03-01')", (blob,))
    db.execute("insert into gl values (2, ?, 'Pine Island', 'ERS', 1996, '1996-01-01')", (blob,))
    db.commit()
    db.close()


class AntBounds(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        src = Path(self.tmp.name) / "src"
        src.mkdir()
        _gpkg(src / antbounds.INSAR)
        tables = {
            "shelves": ([("NAME", 30), ("Regions", 11)], [{"NAME": "Pine_Island", "Regions": "West"}]),
            "basins": ([("NAME", 30), ("Regions", 11), ("Subregions", 11), ("Asso_Shelf", 30)],
                       [{"NAME": "Thwaites", "Regions": "West", "Subregions": "G-H", "Asso_Shelf": "Thwaites"}]),
            "imbie": ([("NAME", 30), ("Regions", 11), ("Subregions", 11)], [{"NAME": "G-H", "Regions": "West", "Subregions": "G-H"}]),
            "gl2008": ([("NAME", 30)], [{"NAME": "Grounded"}]),
        }
        for key, (fields, rows) in tables.items():
            stem = antbounds.SHAPES[key]
            (src / f"{stem}.shp").write_bytes(_shp([_square(-100.0, -75.0)]))
            (src / f"{stem}.dbf").write_bytes(_dbf(fields, rows))
            (src / f"{stem}.prj").write_bytes(PRJ)
        self.patch = override_settings(GLACIO_DIR=self.tmp.name)
        self.patch.enable()
        call_command("build_antarctic_boundaries", str(src), stdout=io.StringIO())

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽고_낸다(self):
        self.assertTrue(antbounds.available())
        doc = self.client.get("/GSM/points/", {"layer": "antbounds:insar_gl"}).json()
        codes = sorted(f["properties"]["code"] for f in doc["features"])
        self.assertEqual(codes, ["p1990", "p2017"])                       # 1996 · 2018
        one = next(f for f in doc["features"] if f["properties"]["code"] == "p2017")
        self.assertEqual(one["geometry"]["type"], "MultiLineString")
        self.assertEqual((one["properties"]["glacier"], one["properties"]["sensor"]), ("Pine Island", "Sentinel-1"))
        shelves = self.client.get("/GSM/points/", {"layer": "antbounds:shelves"}).json()
        self.assertEqual((shelves["labelBy"], shelves["features"][0]["properties"]["name"]), ("name", "Pine Island"))
        basin = self.client.get("/GSM/points/", {"layer": "antbounds:basins"}, HTTP_COOKIE="gsm_lang=en").json()
        props = basin["features"][0]["properties"]
        self.assertEqual((props["code"], props["region"], props["shelf"]), ("West", "West Antarctica", "Thwaites"))
        gl = self.client.get("/GSM/points/", {"layer": "antbounds:gl2008"}).json()
        self.assertEqual(gl["features"][0]["geometry"]["type"], "LineString")

    def test_행과_없을_때(self):
        from viewer import views
        row = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}["antbounds:insar_gl"]
        self.assertEqual((row["kind"], row["style"]), ("points", "class"))
        self.assertTrue(row["version"])
        antbounds.path().unlink()
        self.assertEqual(self.client.get("/GSM/points/", {"layer": "antbounds:imbie"}).status_code, 503)
