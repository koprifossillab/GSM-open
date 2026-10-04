"""레이어가 오백을 넘은 뒤의 첫 화면 비용 (wetherilli 271).

- 카탈로그는 레이어군 수와 상관없이 물음 둘이다(레이어군·켠 레이어) — 예전에는 레이어군마다 하나씩 160 남짓이었다
- 3D 의 `<option>` 은 파이썬이 짓는다 — 템플릿과 같은 이스케이프여야 한다
"""
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from viewer import views
from viewer.models import Layer


class CatalogQueries(TestCase):
    def test_레이어군_수와_상관없이_물음_둘(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        with CaptureQueriesContext(connection) as q:
            groups = views._catalog("ko")
        self.assertGreater(len(groups), 100)
        self.assertEqual(len(q), 2, [x["sql"][:80] for x in q])

    def test_끈_레이어는_빠지고_차례는_그대로(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        first = views._catalog("ko")[0]
        names = [l["name"] for l in first["layers"]]
        Layer.objects.filter(name=names[0]).update(enabled=False)
        again = [l["name"] for l in views._catalog("ko")[0]["layers"]]
        self.assertEqual(again, names[1:])


class Options3D(SimpleTestCase):
    def test_이스케이프와_빈_값(self):
        html = views._options_3d([
            {"name": "a:b", "title": "지질 <1:5만> & 단층", "upstream": "x", "attribution": '<a href="u">© "A"</a>',
             "bbox": [124.5, 33.0, 131.0, 38.5], "minZoom": 12},
            {"name": "c", "title": "C", "upstream": "y", "maxZoom": 0}])
        self.assertEqual(html,
                         '<option value="a:b" data-upstream="x" data-attribution="&lt;a href=&quot;u&quot;&gt;© &quot;A&quot;&lt;/a&gt;"'
                         ' data-min="12" data-bbox="124.5,33.0,131.0,38.5">지질 &lt;1:5만&gt; &amp; 단층</option>'
                         '<option value="c" data-upstream="y">C</option>')
