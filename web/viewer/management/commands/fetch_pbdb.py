"""PBDB 의 화석 산지를 모두 받아 `<EARTH_DIR>/pbdb.sqlite` 로 굽는다 (wetherilli 098).

문(`pbdb.py`)으로 `colls/list.csv?all_records` 를 한 번 받는다(110–160 MB, 몇 분). 받은 CSV 는 `<EARTH_DIR>/pbdb_collections.csv`
에 남기고, `--csv` 로 받아 둔 것을 다시 구울 수 있다. 살아 있는 DB 라 새 산지가 늘 는다 — 가끔 다시 부른다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog, fossils, pbdb


class Command(BaseCommand):
    help = "PBDB 화석 산지 → <EARTH_DIR>/pbdb.sqlite (wetherilli 098)"

    def add_arguments(self, parser):
        parser.add_argument("--csv", help="받아 둔 CSV 로 굽기만 한다 (상류를 부르지 않는다)")

    def handle(self, *args, **opts):
        out = fossils.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        src = Path(opts["csv"]) if opts["csv"] else out.parent / "pbdb_collections.csv"
        if not opts["csv"]:
            self.stdout.write("PBDB 에서 받는다 …")
            try:
                size = pbdb.download(src)
            except pbdb.PbdbError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"  {size / 1e6:.0f} MB")
        got = fossils.build(src, out, log=self.stdout.write)
        # 기록 표에 — 원본 CSV 의 자리와 구운 곳의 수 (jikhanjung P02). sha 는 원본을 날짜 폴더에 두는 4 단계에서 —
        # 여기서 세면 150 MB 를 한 번 더 읽는다(#369 검토)
        fetchlog.note(rows=got["rows"], raw_path=_rel(src))
        self.stdout.write(f"{got['rows']:,} 곳 (판을 찾은 것 {got['plated']:,}, 좌표 없는 것 {got['skipped']:,}) · "
                          f"{got['seconds']} 초 → {out}")


def _rel(path) -> str:
    """기록 표에는 `<DB 옆>` 아래 이름만 — 절대 경로를 남기지 않는다"""
    from django.conf import settings
    try:
        # `<DB 옆>` 기준 — 장부 자리(GSM_STORE_PATH)를 옮겨도 이름이 같다(#369 검토)
        return str(Path(path).resolve().relative_to(Path(settings.DATABASES["default"]["NAME"]).resolve().parent))
    except ValueError:
        return Path(path).name
