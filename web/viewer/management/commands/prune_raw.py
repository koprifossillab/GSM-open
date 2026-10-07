"""받아 둔 원본의 옛 날짜 폴더를 지우고 최근 몇 벌만 남긴다 (jikhanjung P02 4 단계).

**사람이 부른다** — 지우는 일이라 cron 에 두지 않는다. `--dry-run` 으로 무엇을 지울지 먼저 본다. 명세(`sources.json`)의 `raw` 가
날짜 폴더(`<자리>/<YYYYMMDD>/`)인 데이터소스만 본다 — 날짜 없이 덮어쓰는 원본(PBDB·지진 CSV 따위)은 지울 것이 없다.
가장 새 폴더는 언제나 남는다(`kigam50k.latest` 따위가 읽는 것이다).

    manage.py prune_raw --dry-run
    manage.py prune_raw                 # 데이터소스마다 최근 3 벌
    manage.py prune_raw --keep 5 --source kigam50k
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog, rawstore, sources


class Command(BaseCommand):
    help = "받아 둔 원본의 옛 날짜 폴더를 지우고 최근 몇 벌만 남긴다 (jikhanjung P02 4 단계). 사람이 부른다"

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=rawstore.KEEP, help=f"남길 벌 수 (기본 {rawstore.KEEP}, 1 보다 작으면 1)")
        parser.add_argument("--source", help="이 데이터소스만 (명세의 id)")
        parser.add_argument("--dry-run", action="store_true", help="지우지 않고 무엇을 지울지만 보인다")

    def handle(self, *args, **opts):
        fetchlog.refuse_on_host("prune_raw")
        rows = [r for r in sources.load().rows if r.get("raw")]
        if opts["source"]:
            rows = [r for r in rows if r["id"] == opts["source"]]
            if not rows:
                raise CommandError(f"{opts['source']}: 명세에 없거나 raw 가 비었다")
        verb = "지울 것" if opts["dry_run"] else "지웠다"
        total = 0
        for row in rows:
            folder = rawstore.resolve(row["raw"])
            found = rawstore.versions(folder)
            if not found:
                continue                            # 날짜 폴더가 아니다 — 지울 것이 없다
            gone = rawstore.prune(folder, keep=opts["keep"], dry_run=opts["dry_run"])
            total += len(gone)
            kept = [p.name for p in found if p not in gone]
            line = f"{row['id']}: {len(found)} 벌 — 남김 {', '.join(kept)}"
            if gone:
                line += f" · {verb} {', '.join(p.name for p in gone)}"
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS(f"{verb} {total} 벌" + (" — --dry-run 이라 아무것도 지우지 않았다" if opts["dry_run"] else "")))
