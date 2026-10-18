"""스타일 파일의 꼴 (wetherilli 395).

`map.css` 에서 아프리카 밝은 테마의 `}` 가 빠져(wetherilli 207) 그 뒤의 규칙이 모두 그 안에 갇혔다 — 브라우저는 CSS 중첩으로 읽어
아무것에도 걸리지 않는다. 오류가 뜨지 않아 반년 가까이 몰랐다. 주석을 뗀 중괄호의 짝만 본다.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

STATIC = Path(__file__).resolve().parents[1] / "static" / "viewer"


class BracesTest(SimpleTestCase):
    def test_중괄호의_짝(self):
        for path in sorted(STATIC.glob("*.css")):
            with self.subTest(css=path.name):
                text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group().count("\n"), path.read_text(), flags=re.S)
                depth, line_of = 0, []
                for no, line in enumerate(text.split("\n"), 1):
                    for ch in line:
                        if ch == "{":
                            line_of.append(no)
                        elif ch == "}":
                            self.assertTrue(line_of, f"{path.name}:{no} 짝 없는 }}")
                            line_of.pop()
                self.assertEqual(line_of, [], f"{path.name}: 닫히지 않은 {{ — 줄 {line_of}")
