"""점묶음의 점마다 표고를 채운다 (P03).

    manage.py fill_elevation 12              점묶음 12 의 모든 점 (다시 부르면 덮는다)
    manage.py fill_elevation 12 --missing    아직 비어 있는 점만
    manage.py fill_elevation --all --missing 모든 점묶음의 빈 점

화면의 "표고 채우기" 는 점이 2 000 개(극지는 100 개)를 넘으면 이 명령으로 넘긴다.
극지는 PGC 에 한 점에 한 번 묻고 사이를 둔다(`elevation.PGC_PAUSE`). 출처는
`elevation.py` 머리글. 달 점묶음은 LOLA(`trek.lola_values`, devlog 037)로 간다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import elevation, trek, views
from viewer.models import PointSet


class Command(BaseCommand):
    help = "점묶음의 점마다 표고 타일에서 고도를 읽어 채운다"

    def add_arguments(self, parser):
        parser.add_argument("pointset", nargs="?", type=int, help="점묶음 번호")
        parser.add_argument("--all", action="store_true", help="모든 점묶음")
        parser.add_argument("--missing", action="store_true", help="비어 있는 점만")

    def handle(self, *args, **o):
        if o["all"]:
            sets = PointSet.objects.all()
        elif o["pointset"]:
            sets = PointSet.objects.filter(pk=o["pointset"])
            if not sets.exists():
                raise CommandError(f"점묶음 {o['pointset']} 이 없다")
        else:
            raise CommandError("점묶음 번호나 --all 을 준다")
        for ps in sets:
            try:
                filled, missed = views.fill_elevation(ps, only_missing=o["missing"])
            except (elevation.ElevationError, trek.TrekError) as exc:
                self.stderr.write(self.style.ERROR(f"{ps.id} {ps.name}: {exc}"))
                continue
            self.stdout.write(f"{ps.id} {ps.name}: {filled}점 채움, {missed}점은 자료 밖")
