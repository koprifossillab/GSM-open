"""KIGAM 오픈플랫폼의 자료(`/openapi/data`)를 모은다 — 목록과 상세, 그리고 행정구역만 적힌 자료의 자리 (wetherilli 169).

    manage.py fetch_kigam_data              처음은 한 시간 20 분 남짓(목록 35 쪽 + 상세 3 450 건, 1 초 쉬고 하나씩). 다음부터는 바뀐 것만
    manage.py fetch_kigam_data --places     상세는 받지 않고, 행정구역만 적힌 자료의 자리를 VWorld 로 찾는다(찾은 것은 담아 둔다)

지도에 무엇을 올릴지는 아직 정하지 않았다(이슈 #153) — 이 명령은 모으기만 한다.

**천천히 간다** — 1 초에 한 번, 차단 조짐이면 멈춘다. 호출 제한을 재려고 두드리지 않는다(CLAUDE.md "받아온 것의 순위").
멈춰도 받은 것은 남는다(50 건마다 적는다) — 다시 부르면 이어 간다. 운영에서는 tmux 에서 돌린다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import kigam, kigamdata, vworld


class Command(BaseCommand):
    help = "KIGAM 자료 목록·상세를 모은다 → <KIGAM_DATA_DIR>/data.json (wetherilli 169)"

    def add_arguments(self, parser):
        parser.add_argument("--places", action="store_true", help="상세는 받지 않고 행정구역의 자리만 찾는다")
        parser.add_argument("--limit", type=int, help="상세를 이만큼만 (시험·맛보기)")
        parser.add_argument("--pause", type=float, default=1.0, help="물음 사이 초 (기본 1)")

    def handle(self, *args, **opts):
        if opts["pause"] < 1.0:
            raise CommandError("1 초보다 잦게 묻지 않는다")
        if not opts["places"]:
            self.stdout.write("KIGAM 자료 API 에서 받는다 …")
            try:
                got = kigamdata.harvest(log=self.stdout.write, pause=opts["pause"], limit=opts["limit"])
            except kigam.UpstreamError as exc:
                raise CommandError(f"멈췄다 — 받은 것은 남았다: {exc}") from exc
            self.stdout.write(f"목록 {got['listed']:,} · 상세 {got['fetched']:,} · 없어진 것 {got['gone']}")
            return
        data, places = kigamdata.load(), kigamdata.load(kigamdata.PLACES_FILE)
        texts = sorted({kigamdata.admin_text(i) for i in (data.get("items") or {}).values()
                        if not kigamdata.section(i, "위치정보").get("좌표")} - {""} - set(places))
        self.stdout.write(f"행정구역만 적힌 곳 {len(texts):,} 곳을 찾는다 (VWorld)")
        for n, text in enumerate(texts, 1):
            kigamdata.locate(places, text, vworld.geocode, log=self.stdout.write)
            if n % 20 == 0:
                kigamdata.save(places, kigamdata.PLACES_FILE)
        kigamdata.save(places, kigamdata.PLACES_FILE)
        self.stdout.write(f"자리 {sum(1 for v in places.values() if v):,} / {len(places):,} 곳")
