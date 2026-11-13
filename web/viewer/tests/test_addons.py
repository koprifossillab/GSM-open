"""덧붙이의 이음매 — 가짜 덧붙이(`tests/fake_addon`)로 한 번씩 지나간다 (wetherilli P19·446).

진짜 덧붙이는 다른 저장소에 있어 GSM 의 CI 가 보지 못한다. 그래서 **약속을 여기서 지킨다** — 이음매를 고쳐 이 시험이 깨지면
덧붙이도 깨진다. 덧붙이 없이 도는 것이 기본이라, 없을 때 아무것도 달라지지 않는지도 본다.
"""
import json
import os
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404

from viewer import addons, datastatus, doors, i18n, views
from viewer.models import Layer
from viewer.tests.test_mobile import PhoneBase

FAKE = "viewer.tests.fake_addon"
LAYER = "fakeaddon:bed"


class WithoutAddons(SimpleTestCase):
    def test_덧붙이가_없으면_손이_다_비어_있다(self):
        self.assertEqual(addons.names(), ())
        self.assertEqual(addons.seeds(), [])
        self.assertEqual(addons.urlpatterns("GSM/"), [])
        self.assertEqual(list(addons.door_modules()), [])
        self.assertEqual(doors.polar_sets(), {})
        before = (dict(i18n.EN), list(datastatus.ITEMS))
        addons.merge()
        self.assertEqual((i18n.EN, datastatus.ITEMS), before)
        # 얼굴은 GSM 의 것 그대로 — 이름은 언어를 따른다 (wetherilli 453)
        self.assertEqual((addons.brand("ko")["name"], addons.brand("ko")["tagline"]), ("대돌여지도", "GREAT STONE MAP"))
        self.assertEqual((addons.brand("en")["name"], addons.brand("en")["tagline"]), ("Great Stone Map", "대돌여지도"))
        self.assertEqual(addons.brand()["emblem"], "viewer/emblem.svg")

    def test_가짜_덧붙이는_표의_줄마다_하나씩_갖는다(self):
        """`addons.py` 머리의 표에 줄이 늘면 가짜 덧붙이에도 하나 둔다 — 시험하지 않는 이음매가 생기지 않게"""
        here = Path(__file__).parent / "fake_addon"
        for name in ("urls.py", "fakedoor.py", "i18n.py", "datastatus.py", "data/fake_layers.json",
                     "static/fake_addon/map.js", "static/fake_addon/map.css", "brand.py"):
            self.assertTrue((here / name).exists(), name)


@override_settings(ADDONS=(FAKE,))
class Seams(TestCase):
    def setUp(self):
        doors.specs.cache_clear()
        self.addCleanup(doors.specs.cache_clear)

    def test_이름은_패키지의_마지막_마디(self):
        self.assertEqual(addons.short(FAKE), "fake_addon")
        self.assertTrue((addons.folder(FAKE) / "fakedoor.py").exists())

    def test_없는_패키지는_뜰_때_터진다(self):
        with override_settings(ADDONS=("no_such_addon_package",)):
            with self.assertRaises(ImportError):
                addons.seeds()

    def test_주소는_x_밑에_걸린다(self):
        patterns = addons.urlpatterns("GSM/")
        self.assertEqual(len(patterns), 1)
        match = patterns[0].resolve("GSM/x/fake_addon/ping/")
        self.assertEqual(json.loads(match.func(None).content), {"addon": "fake_addon"})
        with self.assertRaises(Resolver404):
            patterns[0].resolve("GSM/x/fake_addon/nope/")

    def test_문이_긁힌다(self):
        spec = doors.specs()["fakeaddon"]
        self.assertEqual((spec.tag, spec.title, spec.local), ("FAKE", "Fake addon", True))
        self.assertEqual(spec.module.__name__, f"{FAKE}.fakedoor")
        self.assertIn("kigam", doors.specs())                      # GSM 의 문은 그대로
        self.assertEqual(doors.client()["fakeaddon"], ["FAKE", "Fake addon", False])

    def test_같은_상류를_GSM_과_겹쳐_적으면_멈춘다(self):
        import viewer.tests.fake_addon.fakedoor as door
        with mock.patch.object(door, "REGISTRY", [{"upstream": "kigam", "tag": "X", "title": "X"}]):
            doors.specs.cache_clear()
            with self.assertRaises(ValueError):
                doors.specs()

    def test_남극_격자가_모인다(self):
        self.assertEqual(list(doors.polar_sets()), [LAYER])
        self.assertEqual(doors.polar_legend(LAYER)["attribution"], "Fake addon")
        self.assertIsNone(doors.polar_legend("antgg:bouguer"))     # GSM 의 것은 views 가 손으로 낸다

    def test_씨앗이_들어간다(self):
        self.assertEqual([label for _, label in addons.seeds()], ["덧붙이 fake_addon (fake_layers)"])
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        layer = Layer.objects.get(name=LAYER)
        self.assertEqual((layer.upstream, layer.group.region, layer.group.name), ("fakeaddon", "antarctica", "가짜 레이어군"))
        self.assertTrue(Layer.objects.filter(name="geomap_simple_geology").exists())   # GSM 의 씨앗도 그대로

    def test_번역표와_구운_자료_표가_합쳐진다(self):
        tables = {name: dict(getattr(i18n, name)) for name in addons.I18N_TABLES}
        items = list(datastatus.ITEMS)

        def restore():
            for name, table in tables.items():
                getattr(i18n, name).clear()
                getattr(i18n, name).update(table)
            datastatus.ITEMS[:] = items
        self.addCleanup(restore)

        addons.merge()
        self.assertEqual(i18n.t("가짜 덧붙이의 문장", "en"), "A sentence from the fake addon")
        self.assertEqual(i18n.EN["지역"], tables["EN"]["지역"])                  # 같은 열쇠는 GSM 것이 이긴다
        self.assertEqual(i18n.LAYER_EN[LAYER], "Fake bed")
        self.assertEqual(i18n.PROP_EN["가짜 바닥 높이 (m)"], "Fake bed elevation (m)")
        self.assertEqual(i18n.GROUP_EN["가짜 레이어군"], "Fake layer group")
        keys = [item.key for item in datastatus.ITEMS]
        self.assertEqual(keys.count("addons/fake_addon/bed/meta.json"), 1)
        addons.merge()                                                           # 두 번 불러도 한 줄
        self.assertEqual(len(datastatus.ITEMS), len(items) + 1)

    def test_격자_레이어가_카탈로그와_타일로_선다(self):
        """덧붙이는 뷰를 짓지 않는다 — `SETS` 만 두면 GSM 의 길(`polargrid/…`)로 타일·누른 자리·카탈로그 행이 선다"""
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        with mock.patch.dict(views.POLAR_SETS, doors.polar_sets()):
            row = next(l for g in views._catalog() for l in g["layers"] if l["name"] == LAYER)
            self.assertEqual(row["hand"], "polargrid")
            self.assertTrue(row["tiles"].startswith("polargrid/fakeaddon/bed/{z}/{x}/{y}.webp"))
            self.assertEqual((row["projection"], row["maxZoom"], row["verified"]), ("EPSG:3031", 2, True))
            self.assertEqual(row["classLegend"]["attribution"], "Fake addon")
            # 구운 것이 없으면 안내 타일 — 404 가 아니다
            self.assertEqual(self.client.get("/GSM/polargrid/fakeaddon/bed/0/0/0.webp").status_code, 200)
            self.assertEqual(self.client.get("/GSM/polargrid/fakeaddon/bed/3/0/0.webp").status_code, 404)
            self.assertEqual(self.client.get(f"/GSM/polargrid/info/?layer={LAYER}&lat=-75&lon=0").json(), {"features": []})

    def test_함께_낼_판은_누른_자리에_같이_뜬다(self):
        """`Set.along` — 바닥을 누르면 두께도. 값이 없는 판은 그 줄만 빠진다 (wetherilli 447)"""
        import dataclasses
        from viewer import polargrid
        bed = doors.polar_sets()[LAYER]
        ice = dataclasses.replace(bed, name="fakeaddon:ice", sub="fake_addon/ice", prop="가짜 얼음 두께 (m)")
        gone = dataclasses.replace(bed, name="fakeaddon:gone", sub="fake_addon/gone", prop="없는 판")
        both = dataclasses.replace(bed, along=("fakeaddon:ice", "fakeaddon:gone", "fakeaddon:unknown"))
        values = {LAYER: -120, "fakeaddon:ice": 2500, "fakeaddon:gone": None}
        with mock.patch.dict(views.POLAR_SETS, {LAYER: both, "fakeaddon:ice": ice, "fakeaddon:gone": gone}), \
                mock.patch.object(polargrid, "value_at", lambda spec, lat, lon: values[spec.name]):
            got = self.client.get(f"/GSM/polargrid/info/?layer={LAYER}&lat=-75&lon=0").json()
        self.assertEqual(got["features"][0]["props"], {"가짜 바닥 높이 (m)": -120, "가짜 얼음 두께 (m)": 2500})

    def test_화면_파일을_지도가_제_것_뒤에_싣는다(self):
        self.assertEqual(addons.screen_assets(), {"scripts": ["fake_addon/map.js"], "styles": ["fake_addon/map.css"]})
        html = self.client.get("/GSM/map/").content.decode()
        own, mine = html.index("viewer/map.js"), html.index("fake_addon/map.js")
        self.assertLess(own, mine)
        self.assertLess(html.index("viewer/map.css"), html.index("fake_addon/map.css"))

    def test_차림의_얼굴이_이름과_아이콘과_대기_화면을_바꾼다(self):
        """덧붙이의 `brand.py` — 적은 열쇠만 바뀌고 나머지는 GSM 의 것이 남는다 (wetherilli 453)"""
        got = addons.brand("ko")
        self.assertEqual((got["name"], got["tagline"], got["emblem_polar"], got["emblem"]),
                         ("가짜지도", "FAKE MAP", "fake_addon/emblem.png", "viewer/emblem.svg"))
        html = self.client.get("/GSM/map/").content.decode()
        self.assertIn("<title>가짜지도</title>", html)
        self.assertIn("<h1>가짜지도 <span", html)
        self.assertIn('<p class="tagline">FAKE MAP</p>', html)
        self.assertIn('data-emblem-polar="/GSM/static/fake_addon/emblem.png', html)
        self.assertIn('"/GSM/static/fake_addon/splash.webp', html)                     # 극지의 대기 화면
        self.assertIn('"/GSM/static/viewer/splash.webp', html)                         # 적지 않은 것은 GSM 의 것
        self.assertNotIn("<h1>대돌여지도", html)
        for path, want in (("/GSM/earth/", "가짜지도 · "), ("/GSM/map/3d/", "가짜지도 3D")):
            page = self.client.get(path)
            if page.status_code == 200:
                self.assertIn(want, page.content.decode(), path)
        # 모르는 열쇠는 터뜨린다 — 오타로 얼굴이 반만 바뀌지 않게
        from viewer.tests.fake_addon import brand as fake
        with mock.patch.dict(fake.BRAND, {"emblm": "x"}):
            with self.assertRaises(ValueError):
                addons.brand()

    def test_점_레이어가_카탈로그와_덩이로_선다(self):
        """덧붙이의 문이 `POINTS`·`points()` 를 두면 GSM 의 길(`points/`)이 덩이를 낸다 — 담지 않는다 (wetherilli 449)"""
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        name = "fakeaddon:cores"
        self.assertEqual(set(doors.addon_points()), {name})
        with mock.patch.dict(views.ADDON_POINTS, doors.addon_points()):
            row = next(l for g in views._catalog() for l in g["layers"] if l["name"] == name)
            self.assertEqual((row["kind"], row["hand"], row["style"], row["attribution"]), ("points", "points", "class", "Fake addon"))
            r = self.client.get(f"/GSM/points/?layer={name}")
            self.assertEqual((r.status_code, r["Cache-Control"]), (200, "no-store"))
            got = r.json()
            self.assertEqual(got["features"][0]["properties"]["name"], "FAKE-GC01")
            self.assertEqual(got["legend"][0]["label"], "가짜 코어")
        self.assertEqual(self.client.get(f"/GSM/points/?layer={name}").status_code, 404)     # 덧붙이가 없으면 모르는 레이어다
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        self.assertIn("points: { source: null, info: null },", js)

    def test_화면의_손_표에_polargrid_가_있다(self):
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        self.assertIn("polargrid: { source: geomapSource, info: polargridInfoUrl }", js)
        self.assertIn("row.hand && LAYER_KINDS[row.hand]", js)


class Profile(TestCase):
    """차림 — 지역 탭 줄이기·따로 화면 숨기기·형제 화면의 입구. 기본은 다 꺼져 있다"""

    def test_기본은_아무것도_싣지_않는다(self):
        html = self.client.get("/GSM/map/").content.decode()
        self.assertEqual(addons.screen_assets(), {"scripts": [], "styles": []})
        self.assertNotIn("fake_addon/", html)
        self.assertNotIn("profile-config", html)
        self.assertNotIn("sibling-link", html)
        for screen in ("earth", "moon", "mars", "mercury"):
            self.assertIn(f'href="/GSM/{screen}/"', html)

    @override_settings(ONLY_REGIONS=("antarctica",))
    def test_세울_지역을_화면에_싣는다(self):
        html = self.client.get("/GSM/map/").content.decode()
        found = re.search(r'<script id="profile-config" type="application/json">(.*?)</script>', html, re.S)
        self.assertEqual(json.loads(found.group(1)), {"regions": ["antarctica"]})

    @override_settings(HIDDEN_SCREENS=("moon", "mars", "mercury"))
    def test_숨긴_화면은_링크도_주소도_없다(self):
        for path in ("map/", "earth/", ""):
            html = self.client.get(f"/GSM/{path}").content.decode()
            for screen in ("moon", "mars", "mercury"):
                self.assertNotIn(f'href="/GSM/{screen}/"', html, f"{path} → {screen}")
        self.assertIn('href="/GSM/earth/"', self.client.get("/GSM/map/").content.decode())
        self.assertEqual(self.client.get("/GSM/moon/").status_code, 404)
        self.assertEqual(self.client.get("/GSM/mercury/").status_code, 404)
        self.assertEqual(self.client.get("/GSM/earth/").status_code, 200)

    @override_settings(SIBLINGS=({"name": "ASM", "url": "/ASM/"},))
    def test_형제_화면의_입구가_숨은_차림에_선다(self):
        html = self.client.get("/GSM/map/").content.decode()
        self.assertRegex(html, r'<a role="menuitem" class="server-only sibling-link" href="/ASM/">.*?ASM</a>')


@override_settings(ONLY_REGIONS=("antarctica",), HIDDEN_SCREENS=("moon", "mars", "mercury"))
class ProfileScreen(PhoneBase):
    """남극만 세운 차림으로 화면이 뜨는지 — 한국이 없어도 첫 탭이 서고 페이지 오류가 없다"""

    def test_남극_탭_하나로_열린다(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        page = self.check_map_screen("map/")
        tabs = page.eval_on_selector_all("#regions .region-tab", "els => els.map(e => e.dataset.region)")
        self.assertEqual(tabs, ["antarctica"])
        self.assertEqual(page.evaluate("document.querySelectorAll('#regions .region-more').length"), 0)
        self.assertEqual(page.evaluate("document.documentElement.dataset.region || document.body.dataset.region || ''") or "antarctica",
                         "antarctica")
        page.context.close()

    def test_없는_지역을_주소로_넘겨도_남극이다(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        page = self.check_map_screen("map/?region=korea")
        tabs = page.eval_on_selector_all("#regions .region-tab.on", "els => els.map(e => e.dataset.region)")
        self.assertEqual(tabs, ["antarctica"])
        page.context.close()


@override_settings(ADDONS=(FAKE,), STATICFILES_DIRS=[*settings.STATICFILES_DIRS, Path(__file__).parent / "fake_addon" / "static"])
class ScreenSeam(PhoneBase):
    """화면 이음매 — 덧붙이의 `map.js` 가 `GSMScreen` 으로 단추를 달고 다 잰 선을 받는다 (wetherilli 447).
    `map.js` 를 고치다 이 손을 깨면 여기서 먼저 안다 — 진짜 덧붙이(다른 저장소)의 화면은 GSM 의 CI 가 보지 못한다"""

    def draw_line(self, page):
        """지도 한가운데 둘레에 두 점 — 끝은 마지막 점을 다시 누른다(OpenLayers 의 Draw)"""
        # 대기 화면이 걷히기 전에 누르면 그 위를 누른다. 도구는 다시 누르면 꺼지므로 꺼져 있을 때만 누른다
        page.wait_for_function("() => !document.getElementById('splash')", timeout=15000)
        page.evaluate("""() => { const tool = document.querySelector('.tool[data-mode=line]');
                                 if (!tool.classList.contains('on')) tool.click(); }""")
        box = page.locator("#map").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for x, y in ((cx - 40, cy - 60), (cx + 40, cy + 20), (cx + 40, cy + 20)):
            page.mouse.click(x, y)
            page.wait_for_timeout(450)
        page.wait_for_timeout(400)

    def test_단추가_도구_줄에_서고_잰_선이_넘어온다(self):
        page, errors = self.open("map/?region=antarctica")
        self.assertEqual(errors, [])
        ready = page.evaluate("window.fakeAddon.ready")
        self.assertEqual((ready["base"], ready["region"], ready["length"]), ("/GSM/", "antarctica", "1.50 km"))
        # 단추는 GSM 의 도구 뒤, "지우기" 의 가름줄 앞
        order = page.eval_on_selector_all("#toolbar .tool-col:first-child > *", "els => els.map(e => e.id || e.className)")
        self.assertLess(order.index("tool-x-fake"), order.index("tool-sep"))
        self.assertEqual(page.locator("#tool-x-fake span").inner_text(), "가짜")
        self.assertFits(self.measure(page), "덧붙이의 단추가 선 도구 줄")

        # 단추가 꺼져 있으면 선은 넘어오되 GSM 의 높이 그래프가 그대로 뜬다
        self.draw_line(page)
        got = page.evaluate("window.fakeAddon.lines")
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0]["coords"]), 2)
        self.assertEqual(got[0]["line"].count(";"), 1)
        self.assertGreater(got[0]["length"], 1000)
        self.assertFalse(page.evaluate("document.getElementById('profile').hidden"))

        # 켜면 덧붙이가 그 선을 가져가고 높이 그래프는 뜨지 않는다. 새로 재기 시작하면 지움을 알린다
        page.evaluate("document.getElementById('tool-x-fake').click()")
        self.assertEqual(page.evaluate("window.fakeAddon.clicks"), [True])
        self.assertEqual(page.get_attribute("#tool-x-fake", "aria-pressed"), "true")
        clears = page.evaluate("window.fakeAddon.clears")
        self.draw_line(page)
        self.assertEqual(len(page.evaluate("window.fakeAddon.lines")), 2)
        self.assertGreater(page.evaluate("window.fakeAddon.clears"), clears)
        self.assertTrue(page.evaluate("document.getElementById('profile').hidden"))
        self.assertEqual(errors, [])
        page.context.close()

    def test_잡은_범위가_넘어오고_팝업에_줄이_붙는다(self):
        """`GSMScreen.onBox` — 덧붙이가 돌려준 요소가 범위 팝업 끝에 선다 (wetherilli 448)"""
        page, errors = self.open("map/?region=antarctica")
        page.wait_for_function("() => !document.getElementById('splash')", timeout=15000)
        page.evaluate("document.querySelector('.tool[data-mode=box]').click()")
        box = page.locator("#map").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx - 70, cy + 60)
        page.mouse.down()
        page.mouse.move(cx - 40, cy + 90, steps=4)
        page.mouse.move(cx - 10, cy + 120, steps=4)
        page.mouse.up()
        page.wait_for_function("() => document.querySelector('#popup-body #fake-box')", timeout=6000)
        got = page.evaluate("window.fakeAddon.box")
        self.assertEqual(sorted(got), ["e", "n", "no", "s", "w"])
        self.assertLess(got["s"], got["n"])
        self.assertLess(got["n"], -60)                                    # 남극 탭의 가운데 둘레다
        self.assertEqual(page.locator("#popup-body > *").last.get_attribute("id"), "fake-box")
        self.assertEqual(errors, [])
        page.context.close()

