"""ITS_LIVE v2 빙하 유속을 필요한 몫만 받아 칠해 둔다 (wetherilli 433).

**호스트에서만 돈다** — 칠하기에 numpy 를 쓴다(제품 이미지에는 없다):

    /srv/GSM/scripts/run.sh build_itslive                      # 남극·그린란드·스발바르
    /srv/GSM/scripts/run.sh build_itslive --region svalbard    # 하나만

COG 를 통째로 받지 않는다 — 머리를 읽고 고른 겹의 타일만 Range 로, 1 초 간격으로 묻는다. 남극 280 MB 남짓(480 m 온 대륙 + 120 m 기지
둘레 둘)·그린란드 170 MB 남짓(240 m)·스발바르 30 MB 남짓(120 m). 결과는 `<GSM_ITSLIVE_DIR>/<지역>/` 의 `tiles/{z}/{x}/{y}.webp`·`*.i16`·
`meta.json` — 운영은 `/srv/GSM/db/itslive/`. 새 타일은 옆 자리(`tiles.new`)에 다 쓰고 바꿔 끼운다.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import itslive


class Command(BaseCommand):
    help = "ITS_LIVE v2 빙하 유속(남극·그린란드·스발바르)을 Range 로 받아 칠해 둔다 — 호스트에서만 (numpy)"

    def add_arguments(self, parser):
        parser.add_argument("--region", action="append", choices=sorted(itslive.REGIONS), help="이 지역만 (여러 번 줄 수 있다)")
        parser.add_argument("--out", default=None, help="기본: GSM_ITSLIVE_DIR/<지역> — 줄 때는 지역 하나만")

    def handle(self, *args, **o):
        try:
            import numpy  # noqa: F401
        except ImportError:
            raise CommandError("numpy 가 없다 — 호스트의 /srv/GSM/scripts/run.sh build_itslive 로 부른다")
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None            # 남극 480 m 겹이 1 억 칸이다 — 폭탄이 아니라 지도다
        regions = o["region"] or list(itslive.REGIONS)
        if o["out"] and len(regions) != 1:
            raise CommandError("--out 은 --region 하나와 함께 준다")
        for region in regions:
            started = time.monotonic()
            try:
                stats = itslive.build(region, o["out"], log_line=self.stdout.write)
            except (OSError, itslive.ItsLiveError) as exc:
                raise CommandError(f"{region}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{region}: 타일 {stats['tiles']} 장, 받은 것 {stats['mb_in']} MB ({time.monotonic() - started:.0f} 초)"))
