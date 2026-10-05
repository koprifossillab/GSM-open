"""단위 면 범례 셋째 — 노바스코샤·앨버타의 보는 범위, 도미니카공화국의 목록 (wetherilli 357). 상류는 바꿔 끼운다 — 꼴은 2026-10-05 에 받은 그대로다"""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import ags, igme, nsgs, views

#: 노바스코샤 `11?f=json` 의 칠하기 규칙(줄였다)
NS_LAYER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "AV_LEGEND", "uniqueValueInfos": [
    {"value": "15350North Mountain Formation: northern mainland", "label": "North Mountain Formation: northern mainland",
     "symbol": {"type": "esriSFS", "color": [189, 253, 198, 255]}},
    {"value": "21000Halifax Formation", "label": "Halifax Formation", "symbol": {"type": "esriSFS", "color": [102, 151, 135, 255]}},
    {"value": "99999Water", "label": "Water", "symbol": {"type": "esriSFS", "color": [0, 0, 0, 0]}}]}}}
NS_STATS = {"features": [
    {"attributes": {"AV_LEGEND": "21000Halifax Formation", "AGE_DESC": "Cambrian", "n": 37}},
    {"attributes": {"AV_LEGEND": "15350North Mountain Formation: northern mainland", "AGE_DESC": "Early Jurassic", "n": 5}},
    {"attributes": {"AV_LEGEND": "99999Water", "AGE_DESC": "", "n": 50}}]}
#: 앨버타 피처 서비스의 통계 질의
AB_STATS = {"features": [
    {"attributes": {"n": 1, "Unit_Name": "Bearpaw Formation", "RGB": "93-168-115", "Age": "Upper Cretaceous"}},
    {"attributes": {"n": 3, "Unit_Name": "Paskapoo Formation", "RGB": "255-247-158", "Age": "Paleogene"}},
    {"attributes": {"n": 2, "Unit_Name": "Broken", "RGB": "n/a", "Age": ""}}]}
#: 도미니카공화국 REST `1?f=json`
DR_LAYER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "Descriptio", "uniqueValueInfos": [
    {"value": "Alluvials deposits", "label": "Alluvials deposits, alluvials terraces", "symbol": {"color": [217, 217, 217, 255]}},
    {"value": "Limestone", "label": "Limestone", "symbol": {"color": [67, 175, 249, 255]}}]}}}


def answer(body, status=200):
    return mock.Mock(status_code=status, json=lambda: body, content=json.dumps(body).encode(), url="u",
                     headers={"content-type": "application/json"}, elapsed=None)


class Doors(TestCase):
    def test_노바스코샤_규칙과_통계(self):
        with mock.patch.object(nsgs, "_get", return_value=answer(NS_LAYER)):
            rules = nsgs.renderer("nsgs:11")
        self.assertEqual(set(rules), {"15350North Mountain Formation: northern mainland", "21000Halifax Formation"})   # 투명한 물은 뺀다
        with mock.patch.object(nsgs, "_get", return_value=answer(NS_STATS)) as get:
            rows = nsgs.extent_legend("nsgs:11", (-64.5, 44.4, -63.0, 45.2), rules, "en")
        self.assertEqual([(r["lithology"], r["color"], r["age"], r["count"]) for r in rows],
                         [("Halifax Formation", "#669787", "Cambrian", 37),
                          ("North Mountain Formation: northern mainland", "#bdfdc6", "Early Jurassic", 5)])
        self.assertEqual(get.call_args[0][1]["groupByFieldsForStatistics"], "AV_LEGEND,AGE_DESC")

    def test_앨버타는_RGB_열(self):
        with mock.patch.object(ags.requests, "get", return_value=answer(AB_STATS)), \
             mock.patch.object(ags.usage, "record"), mock.patch.object(ags.usage, "paused", return_value=0):
            rows = ags.extent_legend("ags:bedrock", (-115, 52.5, -112, 54.5), "ko")
        self.assertEqual([(r["lithology"], r["color"], r["count"]) for r in rows],
                         [("Paskapoo Formation", "#fff79e", 3), ("Bearpaw Formation", "#5da873", 1)])
        self.assertEqual(rows[1]["age"], "백악기 후기")                          # Upper → Late 로 옮겨 ICS 한글판

    def test_도미니카는_규칙_전부를_한_번(self):
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-igme-")), \
             mock.patch.object(igme.requests, "get", return_value=answer(DR_LAYER)) as get, \
             mock.patch.object(igme.usage, "record"), mock.patch.object(igme.usage, "paused", return_value=0):
            rows = igme.legend_rows("igme:sgnrd:0")
            again = igme.legend_rows("igme:sgnrd:0")
        self.assertEqual(get.call_count, 1)                                         # 담아 둔 것을 낸다
        self.assertEqual(rows, again)
        self.assertEqual([(r["lithology"], r["color"]) for r in rows],
                         [("Alluvials deposits, alluvials terraces", "#d9d9d9"), ("Limestone", "#43aff9")])
        self.assertTrue(get.call_args[0][0].endswith("/gis/rest/services/PSysmin/IGME_SGN_EN_Geology/MapServer/1"))   # WMS 0 = REST 1


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-units-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_카탈로그(self):
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        for name in ("nsgs:11", "ags:bedrock"):
            self.assertEqual((rows[name]["legend"], rows[name]["legendUrl"]), ("extent", "units/legend/"), name)
        self.assertTrue(rows["nsgs:9"]["noLegend"])

    def test_노바스코샤_규칙은_한_번(self):
        with mock.patch.object(nsgs, "_get", side_effect=[answer(NS_LAYER), answer(NS_STATS), answer(NS_STATS)]) as get:
            a = self.client.get("/GSM/units/legend/", {"layer": "nsgs:11", "bbox": "-64.5,44.4,-63,45.2"}).json()
            b = self.client.get("/GSM/units/legend/", {"layer": "nsgs:11", "bbox": "-66,44,-64,45"}).json()
            self.client.get("/GSM/units/legend/", {"layer": "nsgs:11", "bbox": "-66,44,-64,45"})
        self.assertEqual(get.call_count, 3)                                         # 규칙 하나, 범위마다 통계 하나 — 같은 범위는 캐시
        self.assertEqual(a["rows"][0]["lithology"], "Halifax Formation")
        self.assertEqual(a["rows"][0]["age"], "캄브리아기")
        self.assertEqual(len(b["rows"]), 2)

    def test_거절과_실패(self):
        self.assertEqual(self.client.get("/GSM/units/legend/", {"layer": "nsgs:9", "bbox": "-64,44,-63,45"}).status_code, 400)
        self.assertEqual(self.client.get("/GSM/units/legend/", {"layer": "ags:bedrock", "bbox": "-130,40,-100,60"}).status_code, 422)
        with mock.patch.object(ags.requests, "get", return_value=answer({"error": {"message": "x"}}, status=200)), \
             mock.patch.object(ags.usage, "record"), mock.patch.object(ags.usage, "paused", return_value=0):
            self.assertEqual(self.client.get("/GSM/units/legend/", {"layer": "ags:bedrock", "bbox": "-115,52,-112,54"}).status_code, 502)

    def test_목록_범례의_길(self):
        with mock.patch.object(igme.requests, "get", return_value=answer(DR_LAYER)), \
             mock.patch.object(igme.usage, "record"), mock.patch.object(igme.usage, "paused", return_value=0):
            r = self.client.get("/GSM/list/legend/", {"layer": "igme:sgnrd:0"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["rows"]), 2)
