"""팝업 속성 이름의 영어 — 문마다의 `friendly` 가 짓는 한국어 이름이 `PROP_EN` 에 있는지 (wetherilli 359).

`test_i18n` 은 `T()`·`msg()` 로 감싼 화면 문장을 지킨다. 속성 이름은 감싸지 않고 `friendly` 의 `rows` 짝(`("암석", v("LITH"))`)이나
dict 열쇠로 적혀 `props_en` 이 표에서 찾는다 — 표에 없으면 영어판 팝업에 한국어가 그대로 뜬다(008 이 "보이면 더한다" 로 미뤄 두었던 것).
코드를 긁어 빠진 것을 잡는다. 상류가 준 값(지층명 따위)은 옮기지 않으니 보지 않는다.
"""
import ast
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from viewer import i18n

HANGUL = re.compile(r"[가-힣]")
NAME_TABLE = re.compile(r"FRIENDLY|LABEL|COLUMN|FIELD|NAMES|PROPS")


def friendly_names():
    """viewer/*.py 의 이름에 friendly 가 든 함수 안 — 두 칸 짝의 첫 칸과 dict 열쇠, 그리고 그 함수가 부르는 모듈 수준 표(열 이름 → 한국어 이름)의
    값 가운데 한글이 든 것 → 자리"""
    found = {}
    for path in sorted((Path(settings.BASE_DIR) / "viewer").glob("*.py")):
        if path.name == "i18n.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # 열 이름 표만 — 이름이 그렇게 생긴 것. 값 표(`PROVINCE_KINDS` 처럼 한국어 갈래 이름을 값으로 내고 영어판은 따로 고르는 것)는 넣지 않는다
        tables = {t.id: node.value for node in tree.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                  for t in node.targets if isinstance(t, ast.Name) and NAME_TABLE.search(t.id)}
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or "friendly" not in fn.name:
                continue
            used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id in tables}
            for name in used:
                for value in tables[name].values:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and HANGUL.search(value.value):
                        found.setdefault(value.value, f"{path.name}:{value.lineno} {name}")
            for node in ast.walk(fn):
                keys = []
                if isinstance(node, ast.Tuple) and len(node.elts) == 2:
                    keys.append(node.elts[0])
                elif isinstance(node, ast.Dict):
                    keys.extend(k for k in node.keys if k is not None)
                for key in keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str) and HANGUL.search(key.value):
                        found.setdefault(key.value, f"{path.name}:{node.lineno} {fn.name}")
    return found


class PropEn(SimpleTestCase):
    def test_friendly_의_속성_이름은_영어가_있다(self):
        names = friendly_names()
        self.assertGreater(len(names), 200)         # 긁기가 헛돌지 않는지 — 2026-10-05 에 227
        missing = {name: where for name, where in names.items() if name not in i18n.PROP_EN}
        self.assertEqual(missing, {}, "i18n.PROP_EN 에 더한다")

    def test_영어판_팝업에_한글이_남지_않는다(self):
        props = {name: "x" for name in friendly_names()}
        left = [k for k in i18n.props_en(props) if HANGUL.search(k) and not k.endswith("(Korean)")]
        self.assertEqual(left, [])
