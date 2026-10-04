"""스웨덴 SGU — 기반암 1:100만·1:5만–25만 (sgu.py, wetherilli 213).
상류를 부르지 않는다 — 속성의 꼴은 2026-10-04 에 스톡홀름 둘레에서 받은 그대로다."""
import importlib.util
import io
import pathlib
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import sgu, static_tables, views
from viewer.models import Layer

NA10 = {"brg": 575775, "litologi": "Metagråvacka, glimmerskiffer (ca 1,96-1,87 miljarder år)",
        "lithology": "Metagreywacke, mica schist (c. 1.96-1.87 Ga)", "tekt_enhet": "Svekokarelska orogenen",
        "tect_unit": "Svecokarelian orogen", "underenhet": "Bergslagens litotektoniska enhet",
        "subunit": "Bergslagen lithotectonic unit", "symbol": "302_108", "etikett": 625}
K50 = {"geo_enh_tx": "Svekokarelska orogenen, intrusivbergart (granit-pegmatitsvit), ställvis metamorf, och migmatit 1,82-1,74 miljarder år",
       "lito_n_tx": "Null:okänt", "tekt_n_tx": "Svekokarelska orogenen", "bergart_tx": "Granit", "farg_tx": "Null:saknas; Null:saknas",
       "min_ss_tx": "kvarts-fältspat-glimmersammansättning",
       "handel1_tx": "intrusionsprocess; endogen miljö; orosirium 7 1820-1800 Ma; staterium 2 1770-1740 Ma; Null:okänt; Null:ej_tillämpligt",
       "prod_bet": "Ba 60"}
GFI = {"type": "FeatureCollection", "features": [
    {"id": "SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K.fid-1", "properties": K50, "geometry": None},
    {"id": "SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K.fid-2", "properties": dict(K50, bergart_tx="Gnejs"), "geometry": None},
    {"id": "SE.GOV.SGU.BERGGRUND_NA10.fid-3", "properties": NA10, "geometry": None}]}
STHLM = {"crs": "EPSG:3413", "bbox": "2995000,-1560000,3025000,-1530000", "width": 256, "height": 256}


class Door(SimpleTestCase):
    def test_레이어_하나가_판_둘을(self):
        self.assertEqual(sgu.upstream_names("sgu:bedrock"),
                         "berg:SE.GOV.SGU.BERGGRUND_NA10,berg:SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K")       # 1:100만 위에 5만
        self.assertEqual(sgu.upstream_names("sgu:bedrock", reverse=True).split(",")[0],
                         "berg:SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K")                                 # 속성은 자세한 것부터
        with self.assertRaises(sgu.SguError):
            sgu.upstream_names("berg:SE.GOV.SGU.BERGGRUND_NA10")                                         # 상류 이름을 곧장 받지 않는다

    def test_판마다_첫_하나(self):
        got = sgu.first_per_layer(GFI["features"])
        self.assertEqual([f["id"] for f in got], ["SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K.fid-1", "SE.GOV.SGU.BERGGRUND_NA10.fid-3"])

    def test_손질(self):
        self.assertEqual(sgu.friendly(NA10), {"암석": "Metagreywacke, mica schist (c. 1.96-1.87 Ga)",
                                              "지구조 단위": "Svecokarelian orogen", "하위 단위": "Bergslagen lithotectonic unit"})
        got = sgu.friendly(K50)
        self.assertEqual(got["암석"], "Granit")
        self.assertNotIn("암층서 단위", got)                                                       # Null:okänt
        self.assertEqual(got["생성"], "intrusionsprocess; endogen miljö; orosirium 7 1820-1800 Ma; staterium 2 1770-1740 Ma")
        self.assertEqual(got["도폭"], "Ba 60")


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
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-sgu-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(sgu.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}

    def test_노르웨이·스웨덴·핀란드_탭에_3413_으로(self):
        self.assertEqual(Layer.objects.get(name="sgu:bedrock").group.region, "fennoscandia")
        self.assertEqual(self.layers["sgu:bedrock"]["projection"], "EPSG:3413")
        self.assertFalse(self.layers["sgu:deformation"]["queryable"])
        self.assertIn("CC0", self.layers["sgu:bedrock"]["attribution"])

    def test_그림은_판_둘을_한_번에(self):
        with mock.patch.object(sgu.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "sgu:bedrock", "version": "1.3.0", "request": "GetMap", **STHLM})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual(get.call_args.args[0], "https://maps3.sgu.se/geoserver/ows")
        self.assertEqual((sent["layers"], sent["srs"], sent["version"]),
                         ("berg:SE.GOV.SGU.BERGGRUND_NA10,berg:SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K", "EPSG:3413", "1.1.1"))

    def test_속성은_자세한_것부터_판마다_하나(self):
        with mock.patch.object(sgu.requests, "get", return_value=answer(json=lambda: GFI)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "sgu:bedrock", "query_layers": "sgu:bedrock", "i": 128, "j": 128, "request": "GetFeatureInfo", **STHLM}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["buffer"], sent["x"], sent["info_format"]), (1, "128", "application/json"))
        self.assertTrue(sent["query_layers"].startswith("berg:SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K,"))
        self.assertEqual([f["props"]["암석"] for f in data["features"]], ["Granit", "Metagreywacke, mica schist (c. 1.96-1.87 Ga)"])

    def test_범례는_1_100만_판(self):
        with mock.patch.object(sgu.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:legend"), {"layer": "sgu:bedrock"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.kwargs["params"]["layer"], "berg:SE.GOV.SGU.BERGGRUND_NA10")

    def test_정적_판은_고르면_싣는다(self):
        spec = importlib.util.spec_from_file_location("static_site", pathlib.Path(__file__).resolve().parents[3] / "deploy" / "static_site.py")
        site = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(site)
        self.assertNotIn("fennoscandia", site.REGIONS)
        self.assertEqual(site.OPTIONAL["sweden"], (["fennoscandia"], ["sgu"]))
        with override_settings(STATIC_SITE={"regions": ["fennoscandia"], "upstreams": ["sgu"]}):
            names = {l["name"] for g in views._static_catalog(views._catalog("ko")) for l in g["layers"]}
        self.assertEqual(names, {"sgu:bedrock", "sgu:deformation", "sgu:minerals", "sgu:magnetic"})  # NGU·GTK 는 서버 판에만
        self.assertEqual(static_tables.tables()["sgu"]["legend"]["sgu:bedrock"], "berg:SE.GOV.SGU.BERGGRUND_NA10")
