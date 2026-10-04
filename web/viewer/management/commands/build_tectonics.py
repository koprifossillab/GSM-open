"""판 경계·세계 지질구 — Hasterok 외 2022 셰이프를 `data/earth_tectonics.json` 으로 굽는다 (wetherilli 272).

    manage.py build_tectonics /nfs/temp-share/GSM/sources/earth/hasterok2022

원본은 Zenodo 5093930(CC BY 4.0) 묶음의 `plates&provinces/` — `global_gprv.*`·`boundaries.*` 가 있으면 된다. 구운 것(1 MB 남짓)은 저장소에 둔다.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import tectonics


class Command(BaseCommand):
    help = "Hasterok 2022 의 판 경계·지질구 셰이프를 data/earth_tectonics.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("folder", help="global_gprv.shp·boundaries.shp 가 든 폴더")

    def handle(self, *args, **o):
        try:
            doc = tectonics.build(o["folder"])
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        doc = {"_주석": "판 경계·세계 지질구 — Hasterok 외 2022(Earth-Science Reviews, Zenodo 5093930, CC BY 4.0). 0.01° 로 반올림하고 "
                        "Douglas–Peucker 로 덜어 냈다. manage.py build_tectonics 가 굽는다 (wetherilli 272).", **doc}
        path = Path(settings.TECTONICS_FILE)
        path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        tectonics.data.cache_clear()
        self.stdout.write(self.style.SUCCESS(
            f"{path} — 지질구 {len(doc['provinces'])} · 경계 {len(doc['boundaries'])} · {path.stat().st_size // 1024} KB"))
