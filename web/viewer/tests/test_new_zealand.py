"""뉴질랜드 GNS·오세아니아 묶음 (wetherilli 218). 상류는 바꿔 끼운다.

속성의 꼴은 2026-10-04 에 받아 본 그대로다 — 1:25만은 숫자 나이, 1:100만은 ICS 영어, 남빅토리아랜드는 1:25만과 같은 열.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import gns, views

WMS = {"crs": "EPSG:3857", "bbox": "19100000,-5400000,19200000,-5300000", "width": "256", "height": "256", "i": "10", "j": "20"}

#: 1:25만 — 크라이스트처치 둘레의 OIS2 강 퇴적층
QMAP = {"code": "Q2.alvgvl", "main_rock": "gravel", "sub_rocks": "sand silt clay", "key_name": "OIS2 (Late Pleistocene) river deposits",
        "stratlex": None, "strat_age": "Q2", "abs_min": 0.012, "abs_max": 0.024, "descriptio": "Unweathered, brownish-grey …",
        "qmap_name": "Christchurch", "terrane_eq": None, "supergroup": None}
#: 1:100만
GMNZ = {"mapsymbol": "lQa", "name": "Late Quaternary alluvium and colluvium", "descr": "Unconsolidated to poorly consolidated mud …",
        "geolhist": "Late Quaternary", "lithology": "mud, sand, gravel, peat", "sgrpequiv": "Pakihi Supergroup", "terrequiv": "None",
        "absmin_ma": "0.0", "absmax_ma": "0.12"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Door(SimpleTestCase):
    def test_우리_이름을_상류_이름으로(self):
        with mock.patch("viewer.gns.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            gns.get_map(dict(WMS, layers="gns:qmap,gns:NZL_GNS_1M_faults", format="image/png"))
        self.assertEqual(get.call_args[1]["params"]["layers"],
                         "NZL_GNS_250K_seamless_qmap_geological_map_current_view,gns:NZL_GNS_1M_faults")
        with self.assertRaises(gns.GnsError):
            gns.get_map(dict(WMS, layers="gmnz:NZL_GNS_GM5_faults"))

    def test_합본을_누르면_단위_레이어에_열을_골라_묻는다(self):
        with mock.patch("viewer.gns.requests.get", return_value=response({"features": [{"properties": QMAP}]})) as get:
            data = gns.get_feature_info(dict(WMS, layers="gns:qmap", query_layers="gns:qmap"))
        params = get.call_args[1]["params"]
        self.assertEqual(params["query_layers"], "NZL_GNS_250K_geologic_units")
        self.assertIn("abs_max", params["propertyName"])
        self.assertNotIn("geom", params["propertyName"])
        self.assertEqual((params["x"], params["y"]), ("10", "20"))
        self.assertEqual(data["features"][0]["properties"]["code"], "Q2.alvgvl")

    def test_선은_누르지_않는다(self):
        self.assertFalse(gns.queryable("gns:NZL_GNS_1M_faults"))
        with self.assertRaises(gns.GnsError):
            gns.get_feature_info(dict(WMS, layers="gns:NZL_GNS_1M_faults", query_layers="gns:NZL_GNS_1M_faults"))

    def test_합본은_범례_그림이_없다(self):
        with self.assertRaises(gns.GnsError):
            gns.get_legend("gns:qmap")


class Ages(SimpleTestCase):
    def test_숫자_나이에서_ICS(self):
        self.assertEqual(gns.ics_span(0.012, 0.024), "Late Pleistocene")
        self.assertEqual(gns.ics_span(0.001, 0.14), "Middle Pleistocene – Holocene")
        self.assertEqual(gns.ics_span("0", "0"), "")                 # 얼음

    def test_경계를_둥글린_나이는_이웃에(self):
        # 상류가 `Tr J` 로 적은 단위가 142 Ma(백악기 바닥 145 바로 밑)까지 내려온다 — 쥐라기로 친다
        self.assertEqual(gns.ics_span(142, 248), "Triassic – Jurassic")


class Friendly(SimpleTestCase):
    def test_1_25만(self):
        out = gns.friendly(QMAP)
        self.assertEqual((out["기호"], out["이름"], out["암석"], out["도폭"]),
                         ("Q2.alvgvl", "OIS2 (Late Pleistocene) river deposits", "gravel, sand silt clay", "Christchurch"))
        self.assertEqual((out["지질시대"], out["연대"]), ("플라이스토세 후기", "0.024–0.012 Ma"))
        self.assertNotIn("지구조 구역", out)

    def test_1_100만은_ICS_영어가_온다(self):
        out = gns.friendly(GMNZ, "en")
        self.assertEqual((out["지질시대"], out["초층군"], out["연대"]), ("Late Quaternary", "Pakihi Supergroup", "0.12–0 Ma"))
        self.assertNotIn("지구조 구역", out)                         # "None" 은 빈 값


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_뉴질랜드_탭과_남극(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["gns:qmap"]
        self.assertEqual((group["region"], layer["projection"], layer["minZoom"]), ("new_zealand", "EPSG:3857", 7))
        self.assertEqual((layer["legend"], layer["legendUrl"]), ("extent", "gns/legend/"))   # 보는 범위의 칸 (wetherilli 355)
        self.assertNotIn("noLegend", layer)
        group, layer = rows["gns:ATA_SVL_GNS_250K_geological_units"]
        self.assertEqual((group["region"], layer["projection"]), ("antarctica", "EPSG:3031"))
        self.assertEqual(set(gns.LAYERS), {n for n in rows if n.startswith("gns:")})

    def test_오세아니아_묶음(self):
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        oceania = re.search(r'oceania: \{ title: "오세아니아".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        self.assertEqual(oceania.replace(" ", ""), '"australia","new_zealand","new_caledonia","french_polynesia"')   # 프랑스 해외 영토는 wetherilli 260
        js3d = (Path(views.__file__).parent / "static/viewer/map3d.js").read_text(encoding="utf-8")
        self.assertIn('oceania: ["australia", "new_zealand", "new_caledonia", "french_polynesia"]', js3d)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        self.assertIsNotNone(prewarm.plan_for("gns:NZL_GNS_1M_geological_units", "gns"))
        self.assertIn("gns", views.MAP3D_WMS)


#: QMAP 합본의 GetLegendGraphic JSON(`hideEmptyRules`·`countMatched`) — 2026-10-05 웰링턴에서 받은 꼴을 줄였다
QMAP_LEGEND = {"Legend": [
    {"layerName": "NZL_GNS_250K_geological_units_scale500k", "rules": [
        {"name": "Q.alvgvl", "title": "Q.alvgvl (45)", "symbolizers": [{"Polygon": {"fill": "#F2F24D"}}]},
        {"name": "Tr.szm", "title": "Tr.szm (20)", "symbolizers": [{"Polygon": {"fill": "#CCF5F5"}}]},
        {"name": "water", "title": "water (60)", "symbolizers": [{"Polygon": {"fill": "#F7FFFF"}}]},
        {"name": "Q1.alvgvl", "title": "Q1.alvgvl (30)", "symbolizers": [{"Polygon": {"fill": "#FFFFE6"}}]}]},
    {"layerName": "NZL_GNS_250K_faults_plotrank", "rules": [
        {"name": "accurate", "title": "accurate (12)", "symbolizers": [{"Line": {"stroke": "#000000"}}]}]}]}


class ExtentLegend(TestCase):
    """QMAP 합본의 보는 범위 범례 (wetherilli 355)"""

    def answer(self, status=200, body=None):
        return mock.Mock(status_code=status, json=lambda: body if body is not None else QMAP_LEGEND,
                         headers={"content-type": "application/json"}, elapsed=None)

    def test_면의_규칙만_많은_것부터(self):
        with mock.patch.object(gns, "_get", return_value=self.answer()) as get:
            rows = gns.extent_legend("gns:qmap", (174.6, -41.4, 175.1, -41.1))
        self.assertEqual([(r["lithology"], r["color"], r["count"]) for r in rows],
                         [("Q.alvgvl", "#f2f24d", 45), ("Q1.alvgvl", "#ffffe6", 30), ("Tr.szm", "#ccf5f5", 20)])   # 물·단층선은 뺀다
        params = get.call_args[0][0]
        self.assertEqual(params["legend_options"], "countMatched:true;hideEmptyRules:true")
        self.assertEqual((params["srs"], params["bbox"]), ("EPSG:4326", "174.6,-41.4,175.1,-41.1"))

    def test_화면의_길(self):
        from django.test import override_settings
        import tempfile
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gns-")):
            with mock.patch.object(gns, "_get", return_value=self.answer()) as get:
                a = self.client.get("/GSM/gns/legend/", {"layer": "gns:qmap", "bbox": "174.6,-41.4,175.1,-41.1"})
                b = self.client.get("/GSM/gns/legend/", {"layer": "gns:qmap", "bbox": "174.6,-41.4,175.1,-41.1"})
            self.assertEqual(get.call_count, 1)                             # 같은 범위는 캐시
            self.assertEqual(a.json()["rows"][0]["lithology"], "Q.alvgvl")
            self.assertEqual(a.json(), b.json())
            self.assertEqual(self.client.get("/GSM/gns/legend/", {"layer": "gns:qmap", "bbox": "166,-47,178,-34"}).status_code, 422)
            self.assertEqual(self.client.get("/GSM/gns/legend/", {"layer": "gns:NZL_GNS_1M_faults", "bbox": "174,-41,175,-40"}).status_code, 400)
            with mock.patch.object(gns, "_get", return_value=self.answer(status=500)):
                self.assertEqual(self.client.get("/GSM/gns/legend/", {"layer": "gns:qmap", "bbox": "170,-44,171,-43"}).status_code, 502)
