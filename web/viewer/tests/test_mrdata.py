"""미국 — USGS SGMC(본토)와 알래스카 SIM 3340 (wetherilli 205). 상류를 부르지 않는다 — 꼴은 2026-10-04 에 받은 그대로다."""
import importlib.util
import io
import pathlib
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import mrdata, static_tables, views
from viewer.models import Layer

#: SGMC WFS 1.0 (PROPERTYNAME 을 붙인 것) — 덴버
GML = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection xmlns:ms="http://mapserver.gis.umn.edu/mapserver" xmlns:wfs="http://www.opengis.net/wfs">
  <gml:featureMember>
      <ms:Lithology>
        <ms:state>CO</ms:state>
        <ms:orig_label>Qa</ms:orig_label>
        <ms:unit_link>COQa;0</ms:unit_link>
        <ms:generalize>Unconsolidated, undifferentiated</ms:generalize>
        <ms:src_url>https://pubs.usgs.gov/of/1992/ofr-92-0507/</ms:src_url>
        <ms:url>https://mrdata.usgs.gov/geology/state/sgmc2-unit.php?unit=COQa;0&amp;x=1</ms:url>
      </ms:Lithology>
  </gml:featureMember>
</wfs:FeatureCollection>"""
#: 알래스카 WMS GetFeatureInfo `text/plain`
PLAIN = """GetFeatureInfo results:

Layer 'units'
  Feature 89979: 
    class = '102'
    label = ''
    state_unit = 'Water'
    age_range = 'Holocene'
    url = 'https://mrdata.usgs.gov/sim3340/show-sim3340.php?seq=A002&src=SR001_102'
"""
MERC = {"crs": "EPSG:3857", "bbox": "-11741355.98,4774562.53,-11663084.47,4852834.05", "width": 512, "height": 512}


def answer(text="", status=200, content=b"\x89PNG", ctype="image/png"):
    return mock.Mock(status_code=status, content=content, text=text, url="…", headers={"content-type": ctype})


class Parse(SimpleTestCase):
    def test_GML(self):
        f = mrdata.parse_gml(GML, "Lithology")
        self.assertEqual(f[0]["properties"]["orig_label"], "Qa")
        self.assertTrue(f[0]["properties"]["url"].endswith("COQa;0&x=1"))           # &amp; 를 푼다

    def test_text_plain(self):
        self.assertEqual(mrdata.parse_plain(PLAIN)[0]["properties"]["state_unit"], "Water")

    def test_본토_속성(self):
        got = mrdata.friendly(mrdata.parse_gml(GML, "Lithology")[0]["properties"])
        self.assertEqual((got["주"], got["기호"], got["암상"]), ("CO", "Qa", "Unconsolidated, undifferentiated"))
        self.assertEqual(got["원도"]["links"][0]["url"], "https://pubs.usgs.gov/of/1992/ofr-92-0507/")

    def test_알래스카_시대는_옮긴다(self):
        got = mrdata.friendly(mrdata.parse_plain(PLAIN)[0]["properties"])
        self.assertEqual((got["이름"], got["지질시대"]), ("Water", "홀로세"))
        self.assertNotIn("기호", got)                                               # 빈 label 은 뺀다
        self.assertEqual(mrdata.friendly(mrdata.parse_plain(PLAIN)[0]["properties"], "en")["지질시대"], "Holocene")

    def test_누른_자리(self):
        lon, lat, pixel = mrdata.click_lonlat(dict(MERC, i=256, j=256))
        self.assertAlmostEqual(lon, -105.12, places=1)
        self.assertAlmostEqual(lat, 39.64, places=1)
        self.assertGreater(pixel, 0)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mrdata-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(mrdata.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="mrdata:sgmc2:sgmc2").group.region, "usa")
        self.assertTrue(self.layers["mrdata:sgmc2:sgmc2"]["noLegend"])
        self.assertFalse(self.layers["mrdata:sgmc2:sgmc2structure"]["queryable"])

    def test_타일은_서비스의_WMS_로(self):
        with mock.patch.object(mrdata.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "mrdata:sim3340:units", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(get.call_args.args[0], "https://mrdata.usgs.gov/services/sim3340")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "units")

    def test_본토는_WFS_로_묻는다(self):
        with mock.patch.object(mrdata.requests, "get", return_value=answer(GML, ctype="text/xml")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "mrdata:sgmc2:sgmc2", "query_layers": "mrdata:sgmc2:sgmc2",
                                                                    "i": 256, "j": 256, "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(get.call_args.args[0], "https://mrdata.usgs.gov/services/wfs/sgmc2")
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["typeName"], sent["version"]), ("Lithology", "1.0.0"))
        self.assertNotIn("msGeometry", sent["propertyName"])
        w, s, e, n = (float(v) for v in sent["bbox"].split(","))
        self.assertTrue(w < -105.12 < e and s < 39.64 < n and e - w < 0.02)
        self.assertEqual(data["features"][0]["props"]["기호"], "Qa")

    def test_알래스카는_text_plain(self):
        with mock.patch.object(mrdata.requests, "get", return_value=answer(PLAIN, ctype="text/plain")) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {"layers": "mrdata:sim3340:units", "query_layers": "mrdata:sim3340:units",
                                                                    "i": 256, "j": 256, "request": "GetFeatureInfo", **MERC}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "text/plain")
        self.assertEqual(data["features"][0]["props"]["지질시대"], "홀로세")


class Static(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=io.StringIO())

    def test_고르면_싣는다(self):
        spec = importlib.util.spec_from_file_location("static_site", pathlib.Path(__file__).resolve().parents[3] / "deploy" / "static_site.py")
        site = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(site)
        self.assertNotIn("usa", site.REGIONS)
        self.assertEqual(site.OPTIONAL["usa"], (["usa"], ["mrdata"]))
        with override_settings(STATIC_SITE={"regions": ["usa"], "upstreams": ["mrdata"]}):
            names = {l["name"] for g in views._static_catalog(views._catalog("ko")) for l in g["layers"]}
        self.assertIn("mrdata:sgmc2:sgmc2", names)
        self.assertEqual(static_tables.tables()["mrdata"]["layers"]["mrdata:sim3340:units"], ["sim3340", "units"])
