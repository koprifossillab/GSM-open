"""`manage.py verify_layers` — 레이어가 `/openapi/wms` 로 실제로 그려지는지 대조해 DB 에 남긴다. DB 를 고치는 명령인데 시험이
없었다 (wetherilli 203). 상류를 부르지 않는다 — `kigam.get_map`·`probe_openapi_feature_info` 를 갈아 끼운다."""
import io
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from viewer import kigam
from viewer.models import Layer, LayerGroup


class VerifyLayers(TestCase):
    def setUp(self):
        group = LayerGroup.objects.create(name="시험", region="korea")
        self.good = Layer.objects.create(name="L_250K_Geology_Map", title="25만", group=group, upstream="kigam")
        self.bad = Layer.objects.create(name="L_1M_Nope", title="없는 것", group=group, upstream="kigam")
        self.other = Layer.objects.create(name="geus:x", title="그린란드", group=group, upstream="geus")
        for name, value in (("has_key", True), ("probe_openapi_feature_info", "막혀 있다 (500)")):
            p = mock.patch.object(kigam, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def run_command(self, **options):
        def get_map(params):
            if params["layers"] == "L_1M_Nope":
                raise kigam.UpstreamError("LayerNotDefined")
            return b"\x89PNG" + b"x" * 10, "image/png"
        out = io.StringIO()
        with mock.patch.object(kigam, "get_map", side_effect=get_map) as get:
            call_command("verify_layers", delay=0, stdout=out, **options)
        return out.getvalue(), get

    def test_그려지면_날짜를_안_되면_내린다(self):
        text, get = self.run_command()
        self.good.refresh_from_db()
        self.bad.refresh_from_db()
        self.assertIsNotNone(self.good.verified_at)
        self.assertEqual(self.good.verify_note, "14 bytes")
        self.assertTrue(self.good.enabled)
        self.assertFalse(self.bad.enabled)
        self.assertIn("LayerNotDefined", self.bad.verify_note)
        self.assertEqual(get.call_count, 2)                     # 그린란드(GEUS)는 묻지 않는다
        self.assertIn("그려지는 것 1, 안 되는 것 1", text)
        self.assertIn("GetFeatureInfo: 막혀 있다", text)          # 끝에 속성 길을 찔러본다

    def test_확인한_것은_다시_묻지_않고_redo_면_다시(self):
        self.run_command()
        _, get = self.run_command()
        self.assertEqual([c.args[0]["layers"] for c in get.call_args_list], ["L_1M_Nope"])   # 날짜가 없는 것만
        _, get = self.run_command(redo=True, only="250K")
        self.assertEqual([c.args[0]["layers"] for c in get.call_args_list], ["L_250K_Geology_Map"])

    def test_키가_없으면_묻지_않는다(self):
        err = io.StringIO()
        with mock.patch.object(kigam, "has_key", return_value=False), mock.patch.object(kigam, "get_map") as get:
            call_command("verify_layers", stdout=io.StringIO(), stderr=err)
        get.assert_not_called()
        self.assertIn("인증키가 없다", err.getvalue())
