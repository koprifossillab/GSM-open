"""PBDB 의 화석 산지를 받아 `<EARTH_DIR>/pbdb.sqlite` 로 굽는다 (wetherilli 098, jikhanjung 026).

문(`pbdb.py`)으로 `colls/list.csv` 를 받는다. 받은 CSV 는 `<EARTH_DIR>/pbdb_collections.csv` 에 남기고, `--csv` 로 받아 둔 것을
다시 구울 수 있다. 살아 있는 DB 라 새 산지가 늘 는다.

    manage.py fetch_pbdb             통째로(`all_records`, 110–160 MB, 몇 분) — 주간 백업이 그달의 첫 월요일에
    manage.py fetch_pbdb --changed   바뀐 것만(한 주에 수십 줄·수십 KB) — 주간 백업이 그 밖의 월요일에 (사람, 2026-10-07)
    manage.py fetch_pbdb --csv <파일> 받지 않고 굽기만

`--changed` 는 마지막으로 된 차례(기록 표)의 시작한 날에서 **하루 앞**부터 바뀐 산지를 받아(겹쳐야 놓치지 않는다) 받아 둔 CSV 에
`collection_no` 로 덮고(지운 표시면 뺀다) **sqlite 는 통째로 다시 굽는다**(`fossils.build`, 2 분 남짓) — upsert 길을 따로 짓지 않는다.
받은 바뀐 것은 `rawstore` 날짜 폴더(`earth/pbdb_changes/`)에 바뀐 판만. 받아 둔 CSV 가 없거나 열이 다르면 통째로 받는다.
지운 산지는 바뀐 것에 안 돌아올 수 있다 — 매달의 통째 받기가 맞춘다.
"""
import hashlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import fetchlog, fossils, pbdb, rawstore

#: 바뀐 것을 받을 때 앞으로 겹치는 날 — 지난 차례가 받은 날의 끝자락을 놓치지 않게
OVERLAP_DAYS = 1


def since_last(src: Path):
    """바뀐 것을 어디서부터 받나 — 마지막으로 된 차례(데이터소스 `pbdb`)의 시작한 날, 없으면 받아 둔 CSV 의 고친 날. 거기서 하루 앞"""
    got = (fetchlog.latest().get("pbdb") or {}).get("last_ok")
    when = None
    if got and not got.get("estimated"):
        try:
            when = datetime.fromisoformat(got["started_at"]).date()
        except (KeyError, ValueError):
            when = None
    if when is None:
        when = datetime.fromtimestamp(src.stat().st_mtime, tz=timezone.get_current_timezone()).date()
    return when - timedelta(days=OVERLAP_DAYS)


class Command(BaseCommand):
    help = "PBDB 화석 산지 → <EARTH_DIR>/pbdb.sqlite (wetherilli 098). --changed 면 바뀐 것만 받아 덮는다 (jikhanjung 026)"

    def add_arguments(self, parser):
        parser.add_argument("--csv", help="받아 둔 CSV 로 굽기만 한다 (상류를 부르지 않는다)")
        parser.add_argument("--changed", action="store_true", help="바뀐 것만 받아 받아 둔 CSV 에 덮고 다시 굽는다")
        parser.add_argument("--since", help="--changed 의 시작 날(YYYY-MM-DD) — 주지 않으면 마지막으로 된 차례의 하루 앞")

    def handle(self, *args, **opts):
        out = fossils.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        src = Path(opts["csv"]) if opts["csv"] else out.parent / "pbdb_collections.csv"
        if opts["changed"] and not opts["csv"]:
            if src.exists():
                if self._changed(src, opts):
                    return self._build(src, out)
                self.stdout.write("바뀐 것을 덮지 못해 통째로 받는다")
            else:
                self.stdout.write("받아 둔 CSV 가 없어 통째로 받는다")
        if not opts["csv"]:
            self.stdout.write("PBDB 에서 받는다 …")
            try:
                digest = hashlib.sha256()
                size = pbdb.download(src, digest=digest)
                fetchlog.note(raw_sha256=digest.hexdigest(), raw_path=rawstore.label(src))
            except pbdb.PbdbError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"  {size / 1e6:.0f} MB")
        self._build(src, out)

    def _changed(self, src: Path, opts) -> bool:
        """바뀐 것만 받아 덮는다. 덮었으면 True, 통째로 받아야 하면 False"""
        since = datetime.strptime(opts["since"], "%Y-%m-%d").date() if opts["since"] else since_last(src)
        self.stdout.write(f"PBDB 에서 {since:%Y-%m-%d} 뒤에 바뀐 산지를 받는다 …")
        with tempfile.TemporaryDirectory(dir=src.parent) as work:
            part = Path(work) / "changes.csv"
            try:
                pbdb.download(part, since=since, timeout=300)
            except pbdb.PbdbError as exc:
                raise CommandError(str(exc)) from exc
            body = part.read_bytes()
            try:
                got = fossils.merge_changes(src, part)
            except fossils.MergeError as exc:
                self.stdout.write(f"  {exc}")
                return False
        # 받은 바뀐 것은 날짜 폴더에 바뀐 판만(jikhanjung 015) — 기록 표의 raw_path·sha 도 거기서
        rawstore.save(Path(settings.EARTH_DIR) / "pbdb_changes", {"changes": {"file": "changes.csv.gz", "body": body}},
                      {"source": "PBDB colls/list (colls_modified_after)", "since": f"{since:%Y-%m-%d}"},
                      timezone.localtime(), key="files", where="earth/pbdb_changes")
        fetchlog.note(upstream_version=f"since {since:%Y-%m-%d}", expected=got["replaced"] + got["added"] + got["deleted"],
                      changed=got["replaced"] + got["added"] + got["deleted"])
        self.stdout.write(f"  바꾼 {got['replaced']:,} · 새로 {got['added']:,} · 뺀 {got['deleted']:,} — 모두 {got['rows']:,} 곳")
        return True

    def _build(self, src: Path, out: Path):
        got = fossils.build(src, out, log=self.stdout.write)
        # 기록 표에 — 구운 곳의 수. 원본의 자리·sha 는 받은 쪽이 적었다(통째면 CSV, 바뀐 것이면 날짜 폴더)
        fetchlog.note(rows=got["rows"])
        self.stdout.write(f"{got['rows']:,} 곳 (판을 찾은 것 {got['plated']:,}, 좌표 없는 것 {got['skipped']:,}) · "
                          f"{got['seconds']} 초 → {out}")
