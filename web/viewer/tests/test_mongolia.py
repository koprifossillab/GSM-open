"""몽골 MonGeoCat (wetherilli 221). 상류는 바꿔 끼운다.

속성·범례의 꼴은 2026-10-04 에 받아 본 그대로다 — 속성은 몽골어·영어 두 벌, 범례 칸 이름은 `10100_Q2` 꼴.
"""
import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import mris, views

WMS = {"crs": "EPSG:3857", "bbox": "11860000,6050000,11940000,6130000", "width": "256", "height": "256", "i": "10", "j": "20"}

#: 울란바토르 — 톨강의 홀로세 퇴적층
UB = {"OBJECTID": "1820", "L_Code": "10109", "Label": "aQ₂", "Formation_Complex_MN": "Голоцены хурдас",
      "Formation_Complex_EN": "Holocene sediment", "MegaZone_MN": "Хучаас хурдас", "MegaZone_EN": "Cover sediments",
      "TecZone_MN": "Хучаас хурдас", "TecZone_EN": "Cover sediments",
      "RockDescription_EN": "Alluvial (a), deluvial-proluvial (dp), aeolian (e) and lake (l) sand …", "L_Code_N": "10100"}

LEGEND = {"layers": [
    {"layerId": 0, "layerName": "Геологи", "legend": [
        {"label": "10100_Q2", "imageData": "AAA", "contentType": "image/png"},
        {"label": "30300_E2", "imageData": "BBB", "contentType": "image/png"},
        {"label": "310400_E2", "imageData": "CCC", "contentType": "image/png"},
        {"label": "910108_grT3-J1", "imageData": "DDD", "contentType": "image/png"},
        {"label": "10000", "imageData": "", "contentType": "image/png"}]},
    {"layerId": 1, "layerName": "Улсын хил", "legend": [{"label": "", "imageData": "EEE"}]}]}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Door(SimpleTestCase):
    def test_WMS_번호와_서비스(self):
        with mock.patch("viewer.mris.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            mris.get_map(dict(WMS, layers="mris:geology:1", format="image/png"))
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/services/Atlas/1_Geology/MapServer/WMSServer"))
        self.assertEqual((params["layers"], params["srs"]), ("1", "EPSG:3857"))
        with self.assertRaises(mris.MrisError):
            mris.get_map(dict(WMS, layers="mris:geology:1,mris:faults:0"))       # 서비스가 다르다
        self.assertFalse(mris.knows("mris:geology:0"))                           # 국경은 부르지 않는다

    def test_속성은_geojson(self):
        with mock.patch("viewer.mris.requests.get", return_value=response({"features": [{"properties": UB}]})) as get:
            data = mris.get_feature_info(dict(WMS, layers="mris:geology:1", query_layers="mris:geology:1"))
        params = get.call_args[1]["params"]
        self.assertEqual((params["query_layers"], params["info_format"], params["x"]), ("1", "application/geojson", "10"))
        self.assertEqual(data["features"][0]["properties"]["Label"], "aQ₂")


class Ages(SimpleTestCase):
    def test_층서_지수(self):
        self.assertEqual(mris.age_of("aQ₂", "10109"), "Holocene")
        self.assertEqual(mris.age_of("J₂₋₃", "40200"), "Middle – Late Jurassic")
        self.assertEqual(mris.age_of("grT3-J1", "910108"), "Late Triassic – Early Jurassic")
        self.assertEqual(mris.age_of("S3-4hd", "110250"), "Ludlow – Pridoli")
        self.assertEqual(mris.age_of("Melanj", "990500"), "")

    def test_E_는_코드로_가른다(self):
        self.assertEqual(mris.age_of("E2", "30300"), "Eocene")                   # 다섯 자리 3xxxx — 고진기
        self.assertEqual(mris.age_of("E2", "310400"), "Middle Cambrian")         # 여섯 자리 — 캄브리아기
        self.assertEqual(mris.age_of("NP3-E1", "410100"), "Ediacaran – Early Cambrian")
        self.assertEqual(mris.age_of("Є₂-O₁dr", "310702"), "Middle Cambrian – Early Ordovician")   # 속성은 제 글자로 쓴다


class Friendly(SimpleTestCase):
    def test_영어_열과_시대(self):
        out = mris.friendly(UB)
        self.assertEqual((out["기호"], out["이름"], out["원 이름"], out["지구조 구역"], out["지질시대"]),
                         ("aQ₂", "Holocene sediment", "Голоцены хурдас", "Cover sediments", "홀로세"))
        self.assertNotIn("지구조 대구역", out)                                   # 구역과 같으면 한 번만

    def test_범례_목록(self):
        with mock.patch("viewer.mris.requests.get", return_value=response(LEGEND)):
            rows = mris.legend_rows("mris:geology:1")
        self.assertEqual([(r["symbol"], r["age"]) for r in rows],
                         [("Q2", "Holocene"), ("E2", "Eocene"), ("E2", "Middle Cambrian"),
                          ("grT3-J1", "Late Triassic – Early Jurassic")])
        self.assertTrue(rows[0]["swatch"].startswith("data:image/png;base64,AAA"))


class Catalog(TestCase):
    def setUp(self):
        # 범례 길은 받은 것을 캐시에 담는다 — 가짜 범례가 개발 캐시에 남지 않게 임시 자리를 쓴다
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mongolia-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_몽골_탭과_동아시아(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["mris:geology:1"]
        self.assertEqual((group["region"], layer["projection"], layer["legend"]), ("mongolia", "EPSG:3857", "list"))
        self.assertFalse(rows["mris:faults:0"][1]["queryable"])
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        eastasia = re.search(r'eastasia: \{ title: "동아시아".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        self.assertIn('"mongolia"', eastasia)

    def test_범례_길(self):
        with mock.patch("viewer.mris.requests.get", return_value=response(LEGEND)):
            got = self.client.get("/GSM/mris/legend/", {"layer": "mris:geology:1"}).json()
        self.assertEqual(got["rows"][0]["age"], "홀로세")
        self.assertEqual(self.client.get("/GSM/mris/legend/", {"layer": "mris:faults:0"}).status_code, 400)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for("mris:geology:1", "mris"))
        self.assertIn("mris", views.MAP3D_WMS)
