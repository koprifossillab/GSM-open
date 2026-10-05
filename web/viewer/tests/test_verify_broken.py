"""대조에서 빈 그림·오류로 나온 레이어 (wetherilli 308) — 상류를 부르지 않는다. 줌은 2026-10-05 에 재었다."""
import io
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import vworld
from viewer.management.commands.prewarm import plan_for
from viewer.management.commands.verify_layers import first_zoom


class Zooms(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-verify-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())

    def test_대조는_VWorld_의_최소_줌을_지킨다(self):
        plan = plan_for("lt_c_ademd", "vworld")
        self.assertEqual(plan.first, vworld.MIN_ZOOM["lt_c_ademd"])
        self.assertEqual(first_zoom(plan), vworld.MIN_ZOOM["lt_c_ademd"] - 1)       # 512 px 격자는 화면 줌보다 하나 작다
        self.assertIsNone(plan_for("lt_c_wkmstrm", "kigam").first if plan_for("lt_c_wkmstrm", "kigam") else None)

    def test_화면도_그_줌부터(self):
        layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        for name, z in (("ispra:100k:1", 11), ("ispra:100k:2", 10), ("sgm:5", 9), ("sgm:anom250:0", 9)):
            if name in layers:
                self.assertEqual(layers[name]["minZoom"], z, name)
