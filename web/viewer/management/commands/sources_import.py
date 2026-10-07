"""파일 시절의 데이터소스 명세와 기록을 DB 로 옮긴다 (jikhanjung P03 1 단계).

    manage.py sources_import             명세는 한 번(표지가 없을 때), 기록은 늘 — 같은 줄은 하나로
    manage.py sources_import --dry-run   옮기지 않고 무엇이 있는지만

컨테이너가 뜰 때 `entrypoint-web.sh` 가 `migrate` 뒤, `sources_seed` 앞에 부른다 — 사람이 서버에서 고친 운영 명세를 씨앗보다 먼저
들이려고. 파일은 지우지 않는다(한 판 동안 견주고, 판을 되돌려도 읽히게 — P03 §6). 실패해도 0 으로 끝난다 — 화면은 떠야 한다.

**"표가 비었나" 로 정하지 않는다**(#381 검토 1) — 옮기다 한 번 깨지고 그 사이 기록 한 줄·씨앗이 들어가면 다시 기회가 없었다.
- 명세는 표지(`sources.IMPORTED`)로 한 번. 씨앗이 먼저 들어가 있으면 파일 쪽으로 덮는다(`sources.import_file`)
- 기록은 **부를 때마다 다 옮긴다** — 같은 (데이터소스·시작한 때·어디서)는 표의 제약이 하나로 거른다. 판을 되돌린 동안 옛 코드가
  store.sqlite 에 적은 줄도 다시 올리면 들어온다. 95 줄 남짓이라 매번 읽어도 싸다

기록의 `started_at` 은 파일에 시간대를 단 ISO 글로 적혀 있었다 — DB 에서는 UTC 로 맞춰 적힌다. 시간대가 달라 글자는 달랐지만 같은
때인 줄은 하나가 된다(`fetch_run_once`). 명세가 바뀐 것을 적던 `_spec` 줄은 옮기지 않는다 — 그 몫은 이제 `DataSourceChange` 다.
"""
import sqlite3

from django.core.management.base import BaseCommand
from django.db import DatabaseError

from viewer import fetchlog, sources


class Command(BaseCommand):
    help = "파일 시절의 데이터소스 명세(sources.json)와 기록(store.sqlite 의 fetch_log)을 DB 로 한 번 옮긴다"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="옮기지 않고 무엇이 있는지만")

    def handle(self, *args, **opts):
        fetchlog.refuse_on_host("sources_import")
        from viewer.models import FetchRunMark

        say = self.stdout.write
        dry = opts["dry_run"]
        try:
            imported = FetchRunMark.objects.filter(key=sources.IMPORTED).exists()
        except DatabaseError as exc:
            self.stderr.write(f"표를 열지 못했다 — migrate 가 먼저다: {exc}")
            return

        # 명세 — 한 번
        if imported:
            say("명세 — 이미 옮겼다")
        else:
            spec = sources.read_file()
            if dry:
                say(f"명세 — {len(spec.rows)} 곳을 옮길 것 ({spec.origin}), 건너뛸 줄 {len(spec.problems)}" if spec.origin != "none"
                    else f"명세 — {sources.path()} 가 없다, 씨앗이 들어간다(sources_seed)")
            else:
                try:
                    done = sources.import_file()
                except DatabaseError as exc:
                    self.stderr.write(f"명세를 옮기지 못했다 — 다음에 뜰 때 다시 한다: {exc}")
                else:
                    if done["origin"] == "none":
                        say(f"명세 — {sources.path()} 가 없다, 씨앗이 들어간다(sources_seed)")
                    else:
                        say(self.style.SUCCESS(f"명세 — {len(done['added'])} 곳을 옮겼다, 씨앗 줄을 파일 쪽으로 덮은 것 "
                                               f"{len(done['replaced'])} ({done['origin']})"))
                    if done["kept"]:
                        self.stderr.write(f"  admin 에서 고친 줄이라 덮지 않았다: {' '.join(done['kept'])}")
                    for where, found in done["problems"]:
                        self.stderr.write(f"  건너뜀 {where or '(파일)'}: " + "; ".join(str(m) for m in found))

        # 기록 — 늘, 같은 줄은 하나로
        store = fetchlog.store_path()
        if not store.exists():
            say("기록 — store.sqlite 가 없다")
            return
        try:
            db = sqlite3.connect(f"file:{store}?mode=ro", uri=True, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                rows = [dict(r) for r in db.execute("SELECT * FROM fetch_log WHERE source != '_spec' ORDER BY id")]
                mark = db.execute("SELECT v FROM fetch_log_meta WHERE k = 'host_offset'").fetchone()
            finally:
                db.close()
        except sqlite3.Error as exc:
            say(f"기록 — store.sqlite 의 fetch_log 를 읽지 못했다: {exc}")
            return
        if dry:
            say(f"기록 — {len(rows)} 줄을 옮길 것 (이미 있는 줄은 하나로)")
            return
        try:
            added = fetchlog.write_many(rows)
            # 호스트 기록을 읽은 자리 — 표에 아직 없을 때만(새 코드가 더 읽었으면 그것이 맞다)
            if mark and str(mark[0]).isdigit():
                FetchRunMark.objects.get_or_create(key="host_offset", defaults={"value": str(mark[0])})
        except DatabaseError as exc:
            self.stderr.write(f"기록을 옮기지 못했다 — 다음에 뜰 때 다시 한다: {exc}")
            return
        say(self.style.SUCCESS(f"기록 — {len(rows)} 줄 가운데 새로 {added} 줄"))
