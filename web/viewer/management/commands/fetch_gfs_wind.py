"""지금의 바람 — GFS 의 가장 새 판의 분석과 예보를 받아 `<WIND_DIR>/gfs/` 에 굽는다 (koprifossillab P02·008).

    manage.py fetch_gfs_wind                  가장 새 판의 빠진 장만 받는다. 다 있으면 아무것도 하지 않는다
    manage.py fetch_gfs_wind --keep-hours 48  유효 시각이 가장 새 판보다 48 시간 넘게 앞선 것은 지운다 (기본)
    manage.py fetch_gfs_wind --cycle 2026100100

**호스트에서 돈다** — ecCodes·numpy 가 cron 의 전용 venv 에만 있다(`requirements-wind.txt`). cron 이 매시 :35 에
`/srv/GSM/scripts/run.sh fetch_gfs_wind` 로 부른다(`deploy/host/crontab.GSM`, koprifossillab 005).

판마다 분석(f000)과 예보 +3·+6·+9·+12 시간(`gfs.FORECAST_HOURS`)을 받는다. 분석이 올라온 가장 새 판을 고르고, 그 판에서
아직 없는 장만 차례로 받는다 — 예보 장은 분석보다 조금 늦게 올라오기도 하므로, 다음 차례(한 시간 뒤)가 빠진 것을 채운다.
목록의 시각은 **유효 시각**이다. 같은 유효 시각을 여러 판이 내면 새 판이 이긴다 — 00 판의 +6 예보는 06 판의 분석이 오면
그것으로 바뀐다. 장 사이는 1 초 쉰다.

구름량(전체·하층·중층·상층)도 같은 요청으로 받아 곁에 굽는다(koprifossillab 011). 구름이 없는 줄(구름을 받기 전의 장)은
빠진 장으로 보아 다시 받는다.
"""
import datetime as dt
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import fetchlog, gfs, wind


def run_of(entry: dict) -> str:
    """목록 한 줄의 판. 예보를 받기 전(0.34.0)의 줄에는 판이 없다 — 그때는 분석만 받았으니 시각이 곧 판이다."""
    return entry.get("run", entry["t"])


class Command(BaseCommand):
    help = "GFS 의 가장 새 판의 바람(10 m·250 hPa) 분석과 예보를 받아 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--cycle", help="이 판만 (YYYYMMDDHH, UTC)")
        parser.add_argument("--keep-hours", type=int, default=48, help="가장 새 판보다 이만큼 앞선 것은 지운다 (기본 48)")
        parser.add_argument("--pause", type=float, default=1.0, help="장 사이에 쉬는 초")

    def handle(self, *args, **opts):
        times = {e["t"]: e for e in wind.read_index("gfs")["times"]}
        cycles = [opts["cycle"]] if opts["cycle"] else gfs.recent_cycles(dt.datetime.now(dt.timezone.utc), 3)
        for cycle in cycles:
            have = {e.get("fh", 0) for e in times.values() if run_of(e) == cycle and e.get("clouds")}
            todo = [fh for fh in gfs.FORECAST_HOURS if fh not in have]
            if not todo:
                fetchlog.note(upstream_version=cycle, changed=0)            # 기록 표에 — 판과 바뀐 장 (jikhanjung 024)
                self.stdout.write(f"{cycle} 은 다 있다 — 할 일 없음")
                break
            done, waiting = [], []
            for fh in todo:
                try:
                    grib = gfs.download(cycle, fh)
                except gfs.GfsError as exc:
                    raise CommandError(str(exc)) from exc
                if grib is None:
                    waiting.append(fh)
                    if fh == 0:
                        break                        # 분석이 아직이면 이 판은 아직 없다
                    continue
                valid = gfs.valid_time(cycle, fh)
                if valid in times and run_of(times[valid]) > cycle:
                    continue                         # 더 새 판이 이미 이 시각을 냈다
                try:
                    winds, clouds = gfs.decode_all(grib)
                    entry = wind.write_time("gfs", valid, winds, clouds)
                except (gfs.GfsError, ValueError) as exc:
                    raise CommandError(f"{cycle} f{fh:03d}: {exc}") from exc
                entry.update(run=cycle, fh=fh)
                times[valid] = entry
                wind.write_index("gfs", list(times.values()))
                done.append(fh)
                time.sleep(opts["pause"])
            if 0 in waiting:
                self.stdout.write(f"{cycle} 은 아직 올라오지 않았다")
                continue                             # 앞 판으로
            fetchlog.note(upstream_version=cycle, expected=len(todo), rows=len(done), changed=len(done))
            self.stdout.write(f"{cycle} — 받은 장 {', '.join(f'+{h}' for h in done) or '없음'}"
                              + (f" · 아직 없는 장 {', '.join(f'+{h}' for h in waiting)}" if waiting else ""))
            break
        else:
            self.stdout.write("받을 판이 없다")
        newest = max((run_of(e) for e in times.values()), default=None)
        if newest:
            edge = (dt.datetime.strptime(newest, "%Y%m%d%H") - dt.timedelta(hours=opts["keep_hours"])).strftime("%Y%m%d%H")
            gone = wind.prune_before("gfs", edge)
            if gone:
                self.stdout.write(f"지움 {', '.join(gone)}")
