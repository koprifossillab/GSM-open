"""소개 화면과 지도의 새 주소 (wetherilli 113).

뿌리(`/GSM/`)는 늘 소개이고 지도는 `map/` 이다. 지도에서 다른 갈래로 가는 주소가 `map/` 밑으로
새지 않는지, 소개가 부르는 그림이 두 언어 모두 있는지 본다.
"""
import re
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

HERE = Path(__file__).resolve().parent.parent
SHOTS = HERE / "static" / "viewer" / "intro"


class IntroTests(TestCase):
    def get(self, name, lang="ko"):
        self.client.cookies["gsm_lang"] = lang
        response = self.client.get(reverse(name))
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_뿌리는_소개다(self):
        self.assertEqual(reverse("viewer:intro"), "/GSM/")
        self.assertEqual(reverse("viewer:map"), "/GSM/map/")
        html = self.get("viewer:intro")
        self.assertIn("intro.js", html)
        self.assertIn('id="skip"', html)
        # 건너뛰기 단추와 갈래 단추는 지도의 새 주소로 간다
        self.assertIn('href="/GSM/map/?region=korea"', html)
        self.assertIn('href="/GSM/map/?region=antarctica"', html)
        self.assertIn('href="/GSM/3d/"', html)

    def test_지도의_갈래는_뿌리_밑이다(self):
        html = self.get("viewer:map")
        for target in ("earth/", "moon/", "mars/", "mercury/", "3d/"):
            self.assertIn(f'href="/GSM/{target}"', html)
        self.assertNotIn('href="/GSM/map/earth/"', html)
        # 숨은 차림에서 소개로 돌아간다
        self.assertIn('class="intro-link" href="/GSM/"', html)

    def test_달_화성_온지구에서_지구는_지도로(self):
        for name in ("viewer:moon", "viewer:mars", "viewer:mercury", "viewer:earth"):
            html = self.get(name)
            self.assertIn('href="/GSM/map/"', html, name)

    def test_영어판(self):
        html = self.get("viewer:intro", "en")
        self.assertIn('<html lang="en">', html)
        self.assertIn("<title>Great Stone Map</title>", html)
        self.assertIn("Go to the map", html)
        self.assertIn("/static/viewer/intro/en/", html)
        self.assertNotIn("/static/viewer/intro/ko/", html)

    def test_그림이_두_언어_모두_있다(self):
        html = (HERE / "templates" / "viewer" / "intro.html").read_text(encoding="utf-8")
        names = set(re.findall(r"shots\|add:'([\w.]+)'", html))
        self.assertTrue(names)
        for lang in ("ko", "en"):
            for name in names:
                self.assertTrue((SHOTS / lang / name).is_file(), f"{lang}/{name}")

    def test_작은_판과_구와_로고가_있다(self):
        """첫 장면에 쏟아지는 수십 장·갈래 단추는 작은 판(thumb/)을, 구는 감는 그림을 쓴다 (wetherilli 115)."""
        html = (HERE / "templates" / "viewer" / "intro.html").read_text(encoding="utf-8")
        thumbs = set(re.findall(r"shots\|add:'thumb/([\w.]+)'", html))
        thumbs |= {n + ".webp" for n in re.search(r'data-names="([^"]+)"', html).group(1).split()}
        for lang in ("ko", "en"):
            for name in thumbs:
                self.assertTrue((SHOTS / lang / "thumb" / name).is_file(), f"{lang}/thumb/{name}")
        for name in ("globe-earth.webp", "globe-moon.webp", "globe-mars.webp", "globe-mercury.webp", "kopri-ci-ko.svg", "kopri-ci-en.svg"):
            self.assertTrue((SHOTS / name).is_file(), name)

    def test_극지_아이콘과_대기_화면(self):
        """극지 지역에서 지도는 극지 아이콘·대기 화면을, 소개는 극지 표지를 쓴다 (wetherilli 123)."""
        static = HERE / "static" / "viewer"
        for name in ("emblem-polar.png", "splash-polar.gif", "splash-polar.webp"):
            self.assertTrue((static / name).is_file(), name)
        html = self.get("viewer:map")
        self.assertIn('data-emblem-polar="/GSM/static/viewer/emblem-polar.png?v=', html)       # 판이 붙는다 (wetherilli 345)
        self.assertIn("splash-polar.gif", html)
        self.assertIn('id="favicon"', html)
        intro = self.get("viewer:intro")
        self.assertIn('id="polartitle"', intro)
        self.assertIn('class="cat polar"', intro)

    def test_소스_링크는_공개용_저장소로(self):
        """AGPL 13조의 소스 길 — 개발 저장소가 아니라 판마다 사본을 미는 GSM-open (wetherilli 149)."""
        intro = self.get("viewer:intro")
        self.assertIn('href="https://github.com/koprifossillab/GSM-open"', intro)
        self.assertNotIn('href="https://github.com/koprifossillab/GSM"', intro)


class OtherRegions(TestCase):
    """지역 칩에 이름이 없는 지역의 수 (wetherilli 344) — 서버 판에만"""
    def test_수를_센다(self):
        from django.core.management import call_command
        from viewer import views
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        n = views._intro_other_regions()
        self.assertGreater(n, 30)
        html = self.client.get("/GSM/").content.decode()
        self.assertIn(f"그 밖의 {n} 지역", html)
        self.assertIn(f"{n} more regions", self.client.get("/GSM/", HTTP_ACCEPT_LANGUAGE="en").content.decode())
