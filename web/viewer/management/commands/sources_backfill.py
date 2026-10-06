"""기록 표가 비어 있을 때 한 번 — 데이터소스마다 지난 한 줄을 파일로 어림해 넣는다 (jikhanjung P02 2 단계).

    manage.py sources_backfill

`datastatus` 가 지금 하는 어림(산출물 파일의 고친 날)으로 `estimated=1` 한 줄을 넣는다. 이미 줄이 있는 데이터소스는 건너뛴다.
저장소에 굽는 것(`data/…`·`static/…`)은 이미지가 지어진 날이 고친 날이라 어림하지 않는다.
"""
import sqlite3

from django.core.management.base import BaseCommand

from viewer import datastatus, fetchlog, sources


class Command(BaseCommand):
    help = "기록 표가 빈 데이터소스에 파일로 어림한 한 줄을 넣는다"

    def handle(self, *args, **opts):
        if fetchlog.on_host():
            self.stderr.write("호스트에서는 장부에 쓰지 않는다 — 컨테이너 안에서 부른다")
            return
        spec = sources.load()
        fetchlog.sync(spec.rows)
        have = fetchlog.latest()
        files = {r["key"]: r for r in datastatus.rows()}
        rows = []
        for row in spec.rows:
            if row["id"] in have:
                continue
            found = [files[o] for o in row.get("outputs", []) if o in files and files[o]["exists"] and files[o]["modified"]]
            if not found:
                continue
            newest = max(f["modified"] for f in found)
            rows.append({"source": row["id"], "command": (row.get("commands") or [""])[0],
                         "started_at": newest.astimezone().isoformat(timespec="seconds"), "result": "ok",
                         "note": "산출물 파일의 고친 날로 어림했다", "estimated": 1, "origin": "backfill",
                         "built_at": newest.astimezone().isoformat(timespec="seconds")})
        try:
            added = fetchlog.write_many(rows) if rows else 0
        except (sqlite3.Error, OSError) as exc:
            self.stderr.write(f"장부에 적지 못했다: {exc}")
            return
        self.stdout.write(self.style.SUCCESS(f"어림한 줄 {added} 곳"))
