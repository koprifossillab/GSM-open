"""데이터소스 명세의 씨앗을 표(`DataSource`)에 넣는다 (jikhanjung P02, P03).

    manage.py sources_seed          비었으면 씨앗째, 차 있으면 씨앗에만 있는 id 를 덧붙인다
    manage.py sources_seed --check  옮기지 않고 견주기만 — 명세의 잘못과 코드와 어긋난 곳을 적는다

컨테이너가 뜰 때 `entrypoint-web.sh` 가 `sources_import`(파일 시절의 운영 명세를 한 번 옮긴다) 뒤에 부른다. 사람이 고친 줄은 덮지 않는다 — 씨앗과 다른 줄은 이름만 알린다.
실패해도 0 으로 끝난다 — 화면은 떠야 한다.
"""
from django.core.management.base import BaseCommand
from django.db import DatabaseError

from viewer import fetchlog, i18n, sources


class Command(BaseCommand):
    help = "데이터소스 명세의 씨앗을 표(DataSource)에 넣는다"

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="옮기지 않고 견주기만")

    def handle(self, *args, **options):
        fetchlog.refuse_on_host("sources_seed")
        say = self.stdout.write
        if not options["check"]:
            try:
                done = sources.seed()
            except (OSError, DatabaseError) as exc:
                self.stderr.write(f"데이터소스 명세를 옮기지 못했다 — 화면은 뜬다: {exc}")
                return
            if done["created"]:
                say(self.style.SUCCESS(f"데이터소스 명세를 씨앗으로 채웠다 — {len(done['added'])} 곳"))
            elif done["added"]:
                say(self.style.SUCCESS(f"씨앗에만 있던 데이터소스 {len(done['added'])} 곳을 덧붙였다: {' '.join(done['added'])}"))
            if done.get("differs"):
                say(f"씨앗과 다른 줄 {len(done['differs'])} — 덮지 않았다: {' '.join(done['differs'])}")
        spec = sources.load()
        say(f"데이터소스 {len(spec.rows)} 곳 ({spec.origin})")
        for where, found in spec.problems:
            self.stderr.write(f"  건너뜀 {where or '(파일)'}: " + "; ".join(i18n.t(m) for m in found))
        for line in sources.coverage(spec.rows):
            self.stderr.write(f"  어긋남: {line}")
