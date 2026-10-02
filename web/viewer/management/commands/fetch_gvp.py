"""GVP 의 홀로세 화산을 모두 받아 `<EARTH_DIR>/gvp_volcanoes.json` 에 적는다 (wetherilli 134).

문(`gvp.py`)으로 WFS 를 한 번 부른다(2.4 MB, 몇 초). 화산 1 200 여 개라 받은 것을 줄여 적기만 하고 굽지 않는다.
GVP 가 판을 올리면(Volcanoes of the World v5.x, 1 년에 한두 번) 다시 부른다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import gvp, volcanoes


class Command(BaseCommand):
    help = "GVP 홀로세 화산 → <EARTH_DIR>/gvp_volcanoes.json (wetherilli 134)"

    def handle(self, *args, **opts):
        out = volcanoes.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stdout.write("GVP 에서 받는다 …")
        try:
            n = gvp.download(out)
        except gvp.GvpError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"화산 {n:,} 곳 → {out}")
