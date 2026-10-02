"""좌표 읽기·쓰기.

`coords` 는 import 가 없어 Django 를 세우지 않고도 돈다. 그래서 여기 시험이
가장 싸고, 가장 자주 깨질 자리이기도 하다 — 사람이 찍어 넣는 꼴이 제각각이다.
"""
from django.test import SimpleTestCase

from viewer import coords


class DdToDms(SimpleTestCase):
    def test_북반구_동경(self):
        self.assertEqual(coords.dd_to_dms(37.5665, True), "37°33'59.4\"N")
        self.assertEqual(coords.dd_to_dms(126.9780, False), "126°58'40.8\"E")

    def test_남반구_서경(self):
        self.assertEqual(coords.dd_to_dms(-37.5, True), "37°30'00.0\"S")
        self.assertEqual(coords.dd_to_dms(-126.5, False), "126°30'00.0\"W")

    def test_초가_60으로_반올림되면_분을_올린다(self):
        # 59'59.97" 는 60.0 으로 반올림된다. 59'60.0" 이 뜨면 안 된다.
        got = coords.dd_to_dms(37 + 59 / 60 + 59.97 / 3600, True)
        self.assertEqual(got, "38°00'00.0\"N")

    def test_영도(self):
        self.assertEqual(coords.dd_to_dms(0.0, True), "0°00'00.0\"N")


class FormatPair(SimpleTestCase):
    def test_위도가_앞에_온다(self):
        # 넘길 때는 lon, lat 이지만 보일 때는 위도가 앞이다
        self.assertEqual(coords.format_pair(126.978, 37.5665), "37.566500, 126.978000")

    def test_도분초(self):
        self.assertEqual(coords.format_pair(126.978, 37.5665, dms=True),
                         "37°33'59.4\"N 126°58'40.8\"E")


class Parse(SimpleTestCase):
    def test_십진도_쉼표(self):
        self.assertEqual(coords.parse("37.5665, 126.978"), (37.5665, 126.978))

    def test_십진도_빈칸(self):
        self.assertEqual(coords.parse("37.5665 126.978"), (37.5665, 126.978))

    def test_도분초_뒤에_반구(self):
        lat, lon = coords.parse("37°30'15.2\"N 127°00'30.1\"E")
        self.assertAlmostEqual(lat, 37.504222, places=5)
        self.assertAlmostEqual(lon, 127.008361, places=5)

    def test_도분초_앞에_반구(self):
        lat, lon = coords.parse("N37 30 15.2 E127 00 30.1")
        self.assertAlmostEqual(lat, 37.504222, places=5)
        self.assertAlmostEqual(lon, 127.008361, places=5)

    def test_남반구_서경은_음수가_된다(self):
        lat, lon = coords.parse("S37 30 00 W127 00 00")
        self.assertAlmostEqual(lat, -37.5, places=6)
        self.assertAlmostEqual(lon, -127.0, places=6)

    def test_범위를_벗어나면_못_읽은_것이다(self):
        self.assertIsNone(coords.parse("137.5, 126.9"))     # 위도가 90 을 넘는다
        self.assertIsNone(coords.parse("37.5, 226.9"))      # 경도가 180 을 넘는다

    def test_좌표가_아니면_None(self):
        for text in ("", "   ", "여기 어디쯤", "37.5"):
            self.assertIsNone(coords.parse(text), text)
