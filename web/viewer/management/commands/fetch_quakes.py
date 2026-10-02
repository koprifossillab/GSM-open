"""USGS 의 M5 이상 지진을 모두 받아 `<EARTH_DIR>/quakes.sqlite` 로 굽는다 (wetherilli 138).

문(`usgs.py`)으로 1900 년부터 5 년씩 끊어 1 초 간격으로 묻는다(26 번 남짓, 1 분 안팎). 받은 CSV 는
`<EARTH_DIR>/quakes.csv` 에 남기고, `--csv` 로 받아 둔 것을 다시 구울 수 있다. 새 지진이 쌓이니 가끔 다시 부른다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import quakes, usgs


class Command(BaseCommand):
    help = "USGS M5 이상 지진 → <EARTH_DIR>/quakes.sqlite (wetherilli 138)"

    def add_arguments(self, parser):
        parser.add_argument("--csv", help="받아 둔 CSV 로 굽기만 한다 (상류를 부르지 않는다)")

    def handle(self, *args, **opts):
        out = quakes.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        src = Path(opts["csv"]) if opts["csv"] else out.parent / "quakes.csv"
        if not opts["csv"]:
            self.stdout.write("USGS 에서 받는다 …")
            try:
                n = usgs.download(src, log_line=self.stdout.write)
            except usgs.UsgsError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"  {n:,} 건")
        got = quakes.build(src, out, log=self.stdout.write)
        self.stdout.write(f"{got['rows']:,} 곳 (좌표·규모 없는 것과 겹친 것 {got['skipped']:,}) · {got['seconds']} 초 → {out}")
