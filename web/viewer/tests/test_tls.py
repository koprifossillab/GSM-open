"""연구소 망이 다시 서명한 잎 — AKI 가 없는 인증서를 파이썬 3.13+ 에서도 받되 검증은 끄지 않는다 (wetherilli 426)."""
import http.server
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from viewer import tls


def _openssl(*args, cwd):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


def make_chain(folder: Path, ca_name: str) -> tuple[Path, Path, Path]:
    """CA 하나와, 장비처럼 **SAN 말고 확장이 없는**(AKI 가 없는) 잎(localhost). (CA, 잎, 잎 키)"""
    _openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem",
             "-days", "2", "-subj", f"/CN={ca_name}", cwd=folder)
    _openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr",
             "-subj", "/CN=localhost", cwd=folder)
    (folder / "ext.cnf").write_text("subjectKeyIdentifier=none\nauthorityKeyIdentifier=none\nsubjectAltName=DNS:localhost\n")
    _openssl("x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-out", "leaf.pem",
             "-days", "2", "-extfile", "ext.cnf", cwd=folder)
    return folder / "ca.pem", folder / "leaf.pem", folder / "leaf.key"


class _Ok(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def serve(leaf: Path, key: Path):
    """잎을 내미는 https 하나. (주소, 끄는 함수)"""
    server = http.server.HTTPServer(("127.0.0.1", 0), _Ok)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(leaf, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop():
        server.shutdown()
        server.server_close()
    return f"https://localhost:{server.server_address[1]}/", stop


@unittest.skipUnless(shutil.which("openssl"), "openssl 이 없다")
class InterceptedLeafTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        (folder / "lab").mkdir()
        (folder / "other").mkdir()
        cls.ca, leaf, key = make_chain(folder / "lab", "KOPRI SSL")
        cls.stranger, _, _ = make_chain(folder / "other", "KOPRI SSL")   # 이름만 같고 키가 다른 CA
        cls.url, cls.stop = serve(leaf, key)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()
        super().tearDownClass()

    def setUp(self):
        tls._trusts_interceptor.cache_clear()
        self.addCleanup(tls._trusts_interceptor.cache_clear)

    def get(self, bundle):
        with override_settings(CA_BUNDLE=str(bundle), EXTRA_CA=""):
            return requests.get(self.url, verify=str(bundle), timeout=10)

    def test_requests_accepts_the_leaf_when_the_bundle_trusts_the_interceptor(self):
        self.assertEqual(self.get(self.ca).text, "ok")

    @unittest.skipIf(sys.version_info < (3, 13), "3.12 는 엄격 검사가 기본이 아니다")
    def test_strict_check_stays_elsewhere(self):
        # 꾸러미의 CA 가 가로채는 장비의 것이 아니면 3.13+ 의 엄격 검사는 그대로다
        with mock.patch.object(tls, "INTERCEPT_CAS", ("Somebody Else",)):
            with self.assertRaisesRegex(requests.exceptions.SSLError, "Authority Key Identifier"):
                self.get(self.ca)

    def test_verification_is_not_switched_off(self):
        # 이름이 같아도 그 CA 가 서명하지 않았으면 멈춘다
        with self.assertRaises(requests.exceptions.SSLError):
            self.get(self.stranger)

    def test_hand_built_context(self):
        with override_settings(CA_BUNDLE=str(self.ca), EXTRA_CA=""):
            ctx = tls.context(cafile=str(self.ca))
        self.assertFalse(ctx.verify_flags & ssl.VERIFY_X509_STRICT)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_install_is_idempotent(self):
        import urllib3.connection
        before = urllib3.connection.create_urllib3_context
        tls.install()
        self.assertIs(urllib3.connection.create_urllib3_context, before)
