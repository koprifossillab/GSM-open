"""HTTP 한 번 — 표준 라이브러리(urllib)만 쓴다. 패키지가 `requests` 없이 노트북에서 돌게 (wetherilli 407).

- 늘 `User-Agent: GSM/0.1` 을 보낸다 — 상류 방화벽이 기본 UA 를 막는다(CLAUDE.md)
- 인증서는 시스템의 것을 믿는다. 연구소 망처럼 TLS 를 다시 서명하는 곳에서는 `SSL_CERT_FILE` 로 꾸러미를 준다
- **주소에 키가 들 수 있다** — 오류 문구에 주소를 싣지 않고, 실어야 하면 `redact` 를 거친다
"""
import re
import ssl
import urllib.error
import urllib.request

from .bake import FetchError

USER_AGENT = "GSM/0.1"
TIMEOUT = 60

_KEY_RE = re.compile(r"(key=)[^&\s]*", re.I)


def redact(text: str, *secrets) -> str:
    """로그·오류에 남길 글에서 키를 지운다 — `key=…` 변수와, 경로에 든 키(VWorld WMTS)."""
    text = _KEY_RE.sub(r"\1…", text or "")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "…")
    return text


def looks_blocked(status: int, head: bytes = b"") -> bool:
    """차단의 얼굴 — 403·429·503, 그리고 방화벽의 `400 Request Blocked`. GSM 을 거칠 때는 GSM 의 쉬는 중(503)도 여기 든다."""
    if status in (403, 429, 503):
        return True
    return status == 400 and b"Request Blocked" in (head or b"")[:1000]


def get(url: str, *, where: str = "", secrets=()):
    """`(상태, 머리 dict(소문자 이름), 본문)`. 닿지 못하면 `FetchError` — 주소는 싣지 않고 `where` 만."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, body
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FetchError(f"닿지 못했다 ({where}): {redact(str(exc), *secrets)}") from exc
