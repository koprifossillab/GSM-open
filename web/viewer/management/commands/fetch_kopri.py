"""극지연구소의 암석 시료 목록과 KPDC 자료 목록·상세를 모아 `KOPRI_DIR` 에 둔다.

    manage.py fetch_kopri                   암석 시료 + KPDC·운석 (상세는 없는 것만)
    manage.py fetch_kopri --only rock       암석 시료만 (스무 장 남짓, 1 분)
    manage.py fetch_kopri --only kpdc       KPDC·운석 목록과 새 상세만
    manage.py fetch_kopri --refresh         상세를 다 다시 받는다 (두 시간 남짓)

**천천히 간다** — 쪽마다 2 초 쉰다(devlog 010). 처음에는 상세 3 500 쪽이라 두 시간쯤 걸리고,
다음부터는 목록 여덟 장과 새로 올라온 상세만 받는다. 상세는 25 쪽마다 파일에 적어 두어
중간에 멈춰도 받은 것은 남는다. 목록에서 사라진 자료는 파일에서도 뺀다.
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from viewer import kopri

#: KPDC 의 묶음 — 과학 자료와 운석. 암석(`Rock`)은 암석 DB 가 더 자세해 그쪽에서 받는다
COLLECTIONS = ("KPDC", "KoreaMet")
SAVE_EVERY = 25


class Command(BaseCommand):
    help = "극지연구소의 암석 시료·KPDC 자료 목록을 천천히 모아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=("rock", "kpdc"), help="이것만 받는다")
        parser.add_argument("--refresh", action="store_true", help="받아 둔 상세도 다시 받는다")
        parser.add_argument("--limit", type=int, default=0, help="상세를 이만큼만 받는다 (시험용)")
        parser.add_argument("--pause", type=float, default=kopri.PAUSE, help="쪽 사이에 쉬는 초")

    def handle(self, *args, **options):
        say = self.stdout.write
        pause = max(options["pause"], 1.0)          # 1 초보다 빨리 두드리지 않는다
        if options["only"] in (None, "rock"):
            rows = kopri.harvest_rock(pause=pause, say=say)
            kopri.save("rock", {"harvested": timezone.now().isoformat(timespec="seconds"),
                                "source": kopri.ROCK_HOME, "rows": rows})
            say(self.style.SUCCESS(f"암석 시료 {len(rows)} 건"))
        if options["only"] in (None, "kpdc"):
            if options["only"] is None:
                time.sleep(pause)
            self.kpdc(pause, options["refresh"], options["limit"], say)

    def kpdc(self, pause, refresh, limit, say):
        data = kopri.load("kpdc") or {}
        records = data.get("records") or {}
        listed = {}
        for index, collection in enumerate(COLLECTIONS):
            if index:
                time.sleep(pause)
            for row in kopri.list_collection(collection, pause=pause, say=say):
                listed[row["uuid"]] = dict(row, c=collection)
        gone = [uuid for uuid in records if uuid not in listed]
        for uuid in gone:
            del records[uuid]
        todo = [uuid for uuid in listed if refresh or "shapes" not in records.get(uuid, {})]
        if limit:
            todo = todo[:limit]
        say(f"목록 {len(listed)} 건 (빠진 것 {len(gone)}), 상세를 받을 것 {len(todo)} 건 — "
            f"{len(todo) * pause / 60:.0f} 분 남짓")
        # 목록의 제목·번호는 늘 새것으로 — 상세를 다시 받지 않아도 고친 제목은 따라간다
        for uuid, row in listed.items():
            records[uuid] = dict(records.get(uuid, {}), **row)
        failed = 0
        for index, uuid in enumerate(todo, 1):
            time.sleep(pause)
            try:
                detail = kopri.fetch_detail(uuid)
            except kopri.KopriError as exc:
                failed += 1
                say(self.style.WARNING(f"{uuid}: {exc}"))
                if failed >= 10 and failed * 2 > index:
                    say(self.style.ERROR("실패가 많아 멈춘다 — 받은 것까지 적어 둔다"))
                    break
                continue
            records[uuid].update(detail, fetched=timezone.now().date().isoformat())
            if index % SAVE_EVERY == 0:
                self.write(records)
                say(f"  {index}/{len(todo)}")
        self.write(records)
        with_shape = sum(1 for r in records.values() if r.get("shapes"))
        say(self.style.SUCCESS(f"KPDC {len(records)} 건, 위치가 있는 것 {with_shape} 건, 실패 {failed}"))

    @staticmethod
    def write(records):
        kopri.save("kpdc", {"harvested": timezone.now().isoformat(timespec="seconds"),
                            "source": kopri.KPDC_HOME, "records": records})
