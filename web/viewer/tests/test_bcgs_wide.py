"""브리티시컬럼비아를 넓게 볼 때 — 줄인 스타일을 POST 로 (wetherilli 317). 상류를 부르지 않는다."""
import tempfile
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import bcgs, usage

STYLE = """<sld:StyledLayerDescriptor><sld:NamedLayer><sld:UserStyle><sld:FeatureTypeStyle>
<sld:Rule><sld:Name>Outlined</sld:Name><sld:MaxScaleDenominator>700000.0</sld:MaxScaleDenominator>
<sld:PolygonSymbolizer><sld:Fill><sld:CssParameter name="fill">#000000</sld:CssParameter></sld:Fill></sld:PolygonSymbolizer></sld:Rule>
<sld:Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>AGE_GROUP</ogc:PropertyName><ogc:Literal>103_intrusive rocks</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>
<sld:MaxScaleDenominator>500000.0</sld:MaxScaleDenominator><sld:PolygonSymbolizer><sld:Fill><sld:CssParameter name="fill">#ff0000</sld:CssParameter></sld:Fill></sld:PolygonSymbolizer></sld:Rule>
<sld:Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>AGE_GROUP</ogc:PropertyName><ogc:Literal>0_intrusive rocks</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>
<sld:MaxScaleDenominator>500000.0</sld:MaxScaleDenominator><sld:PolygonSymbolizer><sld:Fill><sld:CssParameter name="fill">#ff0000</sld:CssParameter></sld:Fill></sld:PolygonSymbolizer></sld:Rule>
<sld:Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>AGE_GROUP</ogc:PropertyName><ogc:Literal>5_sedimentary &amp; volcanic</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>
<sld:MaxScaleDenominator>500000.0</sld:MaxScaleDenominator><sld:PolygonSymbolizer><sld:Fill><sld:CssParameter name="fill">#00ff00</sld:CssParameter></sld:Fill></sld:PolygonSymbolizer></sld:Rule>
</sld:FeatureTypeStyle></sld:UserStyle></sld:NamedLayer></sld:StyledLayerDescriptor>"""
WIDE = {"layers": "bcgs:bedrock", "srs": "EPSG:3978", "bbox": "-2504688.54,0,-1252344.27,1252344.27", "width": "512", "height": "512",
        "format": "image/png"}
CLOSE = dict(WIDE, bbox="-1956787,1017529,-1917651,1056665")


def png():
    return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=b"\x89PNG", elapsed=None)


@override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-bcgs-wide-"))
class Wide(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_같은_색은_한_칸으로_축척_끝은_뺀다(self):
        sld = bcgs.compact_sld(STYLE)
        self.assertEqual(sld.count("<Rule>"), 2)                       # 빨강(값 둘)·초록, 테두리 칸은 버린다
        self.assertIn("<ogc:Or>", sld)
        self.assertNotIn("ScaleDenominator", sld)
        self.assertIn("5_sedimentary &amp; volcanic", sld)

    def test_축척(self):
        self.assertGreater(bcgs._scale(WIDE), bcgs.WIDE_SCALE)
        self.assertLess(bcgs._scale(CLOSE), bcgs.WIDE_SCALE)

    def test_넓으면_POST_가까우면_GET(self):
        styles = mock.Mock(status_code=200, text=STYLE, elapsed=None, content=b"")
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()), \
             mock.patch.object(bcgs.requests, "get", side_effect=[styles, png()]) as get, \
             mock.patch.object(bcgs.requests, "post", return_value=png()) as post:
            bcgs.get_map(dict(WIDE))
            bcgs.get_map(dict(CLOSE))
        self.assertEqual(get.call_args_list[0].kwargs["params"]["request"], "GetStyles")     # 스타일은 한 번
        sent = post.call_args.kwargs["data"]
        self.assertIn("<ogc:Or>", sent["SLD_BODY"])
        self.assertEqual(sent["layers"], bcgs.LAYERS["bcgs:bedrock"])
        self.assertNotIn("SLD_BODY", get.call_args_list[1].kwargs["params"])                  # 가까우면 상류의 스타일 그대로

    def test_광물_산지는_늘_GET(self):
        with mock.patch.object(bcgs.requests, "get", return_value=png()) as get, mock.patch.object(bcgs.requests, "post") as post:
            bcgs.get_map(dict(WIDE, layers="bcgs:minfile"))
        post.assert_not_called()
        self.assertEqual(get.call_count, 1)
