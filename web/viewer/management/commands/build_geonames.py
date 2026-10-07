"""온 세계의 도시 이름 — GeoNames `cities1000` 을 `<EARTH_DIR>/geonames.sqlite` 로 굽는다 (wetherilli 374).

    manage.py build_geonames /nfs/temp-share/GSM/sources/earth/geonames \\
        --countries /nfs/temp-share/GSM/sources/earth/natural_earth/ne_10m_admin_0_countries.zip

폴더에는 download.geonames.org/export/dump 에서 받은 `cities1000.zip`·`admin1CodesASCII.txt` 를 둔다(CC BY 4.0).
`--countries` 는 나라 이름의 한국어판을 옮기려는 것이다 — Natural Earth(퍼블릭 도메인)의 `NAME_KO`. 없으면 나라 칸이 빈다.
구운 것은 20 MB 남짓이라 저장소에 두지 않는다.
"""
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import geonames
from viewer.management.commands.build_natural_earth import dbf


def countries(zip_path) -> list:
    """Natural Earth 나라 표 → [(ISO 두 글자, 영어 이름, 한국어 이름)]. `ISO_A2` 가 -99 인 것(프랑스·노르웨이)은 `ISO_A2_EH` 로."""
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".dbf"))
        rows = dbf(zf.read(name))
    out = {}
    for r in rows:
        cc = r["iso_a2"] if r["iso_a2"] != "-99" else r.get("iso_a2_eh", "")
        if len(cc) == 2 and cc not in out:
            out[cc] = (cc, r["name_en"] or r["name"], r["name_ko"])
    return list(out.values())


class Command(BaseCommand):
    help = "GeoNames cities1000 을 <EARTH_DIR>/geonames.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("folder", help="cities1000.zip·admin1CodesASCII.txt 가 든 폴더")
        parser.add_argument("--countries", help="Natural Earth ne_10m_admin_0_countries.zip — 나라 이름(한국어)")

    def handle(self, *args, **o):
        try:
            names = countries(o["countries"]) if o["countries"] else []
            done = geonames.build(Path(o["folder"]), countries=names)
        except (OSError, KeyError, ValueError, StopIteration, zipfile.BadZipFile) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"{geonames.path()} — 도시 {done['rows']:,} 곳(한국어 이름 {done['korean']:,}), 나라 {len(names)}, {done['seconds']} 초"))
