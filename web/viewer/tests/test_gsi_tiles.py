"""국토지리원 주제 타일 — 브라우저가 곧장 부르는 카탈로그 레이어 (wetherilli 172). 상류를 부르지 않는다."""
import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from viewer import views
from viewer.models import Layer


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=io.StringIO())
        self.rows = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_씨앗은_일본에(self):
        row = Layer.objects.get(name="gsitile:afm")
        self.assertEqual((row.upstream, row.group.region), ("gsitile", "japan"))

    def test_지리원_주소를_그대로_화면에(self):
        afm = self.rows["gsitile:afm"]
        self.assertEqual(afm["tiles"], "https://cyberjapandata.gsi.go.jp/xyz/afm/{z}/{x}/{y}.png")
        self.assertEqual((afm["minZoom"], afm["maxZoom"]), (3, 16))
        self.assertEqual(self.rows["gsitile:vlcd"]["minZoom"], 5)
        self.assertIs(afm["queryable"], False)
        self.assertTrue(afm["noLegend"])

    def test_서버를_거치지_않는다(self):
        # 서버의 문(`_Door`)에 gsitile 이 없다 — /wms/ 로 와도 상류가 아니다
        self.assertNotIn("gsitile", views._Door.MODULES)
