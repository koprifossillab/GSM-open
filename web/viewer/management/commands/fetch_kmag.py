"""다누리 자기장 측정기(KMAG) 궤적을 KPDS 에서 모은다 (wetherilli 377).

Calibrated 하루치(zip 0.8 MB)를 `kpds.PAUSE` 초 간격으로 받아 32 초마다 한 점만 `<KPDS_DIR>/kmag.sqlite` 에 더한다.
처음에는 940 일 남짓이라 30 분쯤, 다음부터는 새로 올라온 날만이다(KPDS 는 석 달마다 더한다).

    manage.py fetch_kmag            # 새 날만
    manage.py fetch_kmag --limit 3  # 시험 삼아 사흘
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import kmag, kpds


class Command(BaseCommand):
    help = "다누리 KMAG Calibrated 하루치들을 KPDS 에서 받아 궤적 sqlite 로 (wetherilli 377)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="이만큼의 날만 받는다")

    def handle(self, *args, **opts):
        try:
            s = kpds.session()
            total, rows = kpds.search(s, "kmag", "Calibrated", 0, 200)
            while len(rows) < total:
                time.sleep(kpds.PAUSE)
                _, more = kpds.search(s, "kmag", "Calibrated", len(rows), 200)
                if not more:
                    break
                rows += more
        except kpds.KpdsError as exc:
            raise CommandError(str(exc)) from exc
        rows = sorted({r["meta"]: r for r in rows if r["meta"]}.values(), key=lambda r: r["meta"])
        conn = kmag.connect(write=True)
        todo = [r for r in rows if not kmag.has_day(conn, r["meta"])]
        if opts["limit"]:
            todo = todo[:opts["limit"]]
        self.stdout.write(f"KPDS 의 KMAG Calibrated {len(rows)} 날, 새로 받을 것 {len(todo)}")
        added = failed = 0
        for k, row in enumerate(todo):
            if k:
                time.sleep(kpds.PAUSE)
            try:
                files = kpds.download(s, row["meta"])
            except kpds.KpdsError as exc:
                failed += 1
                self.stderr.write(f"  {row['meta']}: {exc}")
                if failed >= 5 and not added:
                    raise CommandError("다섯 번 내리 받지 못했다 — 멈춘다")
                continue
            text = next((v for n, v in files.items() if n.lower().endswith(".csv")), None)
            if text is None:
                self.stderr.write(f"  {row['meta']}: CSV 가 없다")
                continue
            n = kmag.add_day(conn, row["meta"], kmag.parse(text.decode("utf-8", "replace")))
            added += 1
            if added % 25 == 0 or k == len(todo) - 1:
                self.stdout.write(f"  {added}/{len(todo)} {row['meta']} {n} 점")
        conn.close()
        self.stdout.write(self.style.SUCCESS(f"{added} 날을 더했다 (못 받은 것 {failed}) — {kmag.summary()}"))
