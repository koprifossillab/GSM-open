"""USGS 화성 옛 지질도를 sqlite 한 장으로 굽는다 (devlog 068).

원본은 USGS 가 옛 PIGWAD 자리에 둔 GIS 묶음이다 —
https://asc-pds-services.s3.us-west-2.amazonaws.com/pigpen/mars/geology/ . 묶음 여럿을 한꺼번에 준다 —
I-1802 전 지구판(`i-1802ABC_Mars_global_geology_dd.zip`)은 꼭 있어야 하고, SIM 2888(`NPlains_geology_SIM2888_2005.zip`)·
I-2650(`i-2650_dd.zip`)·MTM 지역도(`i-1696_dd.zip` …, `i-2208.zip`)는 있는 만큼 들어간다. 받아 둔 것은 NAS 의
`sources/mars/geology/` 에 있다.
결과는 `GSM_MARS_DIR`(기본 `<DB 옆>/mars`)의 `mars_originals.sqlite` 다. 저장소에 두지 않는다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import marsmap


class Command(BaseCommand):
    help = "USGS 화성 옛 지질도·지역 지질도 묶음들(zip 이나 푼 폴더)을 GSM_MARS_DIR/mars_originals.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("sources", nargs="+", help="USGS 묶음(zip 이나 푼 폴더) 여럿")

    def handle(self, *args, **o):
        out = marsmap.data_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            counts = marsmap.build([Path(p) for p in o["sources"]], out)
        except (marsmap.MarsMapError, OSError) as exc:
            raise CommandError(str(exc))
        done = ", ".join(f"{k} {v}" for k, v in counts.items())
        self.stdout.write(f"판 {len(counts)} 장의 단위({done})를 {out} 에 구웠다 ({out.stat().st_size / 1e6:.0f} MB)")
