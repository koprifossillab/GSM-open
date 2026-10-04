"""온 지구 — 지열류 IHFC·세계 암상 GLiM (wetherilli 267). 상류를 부르지 않는다 — 작은 원본을 지어 굽는다."""
import io
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import glim, heatflow

HEAD = ("# Licence: Creative Commons Attribution 4.0 International\r\n#\r\n"
        "P1\tP2\tP3\tP4\tP5\r\nM\tM\tM\tM\tM\r\n"
        "q\tq_uncertainty\tname\tlat_NS\tlong_EW\televation\tenvironment\tq_method\tYear\tQuality_Code_Child\tpublication_reference\tID\r\n")
ROWS = ["366\t\t44593\t49.615\t-129.981\t-2383.7\t[offshore (continental)]\tPRO\t1990\tA\tDavis 1990\tH1",
        "366\t\t44593\t49.615\t-129.981\t-2383.7\t[offshore (continental)]\tPRO\t1990\tA\tDavis 1990\tH1b",   # 같은 자리·값
        "62\t5\t?\t43.0467\t-30.0633\t\t[offshore (marine)]\t\t\t\t\tH2",
        "\t\tx\t10\t10\t\t\t\t\t\t\tH3",                                                                      # 값 없음
        "41\t\tBúrfell\t43.0317\t200\t\t[onshore]\t\t\t\t\tH4"]                                                 # 경도 200 → −160


class Heatflow(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        with zipfile.ZipFile(root / "g.zip", "w") as zf:
            zf.writestr("IHFC_2024_GHFDB_v.2026.03.txt", (HEAD + "\r\n".join(ROWS) + "\r\n").encode("cp1252"))
        self.patch = override_settings(EARTH_DIR=str(root))
        self.patch.enable()
        self.got = heatflow.build(root / "g.zip", log=lambda *_: None)

    def tearDown(self):
        self.patch.disable()
        self.tmp.cleanup()

    def test_굽고_찾는다(self):
        self.assertEqual((self.got["rows"], self.got["skipped"]), (3, 2))
        hit = heatflow.near(-129.98, 49.61, 0.1)[0]
        self.assertEqual((hit["q"], hit["environment"], hit["name"]), (366.0, "offshore (continental)", "44593"))
        self.assertEqual(heatflow.near(-30.06, 43.05, 0.1)[0]["name"], "")              # "?" 는 이름이 아니다
        self.assertEqual(heatflow.near(-160.0, 43.03, 0.1)[0]["name"], "Búrfell")         # 경도를 −180…180 으로, cp1252 를 풀어
        tile = Image.open(io.BytesIO(heatflow.render_tile(0, 0, 0))).convert("RGBA")
        self.assertTrue(any(p[3] for p in tile.getdata()))
        self.assertEqual(heatflow.colour(366), (0xb0, 0x20, 0x7a))

    def test_주소와_화면(self):
        got = self.client.get("/GSM/earth/heatflow/at/", {"lon": -129.98, "lat": 49.61, "r": 0.1}).json()
        self.assertEqual(got["hits"][0]["rows"][0], ["지열류 (mW/m²)", "366"])
        self.assertEqual(self.client.get("/GSM/earth/heatflow/tiles/0/0/0.png")["Content-Type"], "image/png")
        self.assertIn('"heatflow": [{"color"', self.client.get("/GSM/earth/").content.decode())


class Glim(SimpleTestCase):
    def test_ASCII_를_읽는다(self):
        head = "ncols 720\nnrows 360\nxllcorner -180\nyllcorner -90\ncellsize 0.5\nNODATA_value -9999\n"
        rows = ["8 " + " ".join(["-9999"] * 719)] + [" ".join(["16"] * 720)] * 359
        got = glim.read_ascii(head + "\n".join(rows))
        self.assertEqual((len(got), len(got[0])), (360, 720))
        self.assertEqual(got[0][:2], "h.")                                                 # 8 → h, 빈 칸 → .
        with self.assertRaises(ValueError):
            glim.read_ascii(head.replace("720", "100", 1) + "\n".join(rows))

    def test_저장소의_격자(self):
        self.assertIsNotNone(glim.grid())
        self.assertEqual(glim.at(127.0, 37.5) is not None, True)                           # 한반도는 칠해져 있다
        self.assertIsNone(glim.at(-150.0, 0.0))                                            # 태평양 한가운데
        self.assertEqual(glim.name(14, "en"), "Evaporites")
        rows = glim.legend()
        self.assertEqual(len(rows), 15)                                                    # 자료 없음은 범례에 없다
        tile = Image.open(io.BytesIO(glim.render_tile(0, 1, 0))).convert("RGBA")
        self.assertTrue(any(p[3] for p in tile.getdata()))
