"""브라질 SGB 지질도의 단위 이름표를 모아 둔다 — 보는 범위의 범례에 이름·시대를 붙인다 (wetherilli 191).

    manage.py fetch_sgb_units                 # 범례가 있는 판 셋 다 (1:250만·1:100만·1:25만)
    manage.py fetch_sgb_units --layers sgb:2500k

GeoServer 의 범례 JSON 은 기호와 색만 준다. 이름·시대는 WFS 로 판을 한 번 훑어 기호마다 하나씩 모은다 — 기하는 받지 않는다.
1:100만은 4 만 6 천 줄이라 5 000 줄씩 열 번 남짓, 쪽 사이 1 초. 판이 바뀔 일이 드물어 사람이 가끔 부른다. 없어도 범례는 기호로 뜬다.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import sgb


class Command(BaseCommand):
    help = "브라질 SGB 지질도의 기호 → 이름·시대 표를 모아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--layers", default=",".join(sgb.legend_layers()))
        parser.add_argument("--pause", type=float, default=1.0, help="쪽 사이 쉬는 초 (1 초 밑으로는 내리지 않는다)")

    def handle(self, *args, **o):
        if o["pause"] < 1.0:
            raise CommandError("1 초보다 잦게는 묻지 않는다")
        names = [n.strip() for n in o["layers"].split(",") if n.strip()]
        unknown = [n for n in names if n not in sgb.legend_layers()]
        if unknown:
            raise CommandError(f"단위 면이 아닌 레이어: {', '.join(unknown)}")
        path = sgb.units_path()
        layers = sgb.load_units()
        for name in names:
            try:
                layers[name] = sgb.fetch_units(name, pause=o["pause"], log_line=self.stdout.write)
            except sgb.SgbError as exc:
                raise CommandError(f"{name}: {exc}") from exc
            # 판마다 적는다 — 둘째 판에서 멈춰도 첫째 판은 남는다
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(str(path) + ".tmp")
            tmp.write_text(json.dumps({"layers": layers}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
            self.stdout.write(self.style.SUCCESS(f"{name}: 기호 {len(layers[name]):,}개 → {path}"))
