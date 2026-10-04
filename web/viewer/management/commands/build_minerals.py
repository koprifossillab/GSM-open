"""세계 광상 — USGS 광물 자원 자료 여섯을 `<EARTH_DIR>/minerals.sqlite` 로 굽는다 (wetherilli 276).

    manage.py build_minerals /nfs/temp-share/GSM/sources/earth/usgs_minerals

폴더에 mrdata.usgs.gov 의 `mrds-csv.zip`·`porcu-csv.zip`·`sedcu-csv.zip`·`vms-csv.zip`·`podchrome-csv.zip`·`ree-csv.zip` 을 둔다
(공공 도메인). 없는 묶음은 건너뛴다. 운영은 `/srv/GSM/db/earth/`. 새 판이 나오면 zip 만 바꿔 다시 부른다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import minerals


class Command(BaseCommand):
    help = "USGS 광물 자원 자료(MRDS·세계 광상 표 CSV zip 이 든 폴더)를 minerals.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("folder", help="mrds-csv.zip·porcu-csv.zip … 이 든 폴더")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        try:
            got = minerals.build(o["folder"], o["out"], log=self.stdout.write)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{got['rows']:,} 곳 — {o['out'] or minerals.path()} ({got['seconds']} 초)"))
