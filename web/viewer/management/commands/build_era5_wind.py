"""지난 바람 — ERA5 의 날마다 00 UTC 바람을 `<WIND_DIR>/era5/` 에 굽는다 (koprifossillab P02).

    manage.py build_era5_wind                                  2005-06-01 ~ 2007-12-31 (기본)
    manage.py build_era5_wind --from 2005-06-01 --to 2005-06-30
    manage.py build_era5_wind --limit 10                        열 날만 (시험)
    manage.py build_era5_wind --clouds                          이미 구운 날에 구름량만 덧굽는다 (koprifossillab 011)

**호스트에서 돈다** — numcodecs·numpy 가 cron 의 전용 venv 에만 있다(`requirements-wind.txt`). 운영에서는
`/srv/GSM/scripts/run.sh build_era5_wind` 로 부른다. 한 날에 덩이 넷(10 m 통째 둘,
250 hPa 의 층만 둘), 13 MB 남짓을 받는다. **이미 구운 날은 건너뛴다** — 멈췄다가 다시 부르면 이어진다. 날 사이를 쉰다(devlog 010).
목록(`index.json`)은 열 날마다 적는다 — 중간에 멈춰도 구운 것은 화면에 뜬다.

새로 굽는 날에는 구름량(전체·하층·중층·상층, 덩이 넷·9 MB 남짓)도 함께 굽는다. `--clouds` 는 바람만 구운 날(구름을 받기 전)에
구름만 덧굽는다 — 이것도 이미 덧구운 날은 건너뛴다.
"""
import datetime as dt
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import era5, wind

FIRST, LAST = "2005-06-01", "2007-12-31"


class Command(BaseCommand):
    help = "ERA5 의 날마다 00 UTC 바람(10 m·250 hPa)을 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", default=FIRST)
        parser.add_argument("--to", dest="end", default=LAST)
        parser.add_argument("--limit", type=int, default=0, help="새로 구울 날의 수 (0 = 끝까지)")
        parser.add_argument("--pause", type=float, default=1.0, help="날 사이에 쉬는 초")
        parser.add_argument("--clouds", action="store_true", help="이미 구운 날에 구름량만 덧굽는다")

    def handle(self, *args, **opts):
        try:
            start = dt.date.fromisoformat(opts["start"])
            end = dt.date.fromisoformat(opts["end"])
        except ValueError as exc:
            raise CommandError(f"날짜는 YYYY-MM-DD 로: {exc}") from exc
        times = {e["t"]: e for e in wind.read_index("era5")["times"]}
        todo = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
        if opts["clouds"]:
            todo = [d for d in todo if d.strftime("%Y%m%d") in times and not times[d.strftime("%Y%m%d")].get("clouds")]
        else:
            todo = [d for d in todo if d.strftime("%Y%m%d") not in times]
        if opts["limit"]:
            todo = todo[:opts["limit"]]
        self.stdout.write(f"구울 날 {len(todo)} (이미 있는 것 {len(times)})")
        began = time.time()
        for n, day in enumerate(todo, 1):
            stamp = day.strftime("%Y%m%d")
            when = dt.datetime(day.year, day.month, day.day)
            try:
                if opts["clouds"]:
                    times[stamp]["clouds"] = wind.add_clouds("era5", stamp, era5.clouds(when))
                else:
                    times[stamp] = wind.write_time("era5", stamp, era5.winds(when), era5.clouds(when))
            except (era5.Era5Error, ValueError) as exc:
                wind.write_index("era5", list(times.values()))
                raise CommandError(f"{stamp}: {exc} — 그 앞까지는 적어 두었다") from exc
            if n % 10 == 0 or n == len(todo):
                wind.write_index("era5", list(times.values()))
                left = (time.time() - began) / n * (len(todo) - n)
                self.stdout.write(f"  {stamp} · {n}/{len(todo)} · 남은 시간 {left / 60:.0f} 분 남짓")
            time.sleep(opts["pause"])
        self.stdout.write(f"다 했다 — {len(times)} 날")
