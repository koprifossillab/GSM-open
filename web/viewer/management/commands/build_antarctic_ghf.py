"""남극 지열류 모형 셋을 칠해 3031 타일로 잘라 둔다 (wetherilli 432).

원본은 PANGAEA 의 낱 파일 — 받기는 계정 없이 된다:

    https://download.pangaea.de/dataset/924857/files/aq1_01_20.csv                  Stål 2021 Aq1, CC BY 4.0
    https://download.pangaea.de/dataset/930237/files/HF_Min_Max_MaxAbs-1.csv        Lösing & Ebbing 2021, CC BY 4.0
    https://store.pangaea.de/Publications/Martos-etal_2017/Antarctic_GHF.xyz        Martos 2017, CC BY 3.0

NAS `sources/antarctic_ghf/` 에 두고 부른다. 글 파일이라 numpy 없이 컨테이너에서도 돈다:

    manage.py build_antarctic_ghf /nfs/temp-share/GSM/sources/antarctic_ghf/

폴더나 파일 여럿을 받고, 있는 판만 굽는다. 결과는 `<GSM_ANTARCTIC_GHF_DIR>/<판>/` — 운영은 `/srv/GSM/db/antarctic_ghf/`.
"""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import ghfgrid, polargrid


class Command(BaseCommand):
    help = "남극 지열류 모형(Stål·Lösing·Martos)을 칠해 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("sources", nargs="+", help="원본이 든 폴더 또는 파일")
        parser.add_argument("--out", default=None, help="기본: GSM_ANTARCTIC_GHF_DIR (판마다 하위 폴더)")

    def handle(self, *args, **o):
        files = {}
        for src in map(Path, o["sources"]):
            for path in (sorted(src.iterdir()) if src.is_dir() else [src]):
                files[path.name] = path
        found = [(kind, files[spec[0]]) for kind, spec in ghfgrid.KINDS.items() if spec[0] in files]
        if not found:
            raise CommandError("원본이 없다 — " + ", ".join(spec[0] for spec in ghfgrid.KINDS.values()))
        for kind, path in found:
            started = time.monotonic()
            spec = ghfgrid.SETS[f"{ghfgrid.UPSTREAM}:{kind}"]
            out = Path(o["out"]) / kind if o["out"] else None
            try:
                grid = ghfgrid.read(kind, path.read_text(encoding="utf-8", errors="replace"))
                stats = polargrid.bake(spec, grid, path.name, out, log=self.stdout.write)
            except (OSError, ValueError, polargrid.PolarGridError) as exc:
                raise CommandError(f"{path.name}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{spec.name}: 타일 {stats['tiles']} 장, {stats['mb']} MB — {out or spec.root()} ({time.monotonic() - started:.0f} 초)"))
