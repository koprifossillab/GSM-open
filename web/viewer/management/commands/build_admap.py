"""남극 자력 이상 ADMAP-2 를 칠해 3031 타일로 잘라 둔다 (wetherilli 262).

    manage.py build_admap /nfs/temp-share/GSM/sources/admap2/grid.zip

원본 zip(179 MB, PANGAEA 892723) 또는 `ADMAP_2B_2017.grd` 하나를 받는다. 결과는 `<GSM_ADMAP_DIR>/` 의 `tiles/{z}/{x}/{y}.webp`·
`values.i16`(누른 자리)·`meta.json` — 운영은 `/srv/GSM/db/admap2/`. numpy 없이 돌아 컨테이너에서도 부를 수 있다(1 분 남짓, 메모리 수백 MB).
새 타일은 옆 자리(`tiles.new`)에 다 쓰고 나서 바꿔 끼운다.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import admap


class Command(BaseCommand):
    help = "남극 자력 이상 ADMAP-2(zip 또는 grd)를 칠해 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="grid.zip 또는 ADMAP_2B_2017.grd")
        parser.add_argument("--out", default=None, help="기본: GSM_ADMAP_DIR")

    def handle(self, *args, **o):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None            # 2 천만 화소 — 폭탄이 아니라 지도다
        started = time.monotonic()
        try:
            stats = admap.build(o["source"], o["out"], log=self.stdout.write)
        except (OSError, admap.AdmapError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"타일 {stats['tiles']} 장, {stats['mb']} MB — {o['out'] or admap.root()} ({time.monotonic() - started:.0f} 초)"))
