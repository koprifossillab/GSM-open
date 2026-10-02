"""연결 레이어로 나가는 문 (wetherilli P09·122).

남이 준 주소를 서버가 대신 부르므로 **막을 것을 막는지**를 본다 — 사설망·자기 자신, 낮은 포트, http·https 밖,
넘겨주기로 돌아 들어오는 것, 다른 호스트로 넘어갈 때 키를 싣는 것, 너무 큰 것. 실제로 밖을 부르지 않는다
(이름 풀기와 연결을 갈아 끼운다).
"""
import ipaddress
import json
import socket
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import i18n, linked


def resolves(table):
    """호스트 -> IP 표로 getaddrinfo 를 갈아 끼운다."""
    def fake(host, port, *args, **kwargs):
        try:
            ip = str(ipaddress.ip_address(host))          # IP 를 그대로 적은 주소
        except ValueError:
            if host not in table:
                raise socket.gaierror("no such host")
            ip = table[host]
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (ip, port))]
    return mock.patch("viewer.linked.socket.getaddrinfo", side_effect=fake)


HOSTS = {"api.example.org": "93.184.216.34", "lab.local": "172.16.116.98", "evil.example.org": "93.184.216.35",
         "v6.example.org": "2606:2800:220:1::1", "loop.example.org": "127.0.0.1"}


class Response:
    def __init__(self, status=200, body=b"{}", headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {"Content-Type": "application/json"}

    def iter_content(self, size):
        for i in range(0, len(self._body), size):
            yield self._body[i:i + size]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Session:
    """부른 것을 적어 두는 가짜 세션. `answers` 는 주소 -> Response."""
    calls = []

    def __init__(self, ip, answers):
        self.ip, self.answers = ip, answers

    def get(self, url, headers=None, **kw):
        Session.calls.append({"url": url, "ip": self.ip, "headers": dict(headers or {})})
        return self.answers[url.split("?")[0]]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def sessions(answers):
    Session.calls = []
    return mock.patch("viewer.linked._session", side_effect=lambda ip: Session(ip, answers))


@override_settings(LINKED_ALLOW=[])
class CheckUrl(SimpleTestCase):
    def test_공인_주소는_부른다(self):
        with resolves(HOSTS):
            self.assertEqual(linked.check_url("https://api.example.org/x.json"),
                             ("https://api.example.org/x.json", "93.184.216.34"))

    def test_사설망_자기_자신은_막는다(self):
        with resolves(HOSTS):
            for url in ("http://lab.local/", "http://loop.example.org/", "http://127.0.0.1/", "http://10.1.2.3/",
                        "http://169.254.169.254/latest/meta-data", "http://[::1]/", "http://0.0.0.0/"):
                with self.subTest(url=url), self.assertRaises(linked.LinkedError) as cm:
                    linked.check_url(url)
                self.assertEqual(cm.exception.status, 403)

    def test_http_https_밖은_막는다(self):
        for url in ("ftp://api.example.org/", "file:///etc/passwd", "gopher://x/", "javascript:alert(1)", ""):
            with self.subTest(url=url), self.assertRaises(linked.LinkedError):
                linked.check_url(url)

    def test_낮은_포트는_막는다(self):
        with resolves(HOSTS):
            for url in ("http://api.example.org:22/", "http://api.example.org:25/", "https://api.example.org:6/"):
                with self.subTest(url=url), self.assertRaises(linked.LinkedError):
                    linked.check_url(url)
            linked.check_url("http://api.example.org:8080/")

    def test_주소에_계정을_적으면_막는다(self):
        with self.assertRaises(linked.LinkedError):
            linked.check_url("https://user:pw@api.example.org/")

    @override_settings(LINKED_ALLOW=["lab.local"])
    def test_허락한_호스트는_사설망이어도_부른다(self):
        with resolves(HOSTS):
            self.assertEqual(linked.check_url("http://lab.local/api")[1], "172.16.116.98")
            with self.assertRaises(linked.LinkedError):
                linked.check_url("http://loop.example.org/")


class Auth(SimpleTestCase):
    def test_방식마다_필요한_것(self):
        self.assertEqual(linked.check_auth({})["mode"], "none")
        for bad in ({"mode": "magic"}, {"mode": "bearer"}, {"mode": "header", "key": "k"},
                    {"mode": "header", "name": "Host", "key": "k"}, {"mode": "header", "name": "X Y", "key": "k"},
                    {"mode": "query", "key": "k"}, {"mode": "bearer", "key": "a\r\nX-Evil: 1"}):
            with self.subTest(auth=bad), self.assertRaises(linked.LinkedError):
                linked.check_auth(bad)

    def test_로그에는_키가_없다(self):
        out = linked.redact("https://a.b/x?apikey=SECRET&q=1&token=T2", {"mode": "query", "name": "apikey"})
        self.assertNotIn("SECRET", out)
        self.assertNotIn("T2", out)
        self.assertIn("q=1", out)


@override_settings(LINKED_ALLOW=[])
class Fetch(SimpleTestCase):
    def test_키를_싣는_꼴(self):
        answers = {"https://api.example.org/x": Response(body=b'{"type":"FeatureCollection"}')}
        with resolves(HOSTS), sessions(answers):
            linked.fetch("https://api.example.org/x", {"mode": "bearer", "key": "K1"})
            linked.fetch("https://api.example.org/x", {"mode": "header", "name": "X-API-Key", "key": "K2"})
            linked.fetch("https://api.example.org/x?a=1", {"mode": "query", "name": "apikey", "key": "K3"})
        self.assertEqual(Session.calls[0]["headers"]["Authorization"], "Bearer K1")
        self.assertEqual(Session.calls[1]["headers"]["X-API-Key"], "K2")
        self.assertIn("apikey=K3", Session.calls[2]["url"])
        self.assertIn("a=1", Session.calls[2]["url"])

    def test_검사한_IP_로_붙는다(self):
        answers = {"https://api.example.org/x": Response()}
        with resolves(HOSTS), sessions(answers):
            linked.fetch("https://api.example.org/x", {})
        self.assertEqual(Session.calls[0]["ip"], "93.184.216.34")

    def test_넘겨주기로_사설망에_들어가지_못한다(self):
        answers = {"https://api.example.org/x": Response(302, headers={"Location": "http://lab.local/secret"})}
        with resolves(HOSTS), sessions(answers), self.assertRaises(linked.LinkedError) as cm:
            linked.fetch("https://api.example.org/x", {})
        self.assertEqual(cm.exception.status, 403)

    def test_다른_호스트로_넘어가면_키를_싣지_않는다(self):
        answers = {"https://api.example.org/x": Response(302, headers={"Location": "https://evil.example.org/y"}),
                   "https://evil.example.org/y": Response(body=b"{}")}
        with resolves(HOSTS), sessions(answers):
            linked.fetch("https://api.example.org/x?k=1", {"mode": "query", "name": "apikey", "key": "SECRET"})
            linked.fetch("https://api.example.org/x", {"mode": "bearer", "key": "SECRET"})
        second = [c for c in Session.calls if "evil" in c["url"]]
        self.assertEqual(len(second), 2)
        for call in second:
            self.assertNotIn("SECRET", call["url"])
            self.assertNotIn("SECRET", json.dumps(call["headers"]))

    def test_https_에서_http_로_내려가면_키를_싣지_않는다(self):
        answers = {"https://api.example.org/x": Response(302, headers={"Location": "http://api.example.org/y"}),
                   "http://api.example.org/y": Response(body=b"{}")}
        with resolves(HOSTS), sessions(answers):
            linked.fetch("https://api.example.org/x", {"mode": "query", "name": "apikey", "key": "SECRET"})
            linked.fetch("https://api.example.org/x", {"mode": "header", "name": "X-API-Key", "key": "SECRET"})
        down = [c for c in Session.calls if c["url"].startswith("http://")]
        self.assertEqual(len(down), 2)
        for call in down:
            self.assertNotIn("SECRET", call["url"] + json.dumps(call["headers"]))

    def test_http_에서_https_로_오르면_키를_싣는다(self):
        answers = {"http://api.example.org/x": Response(301, headers={"Location": "https://api.example.org/x"}),
                   "https://api.example.org/x": Response(body=b"{}")}
        with resolves(HOSTS), sessions(answers):
            linked.fetch("http://api.example.org/x", {"mode": "bearer", "key": "K"})
        self.assertEqual(Session.calls[-1]["headers"].get("Authorization"), "Bearer K")

    def test_조금씩_흘려도_전체_마감에서_끊는다(self):
        """한 번 읽기는 빨라도 다 합쳐 DEADLINE 을 넘으면 끊는다."""
        clock = iter(range(0, 1000, 3))                   # 부를 때마다 3 초씩 흐른다
        answers = {"https://api.example.org/x": Response(body=b"x" * (65536 * 50))}
        with resolves(HOSTS), sessions(answers), mock.patch("viewer.linked.time.monotonic", side_effect=lambda: next(clock)), \
                self.assertRaises(linked.LinkedError) as cm:
            linked.fetch("https://api.example.org/x", {})
        self.assertEqual(cm.exception.status, 504)

    def test_넘겨주기는_끝이_있다(self):
        answers = {"https://api.example.org/x": Response(302, headers={"Location": "/x"})}
        with resolves(HOSTS), sessions(answers), self.assertRaises(linked.LinkedError):
            linked.fetch("https://api.example.org/x", {})
        self.assertEqual(len(Session.calls), linked.MAX_REDIRECTS + 1)

    def test_너무_크면_끊는다(self):
        answers = {"https://api.example.org/x": Response(body=b"x" * (linked.MAX_BYTES + 10))}
        with resolves(HOSTS), sessions(answers), self.assertRaises(linked.LinkedError) as cm:
            linked.fetch("https://api.example.org/x", {})
        self.assertEqual(cm.exception.status, 413)

    def test_거절은_인증키를_보라고_한다(self):
        answers = {"https://api.example.org/x": Response(401)}
        with resolves(HOSTS), sessions(answers), self.assertRaises(linked.LinkedError) as cm:
            linked.fetch("https://api.example.org/x", {"mode": "bearer", "key": "bad"})
        self.assertIn("인증키", str(cm.exception))
        self.assertIn("401", i18n.t(cm.exception.args[0], "en"))


@override_settings(LINKED_ALLOW=[], PUBLIC=False)
class View(TestCase):
    URL = "/GSM/linked/fetch/"

    def setUp(self):
        linked._calls.clear()

    def post(self, body):
        return self.client.post(self.URL, data=json.dumps(body), content_type="application/json")

    def test_받은_것을_그대로_넘긴다(self):
        with mock.patch("viewer.linked.fetch", return_value=(b"#name: x\r\nlon,lat\r\n1,2\r\n", "text/csv")):
            r = self.post({"url": "https://api.example.org/x", "auth": {"mode": "none"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"#name: x\r\nlon,lat\r\n1,2\r\n")
        self.assertEqual(r["X-GSM-Content-Type"], "text/csv")
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_막힌_까닭을_말한다(self):
        with resolves(HOSTS):
            r = self.post({"url": "http://lab.local/", "auth": {}})
        self.assertEqual(r.status_code, 403)
        self.assertIn("연구실 망", r.json()["error"])

    def test_GET_은_받지_않는다(self):
        self.assertEqual(self.client.get(self.URL).status_code, 405)

    def test_너무_자주는_막는다(self):
        with mock.patch("viewer.linked.fetch", return_value=(b"{}", "")):
            codes = [self.post({"url": "https://api.example.org/x"}).status_code for _ in range(linked.RATE_PER_MINUTE + 1)]
        self.assertEqual(codes[-1], 429)
        self.assertEqual(set(codes[:-1]), {200})

    @override_settings(PUBLIC=True)
    def test_밖에_연_뷰어에서는_닫는다(self):
        with mock.patch("viewer.linked.fetch") as fetch:
            self.assertEqual(self.post({"url": "https://api.example.org/x"}).status_code, 404)
        fetch.assert_not_called()


class ExtraCA(SimpleTestCase):
    """연구소 망이 다시 서명한 https — 더 믿을 인증서가 있으면 연결에 싣는다 (wetherilli 126)."""

    def test_없으면_기본(self):
        with override_settings(EXTRA_CA=""):
            adapter = linked._Pinned("93.184.216.34")
        self.assertNotIn("ssl_context", adapter.poolmanager.connection_pool_kw)

    def test_있으면_싣는다(self):
        with override_settings(EXTRA_CA="/etc/ssl/certs/ca-certificates.crt"), \
                mock.patch("viewer.linked.ssl.SSLContext.load_verify_locations") as load:
            adapter = linked._Pinned("93.184.216.34")
        load.assert_called_once_with("/etc/ssl/certs/ca-certificates.crt")
        self.assertIn("ssl_context", adapter.poolmanager.connection_pool_kw)
