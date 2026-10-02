"""USGS 달 지질도 원도 6 장을 sqlite 한 장으로 굽는다 (devlog 039).

    manage.py build_moon_originals /nfs/temp-share/GSM/sources/moon/Lunar_Geologic_GIS_Renovation_March2013.zip

원본 zip(293 MB) 또는 푼 폴더를 받는다. 결과는 `<GSM_MOON_DIR>/moon_originals.sqlite` —
운영은 `/srv/GSM/db/moon/`. 원본은 NAS `N:\\GSM\\sources\\moon\\` 에 둔다. 판이 바뀌거나 굽는 법
(`moonmap.build`)을 고치면 다시 부른다. 그리는 법만 고쳤으면 `moonmap.RENDERER` 를 올리면 된다.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import moonmap


class Command(BaseCommand):
    help = "USGS 달 지질도 원도 6 장(zip)을 moon_originals.sqlite 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="Lunar_Geologic_GIS_Renovation_March2013.zip 또는 푼 폴더")
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        out = Path(o["out"]) if o["out"] else moonmap.data_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            counts = moonmap.build(o["source"], out)
        except (moonmap.MoonMapError, OSError) as exc:
            raise CommandError(str(exc))
        for map_id, n in counts.items():
            self.stdout.write(f"{map_id}: 단위 {n}")
        self.stdout.write(f"{out} ({out.stat().st_size // 1024 // 1024} MB)")
