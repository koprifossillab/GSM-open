"""운영 대조의 빈 그림 (wetherilli 310) — 축척 끝을 카탈로그의 처음 줌에, 성긴 선·점은 아는 자리부터."""
from django.core.management import call_command
from django.test import TestCase

from viewer import views
from viewer.management.commands import verify_layers
from viewer.models import Layer


class Floors(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        self.rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}

    def test_축척_끝이_처음_줌이다(self):
        for name, floor in views.SCALE_FLOOR.items():
            self.assertIn(name, self.rows, name)
            self.assertGreaterEqual(self.rows[name].get("minZoom") or 0, floor, name)

    def test_아는_자리를_먼저_본다(self):
        for name, (lon, lat) in verify_layers.VERIFY_AT.items():
            layer = Layer.objects.get(name=name)
            w, s, e, n = layer.bbox
            self.assertTrue(w <= lon <= e and s <= lat <= n, name)                        # 레이어 범위 안의 자리
            self.assertEqual(verify_layers.points(layer.bbox, name)[0], (lon, lat))
