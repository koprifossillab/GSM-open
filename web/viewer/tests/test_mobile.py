"""휴대폰 화면 (wetherilli 128·132).

세션마다 휴대폰 크기로 화면을 찍어 눈으로 보던 것을 시험으로 옮겼다. 390×844 터치 기기로 화면을 열어
**가로로 넘치지 않는지, 페이지 오류가 없는지, 지도 위 손잡이들이 화면 안에 있는지**만 본다 —
그림이 예쁜지는 사람이 본다.

브라우저(Playwright 의 Chromium)가 있어야 돈다. 없으면 건너뛰고, CI 의 "휴대폰 화면" job 은
`GSM_BROWSER_TESTS=1` 을 걸어 없으면 깨지게 한다. 로컬에서는

    pip install -r requirements-browser.txt && python -m playwright install chromium

상류는 타지 않는다 — 페이지·정적 파일·점묶음만 통과시키고 타일·표고·범례처럼 상류로 이어지는 요청은
브라우저에서 끊는다.
"""
import os
import re
import unittest
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command

try:
    from playwright.sync_api import sync_playwright
except ImportError:            # 운영 이미지·기본 시험에는 없다
    sync_playwright = None

REQUIRED = os.environ.get("GSM_BROWSER_TESTS") == "1"
PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}

# 화면 안에 있어야 하는 것 — 보이는 것만 잰다
PARTS = ["#panel", "#panel-handle", "#toolbar", "#coordbar", "#scalebar", ".ol-zoom", "#legend-dock",
         "#timebar", "#panel3d", "#tool-share", ".share-notice"]

MEASURE = """(sels) => {
  function box(sel) {
    const el = document.querySelector(sel);
    if (!el) return null;
    const b = el.getBoundingClientRect(), st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || !b.width || !b.height) return null;
    return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, width: b.width, height: b.height };
  }
  const out = { vw: innerWidth, vh: innerHeight, sw: document.documentElement.scrollWidth,
                body: document.body.className, parts: {} };
  sels.forEach((s) => { out.parts[s] = box(s); });
  return out;
}"""


#: 영어판 화면에 보이는 한국어 — 일부러 둔 것(한국어 이름·언어 고르개·위경도 열 이름 안내·판 이력)은 뺀다 (wetherilli 341)
HANGUL_LEAKS = """() => {
  const allowed = new Set(["대돌여지도", "한국어", "언어 · Language", "위도", "경도"]);
  const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const el = w.currentNode.parentElement, t = w.currentNode.textContent.trim();
    if (!el || !t || !/[가-힣]/.test(t) || allowed.has(t) || t.startsWith("대돌여지도 ·")) continue;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || el.closest("[hidden]") || el.closest("#notes")) continue;
    out.push(t.slice(0, 80));
  }
  return out;
}"""


class PhoneBase(StaticLiveServerTestCase):
    """여는 법과 공통 검사 — 시험은 아래 반들이 갖는다. 반마다 브라우저 하나"""

    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            if REQUIRED:
                raise RuntimeError("GSM_BROWSER_TESTS=1 인데 playwright 가 없다")
            raise unittest.SkipTest("playwright 가 없다 — requirements-browser.txt")
        # Playwright 의 동기 API 가 이벤트 루프를 돌려 Django 가 DB 를 막는다. 시험 서버는 따로 돈다
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(
                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        except Exception as e:
            cls.pw.stop()
            super().tearDownClass()
            if REQUIRED:
                raise
            raise unittest.SkipTest(f"Chromium 이 없다 — python -m playwright install chromium ({e})")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        super().tearDownClass()

    # ── 여는 법 ─────────────────────────────────────────────

    def open(self, path, settle=1500, lang=None):
        ctx = self.browser.new_context(**PHONE)
        self.addCleanup(ctx.close)
        if lang:                                    # 영어판 — 글이 길어 넘치기 쉽다 (wetherilli 203)
            ctx.add_cookies([{"name": "gsm_lang", "value": lang, "url": self.live_server_url}])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        base = self.live_server_url + "/GSM/"

        def route(r):
            url = r.request.url
            rest = url[len(base):] if url.startswith(base) else None
            if rest is None:
                return r.abort()
            if r.request.resource_type == "document" or rest.startswith(("static/", "pointsets/", "patchnotes/")):
                return r.continue_()
            return r.abort()       # 타일·표고·범례 — 상류로 이어진다

        page.route("**/*", route)
        page.goto(base + path, wait_until="load")
        page.wait_for_timeout(settle)
        return page, errors

    def measure(self, page):
        return page.evaluate(MEASURE, PARTS)

    # ── 공통 검사 ───────────────────────────────────────────

    def assertFits(self, m, where):
        self.assertLessEqual(m["sw"], m["vw"], f"{where}: 가로로 넘친다 ({m['sw']} > {m['vw']})")
        for sel, b in m["parts"].items():
            if not b:
                continue
            self.assertGreaterEqual(b["left"], -1, f"{where}: {sel} 가 왼쪽으로 나간다")
            self.assertLessEqual(b["right"], m["vw"] + 1, f"{where}: {sel} 가 오른쪽으로 나간다")
            self.assertGreaterEqual(b["top"], -1, f"{where}: {sel} 가 위로 나간다")
            self.assertLessEqual(b["bottom"], m["vh"] + 1, f"{where}: {sel} 가 아래로 나간다")

    def check_map_screen(self, path, settle=1500, lang=None):
        """2D·구 화면 — 패널이 접힌 채로 열려 지도가 화면을 차지하고, 손잡이가 아이콘 한 줄이다."""
        page, errors = self.open(path, settle, lang)
        self.assertEqual(errors, [], f"{path}: 페이지 오류")
        m = self.measure(page)
        self.assertFits(m, path)
        self.assertIn("panel-folded", m["body"], f"{path}: 휴대폰은 패널이 접힌 채로 열린다")
        wrap = page.locator("#map-wrap").bounding_box()
        self.assertGreaterEqual(wrap["height"], 0.75 * m["vh"], f"{path}: 지도 칸이 낮다")
        tools, bar = m["parts"]["#toolbar"], m["parts"]["#coordbar"]
        self.assertLessEqual(tools["width"], 60, f"{path}: 손잡이 묶음이 한 줄이 아니다")
        self.assertLessEqual(tools["bottom"], bar["top"] + 1, f"{path}: 손잡이 묶음이 좌표 막대를 덮는다")
        self.assertFalse(page.locator(".tool-cap").first.is_visible(), f"{path}: 이름표는 뗀다")

        # 펴면 패널이 위에 서고, 지역 탭이 눌려 찌그러지지 않는다. 다시 접힌다
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        m = self.measure(page)
        self.assertNotIn("panel-folded", m["body"])
        self.assertFits(m, path + " (편 패널)")
        self.assertGreaterEqual(page.locator("#panel > .regions").bounding_box()["height"], 28,
                                f"{path}: 편 패널에서 지역 탭이 찌그러진다")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        self.assertIn("panel-folded", self.measure(page)["body"])
        return page


class PhoneScreenTests(PhoneBase):
    # ── 화면마다 ────────────────────────────────────────────

    def test_2D_지도(self):
        self.check_map_screen("map/")

    def test_남극(self):
        self.check_map_screen("map/?region=antarctica")

    def test_지역_탭은_다_나뉘어_돈다(self):
        """지역 탭은 아래 `RegionTabs*` 반들이 나눠 연다 — 나눔이 탭을 빠뜨리지 않는다"""
        regions = region_tabs()
        self.assertIn("france", regions)
        self.assertEqual(sorted(sum((region_tabs(k) for k in range(SHARDS)), [])), sorted(regions))

    def test_지역_접기(self):
        """탭 줄에는 한국·북극·남극만 서고 나머지는 "그 외" 하나로 접힌다. 접힌 지역을 보면 단추가 그 이름이 되고,
        차림이 휴대폰 화면 안에 선다 (wetherilli 214)"""
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        page, errors = self.open("map/?region=canada")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        tabs = page.evaluate("[...document.querySelectorAll('#regions > .region-tab')].map(b => b.dataset.region)")
        self.assertEqual(tabs, ["korea", "arctic", "antarctica"])
        fold = page.locator("#regions .region-fold")
        self.assertTrue(fold.inner_text().startswith("캐나다"), "접힌 지역을 보는데 단추가 그 이름이 아니다")
        self.assertIn("on", fold.get_attribute("class"))
        fold.tap()
        page.wait_for_timeout(200)
        menu = page.locator("#regions .region-menu")
        self.assertTrue(menu.is_visible())
        box = menu.bounding_box()
        self.assertLessEqual(box["x"] + box["width"], 390 + 0.5, "차림이 화면 밖으로 넘친다")
        self.assertLessEqual(box["y"] + box["height"], 844 + 0.5, "차림이 화면 밑으로 넘친다")
        # 휴대폰의 탭 줄은 가로로 굴러 넘친 것을 자른다 — 차림이 그 밑에 묻히지 않는다
        self.assertTrue(page.evaluate("""() => { const m = document.querySelector('#regions .region-menu'), b = m.getBoundingClientRect();
            const hit = document.elementFromPoint(b.left + 20, b.top + 15); return m.contains(hit); }"""), "차림이 다른 것에 덮인다")
        page.locator('#regions .region-menu li[data-region="mexico"]').tap()       # "+ 추가 지역" 칸에서 더한다
        page.wait_for_timeout(800)
        self.assertEqual(page.evaluate("document.documentElement.dataset.region"), "mexico")
        self.assertTrue(page.locator("#regions .region-fold").inner_text().startswith("멕시코"))
        self.assertIn("mexico", page.evaluate("JSON.parse(localStorage.getItem('gsm.regions'))"))
        page.locator('#regions > .region-tab[data-region="arctic"]').tap()
        page.wait_for_timeout(800)
        self.assertTrue(page.locator("#regions .region-fold").inner_text().startswith("그 외"))
        self.assertEqual(errors, [])

    def test_레이어_찾기(self):
        """레이어 찾기 칸은 모든 지역을 훑고, 다른 지역의 레이어를 고르면 그 탭으로 옮겨 켠다. 맞는 줄이 휴대폰 화면 안에 선다 (wetherilli 332)"""
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        page, errors = self.open("map/")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        page.locator("#layer-find").fill("nrcan 리튬")
        page.wait_for_timeout(200)
        rows = page.locator("#layer-found .layer-row")
        self.assertEqual(rows.count(), 1, "캐나다 리튬 유망도가 하나로 찾아지지 않는다")
        self.assertFits(self.measure(page), "레이어 찾기")
        name = rows.first.get_attribute("data-layer")
        self.assertTrue(name.startswith("nrcan:"), name)
        self.assertIn("캐나다", rows.first.inner_text())
        rows.first.tap()
        page.wait_for_timeout(800)
        self.assertEqual(page.evaluate("document.documentElement.dataset.region"), "canada")
        self.assertIn("on", page.locator(f'#layer-catalog .layer-row[data-layer="{name}"]').get_attribute("class"), "옮긴 탭에서 켜지지 않았다")
        self.assertIn("canada", page.evaluate("JSON.parse(localStorage.getItem('gsm.regions'))"))
        page.locator("#layer-find").fill("맞을리없는낱말")
        page.wait_for_timeout(100)
        self.assertEqual(page.locator("#layer-found .layer-row").count(), 0)
        self.assertEqual(errors, [])

    def test_팝업이_화면_안에_선다(self):
        """속성 팝업 하나를 띄워 390 px 안에 서는지, 닫기 단추가 손에 닿는지 본다. 상류를 끊으므로 점묶음의 점을 지도
        한가운데(한국 탭의 처음 자리)에 두고 누른다"""
        from viewer.models import Point, PointSet
        ps = PointSet.objects.create(name="휴대폰 팝업", color="#e4572e")
        Point.objects.create(pointset=ps, lat=36.2, lon=127.8, label="가운데",
                             props={"암상": "화강암", "비고": "아주 긴 설명이 붙은 시료 — " * 6})
        page, errors = self.open("map/", settle=2500)
        box = page.locator("#map").bounding_box()
        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_selector("#popup.on", timeout=5000)
        # 뜬 그 틀에도 화면 안이어야 한다 — 가운데 맞춤이 먹지 않아 오른쪽 아래로 늘어졌다가 지도가 끌려 와 들어오던 것을 잡는다.
        # 그 끌림 한가운데를 재면 느린 CI 에서만 깨졌다 (wetherilli 304)
        page.evaluate("() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)))")
        self.assertFits(page.evaluate(MEASURE, PARTS + ["#popup", "#popup-close"]), "map/ (팝업이 뜬 틀)")
        page.wait_for_timeout(600)          # 속성이 다 차 팝업을 한 번 더 끌어오는 동안(200 ms)을 기다린다
        self.assertEqual(errors, [])
        m = page.evaluate(MEASURE, PARTS + ["#popup", "#popup-close"])
        self.assertFits(m, "map/ (팝업)")
        close = m["parts"]["#popup-close"]
        self.assertIsNotNone(close, "닫기 단추가 보이지 않는다")
        self.assertGreaterEqual(min(close["width"], close["height"]), 20, "닫기 단추가 손가락에 작다")
        # 다른 것(도구 묶음 따위)이 닫기 단추를 덮지 않는다
        self.assertTrue(page.evaluate("""() => { const c = document.getElementById('popup-close'), b = c.getBoundingClientRect();
            const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return c === hit || c.contains(hit); }"""),
                        "닫기 단추가 다른 것에 덮인다")
        page.tap("#popup-close")
        page.wait_for_timeout(300)
        self.assertFalse(page.locator("#popup.on").count(), "팝업이 닫히지 않는다")
        self.assertTrue(page.locator("#toolbar").is_visible(), "팝업을 닫으면 도구 묶음이 돌아온다")

    def test_공유_링크로_연다(self):
        """링크로 열면 그 지역·레이어로 서고, 띠가 화면 안에 뜨고, 그 사람의 기억은 그대로다 (wetherilli 189)"""
        page, errors = self.open("map/#r=antarctica&c=0,-90&z=2&p=3031&l=geomap_simple_geology*80&b=")
        self.assertEqual(errors, [])
        self.assertTrue(page.locator(".share-notice").is_visible(), "링크로 연 띠가 없다")
        self.assertFits(self.measure(page), "map/ (공유 링크)")
        self.assertEqual(page.evaluate("document.documentElement.dataset.region"), "antarctica")
        self.assertEqual(page.evaluate("location.hash"), "", "해시는 읽고 지운다")
        self.assertIsNone(page.evaluate("localStorage.getItem('gsm.region')"), "그 사람의 기억을 덮는다")
        self.assertIsNone(page.evaluate("localStorage.getItem('gsm.layers.antarctica')"))
        self.assertTrue(page.locator("#tool-share").is_visible())

    def test_설정_창(self):
        """설정 창(판 이력·언어·기억 지우기)이 휴대폰 화면 안에 선다 (wetherilli 203)"""
        page, errors = self.open("map/")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        page.tap("#gear")
        page.wait_for_timeout(800)
        self.assertEqual(errors, [])
        box = page.locator("#settings .sheet-box").bounding_box()
        m = self.measure(page)
        self.assertFits(m, "map/ (설정 창)")
        self.assertGreaterEqual(box["x"], -1)
        self.assertLessEqual(box["x"] + box["width"], m["vw"] + 1, "설정 창이 오른쪽으로 나간다")
        self.assertTrue(page.locator("#settings-close").is_visible())
        page.tap("#settings-close")
        page.wait_for_timeout(200)
        self.assertTrue(page.locator("#settings").is_hidden())

    def test_3D_판은_접혀_열린다(self):
        page, errors = self.open("3d/", settle=2000)
        self.assertEqual(errors, [])
        m = self.measure(page)
        self.assertFits(m, "3d/")
        self.assertLess(m["parts"]["#panel3d"]["height"], 80, "3D 판이 접힌 채로 열리지 않는다")
        page.tap("#fold3d")
        page.wait_for_timeout(300)
        m = self.measure(page)
        self.assertGreater(m["parts"]["#panel3d"]["height"], 200)
        self.assertFits(m, "3d/ (편 판)")

    def test_관리와_소개(self):
        for path in ("manage/", ""):
            with self.subTest(path=path or "intro"):
                page, errors = self.open(path)
                self.assertEqual(errors, [], f"{path}: 페이지 오류")
                self.assertFits(self.measure(page), path or "intro")



class GlobeScreens(PhoneBase):
    """구 화면(Cesium 소프트웨어 WebGL)은 한 장에 3 초를 기다린다 — 따로 반으로 두어 `--parallel` 이 나란히 돌린다 (wetherilli 294)"""

    def test_구_화면은_범례가_접혀_열린다(self):
        for path in ("earth/", "moon/", "mars/", "mercury/"):
            with self.subTest(path=path):
                page = self.check_map_screen(path, settle=3000)
                self.assertFalse(page.evaluate("document.getElementById('legend-dock').open"),
                                 f"{path}: 범례가 구를 덮는다")
                # 화면마다 바로 닫는다 — 시험이 끝날 때까지 두면 앞의 구들이 소프트웨어 WebGL 로 계속 그려 CPU 를
                # 다 먹고, 넷째 화면(수성)이 30 초 안에 뜨지 못한다 (wetherilli 145)
                page.context.close()

    def test_영어판(self):
        """영어 글은 한국어보다 길다 — 지역 지도와 온 지구를 영어판으로 연다 (wetherilli 203)"""
        for path, settle in (("map/", 1500), ("earth/", 3000)):
            with self.subTest(path=path):
                page = self.check_map_screen(path, settle, lang="en")
                self.assertEqual(page.evaluate("document.documentElement.lang"), "en")
                # 한국어가 새지 않는다 (wetherilli 341) — 한국어 이름(대돌여지도·그 밑줄), 언어 고르개, 판 이력(옮기지 않는다)만 뺀다
                leaks = page.evaluate(HANGUL_LEAKS)
                self.assertEqual(leaks, [], f"{path}: 영어판에 한국어가 샌다")
                page.context.close()

# ── 지역 탭 전부 (wetherilli 193) ───────────────────────────
# 쉰 남짓한 탭을 한 시험에서 열면 4 분이 든다(탭마다 4 초). 반 여섯으로 나눠 `--parallel` 이 나란히 돌린다 — 지키는 것은 같다 (wetherilli 294)

SHARDS = 6


def region_tabs(shard=None) -> list:
    """`map.js` 의 `REGIONS` 에서 한국·남극 밖의 탭 — 새 지역(남미 따위)이 들어오면 저절로 돈다. `shard` 를 주면 그 몫만"""
    js = (Path(__file__).resolve().parents[1] / "static/viewer/map.js").read_text(encoding="utf-8")
    regions = [r for r in re.findall(r"^    (\w+): \{ title: \"[^\"]+\", proj:", js, re.M) if r not in ("korea", "antarctica")]
    return regions if shard is None else regions[shard::SHARDS]


class PlanetFlows(PhoneBase):
    """달·화성·수성 화면을 손가락으로 써 본다 — 거리 재기와 높이 그래프, 극 평면, 공유 (wetherilli 342).
    표고는 상류라 끊긴다 — 높이 그래프의 판이 뜨는지·자리가 맞는지만 본다"""

    BOX = "(s) => { const e = document.querySelector(s); if (!e || e.hidden) return null; const b = e.getBoundingClientRect(); " \
          "return b.width ? {left: b.left, top: b.top, right: b.right, bottom: b.bottom, width: b.width} : null; }"

    def box(self, page, sel):
        return page.evaluate(self.BOX, sel)

    def assertApart(self, a, b, what):
        if a and b:
            self.assertTrue(a["right"] <= b["left"] or b["right"] <= a["left"] or a["bottom"] <= b["top"] or b["bottom"] <= a["top"],
                            f"{what}: 겹친다 {a} {b}")

    def test_손가락으로_거리를_재면_높이_그래프가_뜬다(self):
        """툴바 상자가 지도를 덮어 둘째 점이 먹히고, 터치에는 두 번 누르기가 오지 않아 선이 끝나지 않았다.
        이제 마지막 점을 다시 누르면 끝난다. 그래프는 화면 안·범례 머리 위에 선다"""
        for body in ("moon", "mars", "mercury"):
            with self.subTest(body=body):
                page, errors = self.open(f"{body}/", settle=4000)
                page.tap('[data-draw="line"]')
                page.wait_for_timeout(300)
                self.assertApart(self.box(page, "#tool-out"), self.box(page, "#panel-handle"), f"{body}: 그리기 안내와 패널 손잡이")
                page.touchscreen.tap(150, 450)
                page.wait_for_timeout(400)
                page.touchscreen.tap(250, 500)          # 툴바 상자가 덮던 자리
                page.wait_for_timeout(400)
                page.touchscreen.tap(250, 500)          # 마지막 점을 다시 — 끝
                page.wait_for_timeout(1500)
                profile = self.box(page, "#profile")
                self.assertIsNotNone(profile, f"{body}: 거리 재기가 끝나지 않는다(높이 그래프가 없다)")
                self.assertGreaterEqual(profile["left"], -1)
                self.assertLessEqual(profile["right"], 391, f"{body}: 높이 그래프가 오른쪽으로 넘친다")
                legend = self.box(page, "#legend-dock")
                if legend:
                    self.assertLessEqual(profile["bottom"], legend["top"] + 1, f"{body}: 높이 그래프가 범례 밑에 깔린다")
                self.assertIn("km", page.locator("#tool-out").inner_text())
                self.assertFits(self.measure(page), f"{body} 높이 그래프")
                self.assertEqual(errors, [])
                page.context.close()

    def test_평면은_극으로_넘어가고_축척_막대가_가리지_않는다(self):
        page, errors = self.open("moon/", settle=4000)
        page.tap("#tool-mode")
        page.wait_for_timeout(1500)
        page.fill("#goto-input", "80, 30")
        page.press("#goto-input", "Enter")
        page.wait_for_timeout(2000)
        self.assertEqual(page.evaluate("window.__gsmMoonFlat.getView().getProjection().getCode()"), "IAU_2015:30130")
        self.assertApart(self.box(page, "#scalebar"), self.box(page, "#legend-dock"), "축척 막대와 범례")
        self.assertFits(self.measure(page), "달 극 평면")
        self.assertEqual(errors, [])

    def test_링크를_복사하면_띠가_뜨고_링크로_연_알림은_넓다(self):
        page, errors = self.open("moon/", settle=4000)
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.live_server_url)
        page.tap("#tool-share")
        page.wait_for_timeout(300)
        self.assertTrue(page.locator(".share-toast").is_visible(), "복사했다는 것이 보이지 않는다 — 휴대폰은 단추의 이름표가 숨는다")
        page.context.close()
        page, errors = self.open("moon/#m=flat&l=units*60&c=40.00000,-20.00000&res=94", settle=4000)
        notice = self.box(page, ".share-notice")
        self.assertIsNotNone(notice)
        self.assertGreaterEqual(notice["width"], 300, "링크로 연 알림이 좁아 글이 서너 자씩 꺾인다")
        self.assertApart(notice, self.box(page, "#scalebar"), "링크 알림과 축척 막대")
        self.assertApart(notice, self.box(page, "#legend-dock"), "링크 알림과 범례")
        self.assertEqual(errors, [])


class RegionTabs(PhoneBase):
    """지역 탭마다 패널 구성·범례·투영이 다르다 — 한국·남극 밖의 탭도 다 연다. 카탈로그가 있어야 탭이 서서 씨앗을 넣는다"""
    shard = None

    def run_tabs(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        for region in region_tabs(self.shard):
            with self.subTest(region=region):
                page = self.check_map_screen(f"map/?region={region}")
                page.context.close()


def _shard(k):
    def test_모든_지역_탭(self):
        self.run_tabs()
    return type(f"RegionTabs{k}", (RegionTabs,), {"shard": k, "test_모든_지역_탭": test_모든_지역_탭, "__module__": __name__})


for _k in range(SHARDS):
    globals()[f"RegionTabs{_k}"] = _shard(_k)


class PointsetsAcrossProjections(PhoneBase):
    """점묶음이 지역마다의 투영(3978·3413·3031·3857)에서 제자리에 선다 — "이 자료로 범위를 맞춘다" 를 누르면 보던 자리가 그 점이다
    (wetherilli 343, 지역이 쉰이 되며 캐나다 람베르트·극 평사도법 탭이 늘었다)"""
    PLACES = {"ottawa": (-75.70, 45.42), "longyearbyen": (15.63, 78.22), "mcmurdo": (166.67, -77.85), "lima": (-77.03, -12.05)}
    TABS = (("canada", "ottawa", "EPSG:3978"), ("svalbard", "longyearbyen", "EPSG:3413"),
            ("antarctica", "mcmurdo", "EPSG:3031"), ("peru", "lima", "EPSG:3857"))

    def setUp(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))

    def test_범위를_맞추면_그_점이다(self):
        for region, place, proj in self.TABS:
            self.fit_and_check(region, place, proj)

    def test_점이_오기_전에_눌러도_그_점이다(self):
        """점(GeoJSON)이 오기 전에 누르면 범위가 비어 아무 일도 없었다 — 느린 CI 의 3978 탭에서 가끔 처음 자리에 남았다(wetherilli 352).
        점을 붙잡아 두었다가 누른 뒤에 내준다"""
        self.fit_and_check("canada", "ottawa", "EPSG:3978", hold=True)

    def fit_and_check(self, region, place, proj, hold=False):
        import json
        from viewer.models import Point, PointSet
        base = self.live_server_url + "/GSM/"
        held = []
        # 점묶음은 탭마다 하나만 — 여럿이면 화면이 덩이를 한꺼번에 묻고, 시험 서버의 메모리 sqlite 가 스레드끼리 부딪힌다
        PointSet.objects.all().delete()
        lon, lat = self.PLACES[place]
        ps = PointSet.objects.create(name=place, color="#e4572e")
        Point.objects.create(pointset=ps, label=place, lat=lat, lon=lon)
        ctx = self.browser.new_context(**PHONE)
        self.addCleanup(ctx.close)
        ctx.add_init_script(f"localStorage.setItem('gsm.region', '{region}');"
                            f"localStorage.setItem('gsm.regions', JSON.stringify(['{region}']));")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def route(r):
            rest = r.request.url[len(base):] if r.request.url.startswith(base) else None
            if hold and rest is not None and rest.startswith("pointsets/") and rest.endswith("/geojson/"):
                return held.append(r)          # 누른 뒤에 내준다
            if rest is not None and (r.request.resource_type == "document" or rest.startswith(("static/", "pointsets/", "patchnotes/"))):
                return r.continue_()
            return r.abort()
        page.route("**/*", route)
        page.goto(base + "map/", wait_until="load")
        page.wait_for_timeout(1500)
        if hold:
            self.assertTrue(held, "점을 붙잡지 못했다 — 화면이 점을 묻지 않았다")
        clicked = page.evaluate("""(place) => {
            const li = [...document.querySelectorAll('#pointset-list li')].find(l => l.textContent.includes(place));
            const b = li && [...li.querySelectorAll('button')].find(x => x.textContent.includes('⊙'));
            if (!b) return false; b.click(); return true; }""", place)
        self.assertTrue(clicked, region)
        if hold:
            page.wait_for_timeout(500)
            for r in held:
                r.continue_()
        # 맞추기는 300 ms 애니메이션이고 자리는 그것이 끝날 때(`moveend`) 저장된다 — 고정으로 기다리지 않고 그 자리가 오기를 기다린다.
        # 끝내 오지 않으면 아래의 같은 검사가 깨진다
        try:
            page.wait_for_function("""([key, lon, lat]) => { const v = JSON.parse(localStorage.getItem(key) || 'null');
                return v && Math.abs(v.lon - lon) < 0.01 && Math.abs(v.lat - lat) < 0.01; }""",
                                   arg=[f"gsm.view.{region}", lon, lat], timeout=6000)
        except Exception:
            pass
        view = json.loads(page.evaluate(f"() => localStorage.getItem('gsm.view.{region}')") or "null")
        self.assertEqual(view["proj"], proj)
        self.assertAlmostEqual(view["lon"], lon, delta=0.01, msg=region)
        self.assertAlmostEqual(view["lat"], lat, delta=0.01, msg=region)
        self.assertEqual(errors, [], region)
