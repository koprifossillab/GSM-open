"""자력 이상·부게 중력 이상 — 칠한 경위도 격자 (wetherilli 391).

진짜 원본(EMAG2 CSV 4.3 GB)은 쓰지 않는다. 작은 격자를 지어 굽기·누른 자리·타일·ICGEM 글 격자 읽기를 본다.
"""
import io
import tempfile
import zipfile
from array import array
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import gravmag
from viewer.models import Layer, LayerGroup


def grid(values, w, h, step=90.0):
    return {"values": array("f", values), "w": w, "h": h, "lon0": -180 + step / 2, "lat0": 90 - step / 2, "dx": step, "dy": step}


class Build(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(EARTH_DIR=self.tmp.name)
        patch.enable()
        self.addCleanup(patch.disable)
        gravmag._meta.cache_clear()
        gravmag._image.cache_clear()

    def test_굽고_읽는다(self):
        nan = float("nan")
        info = gravmag.build("magnetic", grid([-500, 0, 120.4, nan, 1, 2, 3, 4], 4, 2))
        self.assertEqual((info["min"], info["max"]), (-500, 120))
        self.assertTrue(gravmag.available("magnetic"))
        self.assertEqual(gravmag.at("magnetic", -135, 45), -500)            # 서쪽 끝 칸
        self.assertEqual(gravmag.at("magnetic", 45, 45), 120)
        self.assertIsNone(gravmag.at("magnetic", 135, 45))                  # 빈 칸
        tile = Image.open(io.BytesIO(gravmag.render_tile("magnetic", 0, 0, 0)))
        self.assertEqual(tile.size, (256, 256))

    def test_주소(self):
        gravmag.build("magnetic", grid([10] * 8, 4, 2))
        response = self.client.get("/GSM/earth/gravmag/magnetic/0/0/0.png")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/GSM/earth/gravmag/magnetic/7/0/0.png").status_code, 404)
        props = self.client.get("/GSM/gravmag/info/", {"layer": "gravmag:magnetic", "lat": 45, "lon": 10}).json()["features"][0]["props"]
        self.assertEqual(props["자력 이상 (nT)"], "+10")
        group = LayerGroup.objects.create(name="지구물리 격자", region="china")
        Layer.objects.create(name="gravmag:magnetic", title="자력 이상", group=group, upstream="gravmag")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows["gravmag:magnetic"]["projection"], "EPSG:4326")
        self.assertEqual(len(rows["gravmag:magnetic"]["classLegend"]["groups"][0]["rows"]), 7)


class Read(SimpleTestCase):
    def test_ICGEM_글_격자(self):
        text = ("generating_institute GFZ\nmodelname EIGEN-6C4\nfunctional gravity_anomaly_bg\ngridstep 1.0\n"
                "     long  lat  gravity_anomaly_bg\n end_of_head ====\n"
                " 0.0 1.0 -12.5\n 1.0 1.0 3.0\n 359.0 1.0 7.0\n 0.0 0.0 1.0\n 1.0 0.0 2.0\n 359.0 0.0 4.0\n")
        with tempfile.NamedTemporaryFile("w", suffix=".gdf", delete=False) as fh:
            fh.write(text)
        self.addCleanup(Path(fh.name).unlink)
        g = gravmag.read_gdf(fh.name)
        self.assertEqual((g["w"], g["h"], g["lon0"], g["lat0"]), (3, 2, -1.0, 1.0))     # 359° → −1°
        self.assertEqual(list(g["values"])[:3], [7.0, -12.5, 3.0])

    def test_EMAG2_묶음(self):
        rows = "1,1,0.0166666666666667,89.9833333333333,99999,42.0,2,58\n2,1,0.05,89.9833333333333,99999,99999,2,58\n"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as fh:
            path = fh.name
        self.addCleanup(Path(path).unlink)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("EMAG2_V3_20170530.csv", rows)
        g = gravmag.read_emag2(path, shrink=2)
        self.assertEqual((g["w"], g["h"]), (5400, 2700))
        self.assertEqual(g["values"][2700], 42.0)          # 북쪽 첫 줄, 경도 0° 의 칸 — 빈 값(99999)은 섞이지 않는다

    def test_범례(self):
        rows = gravmag.legend("bouguer")
        self.assertEqual(rows[0]["label"], "≤ −180 mGal")
        self.assertEqual(rows[-1]["label"], "≥ 180 mGal")
