"""뷰·화면(JS)이 직접 짓는 팝업 속성 이름도 영어가 있다 (wetherilli 364).

문들의 `friendly()` 가 내는 이름은 `test_prop_en`(wetherilli 359)이 지킨다. 여기는 그 밖 — `views.py` 가 줄을 지으며 적는 이름과
화면 JS 가 속성 객체에 적는 이름이다. 둘 다 영어판에서 `PROP_EN`(서버) 또는 `T()`(화면 — 표는 `EN` 과 `PROP_EN` 을 합친 것,
`i18n.client_table`)로 옮겨진다. 표에 없으면 영어판 팝업에 한국어가 남는다.

긁는 법은 셋이다. 놓치는 꼴이 있을 수 있어, 찾은 수가 너무 적으면(긁는 법이 깨졌으면) 따로 깨진다.
- `views.py`(AST) — 둘짜리 줄(`["이름", 값]`·`("이름", 값)`)의 앞, 사전의 한국어 열쇠, `PROP_EN.get("이름", …)` 의 첫 인자
- 화면 JS — `obj["이름"] = …`, 객체의 `"이름": …`, 둘짜리 배열 `["이름", 값]`(뒤가 글자열인 짝 — `["임브리움기", "Imbrian"]` 같은 옮김 표 — 은 뺀다)
"""
import ast
import re
from pathlib import Path

from django.test import SimpleTestCase

from viewer import i18n

VIEWER = Path(__file__).resolve().parents[1]
KOREAN = re.compile(r"[가-힣]")
JS_PATTERNS = (
    re.compile(r'\[\s*"([가-힣][^"\n]{0,40})"\s*\]\s*=(?!=)'),
    re.compile(r'[{,]\s*"([가-힣][^"\n]{0,40})"\s*:'),
    re.compile(r'\[\s*"([가-힣][^"\n]{0,40})"\s*,\s*+(?!")'),
)


def _korean(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(KOREAN.search(node.value))


def view_names() -> dict:
    """`views.py` 가 적는 한국어 이름 → 줄 번호"""
    tree = ast.parse((VIEWER / "views.py").read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2 and _korean(node.elts[0]):
            found.setdefault(node.elts[0].value, node.lineno)
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None and _korean(key):
                    found.setdefault(key.value, node.lineno)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "PROP_EN"
              and node.args and _korean(node.args[0])):
            found.setdefault(node.args[0].value, node.lineno)
    return found


def screen_names() -> dict:
    """화면 JS 가 적는 한국어 이름 → (파일, 줄)"""
    found = {}
    for path in sorted((VIEWER / "static/viewer").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for pattern in JS_PATTERNS:
            for m in pattern.finditer(text):
                found.setdefault(m.group(1), (path.name, text.count("\n", 0, m.start()) + 1))
    return found


class ScreenPropNames(SimpleTestCase):
    known = {**i18n.EN, **i18n.PROP_EN}

    def test_긁는_법이_이름을_찾는다(self):
        # 2026-10-05 에 views.py 65·JS 60 남짓이었다. 크게 줄면 긁는 법이 깨진 것이다
        self.assertGreater(len(view_names()), 40)
        self.assertGreater(len(screen_names()), 40)

    def test_뷰가_짓는_이름은_영어가_있다(self):
        missing = {name: line for name, line in view_names().items() if name not in self.known}
        self.assertEqual(missing, {}, "views.py 의 이 이름들을 i18n.PROP_EN 에 더한다 (이름: 줄)")

    def test_화면이_짓는_이름은_영어가_있다(self):
        missing = {name: where for name, where in screen_names().items() if name not in self.known}
        self.assertEqual(missing, {}, "화면 JS 의 이 이름들을 i18n.PROP_EN(또는 EN)에 더한다 (이름: 파일·줄)")

    def test_옮김_표의_짝은_이름으로_치지_않는다(self):
        self.assertNotIn("임브리움기", screen_names())           # 달 시대의 한·영 짝 — 이름이 아니다
