"""한국 탭 다시 보기 — 지역 탭의 지열류(IHFC) 점 레이어 (wetherilli 275). 작은 원본을 지어 굽는다(test_heatflow_glim 과 같은 꼴)."""
import json
import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import earthpoints, heatflow, views
from viewer.tests.test_heatflow_glim import HEAD

ROWS = ["85\t3\tHOLE-A\t36.5\t127.5\t120\t[onshore (continental)]\tBHT\t1984\tA\tKim 1984\tK1",
        "228\t\tHOHI-1\t35.1\t129.2\t\t[onshore (continental)]\t\t1984\t\tEhara 1984\tK2",
        "50\t\tfar\t10\t10\t\t\t\t\t\t\tX1"]                                                     # 한국 네모 밖


class KoreaHeatflow(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        with zipfile.ZipFile(root / "g.zip", "w") as zf:
            zf.writestr("IHFC_2024_GHFDB_v.2026.03.txt", (HEAD + "\r\n".join(ROWS) + "\r\n").encode("cp1252"))
        self.patch = override_settings(EARTH_DIR=str(root))
        self.patch.enable()
        heatflow.build(root / "g.zip", log=lambda *_: None)
        earthpoints._body.cache_clear()

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()
        earthpoints._body.cache_clear()

    def test_네모_안의_측정을_값의_칸으로(self):
        d = json.loads(earthpoints.body("earth:heatflow_korea"))
        props = [f["properties"] for f in d["features"]]
        self.assertEqual([p["q"] for p in props], ["85", "228"])                             # 높은 값이 뒤(위)에
        self.assertEqual((props[0]["code"], props[0]["unc"], props[0]["method"]), ("h3", "3", "BHT"))
        self.assertEqual(props[1]["code"], "h5")
        self.assertEqual([r["count"] for r in d["legend"]], [1, 1])

    def test_한국은_지구물리이상도_곁에(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["earth:heatflow_korea"]
        self.assertEqual((group["region"], group["name"]), ("korea", "지구물리이상도"))
        self.assertIn("Magnetic_Raster_2018", [l["name"] for l in group["layers"]])          # KIGAM 자력이상도와 한 레이어군
        self.assertEqual(rows["earth:heatflow_arctic"][0]["name"], "지구물리")
        got = self.client.get("/GSM/points/", {"layer": "earth:heatflow_korea"})
        self.assertEqual(got.status_code, 200)
