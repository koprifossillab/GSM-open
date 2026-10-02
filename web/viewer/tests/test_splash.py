"""대기 화면(스플래시)에 판 번호가 뜬다 — 지도·온 지구·달·화성 (koprifossillab 017)."""
from django.test import TestCase

from gsmweb.version import VERSION


class SplashVersionTests(TestCase):
    def test_every_screen_shows_version(self):
        for url in ("/GSM/map/", "/GSM/earth/", "/GSM/moon/", "/GSM/mars/", "/GSM/mercury/"):
            with self.subTest(url=url):
                page = self.client.get(url).content.decode()
                self.assertIn(f'<p class="splash-ver">v{VERSION}</p>', page)
