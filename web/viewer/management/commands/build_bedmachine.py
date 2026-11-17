"""그린란드 BedMachine v7 을 칠해 3413 타일로 잘라 둔다 (wetherilli 459).

원본은 NSIDC `IDBMG4` v7 의 `BedMachineGreenland-v7.nc`(NetCDF-4, 2.8 GB) — **NASA Earthdata 로그인 뒤**라 사람이 받아 온 토큰으로
한 번 받아 NAS `sources/greenland/bedmachine/` 에 둔다:

    https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/ICEBRIDGE/IDBMG4/7/1988/01/01/BedMachineGreenland-v7.nc

**호스트에서** 부른다 — h5py·numpy 가 있어야 한다(제품 이미지에는 없다):

    /srv/GSM/scripts/run.sh build_bedmachine /nfs/temp-share/GSM/sources/greenland/bedmachine/

같은 폴더에 바닥 열 상태 GBaTS v2(`RDBTS4_…_basal_thermal_state.nc`, 17 MB, NSIDC RDBTS4 v2)가 있으면 그것도 굽는다(wetherilli 461).

결과는 `<GSM_BEDMACHINE_DIR>/<판>/` 의 `tiles/{z}/{x}/{y}.webp`·`values.i16`·`meta.json` — 운영은 `/srv/GSM/db/bedmachine/`.
"""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import bedmachine, polargrid


class Command(BaseCommand):
    help = "그린란드 BedMachine v7(NetCDF-4)의 바닥·얼음 두께·윗면을 칠해 3413 타일로 잘라 둔다 — 호스트에서만 (h5py·numpy)"

    def add_arguments(self, parser):
        parser.add_argument("source", help=f"{bedmachine.FILE} 가 든 폴더 또는 그 파일")
        parser.add_argument("--kind", action="append", choices=sorted([*bedmachine.KINDS, "thermal"]),
                            help="기본: 있는 것 다 (바닥·두께·윗면, 바닥 열 상태)")
        parser.add_argument("--stride", type=int, default=bedmachine.STRIDE, help="원판 몇 칸에 하나를 고를지 (기본 2 — 300 m)")
        parser.add_argument("--out", default=None, help="기본: GSM_BEDMACHINE_DIR (판마다 하위 폴더)")

    def handle(self, *args, **o):
        try:
            import h5py  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            raise CommandError("h5py·numpy 가 없다 — 호스트의 /srv/GSM/scripts/run.sh build_bedmachine <폴더> 로 부른다")
        folder = Path(o["source"])
        path = folder / bedmachine.FILE if folder.is_dir() else folder
        thermal = (folder if folder.is_dir() else folder.parent) / bedmachine.THERMAL_FILE
        kinds = o["kind"] or [*bedmachine.KINDS, *(["thermal"] if thermal.is_file() else [])]
        if "thermal" in kinds:
            kinds.remove("thermal")
            self._thermal(thermal, o["out"])
        if kinds and not path.is_file():
            raise CommandError(f"원본이 없다 — {path}")
        for kind in kinds:
            started = time.monotonic()
            spec = bedmachine.SETS[bedmachine.name(kind)]
            out = Path(o["out"]) / kind if o["out"] else None
            try:
                grid = bedmachine.read_nc(path, kind, o["stride"])
                stats = polargrid.bake(spec, grid, f"{path.name} (1/{o['stride']})", out, log=self.stdout.write)
            except (OSError, polargrid.PolarGridError) as exc:
                raise CommandError(f"{path.name} {kind}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{spec.name}: 타일 {stats['tiles']} 장, {stats['mb']} MB — {out or spec.root()} ({time.monotonic() - started:.0f} 초)"))

    def _thermal(self, path, out):
        if not path.is_file():
            raise CommandError(f"원본이 없다 — {path}")
        spec = bedmachine.SETS[bedmachine.THERMAL]
        out = Path(out) / "thermal" if out else None
        try:
            stats = polargrid.bake(spec, bedmachine.read_thermal(path), path.name, out, log=self.stdout.write)
        except (OSError, polargrid.PolarGridError) as exc:
            raise CommandError(f"{path.name}: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"{spec.name}: 타일 {stats['tiles']} 장, {stats['mb']} MB — {out or spec.root()}"))
