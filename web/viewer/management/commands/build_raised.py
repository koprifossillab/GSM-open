"""RAISED 컨소시엄(Bentley 외 2014)의 접지선을 받아 `<GLACIO_DIR>/raised.json` 에 위경도로 적는다 (wetherilli 420).

셰이프는 Quantarctica3 사본뿐이라 NPI 의 문(`npolar.quantarctica`)으로 다섯 파일을 1 초 간격으로 받는다.
`--from <폴더>` 를 주면 받지 않고 그 폴더의 셰이프 한 벌을 굽는다. 자료가 2014 년에 멈춰 있어 한 번 부르면 된다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import npolar, raised


class Command(BaseCommand):
    help = "RAISED 남극 빙상 후퇴 20·15·10·5 ka (Quantarctica 사본) → <GLACIO_DIR>/raised.json (wetherilli 420)"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="src", help="받아 둔 셰이프 폴더 (RAISED_PaleoIceExtents.*)")

    def handle(self, *args, src=None, **opts):
        out = raised.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        stem = raised.QUANTARCTICA_PATH.rsplit("/", 1)[1]
        try:
            if src:
                parts = {ext: (Path(src) / (stem + ext)).read_bytes() for ext in (".shp", ".dbf", ".prj")}
            else:
                self.stdout.write("Quantarctica 에서 RAISED 셰이프를 받는다 …")
                parts = npolar.quantarctica(raised.QUANTARCTICA_PATH, parts=(".shp", ".dbf", ".prj"))
            got = raised.build(parts, out)
        except (OSError, npolar.NpolarError, raised.RaisedError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(" · ".join(f"{age} ka {n}" for age, n in got.items()) + f" → {out}")
