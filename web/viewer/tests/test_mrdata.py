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
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mrdata-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(mrdata.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        self.assertEqual(Layer.objects.get(name="mrdata:sgmc2:sgmc2").group.region, "usa")
        self.assertEqual((self.layers["mrdata:sgmc2:sgmc2"]["legend"], self.layers["mrdata:sgmc2:sgmc2"]["legendUrl"]),
                         ("extent", "mrdata/legend/"))                      # 보는 범위의 일반화 암상 (wetherilli 334)
        self.assertTrue(self.layers["mrdata:sim3340:units"]["noLegend"])
        self.assertFalse(self.layers["mrdata:sgmc2:sgmc2structure"]["queryable"])

    def test_SGMC_범례는_보는_범위의_갈래(self):
        gml = ("<wfs:FeatureCollection><gml:featureMember><ms:Lithology><ms:generalize>Sedimentary, clastic</ms:generalize></ms:Lithology>"
               "</gml:featureMember><gml:featureMember><ms:Lithology><ms:generalize>Sedimentary, clastic</ms:generalize></ms:Lithology>"
               "</gml:featureMember><gml:featureMember><ms:Lithology><ms:generalize>Igneous, volcanic</ms:generalize></ms:Lithology>"
               "</gml:featureMember><gml:featureMember><ms:Lithology><ms:generalize>Something new</ms:generalize></ms:Lithology>"
               "</gml:featureMember></wfs:FeatureCollection>")
        with mock.patch.object(mrdata.requests, "get", return_value=mock.Mock(status_code=200, text=gml, content=gml.encode(), elapsed=None)) as get:
            got = self.client.get(reverse("viewer:mrdata-legend"), {"layer": "mrdata:sgmc2:sgmc2", "bbox": "-106,39,-104,41"}).json()
            again = self.client.get(reverse("viewer:mrdata-legend"), {"layer": "mrdata:sgmc2:sgmc2", "bbox": "-106,39,-104,41"}).json()
        self.assertEqual(get.call_count, 1)                                        # 범위마다 한 번
        self.assertEqual(get.call_args.kwargs["params"]["propertyName"], "generalize")
        self.assertEqual([r["lithology"] for r in got["rows"]], ["Sedimentary, clastic", "Igneous, volcanic", "Something new"])
        self.assertEqual([r["color"] for r in got["rows"]], ["#b39b4c", "#ff0000", "#cccccc"])   # 모르는 갈래는 회색
        self.assertEqual(got, again)
        wide = self.client.get(reverse("viewer:mrdata-legend"), {"layer": "mrdata:sgmc2:sgmc2", "bbox": "-120,30,-100,45"})
        self.assertEqual(wide.status_code, 422)

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
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
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


class AlaskaWater(SimpleTestCase):
    """알래스카 SIM 3340 의 물 면을 문이 지운다 — 북위 51.5° 의 하늘색 띠 (wetherilli 224)"""

    def png(self, pixels):
        from PIL import Image
        img = Image.new("RGBA", (len(pixels), 1))
        for x, p in enumerate(pixels):
            img.putpixel((x, 0), p)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()

    def test_물과_섞인_가장자리만_지운다(self):
        from PIL import Image
        land, glacier_edge = (255, 255, 222, 255), (153, 204, 77, 255)
        src = self.png([(204, 255, 255, 255), (202, 253, 253, 180), (191, 239, 239, 16), land, glacier_edge, (170, 230, 230, 255)])
        got = list(Image.open(io.BytesIO(mrdata.clear_water(src))).convert("RGBA").getdata())
        self.assertEqual([p[3] for p in got[:3]], [0, 0, 0])
        self.assertEqual(got[3:5], [land, glacier_edge])
        self.assertEqual(got[5][3], 255)                                   # 물 색에서 먼 옥빛은 남긴다

    def test_캐시_열쇠가_바뀐다(self):
        params = {"layers": "mrdata:sim3340:units", "bbox": "1,2,3,4", "width": "256", "height": "256", "crs": "EPSG:3978"}
        self.assertNotEqual(views.map_cache_key(params), views.tilecache.key_for("map", params))
        other = dict(params, layers="mrdata:sgmc2:sgmc2")
        self.assertEqual(views.map_cache_key(other), views.tilecache.key_for("map", other))

    def test_문이_지운_그림을_낸다(self):
        src = self.png([(204, 255, 255, 255), (255, 255, 222, 255)])
        with mock.patch.object(mrdata, "_get", return_value=answer(content=src)):
            body, ctype = mrdata.get_map({"layers": "mrdata:sim3340:units"})
        from PIL import Image
        self.assertEqual(ctype, "image/png")
        self.assertEqual(Image.open(io.BytesIO(body)).convert("RGBA").getpixel((0, 0))[3], 0)


class Islands(SimpleTestCase):
    """하와이·푸에르토리코 (wetherilli 238) — 2026-10-05 에 받은 `text/plain` 그대로"""
    HI = {"id": "5787", "island": "Hawaii", "volcano": "mloa", "symbol": "Qk5", "age_range": "A.D. 1935", "name": "Kau Basalt",
          "rock_type": "Lava flows", "lithology": "Pahoehoe and aa", "volc_stage": "shield", "compositio": "Tholeiitic basalt",
          "source": "Wolfe and Morris, 1996a", "url": "https://mrdata.usgs.gov/geology/state/hi/higeo-unit.php?unit=Qk5"}
    PR = {"fmatn": "Kmal", "name": "Malo Breccia", "age": "upper ? Cretaceous", "lith62name": "Tuff",
          "url": "https://mrdata.usgs.gov/geology/pr/prgeo-unit.php?unit=Kmal"}

    def test_하와이(self):
        got = mrdata.friendly(self.HI)
        self.assertEqual((got["이름"], got["지질시대"], got["암석"]), ("Kau Basalt", "A.D. 1935", "Lava flows · Pahoehoe and aa"))
        self.assertEqual(got["단위 설명"]["links"][0]["url"], self.HI["url"])

    def test_푸에르토리코(self):
        got = mrdata.friendly(self.PR)
        self.assertEqual((got["기호"], got["지질시대"]), ("Kmal", "백악기 후기(?)"))
        self.assertEqual(mrdata.friendly(self.PR, "en")["지질시대"], "upper ? Cretaceous")

    def test_섬은_3857_로_섬_둘레만(self):
        params = {"layers": "mrdata:hi:units"}
        with mock.patch.object(mrdata, "_get", return_value=answer()) as get:
            mrdata.get_map(params)
        self.assertTrue(get.call_args.args[0].endswith("/services/hi"))
        self.assertIn("mrdata:pr:geol", mrdata.QUERYABLE)
        self.assertIn("mrdata:pr:faultn", mrdata.ISLANDS)


class UsgsMore(SimpleTestCase):
    """USGS 의 다른 자료 — 광물 자원·광산 기호·지질 연대·자력·중력 (wetherilli 247). 2026-10-05 에 받은 `text/plain` 그대로"""

    def test_광물_자원(self):
        got = mrdata.friendly({"dep_id": "10199384", "site_name": "Kunklin", "dev_stat": "Prospect", "code_list": " CU",
                               "url": "https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id=10199384"})
        self.assertEqual((got["이름"], got["광종"], got["개발 단계"]), ("Kunklin", "CU", "Prospect"))

    def test_광산_기호(self):
        got = mrdata.friendly({"state": "NM", "county": "Guadalupe", "ftr_type": "Borrow Pit", "ftr_name": "",
                               "topo_name": "Newkirk", "topo_date": "1964", "topo_scale": "24000", "remarks": ""})
        self.assertEqual(got, {"갈래": "Borrow Pit", "주": "Guadalupe · NM", "지형도": "Newkirk (1964, 1:24,000)"})

    def test_지질_연대(self):
        got = mrdata.friendly({"recno": "707", "url": "https://mrdata.usgs.gov/geochron/show-geochron.php?recno=707"})
        self.assertEqual((got["기록 번호"], got["상세"]["links"][0]["url"]), ("707", "https://mrdata.usgs.gov/geochron/show-geochron.php?recno=707"))

    def test_격자는_누르지_않는다(self):
        self.assertNotIn("mrdata:aeromag:namag", mrdata.QUERYABLE)
        self.assertEqual(mrdata.get_feature_info({"layers": "mrdata:gravity:bouguer"}), {"features": []})
        with mock.patch.object(mrdata, "_get", return_value=answer()) as get:
            mrdata.get_map({"layers": "mrdata:aeromag:namag"})
        self.assertTrue(get.call_args.args[0].endswith("/services/aeromag"))
        self.assertEqual(mrdata.MIN_ZOOM["mrdata:usmin:points"], 9)
