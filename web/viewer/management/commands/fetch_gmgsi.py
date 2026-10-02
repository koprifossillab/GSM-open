"""위성 구름 — NOAA GMGSI 의 가장 새 장을 받아 `<WIND_DIR>/gmgsi/` 에 굽는다 (koprifossillab 012).

    manage.py fetch_gmgsi              가장 새 장이 이미 있으면 아무것도 하지 않는다
    manage.py fetch_gmgsi --keep 24    최근 스물네 장만 둔다 (기본)

**호스트에서 돈다** — h5py·numpy 가 cron 의 전용 venv 에만 있다(`requirements-wind.txt`). cron 이 매시 :45 에
`/srv/GSM/scripts/run.sh fetch_gmgsi` 로 부른다(`deploy/host/crontab.GSM`). 장은 정시에서 30 분 남짓 뒤에 올라오므로
가장 가까운 지난 시부터 차례로 묻고, 처음 받은 장에서 멈춘다. 한 시간에 목록 한두 번·장 한 번(7.5 MB 남짓)이다.
"""
import datetime as dt

from django.core.management.base import BaseCommand, CommandError

from viewer import gmgsi, wind


class Command(BaseCommand):
    help = "NOAA GMGSI 위성 적외선 합성의 가장 새 장을 받아 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=24, help="남길 장 수 (기본 24 = 하루)")

    def handle(self, *args, **opts):
        times = {e["t"]: e for e in wind.read_index("gmgsi")["times"]}
        for hour in gmgsi.recent_hours(dt.datetime.now(dt.timezone.utc), 3):
            stamp = hour.strftime("%Y%m%d%H")
            if stamp in times:
                self.stdout.write(f"{stamp} 은 이미 있다 — 할 일 없음")
                break
            try:
                key = gmgsi.hour_key(hour)
                if not key:
                    self.stdout.write(f"{stamp} 은 아직 올라오지 않았다")
                    continue
                blob = gmgsi.download(key)
                entry = wind.write_sat(stamp, gmgsi.decode(blob))
            except (gmgsi.GmgsiError, ValueError, OSError) as exc:
                raise CommandError(f"{stamp}: {exc}") from exc
            times[stamp] = entry
            wind.write_index("gmgsi", list(times.values()))
            gone = wind.prune("gmgsi", opts["keep"])
            self.stdout.write(f"{stamp} 을 구웠다 ({len(blob) / 1e6:.1f} MB)" + (f" · 지움 {', '.join(gone)}" if gone else ""))
            break
        else:
            self.stdout.write("받을 장이 없다")
