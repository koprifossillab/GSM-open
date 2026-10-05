"""레이어 대조의 기록과 견주기 (wetherilli 314)."""
import datetime
import io
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import verifylog


class History(TestCase):
    def setUp(self):
        patch = override_settings(VERIFY_DIR=tempfile.mkdtemp(prefix="gsm-verify-"))
        patch.enable()
        self.addCleanup(patch.disable)
        day = datetime.date(2026, 10, 1)
        verifylog.record({"a": {"upstream": "x", "kind": "그림", "note": ""}, "b": {"upstream": "x", "kind": "오류", "note": "500"},
                          "c": {"upstream": "y", "kind": "그림", "note": ""}}, day)
        # 다음 날은 상류 x 만 돌렸다 — c 는 견주지 않는다
        verifylog.record({"a": {"upstream": "x", "kind": "빈 그림", "note": "5/1/1"}, "b": {"upstream": "x", "kind": "그림", "note": ""}},
                         day + datetime.timedelta(days=1))

    def test_새로_깨진_것과_고쳐진_것(self):
        got = verifylog.diff()
        self.assertEqual((got["day"], got["previous"]), ("2026-10-02", "2026-10-01"))
        self.assertEqual([n for n, *_ in got["newly"]], ["a"])
        self.assertEqual([n for n, *_ in got["fixed"]], ["b"])

    def test_같은_날은_보탠다(self):
        verifylog.record({"d": {"upstream": "z", "kind": "그림", "note": ""}}, datetime.date(2026, 10, 2))
        self.assertEqual(set(verifylog.load(verifylog.files()[-1])["layers"]), {"a", "b", "d"})

    def test_명령과_관리_화면(self):
        out = io.StringIO()
        call_command("verify_layers", diff=True, stdout=out)
        self.assertIn("새로 깨짐 `a`", out.getvalue())
        html = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("2026-10-02", html)
        self.assertIn("새로 깨진 것 1", html)
        self.assertIn("Newly broken since the previous check: 1",
                      self.client.get("/GSM/manage/", HTTP_ACCEPT_LANGUAGE="en").content.decode())
