"""온 지구 화면의 레이어 패널 — 주제로 묶은 레이어군 (wetherilli 278). 지은 레이어가 모두 주제 표(`THEMES`)에 적혔는지 본다.
적지 않아도 "그 밖" 에 서서 사라지지는 않지만, 새 레이어를 더할 때 주제를 잊지 않게 지킨다."""
import re
from pathlib import Path

from django.test import SimpleTestCase

from viewer import i18n, views

JS = (Path(views.__file__).parent / "static/viewer/earth.js").read_text(encoding="utf-8")


def themes() -> list:
    block = JS[JS.index("var THEMES = ["):]
    block = block[:block.index("\n  ];")]
    return [(name, re.findall(r'"([a-z0-9]+)"', keys)) for name, keys in re.findall(r'\["([^"]+)", \[([^\]]*)\]\]', block)]


def defined_layers() -> set:
    """CATALOG 와 그 뒤에 덧붙인 레이어의 이름 — 고생태 산지의 자료형 칸(`row.band`)은 이름이 자료에서 와 빠진다"""
    block = JS[JS.index("var CATALOG = ["):JS.index("// ── 레이어군을 주제로 묶는다")]
    return set(re.findall(r'\{ name: "([a-z0-9]+)", title:', block))


class EarthPanel(SimpleTestCase):
    def test_지은_레이어는_모두_주제에(self):
        listed = [n for _, names in themes() for n in names]
        self.assertEqual(len(listed), len(set(listed)))                              # 두 주제에 서지 않는다
        self.assertEqual(sorted(defined_layers() - set(listed)), [], "주제 표에 적지 않은 레이어")
        self.assertEqual(sorted(set(listed) - defined_layers()), [], "없는 레이어를 적었다")

    def test_주제_이름은_영어도(self):
        for name, _ in themes() + [("그 밖", [])]:
            self.assertIn(name, i18n.EN, name)
