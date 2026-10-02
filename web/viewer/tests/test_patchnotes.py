"""`CHANGELOG.md` 를 화면이 쓸 꼴로 읽는 자리를 시험한다.

마크다운 라이브러리를 들이지 않고 정규식 하나로 끝냈으므로, **문서의 꼴이
조금 어긋나도 견디는지**가 여기서 볼 것이다. 날짜가 빠진 머리, 목록 뒤에
들여쓴 이어짐 줄, 머리가 하나도 없는 글 — 셋 다 실제로 쓰다 보면 생긴다.

마지막 하나는 저장소에 든 진짜 `CHANGELOG.md` 를 읽는다. 시험용 글만
읽어서는 정작 화면에 뜰 문서가 어긋난 것을 못 잡는다.
"""
from pathlib import Path

from django.test import SimpleTestCase

from viewer import patchnotes

CHANGELOG = Path(patchnotes.__file__).resolve().parents[2] / "CHANGELOG.md"


class 판머리(SimpleTestCase):
    def test_판_날짜_제목을_갈라낸다(self):
        notes = patchnotes.parse("## v0.1.0 — 2026-09-23 · 뼈대\n")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["version"], "v0.1.0")
        self.assertEqual(notes[0]["date"], "2026-09-23")
        self.assertEqual(notes[0]["title"], "뼈대")

    def test_날짜와_제목이_없어도_견딘다(self):
        notes = patchnotes.parse("## v0.2.0\n")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["version"], "v0.2.0")
        self.assertEqual(notes[0]["date"], "")
        self.assertEqual(notes[0]["title"], "")

    def test_날짜만_있는_머리(self):
        notes = patchnotes.parse("## v0.3.0 — 2026-10-01\n")
        self.assertEqual(notes[0]["date"], "2026-10-01")
        self.assertEqual(notes[0]["title"], "")

    def test_제목만_있는_머리(self):
        notes = patchnotes.parse("## v0.4.0 · 손질\n")
        self.assertEqual(notes[0]["date"], "")
        self.assertEqual(notes[0]["title"], "손질")


class 줄글과_목록(SimpleTestCase):
    def test_머리_다음의_줄글은_lead_로_간다(self):
        notes = patchnotes.parse(
            "## v0.1.0 — 2026-09-23 · 뼈대\n"
            "\n"
            "첫 판. 아직 인증키가 없다.\n")
        self.assertEqual(notes[0]["lead"], "첫 판. 아직 인증키가 없다.")
        self.assertEqual(notes[0]["items"], [])

    def test_줄글이_여러_줄이면_한_줄로_이어진다(self):
        notes = patchnotes.parse(
            "## v0.1.0\n"
            "\n"
            "첫 판이다.\n"
            "아직 인증키가 없다.\n")
        self.assertEqual(notes[0]["lead"], "첫 판이다. 아직 인증키가 없다.")

    def test_줄표로_시작하는_줄이_items_가_된다(self):
        notes = patchnotes.parse(
            "## v0.1.0\n"
            "\n"
            "- 뼈대를 세웠다 (001)\n"
            "- 레이어 패널을 붙였다\n")
        self.assertEqual(notes[0]["items"],
                         ["뼈대를 세웠다 (001)", "레이어 패널을 붙였다"])

    def test_들여쓴_이어짐_줄은_앞_항목에_붙는다(self):
        notes = patchnotes.parse(
            "## v0.1.0\n"
            "\n"
            "- 배경지도를 고르게 했다 (003).\n"
            "  VWorld 열쇠를 넣으면 둘이 고르개에 오른다\n"
            "- 배포 뼈대\n")
        self.assertEqual(notes[0]["items"], [
            "배경지도를 고르게 했다 (003). VWorld 열쇠를 넣으면 둘이 고르개에 오른다",
            "배포 뼈대",
        ])

    def test_목록이_시작된_뒤의_줄은_lead_로_가지_않는다(self):
        notes = patchnotes.parse(
            "## v0.1.0\n"
            "\n"
            "첫 판이다.\n"
            "\n"
            "- 뼈대를 세웠다\n"
            "이어지는 말\n")
        self.assertEqual(notes[0]["lead"], "첫 판이다.")
        self.assertEqual(notes[0]["items"], ["뼈대를 세웠다 이어지는 말"])


class 여러_판(SimpleTestCase):
    def test_판이_여럿이면_차례대로_나온다(self):
        notes = patchnotes.parse(
            "# 판 이력\n"
            "\n"
            "- 머리보다 앞선 줄은 어느 판에도 들지 않는다\n"
            "\n"
            "## v0.2.0 — 2026-10-01 · 손질\n"
            "\n"
            "- 두 번째 판\n"
            "\n"
            "## v0.1.0 — 2026-09-23 · 뼈대\n"
            "\n"
            "첫 판.\n"
            "\n"
            "- 첫 판의 일\n")
        self.assertEqual([n["version"] for n in notes], ["v0.2.0", "v0.1.0"])
        self.assertEqual(notes[0]["items"], ["두 번째 판"])
        self.assertEqual(notes[1]["lead"], "첫 판.")
        self.assertEqual(notes[1]["items"], ["첫 판의 일"])


class 빈_글(SimpleTestCase):
    def test_빈_문자열은_빈_목록이다(self):
        self.assertEqual(patchnotes.parse(""), [])

    def test_머리가_하나도_없으면_빈_목록이다(self):
        self.assertEqual(patchnotes.parse(
            "# 판 이력\n\n무엇을 적어도 판이 아니다.\n\n- 목록도 마찬가지다\n"), [])


class 실제_문서(SimpleTestCase):
    def test_저장소의_changelog_를_읽는다(self):
        self.assertTrue(CHANGELOG.exists(), f"{CHANGELOG} 가 없다")
        notes = patchnotes.parse(CHANGELOG.read_text(encoding="utf-8"))
        self.assertTrue(notes, "판이 하나도 나오지 않았다")
        self.assertIn("v0.1.0", [n["version"] for n in notes])
        for note in notes:
            self.assertTrue(note["lead"] or note["items"],
                            f"{note['version']} 에 적힌 것이 없다")
