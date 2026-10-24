"""SCAR KGIS 킹조지섬 지형 DB 의 셰이프 zip 열여섯을 `<KGIS_DIR>` 에 받는다 (wetherilli 424).

문(`kgis.py`)으로 AWI ePIC 의 핸들을 1 초 간격으로 푼다(다 합쳐 6.5 MB). 2007 년에 멈춘 자료라 한 번 받으면 끝이다 —
cron 에 두지 않는다. 있는 zip 은 건너뛰고, `--force` 면 다시 받는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import kgis


class Command(BaseCommand):
    help = "SCAR KGIS 킹조지섬 지형 DB(PANGAEA.837976) → <KGIS_DIR>/*.zip (wetherilli 424)"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="있는 zip 도 다시 받는다")

    def handle(self, *args, **opts):
        self.stdout.write(f"AWI ePIC 에서 SCAR KGIS 를 받는다 → {kgis.root()}")
        try:
            got = kgis.download(force=opts["force"], log_line=self.stdout.write)
        except kgis.KgisError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"받음 {got['got']} · 있어서 건너뜀 {got['skipped']} · {got['bytes'] / 1e6:.1f} MB")
