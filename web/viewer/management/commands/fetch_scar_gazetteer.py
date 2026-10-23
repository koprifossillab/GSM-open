"""SCAR 남극 통합 지명사전(CGA)을 모두 받아 `<SCAR_DIR>/cga_place_names.json` 에 적는다 (wetherilli 412).

문(`scar.py`)으로 AADC 의 WFS 를 1 만 건씩 1 초 간격으로 부른다(네 쪽, 이름 3 만 9 천). 지형마다 묶어 적기만 한다.
지명사전은 나라들이 이름을 더할 때마다 자라니 판을 붙이기 전이나 몇 달에 한 번 사람이 부른다 — cron 에 두지 않는다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import scar


class Command(BaseCommand):
    help = "SCAR 남극 통합 지명사전 → <SCAR_DIR>/cga_place_names.json (wetherilli 412)"

    def handle(self, *args, **opts):
        out = scar.path()
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stdout.write("AADC 에서 SCAR 지명사전을 받는다 …")
        try:
            got = scar.download(out)
        except scar.ScarError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"이름 {got['names']:,} · 지형 {got['places']:,} → {out}")
