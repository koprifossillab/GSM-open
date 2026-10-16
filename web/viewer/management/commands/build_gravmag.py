"""자력 이상(EMAG2v3)·부게 중력 이상(EIGEN-6C4)을 구워 둔다 (wetherilli 391). numpy 없이 돈다 — 컨테이너에서도 부를 수 있다.

    manage.py build_gravmag --magnetic /nfs/temp-share/GSM/sources/earth/emag2/EMAG2_V3_20170530.zip
    manage.py build_gravmag --bouguer  /nfs/temp-share/GSM/sources/earth/icgem/EIGEN-6C4_bouguer.gdf

결과는 `<GSM_EARTH_DIR>/gravmag_magnetic.*`·`gravmag_bouguer.*` — 운영은 `/srv/GSM/db/earth/`. 판 하나만 줘도 된다.
EMAG2 는 CSV 5 800 만 줄을 흘려 읽어 4′ 로 줄인다 — 몇 분, 메모리 0.5 GB 남짓.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import gravmag


class Command(BaseCommand):
    help = "자력 이상(EMAG2v3 float TIFF)·부게 중력 이상(ICGEM .gdf)을 지역 탭용 경위도 격자로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--magnetic", help="EMAG2v3 CSV 묶음 EMAG2_V3_20170530.zip")
        parser.add_argument("--bouguer", help="ICGEM 이 EIGEN-6C4 로 뽑은 부게 이상 격자 (.gdf)")

    def handle(self, *args, **o):
        if not o["magnetic"] and not o["bouguer"]:
            raise CommandError("--magnetic 이나 --bouguer 를 준다")
        for kind, path, read in (("magnetic", o["magnetic"], gravmag.read_emag2), ("bouguer", o["bouguer"], gravmag.read_gdf)):
            if not path:
                continue
            started = time.monotonic()
            try:
                info = gravmag.build(kind, read(path))
            except (OSError, ValueError, KeyError, gravmag.GravMagError) as exc:
                raise CommandError(f"{kind}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{kind}: {info['w']}×{info['h']}, {info['min']:g} … {info['max']:g} ({time.monotonic() - started:.0f} 초)"))
