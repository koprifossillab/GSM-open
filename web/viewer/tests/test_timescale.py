"""온 지구 시간 축의 지질시대 띠 — ICS 표 (wetherilli 373)."""
from django.test import SimpleTestCase

from viewer import timescale


class TimescaleTests(SimpleTestCase):
    def spans(self, rank, lang="ko"):
        return [u for u in timescale.units(lang) if u["rank"] == rank]

    def assertSeamless(self, rank, oldest, youngest=0):
        rows = self.spans(rank)
        self.assertLessEqual(oldest, rows[0]["b"], rank)
        self.assertEqual(rows[-1]["t"], youngest, rank)
        for older, younger in zip(rows, rows[1:]):
            self.assertEqual(older["t"], younger["b"], f"{older['name']} / {younger['name']} 사이가 벌어졌다")

    def test_누대_대_기는_막대_끝까지_빈틈이_없다(self):
        for rank in ("eon", "era", "period"):
            self.assertSeamless(rank, 1100)

    def test_세는_현생누대를_절은_제4기를_빈틈없이_덮는다(self):
        self.assertSeamless("epoch", 538.8)
        self.assertSeamless("stage", 2.58)

    def test_색은_여섯_자리_16진수(self):
        for u in timescale.units():
            self.assertRegex(u["color"], r"^#[0-9A-Fa-f]{6}$", u["name"])

    def test_영어판은_영어_이름(self):
        names = {u["name"] for u in timescale.units("en")}
        self.assertIn("Triassic", names)
        self.assertIn("Chibanian", names)
        self.assertFalse([n for n in names if any("가" <= c <= "힣" for c in n)])
