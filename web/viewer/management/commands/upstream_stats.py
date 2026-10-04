"""상류에 하루 몇 번 물었는지 본다.

    manage.py upstream_stats            지난 14 일
    manage.py upstream_stats --days 60

**한계를 재지 않고 지켜보는 자리다** (devlog 010). 차단 조짐(403·429·방화벽의
`Request Blocked`)이 한 번이라도 있었으면 맨 끝에 적는다 — 그때는 미리
데우기를 멈추고 까닭을 본다.
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from viewer import usage
from viewer.models import UpstreamDay


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
        self.stdout.write(f"{'날짜':<12}{'상류':<12}{'성공':>8}{'실패':>6}{'차단':>6}")
        blocked_days = []
        for r in rows:
            self.stdout.write(f"{r.day!s:<12}{r.upstream:<12}{r.ok:>8}{r.fail:>6}{r.blocked:>6}")
            if r.blocked:
                blocked_days.append(f"{r.day} {r.upstream}")
        left = usage.paused()
        if left:
            self.stdout.write(self.style.WARNING(f"\n지금 쉬는 중이다 — {int(left)}초 남았다 (이 프로세스 기준)"))
        if blocked_days:
            self.stdout.write(self.style.ERROR(
                "\n차단 조짐이 있던 날: " + ", ".join(blocked_days)
                + "\n미리 데우기를 멈추고 로그의 '차단하는 얼굴' 을 본다."))
        else:
            self.stdout.write(self.style.SUCCESS("\n차단 조짐 없음."))
