"""동남극 고지형 Gernon 외 2026 을 연대마다 칠해 3031 타일로 잘라 둔다 (wetherilli 436).

원본은 Zenodo 19205651 의 zip 하나(CC BY 4.0, 계정 없이 받는다):

    https://zenodo.org/records/19205651   → GIS_files.zip (47 MB, GeoTIFF 34 장 + 관심 구역 셰이프)

NAS `sources/antarctic_papers/` 에 두고 부른다. Pillow 로 읽어 numpy 없이 컨테이너에서도 돈다:

    manage.py build_gernon_paleotopo /nfs/temp-share/GSM/sources/antarctic_papers/gernon2026_zenodo_19205651_GIS_files.zip

34 연대(`gernontopo.AGES`, 100–34 Ma, 2 Myr)를 다 굽는다(wetherilli 439). 결과는 `<GSM_GERNON_PALEOTOPO_DIR>/<연대>/` — 운영은
`/srv/GSM/db/gernon_paleotopo/`. 같은 zip 에서 **등고선**(`contours.json`, 2.8 MB 남짓 — 저장소에 두기엔 커서 여기로 옮겼다)도 함께 굽는다.
`--contours-only` 면 등고선만 (몇십 초).
"""
import time
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import antpapers, gernontopo, polargrid


class Command(BaseCommand):
    help = "동남극 고지형(Gernon 외 2026, FastScape 모형)을 연대마다 칠해 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="Zenodo 19205651 의 GIS_files zip")
        parser.add_argument("--out", default=None, help="기본: GSM_GERNON_PALEOTOPO_DIR (연대마다 하위 폴더)")
        parser.add_argument("--contours-only", action="store_true", help="래스터는 두고 등고선(contours.json)만 다시 굽는다")

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
            started = time.monotonic()
            out = Path(o["out"]) / "contours.json" if o["out"] else None
            try:
                counts = antpapers.build_contours(lambda age: z.read(found[age]), sorted(found, reverse=True), out)
            except (OSError, ValueError, antpapers.AntPapersError) as exc:
                raise CommandError(f"등고선: {exc}") from exc
            out = out or antpapers.contours_path()
            self.stdout.write(self.style.SUCCESS(
                f"등고선 {len(counts)} 연대, 선 {sum(counts.values()):,} — {out} {out.stat().st_size // 1024} KB "
                f"({time.monotonic() - started:.0f} 초)"))
            if o["contours_only"]:
                return
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
