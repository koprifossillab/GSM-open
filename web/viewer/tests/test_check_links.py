"""출처 링크 점검 스크립트(`deploy/check_links.py`, wetherilli 339) — 링크를 긁는 쪽만. 망을 타지 않는다."""
import importlib.util
import pathlib

from django.test import SimpleTestCase

ROOT = pathlib.Path(__file__).resolve().parents[3]


def load():
    spec = importlib.util.spec_from_file_location("check_links", ROOT / "deploy" / "check_links.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckLinks(SimpleTestCase):
    def test_출처의_링크를_긁는다(self):
        found = load().links()
        self.assertIn("https://www.bgs.ac.uk/geology-projects/gsni/", found)          # 북아일랜드 GSNI — 옛 주소는 404 였다
        self.assertIn("https://www.geologischedienst.nl/", found)                    # TNO 지질조사부 — 옛 주소는 404 였다
        self.assertFalse([u for u in found if "{" in u or "localhost" in u])
        self.assertNotIn("https://www.economy-ni.gov.uk/topics/geological-survey-northern-ireland", found)

    def test_갈래(self):
        kind = load().kind
        self.assertEqual([kind(200), kind(301), kind(403), kind(404), kind("URLError")],
                         ["살아 있다", "살아 있다", "사람만", "깨졌다", "닿지 않는다"])
