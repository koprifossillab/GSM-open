"""남호주 방사능 농도 격자(K·Th·U)를 네 칸에 하나씩 골라 적어 둔다 — 누른 자리의 값 (wetherilli 358).

    manage.py build_sa_radiometrics /nfs/temp-share/GSM/sources/australia/sa_radiometrics/SA_RAD_{K,Th,U}_2024_GDA94*.zip

원소마다의 ZIP(SARIG `mesac771`, 650 MB 남짓)을 받는다. 결과는 `<GSM_SARAD_DIR>/` 의 `k.i16`·`th.i16`·`u.i16`·`meta.json` — 운영은
`/srv/GSM/db/sa_radiometrics/`. numpy 없이 돌아 컨테이너에서도 부를 수 있다(원소마다 1 분 남짓, 메모리는 줄 하나).
"""
import time
import zipfile

from django.core.management.base import BaseCommand, CommandError

from viewer import sarad


class Command(BaseCommand):
    help = "남호주 방사능 농도 격자(K·Th·U ZIP)를 골라 적어 둔다 — 누른 자리의 값"

    def add_arguments(self, parser):
        parser.add_argument("sources", nargs="+", help="SA_RAD_K/Th/U_2024_*.zip")
        parser.add_argument("--out", default=None, help="기본: GSM_SARAD_DIR")

    def handle(self, *args, **o):
        started = time.monotonic()
        try:
            meta = sarad.build(o["sources"], o["out"], log=self.stdout.write)
        except (OSError, zipfile.BadZipFile, sarad.SaradError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"원소 {', '.join(sorted(meta))} — {o['out'] or sarad.root()} ({time.monotonic() - started:.0f} 초)"))
