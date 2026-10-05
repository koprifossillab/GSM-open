"""알래스카 DGGS 의 광산·산지·광업 지구 (wetherilli 322) — 상류를 부르지 않는다. 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import usstates

LCC = {"crs": "EPSG:3978", "bbox": "-2600000,1500000,-1000000,3000000", "width": 256, "height": 256}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Dggs(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(usstates.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_REST_export(self):
        with mock.patch.object(usstates.requests, "get", return_value=answer()) as get:
            usstates.DGGS.get_map(dict(LCC, layers="dggs:minerals"))
        self.assertEqual(get.call_args.args[0],
                         "https://maps.dggs.alaska.gov/arcgis/rest/services/Mineral_Occurrences_2020_MIL1/MapServer/export")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:12")

    def test_점은_넓게_누른다(self):
        body = {"results": [{"attributes": {"property": "Kahilt (Cristo)", "commodities_major": "Cu, Au", "critical_minerals_ardf": "none reported",
                                            "property_status": "Occurrence", "distribution_policy": "public, data visibility"}}]}
        with mock.patch.object(usstates.requests, "get", return_value=answer(body, "application/json")) as get:
            got = usstates.DGGS.get_feature_info(dict(LCC, layers="dggs:minerals", query_layers="dggs:minerals", i=6, j=64))
        self.assertEqual(get.call_args.kwargs["params"]["tolerance"], 4)
        props = usstates.friendly(got["features"][0]["properties"])
        self.assertEqual((props["이름"], props["광종"], props["개발 단계"]), ("Kahilt (Cristo)", "Cu, Au", "Occurrence"))
        self.assertNotIn("핵심 광물", props)                                # "none reported" 는 뺀다

    def test_광업_지구(self):
        self.assertEqual(usstates.friendly({"name": "Redoubt District", "region": "Cook Inlet-Susitna  Region", "sq_miles": 1.0}),
                         {"광업 지구": "Redoubt District", "권역": "Cook Inlet-Susitna Region"})
        self.assertNotIn("dggs:districts", usstates.LEGEND_LAYERS)
