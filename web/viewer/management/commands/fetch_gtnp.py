"""GTN-P 영구동토 시추공 목록을 받아 `<GTNP_DIR>/gtnp_boreholes.json` 에 적는다 (wetherilli 422).

문(`gtnp.py`)으로 Arctic Portal 의 WFS 를 한 번 부른다(CSV 한 장, 시추공 1 389). 줄여 적기만 한다.
상류의 지온은 2016 년에 멈춰 있어 자주 받을 까닭이 없다 — 판을 붙이기 전이나 상류가 바뀌었다고 들으면 사람이 부른다. cron 에 두지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import gtnp


class Command(BaseCommand):
    help = "GTN-P 영구동토 시추공 → <GTNP_DIR>/gtnp_boreholes.json (wetherilli 422)"

    def handle(self, *args, **opts):
        out = gtnp.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stdout.write("Arctic Portal 에서 GTN-P 시추공 목록을 받는다 …")
        try:
            got = gtnp.download(out)
        except gtnp.GtnpError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"시추공 {got['boreholes']:,} · 지온이 있는 것 {got['magt']:,} → {out}")
