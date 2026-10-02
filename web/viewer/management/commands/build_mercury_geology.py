"""USGS 수성 지질도(1:500만 도폭 아홉의 합본)를 sqlite 한 장으로 굽는다 (wetherilli 144).

원본은 Frigeri 외(2008)의 합본을 USGS 가 옛 PIGWAD 자리에 둔 것이다 —
https://asc-pds-services.s3.us-west-2.amazonaws.com/pigpen/mercury/merged_geology/mercuryMerged_geology-1.0.zip
(9 MB). 받아 둔 것은 NAS 의 `sources/mercury/` 에 있다.
결과는 `GSM_MERCURY_DIR`(기본 `<DB 옆>/mercury`)의 `mercury_geology.sqlite` 다. 저장소에 두지 않는다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import mercurymap


class Command(BaseCommand):
    help = "USGS 수성 지질도 합본(zip 이나 푼 폴더)을 GSM_MERCURY_DIR/mercury_geology.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="mercuryMerged_geology-1.0.zip 이나 푼 폴더")

    def handle(self, *args, **o):
        out = mercurymap.data_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            counts = mercurymap.build(Path(o["source"]), out)
        except (mercurymap.MercuryMapError, OSError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"단위 {counts['units']} 개·구조선 {counts['lines']} 개를 {out} 에 구웠다 "
                          f"({out.stat().st_size / 1e6:.1f} MB)")
