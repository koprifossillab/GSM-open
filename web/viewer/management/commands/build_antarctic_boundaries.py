"""남극 접지선·빙붕·유역(MEaSUREs)을 줄여 위경도 한 덩이로 굽는다 (wetherilli 460).

원본은 NASA Earthdata 로그인 뒤의 NSIDC 클라우드 — 사람이 받아 온 토큰으로 한 번 받아 NAS `sources/antarctica/measures/` 에 둔다:

    …/MEASURES/NSIDC-0498/2/1992/02/07/InSAR_GL_Antarctica_v02.1.gpkg
    …/MEASURES/NSIDC-0709/2/1992/02/07/{IceShelf,Basins,Basins_IMBIE,GroundingLine}_Antarctica_v02.{shp,shx,dbf,prj}

numpy 없이 돈다 — 컨테이너에서 부른다:

    docker compose exec web python manage.py build_antarctic_boundaries /srv/GSM/db/sources/measures/

결과는 `<GSM_GLACIO_DIR>/antarctic_boundaries.json`(7 MB 남짓). 몇 초다.
"""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import antbounds


class Command(BaseCommand):
    help = "남극 접지선(InSAR, NSIDC-0498)·빙붕·유역(NSIDC-0709)을 줄여 위경도 한 덩이로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="gpkg 와 셰이프들이 든 폴더")
        parser.add_argument("--out", default=None, help=f"기본: GSM_GLACIO_DIR/{antbounds.FILE}")

    def handle(self, *args, **o):
        folder = Path(o["source"])
        if not folder.is_dir():
            raise CommandError(f"폴더가 아니다 — {folder}")
        started = time.monotonic()
        try:
            counts = antbounds.build(folder, o["out"])
        except (OSError, antbounds.AntBoundsError) as exc:
            raise CommandError(str(exc)) from exc
        mb = counts.pop("mb")
        for name, n in counts.items():
            self.stdout.write(f"{name}: {n:,}")
        self.stdout.write(self.style.SUCCESS(
            f"{o['out'] or antbounds.path()} — {mb} MB ({time.monotonic() - started:.0f} 초)"))
