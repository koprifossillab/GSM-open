"""대만 지질운의 열린자료를 한 번 받아 `TAIWAN_OPEN_DIR` 에 둔다 (wetherilli 305).

    manage.py fetch_taiwan_open                    # 갈래 일곱 모두 (몇 분)
    manage.py fetch_taiwan_open --api RockFall     # 하나만

탄층·토석류(퇴적·선상·유동구)·낙석·GPS 상시 관측소·암체 강도 등급 — 지질운에 WMS 그림이 없는 것이다. 문(`gsmma.fetch_open`)이 섬 전체
네모로 묻고, 상류가 끊으면 넷으로 나눠 다시 묻는다. 네 번 나눠도 끊기는 네모는 건너뛰고 파일의 `holes` 에 적는다. 묻는 사이 2 초. 화면이 부를 때는 상류를 타지 않는다(`twopen.py`).
사람이 부르는 명령이다 — cron 에 두지 않는다. 자료가 바뀌면(드물다) 다시 부른다.
"""
import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import gsmma, twopen


class Command(BaseCommand):
    help = "대만 지질운의 열린자료(WMS 가 없는 것)를 받아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--api", default="", help="이 갈래만 (쉼표로 여럿)")
        parser.add_argument("--gap", type=float, default=2.0, help="상류에 묻는 사이 초 (기본 2)")

    def handle(self, *args, **o):
        apis = [a.strip() for a in o["api"].split(",") if a.strip()] or list(gsmma.OPEN_APIS)
        unknown = [a for a in apis if a not in gsmma.OPEN_APIS]
        if unknown:
            raise CommandError(f"모르는 갈래: {', '.join(unknown)} — {', '.join(gsmma.OPEN_APIS)}")
        folder = Path(settings.TAIWAN_OPEN_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        for api in apis:
            started = time.time()
            holes = []
            try:
                features = gsmma.fetch_open(api, gap=o["gap"], log=self.stdout.write, holes=holes)
            except gsmma.GsmmaError as exc:
                raise CommandError(str(exc)) from exc
            tmp = folder / f"{api}.geojson.part"
            tmp.write_text(json.dumps({"type": "FeatureCollection", "fetched": time.strftime("%Y-%m-%d"),
                                       **({"holes": holes} if holes else {}), "features": features},
                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tmp.replace(folder / f"{api}.geojson")
            self.stdout.write(self.style.SUCCESS(f"{api} — {len(features):,} 개 ({time.time() - started:.0f} 초)"))
            if holes:
                self.stdout.write(self.style.WARNING(f"  받지 못한 네모 {len(holes)} — 파일의 holes 에 적었다: {holes}"))
        twopen.forget()
