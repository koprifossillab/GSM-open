"""EMODnet 해저 지질 (wetherilli 135). 상류를 부르지 않는다 — 속성의 꼴은 2026-10-02 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import emodnet
from viewer.models import Layer

LITHOLOGY = {
    "objectid": 4060, "age_older": "Pennsylvanian", "age_younger": "Permian", "lithology1": "limestone",
    "label_age": "Pennsylvanian - Permian", "label_litho": "limestone", "original_legend_text": "Late Carboniferous - Permian",
    "scale": 5000000, "name": None, "data_holder": "",
    "reference": "Reference: Asch, K. (2005): The 1:5 Million International Geological Map of Europe and Adjacent Areas. BGR (Hannover)",
    "data_provider": "BGR, Asch, Kristine, kristine.Asch@BGR.de", "shape_area": 0.0113,
}
SUBSTRATE = {
    "objectid": 31293, "name": "Seabed sediments (grain size), N1000 overview", "data_holder": "NGU",
    "contact": "aave.lepland@ngu.no", "scale": 2000000, "original_substrate": "Muddy sandy gravel",
    "folk_16cl_txt": "441. muddy sandy Gravel", "folk_7cl_txt": "4. Mixed sediment", "folk_5cl_txt": "4. Mixed sediment",
}
FAULTS = "emodnet:bgr:pre_quaternary_faults"


class Friendly(SimpleTestCase):
    def test_암상_시대만_추리고_시대를_옮긴다(self):
        got = emodnet.friendly(LITHOLOGY)
        self.assertEqual(list(got), ["암상", "지질시대", "원 범례", "축척", "참고 문헌"])
        self.assertEqual(got["지질시대"], "펜실베니아아기~페름기")
        self.assertEqual(got["축척"], "1:5,000,000")
        self.assertTrue(got["참고 문헌"].startswith("Asch, K. (2005)"))
        self.assertEqual(emodnet.friendly(LITHOLOGY, "en")["지질시대"], "Pennsylvanian - Permian")

    def test_퇴적물_담당자_메일은_싣지_않는다(self):
        got = emodnet.friendly(SUBSTRATE)
        self.assertEqual(got["해저 퇴적물 (Folk 7)"], "4. Mixed sediment")
        self.assertEqual(got["자료 보유 기관"], "NGU")
        self.assertNotIn("aave.lepland@ngu.no", got.values())

    def test_상류_이름은_접두사를_뗀다(self):
        self.assertEqual(emodnet.upstream_name(FAULTS), "bgr:pre_quaternary_faults")
        self.assertEqual(emodnet.upstream_name("emodnet:a, emodnet:b"), "a,b")


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-emodnet-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(emodnet.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_씨앗은_북극해에(self):
        row = Layer.objects.get(name=FAULTS)
        self.assertEqual((row.upstream, row.group.region), ("emodnet", "arctic_ocean"))
        layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        self.assertEqual(layers[FAULTS]["projection"], "EPSG:3413")

    def test_타일은_접두사를_떼고_1_1_1_로(self):
        with mock.patch.object(emodnet.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {
                "layers": FAULTS, "crs": "EPSG:3413", "version": "1.3.0", "request": "GetMap",
                "bbox": "1079737,-702254,1179737,-602254", "width": 512, "height": 512})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["srs"], sent["version"]),
                         ("bgr:pre_quaternary_faults", "EPSG:3413", "1.1.1"))

    def test_누르면_추린_속성(self):
        body = {"type": "FeatureCollection", "features": [{"id": "x.1", "properties": SUBSTRATE}]}
        with mock.patch.object(emodnet.requests, "get",
                               return_value=answer(json=mock.Mock(return_value=body))) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "emodnet:cp_wp3_seabed_substrate_folk_7",
                "query_layers": "emodnet:cp_wp3_seabed_substrate_folk_7", "crs": "EPSG:3413",
                "bbox": "1079737,-702254,1179737,-602254", "width": 256, "height": 256,
                "i": 200, "j": 200, "request": "GetFeatureInfo"}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["query_layers"], sent["x"], sent["info_format"]),
                         ("cp_wp3_seabed_substrate_folk_7", "200", "application/json"))
        self.assertEqual(data["features"][0]["props"]["해저 퇴적물 (Folk 7)"], "4. Mixed sediment")
