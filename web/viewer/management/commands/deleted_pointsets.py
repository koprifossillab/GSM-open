"""지운 점묶음의 기록을 보고, 잘못 지운 것을 되살린다.

    manage.py deleted_pointsets                 지운 기록 (최근 30 개)
    manage.py deleted_pointsets --all
    manage.py deleted_pointsets --restore 12    12 번을 되살린다

지울 때 남긴 GeoJSON 사본으로 새 점묶음을 만든다. 이름·색·점·선·면·속성이
그대로 돌아온다. 점묶음 번호(id)는 새로 붙는다. devlog 014.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import pointsets
from viewer.models import PointSetDeletion


class Command(BaseCommand):
    help = "지운 점묶음의 기록을 보고 되살린다"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--restore", type=int, metavar="번호")

    def handle(self, *args, **o):
        if o["restore"]:
            return self._restore(o["restore"])
        rows = PointSetDeletion.objects.all()
        if not o["all"]:
            rows = rows[:30]
        if not rows:
            self.stdout.write("지운 기록이 없다.")
            return
        self.stdout.write(f"{'번호':>4}  {'지운 때':<16} {'지운 곳':<15} {'점·선·면':<10} 이름")
        for r in rows:
            mark = f"  (되살림 {timezone.localtime(r.restored_at):%m-%d %H:%M})" if r.restored_at else ""
            self.stdout.write(
                f"{r.id:>4}  {timezone.localtime(r.deleted_at):%Y-%m-%d %H:%M} {r.client:<15} "
                f"{f'{r.points}·{r.lines}·{r.polygons}':<10} {r.name}{mark}")

    def _restore(self, pk):
        try:
            gone = PointSetDeletion.objects.get(pk=pk)
        except PointSetDeletion.DoesNotExist:
            raise CommandError(f"{pk} 번 기록이 없다")
        ps, points, shapes = pointsets.restore(gone)
        self.stdout.write(self.style.SUCCESS(
            f"'{ps.name}' 을 되살렸다 — 점 {points}, 모양 {shapes}. 새 번호 {ps.id}."))
