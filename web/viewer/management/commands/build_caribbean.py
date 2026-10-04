"""USGS 대앤틸리스·버진아일랜드 지질도(OFR 2019-1036 · SIM 3534)를 sqlite 한 장으로 굽는다 (wetherilli 254).

    manage.py build_caribbean /nfs/temp-share/GSM/sources/caribbean/ofr20191036_spatialdata.zip

원본 zip(196 MB) 또는 푼 폴더를 받는다. 결과는 `<GSM_CARIBBEAN_DIR>/sim3534.sqlite` — 운영은 `/srv/GSM/db/caribbean/`.
원본은 NAS `N:\\GSM\\sources\\caribbean\\` 에 둔다. 굽는 법(`caribmap.build`)을 고치면 다시 부른다. 그리는 법만 고쳤으면
`caribmap.RENDERER` 를 올리면 된다.
"""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import caribmap


class Command(BaseCommand):
    help = "USGS 대앤틸리스 지질도(zip)를 sim3534.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="ofr20191036_spatialdata.zip 또는 푼 폴더")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        out = Path(o["out"]) if o["out"] else caribmap.data_file()
        started = time.time()
        try:
            counts = caribmap.build(o["source"], out)
        except (OSError, caribmap.CaribMapError) as exc:
            raise CommandError(str(exc)) from exc
        size = out.stat().st_size / 1e6
        self.stdout.write(f"{out} — 단위 {counts['units']:,} · 단층 {counts['faults']:,} · {size:.1f} MB · {time.time() - started:.0f} 초")
