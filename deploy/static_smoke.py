"""정적 판 연기 시험 — 구운 판을 로컬 파일 서버로 띄워 브라우저로 열어 본다 (wetherilli 315).

    python deploy/static_smoke.py <구운 판 폴더>        # static_site.py 의 출력(그 안에 index.html·map/·static/)
    python deploy/static_smoke.py <폴더> --prefix /GSM-open/ --shots <그림 폴더>

정적 판(https://koprifossillab.github.io/GSM-open/)은 연구소 망에서 밖으로 열어 볼 수 없어 아무도 화면을 본 적이 없다. 그래서 `publish_pages.sh` 가
굽고 나서 밀기 전에 이것을 부른다 — 깨지면 밀지 않는다.

- 소개(한국어·영어) — 페이지 오류가 없고 지역 칩이 선다
- 지도 — 판에 실린 지역(`static-config` 의 `regions`)마다 하나씩: 페이지 오류가 없고, 레이어 목록이 서고(`.layer-row`), 한국에서는 설정 창의
  판 이력(`patchnotes.json`)이 뜬다
- **온 지구·3D·달·화성·수성은 정적 판에 없다**(wetherilli 167) — 열지 않는다

상류는 타지 않는다 — 판 밖으로 나가는 그림(타일)은 투명 1 픽셀로 갈아 끼우고, 나머지(JSON·글꼴)는 끊는다. 망이 없어도 같은 결과다.
처음 열 때 뜨는 키 창(wetherilli 174)은 "나중에" 로 넘긴 탭처럼 연다.

브라우저(Playwright 의 Chromium)가 없으면 건너뛴다(끝 코드 0). `GSM_BROWSER_TESTS=1` 이면 깨진다 — CI 의 "휴대폰 화면" job 과 같다.
끝 코드: 0 통과 또는 건너뜀, 1 깨짐.
"""
import argparse
import base64
import functools
import http.server
import json
import os
import pathlib
import re
import sys
import threading

PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
LAUNCH = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def regions_of(site: pathlib.Path) -> list:
    html = (site / "map" / "index.html").read_text(encoding="utf-8")
    found = re.search(r'id="static-config" type="application/json">(.*?)</script>', html, re.S)
    return list(json.loads(found.group(1)).get("regions") or []) if found else []


class Smoke:
    def __init__(self, site: pathlib.Path, prefix: str, shots=None, settle=2500, log=print):
        self.site, self.prefix, self.shots, self.settle, self.log = site, prefix, shots, settle, log
        self.failures = []

    def run(self, browser, base: str) -> list:
        self.base = base
        self.intro("", "ko")
        self.intro("en/", "en")
        for region in regions_of(self.site):
            self.map(region)
        return self.failures

    # ── 여는 법 ──────────────────────────────────────────────
    def _page(self, region=None):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
        if region:
            ctx.add_init_script("try { localStorage.setItem('gsm.region', %s); sessionStorage.setItem('gsm.key.later', '1'); } catch (e) {}"
                                % json.dumps(region))
        page = ctx.new_page()
        errors, outside = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def route(r):
            if r.request.url.startswith(self.base):
                return r.continue_()
            outside.append(r.request.url)
            if r.request.resource_type == "image":          # 상류 타일·배경 — 빈 그림으로
                return r.fulfill(status=200, content_type="image/png", body=PNG_1PX)
            return r.abort()
        page.route("**/*", route)
        return ctx, page, errors, outside

    def _check(self, where: str, ok: bool, why: str):
        if ok:
            self.log(f"  ✓ {where}")
        else:
            self.log(f"  ✗ {where} — {why}")
            self.failures.append(f"{where}: {why}")

    def _shot(self, page, name):
        if self.shots:
            pathlib.Path(self.shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(pathlib.Path(self.shots) / f"{name}.png"))

    # ── 화면마다 ────────────────────────────────────────────
    def intro(self, path: str, lang: str):
        ctx, page, errors, _ = self._page()
        try:
            page.goto(self.base + path, wait_until="load")
            page.wait_for_timeout(1000)
            chips = page.eval_on_selector_all(".chips.regions li", "els => els.filter(e => !e.hidden).length")
            self._shot(page, f"intro-{lang}")
            self._check(f"소개 ({lang})", not errors and chips > 0,
                        "; ".join(errors[:3]) if errors else "지역 칩이 하나도 서지 않았다")
        finally:
            ctx.close()

    def map(self, region: str):
        ctx, page, errors, outside = self._page(region)
        try:
            page.goto(f"{self.base}map/?region={region}", wait_until="load")
            page.wait_for_timeout(self.settle)
            rows = page.eval_on_selector_all(".layer-row", "els => els.length")
            here = page.evaluate("document.documentElement.dataset.region")
            notes = ""
            if region == "korea":
                page.click("#gear")
                try:
                    page.wait_for_function("document.getElementById('notes').textContent.length > 20", timeout=5000)
                    notes = page.inner_text("#notes")
                except Exception:                                # noqa: BLE001 — 시간이 다 되면 아래에서 깨진다
                    notes = ""
            self._shot(page, f"map-{region}")
            why = ("; ".join(errors[:3]) if errors else
                   f"다른 지역({here})으로 섰다" if here != region else
                   "레이어 목록이 비었다" if rows == 0 else
                   "판 이력이 뜨지 않았다" if region == "korea" and (len(notes) <= 20 or "판 이력을 읽지 못했다" in notes) else "")
            self._check(f"지도 {region} (레이어 {rows}, 판 밖 요청 {len(outside)})", not why, why)
        finally:
            ctx.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="정적 판 연기 시험 — 구운 판을 띄워 브라우저로 열어 본다")
    parser.add_argument("site", help="static_site.py 가 구운 폴더 (index.html·map/·static/ 이 든 곳)")
    parser.add_argument("--prefix", default="/GSM-open/", help="판의 주소 앞머리 (기본 /GSM-open/)")
    parser.add_argument("--shots", default="", help="화면을 찍어 둘 폴더")
    parser.add_argument("--settle", type=int, default=2500, help="지도를 열고 기다리는 밀리초")
    o = parser.parse_args(argv)
    site = pathlib.Path(o.site).resolve()
    if not (site / "map" / "index.html").is_file():
        print(f"구운 판이 아니다 — {site}/map/index.html 이 없다", file=sys.stderr)
        return 1
    required = os.environ.get("GSM_BROWSER_TESTS") == "1"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 가 없어 정적 판 연기 시험을 건너뛴다 — pip install -r requirements-browser.txt")
        return 1 if required else 0

    # 판을 `<앞머리>` 아래에 두고 띄운다 — 판 안의 주소가 `/GSM-open/static/…` 꼴이다
    prefix = "/" + o.prefix.strip("/") + "/"
    root = site.parent if site.name == prefix.strip("/").split("/")[-1] else None
    if root is None:
        import tempfile
        root = pathlib.Path(tempfile.mkdtemp(prefix="gsm-static-smoke-"))
        link = root / prefix.strip("/")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(site, target_is_directory=True)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}{prefix}"
    print(f"정적 판 연기 시험 — {site} 를 {base} 로")
    smoke = Smoke(site, prefix, o.shots or None, o.settle)
    try:
        with sync_playwright() as pw:
            try:
                smoke.browser = pw.chromium.launch(args=LAUNCH)
            except Exception as exc:                            # noqa: BLE001
                print(f"Chromium 이 없어 건너뛴다 — python -m playwright install chromium ({exc})")
                return 1 if required else 0
            try:
                failures = smoke.run(smoke.browser, base)
            finally:
                smoke.browser.close()
    finally:
        httpd.shutdown()
    if failures:
        print(f"깨졌다 — {len(failures)} 곳:", *failures, sep="\n  ")
        return 1
    print("통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
