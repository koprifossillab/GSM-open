"""연구소 밖 정적 판 — 굽기와 화면 (wetherilli 168, P11).

`deploy/static_site.py` 로 **작은 판**(한국 + 가짜로 구운 것 조금)을 임시 폴더에 한 번 굽는다. 굽는 것은 따로 도는 파이썬이다 —
그 스크립트는 제 손으로 Django 를 세우고(빈 DB 에 씨앗) 운영 DB·캐시를 건드리지 않는다. 그다음

- 구운 것을 본다 — 키(운영 KIGAM·VWorld)가 HTML 에 없는지, 구운 것(`--baked`)이 제자리에 얹히고 `static-config` 에 실리는지,
  지명 색인이 지어지는지
- 브라우저로 띄운다(Playwright, `test_mobile` 과 같은 틀) — `/GSM-open/` 꼴로 한국 탭·남극 탭이 페이지 오류 없이 서고, 한국의
  키 칸이 뜨는지. `static-kinds.js` 는 아직 없어도(gsm-85 의 몫) 깨지지 않아야 한다

브라우저 몫은 Chromium 이 있어야 돈다. 없으면 건너뛰고, CI 의 "휴대폰 화면" job 은 `GSM_BROWSER_TESTS=1` 로 깨지게 한다.
상류는 타지 않는다 — 브라우저가 이 판 밖으로 나가는 요청은 다 끊는다.
"""
import functools
import http.server
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import unittest

from django.test import SimpleTestCase

try:
    from playwright.sync_api import sync_playwright
except ImportError:            # 운영 이미지·기본 시험에는 없다
    sync_playwright = None

REQUIRED = os.environ.get("GSM_BROWSER_TESTS") == "1"
ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "deploy" / "static_site.py"
KIGAM_SECRET = "SENTINEL-KIGAM-KEY-0000"
VWORLD_SECRET = "SENTINEL-VWORLD-KEY-0000"
PREFIX = "/GSM-open/"
# 1×1 투명 PNG
#: 아직 병합 전인 몫 — 들어오면 그 시험이 저절로 켜진다
HAS_PLACENAMES = "def place_index" in SCRIPT.read_text(encoding="utf-8")        # #142, wetherilli 166
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000005057c2f2b0000000049454e44ae426082")


def fake_baked(folder: pathlib.Path):
    """`manage.py bake_static` 의 출력을 흉내 낸 작은 폴더 — GeoMAP 한 장, 얀마옌 한 덩이, 스발바르 지명 하나."""
    def put(rel, data):
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
    empty = {"type": "FeatureCollection", "features": [], "labels": {}, "style": "unit", "legend": []}
    put("geomap/geomap_simple_geology/0/0/0.png", PNG)
    put("legend/geomap/geomap_simple_geology.png", PNG)
    put("points/janmayen/units.json", empty)
    put("points/janmayen/units.en.json", empty)
    put("points/npolar/place_names.json", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [15.633, 78.223]},
         "properties": {"name": "Longyearbyen", "area": "Svalbard"}}]})
    put("manifest.json", {"parts": {
        "geomap": {"geomap_simple_geology": {"max_zoom": 1, "tiles": 1}},
        "points": {"janmayen:units": {"bytes": 1, "lang": True}, "npolar:place_names": {"bytes": 1}},
        "ibcso": {}}, "files": [], "total_bytes": 0})


@functools.lru_cache(maxsize=1)
def built() -> pathlib.Path:
    """작은 판을 한 번만 굽는다 — 굽는 데 열 몇 초가 든다. 돌려주는 것은 `/GSM-open/` 의 뿌리를 품은 폴더."""
    work = pathlib.Path(tempfile.mkdtemp(prefix="gsm-static-test-"))
    fake_baked(work / "baked")
    env = dict(os.environ, GSM_KIGAM_KEY=KIGAM_SECRET, GSM_VWORLD_KEY=VWORLD_SECRET,
               GSM_SECRET_KEY="static-test", DJANGO_SETTINGS_MODULE="gsmweb.settings")
    done = subprocess.run([sys.executable, str(SCRIPT), str(work / "site" / "GSM-open"),
                           "--baked", str(work / "baked"), "--prefix", PREFIX],
                          env=env, capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise RuntimeError(f"정적 판을 굽지 못했다:\n{done.stdout}\n{done.stderr}")
    return work / "site"


def static_config(html: str) -> dict:
    return json.loads(re.search(r'id="static-config" type="application/json">(.*?)</script>', html, re.S).group(1))


class Build(SimpleTestCase):
    """구운 것 — 브라우저 없이."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = built() / "GSM-open"
        cls.html = (cls.site / "map" / "index.html").read_text(encoding="utf-8")

    def test_운영_KIGAM_키가_없다(self):
        self.assertNotIn(KIGAM_SECRET, self.html)
        hits = [p for p in self.site.rglob("*.html") if KIGAM_SECRET in p.read_text(encoding="utf-8", errors="ignore")]
        self.assertEqual(hits, [])

    def test_운영_VWorld_키가_없다(self):
        # VWorld 도 보는 사람이 각자 넣는다 — 굽는 판에는 어떤 키도 없다 (wetherilli 174)
        self.assertNotIn(VWORLD_SECRET, self.html)
        self.assertIn('id="vworld-key" type="application/json">""<', self.html)
        self.assertIn("vworld", static_config(self.html)["upstreams"])

    def test_주소_앞머리는_GSM_open(self):
        self.assertNotIn('"/GSM/', self.html)
        self.assertIn(PREFIX + "static/", self.html)
        self.assertTrue((self.site / "index.html").is_file())
        self.assertTrue((self.site / ".nojekyll").is_file())

    def test_구운_것이_제자리에_얹히고_화면에_알린다(self):
        self.assertTrue((self.site / "geomap/geomap_simple_geology/0/0/0.png").is_file())
        self.assertTrue((self.site / "points/janmayen/units.en.json").is_file())
        config = static_config(self.html)
        self.assertIn("antarctica", config["regions"])
        self.assertIn("geomap", config["upstreams"])
        self.assertEqual(config["baked"]["geomap"], {"geomap_simple_geology": 1})
        self.assertTrue(config["baked"]["points"]["janmayen:units"])

    @unittest.skipUnless(HAS_PLACENAMES, "정적 판의 지명 색인(#142, wetherilli 166)이 아직 없다")
    def test_지명_색인을_짓는다(self):
        config = static_config(self.html)
        rel = config["baked"]["placenames"]["svalbard"][0]
        rows = json.loads((self.site / rel).read_text(encoding="utf-8"))
        self.assertEqual(rows[0][0], ["Longyearbyen"])
        self.assertEqual((rows[0][2], rows[0][3]), (78.223, 15.633))

    def test_구운_점_레이어만_목록에(self):
        groups = json.loads(re.search(r'id="catalog-data" type="application/json">(.*?)</script>',
                                      self.html, re.S).group(1))
        names = {l["name"] for g in groups for l in g["layers"]}
        self.assertIn("janmayen:units", names)
        self.assertNotIn("janmayen:lines", names)             # 굽지 않은 것
        self.assertFalse({n for n in names if n.startswith(("geo3al:", "phyloserver:", "peninsula:"))})

    def test_극지는_곧장_부르는_상류로_선다(self):
        # wetherilli 161 — 굽지 않아도 NPI·EMODnet·KPDC 지도 서버가 선다. KPDC 의 모아 둔 점은 구운 것이 있어야
        groups = json.loads(re.search(r'id="catalog-data" type="application/json">(.*?)</script>',
                                      self.html, re.S).group(1))
        names = {l["name"] for g in groups for l in g["layers"]}
        self.assertIn("npolar:svalbard_units", names)
        self.assertIn("emodnet:cp_wp4_pre_quaternary_geology_lithology", names)
        self.assertIn("kopri:rock_outcrops", names)
        self.assertNotIn("kopri:rock_samples", names)
        tables = json.loads(re.search(r'id="static-tables" type="application/json">(.*?)</script>',
                                      self.html, re.S).group(1))
        self.assertIn("G_Geologi_Svalbard_S250_S750", json.dumps(tables["npolar"]["tiles"]))


    def test_판_이력을_떠_둔다(self):
        """설정 창의 판 이력 — 서버의 `patchnotes/` 가 없으니 굽을 때 `patchnotes.json` 으로 떠 둔다."""
        notes = json.loads((self.site / "patchnotes.json").read_text(encoding="utf-8"))
        self.assertTrue(notes["notes"])

    def test_소개의_첫_장면에_서버_화면이_없다(self):
        """정적 판에 없는 화면(온 지구·달·화성·수성·3D)은 소개의 첫 장면에서 뺀다."""
        for intro in (self.site / "index.html", self.site / "en" / "index.html"):
            html = intro.read_text(encoding="utf-8")
            title = html[html.index('id="title"'):html.index('id="hook"')]
            self.assertNotIn("data-moon", title)
            self.assertNotIn('class="moon"', title)
            self.assertNotIn("3D", title)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Browser(SimpleTestCase):
    """구운 판을 `/GSM-open/` 꼴로 띄워 본다 — Chromium 이 있을 때만."""

    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            if REQUIRED:
                raise RuntimeError("GSM_BROWSER_TESTS=1 인데 playwright 가 없다")
            raise unittest.SkipTest("playwright 가 없다 — requirements-browser.txt")
        super().setUpClass()
        root = built()
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}{PREFIX}"
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(
                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        except Exception as e:
            cls.pw.stop()
            cls.httpd.shutdown()
            if REQUIRED:
                raise
            raise unittest.SkipTest(f"Chromium 이 없다 — python -m playwright install chromium ({e})")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        super().tearDownClass()

    def open(self, region, settle=2500, asked=None, ask_keys=False):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 800})
        self.addCleanup(ctx.close)
        ctx.add_init_script("try { localStorage.setItem('gsm.region', %s); } catch (e) {}" % json.dumps(region))
        if not ask_keys:
            # 처음 열 때 뜨는 키 창(wetherilli 174)을 "나중에" 로 넘긴 탭처럼 — 다른 시험이 창에 가리지 않게
            ctx.add_init_script("try { sessionStorage.setItem('gsm.key.later', '1'); } catch (e) {}")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # 이 판 밖(상류·배경)은 끊는다 — 시험이 망에 기대지 않게
        def route(r):
            if r.request.url.startswith(self.base):
                return r.continue_()
            if asked is not None:
                asked.append(r.request.url)
            return r.abort()
        page.route("**/*", route)
        page.goto(self.base + "map/?region=" + region, wait_until="load")
        page.wait_for_timeout(settle)
        return page, errors

    def test_처음_열면_키_둘을_묻는다(self):
        """KIGAM·VWorld 둘 다 각자 키 — 처음 열면 둘을 받는 창이 뜬다 (wetherilli 174)."""
        page, errors = self.open("korea", ask_keys=True)
        self.assertEqual(errors, [])
        self.assertTrue(page.is_visible("#key-dialog"))
        self.assertEqual(len(page.query_selector_all("#key-dialog input[type=password]")), 2)
        page.click("#key-dialog .key-buttons .btn.quiet:nth-child(2)")          # 나중에
        self.assertFalse(page.query_selector("#key-dialog"))
        self.assertTrue(page.is_visible("#static-key button"))

    def test_넣은_키는_이_브라우저에만(self):
        page, errors = self.open("korea", ask_keys=True)
        inputs = page.query_selector_all("#key-dialog input[type=password]")
        inputs[0].fill("kigam-key")
        inputs[1].fill("vworld-key")
        with page.expect_navigation():
            page.click("#key-dialog .key-buttons .btn:not(.quiet)")               # 저장 — 다시 연다
        page.wait_for_timeout(1500)
        held = page.evaluate("[localStorage.getItem('gsm.key.kigam'), localStorage.getItem('gsm.key.vworld')]")
        self.assertIn("kigam-key", held[0])
        self.assertIn("vworld-key", held[1])
        self.assertFalse(page.query_selector("#key-dialog"))                     # 둘 다 있으니 다시 묻지 않는다

    def test_남극_탭이_구운_것으로_선다(self):
        page, errors = self.open("antarctica")
        self.assertEqual(errors, [])
        self.assertIn("geomap_simple_geology", page.content())

    def test_스발바르는_NPI_를_곧장_부른다(self):
        # wetherilli 161 — 첫 레이어(NPI 지질 단위)의 그림을 서버가 아니라 NPI 지도 서버의 `export` 에 묻는다
        asked = []
        page, errors = self.open("svalbard", settle=4000, asked=asked)
        self.assertEqual(errors, [])
        self.assertTrue(any("/MapServer/export" in url for url in asked), asked[:5])

    def test_극지_범례를_열어도_멈추지_않는다(self):
        page, errors = self.open("svalbard", settle=3000)
        button = page.query_selector('#panel button[title="범례를 펼친다"]')
        self.assertIsNotNone(button)
        button.click()
        page.wait_for_timeout(1500)
        self.assertEqual(errors, [])

    @unittest.skipUnless(HAS_PLACENAMES, "정적 판의 지명 색인(#142, wetherilli 166)이 아직 없다")
    def test_지명을_구운_색인에서_찾는다(self):
        page, errors = self.open("svalbard")
        page.fill("#goto-input", "longyear")
        page.press("#goto-input", "Enter")
        page.wait_for_selector("#search-results li[data-i]", timeout=10000)
        self.assertIn("Longyearbyen", page.inner_text("#search-results"))
        self.assertEqual(errors, [])

    def test_설정_창에_판_이력이_뜬다(self):
        page, errors = self.open("korea")
        page.click("#gear")
        page.wait_for_function("document.getElementById('notes').textContent.length > 20", timeout=5000)
        self.assertNotIn("판 이력을 읽지 못했다", page.inner_text("#notes"))
        self.assertEqual(errors, [])

    def test_소개는_실린_지역의_칩만(self):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(self.base) else r.abort())
        page.goto(self.base, wait_until="load")
        page.wait_for_timeout(1000)
        shown = page.eval_on_selector_all(".chips.regions li", "els => els.filter(e => !e.hidden).map(e => e.textContent)")
        self.assertIn("한국", shown)
        self.assertIn("남극", shown)
        self.assertNotIn("일본", shown)
        self.assertNotIn("동아시아", shown)
        self.assertEqual(errors, [])
