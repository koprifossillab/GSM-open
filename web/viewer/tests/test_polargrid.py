"""칠해 잘라 둔 남극 격자 — 틀(`polargrid`)과 중력 AntGG2021 (wetherilli 431). 상류를 부르지 않는다 — 작은 격자를 지어 굽는다."""
import io
import math
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import antgg, polargrid

N, RES = 41, 150000.0
HALF = (N - 1) / 2 * RES                                       # 가운데가 극


def grid() -> polargrid.Grid:
    """rows[j][i] 가 (xs[i], ys[j]). ys 는 남에서 북으로(AntGG 꼴). 위쪽 절반(y > 0)은 +120, 아래쪽은 −80, 맨 아래 줄 왼쪽 넷은 빈 곳"""
    xs = [-HALF + i * RES for i in range(N)]
    ys = [-HALF + j * RES for j in range(N)]
    rows = [[math.nan if j == 0 and i < 4 else (120.0 if ys[j] > 0 else -80.0) for i in range(N)] for j in range(N)]
    return polargrid.from_rows(rows, xs, ys)


class Shape(SimpleTestCase):
    def test_줄은_위에서_아래로(self):
        g = grid()
        self.assertEqual((g.ne, g.nv, g.res, g.x0, g.ytop), (N, N, RES, -HALF, HALF))
        self.assertEqual(g.values[0], 120.0)                         # 맨 위 줄
        self.assertTrue(math.isnan(g.values[(N - 1) * N]))           # 맨 아래 줄의 왼쪽 끝
        self.assertEqual(g.values[(N - 1) * N + 4], -80.0)

    def test_흩어진_점을_칸으로(self):
        pts = [(0.0, 0.0, 10.0), (20000.0, 0.0, 20.0), (500000.0, 500000.0, 30.0)]
        g = polargrid.rasterize(pts, 20000.0, radius=15000.0)
        self.assertEqual(g.res, 20000.0)
        filled = [v for v in g.values if v == v]
        self.assertEqual(sorted(filled), [10.0, 20.0, 30.0])        # 반지름 밖의 칸은 빈다

    def test_칠하기(self):
        index_of = polargrid.ramp_index(lambda v: v / 100, -1.0, 1.0)
        self.assertEqual((index_of(-1e6), index_of(0), index_of(1e6)), (1, 128, 255))
        classes = ((40, "#2b5fa8"), (60, "#3fa7c9"), (1e9, "#b0207a"))
        self.assertEqual([polargrid.class_index(classes)(v) for v in (10, 50, 999)], [1, 2, 3])
        pal = polargrid.class_palette(classes)
        self.assertEqual((len(pal), pal[3:6]), (768, (0x2b, 0x5f, 0xa8)))


class Bake(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = override_settings(ANTGG_DIR=self.tmp.name)
        self.patch.enable()
        self.spec = antgg.SETS["antgg:bouguer"]
        self.stats = polargrid.bake(self.spec, grid(), "test.nc", log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽고_누른다(self):
        self.assertEqual((self.stats["cells"], self.stats["min"], self.stats["max"]), (N * N - 4, -80, 120))
        self.assertTrue(self.spec.available())
        self.assertFalse(antgg.SETS["antgg:free_air"].available())
        self.assertEqual(polargrid.value_at(self.spec, -81.0, 0.0), 120)       # 3031 에서 경도 0° 가 위
        self.assertEqual(polargrid.value_at(self.spec, -81.0, 180.0), -80)
        self.assertIsNone(polargrid.value_at(self.spec, 10.0, 0.0))             # 격자 밖
        tile = Image.open(io.BytesIO(self.spec.read_tile(0, 0, 0))).convert("RGBA")
        self.assertGreater(sum(1 for p in tile.getdata() if p[3]), 10000)

    def test_주소(self):
        r = self.client.get("/GSM/polargrid/antgg/bouguer/0/0/0.webp")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/webp"))
        self.assertEqual(self.client.get("/GSM/polargrid/antgg/bouguer/9/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/polargrid/antgg/nothing/0/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/polargrid/antgg/free_air/0/0/0.webp").status_code, 200)   # 안내 타일
        got = self.client.get("/GSM/polargrid/info/", {"layer": "antgg:bouguer", "lat": -81, "lon": 0}).json()
        self.assertEqual(got["features"][0]["props"]["부게 이상 (mGal)"], "+120.0")
        en = self.client.get("/GSM/polargrid/info/", {"layer": "antgg:bouguer", "lat": -81, "lon": 180},
                             HTTP_COOKIE="gsm_lang=en").json()
        self.assertIn("−80.0", list(en["features"][0]["props"].values()))
        self.assertEqual(self.client.get("/GSM/polargrid/info/", {"layer": "antgg:bouguer", "lat": 10, "lon": 0}).json(),
                         {"features": []})
        self.assertEqual(self.client.get("/GSM/polargrid/info/", {"layer": "x", "lat": 1, "lon": 1}).status_code, 400)
        from viewer import views
        row = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}["antgg:bouguer"]
        self.assertEqual((row["projection"], row["maxZoom"]), ("EPSG:3031", antgg.MAX_ZOOM))
        self.assertTrue(row["tiles"].startswith("polargrid/antgg/bouguer/{z}/{x}/{y}.webp"))
        self.assertEqual(row["classLegend"]["groups"][0]["rows"][0]["label"], "≤ −300 mGal")

    def test_3D_로_편다(self):
        got = self.client.get("/GSM/warp/antgg/bouguer/2/1/3.png")              # 남극을 덮는 3857 칸
        self.assertEqual((got.status_code, got.content[:8]), (200, b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(self.client.get("/GSM/warp/antgg/bouguer/1/0/0.png").status_code, 404)   # 줌 2 아래


class ReadNc(SimpleTestCase):
    def test_머리의_x_y_를_믿지_않는다(self):
        try:
            import h5py
        except ImportError:
            self.skipTest("h5py 가 없다 — 호스트에서만")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.nc"
            with h5py.File(path, "w") as h:
                h["x"] = [0.0, 5000.0, 10000.0]
                h["y"] = [-5000.0, 0.0]
                h["Boug_anom"] = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]             # (y, x)
            g = antgg.read_nc(path, "Boug_anom")
            self.assertEqual((g.ne, g.nv, list(g.values)), (3, 2, [4.0, 5.0, 6.0, 1.0, 2.0, 3.0]))


class HeatFlowModels(TestCase):
    """남극 지열류 모형 셋 — 원본 글의 꼴과 IHFC 측정 점의 색 (wetherilli 432)"""
    STAL = "Q (mW/m2),U (mW/m2),X,Y,Lat,Lon\n50,9,0,0,-90,0\n130,9,20072,0,-89.8,90\n"
    LOSING = "Lon,Lat,HF [mW/m2],HF_min [mW/m2],HF_max [mW/m2],HF_max_abs [mW/m2]\n0,-89.5,45,40,50,5\n180,-89.5,250,200,300,50\n"
    MARTOS = "  -15000  0  70.5\n   0  0  30.0\n"

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def test_셋을_읽는다(self):
        from viewer import ghfgrid
        stal = ghfgrid.read("stal", self.STAL)
        self.assertEqual((stal.ne, stal.nv, stal.res, sorted(v for v in stal.values if v == v)), (2, 1, 20072.0, [50.0, 130.0]))
        losing = ghfgrid.read("losing", self.LOSING)
        self.assertEqual(sorted(v for v in losing.values if v == v)[-1], 250.0)
        martos = ghfgrid.read("martos", self.MARTOS)
        self.assertEqual((martos.res, list(martos.values)), (15000.0, [70.5, 30.0]))
        with self.assertRaises(polargrid.PolarGridError):
            ghfgrid.read("stal", "a,b\n1,2\n")

    def test_측정_점과_같은_색(self):
        from viewer import ghfgrid, heatflow
        spec = ghfgrid.SETS["ghfgrid:stal"]
        i = spec.index_of(130.0)
        self.assertEqual(tuple(spec.palette[3 * i:3 * i + 3]), heatflow.colour(130.0))
        rows = ghfgrid.legend("ghfgrid:stal", "en")["groups"][0]["rows"]
        self.assertEqual([r["color"] for r in rows], [c for _, c, _ in heatflow.CLASSES])

    def test_굽고_누른다(self):
        from viewer import ghfgrid
        with tempfile.TemporaryDirectory() as tmp, override_settings(ANTARCTIC_GHF_DIR=tmp):
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "Antarctic_GHF.xyz").write_text(self.MARTOS)
            call_command("build_antarctic_ghf", str(Path(tmp) / "src"), stdout=io.StringIO())
            self.assertTrue(ghfgrid.SETS["ghfgrid:martos"].available())
            self.assertFalse(ghfgrid.SETS["ghfgrid:stal"].available())
            got = self.client.get("/GSM/polargrid/info/", {"layer": "ghfgrid:martos", "lat": -90, "lon": 0}).json()
            self.assertEqual(got["features"][0]["props"], {"지열류 모형 (mW/m²)": "+30.0"})
            self.assertEqual(self.client.get("/GSM/polargrid/ghfgrid/martos/0/0/0.webp").status_code, 200)
        from viewer import views
        row = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}["ghfgrid:losing"]
        self.assertEqual(row["classLegend"]["groups"][0]["rows"][0]["color"], "#2b5fa8")
