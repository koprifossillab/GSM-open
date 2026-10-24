"""빙저호 목록(Livingstone 외 2022)을 받아 `<GLACIO_DIR>/subglacial_lakes.json` 에 적는다 (wetherilli 420).

문(`orda.py`)으로 figshare 를 두 번 부른다 — 항목의 파일 목록, 엑셀 한 장(1 초 간격). 남극·그린란드 시트만 줄여 적는다.
목록은 몇 해에 한 번 고쳐진다 — cron 에 두지 않고 사람이 부른다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import orda


class Command(BaseCommand):
    help = "빙저호 목록 Livingstone 외 2022 (ORDA) → <GLACIO_DIR>/subglacial_lakes.json (wetherilli 420)"

    def handle(self, *args, **opts):
        out = orda.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stdout.write("figshare 에서 빙저호 목록을 받는다 …")
        try:
            got = orda.download(out)
        except orda.OrdaError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(" · ".join(f"{k} {n}" for k, n in got.items()) + f" → {out}")
