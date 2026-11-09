"""동남극 고지형 Gernon 2026 — GeoTIFF 읽기·칠하기·굽기·누른 자리 (wetherilli 436). 작은 TIFF 를 지어 굽는다."""
import io
import math
import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, TiffImagePlugin

from viewer import gernontopo, views

N, RES = 41, 150000.0
LEFT, TOP = -(N / 2) * RES, (N / 2) * RES                      # 왼쪽 위 모서리 — 가운데 칸이 극


def tif(north=1800.0, south=-3000.0) -> bytes:
    """위쪽 절반(y > 0)은 north m, 아래쪽은 south m, 맨 위 줄 왼쪽 셋은 NaN. Gernon 의 꼬리표 꼴(33550·33922)"""
    image = Image.new("F", (N, N))
    image.putdata([math.nan if r == 0 and c < 3 else (north if r < N // 2 else south) for r in range(N) for c in range(N)])
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[33550] = (RES, RES, 0.0)
    info[33922] = (0.0, 0.0, 0.0, LEFT, TOP, 0.0)
    buf = io.BytesIO()
    image.save(buf, format="TIFF", compression="tiff_lzw", tiffinfo=info)
    return buf.getvalue()


class Read(SimpleTestCase):
    def test_원점은_칸의_가운데로(self):
        g = gernontopo.read_tif(tif())
        self.assertEqual((g.ne, g.nv, g.res, g.x0, g.ytop), (N, N, RES, LEFT + RES / 2, TOP - RES / 2))
        self.assertTrue(math.isnan(g.values[0]))
        self.assertEqual((g.values[3], g.values[(N - 1) * N]), (1800.0, -3000.0))

    def test_칠하기는_1500_에서_건너뛴다(self):
        index_of = gernontopo.SETS["gernontopo:100"].index_of
        below, above = index_of(1499), index_of(1500)
        self.assertEqual(above, below + 1)
        self.assertEqual(gernontopo.CLASSES[above - 1][1], "#c0703c")
        self.assertLess(index_of(-1), index_of(0))                   # 바다와 뭍이 갈린다

    def test_범례(self):
        got = gernontopo.legend("gernontopo:44", "en")
        self.assertEqual(got["groups"][0]["name"], "Palaeotopography 44 Ma (FastScape model)")
        self.assertEqual(len(got["groups"][0]["rows"]), len(gernontopo.CLASSES))
        self.assertIn("10.5281/zenodo.19205651", got["attribution"])


class Bake(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def test_zip_에서_굽고_누른다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(GERNON_PALEOTOPO_DIR=tmp):
            src = Path(tmp) / "GIS_files.zip"
            with zipfile.ZipFile(src, "w") as z:
                z.writestr("GIS_files/COB160BestFitModel100Ma.tif", tif())
                z.writestr("GIS_files/COB160BestFitModel098Ma.tif", tif())        # 내지 않는 연대는 건너뛴다
            call_command("build_gernon_paleotopo", str(src), stdout=io.StringIO(), stderr=io.StringIO())
            self.assertTrue(gernontopo.SETS["gernontopo:100"].available())
            self.assertFalse((Path(tmp) / "98").exists())
            self.assertEqual(self.client.get("/GSM/polargrid/gernontopo/100/0/0/0.webp")["Content-Type"], "image/webp")
            self.assertEqual(self.client.get("/GSM/polargrid/gernontopo/90/0/0/0.webp").status_code, 200)   # 안내 타일
            got = self.client.get("/GSM/polargrid/info/", {"layer": "gernontopo:100", "lat": -80, "lon": 0}).json()
            self.assertEqual(got["features"][0]["props"], {"고도 (m)": 1800, "연대 (Ma)": 100})
            en = self.client.get("/GSM/polargrid/info/", {"layer": "gernontopo:100", "lat": -80, "lon": 180},
                                 HTTP_COOKIE="gsm_lang=en").json()
            self.assertEqual(en["features"][0]["props"].get("Age (Ma)"), 100)

    def test_카탈로그(self):
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        names = [f"gernontopo:{a}" for a in gernontopo.AGES]
        self.assertTrue(all(n in rows for n in names))
        row = rows["gernontopo:34"]
        self.assertEqual((row["projection"], row["maxZoom"]), ("EPSG:3031", gernontopo.MAX_ZOOM))
        self.assertTrue(row["tiles"].startswith("polargrid/gernontopo/34/{z}/{x}/{y}.webp"))
