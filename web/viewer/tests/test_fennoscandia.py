"""노르웨이·핀란드 기반암 — NGU·GTK (wetherilli 140). 상류를 부르지 않는다 — 속성의 꼴은 2026-10-02 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import gtk, ngu
from viewer.models import Layer

NGU_PLAIN = """GetFeatureInfo results:

Layer 'Berggrunn_regional_hovedbergarter'
  Feature 39881:
    berggrunn_datatype_tekst = 'Bergartsflater (regionalt nivå, 1:250 000)'
    objectid = '39881'
    bergartsenhet_tekst = 'Grønnstein, (Støren, Byafoss)'
    bergartsenhet_tekst_engelsk = ''
    hovedbergart_tekst = 'Grønnstein'
    tektoniskhovedinndeling_tekst = 'Kaledonsk orogen'
    tektoniskenhet_tekst = 'Øvre kaledonske dekkeserie'
    dannelsesalder_tekst = ''
    dannelsesalder_visning_tekst = 'Fra Kambrium (541.0-485.4 Ma) til Ordovicium - Undre ordovicium (485.4-470.0 Ma)'
    metamorffacies_tekst = 'Grønnskiferfacies'
"""
NGU_UNMAPPED = """GetFeatureInfo results:

Layer 'Berggrunn_lokal_bergartsenheter_fullzoom'
  Feature 105479:
    bergartsenhet_tekst = 'IKKE KARTLAGT'
    rgbfargekode = '255 255 255'
"""
GTK_PROPS = {
    "OBJECTID": "64775", "EON_": "Proterozoic", "ERA_": "Mesoproterozoic", "PERIOD_": "not determined",
    "EPOCH_": "not determined", "SUPERGROUP_": "Diverse Mesoproterozoic formations", "GROUP__": "Null",
    "FORMATION_": "Muhos formation", "ORIGINAL_NAME": "Silttikivi, savikivi",
    "ROCK_CLASS_": "Siliciclastic sedimentary rock", "ROCK_NAME_": "Silicate-siltstone", "Shape": "Polygon",
}
NGU_LAYER = "ngu:Berggrunn_regional_hovedbergarter"
GTK_LAYER = "gtk:Litologiset_yksiköt_200k25132"


class Friendly(SimpleTestCase):
    def test_ngu_열을_추리고_값은_그대로(self):
        feature = ngu.parse_plain(NGU_PLAIN)[0]
        self.assertEqual(feature["id"], "Berggrunn_regional_hovedbergarter.39881")
        got = ngu.friendly(feature["properties"])
        self.assertEqual(got["암석 단위"], "Grønnstein, (Støren, Byafoss)")
        self.assertEqual(got["형성 연대"], "Fra Kambrium (541.0-485.4 Ma) til Ordovicium - Undre ordovicium (485.4-470.0 Ma)")
        self.assertNotIn("암석 단위 (영문)", got)              # 빈 칸은 싣지 않는다
        self.assertEqual(list(got)[0], "암석 단위")

    def test_ngu_그리지_않은_칸은_비운다(self):
        self.assertEqual(ngu.friendly(ngu.parse_plain(NGU_UNMAPPED)[0]["properties"]), {})

    def test_gtk_빈_값을_빼고_시대를_옮긴다(self):
        got = gtk.friendly(GTK_PROPS)
        self.assertEqual(got["암석"], "Silicate-siltstone")
        self.assertEqual(got["층"], "Muhos formation")
        self.assertEqual(got["지질시대"], "중원생대")             # EPOCH_ 가 비어 ERA_ 로
        self.assertNotIn("층군", got)
        self.assertEqual(gtk.friendly(GTK_PROPS, "en")["지질시대"], "Mesoproterozoic")

    def test_접두사를_뗀다(self):
        self.assertEqual(ngu.upstream_name(NGU_LAYER), "Berggrunn_regional_hovedbergarter")
        self.assertEqual(gtk.upstream_name(GTK_LAYER), "Litologiset_yksiköt_200k25132")


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-fenno-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for mod in (ngu, gtk):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)

    def test_씨앗은_노르웨이_핀란드에_투영과_함께(self):
        self.assertEqual(Layer.objects.get(name=NGU_LAYER).group.region, "fennoscandia")
        self.assertEqual(Layer.objects.get(name=GTK_LAYER).upstream, "gtk")
        layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        self.assertEqual(layers[NGU_LAYER]["projection"], "EPSG:3575")
        self.assertEqual(layers[GTK_LAYER]["projection"], "EPSG:3413")

    def test_ngu_타일은_3575_로_접두사를_떼고(self):
        with mock.patch.object(ngu.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {
                "layers": NGU_LAYER, "crs": "EPSG:3575", "version": "1.3.0", "request": "GetMap",
                "bbox": "300000,-2900000,340000,-2860000", "width": 512, "height": 512})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"], sent["version"]),
                         ("Berggrunn_regional_hovedbergarter", "EPSG:3575", "1.1.1"))

    def test_ngu_속성은_text_plain(self):
        with mock.patch.object(ngu.requests, "get",
                               return_value=answer(text=NGU_PLAIN, headers={"content-type": "text/plain"})) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": NGU_LAYER, "query_layers": NGU_LAYER, "crs": "EPSG:3575",
                "bbox": "300000,-2900000,340000,-2860000", "width": 512, "height": 512,
                "i": 256, "j": 256, "request": "GetFeatureInfo"}).json()
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "text/plain")
        self.assertEqual(data["features"][0]["props"]["주 암석"], "Grønnstein")

    def test_ngu_그리지_않은_칸은_팝업에_없다(self):
        with mock.patch.object(ngu.requests, "get",
                               return_value=answer(text=NGU_UNMAPPED, headers={"content-type": "text/plain"})):
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "ngu:Berggrunn_lokal_bergartsenheter_fullzoom",
                "query_layers": "ngu:Berggrunn_lokal_bergartsenheter_fullzoom", "crs": "EPSG:3575",
                "bbox": "300000,-2900000,340000,-2860000", "width": 512, "height": 512,
                "i": 256, "j": 256, "request": "GetFeatureInfo"}).json()
        self.assertEqual(data["features"], [])

    def test_gtk_속성은_geojson(self):
        body = {"type": "FeatureCollection", "features": [{"properties": GTK_PROPS}]}
        with mock.patch.object(gtk.requests, "get", return_value=answer(json=mock.Mock(return_value=body))) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": GTK_LAYER, "query_layers": GTK_LAYER, "crs": "EPSG:3413",
                "bbox": "1800000,-2600000,2000000,-2400000", "width": 512, "height": 512,
                "i": 256, "j": 300, "request": "GetFeatureInfo"}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["query_layers"], sent["info_format"]), ("Litologiset_yksiköt_200k25132", "application/geo+json"))
        self.assertEqual(data["features"][0]["props"]["암석"], "Silicate-siltstone")
