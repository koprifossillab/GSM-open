"""영국 — 수리지질·G-BASE 시료 지점·CMIC 하천 퇴적물 지화학 (wetherilli 324). 상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import bgs

WEB = {"crs": "EPSG:3857", "bbox": "-600000,6480000,-560000,6520000", "width": 256, "height": 256}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Cmic(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(bgs.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_원소_지도는_REST_export(self):
        with mock.patch.object(bgs.requests, "get", return_value=answer()) as get:
            bgs.geoindex_get_map(dict(WEB, layers="bgsgi:gq:Cu"))
        self.assertEqual(get.call_args.args[0],
                         "https://map.bgs.ac.uk/arcgis/rest/services/CMIC/Stream_Sediment_Geochemistry/MapServer/export")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:17")

    def test_누르면_함량(self):
        body = {"results": [{"attributes": {"Classify.Pixel Value": "37.912", "Classify.Class value": "0"}}]}
        with mock.patch.object(bgs.requests, "get", return_value=answer(body, "application/json")):
            got = bgs.geoindex_get_feature_info(dict(WEB, layers="bgsgi:gq:Cu", query_layers="bgsgi:gq:Cu", i=128, j=128))
        self.assertEqual(bgs.geoindex_friendly(got["features"][0]["properties"]), {"원소": "Cu", "함량 (mg/kg)": "37.9"})
        self.assertEqual(bgs.geoindex_friendly({"_gq": "CaO", "_oxide": True, "value": "1.234"}), {"원소": "CaO", "함량 (%)": "1.23"})

    def test_목록_범례와_누르기(self):
        self.assertIn("bgsgi:gq:Zn", bgs.LEGEND_LAYERS)
        self.assertTrue(bgs.geoindex_queryable("bgsgi:gq:Zn"))
        self.assertTrue(bgs.geoindex_queryable("bgsgi:hydrogeology"))
        self.assertFalse(bgs.geoindex_queryable("bgsgi:magnetic"))


class GeoIndex(SimpleTestCase):
    def test_수리지질과_시료(self):
        hydro = bgs.geoindex_friendly({"ROCK_UNIT": "WARWICKSHIRE GROUP", "CLASS": "2B", "CHARACTER": "Moderately productive aquifer"})
        self.assertEqual((hydro["암석 단위"], hydro["대수층"]), ("WARWICKSHIRE GROUP", "Moderately productive aquifer"))
        sample = bgs.geoindex_friendly({"SAMPLE_NUMBER": "4 32 2782 C+", "ANALYTES": "Ag,As Au ", "PROJECT": "G-BASE", "EASTING": "1", "NORTHING": "2"})
        self.assertEqual(sample["분석 원소"], "Ag As Au")
