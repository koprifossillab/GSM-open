"""남극순환류 전선 — Park & Durand 2019 의 NetCDF 를 `data/acc_fronts.json` 으로 굽는다 (wetherilli 429).

    manage.py build_acc_fronts 62985.nc

원본은 SEANOE(https://doi.org/10.17882/59800 의 `data/62985.nc`, 321 KB, CC BY 4.0). 구운 것은 작아서 저장소에 둔다 —
다시 구우면 그 파일을 커밋한다. numpy 없이 돈다(`seafloor.read_netcdf3`).
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import accfronts


class Command(BaseCommand):
    help = "남극순환류 전선 NetCDF 를 data/acc_fronts.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("netcdf", help="SEANOE 59800 의 62985.nc")

    def handle(self, *args, **o):
        try:
            counts = accfronts.build(Path(o["netcdf"]).read_bytes())
        except (OSError, accfronts.AccFrontsError) as exc:
            raise CommandError(str(exc)) from exc
        path = accfronts.path()
        self.stdout.write(self.style.SUCCESS(
            f"{path} — " + " · ".join(f"{k} {v:,}" for k, v in counts.items()) + f" · {path.stat().st_size // 1024} KB"))
