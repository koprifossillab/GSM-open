"""상류에 하루 몇 번 물었는지 본다.

    manage.py upstream_stats            지난 14 일
    manage.py upstream_stats --days 60

**한계를 재지 않고 지켜보는 자리다** (devlog 010). 걸린 시간(wetherilli 290)도 — 날마다 평균과 p95(칸에서 어림한 위 끝),
맨 끝에 기간을 합친 상류별 평균이 느린 차례로 선다. 느린 상류를 메타타일(wetherilli 287)로 돌릴 때 본다. 차단 조짐(403·429·방화벽의
`Request Blocked`)이 한 번이라도 있었으면 맨 끝에 적는다 — 그때는 미리
데우기를 멈추고 까닭을 본다.
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from viewer import usage
from viewer.models import UpstreamDay

BUCKET_FIELDS = usage.BUCKET_FIELDS
p95 = usage.p95
mean = usage.mean


class Command(BaseCommand):
    help = "상류에 하루 몇 번 물었는지 본다"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)

    def handle(self, *args, **options):
        since = timezone.localdate() - datetime.timedelta(days=options["days"] - 1)
        rows = UpstreamDay.objects.filter(day__gte=since).order_by("day", "upstream")
        if not rows:
            self.stdout.write("센 것이 없다.")
            return
        self.stdout.write(f"{'날짜':<12}{'상류':<12}{'성공':>8}{'실패':>6}{'차단':>6}{'평균초':>8}{'p95초':>8}")
        blocked_days = []
        totals = {}
        for r in rows:
            counts = [getattr(r, f) for f in BUCKET_FIELDS]
            self.stdout.write(f"{r.day!s:<12}{r.upstream:<12}{r.ok:>8}{r.fail:>6}{r.blocked:>6}"
                              f"{mean(r.seconds, r.timed):>8}{p95(counts):>8}")
            if r.blocked:
                blocked_days.append(f"{r.day} {r.upstream}")
            if r.timed:
                t = totals.setdefault(r.upstream, [0, 0.0, [0] * len(BUCKET_FIELDS)])
                t[0] += r.timed
                t[1] += r.seconds
                t[2] = [a + b for a, b in zip(t[2], counts)]
        if totals:
            self.stdout.write(f"\n상류별 걸린 시간 — 지난 {options['days']} 일, 느린 차례")
            self.stdout.write(f"{'상류':<12}{'잰 건수':>10}{'평균초':>8}{'p95초':>8}")
            for name, (timed, seconds, counts) in sorted(totals.items(), key=lambda kv: -kv[1][1] / kv[1][0]):
                self.stdout.write(f"{name:<12}{timed:>10}{mean(seconds, timed):>8}{p95(counts):>8}")
        left = usage.paused()
        if left:
            self.stdout.write(self.style.WARNING(f"\n지금 쉬는 중이다 — {int(left)}초 남았다 (이 프로세스 기준)"))
        if blocked_days:
            self.stdout.write(self.style.ERROR(
                "\n차단 조짐이 있던 날: " + ", ".join(blocked_days)
                + "\n미리 데우기를 멈추고 로그의 '차단하는 얼굴' 을 본다."))
        else:
            self.stdout.write(self.style.SUCCESS("\n차단 조짐 없음."))
