"""세계 암상 — GLiM 0.5° 격자판을 `data/glim_05deg.json` 으로 굽는다 (wetherilli 267).

    manage.py build_glim /nfs/temp-share/GSM/sources/earth/GLiM_0.5deg.zip

원본은 PANGAEA 788537(Hartmann & Moosdorf 2012, CC BY 3.0) — zip 안의 `glim_wgs84_0point5deg.txt.asc`. 구운 것(260 KB 남짓)은 저장소에 둔다.
"""
import json
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import glim

MEMBER = "glim_wgs84_0point5deg.txt.asc"


class Command(BaseCommand):
    help = "GLiM 0.5° 격자(zip 또는 .asc)를 data/glim_05deg.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("source", help="PANGAEA 788537 의 zip 또는 glim_wgs84_0point5deg.txt.asc")

    def handle(self, *args, **o):
        src = Path(o["source"])
        try:
            if src.suffix.lower() == ".zip":
                with zipfile.ZipFile(src) as zf:
                    text = zf.read(MEMBER).decode("ascii")
            else:
                text = src.read_text(encoding="ascii")
            rows = glim.read_ascii(text)
        except (OSError, KeyError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        doc = {"_주석": "GLiM 0.5° 격자(Hartmann & Moosdorf 2012, PANGAEA 788537, CC BY 3.0) — 줄마다 720 글자, 북→남. "
                        "'.' 은 빈 칸, 'a' 부터 갈래 번호 1… (web/viewer/glim.py 의 CLASSES). manage.py build_glim 이 굽는다 (wetherilli 267).",
               "rows": rows}
        Path(settings.GLIM_FILE).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        filled = sum(1 for r in rows for c in r if c != glim.NODATA)
        self.stdout.write(self.style.SUCCESS(f"{settings.GLIM_FILE} — 칠한 칸 {filled:,}"))
