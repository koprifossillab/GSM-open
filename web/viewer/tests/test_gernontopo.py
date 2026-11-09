"""동남극 고지형 Gernon 2026 — GeoTIFF 읽기·칠하기·굽기·누른 자리 (wetherilli 436), 레이어 하나와 연대 34 장 (439). 작은 TIFF 를 지어 굽는다."""
import importlib
import io
import json
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
        self.assertEqual(gernontopo.legend(gernontopo.LAYER, "en")["groups"][0]["name"], "Palaeotopography (FastScape model)")
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
                z.writestr("GIS_files/COB160BestFitModel098Ma.tif", tif(north=900.0))     # 2 Myr 마다 다 굽는다 (439)
            call_command("build_gernon_paleotopo", str(src), stdout=io.StringIO(), stderr=io.StringIO())
            self.assertTrue(gernontopo.SETS["gernontopo:100"].available())
            self.assertTrue(gernontopo.set_for(98).available())
            # 등고선도 같은 zip 에서 래스터 옆에 — 98 Ma 는 1 500 m 에 닿지 않는다
            contours = json.loads((Path(tmp) / "contours.json").read_text(encoding="utf-8"))["ages"]
            self.assertEqual(sorted(contours), ["100", "98"])
            self.assertIn("1500", {r[0] for r in contours["100"]})
            self.assertNotIn("1500", {r[0] for r in contours["98"]})
            self.assertEqual(self.client.get("/GSM/polargrid/gernontopo/100/0/0/0.webp")["Content-Type"], "image/webp")
            self.assertEqual(self.client.get("/GSM/polargrid/gernontopo/90/0/0/0.webp").status_code, 200)   # 안내 타일
            got = self.client.get("/GSM/polargrid/info/", {"layer": "gernontopo:100", "lat": -80, "lon": 0}).json()
            self.assertEqual(got["features"][0]["props"], {"고도 (m)": 1800, "연대 (Ma)": 100})
            # 카탈로그의 레이어 하나로 물으면 `age` 의 판 — 화면의 연대 막대가 그 연대를 붙인다
            got = self.client.get("/GSM/polargrid/info/", {"layer": gernontopo.LAYER, "age": 98, "lat": -80, "lon": 0}).json()
            self.assertEqual(got["features"][0]["props"], {"고도 (m)": 900, "연대 (Ma)": 98})
            # 34 장이 판 하나를 나눠 쓴다 — 카탈로그 주소의 `?v=` 로 부르면 오래 둔다
            self.assertEqual(views._gernon_version(), "")                     # 다 굽지 않았으면 판이 없다
            en = self.client.get("/GSM/polargrid/info/", {"layer": "gernontopo:100", "lat": -80, "lon": 180},
                                 HTTP_COOKIE="gsm_lang=en").json()
            self.assertEqual(en["features"][0]["props"].get("Age (Ma)"), 100)

    def test_카탈로그는_한_줄(self):
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        self.assertFalse(any(n.startswith("gernontopo:") and n != gernontopo.LAYER for n in rows))
        row = rows[gernontopo.LAYER]
        self.assertEqual((row["projection"], row["maxZoom"]), ("EPSG:3031", gernontopo.MAX_ZOOM))
        self.assertTrue(row["tiles"].startswith("polargrid/gernontopo/{age}/{z}/{x}/{y}.webp"))
        self.assertEqual(row["ages"], list(range(100, 33, -2)))
        self.assertEqual(len(row["ages"]), 34)
        # 등고선·빙상 범위도 같은 레이어군에서 연대를 따른다
        for name in ("antpapers:gernon_contours", "antpapers:gernon_ice"):
            self.assertEqual(rows[name]["ages"], row["ages"])
        group = next(g for g in views._catalog("ko") if any(l["name"] == gernontopo.LAYER for l in g["layers"]))
        self.assertEqual({l["name"] for l in group["layers"]},
                         {gernontopo.LAYER, "antpapers:gernon_contours", "antpapers:gernon_ice"})

    def test_3d_는_한_연대(self):
        self.assertEqual(gernontopo.SETS[gernontopo.LAYER].name, f"gernontopo:{gernontopo.AGE_3D}")
        self.assertIsNone(gernontopo.set_for(35))
        self.assertIsNone(gernontopo.set_for("x"))


class Migration(TestCase):
    def test_옛_열_줄을_지운다(self):
        from django.apps import apps

        from viewer.models import Layer, LayerGroup
        old = LayerGroup.objects.create(name="동남극 고지형 등고선 (Gernon 2026)", region="antarctica", order=0)
        Layer.objects.create(name="antpapers:gernon_60ma", title="x", group=old, upstream="antpapers")
        keep = LayerGroup.objects.create(name="남극 그대로", region="antarctica", order=1)
        Layer.objects.create(name="gernontopo:60", title="x", group=keep, upstream="gernontopo")
        Layer.objects.create(name="gernontopo:paleotopo", title="x", group=keep, upstream="gernontopo")
        importlib.import_module("viewer.migrations.0052_gernon_timeline").forward(apps, None)
        self.assertEqual(list(Layer.objects.values_list("name", flat=True)), ["gernontopo:paleotopo"])
        self.assertEqual(list(LayerGroup.objects.values_list("name", flat=True)), ["남극 그대로"])
