"""해양 지각 연대·해저 퇴적층 두께를 구워 둔다 (wetherilli 264). numpy·h5py 없이 돈다 — 컨테이너에서도 부를 수 있다.

    manage.py build_seafloor --age /nfs/temp-share/GSM/sources/earth/age.2020.1.GTS2012.6m.grd \\
                             --sediment /nfs/temp-share/GSM/sources/earth/GlobSed-v3.xyz

결과는 `<GSM_EARTH_DIR>/seafloor_age.*`·`seafloor_sediment.*` — 운영은 `/srv/GSM/db/earth/`. 원본은 NAS `N:\\GSM\\sources\\earth\\`
(연대는 EarthByte agegrid 2020, 두께는 NOAA NCEI 0305030). 판 하나만 줘도 된다.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import seafloor


class Command(BaseCommand):
    help = "해양 지각 연대(Seton 2020 .grd)·퇴적층 두께(GlobSed v3 .xyz)를 온 지구 화면용으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--age", help="age.2020.1.GTS2012.6m.grd (NetCDF-3)")
        parser.add_argument("--sediment", help="GlobSed-v3.xyz")

    def handle(self, *args, **o):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        if not o["age"] and not o["sediment"]:
            raise CommandError("--age 나 --sediment 를 준다")
        for kind, path, read in (("age", o["age"], seafloor.read_age), ("sediment", o["sediment"], seafloor.read_xyz)):
            if not path:
                continue
            started = time.monotonic()
            try:
                info = seafloor.build(kind, read(path))
            except (OSError, ValueError, seafloor.SeafloorError) as exc:
                raise CommandError(f"{kind}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{kind}: {info['w']}×{info['h']}, {info['min']:g} … {info['max']:g} ({time.monotonic() - started:.0f} 초)"))
