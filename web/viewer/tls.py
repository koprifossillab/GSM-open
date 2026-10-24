"""상류로 나가는 https 의 검증 — 파이썬 3.13 의 엄격 검사(`VERIFY_X509_STRICT`)를 가로채는 망에서만 푼다 (wetherilli 426).

연구소 망의 TLS 검사 장비는 https 를 제 CA("KOPRI SSL")로 다시 서명한다. CA 는 시스템 꾸러미에 깔려 있어 믿지만
(`settings.CA_BUNDLE`·`EXTRA_CA`, `deploy/ca/`), **장비가 지어 내는 잎 인증서에는 SAN 말고 확장이 없다** — 기관 키
식별자(AKI)가 빠졌다. 파이썬 3.13 부터 `ssl.create_default_context()` 와 urllib3 2.x 의 기본 컨텍스트가
`VERIFY_X509_STRICT` 를 켜서, 그런 잎을 `Missing Authority Key Identifier` 로 거절한다. 3.12 의 컨테이너는 돌고,
3.14 로 도는 호스트의 받기(`run.sh` 의 venv — `fetch_recent_quakes` 등)가 멈췄다.

그래서 **이 기계가 가로채는 CA 를 믿을 때만** 엄격 검사 하나를 끈다. 체인 검증·호스트 이름 검사·믿는 꾸러미는 그대로다 —
3.12 와 같은 검사다. 망 밖(CI·남의 기계)에서는 꾸러미에 그 CA 가 없으니 아무것도 바꾸지 않는다.

문마다 `requests.get(..., verify=settings.CA_BUNDLE or True)` 를 부르므로 고칠 자리를 하나로 두려고 urllib3 가 기본
컨텍스트를 짓는 함수를 감싼다(`install`, `apps.py` 가 부른다). 손으로 컨텍스트를 짓는 문(`kopri`·`linked`)은 `context()` 를 쓴다.
"""
import functools
import ssl

from django.conf import settings

#: 다시 서명하는 장비의 CA 이름(CN). 이것이 믿는 꾸러미에 들 때만 엄격 검사를 푼다
INTERCEPT_CAS = ("KOPRI SSL",)


@functools.cache
def _trusts_interceptor(*bundles: str) -> bool:
    for path in bundles:
        if not path:
            continue
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        try:
            ctx.load_verify_locations(path)
        except (OSError, ssl.SSLError):
            continue
        for ca in ctx.get_ca_certs():
            names = {v for rdn in ca.get("subject", ()) for k, v in rdn if k == "commonName"}
            if names & set(INTERCEPT_CAS):
                return True
    return False


def intercepted() -> bool:
    """이 기계가 TLS 를 다시 서명하는 장비의 CA 를 믿는가."""
    return _trusts_interceptor(settings.CA_BUNDLE, settings.EXTRA_CA)


def relax(ctx: ssl.SSLContext) -> ssl.SSLContext:
    """가로채는 망이면 `VERIFY_X509_STRICT` 만 끈다. 검증은 끄지 않는다."""
    if intercepted():
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def context(cafile: str | None = None) -> ssl.SSLContext:
    """`ssl.create_default_context` 와 같되 가로채는 망의 잎을 받아 준다."""
    return relax(ssl.create_default_context(cafile=cafile))


def install() -> None:
    """urllib3 의 기본 컨텍스트(그래서 모든 `requests` 부르기)에 `relax` 를 건다. 두 번 불러도 한 번이다."""
    import urllib3.connection
    import urllib3.util.ssl_

    original = urllib3.util.ssl_.create_urllib3_context
    if getattr(original, "_gsm_relaxed", False):
        return

    @functools.wraps(original)
    def create(*args, **kwargs):
        return relax(original(*args, **kwargs))

    create._gsm_relaxed = True
    # connection 은 이름을 제 모듈로 가져가 쓴다 — 둘 다 바꾼다
    urllib3.util.ssl_.create_urllib3_context = create
    urllib3.connection.create_urllib3_context = create
    try:
        import requests.adapters
    except ImportError:                                # pragma: no cover — requests 없는 곳
        return
    # requests 는 import 할 때 certifi 컨텍스트를 하나 지어 둔다(verify=True 일 때 쓴다)
    if getattr(requests.adapters, "_preloaded_ssl_context", None) is not None:
        relax(requests.adapters._preloaded_ssl_context)
