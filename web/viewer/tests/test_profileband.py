"""높이 그래프 밑의 지질 띠 (wetherilli 180). 상류를 부르지 않는다 — 우리 파일로 그리는 레이어만 띠가 선다.

GeoMAP·geo3al 은 그쪽 시험의 작은 파일을 빌려 짓고, 달·화성·수성은 `identify` 를 갈아 끼운다.
"""
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import crs, geo3al, geomap, marsmap, mercurymap, moonmap, profileband
from viewer.tests.test_geo3al import PRJ, write_dbf, write_shp
from viewer.tests.test_geo3al import square as lonlat_square
from viewer.tests.test_geomap import SX, SY, WithData


def runs(band):
    """띠 → 이어지는 단위 이름의 차례 (빈 자리는 None)."""
    out = []
    for k in band["band"]:
        label = None if k is None else band["units"][k]["label"]
        if not out or out[-1] != label:
            out.append(label)
    return out


class Geomap(WithData, SimpleTestCase):
    def line(self):
        # 세종기지 둘레를 동서로 — 큰 네모(화산암)의 구멍 안에 작은 네모(관입암)가 있다
        return [geomap.xy3031_to_lonlat(SX - 15000, SY), geomap.xy3031_to_lonlat(SX + 15000, SY)]

    def test_구멍과_섬을_차례로(self):
        got = profileband.band("geomap_simple_geology", self.line(), 121)
        names = runs(got)
        self.assertEqual([n is None for n in names], [True, False, True, False, True, False, True])
        self.assertEqual(names[1], names[5])                 # 구멍 양쪽은 같은 화산암
        self.assertNotEqual(names[1], names[3])
        self.assertEqual(len(got["band"]), 121)
        self.assertTrue(all(u["color"].startswith("#") and len(u["color"]) == 7 for u in got["units"]))

    def test_점은_높이_그래프와_같다(self):
        pts = crs.great_circle_points(self.line(), 50)
        with mock.patch.object(geomap, "units_along", return_value=[None] * len(pts)) as along:
            profileband.band("geomap_simple_geology", self.line(), 50)
        sent = along.call_args.args[1]
        self.assertEqual(sent[0], geomap.lonlat_to_3031(pts[0][0], pts[0][1]))
        self.assertEqual(len(sent), 50)

    def test_단층은_띠가_없다(self):
        self.assertFalse(profileband.knows("geomap_faults"))
        self.assertFalse(profileband.knows("geomap_quality"))


class Geo3al(SimpleTestCase):
    ROWS = [{"TYPE": "", "GLG": "JK", "GEN_GLG": "KJ"}, {"TYPE": "i", "GLG": "K", "GEN_GLG": "K"},
            {"TYPE": "", "GLG": "H2O", "GEN_GLG": "H2O"}, {"TYPE": "", "GLG": "PZu", "GEN_GLG": "Pzu"}]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / geo3al.DATASET
        root.mkdir()
        write_shp(root / "geo3al.shp", [[lonlat_square(100 + 2 * i, 30, 1)] for i in range(len(self.ROWS))])
        write_dbf(root / "geo3al.dbf", self.ROWS)
        (root / "geo3al.prj").write_text(PRJ, encoding="latin-1")
        geo3al._memo.clear()
        patch = override_settings(USGS_DIR=self.tmp.name)
        patch.enable()
        self.addCleanup(patch.disable)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(geo3al._memo.clear)

    def test_시대(self):
        got = profileband.band("geo3al:age", [(99.5, 30.5), (107.5, 30.5)], 161)
        self.assertEqual([n for n in runs(got) if n], ["쥐라기~백악기", "백악기", "고생대 후기"])   # 물은 비운다
        self.assertEqual(got["units"][0]["color"], geo3al.AGE_BY_CODE["KJ"][1])

    def test_암종과_영어(self):
        got = profileband.band("geo3al:rock", [(99.5, 30.5), (107.5, 30.5)], 161, "en")
        self.assertEqual([n for n in runs(got) if n], ["Intrusive igneous rock"])


class Bodies(SimpleTestCase):
    def test_달_원도(self):
        def identify(lon, lat):
            return {"unit": "Im", "name": "Mare Material", "color": "#f6b8bb"} if lon < 0 else None
        with mock.patch.object(moonmap, "identify", side_effect=identify):
            got = profileband.band("moon:orig-units", [(-10, 0), (10, 0)], 21)
        self.assertEqual(runs(got), ["Im · Mare Material", None])

    def test_화성과_수성(self):
        with mock.patch.object(marsmap, "identify", return_value={"unit": "HNu", "name": "", "color": "#c900db"}):
            self.assertEqual(runs(profileband.band("mars:orig-units", [(0, 0), (1, 0)], 8)), ["HNu"])
        with mock.patch.object(mercurymap, "identify",
                               return_value={"unit": "pi", "group": "intercrater plains material", "color": "#fead36"}):
            self.assertEqual(runs(profileband.band("mercury:units", [(0, 0), (1, 0)], 8)),
                             ["pi · Intercrater plains material"])


class Views(TestCase):
    def get(self, **params):
        return self.client.get(reverse("viewer:profile-band"), params)

    def test_상류뿐인_레이어는_띠가_없다(self):
        self.assertEqual(self.get(layer="L_250K_Geology_Map", line="127,37;128,37").status_code, 404)
        self.assertEqual(self.get(layer="egdi:GeologicUnitView_Age", line="2,48;3,48").status_code, 404)

    def test_밖에_열면_내부용은_404(self):
        with override_settings(PUBLIC=True):
            self.assertEqual(self.get(layer="geo3al:age", line="100,30;101,30").status_code, 404)

    def test_선이_없으면_400(self):
        self.assertEqual(self.get(layer="moon:orig-units", line="1,2").status_code, 400)

    def test_파일이_없으면_503(self):
        with override_settings(MOON_DIR=tempfile.mkdtemp(prefix="gsm-band-")):
            self.assertEqual(self.get(layer="moon:orig-units", line="0,0;1,0").status_code, 503)

    def test_띠(self):
        with mock.patch.object(moonmap, "available", return_value=True), \
                mock.patch.object(moonmap, "identify", return_value={"unit": "Ip", "name": "", "color": "#123456"}):
            data = self.get(layer="moon:orig-units", line="0,0;1,0", n=8).json()
        self.assertEqual(data["band"], [0] * 8)
        self.assertEqual(data["units"], [{"label": "Ip", "color": "#123456"}])

    def test_카탈로그가_띠를_알린다(self):
        from django.core.management import call_command
        import io
        call_command("seed_catalog", stdout=io.StringIO())
        rows = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        self.assertIs(rows["geomap_simple_geology"].get("band"), True)
        self.assertNotIn("band", rows["geomap_faults"])
        self.assertNotIn("band", rows.get("L_250K_Geology_Map", {}))


class EarthCrust(SimpleTestCase):
    """온 지구의 지각 두께 띠 (wetherilli 186) — 범례의 10 km 칸으로 묶는다"""

    def test_칸으로_묶는다(self):
        from viewer import crust
        with mock.patch.object(crust, "at", side_effect=lambda lon, lat: None if lon > 0.5 else 35.2):
            got = profileband.band("earth:crust", [(0, 0), (1, 0)], 11)
        self.assertEqual(runs(got), ["30–40 km", None])
        self.assertEqual(got["units"][0]["color"], crust.legend()[3]["color"])


class Pages(TestCase):
    """온 지구의 높이 그래프와 달·화성·수성의 "그리기가 멈췄다" 안내 (wetherilli 186)"""

    def test_온_지구에_높이_그래프(self):
        page = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertIn('id="profile"', page)
        self.assertIn("profile-band.js", page)

    def test_세_화면에_멈춤_안내(self):
        for name in ("moon", "mars", "mercury"):
            page = self.client.get(reverse(f"viewer:{name}")).content.decode()
            self.assertIn('id="render-failed"', page, name)
            self.assertIn('id="render-failed-flat"', page, name)
