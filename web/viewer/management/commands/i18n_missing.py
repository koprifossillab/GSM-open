"""영어판에서 아직 한국어로 남는 것을 모아 보인다.

    manage.py i18n_missing              사람이 읽는 목록
    manage.py i18n_missing --markdown   TODOs.md 에 붙일 체크 목록

화면 문장이 번역표에 빠진 것은 `test_i18n` 이 시험으로 막는다. 여기서
보이는 것은 **자료에서 오는 것** — 레이어 제목·레이어군·레이어 설명이다.
시험으로 막지 않는 까닭은 카탈로그가 상류를 따라 바뀌기 때문이다. 새
레이어가 들어온 날 시험이 깨지면 안 된다.
"""
import re

from django.core.management.base import BaseCommand

from viewer import i18n
from viewer.models import Layer, LayerGroup

KOREAN = re.compile(r"[가-힣]")


class Command(BaseCommand):
    help = "영어판에서 아직 한국어로 남는 것을 보인다"

    def add_arguments(self, parser):
        parser.add_argument("--markdown", action="store_true",
                            help="TODOs.md 에 붙일 체크 목록으로 적는다")

    def handle(self, *args, **options):
        from viewer.tests.test_i18n import used_keys
        sections = []

        ui = sorted(used_keys() - set(i18n.EN))
        sections.append(("화면 문장 (`i18n.EN`)", ui))

        groups = [g.name for g in LayerGroup.objects.all()
                  if g.name not in i18n.GROUP_EN]
        sections.append(("레이어군 이름 (`i18n.GROUP_EN`)", groups))

        layers = [f"`{l.name}` {l.title}" for l in Layer.objects.all()
                  if l.name not in i18n.LAYER_EN]
        sections.append(("레이어 제목 (`i18n.LAYER_EN`)", layers))

        abstracts = [f"`{l.name}` {l.abstract[:40]}…" for l in Layer.objects.all()
                     if l.abstract and KOREAN.search(l.abstract) and l.name not in i18n.ABSTRACT_EN]
        sections.append(("레이어 설명 (`i18n.ABSTRACT_EN`) — 없으면 영어판에서 숨긴다",
                         abstracts))

        md = options["markdown"]
        for title, items in sections:
            self.stdout.write(f"\n### {title} — {len(items)}" if md else f"\n{title}: {len(items)}")
            for item in items:
                self.stdout.write(f"- [ ] {item}" if md else f"  {item}")
