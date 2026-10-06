"""문의 명세(`REGISTRY`)를 모으는 `doors.py` (wetherilli 371)."""

import json
import re

from django.conf import settings
from django.test import SimpleTestCase

from viewer import doors, i18n, views


class Registry(SimpleTestCase):
    def test_문마다_세_손이_있다(self):
        for name, door in doors.relays().items():
            for attr in ("get_map", "get_feature_info", "get_legend"):
                self.assertTrue(callable(getattr(door, attr, None)), f"{name}.{attr}")

    def test_views_의_문_표가_REGISTRY_에서_온다(self):
        self.assertEqual(views._Door.MODULES, doors.relays())
        self.assertIn("kigam", views._Door.MODULES)

    def test_열쇠가_필요한_문만_ready_를_적는다(self):
        need = {name for name, spec in doors.specs().items() if spec.ready}
        self.assertEqual(need, {"kigam", "vworld", "geomap"})
        self.assertTrue(doors.specs()["geomap"].local)

    def test_오류_튜플에_문의_예외가_든다(self):
        errors = views.UPSTREAM_ERRORS
        for module in {spec.module for spec in doors.specs().values()}:
            for obj in vars(module).values():
                if isinstance(obj, type) and issubclass(obj, Exception) and obj.__module__ == module.__name__:
                    self.assertIn(obj, errors, f"{module.__name__}.{obj.__name__}")

    def test_딱지와_기관_이름이_있고_영어가_있다(self):
        """기관 이름은 화면이 `T()` 로 옮긴다 — 한글이 든 이름은 `i18n.EN` 에 있어야 한다."""
        for name, spec in doors.specs().items():
            self.assertTrue(spec.tag and spec.title, name)
            if re.search(r"[가-힣]", spec.title):
                self.assertIn(spec.title, i18n.EN, name)

    def test_씨앗의_상류는_명세가_있다(self):
        """명세가 없으면 딱지가 상류 이름을 대문자로 쓴 것이 되고 기관 이름이 빈다 — 새 상류가 `REGISTRY` 를 잊지 않게.
        노던테리토리(ntgs)는 명세 없이 들어온 것이라 둔다."""
        used = set()
        for seed in (settings.REPO_DIR / "data").glob("*_layers.json"):
            used.add(json.loads(seed.read_text(encoding="utf-8")).get("_상류", "kigam"))
        self.assertLessEqual(used - {"ntgs"}, set(doors.specs()))

    def test_화면에_싣는_표(self):
        table = doors.client()
        self.assertEqual(table["ygs"], ["YGS", "유콘 지질조사소", True])
        self.assertFalse(table["kigam"][2])

    def test_파는_자료는_미리_데우지_않는다(self):
        from viewer.management.commands import prewarm
        for name in views.NO_STORE:
            self.assertNotIn(name, prewarm.PROJECTED)
        self.assertIn("sgc", prewarm.PROJECTED)
