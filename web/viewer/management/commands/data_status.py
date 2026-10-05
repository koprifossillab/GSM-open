"""구운 자료의 나이 — `<DB 옆>` 아래 파일마다 있는지·크기·만든 날·원본 판 (wetherilli 312).

    manage.py data_status              # 표
    manage.py data_status --missing    # 있어야 하는데 없는 것만

읽기만 한다. 표는 `datastatus.ITEMS` 다 — 새로 굽는 파일을 더하면 거기 한 줄 더한다.
"""
from django.core.management.base import BaseCommand

from viewer import datastatus
from viewer.i18n import t


class Command(BaseCommand):
    help = "구운 자료(<DB 옆>)마다 있는지·크기·만든 날·원본 판을 한 표로"

    def add_arguments(self, parser):
        parser.add_argument("--missing", action="store_true", help="있어야 하는데 없는 것만")

    def handle(self, *args, **o):
        table = datastatus.rows()
        shown = [r for r in table if r["needed"] and not r["exists"]] if o["missing"] else table
        self.stdout.write("| 파일 | 무엇 | 크기 | 고친 날 | 원본 판 | 만드는 명령 |\n|---|---|---:|---|---|---|")
        for r in shown:
            if not r["exists"]:
                state = "**없다**" if r["needed"] else "없다(밖에 연 판)"
                self.stdout.write(f"| {r['key']} | {t(r['what'])} | {state} | | | `{r['command']}` |")
                continue
            size = datastatus.human_size(r["size"]) if r["size"] is not None else f"{r['count']} 칸"
            self.stdout.write(f"| {r['key']} | {t(r['what'])} | {size} | {r['modified']:%Y-%m-%d} | {r['version']} | `{r['command']}` |")
        lost = datastatus.missing(table)
        style = self.style.WARNING if lost else self.style.SUCCESS
        self.stdout.write(style(f"\n{len(table)} 가운데 있는 것 {sum(r['exists'] for r in table)}, 있어야 하는데 없는 것 {len(lost)}"
                                + (f" — {', '.join(lost)}" if lost else "")))
