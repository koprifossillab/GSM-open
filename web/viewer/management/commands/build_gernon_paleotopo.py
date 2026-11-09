"""동남극 고지형 Gernon 외 2026 을 연대마다 칠해 3031 타일로 잘라 둔다 (wetherilli 436).

원본은 Zenodo 19205651 의 zip 하나(CC BY 4.0, 계정 없이 받는다):

    https://zenodo.org/records/19205651   → GIS_files.zip (47 MB, GeoTIFF 34 장 + 관심 구역 셰이프)

NAS `sources/antarctic_papers/` 에 두고 부른다. Pillow 로 읽어 numpy 없이 컨테이너에서도 돈다:

    manage.py build_gernon_paleotopo /nfs/temp-share/GSM/sources/antarctic_papers/gernon2026_zenodo_19205651_GIS_files.zip

내는 연대 열 개(`gernontopo.AGES`)만 굽는다. 결과는 `<GSM_GERNON_PALEOTOPO_DIR>/<연대>/` — 운영은 `/srv/GSM/db/gernon_paleotopo/`.
"""
import time
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import gernontopo, polargrid


class Command(BaseCommand):
    help = "동남극 고지형(Gernon 외 2026, FastScape 모형)을 연대마다 칠해 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="Zenodo 19205651 의 GIS_files zip")
        parser.add_argument("--out", default=None, help="기본: GSM_GERNON_PALEOTOPO_DIR (연대마다 하위 폴더)")

    def handle(self, *args, **o):
        path = Path(o["zip"])
        try:
            found = gernontopo.members(path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise CommandError(f"{path}: {exc}") from exc
        missing = [a for a in gernontopo.AGES if a not in found]
        if not found:
            raise CommandError("COB160BestFitModel<NNN>Ma.tif 가 하나도 없다")
        if missing:
            self.stderr.write(f"없는 연대 — {', '.join(map(str, missing))} Ma")
        with zipfile.ZipFile(path) as z:
            for age in sorted(found, reverse=True):
                started = time.monotonic()
                spec = gernontopo.SETS[f"{gernontopo.UPSTREAM}:{gernontopo.kind(age)}"]
                out = Path(o["out"]) / gernontopo.kind(age) if o["out"] else None
                try:
                    grid = gernontopo.read_tif(z.read(found[age]))
                    stats = polargrid.bake(spec, grid, Path(found[age]).name, out, log=self.stdout.write)
                except (OSError, ValueError, polargrid.PolarGridError) as exc:
                    raise CommandError(f"{found[age]}: {exc}") from exc
                self.stdout.write(self.style.SUCCESS(
                    f"{spec.name}: 타일 {stats['tiles']} 장, {stats['mb']} MB — {out or spec.root()} ({time.monotonic() - started:.0f} 초)"))
