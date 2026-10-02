"""연결 레이어로 나가는 문 — 사람이 준 주소(남의 API)를 대신 부른다 (wetherilli P09·122).

개인 레이어를 남의 사이트에 잇는다. 그 사이트가 우리 양식(docs/개인레이어_양식.md)으로 주는 주소와
인증키를 사람이 관리 화면에 넣으면, 지도를 열 때마다 브라우저가 거기서 새로 받는다. **브라우저가 먼저
곧장 부르고**, 상대가 CORS 를 열지 않아 막히면 이 문을 거친다. 주소와 키는 브라우저에만 있다 —
여기로는 그 요청에 실려 왔다 가고, **적지 않는다.** 로그에도 주소의 키 자리는 지운다(`redact`).

다른 문과 다른 것 — 주소를 우리가 정하지 않는다. 그래서 막을 것을 여기서 막는다.

- **사설망·자기 자신을 부르지 않는다.** 이 서버는 연구실 망(phyloserver·NAS·DB)에 닿는다. 남이 그 주소를
  넣어 우리 서버를 디딤돌로 쓰지 못하게, 호스트를 풀어 공인 주소가 아니면 거절한다. 연구실 안의 API 를
  잇고 싶으면 사람이 `settings.LINKED_ALLOW` 에 그 호스트를 적는다
- 넘겨주기(3xx)도 한 번씩 같은 검사를 한다. **다른 호스트로 넘어가면 키를 싣지 않는다**
- 크기(`MAX_BYTES`)·시간에 끝이 있고, 한 사람이 1 분에 `RATE_PER_MINUTE` 번까지. 시간은 **넘겨주기까지 다 합쳐
  `DEADLINE` 초**다 — requests 의 읽기 시간(`TIMEOUT`)은 한 번 읽기의 상한이라, 몇 초마다 조금씩 흘려 보내면
  20 MB 까지 몇 분이고 워커를 붙잡는다 (wetherilli 124)
- 같은 호스트라도 **https 에서 http 로 내려가는 넘겨주기에는 키를 싣지 않는다** — 키가 평문으로 흐른다
- 받은 것을 풀지 않는다 — 읽는 것은 브라우저의 `personal.js` 하나다. 풀이가 두 벌이 되지 않게

- **검사한 IP 로만 붙는다.** 호스트를 풀어 검사한 뒤 requests 가 다시 풀면, 그 사이에 DNS 를 바꿔(rebinding)
  사설 주소로 돌릴 수 있다. 그래서 연결을 맺는 자리(`_new_conn`)만 바꿔 끼워 검사한 IP 로 붙는다 — TLS 의
  인증서 검사와 Host 머리는 호스트 이름 그대로다
- 포트는 80·443 과 1024 위만. 메일·SSH 같은 낮은 포트를 두드리는 디딤돌이 되지 않게
- 연구소 망은 https 를 제 인증서로 다시 서명한다. `settings.EXTRA_CA` 가 있으면 그것도 믿는다 (wetherilli 126)
"""
import ipaddress
import logging
import re
import socket
import ssl
import threading
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.util import connection as u3connection

from . import usage
from .i18n import msg

log = logging.getLogger(__name__)

UPSTREAM = "linked"
USER_AGENT = "GSM/0.1 (linked layer)"
TIMEOUT = (5, 20)
#: 한 번 받기의 전체 마감(초) — 넘겨주기·본문 읽기를 다 합친다
DEADLINE = 20
MAX_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 3
RATE_PER_MINUTE = 30
#: 인증키를 싣는 꼴. 양식 문서의 "연결" 절과 같다
AUTH_MODES = ("none", "bearer", "header", "query")
#: 머리 이름으로 받지 않는 것 — 요청을 망가뜨리거나 다른 뜻이 된다
BAD_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "cookie", "user-agent"}
HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,64}$")


class LinkedError(Exception):
    """사람에게 그대로 보일 까닭. `status` 는 우리가 돌려줄 HTTP 상태."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


# ── 검사 ──────────────────────────────────────────────────────────────

def check_auth(auth: dict) -> dict:
    mode = (auth or {}).get("mode") or "none"
    if mode not in AUTH_MODES:
        raise LinkedError(msg("인증 방식을 모른다"), 400)
    name = str((auth or {}).get("name") or "").strip()
    key = str((auth or {}).get("key") or "")
    if mode in ("header", "query") and not name:
        raise LinkedError(msg("인증키를 싣는 이름이 없다"), 400)
    if mode == "header" and (not HEADER_NAME.match(name) or name.lower() in BAD_HEADERS):
        raise LinkedError(msg("쓸 수 없는 머리 이름이다"), 400)
    if mode != "none" and not key:
        raise LinkedError(msg("인증키가 비었다"), 400)
    if any(c in key for c in "\r\n"):
        raise LinkedError(msg("인증키에 줄바꿈이 들었다"), 400)
    return {"mode": mode, "name": name, "key": key}


def check_url(url: str) -> tuple:
    """http·https 이고, 호스트가 공인 주소이거나 허락한 것인지. (고친 주소, 붙을 IP) 를 돌려준다."""
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        raise LinkedError(msg("주소를 읽지 못했다"), 400)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LinkedError(msg("http·https 주소만 부른다"), 400)
    if parts.username or parts.password:
        raise LinkedError(msg("주소에 계정을 적지 않는다 — 인증키 칸을 쓴다"), 400)
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise LinkedError(msg("포트를 읽지 못했다"), 400)
    if port not in (80, 443) and port < 1024:
        raise LinkedError(msg("80·443 과 1024 위의 포트만 부른다"), 403)
    host = parts.hostname.lower()
    ips = _addresses(host, port)
    if host not in settings.LINKED_ALLOW:
        for ip in ips:
            if not ip.is_global or ip.is_multicast:
                raise LinkedError(msg("연구실 망·자기 자신의 주소는 서버가 부르지 않는다"), 403)
    return urlunsplit(parts), str(ips[0])


def _addresses(host: str, port: int) -> list:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise LinkedError(msg("호스트를 찾지 못했다"), 502)
    out = []
    for info in infos:
        try:
            out.append(ipaddress.ip_address(info[4][0].split("%", 1)[0]))
        except ValueError:
            continue
    if not out:
        raise LinkedError(msg("호스트를 찾지 못했다"), 502)
    # IPv4 를 먼저 — 이 서버는 IPv6 길이 없는 망에 있기도 하다. 붙는 것은 맨 앞의 것 하나다
    return sorted(out, key=lambda ip: ip.version)


def redact(url: str, auth: dict = None) -> str:
    """로그에 남길 주소 — 키를 실은 자리(query 의 이름)와 key·token 꼴의 값을 지운다."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "?"
    hide = {(auth or {}).get("name", "").lower()} if (auth or {}).get("mode") == "query" else set()
    query = [(k, "…" if k.lower() in hide or re.search(r"key|token|secret|auth", k, re.I) else v)
             for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query)))


# ── 한 사람이 너무 자주 부르지 않게 ───────────────────────────────────

_lock = threading.Lock()
_calls = defaultdict(deque)


def allow(client: str) -> bool:
    now = time.time()
    with _lock:
        q = _calls[client]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MINUTE:
            return False
        q.append(now)
        return True


# ── 부르기 ────────────────────────────────────────────────────────────

class _Pinned(HTTPAdapter):
    """연결을 맺을 때 호스트 이름을 다시 풀지 않고 `ip` 로 붙는다. 그 밖(TLS SNI·인증서·Host)은 그대로."""

    def __init__(self, ip: str):
        self._ip = ip
        super().__init__(max_retries=0)

    def init_poolmanager(self, *args, **kwargs):
        # 연구소 망의 TLS 검사 장비가 다시 서명한 것도 믿는다 — requests 가 늘 싣는 certifi 에 더해진다
        if settings.EXTRA_CA:
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(settings.EXTRA_CA)
            kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)
        ip = self._ip

        def new_conn(conn):
            return u3connection.create_connection((ip, conn.port), conn.timeout,
                                                  source_address=conn.source_address,
                                                  socket_options=conn.socket_options)

        pools = dict(self.poolmanager.pool_classes_by_scheme)
        for scheme, base in (("http", HTTPConnectionPool), ("https", HTTPSConnectionPool)):
            conn_cls = type("Pinned" + base.ConnectionCls.__name__, (base.ConnectionCls,), {"_new_conn": new_conn})
            pools[scheme] = type("Pinned" + base.__name__, (base,), {"ConnectionCls": conn_cls})
        self.poolmanager.pool_classes_by_scheme = pools


def _session(ip: str) -> requests.Session:
    session = requests.Session()
    session.trust_env = False         # 환경의 프록시를 타지 않는다 — 붙는 IP 가 검사한 그것이어야 한다
    adapter = _Pinned(ip)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _with_auth(url: str, auth: dict, headers: dict) -> str:
    if auth["mode"] == "bearer":
        headers["Authorization"] = "Bearer " + auth["key"]
    elif auth["mode"] == "header":
        headers[auth["name"]] = auth["key"]
    elif auth["mode"] == "query":
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != auth["name"]]
        query.append((auth["name"], auth["key"]))
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url


def fetch(url: str, auth: dict) -> tuple:
    """주소를 불러 (본문 바이트, content-type) 을 돌려준다. 못 하면 LinkedError."""
    auth = check_auth(auth)
    url, ip = check_url(url)
    origin = urlsplit(url)
    deadline = time.monotonic() + DEADLINE
    for _ in range(MAX_REDIRECTS + 1):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json, text/csv;q=0.9, */*;q=0.5"}
        here = urlsplit(url)
        # 키는 처음 준 호스트에만, 그리고 https 로 받은 것을 http 로 내려 보내지 않는다
        same = here.hostname == origin.hostname and not (origin.scheme == "https" and here.scheme == "http")
        left = deadline - time.monotonic()
        if left <= 0:
            raise LinkedError(msg("너무 오래 걸린다 — {s} 초 안에 받는다", s=DEADLINE), 504)
        target = _with_auth(url, auth, headers) if same else url
        with _session(ip) as session:
            try:
                r = session.get(target, headers=headers, timeout=(TIMEOUT[0], min(TIMEOUT[1], left)), stream=True, allow_redirects=False)
            except requests.RequestException as exc:
                usage.record(UPSTREAM, ok=False)
                log.info("연결 레이어 — 닿지 못했다 %s (%s)", redact(target, auth), type(exc).__name__)
                raise LinkedError(msg("상대 서버에 닿지 못했다"))
            with r:
                if r.status_code in (301, 302, 303, 307, 308):
                    nxt = r.headers.get("Location")
                    if not nxt:
                        raise LinkedError(msg("상대 서버가 빈 곳으로 넘겼다"))
                    url, ip = check_url(urljoin(url, nxt))
                    continue
                if r.status_code != 200:
                    usage.record(UPSTREAM, ok=False)
                    log.info("연결 레이어 — %s 가 %s", redact(target, auth), r.status_code)
                    if r.status_code in (401, 403):
                        raise LinkedError(msg("상대 서버가 거절했다 ({status}) — 인증키를 본다", status=r.status_code))
                    raise LinkedError(msg("상대 서버가 주지 않았다 ({status})", status=r.status_code))
                body = bytearray()
                try:
                    for chunk in r.iter_content(65536):
                        if time.monotonic() > deadline:
                            usage.record(UPSTREAM, ok=False)
                            raise LinkedError(msg("너무 오래 걸린다 — {s} 초 안에 받는다", s=DEADLINE), 504)
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise LinkedError(msg("너무 크다 — {mb} MB 까지 받는다", mb=MAX_BYTES // (1024 * 1024)), 413)
                except requests.RequestException:
                    usage.record(UPSTREAM, ok=False)
                    raise LinkedError(msg("받다가 끊겼다"))
                usage.record(UPSTREAM, ok=True)
                return bytes(body), r.headers.get("Content-Type", "")
    raise LinkedError(msg("넘겨주기가 너무 많다"))
