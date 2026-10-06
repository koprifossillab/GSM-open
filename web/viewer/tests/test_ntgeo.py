"""노던테리토리 1:250만 지질도·단층 — 열린자료 셰이프 ZIP 을 한 덩이로 (wetherilli 361).

진짜 ZIP(4.4 MB) 대신 같은 꼴의 작은 셰이프를 지어 읽는다. 셰이프·dBASE 를 짓는 것은 카리브 시험의 것을 빌린다.
"""
import json
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import ntgeo
from viewer.tests.test_caribmap import _dbf, _shp

UNIT_FIELDS = [("SYMBOL", 30), ("GEOLREGION", 64), ("LITHCLASS", 30), ("EON", 20), ("ERA", 20), ("PERIOD", 20), ("AGERANGE", 20),
               ("STRAT_UNIT", 100), ("LITHDESCN1", 254)]
FAULT_FIELDS = [("NAME", 40), ("DEFZONE", 50), ("DERIVATION", 40), ("DATA", 50)]


def square(w, s, e, n):
    return [(w, s), (w, n), (e, n), (e, s), (w, s)]           # 바깥 고리는 시계 방향


def wiggly(w, s, e, n, steps=40):
    """꼭짓점이 많은 큰 네모 — 줄이면 넷만 남는다"""
    top = [(w + (e - w) * k / steps, n + 0.0001 * (k % 2)) for k in range(steps + 1)]
    return [(w, s), *top, (e, s), (w, s)]


def write(root: Path):
    units = [{"SYMBOL": "V6", "GEOLREGION": "Birrindudu Basin", "LITHCLASS": "Sedimentary", "EON": "Proterozoic", "ERA": "Palaeoproterozoic",
              "PERIOD": "Statherian", "AGERANGE": "1800 to 1700 Ma", "STRAT_UNIT": "Birrindudu Group", "LITHDESCN1": "Sandstone"},
             {"SYMBOL": "Qa", "LITHCLASS": "Sedimentary", "EON": "Phanerozoic", "ERA": "Cenozoic", "PERIOD": "Quaternary"},
             {"SYMBOL": "M7", "EON": "Proterozoic", "ERA": "Mesoproterozoic", "PERIOD": "Ectasian-Stenian"},
             {"SYMBOL": "sea", "GEOLREGION": "Arafura Sea"},
             {"SYMBOL": "x", "EON": "Proterozoic", "ERA": "Palaeoproterozoic"}]
    shapes = [[wiggly(130, -20, 132, -18)], [square(133, -15, 134, -14)], [square(135, -16, 135.001, -15.999)],
              [square(129, -11, 138, -10)], [square(136, -24, 137, -23), [(136.4, -23.6), (136.6, -23.6), (136.6, -23.4), (136.4, -23.4), (136.4, -23.6)]]]
    faults = [{"NAME": "Emu Fault", "DEFZONE": "Emu Fault Zone", "DERIVATION": "Generalised Mapping"},
              {"DERIVATION": "Interpreted", "DATA": "Geophysics"}]
    lines = [[[(130, -20), (131, -19)]], [[(132, -21), (132.5, -21.2), (133, -21)]]]
    for name, fields, rows, shp in (("GEO_INTERP_2500K", UNIT_FIELDS, units, _shp(5, shapes)),
                                    ("GEO_FAULTS_2500K", FAULT_FIELDS, faults, _shp(3, lines))):
        with zipfile.ZipFile(root / f"{name}_shp.zip", "w") as zf:
            zf.writestr(f"{name}.shp", shp)
            zf.writestr(f"{name}.dbf", _dbf(fields, rows))


class Read(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        write(self.root)
        o = override_settings(NTGEO_DIR=str(self.root))
        o.enable()
        self.addCleanup(o.disable)
        ntgeo._cache.clear()

    def body(self, name, lang="ko"):
        return json.loads(ntgeo.body(name, lang))

    def test_단위는_ICS_색과_한국어_시대로(self):
        got = self.body(ntgeo.UNITS)
        self.assertEqual(got["style"], "unit")
        props = [f["properties"] for f in got["features"]]
        self.assertEqual([p["symbol"] for p in props], ["V6", "Qa", "M7", "x"])       # 바다는 뺀다
        first = props[0]
        self.assertEqual((first["color"], first["age"], first["code"], first["name"]), ("#F875A7", "스타테로스기", "Statherian", "Birrindudu Group"))
        self.assertEqual(props[2]["color"], ntgeo.ICS["Ectasian"])          # 걸침은 앞의 기의 색
        self.assertEqual(props[3]["age"], "고원생대")                       # 기가 없으면 대
        self.assertEqual([r["code"] for r in got["legend"]], ["Quaternary", "Ectasian", "Statherian", "Palaeoproterozoic"])   # 젊은 것부터

    def test_영어판은_ICS_이름_그대로(self):
        got = self.body(ntgeo.UNITS, "en")
        self.assertEqual(got["features"][0]["properties"]["age"], "Statherian")
        self.assertEqual(got["legend"][0]["label"], "Quaternary")

    def test_줄이되_작은_단위와_구멍은_남긴다(self):
        feats = self.body(ntgeo.UNITS)["features"]
        big = feats[0]["geometry"]["coordinates"][0][0]
        self.assertLess(len(big), 10)                                       # 44 꼭짓점 → 넷 남짓
        tiny = feats[2]["geometry"]["coordinates"][0][0]
        self.assertEqual(len(tiny), 5)                                      # 0.001° 네모도 무너지지 않는다
        holed = feats[3]["geometry"]["coordinates"]
        self.assertEqual((len(holed), len(holed[0])), (1, 2))               # 바깥 고리 하나 + 구멍 하나

    def test_단층은_해석과_지도로(self):
        got = self.body(ntgeo.FAULTS)
        self.assertEqual(got["style"], "line")
        self.assertEqual([f["properties"]["code"] for f in got["features"]], ["mapped", "interp"])
        self.assertEqual(got["features"][0]["properties"]["zone"], "Emu Fault Zone")
        legend = {r["code"]: r for r in got["legend"]}
        self.assertIn("dash", legend["interp"])
        self.assertNotIn("dash", legend["mapped"])
        self.assertEqual(self.body(ntgeo.FAULTS, "en")["legend"][1]["label"], "Interpreted fault (geophysics)")

    def test_열_이름에_영어가_있다(self):
        from viewer import i18n
        self.assertEqual([k for k in ntgeo.LABELS.values() if k not in i18n.PROP_EN], [])

    def test_고친_ZIP_은_다시_읽는다(self):
        self.body(ntgeo.UNITS)
        held = ntgeo._cache[ntgeo.UNITS]
        self.body(ntgeo.UNITS)
        self.assertIs(ntgeo._cache[ntgeo.UNITS], held)
        (self.root / ntgeo.FILES[ntgeo.UNITS]).write_bytes(b"not a zip")
        with self.assertRaises(ntgeo.NtGeoError):
            self.body(ntgeo.UNITS)


@override_settings(NTGEO_DIR="/nonexistent/nt_geology")
class Route(TestCase):
    def test_파일이_없으면_503_으로_까닭을(self):
        r = self.client.get("/GSM/points/", {"layer": "ntgs:geology"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("NTGS", r.json()["error"])

    def test_있으면_한_덩이(self):
        root = Path(tempfile.mkdtemp())
        write(root)
        ntgeo._cache.clear()
        with override_settings(NTGEO_DIR=str(root)):
            r = self.client.get("/GSM/points/", {"layer": "ntgs:faults"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["features"]), 2)
