"""아프리카 나라 판 — 남아공 CGS 1:100만(cgs.py)·나미비아 GSN 1:100만(bgs.py 의 GSN) (wetherilli 209).
상류를 부르지 않는다 — 속성의 꼴은 2026-10-04 에 요하네스버그·빈트후크 둘레에서 받은 그대로다."""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import bgs, cgs, tilecache
from viewer.models import Layer

CGS_IDENTIFY = {"results": [{"layerId": 5, "attributes": {
    "OBJECTID": "3370", "STRAT_NAME": "KLIPRIVIERSBERG", "STRAT_RANK": "GRP", "STRAT_PAR_": "VENTERSDORP",
    "CHRONO_NAM": "RANDIAN", "LITHO_1": "ANDESITE", "LITH0_2": "TUFF", "LITHO_3": " ", "LABEL": "Rk"}}]}
GSN_PLAIN = """GetFeatureInfo results:

Layer 'NAM_GSN_1M_BLS'
  Feature 2031: 
    AGE = 'Namibian'
    FORMATION = 'Kuiseb'
    SUBGROUP = 'Khomas'
    GROUP = 'Swakop'
    SEQUENCE = 'Damara'
    ROCKTYPES = 'Mica schist, minor quartzite, graphitic schist, marble'
    MAPCODE = 'Nk'
"""
JHB = {"crs": "EPSG:3857", "bbox": "3067000,-3074000,3167000,-2974000", "width": 256, "height": 256}
WDH = {"crs": "EPSG:3857", "bbox": "1750000,-2730000,2050000,-2430000", "width": 256, "height": 256}


class Friendly(SimpleTestCase):
    def test_남아공_층서·시대·암석(self):
        got = cgs.friendly(CGS_IDENTIFY["results"][0]["attributes"])
        self.assertEqual(got, {"층서 이름": "KLIPRIVIERSBERG (GRP)", "상위 층서": "VENTERSDORP", "지질시대": "RANDIAN",
                               "암석": "ANDESITE, TUFF", "기호": "Rk"})          # 상류의 열 이름 오타(LITH0_2)도 읽는다

    def test_남아공_WMS_변수를_export_로(self):
        sent = cgs.export_params(dict(JHB, layers="cgs:geology_1m"))
        self.assertEqual((sent["layers"], sent["bboxSR"], sent["size"]), ("show:5", 3857, "256,256"))
        with self.assertRaises(cgs.CgsError):
            cgs.export_params(dict(JHB, layers="cgs:geology_1m", crs="EPSG:4326"))

    def test_나미비아_text_plain(self):
        props = bgs.parse_mapserver_plain(GSN_PLAIN)[0]["properties"]
        self.assertEqual(bgs.gsn_friendly(props)["누층군"], "Damara")
        self.assertEqual(bgs.gsn_friendly(props)["지질시대"], "Namibian")


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-africa-c-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for mod in (bgs, cgs):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_아프리카_탭에_얹는다(self):
        self.assertEqual(Layer.objects.get(name="cgs:geology_1m").group.region, "africa")
        self.assertEqual(Layer.objects.get(name="gsn:NAM_GSN_1M_BLS").group.region, "africa")
        self.assertEqual(self.layers["cgs:geology_1m"]["legend"], "list")
        self.assertIn("Council for Geoscience", self.layers["cgs:geology_1m"]["attribution"])

    def test_자료를_파는_상류는_서버_캐시에_담지_않는다(self):
        with mock.patch.object(cgs.requests, "get", return_value=answer()) as get:
            for _ in range(2):
                r = self.client.get(reverse("viewer:wms"), {"layers": "cgs:geology_1m", "version": "1.3.0",
                                                             "request": "GetMap", **JHB})
                self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_count, 2)                                   # 둘째도 상류에 묻는다
        self.assertTrue(get.call_args.args[0].endswith("/Geology/MapServer/export"))
        with mock.patch.object(bgs.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "gsn:NAM_GSN_1M_BLS", "version": "1.3.0", "request": "GetMap", **WDH})
            self.client.get(reverse("viewer:wms"), {"layers": "gsn:NAM_GSN_1M_BLS", "version": "1.3.0", "request": "GetMap", **WDH})
        self.assertEqual(get.call_count, 2)

    def test_남아공_속성은_identify(self):
        with mock.patch.object(cgs.requests, "get", return_value=answer(json=lambda: CGS_IDENTIFY)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "cgs:geology_1m", "query_layers": "cgs:geology_1m", "i": 128, "j": 128,
                "request": "GetFeatureInfo", **JHB}).json()
        self.assertTrue(get.call_args.args[0].endswith("/identify"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "visible:5")
        self.assertEqual(data["features"][0]["props"]["지질시대"], "RANDIAN")

    def test_나미비아_속성은_styles·format_을_채운다(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer(text=GSN_PLAIN)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gsn:NAM_GSN_1M_BLS", "query_layers": "gsn:NAM_GSN_1M_BLS", "i": 128, "j": 128,
                "request": "GetFeatureInfo", **WDH}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["styles"], sent["format"], sent["info_format"]), ("", "image/png", "text/plain"))
        self.assertEqual(data["features"][0]["props"]["층"], "Kuiseb")

    def test_남아공_범례는_목록(self):
        legend = {"layers": [{"layerId": 5, "legend": [{"label": "ARCHAEAN", "imageData": "iVBO", "contentType": "image/png"}]}]}
        with mock.patch.object(cgs.requests, "get", return_value=answer(json=lambda: legend)):
            rows = self.client.get(reverse("viewer:cgs-legend"), {"layer": "cgs:geology_1m"}).json()["rows"]
        self.assertEqual(rows[0]["lithology"], "Archaean")
        self.assertTrue(rows[0]["swatch"].startswith("data:image/png;base64,"))
