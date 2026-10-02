"""아라온호의 마지막 자리를 받아 `KOPRI_DIR/araon.jsonl` 에 한 줄 보탠다.

    manage.py fetch_araon                 마지막 자리 하나를 보탠다 (cron 이 매시간)
    manage.py fetch_araon --past          지난 365 일의 항적을 한 번 떠 둔다 — 날짜는 하루 단위, 365 번을 2 초 간격으로 (koprifossillab 009)

호스트 cron 이 매시간 `/srv/GSM/scripts/run.sh fetch_araon` 으로 부른다(`deploy/host/crontab.GSM`, koprifossillab 005). 한 번에 한 쪽만 받는다. 배가 아직 새 자리를 안
보냈으면(시각이 마지막 줄과 같으면) 보태지 않는다 — 극지에서는 위성 보고가 몇 시간씩 밀리기도 한다.
극지연구소 쪽은 지난 자리를 지워 버리므로, 이 파일이 아라온호 항적의 우리 쪽 기록이다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import kopri


class Command(BaseCommand):
    help = "아라온호의 마지막 자리를 받아 쌓는다"

    def add_arguments(self, parser):
        parser.add_argument("--past", action="store_true", help="지난 항적을 떠 둔다 (날짜는 하루 단위)")
        parser.add_argument("--days", type=int, default=kopri.ARAON_PAST_DAYS, help="--past 로 거슬러 갈 날 (365 까지)")

    def handle(self, *args, **options):
        if options["past"]:
            try:
                data = kopri.fetch_araon_past(min(max(options["days"], 1), kopri.ARAON_PAST_DAYS), say=self.stdout.write)
            except kopri.KopriError as exc:
                raise CommandError(str(exc)) from exc
            path = kopri.save_araon_past(data)
            self.stdout.write(f"아라온호 지난 항적 {len(data['points'])} 자리 ({data['nday']} 일) → {path}")
            return
        try:
            row = kopri.fetch_araon()
        except kopri.KopriError as exc:
            raise CommandError(str(exc)) from exc
        if kopri.append_araon(row):
            self.stdout.write(f"아라온호 {row['time']} {row['lat']}, {row['lon']}")
        else:
            self.stdout.write(f"아라온호 새 자리 없음 (마지막 {row['time']})")
