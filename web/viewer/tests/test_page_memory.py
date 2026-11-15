"""화면이 레이어를 세울지 물을 때 자료를 통째로 올리지 않는다 (wetherilli 458).

온 지구 화면 한 번에 일꾼마다 60 MB 가 붙었다 — "있는가" 를 묻는 것이 파일을 읽어 붙들었기 때문이다. 타일을 그릴 때만 읽는다."""
from django.test import TestCase

from viewer import faults, icemargins, impacts, paleocoast, tectonics


class EarthPage(TestCase):
    def test_온_지구_화면은_큰_자료를_붙들지_않는다(self):
        loaders = (faults.data, tectonics.data, impacts.data, icemargins.data, paleocoast._load)
        for loader in loaders:
            loader.cache_clear()
        self.assertEqual(self.client.get("/GSM/earth/").status_code, 200)
        for loader in loaders:
            self.assertEqual(loader.cache_info().currsize, 0, loader.__module__)

    def test_있는가와_연대는_읽은_것과_같다(self):
        self.assertEqual(tectonics.available(), tectonics.data() is not None)
        self.assertEqual(impacts.available(), impacts.data() is not None)
        self.assertEqual(faults.available(), faults.data() is not None)
        d = icemargins.data() or {}
        self.assertEqual(icemargins.stops(), {k: sorted(float(a) for a in d.get(k, {})) for k in ("nadi", "dated")})
        whole = paleocoast.load()
        self.assertEqual(paleocoast.ages(), whole["ages"] if whole else [])
