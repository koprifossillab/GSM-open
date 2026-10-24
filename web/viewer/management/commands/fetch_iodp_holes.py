"""과학 해양 시추(DSDP·ODP·IODP)의 시추공 목록을 받아 `<EARTH_DIR>/iodp_holes.json` 에 적는다 (wetherilli 418).

문(`iodp.py`)으로 `kml.iodp.org/Drilled_Holes.csv` 를 한 번 부른다(690 KB). 줄여 적기만 한다.
항차가 끝나 목록이 고쳐질 때(1 년에 몇 번) 사람이 다시 부른다 — cron 에 두지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import iodp


class Command(BaseCommand):
    help = "IODP 시추공 목록 → <EARTH_DIR>/iodp_holes.json (wetherilli 418)"

    def handle(self, *args, **opts):
        out = iodp.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stdout.write("IODP 에서 시추공 목록을 받는다 …")
        try:
            n = iodp.download(out)
        except iodp.IodpError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"시추공 {n:,} → {out}")
