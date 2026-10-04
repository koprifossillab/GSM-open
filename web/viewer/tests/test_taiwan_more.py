"""대만 셋째 판 — 5만 유역 지질도·광상·불연속면, 활성단층의 속성 (wetherilli 263). 상류는 바꿔 끼운다.

꼴은 2026-10-05 에 차룽푸 단층 둘레를 물어 받은 그대로다 — 한 단층이 토막 여럿으로 온다.
"""
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import gsmma, views

LINE = lambda x: {"type": "LineString", "coordinates": [[x, 24.10], [x + 0.01, 24.12]]}  # noqa: E731
FAULTS = {"features": [
    {"type": "Feature", "geometry": LINE(120.80), "properties": {"Name": "車籠埔斷層", "FAULT_TYPE": "第一類", "observe": "觀察"}},
    {"type": "Feature", "geometry": LINE(120.74), "properties": {"Name": "車籠埔斷層", "FAULT_TYPE": "第一類", "observe": "觀察"}},
    {"type": "Feature", "geometry": LINE(120.90), "properties": {"Name": "大茅埔-雙冬斷層", "FAULT_TYPE": "第二類", "observe": "推測"}}]}
CLICK = {"query_layers": "gsmma:active_faults", "crs": "EPSG:4326", "version": "1.3.0",
         "bbox": "24.0,120.6,24.2,120.8", "width": 200, "height": 200, "i": 140, "j": 100}


class ActiveFaults(SimpleTestCase):
    def test_가까운_단층부터_이름은_하나씩(self):
        answer = mock.Mock(status_code=200, content=b"", url="…", headers={"content-type": "application/json"})
        answer.json.return_value = FAULTS
        with mock.patch.object(gsmma.requests, "get", return_value=answer) as get, \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            data = gsmma.get_feature_info(CLICK)
        self.assertTrue(get.call_args.args[0].endswith("/ActiveFault"))
        names = [f["properties"]["FaultName"] for f in data["features"]]
        self.assertEqual(names, ["車籠埔斷層", "大茅埔-雙冬斷層"])                  # 같은 이름의 토막은 하나만
        out = gsmma.friendly(data["features"][0]["properties"])
        self.assertEqual((out["단층 이름"], out["단층 분류"], out["확인 여부"]), ("車籠埔斷層", "第一類", "觀察"))
        self.assertNotIn("지층명", out)

    def test_새_레이어의_상류_이름(self):
        self.assertEqual(gsmma._upstream_layers("gsmma:ore_50k"), "WMS/50K_Geomap_ore_line,WMS/50K_Geomap_ore_point")
        self.assertTrue(gsmma._upstream_layers("gsmma:drainage_50k").startswith("WMS/50K_Geomap_drainage_strata_2013"))


class Catalog(TestCase):
    def test_셋째_판(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name in ("gsmma:drainage_50k", "gsmma:ore_50k", "gsmma:ore_250k", "gsmma:discontinuity_50k"):
            group, layer = rows[name]
            self.assertEqual((group["region"], layer["projection"], layer["queryable"], layer.get("noLegend")),
                             ("taiwan", "EPSG:4326", False, True), name)
        self.assertNotIn("queryable", {k: v for k, v in rows["gsmma:active_faults"][1].items() if v is False})
