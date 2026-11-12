"""덧붙이의 이음매 — 가짜 덧붙이(`tests/fake_addon`)로 한 번씩 지나간다 (wetherilli P19·446).

진짜 덧붙이는 다른 저장소에 있어 GSM 의 CI 가 보지 못한다. 그래서 **약속을 여기서 지킨다** — 이음매를 고쳐 이 시험이 깨지면
덧붙이도 깨진다. 덧붙이 없이 도는 것이 기본이라, 없을 때 아무것도 달라지지 않는지도 본다.
"""
import json
import os
import re
from pathlib import Path
from unittest import mock

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

    def test_가짜_덧붙이는_표의_줄마다_하나씩_갖는다(self):
        """`addons.py` 머리의 표에 줄이 늘면 가짜 덧붙이에도 하나 둔다 — 시험하지 않는 이음매가 생기지 않게"""
        here = Path(__file__).parent / "fake_addon"
        for name in ("urls.py", "fakedoor.py", "i18n.py", "datastatus.py", "data/fake_layers.json"):
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

    def test_화면의_손_표에_polargrid_가_있다(self):
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        self.assertIn("polargrid: { source: geomapSource, info: polargridInfoUrl }", js)
        self.assertIn("row.hand && LAYER_KINDS[row.hand]", js)


class Profile(TestCase):
    """차림 — 지역 탭 줄이기·따로 화면 숨기기·형제 화면의 입구. 기본은 다 꺼져 있다"""

    def test_기본은_아무것도_싣지_않는다(self):
        html = self.client.get("/GSM/map/").content.decode()
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
