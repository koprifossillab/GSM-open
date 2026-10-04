"""지열류 — IHFC 세계 지열류 자료 2024 판을 `<EARTH_DIR>/heatflow.sqlite` 로 굽는다 (wetherilli 267).

    manage.py build_heatflow /nfs/temp-share/GSM/sources/earth/GHFDB-R2024_v.2026-03.zip

원본은 GFZ Data Services(doi:10.5880/fidgeo.2024.014, CC BY 4.0). 운영은 `/srv/GSM/db/earth/`. 새 판이 나오면 zip 만 바꿔 다시 부른다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import heatflow


class Command(BaseCommand):
    help = "IHFC 세계 지열류 자료(zip 또는 .txt)를 heatflow.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="GHFBD-R2024_*.zip 또는 IHFC_2024_GHFDB_*.txt")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        try:
            got = heatflow.build(o["source"], o["out"], log=self.stdout.write)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{got['rows']:,} 곳 — {o['out'] or heatflow.path()} ({got['seconds']} 초)"))
