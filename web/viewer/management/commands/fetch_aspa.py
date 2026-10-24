"""남극 특별보호구역 ASPA 2024(AADC, CC BY 4.0)를 받아 `<AADC_DIR>/aspa_2024.json` 에 굽는다 (wetherilli 423).

문(`aadc.py`)으로 셰이프 파일 열둘(면·점 각 다섯, 조건·설명)을 1 초 간격으로 받는다. 원본은 `<AADC_DIR>/aspa_raw/<날짜>/` 에 —
바뀐 판만 새 폴더가 생긴다(`rawstore`). ASPA 는 남극조약 협의당사국회의(ATCM)가 해마다 지정·해제하고 AADC 가 몇 해마다 판을
올리니 사람이 가끔 부른다 — cron 에 두지 않는다. `--from <폴더>` 는 받아 둔 파일(그 폴더에 이름 그대로)로 굽기만 한다.
"""
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import aadc, fetchlog, rawstore


class Command(BaseCommand):
    help = "남극 특별보호구역 ASPA 2024 → <AADC_DIR>/aspa_2024.json (wetherilli 423)"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="source", help="받아 둔 셰이프 파일이 든 폴더 — 상류를 부르지 않는다")

    def handle(self, *args, **opts):
        if opts["source"]:
            folder = Path(opts["source"])
            if not folder.is_dir():
                raise CommandError(f"폴더가 없다: {folder}")
            files = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        else:
            self.stdout.write("AADC 에서 ASPA 2024 를 받는다 …")
            try:
                files = aadc.download()
            except aadc.AadcError as exc:
                raise CommandError(str(exc)) from exc
            entries = {name: {"file": name, "body": body} for name, body in files.items()}
            dest, fresh = rawstore.save(aadc.raw_dir(), entries, {"source": aadc.SOURCE_URL, "dataset": aadc.ASPA_ID},
                                        datetime.now(timezone.utc))
            self.stdout.write(f"원본 → {dest}" + ("" if fresh else " (앞 판과 같다)"))
        try:
            baked = aadc.convert(files)
        except (KeyError, aadc.AadcError) as exc:
            raise CommandError(f"ASPA 파일을 읽지 못했다: {exc}") from exc
        out = aadc.write(baked)
        fetchlog.note(rows=len(baked["polygons"]))
        self.stdout.write(f"면 {len(baked['polygons'])} · 점 {len(baked['points'])} → {out}")
