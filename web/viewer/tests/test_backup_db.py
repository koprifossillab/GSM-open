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


class Scrub(SimpleTestCase):
    """서버를 떠날 사본에서 로그인 세션을 지운다 — 무결성 검사 뒤, VACUUM 까지, 저널은 DELETE (jikhanjung 025)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        db = sqlite3.connect(self.dir / "GSM.db")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE django_session (session_key TEXT PRIMARY KEY, session_data TEXT, expire_date TEXT)")
        db.execute("CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
        db.execute("INSERT INTO django_session VALUES ('쿠키값SECRETKEY', 'data', '2099-01-01')")
        db.execute("INSERT INTO auth_user VALUES (1, 'koprifossillab', 'pbkdf2_sha256$hash')")
        db.commit()
        db.close()
        over = override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(self.dir / "GSM.db")}},
                                 STORE_PATH=str(self.dir / "store.sqlite"))
        over.enable()
        self.addCleanup(over.disable)

    def test_세션은_비우고_계정은_둔다(self):
        data = _run()
        self.assertNotIn(b"SECRETKEY", data)                     # VACUUM — 빈 페이지에도 남지 않는다
        copy = self.dir / "copy.sqlite"
        copy.write_bytes(data)
        db = sqlite3.connect(copy)
        try:
            self.assertEqual(db.execute("SELECT count(*) FROM django_session").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT username FROM auth_user").fetchall(), [("koprifossillab",)])
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        finally:
            db.close()
        live = sqlite3.connect(self.dir / "GSM.db")                # 살아 있는 DB 는 그대로
        try:
            self.assertEqual(live.execute("SELECT count(*) FROM django_session").fetchone()[0], 1)
        finally:
            live.close()


class WeeklyBackupNames(SimpleTestCase):
    """weekly_backup.sh 의 이름 짓기와 ② 줄이기 — 같은 날 두 번째는 덮지 않고, 줄이기는 그것도 센다 (jikhanjung 025)."""

    SCRIPT = Path(__file__).resolve().parents[3] / "deploy/scripts/weekly_backup.sh"

    def func(self, name):
        text = self.SCRIPT.read_text(encoding="utf-8")
        start = text.index(f"{name}() {{")
        return text[start:text.index("\n}\n", start) + 3]

    def bash(self, body, cwd):
        import subprocess
        script = "set -u\nnas_up() { return 1; }\nNAS=/nonexistent\n" + self.func("free_name") + self.func("prune_built") + body
        out = subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_같은_날_두_번째는_점_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.bash("free_name \"$PWD/GSM.20261012\" .tar.gz", d).strip(), f"{d}/GSM.20261012.tar.gz")
            Path(d, "GSM.20261012.tar.gz").write_text("아침")
            Path(d, "GSM.20261012.2.tar.gz").write_text("낮")
            self.assertEqual(self.bash("free_name \"$PWD/GSM.20261012\" .tar.gz", d).strip(), f"{d}/GSM.20261012.3.tar.gz")

    def test_줄이기는_달마다_가장_새_것_하나(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            now = time.time()
            names = {"GSM-built.20260102.tar": 300, "GSM-built.20260115.tar": 290, "GSM-built.20260115.2.tar": 289,
                     "GSM-built.20260203.tar": 260, "GSM-built.20260210.tar": 250}
            for name, days in names.items():
                p = Path(d, name)
                p.write_text("x")
                os.utime(p, (now - days * 86400,) * 2)
            recent = Path(d, "GSM-built.29991231.tar")             # 30 일 안 — 다 둔다(날짜가 미래면 cutoff 보다 크다)
            recent.write_text("x")
            self.bash('prune_built "$PWD"', d)
            kept = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(kept, ["GSM-built.20260115.2.tar", "GSM-built.20260210.tar", "GSM-built.29991231.tar"])
