"""시험 러너가 개발 캐시·자료 자리를 빈 임시 자리로 돌리는지 (wetherilli 354)."""
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from gsmweb import testrunner
from viewer import tilecache


class Redirect(SimpleTestCase):
    def test_settings_의_자리를_빠짐없이_돌린다(self):
        # settings 에 `GSM_*_DIR` 이 새로 생기면 러너의 표에도 있어야 한다 — 없으면 시험이 그 자리의 진짜 자료를 읽거나 쓴다
        text = (Path(settings.BASE_DIR) / "gsmweb" / "settings.py").read_text(encoding="utf-8")
        names = set(re.findall(r"^([A-Z0-9_]+_DIR) *=", text, re.M)) - testrunner.KEEP
        self.assertEqual(names - set(testrunner.REDIRECT), set())

    def test_시험_동안은_저장소_밖이다(self):
        repo = Path(settings.REPO_DIR).resolve()
        for name in testrunner.REDIRECT:
            with self.subTest(name=name):
                self.assertNotIn(repo, Path(getattr(settings, name)).resolve().parents)

    def test_임시_파일도_러너의_자리_안이다(self):
        # 시험이 mkdtemp() 로 만들고 지우지 않아도 /tmp 에 쌓이지 않는다 — 러너가 다 돌고 함께 지운다 (koprifossillab 020)
        root = Path(settings.TILE_CACHE_DIR).resolve().parents[1]
        here = Path(tempfile.mkdtemp()).resolve()
        self.assertIn(root, here.parents)
        self.assertEqual(os.environ.get("TMPDIR"), tempfile.gettempdir())

    def test_타일_캐시는_시험마다_비었다(self):
        self.assertEqual(tilecache.stats()["count"], 0)
        tilecache.put(tilecache.key_text("t", "남긴다"), b"x")      # 다음 시험이 이것을 보면 안 된다

    def test_타일_캐시는_시험마다_비었다_둘째(self):
        self.assertEqual(tilecache.stats()["count"], 0)


class Snapshot(SimpleTestCase):
    def test_새로_생긴_것을_잡는다(self):
        before = {"a": (1, 1), "b": (2, 2)}
        self.assertEqual(testrunner.changed(before, {"a": (1, 1), "b": (2, 3), "c": (0, 0)}), ["c"])     # 바뀐 b 는 사람 손일 수 있다
        self.assertEqual(testrunner.changed(before, {"a": (1, 1)}), [])       # 지운 것은 남긴 것이 아니다
