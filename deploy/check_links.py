"""출처 링크 점검 — 화면에 뜨는 출처·원본 링크가 아직 살아 있는지 한 번씩 찔러 본다 (wetherilli 339).

    python deploy/check_links.py              # 표
    python deploy/check_links.py --broken     # 깨진 것만

링크는 코드에서 긁는다 — 문의 출처(`ATTRIBUTION` 따위의 `href`)·템플릿·화면 스크립트·씨앗의 `source`·문의 `SOURCE_URL`. 서비스 주소(WMS 따위)는
사람이 누르는 링크가 아니라 보지 않는다(그것은 `manage.py verify_layers` 의 몫).

- 1 초 간격으로 한 번씩. 먼저 `GSM/0.1` 로 묻고, 안 되면 브라우저 User-Agent 로 한 번 더 — 사람의 브라우저에서는 열리는 곳이 많다
- 갈래: **살아 있다**(< 400), **사람만**(403 — 봇 막이·지역 막이, 브라우저에서는 열릴 수 있다), **깨졌다**(404·410 따위), **닿지 않는다**(연결 오류)
- 뷰어 앱 밖의 스크립트다 — 뷰어의 문(`web/viewer/<문>.py`)만 상류를 부른다는 규칙(CLAUDE.md)은 앱 안의 것이고, 이것은 사람이 부르는 점검이다.
  표준 라이브러리만 쓴다
끝 코드: 깨진 것이 있으면 1.
"""
import argparse
import http.cookiejar
import pathlib
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ["web/viewer/*.py", "web/viewer/templates/viewer/*.html", "web/viewer/static/viewer/*.js", "data/*.json", "README.md"]
HREF = re.compile(r"""href=\\?["'](https?://[^"'\\\s]+)""")
SOURCE = re.compile(r"""(?:"source"\s*:\s*|SOURCE_URL\s*=\s*)"(https?://[^"]+)""")
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
CA = "/etc/ssl/certs/ca-certificates.crt"


def links() -> dict:
    """링크 → 처음 나온 파일"""
    found = {}
    for pattern in SOURCES:
        for path in sorted(ROOT.glob(pattern)):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for url in HREF.findall(text) + SOURCE.findall(text):
                url = url.rstrip(").,;")
                if "{" in url or "localhost" in url:
                    continue
                found.setdefault(url, str(path.relative_to(ROOT)))
    return found


def ask(url: str, agent: str, context) -> object:
    headers = {"User-Agent": agent}
    if agent == BROWSER:                  # 몇몇 곳은 Accept 가 없으면 400 이다(BGR)
        headers.update({"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en,ko;q=0.8"})
    request = urllib.request.Request(url, headers=headers)
    # 쿠키를 들고 따라간다 — BGR 은 쿠키 확인 쪽으로 돌려보냈다가 쿠키가 없으면 400 이다
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                         urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(request, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:                                    # noqa: BLE001 — 갈래만 적는다
        return type(exc).__name__


def kind(status) -> str:
    if isinstance(status, int) and status < 400:
        return "살아 있다"
    if status in (401, 403, 429):
        return "사람만"
    if isinstance(status, int):
        return "깨졌다"
    return "닿지 않는다"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="화면에 뜨는 출처 링크가 살아 있는지 본다")
    parser.add_argument("--broken", action="store_true", help="살아 있지 않은 것만")
    parser.add_argument("--gap", type=float, default=1.0)
    o = parser.parse_args(argv)
    context = ssl.create_default_context(cafile=CA) if pathlib.Path(CA).exists() else ssl.create_default_context()
    table = []
    for url, where in sorted(links().items()):
        status = ask(url, "GSM/0.1", context)
        if kind(status) != "살아 있다":
            time.sleep(o.gap)
            status = ask(url, BROWSER, context)
        table.append((kind(status), status, url, where))
        time.sleep(o.gap)
    for k, status, url, where in table:
        if not o.broken or k != "살아 있다":
            print(f"{k}\t{status}\t{url}\t{where}")
    counts = {k: sum(1 for row in table if row[0] == k) for k in ("살아 있다", "사람만", "깨졌다", "닿지 않는다")}
    print(" · ".join(f"{k} {n}" for k, n in counts.items()), file=sys.stderr)
    return 1 if counts["깨졌다"] else 0


if __name__ == "__main__":
    sys.exit(main())
