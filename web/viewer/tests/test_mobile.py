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
import sys
import time
import unittest
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
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
        # 깨졌을 때 까닭을 적으려고 콘솔도 받아 둔다 — 검사하지는 않는다 (jikhanjung 010)
        page.gsm_console = []
        page.on("console", lambda m: page.gsm_console.append(f"{m.type}: {m.text}"[:200]))
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

    def test_저장_탭은_카드로_단추가_보인다(self):
        """저장 탭의 표는 칸이 일곱이라 지우기·내려받기 단추가 가로로 굴려야 보였다 — 휴대폰에서는 카드로 세운다 (wetherilli 369)"""
        page, errors = self.open("manage/")
        page.tap("#mg-ex-try")
        page.wait_for_timeout(800)
        page.tap("#mg-save")
        page.wait_for_timeout(800)
        page.tap('#mg-tabs [data-tab="stored"]')
        page.wait_for_selector("#mg-layers .mg-row-acts button", timeout=15000)   # IndexedDB 저장·다시 그리기를 기다린다 — 고정 대기는 느린 CI 에서 깨진다
        buttons = page.evaluate("""() => [...document.querySelectorAll('#mg-layers .mg-row-acts button')].map(b => {
            const r = b.getBoundingClientRect(); return [b.textContent, r.left, r.right]; })""")
        self.assertTrue(buttons, "저장한 개인 레이어의 단추가 없다")
        for text, left, right in buttons:
            self.assertGreaterEqual(left, 0, f"'{text}' 단추가 왼쪽 밖이다")
            self.assertLessEqual(right, 390, f"'{text}' 단추가 굴려야 보인다")
        scroll = page.evaluate("(() => { const e = document.getElementById('mg-layers').closest('.mg-scroll'); return [e.scrollWidth, e.clientWidth]; })()")
        self.assertLessEqual(scroll[0], scroll[1] + 1, "저장 탭의 표가 가로로 구른다")
        self.assertFits(self.measure(page), "manage stored")
        self.assertEqual(errors, [])

    def test_데이터소스_탭은_카드로_서고_누르면_지난_차례가_펼쳐진다(self):
        """칸이 여섯이라 가로로 굴렀다 — 휴대폰에서는 카드로 (jikhanjung P02 3 단계)"""
        page, errors = self.open("manage/")
        page.tap('#mg-tabs [data-tab="sources"]')
        page.wait_for_selector("#mg-sources tr.mg-src", timeout=10000)
        scroll = page.evaluate("(() => { const e = document.getElementById('mg-sources').closest('.mg-scroll'); return [e.scrollWidth, e.clientWidth]; })()")
        self.assertLessEqual(scroll[0], scroll[1] + 1, "데이터소스 표가 가로로 구른다")
        first = page.locator("#mg-sources tr.mg-src").first
        src = first.get_attribute("data-src")
        first.tap()
        page.wait_for_timeout(300)
        self.assertTrue(page.locator(f'#mg-sources tr.mg-src-more[data-for="{src}"]').is_visible(), "눌러도 펼쳐지지 않는다")
        self.assertEqual(first.locator(".mg-src-toggle").get_attribute("aria-expanded"), "true")
        self.assertFits(self.measure(page), "manage sources")
        self.assertEqual(errors, [])

    def test_관리와_소개(self):
        for path in ("manage/", ""):
            with self.subTest(path=path or "intro"):
                page, errors = self.open(path)
                self.assertEqual(errors, [], f"{path}: 페이지 오류")
                self.assertFits(self.measure(page), path or "intro")

    def test_소개는_휴대폰에서도_언어를_바꾼다(self):
        """머리줄의 언어 단추는 휴대폰에서 숨는다(자리가 없다) — 그러면 바꿀 길이 없었다. 끝에 같은 단추가 선다 (wetherilli 365)"""
        page, errors = self.open("")
        other = page.locator('.langs button[data-lang="en"]:visible')
        self.assertEqual(other.count(), 1, "휴대폰에서 언어를 바꿀 단추가 보이지 않는다")
        other.scroll_into_view_if_needed()
        other.tap()
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        self.assertEqual(page.evaluate("document.documentElement.lang"), "en")
        self.assertEqual(page.locator('.langs button[data-lang="ko"]:visible').count(), 1, "영어판에서 한국어로 돌아올 단추가 없다")
        self.assertFits(self.measure(page), "intro en")
        self.assertEqual(errors, [])

    def test_소개_다시_보지_않기(self):
        """"지도로 바로 가기" 밑의 체크 — 고르면 다음부터 뿌리에서 곧장 지도로, 지도의 "대돌여지도 소개"(`?intro=1`)에서 풀 수 있다 (jikhanjung 021)"""
        page, errors = self.open("")
        keep = page.locator("#skip-intro")
        self.assertTrue(keep.is_visible(), "체크가 보이지 않는다")
        self.assertFits(self.measure(page), "intro skip box")
        keep.tap()
        self.assertEqual(page.evaluate("localStorage.getItem('gsm.intro.skip')"), "1")
        page.goto(self.live_server_url + "/GSM/", wait_until="load")
        self.assertTrue(page.url.endswith("/GSM/map/"), page.url)                 # 소개를 건너 지도로
        page.goto(self.live_server_url + "/GSM/?intro=1", wait_until="load")      # 지도의 "대돌여지도 소개"
        self.assertTrue(page.url.endswith("/GSM/?intro=1"), page.url)
        keep = page.locator("#skip-intro")
        self.assertTrue(keep.is_checked())
        keep.tap()
        self.assertIsNone(page.evaluate("localStorage.getItem('gsm.intro.skip')"))
        page.goto(self.live_server_url + "/GSM/", wait_until="load")
        self.assertTrue(page.url.endswith("/GSM/"), page.url)                     # 풀면 다시 소개
        self.assertEqual(errors, [])

    def test_관리_화면의_상자_제목은_한_줄이다(self):
        """제목 옆의 안내 글이 제목을 밀어 "개인 레이 / 어" 처럼 꺾였다 — 휴대폰에서 안내는 다음 줄로 (wetherilli 365)"""
        page, errors = self.open("manage/")
        for tab in ("import", "stored", "upstream", "sources"):
            page.tap(f'#mg-tabs [data-tab="{tab}"]')
            page.wait_for_timeout(300)
            lines = page.evaluate("""() => [...document.querySelectorAll('.mg-body.on .box-head')].map(h => {
                const t = [...h.childNodes].find(n => n.nodeType === 3 && n.textContent.trim()); if (!t) return null;
                const r = document.createRange(); r.selectNodeContents(t); const n = r.getClientRects().length;
                return n ? [t.textContent.trim(), n] : null; }).filter(Boolean)""")
            for title, n in lines:
                self.assertEqual(n, 1, f"{tab}: 상자 제목 '{title}' 이 꺾였다")
            self.assertFits(self.measure(page), f"manage {tab}")
        self.assertEqual(errors, [])



class GlobeScreens(PhoneBase):
    """구 화면(Cesium 소프트웨어 WebGL)은 한 장에 3 초를 기다린다 — 따로 반으로 두어 `--parallel` 이 나란히 돌린다 (wetherilli 294)"""

    def test_구_화면은_범례가_접혀_열린다(self):
        for path in ("earth/", "moon/", "mars/", "mercury/"):
            with self.subTest(path=path):
                page = self.check_map_screen(path, settle=3000)
                self.assertFalse(page.evaluate("document.getElementById('legend-dock').open"),
                                 f"{path}: 범례가 구를 덮는다")
                # 레이어 목록의 줄마다 출처가 선다 — 켜기 전에도 무엇을 얹는지 보인다 (wetherilli 360)
                bare = page.evaluate("[...document.querySelectorAll('#layer-catalog .layer-row')]"
                                     ".filter(r => !(r.querySelector('.src') || {}).textContent).map(r => r.textContent.trim())")
                self.assertEqual(bare, [], f"{path}: 출처가 빈 레이어")
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


class RegionCompare(PhoneBase):
    """주제도 비교 — 나란히 보기를 켰다 끄면 왼쪽 지도까지 깨졌다(축척 1:150 억, 줌이 비고 누른 자리가 다른 반구로).
    숨은 오른쪽 지도가 보기를 나눠 쥔 채 크기 0 으로 재어졌다. 이름표는 휴대폰에서 서로·손잡이·툴바와 겹쳤다 (wetherilli 356)"""

    BOX = "(s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); " \
          "return b.width ? {left: b.left, top: b.top, right: b.right, bottom: b.bottom} : null; }"

    def assertApart(self, a, b, what):
        if a and b:
            self.assertTrue(a["right"] <= b["left"] or b["right"] <= a["left"] or a["bottom"] <= b["top"] or b["bottom"] <= a["top"],
                            f"{what}: 겹친다 {a} {b}")

    def test_나란히_보기를_끄면_지도가_그대로다(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        for region in ("svalbard", "canada"):
            with self.subTest(region=region):
                page, errors = self.open(f"map/?region={region}")
                before = page.locator("#zoombadge").inner_text()
                self.assertIn("줌", before)
                page.tap("#panel-handle")
                page.wait_for_timeout(300)
                page.evaluate("document.querySelectorAll('#layer-catalog details').forEach(d => d.open = true)")
                page.locator("#layer-catalog .layer-row:not(.on)").first.click()
                page.wait_for_timeout(300)
                page.locator('[data-cmp="split"]').click()
                page.wait_for_timeout(800)
                page.tap("#panel-handle")
                page.wait_for_timeout(400)
                left, right = page.evaluate(self.BOX, "#split-left"), page.evaluate(self.BOX, "#split-right")
                self.assertApart(left, right, f"{region}: 두 이름표")
                self.assertApart(left, page.evaluate(self.BOX, "#panel-handle"), f"{region}: 왼쪽 이름표와 손잡이")
                self.assertApart(right, page.evaluate(self.BOX, "#panel-handle"), f"{region}: 오른쪽 이름표와 손잡이")
                self.assertApart(right, page.evaluate(self.BOX, "#toolbar .tool-col"), f"{region}: 오른쪽 이름표와 툴바")
                page.tap("#panel-handle")
                page.wait_for_timeout(300)
                page.locator('[data-cmp="off"]').click()
                page.wait_for_timeout(800)
                self.assertEqual(page.locator("#zoombadge").inner_text(), before, f"{region}: 나란히 보기를 끄니 줌이 바뀌었다(지도가 깨졌다)")
                view = page.evaluate(f"JSON.parse(localStorage.getItem('gsm.view.{region}') || 'null')")
                self.assertIsNotNone(view and view.get("zoom"), f"{region}: 저장된 줌이 비었다")
                self.assertEqual(errors, [])
                page.context.close()


class Phone3D(PhoneBase):
    """3D(MapLibre)를 손가락으로 — 점묶음의 점을 누르면 팝업이 화면 안에 선다. 최대 폭 320 px 이면 390 px 화면에서
    MapLibre 가 어느 쪽에 붙여도 넘쳤다(오른쪽으로 85 px, wetherilli 362)"""

    #: 3D 의 첫 화면(`map.on("load")`)을 기다리는 시간. 휴대폰 job 이 이것을 넘겨 가끔 깨졌는데(10/05–06), 느린 러너
    #: 탓이 아니라 MapLibre 가 늦게 실패한 타일 뒤에 `load` 를 쏘지 않던 것이었다 — 60 초를 줘도 깨졌다. `map3d.js` 가
    #: 실패마다 다시 그리게 고쳤다. 기다림은 원래대로 두고, 넘기면 까닭을 적는다 (jikhanjung 010)
    READY_TIMEOUT = 15

    def wait_ready(self, page, started):
        """3D 가 뜰 때까지. 넘기면 상태·콘솔을 실패 글에 적고, 화면을 열기 시작한 때(`started`)부터 걸린 초는 늘
        기록에 남긴다 — 다음에 느려지면 견줄 수 있게."""
        try:
            page.wait_for_function("window.__gsm3dReady", timeout=self.READY_TIMEOUT * 1000)
        except PlaywrightTimeout:
            state = page.evaluate("""() => { const m = window.__gsm3d;
                return { map: !!m, styleLoaded: m ? m.isStyleLoaded() : null, loaded: m ? m.loaded() : null,
                         webgl: !!document.createElement("canvas").getContext("webgl") }; }""")
            self.fail(f"3D 가 {self.READY_TIMEOUT} 초 안에 뜨지 않았다 — 상태 {state}, "
                      f"콘솔 끝 {getattr(page, 'gsm_console', [])[-8:]}")
        print(f"\n3D 첫 화면 {time.monotonic() - started:.1f} 초", file=sys.stderr, flush=True)

    def test_늦게_실패한_타일에도_3D_가_뜬다(self):
        """마지막 타일이 마지막 그리기보다 늦게 실패하면 MapLibre 가 `load` 를 쏘지 않았다 — 실패한 타일은 다시
        그리기를 부르지 않기 때문이다. 휴대폰 job 이 가끔 깨진 까닭이 이것이었다(`loaded()` 는 참인데 신호가 없다).
        지형 타일의 실패를 첫 그리기 뒤로 미뤄 그 순서를 늘 만든다 (jikhanjung 010)"""
        ctx = self.browser.new_context(**PHONE)
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        base = self.live_server_url + "/GSM/"
        held = []

        def route(r):
            url = r.request.url
            rest = url[len(base):] if url.startswith(base) else None
            if rest is not None and (r.request.resource_type == "document" or rest.startswith(("static/", "pointsets/"))):
                return r.continue_()
            if not held and ("terrarium" in url or "/dem/" in url):
                held.append(url)
                time.sleep(2.5)     # 동기 API 라 이 사이 다른 요청도 줄을 선다 — 다 함께 늦게 실패한다
            return r.abort()

        page.route("**/*", route)
        page.goto(base + "3d/?lat=36.36&lon=127.39&z=12&region=korea", wait_until="load")
        started = time.monotonic()
        self.wait_ready(page, started)
        self.assertTrue(held, "지형 타일을 부르지 않았다 — 시험이 경합을 만들지 못했다")

    def test_점을_누르면_팝업이_화면_안이다(self):
        from viewer.models import Point, PointSet
        ps = PointSet.objects.create(name="대전 시료", color="#e4572e")
        Point.objects.create(pointset=ps, label="시료 1", lat=36.35, lon=127.38,
                             props={"암석": "화강암", "비고": "설명이 긴 시료라 팝업이 넓어진다 " * 4})
        started = time.monotonic()
        page, errors = self.open("3d/?lat=36.36&lon=127.39&z=12&region=korea", settle=3000)
        self.wait_ready(page, started)
        page.wait_for_timeout(1500)
        x, y = page.evaluate("(() => { const p = window.__gsm3d.project([127.38, 36.35]); return [p.x, p.y]; })()")
        self.assertTrue(0 < x < 390 and 0 < y < 844, "점이 화면 밖이다")
        page.touchscreen.tap(x, y)
        page.wait_for_timeout(1000)
        popup = page.locator(".maplibregl-popup")
        self.assertEqual(popup.count(), 1, "점을 눌렀는데 팝업이 뜨지 않는다")
        self.assertIn("화강암", popup.inner_text())
        box = popup.bounding_box()
        self.assertGreaterEqual(box["x"], -1, "3D 팝업이 왼쪽으로 넘친다")
        self.assertLessEqual(box["x"] + box["width"], 391, "3D 팝업이 오른쪽으로 넘친다")
        self.assertFits(self.measure(page), "3d 팝업")
        self.assertEqual(errors, [])


def tiny_pack(bbox, layers, built="2026-10-10", title="시험 묶음"):
    """P13 꼴의 작은 묶음 — 레이어마다 (처음 격자 줌, 마지막 격자 줌), 타일은 빨간 한 장 (wetherilli 382).
    열쇠는 화면의 tileCoord 그대로 — KIGAM 은 512 px 격자(격자 줌 = 화면 줌 − 1), VWorld 는 256 px.
    굽는 쪽의 `offlinepack.write` 가 오면 그것으로 바꾼다"""
    import io
    import json
    import math
    import struct

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (220, 30, 30, 255)).save(buf, "PNG")
    png = buf.getvalue()

    def xy(lon, lat, z):
        n = 2 ** z
        y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        return int((lon + 180) / 360 * n), int(y)

    tiles, body = {}, b""
    for name, (z0, z1) in layers.items():
        for z in range(z0, z1 + 1):
            x0, y0 = xy(bbox[0] - 0.02, bbox[3] + 0.02, z)
            x1, y1 = xy(bbox[2] + 0.02, bbox[1] - 0.02, z)
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    tiles[f"{name}/{z}/{x}/{y}"] = [len(body), len(png)]
                    body += png
    head = {"box": "test", "title": title, "built": built, "bbox": bbox, "region": "korea",
            "note": "시험", "dropped": {},
            "layers": {n: {"grid": "EPSG:3857", "tile_size": 256 if n.startswith("vworld:") else 512,
                           "type": "image/png", "zooms": list(z),
                           "attribution": "VWorld" if n.startswith("vworld:") else "한국지질자원연구원"}
                       for n, z in layers.items()},
            "tiles": tiles}
    raw = json.dumps(head, ensure_ascii=False, separators=(",", ":")).encode()
    return b"GSMPACK1" + struct.pack("<I", len(raw)) + raw + body


class OfflinePack(PhoneBase):
    """오프라인 묶음 (wetherilli P13·382) — 망을 끊은 채(타일 요청은 다 끊긴다) 묶음을 들이면 그 범위의 타일이 묶음에서 그려지고,
    지도 위에 "오프라인" 표가 뜬다. 열쇠가 없어도 묶음이 덮는 VWorld 배경이 고르개에 오른다"""

    def test_묶음을_들이면_망_없이_그린다(self):
        call_command("seed_catalog", stdout=open(os.devnull, "w"))
        bbox = [128.85, 37.10, 128.86, 37.11]
        # 이름이 길어도 휴대폰의 표는 한 줄이다 (wetherilli 382)
        pack = tiny_pack(bbox, {"L_50K_Geology_Map": (12, 17), "vworld:Base": (12, 18)},
                         title="시험 묶음 — 장성 도폭 (태백) 둘레의 아주 긴 이름")
        # 정적 판처럼 남극에서 연다(wetherilli 379) — "가 보기" 가 묶음의 지역(한국)으로 넘어가야 한다
        page, errors = self.open("map/?region=antarctica")
        page.evaluate("""() => { window.__blobs = 0; const make = URL.createObjectURL;
                                 URL.createObjectURL = function (b) { window.__blobs++; return make.call(URL, b); }; }""")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        page.tap("#gear")
        page.wait_for_timeout(500)
        page.tap(".stab[data-stab=offline]")
        self.assertFits(self.measure(page), "map/ (설정 — 오프라인)")
        page.set_input_files("#offline-file", files=[{"name": "test-20261010.gsmpack", "mimeType": "application/octet-stream",
                                                      "buffer": pack}])
        page.wait_for_selector("#offline-list li:not(.empty)", timeout=5000)
        self.assertIn("시험 묶음", page.locator("#offline-list").inner_text())
        self.assertIn("다시 열기", page.locator("#offline-status").inner_text())    # 열쇠가 없던 배경이 새로 덮였다

        # 가 보기 — 묶음의 범위로 가면 표가 뜨고, 켠 5만 지질도 타일이 묶음에서 온다
        page.locator("#offline-list button", has_text="가 보기").tap()
        page.wait_for_timeout(2000)
        self.assertEqual(page.evaluate("document.querySelector('#regions .region-tab.on').dataset.region"), "korea",
                         "가 보기가 묶음의 지역으로 넘어가지 않았다")
        badge = page.locator("#offline-badge")
        self.assertTrue(badge.is_visible(), "묶음 안인데 오프라인 표가 없다")
        self.assertIn("오프라인: 시험 묶음", badge.inner_text())
        self.assertNotIn("출처", badge.inner_text(), "휴대폰에서는 출처를 접어 둔다")
        head = page.locator("#offline-badge b").bounding_box()
        self.assertLessEqual(head["height"], 20, "표의 이름·날짜가 한 줄이 아니다")
        self.assertLessEqual(badge.bounding_box()["height"], 32, "휴대폰의 표가 한 줄보다 높다")
        self.assertEqual(page.evaluate(
            "(() => { const b = document.querySelector('#offline-badge .offline-name'); return b.scrollWidth > b.clientWidth; })()"),
            True, "긴 이름이 말줄임되지 않았다")
        self.assertTrue(page.locator("#offline-badge .offline-date").is_visible(), "이름이 길어도 날짜는 보인다")
        self.assertIn("· 10-10", badge.inner_text())
        badge.tap()
        page.wait_for_timeout(200)
        self.assertIn("출처: 한국지질자원연구원 · VWorld", badge.inner_text(), "누르면 출처가 펴진다")
        badge.tap()
        page.wait_for_timeout(200)
        self.assertNotIn("출처", badge.inner_text())
        self.assertGreater(page.evaluate("window.__blobs"), 0, "묶음의 타일을 그리지 않았다")
        self.assertFits(self.measure(page), "map/ (오프라인 표)")

        # 다시 열면 열쇠 없이도 VWorld 배경이 고르개에 오르고, 키를 묻지 않는다
        page.reload(wait_until="load")
        page.wait_for_timeout(1500)
        self.assertEqual(page.locator("#basemap option[value=vworld]").count(), 1, "묶음이 덮는 배경이 고르개에 없다")
        self.assertEqual(page.locator("#basemap option[value=vworld_white]").count(), 0, "덮지 않는 배경이 올랐다")
        self.assertEqual(errors, [])

    def test_꼴이_아니면_거절한다(self):
        page, errors = self.open("map/")
        page.tap("#panel-handle")
        page.wait_for_timeout(300)
        page.tap("#gear")
        page.wait_for_timeout(500)
        page.tap(".stab[data-stab=offline]")
        page.set_input_files("#offline-file", files=[{"name": "x.gsmpack", "mimeType": "application/octet-stream",
                                                      "buffer": b"NOTAPACK" + b"\0" * 32}])
        page.wait_for_timeout(800)
        status = page.locator("#offline-status")
        self.assertIn("오프라인 묶음(.gsmpack)이 아니다", status.inner_text())
        self.assertIn("bad", status.get_attribute("class"))
        self.assertIn("들인 묶음이 없다", page.locator("#offline-list").inner_text())
        self.assertEqual(errors, [])
