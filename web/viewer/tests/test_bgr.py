"""독일 BGR 의 GK2000 (wetherilli 327)."""
from django.test import SimpleTestCase

from viewer import bgr, i18n


class Gk2000(SimpleTestCase):
    """GK2000(1:200만) — 줌 9 앞의 축척 (wetherilli 327)"""
    def test_판과_속성(self):
        self.assertEqual(bgr.split("bgr:gk2000:0"), ("gk2000", "0"))
        self.assertEqual(bgr.ZOOMS["gk2000"], (None, 10))
        self.assertFalse(bgr.queryable("bgr:gk2000:2"))
        self.assertEqual(bgr.friendly({"OBJECTID": "2744", "Geologie": "Obertrias"}), {"지질시대": i18n.age_ko("Late Triassic")})
        self.assertEqual(bgr.friendly({"Geologie": "Obertrias"}, "en"), {"지질시대": "Late Triassic"})
