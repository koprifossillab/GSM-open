"""GVP 의 화산을 모두 받아 `<EARTH_DIR>/gvp_volcanoes.json`·`gvp_pleistocene.json` 에 적는다 (wetherilli 134·194).

문(`gvp.py`)으로 WFS 를 갈래마다 한 번 부른다(홀로세 2.4 MB·플라이스토세 1 452 곳, 몇 초씩). 받은 것을 줄여 적기만 하고 굽지 않는다.
GVP 가 판을 올리면(Volcanoes of the World v5.x, 1 년에 한두 번) 다시 부른다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import gvp, volcanoes


class Command(BaseCommand):
    help = "GVP 화산 → <EARTH_DIR>/gvp_volcanoes.json·gvp_pleistocene.json (wetherilli 134·194)"

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=tuple(gvp.LAYERS), action="append",
                            help="받을 갈래 (여럿 줄 수 있다). 없으면 둘 다")

    def handle(self, *args, **opts):
        for kind in opts.get("kind") or tuple(gvp.LAYERS):
            out = volcanoes.path(kind)
            out.parent.mkdir(parents=True, exist_ok=True)
            self.stdout.write(f"GVP 에서 받는다 ({kind}) …")
            try:
                n = gvp.download(out, kind)
            except gvp.GvpError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"화산 {n:,} 곳 → {out}")
