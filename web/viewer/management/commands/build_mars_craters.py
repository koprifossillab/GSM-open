"""화성 크레이터 목록(Robbins & Hynek 2012)을 sqlite 한 장으로 굽는다 (devlog 067).

원본은 USGS 가 옛 PIGWAD 자리에 둔 `RobbinsCraterDatabase_20121016.tab.zip`(13.6 MB)이다 —
https://asc-pds-services.s3.us-west-2.amazonaws.com/pigpen/mars/crater_consortium/ . 받아 둔 것은 NAS 의
`sources/mars/` 에 있다. 결과는 `GSM_MARS_DIR`(기본 `<DB 옆>/mars`)의 `mars_craters.sqlite` 다. 저장소에 두지 않는다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import marscraters


class Command(BaseCommand):
    help = "Robbins 화성 크레이터 목록(.tab.zip)을 GSM_MARS_DIR/mars_craters.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="RobbinsCraterDatabase_*.tab.zip 또는 풀어 둔 .tab")

    def handle(self, *args, **o):
        out = marscraters.data_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            n = marscraters.build(Path(o["source"]), out)
        except (marscraters.MarsCraterError, OSError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"크레이터 {n} 개를 {out} 에 구웠다 ({out.stat().st_size / 1e6:.0f} MB)")
