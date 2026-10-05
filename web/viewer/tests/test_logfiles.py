"""판을 다시 띄워도 남는 기록 (wetherilli 351) — 하루 한 장, 크기 한도, 지우는 날, 키 지우기"""
import datetime
import logging
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from gsmweb import logfiles

REPO = Path(__file__).resolve().parents[3]


def record(msg, *args):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args or None, None)


class Redact(SimpleTestCase):
    def test_질의의_키를_지운다(self):
        self.assertEqual(logfiles.redact("GET /GSM/wms/?key=abc&x=1"), "GET /GSM/wms/?key=…&x=1")
        self.assertEqual(logfiles.redact("/a?apikey=s3cr3t HTTP/1.1"), "/a?apikey=… HTTP/1.1")
        self.assertEqual(logfiles.redact("/a?x=1&access_token=t0k"), "/a?x=1&access_token=…")
        self.assertEqual(logfiles.redact("/a?whoami=me@example.org&y=2"), "/a?whoami=…&y=2")

    def test_인코딩된_주소_안의_키도(self):
        # 연결 레이어 — 남의 주소가 url= 에 인코딩돼 들어온다
        line = "/GSM/linked/fetch/?url=https%3A%2F%2Fa.example%2Fq%3Fapikey%3DSECRET%26f%3Djson"
        out = logfiles.redact(line)
        self.assertNotIn("SECRET", out)
        self.assertIn("%26f%3Djson", out)

    def test_키가_없으면_그대로(self):
        line = '127.0.0.1 - - "GET /GSM/wms/?LAYERS=lneg:500k:2&BBOX=1,2,3,4 HTTP/1.1" 200 3487'
        self.assertEqual(logfiles.redact(line), line)

    def test_화면으로_가는_줄에도(self):
        r = record('"GET %s"', "/x?key=abc")
        logfiles.RedactFilter().filter(r)
        self.assertEqual(r.getMessage(), '"GET /x?key=…"')


class DailyFileTests(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.day = datetime.date(2026, 10, 5)

    def make(self, **kw):
        h = logfiles.DailyFile(self.dir, "access", today=lambda: self.day, **kw)
        h.setFormatter(logging.Formatter("%(message)s"))
        self.addCleanup(h.close)
        return h

    def test_하루_한_장이고_날이_바뀌면_새_장(self):
        h = self.make()
        h.emit(record("one ?key=abc"))
        self.day = datetime.date(2026, 10, 6)
        h.emit(record("two"))
        self.assertEqual((self.dir / "access-20261005.log").read_text(), "one ?key=…\n")
        self.assertEqual((self.dir / "access-20261006.log").read_text(), "two\n")

    def test_두_손잡이가_한_장에_보탠다(self):
        # 워커마다 손잡이가 따로다 — 덮지 않고 잇는다
        a, b = self.make(), self.make()
        a.emit(record("a")); b.emit(record("b")); a.emit(record("c"))
        self.assertEqual((self.dir / "access-20261005.log").read_text(), "a\nb\nc\n")

    def test_한도를_넘으면_한_줄만_남기고_멈춘다(self):
        h = self.make(max_bytes=40)
        for i in range(10):
            h.emit(record(f"line {i:02d}"))
        text = (self.dir / "access-20261005.log").read_text()
        self.assertEqual(text.count("line"), 5)
        self.assertEqual(text.count("한도"), 1)

    def test_오래된_장을_지운다(self):
        for stamp in ("20260801", "20260904", "20260905", "20261004"):
            (self.dir / f"access-{stamp}.log").write_text("old\n")
        (self.dir / "app-20260801.log").write_text("other prefix\n")
        self.make(keep_days=30).emit(record("new"))
        left = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(left, ["access-20260905.log", "access-20261004.log", "access-20261005.log", "app-20260801.log"])

    def test_여러_줄은_들여_쓴다(self):
        h = self.make()
        h.emit(record("Traceback\nline 2"))
        self.assertEqual((self.dir / "access-20261005.log").read_text(), "Traceback\n  line 2\n")


class Wiring(SimpleTestCase):
    def test_자리가_없으면_손잡이도_없다(self):
        import os
        old = os.environ.pop("GSM_LOG_DIR", None)
        try:
            self.assertIsNone(logfiles.handler("access", "%(message)s"))
        finally:
            if old is not None:
                os.environ["GSM_LOG_DIR"] = old

    def test_컨테이너가_자리를_주고_백업은_뺀다(self):
        entry = (REPO / "deploy/entrypoint-web.sh").read_text()
        self.assertIn("--config /app/deploy/gunicorn.conf.py", entry)
        self.assertIn('GSM_LOG_DIR="${GSM_LOG_DIR:-$(dirname', entry)
        self.assertTrue((REPO / "deploy/gunicorn.conf.py").exists())
        backup = (REPO / "deploy/scripts/weekly_backup.sh").read_text()
        self.assertRegex(backup, r"SECRETS='[^']*\|logs/\.\*\)\$'")
