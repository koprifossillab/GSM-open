"""`manage.py verify_layers` — 레이어가 실제로 그려지는지 모든 상류에 한 장씩 대조해 DB 에 남긴다 (wetherilli 203·298).
상류를 부르지 않는다 — 문의 `get_map` 을 갈아 끼운다."""
import io
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from PIL import Image

from viewer import geus, kigam, sgm, usage
from viewer.models import Layer, LayerGroup


def png(colour):
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), colour).save(buf, "PNG")
    return buf.getvalue()


PAINTED = png((200, 80, 40, 255))
BLANK = png((0, 0, 0, 0))


class VerifyLayers(TestCase):
    def setUp(self):
        group = LayerGroup.objects.create(name="시험", region="korea")
        self.good = Layer.objects.create(name="L_250K_Geology_Map", title="25만", group=group, upstream="kigam",
                                         bbox_west=124, bbox_south=33, bbox_east=131, bbox_north=39)
        self.bad = Layer.objects.create(name="L_1M_Nope", title="없는 것", group=group, upstream="kigam")
        self.other = Layer.objects.create(name="geus:x", title="그린란드", group=group, upstream="geus")
        for name, value in (("has_key", True), ("probe_openapi_feature_info", "막혀 있다 (500)")):
            p = mock.patch.object(kigam, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(usage, "paused", return_value=0)
        p.start()
        self.addCleanup(p.stop)

    def run_command(self, geus_answer=PAINTED, **options):
        def kigam_map(params):
            if params["layers"] == "L_1M_Nope":
                raise kigam.UpstreamError("LayerNotDefined")
            return PAINTED, "image/png"
        out = io.StringIO()
        with mock.patch.object(kigam, "get_map", side_effect=kigam_map) as get, \
             mock.patch.object(geus, "get_map", return_value=(geus_answer, "image/png")) as gget:
            call_command("verify_layers", delay=0, stdout=out, stderr=io.StringIO(), **options)
        return out.getvalue(), get, gget

    def test_그림은_날짜를_KIGAM_오류는_내린다(self):
        text, get, gget = self.run_command()
        for layer in (self.good, self.bad, self.other):
            layer.refresh_from_db()
        self.assertIsNotNone(self.good.verified_at)
        self.assertIn("그림 — ", self.good.verify_note)
        self.assertTrue(self.good.enabled)
        self.assertFalse(self.bad.enabled)
        self.assertIn("LayerNotDefined", self.bad.verify_note)
        self.assertIsNotNone(self.other.verified_at)              # 그린란드(GEUS)도 이제 묻는다
        self.assertEqual((get.call_count, gget.call_count), (2, 1))
        self.assertIn("| kigam | 1 | 0 | 1 | 0 |", text)           # 상류마다 표
        self.assertIn("그림 2, 빈 그림 0, 오류 1, 건너뜀 0", text)
        self.assertIn("GetFeatureInfo: 막혀 있다", text)

    def test_빈_그림은_한_칸_더_보고_날짜를_남기지_않는다(self):
        text, _, gget = self.run_command(geus_answer=BLANK, upstream="geus")
        self.other.refresh_from_db()
        self.assertEqual(gget.call_count, 5)                         # 한가운데와 귀퉁이 쪽 넷
        self.assertIsNone(self.other.verified_at)
        self.assertTrue(self.other.enabled)                         # KIGAM 밖은 내리지 않는다
        self.assertIn("빈 그림", self.other.verify_note)
        self.assertIn("- geus `geus:x` — 빈 그림", text)

    def test_확인한_것은_다시_묻지_않고_redo_면_다시(self):
        self.run_command()
        _, get, gget = self.run_command()
        self.assertEqual([c.args[0]["layers"] for c in get.call_args_list], ["L_1M_Nope"])   # 날짜가 없는 것만
        self.assertEqual(gget.call_count, 0)
        _, get, _ = self.run_command(redo=True, only="250K")
        self.assertEqual([c.args[0]["layers"] for c in get.call_args_list], ["L_250K_Geology_Map"])

    def test_키가_없으면_KIGAM_만_건너뛴다(self):
        err = io.StringIO()
        with mock.patch.object(kigam, "has_key", return_value=False), mock.patch.object(kigam, "get_map") as get, \
             mock.patch.object(geus, "get_map", return_value=(PAINTED, "image/png")) as gget:
            call_command("verify_layers", delay=0, stdout=io.StringIO(), stderr=err)
        get.assert_not_called()
        self.assertEqual(gget.call_count, 1)
        self.assertIn("인증키가 없다", err.getvalue())

    def test_점_레이어는_건너뛴다(self):
        group = LayerGroup.objects.get(name="시험")
        Layer.objects.create(name="grportal:samples", title="시료", group=group, upstream="grportal")
        text, *_ = self.run_command(upstream="grportal")
        self.assertIn("| grportal | 0 | 0 | 0 | 1 |", text)


class Pace(TestCase):
    """천천히 간다 — 한 상류가 연달아 셋 깨지면 그 상류는 그만, 차단 조짐이면 멈춘다"""

    def setUp(self):
        group = LayerGroup.objects.create(name="멕시코", region="mexico")
        for n in range(5):
            Layer.objects.create(name=f"sgm:geo:{n}", title=f"{n}", group=group, upstream="sgm",
                                 bbox_west=-110, bbox_south=20, bbox_east=-90, bbox_north=30)
        p = mock.patch.object(kigam, "has_key", return_value=False)
        p.start()
        self.addCleanup(p.stop)

    def test_연달아_셋이면_그_상류는_그만(self):
        out = io.StringIO()
        with mock.patch.object(sgm, "get_map", side_effect=sgm.SgmError("503")) as get, \
             mock.patch.object(usage, "paused", return_value=0):
            call_command("verify_layers", delay=0, stdout=out, stderr=io.StringIO())
        self.assertEqual(get.call_count, 3)
        self.assertIn("| sgm | 0 | 0 | 3 | 2 |", out.getvalue())

    def test_차단_조짐이면_멈춘다(self):
        err = io.StringIO()
        with mock.patch.object(sgm, "get_map", side_effect=sgm.SgmError("차단 — 429")) as get:
            call_command("verify_layers", delay=0, stdout=io.StringIO(), stderr=err)
        self.assertEqual(get.call_count, 1)
        self.assertIn("차단 조짐 — 멈춘다", err.getvalue())
