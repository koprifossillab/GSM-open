"""팝업에 올리기 전에 상류 속성을 손보는 자리.

상류가 주는 것을 그대로 믿지 않는다 — 앵커가 섞여 오고, 물어본 적 없는
곁가지가 딸려 오고, 같은 것이 여러 번 온다.
"""
from django.test import SimpleTestCase

from viewer import views

DOPOK = ('유성[1977]'
         '<a href="https://data.kigam.re.kr/mgeo/common/MAP/original_map/'
         'geology_50k/file_down.do?savFile=GF12_org_map.pdf">(원도)</a>'
         '<a href="https://doi.org/10.22747/data.20210324.2980">(수치지질도)</a>')


class SplitLinks(SimpleTestCase):
    def test_앵커가_없으면_그대로_둔다(self):
        self.assertEqual(views._split_links("충적층"), "충적층")

    def test_숫자와_None_도_그대로(self):
        self.assertEqual(views._split_links(1997), 1997)
        self.assertIsNone(views._split_links(None))

    def test_5만_도폭을_글자와_링크로_가른다(self):
        got = views._split_links(DOPOK)
        self.assertEqual(got["text"], "유성[1977]")
        self.assertEqual([l["label"] for l in got["links"]], ["(원도)", "(수치지질도)"])
        self.assertTrue(got["links"][0]["url"].endswith("GF12_org_map.pdf"))
        self.assertEqual(got["links"][1]["url"], "https://doi.org/10.22747/data.20210324.2980")

    def test_http_https_가_아니면_링크로_받지_않는다(self):
        got = views._split_links('가<a href="javascript:alert(1)">눌러</a>')
        # 받을 링크가 없으면 글자만 남는다
        self.assertEqual(got, "가눌러")

    def test_태그는_글자로_새어나오지_않는다(self):
        got = views._split_links('<b>굵게</b><a href="https://x/">열기</a>')
        self.assertEqual(got["text"], "굵게")
        self.assertNotIn("<", got["text"])

    def test_이름표가_비면_대신_적는다(self):
        got = views._split_links('가<a href="https://x/"></a>')
        self.assertEqual(got["links"][0]["label"], "열기")


class IsNoise(SimpleTestCase):
    def test_행정경계는_곁가지다(self):
        self.assertTrue(views._is_noise("admin_boundary_SGG_201907_NGII.76"))

    def test_지질은_곁가지가_아니다(self):
        self.assertFalse(views._is_noise("l_50k_geology_litho_latest.56592"))

    def test_도곽은_버리지_않는다(self):
        """도폭명·제작연도·조사자가 들어 있어 5만을 볼 때 쓸모가 있다."""
        self.assertFalse(views._is_noise("l_250k_geology_frame.4"))

    def test_빈_아이디도_견딘다(self):
        self.assertFalse(views._is_noise(""))


class Cached(SimpleTestCase):
    """속성도 담아 두고, 다음에 같은 것을 물으면 상류를 타지 않는다."""

    ANSWER = {"type": "FeatureCollection", "features": [{
        "id": "l_250k_geology_litho.1",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0]] * 500]},
        "properties": {"지층명": "충적층"}}]}
    QUERY = ("/GSM/featureinfo/?request=GetFeatureInfo&layers=L_250K_Geology_Map"
             "&query_layers=L_250K_Geology_Map&srs=EPSG:3857&bbox=1,2,3,4"
             "&width=256&height=256&x=10&y=10")

    def setUp(self):
        import tempfile
        from django.test import override_settings
        self.dir = tempfile.mkdtemp(prefix="gsm-info-")
        patch = override_settings(TILE_CACHE_DIR=self.dir, KIGAM_KEY="abc",
                                  DEV_DIRECT_WMS=False,
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)

    def _ask(self, **kw):
        from unittest import mock
        from viewer import kigam
        with mock.patch.object(kigam, "get_feature_info", **kw) as upstream:
            response = self.client.get(self.QUERY)
        return response, upstream

    def test_두_번째는_상류를_타지_않는다(self):
        first, up1 = self._ask(return_value=self.ANSWER)
        second, up2 = self._ask(return_value=self.ANSWER)
        self.assertEqual(up1.call_count, 1)
        self.assertEqual(up2.call_count, 0)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(second.json()["features"][0]["props"]["지층명"], "충적층")

    def test_기하는_떼고_담는다(self):
        from pathlib import Path
        self._ask(return_value=self.ANSWER)
        stored = next(Path(self.dir).rglob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn("coordinates", stored)
        self.assertIn("충적층", stored)

    def test_상류가_못_주면_늙은_것을_낸다(self):
        import os
        import time
        from pathlib import Path
        from viewer import kigam
        self._ask(return_value=self.ANSWER)
        path = next(Path(self.dir).rglob("*.json"))
        old = time.time() - 4 * 365 * 86400
        os.utime(path, (old, old))
        response, up = self._ask(side_effect=kigam.UpstreamError("막혔다"))
        self.assertEqual(up.call_count, 1)          # 늙었으니 다시 물었다
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["features"][0]["props"]["지층명"], "충적층")
