"""남극 중력 AntGG2021 을 칠해 3031 타일로 잘라 둔다 (wetherilli 431).

원본은 PANGAEA 971238 의 낱 파일(각 27 MB, CC BY 4.0) — 받기는 계정 없이 된다:

    https://download.pangaea.de/dataset/971238/files/AntGG2021_Gravity-anomaly.nc
    https://download.pangaea.de/dataset/971238/files/AntGG2021_Bouguer-anomaly.nc

NAS `sources/antgg2021/` 에 두고 **호스트에서** 부른다 — NetCDF-4(HDF5)라 h5py 가 있어야 한다(제품 이미지에는 없다):

    /srv/GSM/scripts/run.sh build_antgg /nfs/temp-share/GSM/sources/antgg2021/

폴더나 파일 여럿을 받는다. 결과는 `<GSM_ANTGG_DIR>/<판>/` 의 `tiles/{z}/{x}/{y}.webp`·`values.i16`·`meta.json` — 운영은
`/srv/GSM/db/antgg/`. 판 하나에 몇 초다.
"""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import antgg, polargrid


class Command(BaseCommand):
    help = "남극 중력 AntGG2021(NetCDF-4)을 칠해 3031 타일로 잘라 둔다 — 호스트에서만 (h5py)"

    def add_arguments(self, parser):
        parser.add_argument("sources", nargs="+", help="원본 .nc 가 든 폴더 또는 .nc 파일")
        parser.add_argument("--out", default=None, help="기본: GSM_ANTGG_DIR (판마다 하위 폴더)")

    def handle(self, *args, **o):
        try:
            import h5py  # noqa: F401
        except ImportError:
            raise CommandError("h5py 가 없다 — 호스트의 /srv/GSM/scripts/run.sh build_antgg <폴더> 로 부른다")
        files = {}
        for src in map(Path, o["sources"]):
            for path in (sorted(src.glob("*.nc")) if src.is_dir() else [src]):
                files[path.name] = path
        found = [(kind, files[spec[0]]) for kind, spec in antgg.KINDS.items() if spec[0] in files]
        if not found:
            raise CommandError("원본이 없다 — " + ", ".join(spec[0] for spec in antgg.KINDS.values()))
        for kind, path in found:
            started = time.monotonic()
            spec = antgg.SETS[f"{antgg.UPSTREAM}:{kind}"]
            out = Path(o["out"]) / kind if o["out"] else None
            try:
                grid = antgg.read_nc(path, antgg.KINDS[kind][1])
                stats = polargrid.bake(spec, grid, path.name, out, log=self.stdout.write)
            except (OSError, polargrid.PolarGridError) as exc:
                raise CommandError(f"{path.name}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{spec.name}: 타일 {stats['tiles']} 장, {stats['mb']} MB — {out or spec.root()} ({time.monotonic() - started:.0f} 초)"))
