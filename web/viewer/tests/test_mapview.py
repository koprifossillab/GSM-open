"""첫 화면 — CSS·JS 주소에 내용 표가 붙는지.

nginx 가 정적 파일을 7 일간 `immutable` 로 내보내므로, 주소가 그대로면
브라우저는 새로 배포한 CSS·JS 를 받지 않는다. v0.2.1 이 그렇게 옛 판으로 떴다.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import views
from viewer.models import Layer, LayerGroup


@override_settings(DEBUG=False)
class AssetStampTests(TestCase):
    def setUp(self):
        views.asset_stamp.cache_clear()

    def test_css_and_js_carry_the_stamp(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        stamp = views.asset_stamp()
        self.assertRegex(stamp, r"^[0-9a-f]{10}$")
        self.assertIn("map.css?v=" + stamp, html)
        self.assertIn("map.js?v=" + stamp, html)

    def test_stamp_follows_content(self):
        before = views.asset_stamp()
        views.asset_stamp.cache_clear()
        original = views.STAMPED
        try:
            views.STAMPED = original[:1]
            self.assertNotEqual(views.asset_stamp(), before)
        finally:
            views.STAMPED = original
            views.asset_stamp.cache_clear()

    def test_splash_is_in_the_first_paint(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        self.assertTrue(re.search(r'<div id="splash"[^>]*>\s*<img[^>]*splash\.gif', html))
        self.assertIn("불러오는 중", html)


class PolarProjectionTests(TestCase):
    """극지 화면 (devlog 017). 투영은 브라우저가 바꾸지만, 그러려면 서버가
    proj4 를 싣고 레이어마다 상류를 알려 줘야 한다."""

    def test_proj4_is_loaded_between_ol_and_map_js(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        self.assertIn("vendor/proj4.js", html)
        self.assertLess(html.index("vendor/ol.js"), html.index("vendor/proj4.js"))
        self.assertLess(html.index("vendor/proj4.js"), html.index("viewer/map.js"))

    def test_catalog_rows_carry_upstream(self):
        """화면은 상류를 보고 레이어를 만든다 — WMS 인가 구운 타일(geomap)인가."""
        g = LayerGroup.objects.create(name="지질도", region="greenland")
        Layer.objects.create(name="grl_g500_lithostr_search", title="50만", group=g, upstream="geus")
        k = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만", group=k)
        rows = {l["name"]: l for grp in views._catalog() for l in grp["layers"]}
        self.assertEqual(rows["grl_g500_lithostr_search"]["upstream"], "geus")
        self.assertEqual(rows["L_50K_Geology_Map"]["upstream"], "kigam")

    def test_every_seed_upstream_has_a_layer_maker(self):
        """씨앗의 상류(`_상류`)가 map.js 의 `LAYER_KINDS` 에 없으면 그 레이어는
        KIGAM WMS 로 잘못 불린다. 씨앗을 새로 더해도 여기서 걸린다."""
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        block = re.search(r"var LAYER_KINDS = \{(.*?)\n  \};", js, re.S).group(1)
        kinds = set(re.findall(r"^\s*(\w+):", block, re.M))
        used = {"kigam"}
        for seed in (settings.REPO_DIR / "data").glob("*_layers.json"):
            used.add(json.loads(seed.read_text(encoding="utf-8")).get("_상류", "kigam"))
        self.assertLessEqual(used, kinds)
        self.assertIn("geomap", kinds)


class Map3dView(TestCase):
    """3D 가 점묶음 요약과 번역표를 싣는지 (P02)."""

    def test_점묶음_요약을_싣는다(self):
        from viewer.models import PointSet
        PointSet.objects.create(name="설악 시료 </script><b>", color="#e4572e")
        html = self.client.get(reverse("viewer:map3d")).content.decode()
        self.assertIn('id="pointset-data"', html)
        self.assertIn('id="i18n-data"', html)
        # 사람이 적은 이름에 든 `</script>` 가 문서를 끊지 않는다
        self.assertNotIn("설악 시료 </script>", html)
        data = re.search(r'id="pointset-data" type="application/json">(.*?)</script>', html).group(1)
        self.assertEqual(json.loads(data)[0]["name"], "설악 시료 </script><b>")

    def test_3857_WMS_레이어만_고른다(self):
        group = LayerGroup.objects.create(name="시험")
        Layer.objects.create(name="L_250K_Geology_Map", title="25만", group=group, upstream="kigam")
        Layer.objects.create(name="gsj:geology", title="일본", group=group, upstream="gsj")
        Layer.objects.create(name="lt_l_gimsfault", title="단층", group=group, upstream="vworld", kind="vector")
        html = self.client.get(reverse("viewer:map3d")).content.decode()
        self.assertIn('value="L_250K_Geology_Map"', html)
        self.assertNotIn('value="gsj:geology"', html)
        self.assertNotIn('value="lt_l_gimsfault"', html)


class MoonView(TestCase):
    """달 (036, P05). 지역 탭이 아니라 대돌여지도 아이콘의 숨은 차림에서 들어간다."""

    def test_달_화면이_Cesium_과_달_스크립트를_싣는다(self):
        html = self.client.get(reverse("viewer:moon")).content.decode()
        self.assertIn("vendor/cesium/Cesium.js", html)
        self.assertIn("CESIUM_BASE_URL", html)
        self.assertIn("viewer/moon.js", html)

    def test_2D_의_아이콘이_숨은_차림으로_달을_연다(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        self.assertIn('id="emblem-btn"', html)
        menu = re.search(r'<nav class="hidden-menu" id="hidden-menu"[^>]*hidden>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(menu)
        self.assertIn('href="/GSM/moon/"', menu.group(1))   # 지도는 map/ 에 산다 (wetherilli 113)

    def test_달은_지역_탭이_아니다(self):
        from viewer.models import REGIONS
        self.assertNotIn("moon", dict(REGIONS))


class AntarcticStations(TestCase):
    """남극 탭의 "자세" — 장보고·세종 기지로 바로 가는 단추 (049).
    묶음은 방위 단추가 생겨 모든 탭에 서고, 기지 단추만 남극에서 선다 (wetherilli 114)."""

    def test_두_기지_단추가_남극에서만_선다(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        group = re.search(r'<div class="tool-col" role="group" aria-label="자세">(.*?)</div>\s*<output id="tool-out"', html, re.S)
        self.assertIsNotNone(group)
        for name in ("jangbogo", "sejong"):
            button = re.search(r'<button [^>]*data-goto="%s"[^>]*>' % name, group.group(1)).group(0)
            self.assertIn("antarctica-only", button)


class MapCompass(TestCase):
    """2D 지도의 방위 — 우클릭한 채 끌어 돌린 지도를 "자세" 묶음의 단추가 되돌린다 (wetherilli 114)."""

    def test_방위_단추는_모든_탭의_자세_묶음에(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        group = re.search(r'<div class="tool-col" role="group" aria-label="자세">(.*?)</div>\s*<output id="tool-out"', html, re.S)
        button = re.search(r'<button [^>]*id="tool-compass"[^>]*>', group.group(1)).group(0)
        self.assertNotIn("antarctica-only", button)
        self.assertIn('id="compass-needle"', group.group(1))


class Map3dGraduated(TestCase):
    """3D 는 실험을 벗었다 (059) — 단추가 늘 보이고, 실험 토글은 남는다."""

    def test_3D_단추가_늘_보인다(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        button = re.search(r'<a [^>]*id="tool-3d"[^>]*>', html).group(0)
        self.assertNotIn("hidden", button)
        self.assertNotIn("labs", button)
        self.assertIn('id="opt-labs"', html)


class Map3dRegions(TestCase):
    """3D 의 레이어 목록은 지역을 따른다 (050) — 화면이 거를 수 있게 레이어군마다 지역을 싣는다."""

    def test_레이어군마다_지역이_붙는다(self):
        korea = LayerGroup.objects.create(name="지질도", region="korea")
        south = LayerGroup.objects.create(name="GeoMAP", region="antarctica")
        Layer.objects.create(name="L_250K_Geology_Map", title="25만", group=korea, upstream="kigam")
        Layer.objects.create(name="npolar:dml_units", title="DML", group=south, upstream="npolar")
        html = self.client.get(reverse("viewer:map3d"), {"region": "antarctica"}).content.decode()
        self.assertIn('data-region="korea"', html)
        self.assertIn('data-region="antarctica"', html)
