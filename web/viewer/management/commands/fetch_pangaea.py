"""PANGAEA 극지 현장 둘레의 자료 목록을 받아 `<PANGAEA_DIR>/pangaea.json` 에 적는다 (wetherilli 421).

문(`pangaea.py`)으로 PANGAEA 검색(Elasticsearch)을 200 건씩 1 초 간격으로 부른다 — 현장 다섯, 5 600 건 남짓, 서른 쪽 남짓.
자료는 꾸준히 늘지만 빠르지 않으니 판을 붙이기 전이나 몇 달에 한 번 사람이 부른다 — cron 에 두지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import pangaea


class Command(BaseCommand):
    help = "PANGAEA 극지 현장 둘레의 자료 목록 → <PANGAEA_DIR>/pangaea.json (wetherilli 421)"

    def handle(self, *args, **opts):
        self.stdout.write("PANGAEA 에서 현장 둘레의 자료 목록을 받는다 …")
        try:
            counts = pangaea.download(say=self.stdout.write)
        except pangaea.PangaeaError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(" · ".join(f"{area} {n:,}" for area, n in counts.items())
                          + f" → {pangaea.path()}")
