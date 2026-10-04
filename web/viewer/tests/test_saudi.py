"""사우디 SGS 1:25만 (wetherilli 227). 상류는 바꿔 끼운다.

속성·통계·범례의 꼴은 2026-10-04 에 받아 본 그대로다.
"""
import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import sgs, views

WMS = {"crs": "EPSG:3857", "bbox": "4400000,2450000,4420000,2470000", "width": "256", "height": "256", "i": "10", "j": "20"}

#: 메카 도폭의 충적 선상지
MAKKAH = {"OBJECTID": "88094", "Map_Name": "Makkah GM-107C", "Unit_Name": "Quaternary alluvial fan and flood plain deposits",
          "Unit_SYM": "Qat", "Main_Litho": "Alluvial Fan deposits (Terraced)", "EON": "Phanerozoic", "ERA": "Cenozoic",
          "Period": "Quaternary", "Age_Ma": "<1 Ma", "Terrane": "Phanerozoic", "Sub_Terane": "Surficial cover"}
STATS = {"features": [
    {"attributes": {"Symbol": "Nbr", "Label": "Rahat alkali olivine basalt and basanite", "Period": "Neogene", "n": 70}},
    {"attributes": {"Symbol": "Qu", "Label": "Quaternary sand, gravel, and silt deposits", "Period": "Quaternary", "n": 378}},
    {"attributes": {"Symbol": "gkkf", "Label": "Ghamr group, Kharzah formation, silicic rocks", "Period": "Cryogenian", "n": 2}}]}
LEGEND = {"layers": [{"layerId": 0, "legend": [
    {"label": "Qu: Quaternary sand, gravel, and silt deposits", "imageData": "QQQ", "contentType": "image/png"},
    {"label": "Nbr: Rahat alkali olivine basalt and basanite", "imageData": "NNN", "contentType": "image/png"}]}]}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Door(SimpleTestCase):
    def test_이름_있는_WMS_레이어로(self):
        with mock.patch("viewer.sgs.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            sgs.get_map(dict(WMS, layers="sgs:geology", format="image/png"))
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/services/Geology/Geology_250K/MapServer/WMSServer"))
        self.assertEqual(params["layers"], "Geology_250K_Standard")              # 번호 0 은 LayerNotDefined

    def test_속성(self):
        with mock.patch("viewer.sgs.requests.get", return_value=response({"features": [{"properties": MAKKAH}]})) as get:
            data = sgs.get_feature_info(dict(WMS, layers="sgs:geology", query_layers="sgs:geology"))
        self.assertEqual((get.call_args[1]["params"]["info_format"], get.call_args[1]["params"]["feature_count"]),
                         ("application/geojson", "1"))
        out = sgs.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["지질시대"], out["연대"], out["지구조 구역"], out["도폭"]),
                         ("Qat", "제4기", "<1 Ma", "Phanerozoic · Surficial cover", "Makkah GM-107C"))
        self.assertEqual(sgs.friendly(MAKKAH, "en")["지질시대"], "Quaternary")


class Legend(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-saudi-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_보는_범위의_단위를_센다(self):
        with mock.patch("viewer.sgs.requests.get", return_value=response(STATS)) as get:
            rows = sgs.extent_legend((39.0, 21.0, 41.0, 23.0))
        params = get.call_args[1]["params"]
        self.assertEqual(params["groupByFieldsForStatistics"], "Symbol,Label,Period")
        self.assertEqual([r["symbol"] for r in rows], ["Qu", "Nbr", "gkkf"])            # 면이 많은 것부터

    def test_범례_길(self):
        def fake(url, params=None, **kw):
            return response(LEGEND if url.endswith("/legend") else STATS)
        with mock.patch("viewer.sgs.requests.get", side_effect=fake):
            got = self.client.get("/GSM/sgs/legend/", {"layer": "sgs:geology", "bbox": "39,21,41,23"}).json()
        first = got["rows"][0]
        self.assertEqual((first["symbol"], first["age"]), ("Qu", "제4기"))
        self.assertTrue(first["swatch"].endswith("base64,QQQ"))
        self.assertEqual(got["rows"][2]["swatch"], "")                                   # 견본이 없는 칸
        wide = self.client.get("/GSM/sgs/legend/", {"layer": "sgs:geology", "bbox": "34,16,48,32"})
        self.assertEqual(wide.status_code, 422)


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_사우디_탭(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["sgs:geology"]
        self.assertEqual((group["region"], layer["projection"], layer["legend"], layer["legendUrl"]),
                         ("saudi", "EPSG:3857", "extent", "sgs/legend/"))
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        self.assertTrue(re.search(r'saudi: \{ title: "사우디아라비아", proj: "EPSG:3857"', js))

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for("sgs:geology", "sgs"))
        self.assertIn("sgs", views.MAP3D_WMS)
