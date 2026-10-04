"""지각 응력 — World Stress Map 2025 CSV 를 `<EARTH_DIR>/stress.sqlite` 로 굽는다 (wetherilli 273).

    manage.py build_stress /nfs/temp-share/GSM/sources/earth/WSM_Database_2025.csv

원본은 GFZ Data Services(doi:10.5880/WSM.2025.001, CC BY 4.0). 운영은 `/srv/GSM/db/earth/`.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import stress


class Command(BaseCommand):
    help = "World Stress Map 2025 CSV 를 stress.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("csv", help="WSM_Database_2025.csv")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        try:
            got = stress.build(o["csv"], o["out"], log=self.stdout.write)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{got['rows']:,} 곳 — {o['out'] or stress.path()} ({got['seconds']} 초)"))
