"""sqlite 의 사본을 떠 표준 출력으로 낸다 — 호스트의 주간 백업이 컨테이너를 거쳐 DB 를 뜨는 길 (jikhanjung 017).

    docker compose exec -T -w /app/web web python manage.py backup_db > GSM.db             GSM.db 의 사본
    docker compose exec -T -w /app/web web python manage.py backup_db --store > store.sqlite  store.sqlite 의 사본

**호스트는 GSM.db 를 열지 않는다**(사람, 2026-10-07, jikhanjung P03) — 백업도 그렇다. 살아 있는 DB 는 컨테이너 안에서만 연다.
sqlite 의 온라인 백업(쓰는 중에도 한 시점의 온전한 사본)으로 컨테이너의 임시 자리에 뜨고, `integrity_check` 를 지난 사본만 바이트째
표준 출력으로 흘린다. 호스트는 받은 파일을 tar 에 담기만 한다 — 살아 있는 DB 의 잠금·저널·(뒤의 WAL 의 -shm)에 닿지 않는다.
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
            out = sys.stdout.buffer
            with open(copy, "rb") as fh:
                shutil.copyfileobj(fh, out, 1 << 20)
            out.flush()
            self.stderr.write(f"{src.name} 사본 {os.path.getsize(copy):,} 바이트를 냈다")
        finally:
            shutil.rmtree(work, ignore_errors=True)
