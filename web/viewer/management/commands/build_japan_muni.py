"""일본 시군구 코드 → 이름 표를 굽는다 — 좌표→주소(`mreversegeocoder`)가 코드만 주어서 (wetherilli 230).

원본은 지리원 지도(地理院地図)가 같은 일에 쓰는 `https://maps.gsi.go.jp/js/muni.js` 다(`GSI.MUNI_ARRAY["13101"] = '13,東京都,13101,千代田区'`,
1 919 줄). 사람이 받아 넘긴다 — 이 명령은 상류를 부르지 않는다:

    curl -A 'GSM/0.1' -O https://maps.gsi.go.jp/js/muni.js
    python manage.py build_japan_muni muni.js

쓰는 곳은 화면(`static/viewer/japan-muni.json`, 브라우저가 처음 일본 주소를 물을 때 한 번 받는다). 꼴은 `{"코드": "도도부현 시군구"}`.
코드는 앞의 0 을 뗀 수다 — 상류의 `muniCd` 는 `01101` 로 오고 표는 `1101` 이라 화면이 수로 맞춘다. 시군구 이름 속의 전각 빈칸
(`札幌市　中央区`)은 뗀다 — 주소는 붙여 쓴다.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

ROW = re.compile(r"""MUNI_ARRAY\["(\d+)"\]\s*=\s*'([^']*)'""")


def parse(text: str) -> dict:
    out = {}
    for code, value in ROW.findall(text):
        parts = value.split(",")
        if len(parts) != 4 or parts[2] != code:
            raise CommandError(f"꼴이 다른 줄: {code} {value}")
        out[str(int(code))] = parts[1] + parts[3].replace("　", "").replace(" ", "")
    return out


class Command(BaseCommand):
    help = "지리원 지도의 muni.js → static/viewer/japan-muni.json (일본 시군구 코드 → 이름)"

    def add_arguments(self, parser):
        parser.add_argument("muni_js", help="받아 둔 muni.js")

    def handle(self, muni_js, **opts):
        table = parse(Path(muni_js).read_text(encoding="utf-8"))
        if len(table) < 1500:
            raise CommandError(f"줄이 너무 적다 ({len(table)}) — 다른 파일이 아닌가")
        out = Path(settings.BASE_DIR) / "viewer" / "static" / "viewer" / "japan-muni.json"
        out.write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(table)} 시군구 → {out}")
