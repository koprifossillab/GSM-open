"""ECCO2 의 표층 해류를 받아 `<OCEAN_DIR>/ecco2/` 에 굽는다 (koprifossillab 014).

    manage.py build_ecco2 --date 20060617              그 날 하나 (3 일 평균 파일이 있는 날)
    manage.py build_ecco2 --date 20060617 --date …     여럿
    manage.py build_ecco2 --monthly                     달마다 15 일에 가장 가까운 날 하나 — 1992-01 ~ 2019-03, 327 날
    manage.py build_ecco2 --monthly --from 200601 --to 200612
    manage.py build_ecco2 --list                        받을 수 있는 날을 적기만 한다

**사람이 부른다** — 해류는 빨리 바뀌지 않아 cron 에 걸지 않았다. **호스트에서 돈다** — 굽기에 numpy 가 들어 cron 의
전용 venv(`/srv/GSM/scripts/run.sh build_ecco2 …`)로 부른다(koprifossillab 005). 날마다 `UVEL`·`VVEL` 의 머리와 표층(4 MB 씩)을
Range 로 받는다. 파일 사이 1 초 쉰다. 이미 구운 날은 `--force` 가 아니면 건너뛴다 — 받다 멈추면 다시 부르면 이어 간다.

**달마다 한 장**(koprifossillab 015) — 해류는 철 따라 바뀌고 와류는 몇 주에 걸쳐 움직인다. 달마다 그 달 15 일에 가장
가까운 3 일 평균 하나를 고른다(평균하지 않는다 — 와류가 산다). 날짜는 `UVEL`·`VVEL` 둘 다 있는 날에서만 고른다.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import ecco, ocean


def monthly(days: list) -> list:
    """`YYYYMMDD` 들 -> 달마다 15 일에 가장 가까운 하나. 같은 거리면 앞날."""
    best = {}
    for day in days:
        month, gap = day[:6], abs(int(day[6:]) - 15)
        if month not in best or gap < best[month][0]:
            best[month] = (gap, day)
    return [best[m][1] for m in sorted(best)]


class Command(BaseCommand):
    help = "ECCO2 의 표층 해류(u·v)를 받아 PNG 로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--date", action="append", default=[], help="YYYYMMDD — 여럿이면 되풀이")
        parser.add_argument("--list", action="store_true", help="받을 수 있는 날을 적는다")
        parser.add_argument("--monthly", action="store_true", help="달마다 15 일에 가장 가까운 날 하나")
        parser.add_argument("--from", dest="start", default="", help="--monthly 의 첫 달 (YYYYMM)")
        parser.add_argument("--to", dest="end", default="", help="--monthly 의 끝 달 (YYYYMM)")
        parser.add_argument("--force", action="store_true", help="구운 날도 다시")
        parser.add_argument("--pause", type=float, default=1.0, help="파일 사이에 쉬는 초")

    def handle(self, *args, **opts):
        if opts["list"]:
            days = ecco.dates("UVEL")
            self.stdout.write(f"{len(days)} 날 — {days[0]} … {days[-1]}" if days else "없다")
            return
        if opts["monthly"]:
            both = sorted(set(ecco.dates("UVEL")) & set(ecco.dates("VVEL")))
            opts["date"] += [d for d in monthly(both) if (not opts["start"] or d[:6] >= opts["start"])
                             and (not opts["end"] or d[:6] <= opts["end"])]
            self.stdout.write(f"달마다 하나 — {len(opts['date'])} 날")
        if not opts["date"]:
            raise CommandError("--date 를 준다 (또는 --monthly·--list)")
        times = {e["t"]: e for e in ocean.read_index("ecco2")["times"]}
        pause = max(opts["pause"], 1.0)
        for i, day in enumerate(opts["date"]):
            if not ocean.valid("ecco2", day):
                raise CommandError(f"날짜가 YYYYMMDD 가 아니다: {day}")
            if day in times and not opts["force"]:
                self.stdout.write(f"{day} 은 이미 구웠다 — 건너뜀")
                continue
            if i:
                time.sleep(pause)
            try:
                u = ecco.surface("UVEL", day)
                time.sleep(pause)
                v = ecco.surface("VVEL", day)
            except ecco.EccoError as exc:
                raise CommandError(f"{day}: {exc}") from exc
            times[day] = ocean.write_time("ecco2", day, u, v)
            ocean.write_index("ecco2", list(times.values()))
            self.stdout.write(f"{day} 구웠다 — u {times[day]['u']} · v {times[day]['v']} m/s")
