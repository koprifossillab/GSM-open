"""sqlite 의 사본을 떠 표준 출력으로 낸다 — 호스트의 주간 백업이 컨테이너를 거쳐 DB 를 뜨는 길 (jikhanjung 017).

    docker compose exec -T -w /app/web web python manage.py backup_db > GSM.db             GSM.db 의 사본
    docker compose exec -T -w /app/web web python manage.py backup_db --store > store.sqlite  store.sqlite 의 사본

**호스트는 GSM.db 를 열지 않는다**(사람, 2026-10-07, jikhanjung P03) — 백업도 그렇다. 살아 있는 DB 는 컨테이너 안에서만 연다.
sqlite 의 온라인 백업(쓰는 중에도 한 시점의 온전한 사본)으로 컨테이너의 임시 자리에 뜨고, `integrity_check` 를 지난 사본에서
로그인 세션을 지우고(VACUUM, jikhanjung 025) 바이트째 표준 출력으로 흘린다. 호스트는 받은 파일을 tar 에 담기만 한다 — 살아 있는 DB 의 잠금·저널·(뒤의 WAL 의 -shm)에 닿지 않는다.
실패하면 아무것도 내지 않고 1 로 끝난다 — 호스트는 빈 파일을 보고 멈춘다.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog


def _scrub(copy: Path):
    """서버를 떠날 사본을 손질한다 — **무결성 검사 뒤에**(앞에 두면 깨진 원본의 VACUUM 이 예외를 낸다).

    - **로그인 세션을 지운다**(`django_session` 을 비우고 VACUUM) — 세션 키가 곧 쿠키 값이라 사본을 읽은 사람이 그대로 로그인된다.
      사본은 누구나 읽는 NAS 로 간다. 탭의 로그인·staff 계정이 생겨(jikhanjung 020) 세션이 쌓이기 시작했다. 비밀번호 해시는 둔다.
      VACUUM 까지 — 지운 세션이 빈 페이지에 남는다 (.guides/web/data-safety.md §7, jikhanjung 025)
    - **저널 모드를 DELETE 로** — 사본은 원본의 저널 모드를 물려받는다. 뒤에 원본을 WAL 로 바꿔도 사본은 파일 하나로 완결되게 (§5)
    """
    db = sqlite3.connect(copy)
    try:
        db.execute("PRAGMA journal_mode=DELETE")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='django_session'").fetchone():
            db.execute("DELETE FROM django_session")
            db.commit()
        db.execute("VACUUM")
    finally:
        db.close()


class Command(BaseCommand):
    help = "GSM.db(또는 --store 면 store.sqlite)의 사본을 떠 표준 출력으로 낸다 — 주간 백업이 컨테이너를 거쳐 부른다"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--store", action="store_true", help="GSM.db 대신 store.sqlite")

    def handle(self, *args, **opts):
        fetchlog.refuse_on_host("backup_db")
        src = Path(settings.STORE_PATH if opts["store"] else settings.DATABASES["default"]["NAME"])
        if not src.exists():
            raise CommandError(f"{src.name} 가 없다")
        work = Path(tempfile.mkdtemp(prefix="gsm-backup-"))
        try:
            copy = work / src.name
            live = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=60)
            dst = sqlite3.connect(copy)
            try:
                live.backup(dst)
                ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                dst.close()
                live.close()
            if ok != "ok":
                raise CommandError(f"{src.name} 사본이 integrity_check 를 지나지 못했다: {ok}")
            _scrub(copy)
            out = sys.stdout.buffer
            with open(copy, "rb") as fh:
                shutil.copyfileobj(fh, out, 1 << 20)
            out.flush()
            self.stderr.write(f"{src.name} 사본 {os.path.getsize(copy):,} 바이트를 냈다")
        finally:
            shutil.rmtree(work, ignore_errors=True)
