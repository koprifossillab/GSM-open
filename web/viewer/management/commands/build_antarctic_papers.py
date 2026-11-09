"""남극 논문 두 편의 벡터 레이어 — 자료 저장소의 zip 둘을 `data/antarctic_papers.json` 으로 굽는다 (wetherilli 435).

    manage.py build_antarctic_papers armadillo2026_figshare_25450219_EAFBP.zip gernon2026_zenodo_19205651_GIS_files.zip \\
        [--fig2a fig2a_lines.geojson]

원본은 figshare 25450219(`EAFBP.zip`, CC BY 4.0)와 Zenodo 19205651(`GIS_files.zip`, CC BY 4.0). Fig. 2a 해석선은 그림에서 딴
GeoJSON 이다. 구운 것은 1 MB 안팎이라 저장소에 둔다 — 다시 구우면 그 파일을 커밋한다. numpy 없이 돈다(10 초 남짓).
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import antpapers


class Command(BaseCommand):
    help = "Armadillo·Gernon 2026 의 자료 zip 을 data/antarctic_papers.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("eafbp", help="figshare 25450219 의 EAFBP.zip")
        parser.add_argument("gernon", help="Zenodo 19205651 의 GIS_files.zip")
        parser.add_argument("--fig2a", help="Fig. 2a 해석선 GeoJSON (경위도, name·kind)")

    def handle(self, *args, **o):
        try:
            counts = antpapers.build(Path(o["eafbp"]).read_bytes(), Path(o["gernon"]).read_bytes(),
                                     Path(o["fig2a"]).read_bytes() if o["fig2a"] else None)
        except (OSError, antpapers.AntPapersError) as exc:
            raise CommandError(str(exc)) from exc
        path = antpapers.path()
        for name, n in counts.items():
            self.stdout.write(f"  {name} {n:,}")
        self.stdout.write(self.style.SUCCESS(f"{path} — {path.stat().st_size // 1024} KB"))
