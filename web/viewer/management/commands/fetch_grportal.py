"""상류에서 통째로 받는 점 레이어를 미리 받아 둔다 — 그린란드 정부 포털과 NPI.

    manage.py fetch_grportal              없는 것만 받는다
    manage.py fetch_grportal --refresh    있어도 다시 받아 덮는다
    manage.py fetch_grportal --only npolar

화면에서 처음 켜는 사람이 기다리지 않게 하려는 것이다 — 그린란드 시료 2 만 점은
열 장, 20 초 남짓 걸리고(019), 스발바르 지명은 첫 찾기가 15 초다(021). 받는 길은
화면이 부르는 것과 같다(`views.point_features`). 레이어 사이에 1 초 쉰다
(devlog 010 의 빠르기).

이름이 `fetch_grportal` 인 것은 처음에 포털만 받았기 때문이다. 배포 스크립트와
사람 손이 이 이름을 알아 그대로 둔다.
"""
import time

from django.core.management.base import BaseCommand

from viewer import grportal, npolar, views

#: 받을 것. (상류 이름, 레이어 목록)
DOORS = (("grportal", lambda: list(grportal.LAYERS)),
         ("npolar", lambda: list(npolar.POINTS)))


class Command(BaseCommand):
    help = "그린란드 정부 포털·NPI 의 점 레이어를 캐시에 받아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--refresh", action="store_true", help="있어도 다시 받는다")
        parser.add_argument("--only", choices=[d[0] for d in DOORS], help="이 상류만 받는다")

    def handle(self, *args, **options):
        names = [name for door, layers in DOORS
                 if not options["only"] or door == options["only"] for name in layers()]
        for index, name in enumerate(names):
            if index:
                time.sleep(1)
            try:
                data = views.point_features(name, refresh=options["refresh"])
            except views.POINT_ERRORS as exc:
                self.stdout.write(self.style.ERROR(f"{name}: {exc}"))
                continue
            count = data.count(b'"Feature"')
            self.stdout.write(f"{name}: {count}점, {len(data) // 1024} KB")
