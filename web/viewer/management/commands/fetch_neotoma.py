"""Neotoma 의 자료를 모두 받아 `<EARTH_DIR>/neotoma.sqlite` 로 굽는다 (wetherilli 139).

문(`neotoma.py`)으로 자료 번호를 500 개씩 묶어 1 초 간격으로 묻는다(140 번 남짓, 한 시간쯤). 받은 것은
`<EARTH_DIR>/neotoma_datasets.jsonl` 에 남기고, `--jsonl` 로 받아 둔 것을 다시 구울 수 있다. 새 자료가 쌓이니 가끔 다시 부른다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog, neotoma, paleoeco, rawstore


class Command(BaseCommand):
    help = "Neotoma 고생태 산지 → <EARTH_DIR>/neotoma.sqlite (wetherilli 139)"

    def add_arguments(self, parser):
        parser.add_argument("--jsonl", help="받아 둔 JSON Lines 로 굽기만 한다 (상류를 부르지 않는다)")

    def handle(self, *args, **opts):
        out = paleoeco.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        src = Path(opts["jsonl"]) if opts["jsonl"] else out.parent / "neotoma_datasets.jsonl"
        if not opts["jsonl"]:
            self.stdout.write("Neotoma 에서 받는다 — 한 시간쯤 걸린다 …")
            try:
                n = neotoma.download(src, log_line=self.stdout.write)
            except neotoma.NeotomaError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"  자료 {n:,} 건")
        got = paleoeco.build(src, out, log=self.stdout.write)
        # 기록 표에 — 원본의 자리·판과 구운 수 (jikhanjung P02 4 단계). 몇십 MB 라 다 읽어 셈한다
        fetchlog.note(raw_path=rawstore.label(src), raw_sha256=rawstore.file_sha256(src),
                      rows=got["datasets"])
        self.stdout.write(f"산지 {got['sites']:,} 곳 · 자료 {got['datasets']:,} 건 · {got['seconds']} 초 → {out}")
