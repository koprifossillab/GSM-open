"""카리브 — USGS 대앤틸리스 지질도(OFR 2019-1036 · SIM 3534)를 굽고 그린다 (wetherilli 254). 상류를 부르지 않는다 — 작은 셰이프를 지어 굽는다."""
import io
import struct
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from PIL import Image

from viewer import caribmap, crs


def _dbf(fields, rows):
    head = struct.pack("<BBBBIHH20x", 3, 126, 1, 1, len(rows), 32 + 32 * len(fields) + 1, 1 + sum(w for _, w in fields))
    desc = b"".join(struct.pack("<11sc4xB15x", n.encode(), b"C", w) for n, w in fields) + b"\r"
    body = b"".join(b" " + b"".join(str(r.get(n, "")).encode("latin-1").ljust(w)[:w] for n, w in fields) for r in rows)
    return head + desc + body + b"\x1a"


def _shp(kind, parts_list):
    """다각형(5)·선(3) 셰이프 — 레코드마다 부분 목록[(x, y)…]."""
    recs = b""
    for i, parts in enumerate(parts_list, 1):
        pts = [p for part in parts for p in part]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        starts, at = [], 0
        for part in parts:
            starts.append(at)
            at += len(part)
        content = struct.pack("<i4d2i", kind, min(xs), min(ys), max(xs), max(ys), len(parts), len(pts))
        content += struct.pack(f"<{len(parts)}i", *starts) + b"".join(struct.pack("<2d", *p) for p in pts)
        recs += struct.pack(">2i", i, len(content) // 2) + content
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(recs)) // 2) + struct.pack("<2i4d4d", 1000, kind, 0, 0, 0, 0, 0, 0, 0, 0)
    return head + recs


def _lcc(lon, lat):
    p = caribmap.LCC
    return crs.latlon_to_lcc(lat, lon, p["lon0"], p["lat1"], p["lat2"], p["lat0"], p["fe"], p["fn"])


def _ring(w, s, e, n):        # 바깥 고리는 시계 방향
    return [_lcc(w, s), _lcc(w, n), _lcc(e, n), _lcc(e, s), _lcc(w, s)]


class Build(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        z = root / "ofr.zip"
        polys = [[_ring(-66.6, 18.0, -66.2, 18.4)], [_ring(-66.9, 18.0, -66.7, 18.2)]]
        fields = [("GA_LABEL", 10), ("GA_UNITNAM", 60), ("AGE_RANGE", 40), ("GA_SYMBOL", 6), ("GACLASS", 6)]
        rows = [{"GA_LABEL": "Ksv", "GA_UNITNAM": "Older mixed rocks", "AGE_RANGE": "Cretaceous", "GA_SYMBOL": "20", "GACLASS": "300"},
                {"GA_LABEL": "", "GA_UNITNAM": "Water", "AGE_RANGE": "", "GA_SYMBOL": "300", "GACLASS": "102"}]
        arcs = [[[_lcc(-66.5, 18.1), _lcc(-66.3, 18.3)]], [[_lcc(-66.5, 18.3), _lcc(-66.3, 18.1)]]]
        arc_rows = [{"LINE_TYPE": "Thrust fault, location certain"}, {"LINE_TYPE": "Stratigraphic contact, location certain"}]
        descr = 'GA_label,Unit_name,GAclass,Age_range,Description,Lith_type\n"Ksv","Older mixed rocks","300","Cretaceous","' + "x " * 400 + '","Sedimentary"\n'
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("GAgeol_OFR/shapefiles/GAgeol_poly.shp", _shp(5, polys))
            zf.writestr("GAgeol_OFR/shapefiles/GAgeol_poly.dbf", _dbf(fields, rows))
            zf.writestr("GAgeol_OFR/shapefiles/GAgeol_arc.shp", _shp(3, arcs))
            zf.writestr("GAgeol_OFR/shapefiles/GAgeol_arc.dbf", _dbf([("LINE_TYPE", 60)], arc_rows))
            zf.writestr("GAgeol_OFR/supplemental_databases/CSV/GAdescrp.csv", descr.encode("cp1252"))
            zf.writestr("__MACOSX/GAgeol_OFR/shapefiles/._GAgeol_poly.shp", b"junk")
        cls.patch = override_settings(CARIBBEAN_DIR=str(root))
        cls.patch.enable()
        cls.counts = caribmap.build(z, caribmap.data_file())

    @classmethod
    def tearDownClass(cls):
        cls.patch.disable()
        cls.tmp.cleanup()
        super().tearDownClass()

    def test_물은_빼고_단층만(self):
        self.assertEqual(self.counts, {"units": 1, "faults": 1})          # 물 면·접촉선은 빠진다

    def test_누른_자리(self):
        unit = caribmap.identify(-66.4, 18.2)
        self.assertEqual((unit["label"], unit["color"], unit["lithology"]), ("Ksv", "#ffffde", "Sedimentary"))  # 기호 20 = 연노랑
        self.assertIsNone(caribmap.identify(-66.8, 18.1))                 # 물
        got = caribmap.friendly(unit)
        self.assertEqual(got["지질시대"], "백악기")
        self.assertTrue(got["설명"].endswith("…") and len(got["설명"]) <= caribmap.DESCR_MAX + 2)

    def test_타일과_범례(self):
        tile = Image.open(io.BytesIO(caribmap.render_tile("sim3534:units", 10, 323, 459))).convert("RGBA")
        self.assertGreater(sum(1 for p in tile.getdata() if p[3]), 1000)
        rows = caribmap.extent_legend(-67, 17.9, -66, 18.5)
        self.assertEqual([(r["symbol"], r["count"]) for r in rows], [("Ksv", 1)])

    def test_단층의_갈래(self):
        self.assertEqual(caribmap.fault_kind("Thrust fault, location certain, teeth on right"), "thrust")
        self.assertEqual(caribmap.fault_kind("Concealed fault of uncertain displacement"), "concealed")
        self.assertEqual(caribmap.fault_kind("Left lateral fault, location approximate"), "strike")
        self.assertIsNone(caribmap.fault_kind("Shoreline or riverbank"))

    def test_주소(self):
        from django.test import Client
        c = Client()
        r = c.get("/GSM/sim3534/units/10/323/459.png")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
        self.assertEqual(c.get("/GSM/sim3534/units/3/9/9.png").status_code, 404)
        d = c.get("/GSM/sim3534/info/", {"layer": "sim3534:units", "lat": 18.2, "lon": -66.4}).json()
        self.assertEqual(d["features"][0]["props"]["기호"], "Ksv")
        self.assertEqual(c.get("/GSM/sim3534/info/", {"layer": "sim3534:faults", "lat": 18.2, "lon": -66.4}).status_code, 400)
        rows = c.get("/GSM/sim3534/legend/", {"layer": "sim3534:units", "bbox": "-67,17.9,-66,18.5"}).json()["rows"]
        self.assertEqual(rows[0]["symbol"], "Ksv")
        self.assertEqual(c.get("/GSM/sim3534/legend/", {"layer": "sim3534:units", "bbox": "-85,10,-60,25"}).status_code, 422)
        self.assertEqual(len(c.get("/GSM/sim3534/legend/", {"layer": "sim3534:faults"}).json()["rows"]), 5)


class Missing(SimpleTestCase):
    def test_파일이_없어도_돈다(self):
        from django.test import Client
        with tempfile.TemporaryDirectory() as tmp, override_settings(CARIBBEAN_DIR=tmp):
            r = Client().get("/GSM/sim3534/units/10/323/459.png")
            self.assertEqual(r.status_code, 200)                       # 안내 타일
            self.assertEqual(Client().get("/GSM/sim3534/info/", {"layer": "sim3534:units", "lat": 18, "lon": -66}).status_code, 503)
