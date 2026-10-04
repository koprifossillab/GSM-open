"""지구 충돌구·거대 화성암 지대 — `data/earth_impacts.json` 으로 굽는다 (wetherilli 283).

    manage.py build_impacts --wikidata /nfs/temp-share/GSM/sources/earth/impacts/wikidata_impact_craters_20261005.json \\
                            --lips /nfs/temp-share/GSM/sources/earth/earthbyte/IgneousProvinces.zip

충돌구는 Wikidata SPARQL 의 답(JSON, CC0)을 떠 둔 파일, LIP 는 EarthByte GPlates 2.3 자료(CC BY 4.0). LIP 에 PALEOMAP 판을 붙이므로
`data/paleomap2016.json` 이 있어야 한다.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import impacts


class Command(BaseCommand):
    help = "충돌구(Wikidata JSON)·LIP(EarthByte zip)를 data/earth_impacts.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--wikidata", required=True)
        parser.add_argument("--lips", required=True)

    def handle(self, *args, **o):
        try:
            craters = impacts.read_wikidata(o["wikidata"])
            lips = impacts.read_lips(o["lips"])
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        doc = {"_주석": "지구 충돌구(Wikidata, CC0, 2026-10-05 의 SPARQL 답)와 거대 화성암 지대(Johansson 외 2018, EarthByte GPlates 2.3, "
                        "CC BY 4.0). LIP 의 pid·reach 는 면의 가운데가 담기는 PALEOMAP 판이다. manage.py build_impacts 가 굽는다 (wetherilli 283).",
               "impacts": craters, "lips": lips}
        path = Path(settings.IMPACTS_FILE)
        path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        impacts.data.cache_clear()
        moved = sum(1 for x in lips if x["pid"] is not None)
        self.stdout.write(self.style.SUCCESS(
            f"{path} — 충돌구 {len(craters)} · LIP {len(lips)}(판이 붙은 것 {moved}) · {path.stat().st_size // 1024} KB"))
