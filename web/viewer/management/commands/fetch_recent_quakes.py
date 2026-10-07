"""최근 지진 — USGS 실시간 피드(지난 7 일 M2.5 이상)를 받아 `<EARTH_DIR>/quakes_recent.json` 에 쓴다 (wetherilli 292).

    manage.py fetch_recent_quakes

호스트 cron 의 `hourly.sh` 가 한 시간에 한 번 부른다(`/srv/GSM/scripts/run.sh fetch_recent_quakes`). 피드는 USGS 가 자주 받아 가라고 연 주소지만
그래도 한 시간에 한 번만 받는다. 화면은 이 파일만 읽는다(`recentquakes.py`).
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog, recentquakes, usgs


class Command(BaseCommand):
    help = "USGS 실시간 지진 피드(지난 7 일 M2.5 이상)를 받아 둔다"

    def handle(self, *args, **opts):
        try:
            got = usgs.fetch_recent(recentquakes.path())
        except (usgs.UsgsError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        # 기록 표에 — 받은 수와 피드를 지은 때 (jikhanjung 024)
        fetchlog.note(rows=got["quakes"], upstream_version=f"{recentquakes.when(got['generated'])} UTC")
        self.stdout.write(f"최근 지진 {got['quakes']:,} 곳 — 피드를 지은 때 {recentquakes.when(got['generated'])} UTC")
