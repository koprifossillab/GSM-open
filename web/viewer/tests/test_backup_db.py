"""`manage.py backup_db` — 주간 백업이 컨테이너를 거쳐 DB 사본을 받는 길 (jikhanjung 017).

지키는 것 — 표준 출력이 온전한 sqlite 한 장이다(다른 글이 섞이지 않는다), --store 는 store.sqlite, 호스트에서는 멈춘다, 없으면 멈춘다.
"""
import io
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


def _run(*args):
    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="utf-8")
    with mock.patch.object(sys, "stdout", out):
        call_command("backup_db", *args, stderr=io.StringIO())
        out.flush()
    return raw.getvalue()


class BackupDb(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for name, table in (("GSM.db", "gsm"), ("store.sqlite", "store")):
            db = sqlite3.connect(self.dir / name)
            db.execute(f"CREATE TABLE {table} (x)")
            db.execute(f"INSERT INTO {table} VALUES (1)")
            db.commit()
            db.close()
        over = override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(self.dir / "GSM.db")}},
                                 STORE_PATH=str(self.dir / "store.sqlite"))
        over.enable()
        self.addCleanup(over.disable)

    def opened(self, data):
        copy = self.dir / "copy.sqlite"
        copy.write_bytes(data)
        db = sqlite3.connect(copy)
        try:
            return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        finally:
            db.close()

    def test_표준_출력이_온전한_사본(self):
        data = _run()
        self.assertTrue(data.startswith(b"SQLite format 3\x00"))
        self.assertEqual(self.opened(data), ["gsm"])

    def test_store(self):
        self.assertEqual(self.opened(_run("--store")), ["store"])

    def test_호스트에서는_멈춘다(self):
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}), self.assertRaisesRegex(CommandError, "컨테이너 안에서"):
            _run()

    def test_없으면_멈춘다(self):
        (self.dir / "store.sqlite").unlink()
        with self.assertRaises(CommandError):
            _run("--store")
