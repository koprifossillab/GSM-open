"""남극 논문 두 편의 벡터 레이어 — 자료 저장소의 zip 과 그림에서 딴 GeoJSON 을 `data/antarctic_papers.json` 으로 굽는다 (wetherilli 435).

    manage.py build_antarctic_papers armadillo2026_figshare_25450219_EAFBP.zip \\
        [--fig2a fig2a_lines.geojson] [--fig4a fig4a_ice_extent.geojson]

원본은 figshare 25450219(`EAFBP.zip`, CC BY 4.0). Fig. 2a 해석선(wetherilli 437)과 Gernon 2026 Fig. 4A 의 빙상 범위(wetherilli 440)는
그림에서 딴 GeoJSON 이다. 구운 것은 0.2 MB 남짓이라 저장소에 둔다 — 다시 구우면 그 파일을 커밋한다. numpy 없이 돈다.
**고지형 등고선은 여기서 굽지 않는다** — 34 연대라 저장소에 두기엔 커서 `build_gernon_paleotopo` 가 래스터 옆에 굽는다(wetherilli 439).
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import antpapers


class Command(BaseCommand):
    help = "Armadillo 2026 의 자료 zip 과 그림에서 딴 선·면을 data/antarctic_papers.json 으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("eafbp", help="figshare 25450219 의 EAFBP.zip")
        parser.add_argument("--fig2a", help="Fig. 2a 해석선 GeoJSON (경위도, name·kind)")
        parser.add_argument("--fig4a", help="Gernon 2026 Fig. 4A 빙상 범위 GeoJSON (경위도, age_ma·name·note·area_km2, 면)")

    def handle(self, *args, **o):
        def read(key):
            return Path(o[key]).read_bytes() if o[key] else None
        try:
            counts = antpapers.build(Path(o["eafbp"]).read_bytes(), read("fig2a"), read("fig4a"))
        except (OSError, antpapers.AntPapersError) as exc:
            raise CommandError(str(exc)) from exc
        path = antpapers.path()
        for name, n in counts.items():
            self.stdout.write(f"  {name} {n:,}")
        self.stdout.write(self.style.SUCCESS(f"{path} — {path.stat().st_size // 1024} KB"))
