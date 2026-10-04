"""세계 활성단층 — GEM Global Active Faults GeoJSON 을 `<EARTH_DIR>/earth_faults.json` 으로 굽는다 (wetherilli 279).

    manage.py build_faults /nfs/temp-share/GSM/sources/earth/gem_faults/gem_active_faults_harmonized.geojson

원본은 GitHub GEMScienceTools/gem-global-active-faults(CC BY-SA 4.0). 구운 것도 같은 조건이다.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import faults


class Command(BaseCommand):
    help = "GEM Global Active Faults GeoJSON 을 data/earth_faults.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("geojson", help="gem_active_faults_harmonized.geojson")

    def handle(self, *args, **o):
        try:
            doc = faults.build(o["geojson"])
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        doc = {"_주석": "세계 활성단층 — GEM Global Active Faults(Styron & Pagani 2020), CC BY-SA 4.0 — 이 파일도 같은 조건이다. "
                        "0.001° 로 반올림하고 Douglas–Peucker 로 덜어 냈다. manage.py build_faults 가 굽는다 (wetherilli 279).", **doc}
        path = Path(settings.FAULTS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        faults.data.cache_clear()
        self.stdout.write(self.style.SUCCESS(f"{path} — 단층 {len(doc['faults']):,} · {path.stat().st_size // 1024} KB"))
