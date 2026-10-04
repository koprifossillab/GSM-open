"""점묶음의 한국 점마다 VWorld 둘레를 채운다 — 도로명·지번·읍면동·가장 가까운 단층·둘레 지명 (074).

    manage.py fill_places 12              점묶음 12 의 한국 점 모두 (다시 부르면 덮는다)
    manage.py fill_places 12 --missing    아직 비어 있는 점만
    manage.py fill_places --all --missing 모든 점묶음의 빈 점

화면의 📍 는 한국 점이 50 개를 넘으면 이 명령으로 넘긴다. 한 점에 VWorld 에 넷을 묻고 점 사이를 둔다
(`views.PLACES_PAUSE`). 대한민국 둘레(`vworld.KOREA_BOX`) 밖의 점은 묻지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import views, vworld
from viewer.models import PointSet


class Command(BaseCommand):
    help = "점묶음의 한국 점마다 VWorld 에서 주소·읍면동·가까운 단층·둘레 지명·보호구역·지목·소유구분을 채운다"

    def add_arguments(self, parser):
        parser.add_argument("pointset", nargs="?", type=int, help="점묶음 번호")
        parser.add_argument("--all", action="store_true", help="모든 점묶음")
        parser.add_argument("--missing", action="store_true", help="비어 있는 점만")

    def handle(self, *args, **o):
        if not vworld.enabled():
            raise CommandError("VWorld 열쇠가 없다 — GSM_VWORLD_KEY 나 <DB 옆>/vworld_key")
        if o["all"]:
            sets = PointSet.objects.filter(body="earth")
        elif o["pointset"]:
            sets = PointSet.objects.filter(pk=o["pointset"])
            if not sets.exists():
                raise CommandError(f"점묶음 {o['pointset']} 이 없다")
        else:
            raise CommandError("점묶음 번호나 --all 을 준다")
        for ps in sets:
            try:
                filled, missed = views.fill_places(ps, only_missing=o["missing"])
            except vworld.VWorldError as exc:
                self.stderr.write(self.style.ERROR(f"{ps.id} {ps.name}: {exc}"))
                continue
            self.stdout.write(f"{ps.id} {ps.name}: {filled}점 채움, {missed}점은 받지 못했다")
