"""세계 빙하 — RGI 7.0 빙하 속성 CSV 를 `<EARTH_DIR>/glaciers.sqlite` 로 굽는다 (wetherilli 289).

    manage.py build_glaciers /nfs/temp-share/GSM/sources/earth/rgi7/RGI2000-v7.0-G-global-attributes.csv

원본은 RGI 7.0(CC BY 4.0) — OGGM 거울(cluster.klima.uni-bremen.de/~oggm/rgi/)에서 받았다. 운영은 `/srv/GSM/db/earth/`.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import glaciers


class Command(BaseCommand):
    help = "RGI 7.0 빙하 속성 CSV 를 glaciers.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("csv", help="RGI2000-v7.0-G-global-attributes.csv")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        try:
            got = glaciers.build(o["csv"], o["out"], log=self.stdout.write)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{got['rows']:,} 개 — {o['out'] or glaciers.path()} ({got['seconds']} 초)"))
