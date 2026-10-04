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


class PhoneScreenTests(StaticLiveServerTestCase):
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

    # ── 화면마다 ────────────────────────────────────────────

    def test_2D_지도(self):
        self.check_map_screen("map/")

    def test_남극(self):
        self.check_map_screen("map/?region=antarctica")

    def test_모든_지역_탭(self):
        """지역 탭마다 패널 구성·범례·투영이 다르다 — 한국·남극 밖의 탭도 다 연다 (wetherilli 193). 탭 목록은 `map.js` 의
        `REGIONS` 에서 읽는다 — 새 지역(남미 따위)이 들어오면 저절로 돈다. 카탈로그가 있어야 탭이 서서 씨앗을 넣는다"""
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        js = (Path(__file__).resolve().parents[1] / "static/viewer/map.js").read_text(encoding="utf-8")
        regions = [r for r in re.findall(r"^    (\w+): \{ title: \"[^\"]+\", proj:", js, re.M)
                   if r not in ("korea", "antarctica")]
        self.assertIn("france", regions)
        for region in regions:
            with self.subTest(region=region):
                page = self.check_map_screen(f"map/?region={region}")
                page.context.close()

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
        page.wait_for_timeout(600)          # 지도가 팝업을 보이게 옮기는 동안(autoPan 200 ms)을 기다린다
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

    def test_구_화면은_범례가_접혀_열린다(self):
        for path in ("earth/", "moon/", "mars/", "mercury/"):
            with self.subTest(path=path):
                page = self.check_map_screen(path, settle=3000)
                self.assertFalse(page.evaluate("document.getElementById('legend-dock').open"),
                                 f"{path}: 범례가 구를 덮는다")
                # 화면마다 바로 닫는다 — 시험이 끝날 때까지 두면 앞의 구들이 소프트웨어 WebGL 로 계속 그려 CPU 를
                # 다 먹고, 넷째 화면(수성)이 30 초 안에 뜨지 못한다 (wetherilli 145)
                page.context.close()

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

    def test_영어판(self):
        """영어 글은 한국어보다 길다 — 지역 지도와 온 지구를 영어판으로 연다 (wetherilli 203)"""
        for path, settle in (("map/", 1500), ("earth/", 3000)):
            with self.subTest(path=path):
                page = self.check_map_screen(path, settle, lang="en")
                self.assertEqual(page.evaluate("document.documentElement.lang"), "en")
                page.context.close()

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
