"""넓게 보면 느린 레이어의 처음 줌 (wetherilli 313) — 한 칸이 10 초를 넘는 줌은 묻지 않는다. 상류를 부르지 않는다."""
import io
import pathlib
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import views
from viewer.management.commands.verify_layers import first_zoom, plan_of
from viewer.models import Layer

MAPJS = pathlib.Path(__file__).resolve().parents[1] / "static" / "viewer" / "map.js"


class SlowFloor(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-slow-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())

    def test_카탈로그의_처음_줌(self):
        rows = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        for name, floor in views.SLOW_FLOOR.items():
            if name in rows:
                self.assertGreaterEqual(rows[name]["minZoom"], floor, name)

    def test_대조와_미리_데우기도_그_줌부터(self):
        layer = Layer.objects.get(name="esdm:geology")
        self.assertEqual(first_zoom(plan_of(layer)), views.SLOW_FLOOR["esdm:geology"] - 1)     # 512 px 격자는 하나 작다

    def test_패널이_그_까닭을_적는다(self):
        js = MAPJS.read_text(encoding="utf-8")
        self.assertIn('note(T("줌 {n} 부터 그려진다", { n: minZoom }))', js)
