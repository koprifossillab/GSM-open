"""GSJ 1:200만 지질도·중력을 누르면 이름이 뜬다 (wetherilli 316). 상류를 부르지 않는다 — `_gsjows_get` 을 갈아 끼운다."""
import tempfile
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import gsj, i18n

SLD = """<StyledLayerDescriptor><NamedLayer><Name>area</Name><UserStyle><FeatureTypeStyle>
<Rule>
<Name>0 Undef0 : 未定義0 </Name></Rule>
<Rule>
<Name>3 PG2-N1 : 中期始新世より中期中新世前期の堆積岩類 </Name></Rule>
<Rule>
<Name>19 Cm-H : 時代未詳の付加コンプレックスで超苦鉄質火成岩類</Name></Rule>
<Rule>
<Name>300 Sea : 海</Name></Rule>
</FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>"""
CLICK = {"srs": "EPSG:4326", "bbox": "138.5,35.5,139.5,36.5", "width": "101", "height": "101", "x": "50", "y": "50"}


def answer(text):
    return mock.Mock(status_code=200, text=text)


class AgeJa(SimpleTestCase):
    def test_옮긴다(self):
        self.assertEqual(i18n.age_ja("後期更新世後期より完新世"), "플라이스토세 후기 후반~홀로세")
        self.assertEqual(i18n.age_ja("中期始新世より中期中新世前期", "en"), "Middle Eocene – early Middle Miocene")
        self.assertEqual(i18n.age_ja("先シルル紀"), "실루리아기 이전")
        self.assertEqual(i18n.age_ja("新しい何か"), "新しい何か")                # 모르면 원문


@override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsjows-"))
class Click(SimpleTestCase):
    def test_지질도는_번호를_기호와_설명으로(self):
        calls = []

        def get(url, params):
            calls.append(params["request"])
            return answer(SLD if params["request"] == "GetStyles" else "GetFeatureInfo results:\n  Feature 5798: \n    GEO200 = '3'\n")
        with mock.patch.object(gsj, "_gsjows_get", side_effect=get):
            got = gsj.gsjows_get_feature_info(dict(CLICK, layers="gsjows:japan2m", query_layers="gsjows:japan2m"))
            again = gsj.gsjows_get_feature_info(dict(CLICK, layers="gsjows:japan2m", query_layers="gsjows:japan2m"))
        self.assertEqual(calls, ["GetFeatureInfo", "GetStyles", "GetFeatureInfo"])        # 범례 표는 한 번만 받는다
        self.assertEqual(got, again)
        props = gsj.gsjows_friendly(got["features"][0]["properties"])
        self.assertEqual(props["기호"], "PG2-N1")
        self.assertEqual(props["지질시대"], "에오세 중기~마이오세 중기 전반")
        self.assertEqual(props["암상"], "堆積岩類")                                    # 값은 옮기지 않는다

    def test_바다는_비운다(self):
        def get(url, params):
            return answer(SLD if params["request"] == "GetStyles" else "    GEO200 = '300'\n")
        with mock.patch.object(gsj, "_gsjows_get", side_effect=get), \
             override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()):
            self.assertEqual(gsj.gsjows_get_feature_info(dict(CLICK, layers="gsjows:japan2m"))["features"], [])

    def test_중력은_둘레_등치선의_범위(self):
        seen = []

        def get(url, params):
            seen.append(params["bbox"])
            if len(seen) == 1:
                return answer("  Search returned no results.\n")
            return answer("    VAL = '10'\n    VAL = '12'\n    VAL = '10'\n")
        with mock.patch.object(gsj, "_gsjows_get", side_effect=get):
            got = gsj.gsjows_get_feature_info(dict(CLICK, layers="gsjows:gravity"))
        self.assertEqual(len(seen), 2)                                                  # 비면 넓혀 한 번 더
        self.assertEqual(gsj.gsjows_friendly(got["features"][0]["properties"]), {"부게 이상 (mGal, 둘레 등치선)": "10 – 12"})

    def test_지구화학도는_누르지_않는다(self):
        with mock.patch.object(gsj, "_gsjows_get") as get:
            self.assertEqual(gsj.gsjows_get_feature_info(dict(CLICK, layers="gsjows:geochem:Cu"))["features"], [])
        get.assert_not_called()
