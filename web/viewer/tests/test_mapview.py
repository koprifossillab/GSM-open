"""첫 화면 — CSS·JS 주소에 내용 표가 붙는지.

nginx 가 정적 파일을 7 일간 `immutable` 로 내보내므로, 주소가 그대로면
브라우저는 새로 배포한 CSS·JS 를 받지 않는다. v0.2.1 이 그렇게 옛 판으로 떴다.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
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

    def test_정적_주소에는_판이_붙는다(self):
        """정적 파일은 nginx 가 `?v=` 가 붙은 것만 1 년 `immutable` 로 둔다(wetherilli 345) — 템플릿의 파일 주소마다 판을 붙인다.
        끝이 `/` 인 뿌리 주소(Cesium·MapLibre 가 제 안에서 이어 붙인다)만 뺀다"""
        import pathlib
        missing = []
        for path in sorted((pathlib.Path(__file__).resolve().parents[1] / "templates" / "viewer").glob("*.html")):
            for m in re.finditer(r"\{% static '([^']+)' %\}(\S?)", path.read_text(encoding="utf-8")):
                if not m.group(1).endswith("/") and m.group(2) != "?":
                    missing.append(f"{path.name}: {m.group(1)}")
        self.assertEqual(missing, [])

    def test_splash_is_in_the_first_paint(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        # 대기 그림은 첫 칠에 든다 — 그림 자리(`picture`)가 splash 안에 있고, 그 바로 밑 스크립트가 주소를 고른다(WebP, 못 읽으면 GIF, wetherilli 345)
        self.assertTrue(re.search(r'<div id="splash"[^>]*>.*?<picture><source type="image/webp" id="splash-webp"><img id="splash-img"', html, re.S))
        script = html[html.index('id="splash-img"'):html.index("viewer/map.js")]
        self.assertIn("splash.webp?v=", script)
        self.assertIn("splash.gif?v=", script)
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

    def test_3857_타일_레이어만_고른다(self):
        group = LayerGroup.objects.create(name="시험")
        Layer.objects.create(name="L_250K_Geology_Map", title="25만", group=group, upstream="kigam")
        # 일본 GSJ 는 3857 z/x/y 라 그대로 얹는다(wetherilli 187). 극지 투영으로만 받는 극지연구소 KPDC 지도 서버와 모양(벡터)은 뺀다.
        # 노르웨이 NGU(wetherilli 335)·PGC(338)는 3857 도 그려 얹는다
        Layer.objects.create(name="gsj:geology", title="일본", group=group, upstream="gsj")
        Layer.objects.create(name="ngu:Berggrunn_nasjonal_bergartsenheter", title="노르웨이", group=group, upstream="ngu")
        Layer.objects.create(name="pgc:greenland_slope", title="경사", group=group, upstream="pgc")
        Layer.objects.create(name="kopri:lakes", title="호수", group=group, upstream="kopri")
        Layer.objects.create(name="lt_l_gimsfault", title="단층", group=group, upstream="vworld", kind="vector")
        html = self.client.get(reverse("viewer:map3d")).content.decode()
        self.assertIn('value="L_250K_Geology_Map"', html)
        self.assertIn('value="gsj:geology"', html)
        self.assertIn('value="ngu:Berggrunn_nasjonal_bergartsenheter"', html)
        self.assertIn('value="pgc:greenland_slope"', html)
        self.assertNotIn('value="kopri:lakes"', html)
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


class StaticSiteTests(TestCase):
    """연구소 밖 정적 판 (wetherilli P11·162) — 지도 화면을 서버 없이 도는 꼴로 그린다."""

    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        import io
        from django.core.management import call_command
        call_command("seed_catalog", stdout=io.StringIO())

    def test_정적_판의_소개는_서버_화면으로_가는_문이_없다(self):
        """wetherilli 167 — 3D·온 지구·달·화성·수성은 서버가 있어야 한다. 영어로도 그린다."""
        from django.test import override_settings
        for lang in ("ko", "en"):
            self.client.cookies["gsm_lang"] = lang
            with override_settings(STATIC_SITE={"regions": ["korea"], "upstreams": ["kigam"]}):
                html = self.client.get("/GSM/").content.decode()
            self.assertIn('id="static-config"', html)
            self.assertIn('href="/GSM/map/?region=korea"', html)
            for door in ("3d/", "earth/", "moon/", "mars/", "mercury/"):
                self.assertNotIn(f'href="/GSM/{door}"', html, door)
                self.assertNotIn(f'data-go="{door}"', html, door)
            self.assertNotIn('id="space"', html)
        self.assertIn("Great Stone Map", html)
        html = self.client.get("/GSM/").content.decode()                 # 서버 판은 그대로
        self.assertNotIn('id="static-config"', html)
        self.assertIn('href="/GSM/moon/"', html)
        self.assertIn('id="space"', html)

    def test_정적_판은_실을_것만_싣고_키는_없다(self):
        from django.test import override_settings
        import json as _json
        import re as _re
        with override_settings(STATIC_SITE={"regions": ["korea"], "upstreams": ["kigam"]}, KIGAM_KEY="비밀"):
            html = self.client.get("/GSM/map/").content.decode()
        self.assertIn('class="static-site"', html)
        self.assertIn('id="static-config"', html)
        self.assertIn("static-kinds.js", html)
        self.assertNotIn("비밀", html)
        groups = _json.loads(_re.search(r'id="catalog-data" type="application/json">(.*?)</script>', html, _re.S).group(1))
        ups = {l["upstream"] for g in groups for l in g["layers"]}
        self.assertEqual(ups, {"kigam"})
        self.assertEqual({g["region"] for g in groups}, {"korea"})
        names = {l["name"] for g in groups for l in g["layers"]}
        self.assertNotIn("L_50K_Geology_Map_NoAttitude", names)          # 문서에 없는 GeoServer 를 탄다

    def test_정적_판의_VWorld_는_공개_판용_키와_그림만(self):
        """wetherilli 164 — 공개 판용 키를 싣고, WFS 벡터(단층 따위)는 CORS 가 없어 뺀다."""
        from django.test import override_settings
        import json as _json
        import re as _re
        with override_settings(STATIC_SITE={"regions": ["korea"], "upstreams": ["kigam", "vworld"]},
                               KIGAM_KEY="비밀", VWORLD_KEY="공개판열쇠"):
            html = self.client.get("/GSM/map/").content.decode()
        self.assertIn('"공개판열쇠"', html)
        self.assertNotIn("비밀", html)
        groups = _json.loads(_re.search(r'id="catalog-data" type="application/json">(.*?)</script>', html, _re.S).group(1))
        vworld = [l for g in groups for l in g["layers"] if l["upstream"] == "vworld"]
        self.assertTrue(vworld)
        self.assertFalse([l["name"] for l in vworld if l.get("kind") == "vector"])
        self.assertNotIn("lt_l_gimsfault", {l["name"] for l in vworld})

    def test_구운_점_레이어는_이름으로_싣는다(self):
        # NPI·극지연구소에는 서버를 타는 지도 레이어가 섞여 있다 — 구운 점만 이름으로 (wetherilli 165)
        from django.test import override_settings
        import json as _json
        import re as _re
        spec = {"regions": ["antarctica", "jan_mayen"], "upstreams": ["geomap"],
                "baked": {"geomap": {"geomap_simple_geology": 10}, "points": {"npolar:dml_samples": False,
                                                                                "janmayen:units": True}}}
        with override_settings(STATIC_SITE=spec):
            html = self.client.get("/GSM/map/").content.decode()
        groups = _json.loads(_re.search(r'id="catalog-data" type="application/json">(.*?)</script>', html, _re.S).group(1))
        names = {l["name"] for g in groups for l in g["layers"]}
        self.assertIn("geomap_simple_geology", names)
        self.assertIn("npolar:dml_samples", names)
        self.assertIn("janmayen:units", names)
        self.assertNotIn("janmayen:lines", names)                             # 굽지 않은 것은 없다
        self.assertFalse({n for n in names if n.startswith("npolar:") and n != "npolar:dml_samples"})
        self.assertIn('"baked"', html)

    def test_운영_판은_그대로(self):
        html = self.client.get("/GSM/map/").content.decode()
        self.assertNotIn('class="static-site"', html)
        self.assertNotIn("static-config", html)


class ShareLinkTests(TestCase):
    """공유 링크 (wetherilli 189) — 다섯 화면이 `share.js` 를 화면의 스크립트보다 먼저 싣고 "링크" 단추를 둔다.
    링크를 읽고 지우는 것·기억을 덮지 않는 것은 브라우저 시험(`test_mobile`)이 본다"""

    def test_다섯_화면에_단추와_스크립트(self):
        for name, script in (("map", "map.js"), ("earth", "earth.js"), ("moon", "moon.js"), ("mars", "mars.js"),
                             ("mercury", "mercury.js")):
            with self.subTest(name=name):
                html = self.client.get(f"/GSM/{name}/").content.decode()
                self.assertIn('id="tool-share"', html)
                self.assertLess(html.index("viewer/share.js"), html.index(f"viewer/{script}"))


class Borrow3d(SimpleTestCase):
    """3D 가 빌려 오는 표(`map3d.js` 의 `BORROW`)는 2D 의 `REGIONS.*.borrow` 와 같다 (wetherilli 340)"""
    def test_2D_와_같다(self):
        here = Path(views.__file__).parent / "static/viewer"
        js2 = (here / "map.js").read_text(encoding="utf-8")
        js3 = (here / "map3d.js").read_text(encoding="utf-8")
        two = {}
        for m in re.finditer(r"^    ([a-z_]+): \{ title:(.*?)(?=^    [a-z_]+: \{ title:|^  \};)", js2, re.S | re.M):
            b = re.search(r"borrow:\s*(\{[^}]*\})", m.group(2))
            if b:
                # 열쇠는 `{`·`,` 뒤의 낱말뿐이다 — 값의 `"sgc:sa:"` 같은 앞머리를 건드리지 않는다
                two[m.group(1)] = json.loads(re.sub(r"([{,]\s*)([a-z_]+):", r'\1"\2":', b.group(1).replace("'", '"')))
        block = re.search(r"var BORROW = (\{.*?\n  \});", js3, re.S).group(1)
        three = json.loads(re.sub(r"^(\s+)([a-z_]+):", r'\1"\2":', block, flags=re.M))
        self.assertEqual(three, two)
