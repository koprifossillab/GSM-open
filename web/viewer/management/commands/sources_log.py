"""받은 차례의 기록을 본다 (jikhanjung P02 2 단계). 관리 화면의 "데이터소스" 탭(3 단계)이 서기 전까지 사람이 보는 길.

    manage.py sources_log                 데이터소스마다 마지막 줄과 마지막으로 된 때 — 호스트가 남긴 것을 먼저 옮겨 적는다
    manage.py sources_log --source pbdb   한 데이터소스의 지난 차례들
    manage.py sources_log --no-sync       옮겨 적지 않고 보기만
"""
from django.core.management.base import BaseCommand

from viewer import fetchlog, sources


class Command(BaseCommand):
    help = "받은 차례의 기록(store.sqlite 의 fetch_log)을 본다"

    def add_arguments(self, parser):
        parser.add_argument("--source", default="", help="이 데이터소스의 지난 차례들")
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--no-sync", action="store_true", help="hourly_status.json·호스트 기록을 옮겨 적지 않는다")
        parser.add_argument("--sync-only", action="store_true",
                            help="옮겨 적기만 하고 표는 내지 않는다 — hourly.sh 가 차례 끝에 부른다 (#373 검토 2)")

    def handle(self, *args, **opts):
        say = self.stdout.write
        spec = sources.load()
        if not opts["no_sync"]:
            moved = fetchlog.sync(spec.rows)
            if moved or opts["sync_only"]:
                say(f"호스트가 남긴 {moved} 줄을 옮겨 적었다")
        if opts["sync_only"]:
            return
        if opts["source"]:
            for r in fetchlog.history(opts["source"], opts["limit"]):
                say(_line(r))
            return
        latest = fetchlog.latest()
        for row in spec.rows:
            got = latest.get(row["id"]) or {}
            last, ok = got.get("last"), got.get("last_ok")
            when = (last or {}).get("started_at", "—")[:16]
            ok_when = (ok or {}).get("started_at", "—")[:16]
            mark = "~" if last and last.get("estimated") else " "
            say(f"{row['id']:<20} {row['schedule']:<20} 마지막 {when:<16}{mark} {(last or {}).get('result', '—'):<4} "
                f"된 때 {ok_when:<16} {((last or {}).get('note') or '')[:60]}")


def _line(r):
    counts = ""
    if r.get("expected") is not None or r.get("rows") is not None:
        counts = f" 센 수 {r.get('expected')} · 받은 수 {r.get('rows')}"
    return (f"{r['started_at'][:19]} {r['origin']:<9} {r['result']:<4} {r.get('seconds') or '':>7}s"
            f"{counts} {r.get('raw_path') or ''} {(r.get('note') or '')[:80]}")
