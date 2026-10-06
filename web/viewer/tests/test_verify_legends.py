"""레이어 대조가 범례 길도 본다 — `verify_layers --legends` (wetherilli 367). 상류는 타지 않는다 — 우리 뷰를 바꿔 끼운다"""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.http import JsonResponse
from django.test import TestCase, override_settings

from viewer import verifylog
from viewer.management.commands import verify_layers as vl
from viewer.models import Layer


class LegendCheck(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(VERIFY_DIR=tempfile.mkdtemp(prefix="gsm-verify-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_보는_범위와_목록만_고른다(self):
        names = {layer.name: row["legend"] for layer, row in vl.legend_rows()}
        self.assertEqual(names.get("gns:qmap"), "extent")
        self.assertEqual(names.get("igme:sgnrd:0"), "list")
        self.assertNotIn("gns:NZL_GNS_1M_faults", names)               # 그림 범례는 GetLegendGraphic 한 길이라 뺀다
        self.assertGreater(len(names), 50)

    def test_칸이_서면_그림_없으면_다음_자리_422_면_더_작게(self):
        layer = Layer.objects.get(name="gns:qmap")
        row = {"legend": "extent", "legendUrl": "gns/legend/"}
        answers = [(422, JsonResponse({"error": "넓다", "rows": []}, status=422)),     # 첫 자리, 큰 네모
                   (200, JsonResponse({"rows": []})),                                  # 첫 자리, 작은 네모 — 비었다
                   (200, JsonResponse({"rows": [{"lithology": "Q1.alvgvl"}], "more": 2}))]   # 다음 자리
        with mock.patch.object(vl, "_call", side_effect=answers) as call, mock.patch.object(vl.time, "sleep"):
            kind, note = vl.check_legend(layer, row, delay=0)
        self.assertEqual(kind, "그림")
        self.assertIn("3칸", note)
        self.assertEqual(call.call_count, 3)
        self.assertIn("bbox", call.call_args.kwargs)

    def test_오류와_목록(self):
        layer = Layer.objects.get(name="igme:sgnrd:0")
        with mock.patch.object(vl, "_call", return_value=(502, JsonResponse({"error": "범례를 받지 못했다", "rows": []}, status=502))):
            kind, note = vl.check_legend(layer, {"legend": "list", "legendUrl": "list/legend/"}, delay=0)
        self.assertEqual(kind, "오류")
        self.assertIn("502", note)

    def test_명령은_캐시_없이_돌고_기록은_legend_앞머리(self):
        seen = []

        def fake(layer, row, delay):
            from django.conf import settings
            seen.append(settings.TILE_CACHE_DIR)
            return ("오류", "502") if layer.name == "gns:qmap" else ("그림", "3칸")
        out = io.StringIO()
        with mock.patch.object(vl, "check_legend", side_effect=fake):
            call_command("verify_layers", "--legends", "--upstream", "gns,igme", stdout=out)
        self.assertEqual(set(seen), {""})                               # 캐시를 껐다
        layers = json.loads(verifylog.files()[-1].read_text())["layers"]
        self.assertEqual(layers["legend:gns:qmap"]["kind"], "오류")
        self.assertEqual(layers["legend:igme:sgnrd:0"]["kind"], "그림")
        self.assertIsNone(Layer.objects.get(name="gns:qmap").verified_at)   # 타일 대조의 기록은 건드리지 않는다
        summary = verifylog.summary()
        self.assertEqual((summary["drawn"], summary["legends"], summary["legend_broken"]), (0, 1, 1))   # 타일 수에 섞지 않는다
