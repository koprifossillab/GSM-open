"""'그 외' 차림의 대륙 머리 (wetherilli 268) — 맨 위의 지역(묶음, 또는 어느 묶음에도 들지 않는 지역)이 모두 대륙 하나에 적혔는지 본다.
적지 않아도 '그 밖' 에 서서 사라지지는 않지만, 새 지역을 더할 때 대륙을 잊지 않게 지킨다."""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from viewer import views

JS = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")


def regions() -> dict:
    """REGIONS 의 열쇠 → 딸린 지역(includes)"""
    body = JS[JS.index("var REGIONS = {"):]
    body = body[:body.index("\n  };")]
    keys = re.findall(r"^    ([a-z_]+): \{", body, re.M)
    out = {}
    for n, key in enumerate(keys):
        start = body.index(f"\n    {key}: {{")
        end = body.index(f"\n    {keys[n + 1]}: {{") if n + 1 < len(keys) else len(body)
        inc = re.search(r"includes: \[([^\]]*)\]", body[start:end])
        out[key] = re.findall(r'"([a-z_]+)"', inc.group(1)) if inc else []
    return out


def continents() -> list:
    block = JS[JS.index("var CONTINENTS = ["):]
    block = block[:block.index("\n  ];")]
    return [(name, re.findall(r'"([a-z_]+)"', keys)) for name, keys in re.findall(r'\["([^"]+)", \[([^\]]*)\]\]', block)]


class RegionMenu(SimpleTestCase):
    def test_맨_위의_지역은_모두_대륙에(self):
        regs = regions()
        children = {c for kids in regs.values() for c in kids}
        tops = {k for k in regs if k not in children}
        listed = [k for _, keys in continents() for k in keys]
        self.assertEqual(len(listed), len(set(listed)))                     # 두 대륙에 서지 않는다
        self.assertEqual(sorted(tops - set(listed)), [], "대륙에 적지 않은 맨 위의 지역")
        self.assertEqual(sorted(set(listed) - set(regs)), [], "없는 지역을 적었다")
        self.assertEqual(sorted(set(listed) & children), [], "묶음에 딸린 지역은 그 묶음 밑에 선다")

    def test_대륙_이름은_영어도(self):
        from viewer import i18n
        for name, _ in continents() + [("그 밖", [])]:
            self.assertIn(name, i18n.EN, name)
