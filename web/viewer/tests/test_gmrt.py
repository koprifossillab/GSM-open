"""극지 수심 GMRT (wetherilli 428). 상류를 부르지 않는다."""
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

from viewer import doors, gmrt

DATA = Path(__file__).resolve().parents[3] / "data"


class Reply:
    def __init__(self, status=200, body=b"", ctype="image/png", data=None):
        self.status_code, self.content, self.headers, self._data = status, body, {"content-type": ctype}, data
        self.url, self.elapsed = "u", None

    def json(self):
        return self._data


class Door(SimpleTestCase):
    def test_평사도법을_푼다(self):
        """참값은 proj4.js(화면이 쓰는 것)로 낸 것 — 세종 기지·장보고 기지·다산 기지·척치해"""
        for code, x, y, lat, lon in (("EPSG:3031", -2630854.938, 1594124.634, -62.2234, -58.7869),
                                     ("EPSG:3031", 456795.229, -1617512.273, -74.62, 164.23),
                                     ("EPSG:3995", 249606.704, -1181402.627, 78.92, 11.93),
                                     ("EPSG:3995", -284571.723, 1613886.439, 75.0, -170.0)):
            got = gmrt.stereo_to_latlon(code, x, y)
            self.assertAlmostEqual(got[0], lat, places=4)
            self.assertAlmostEqual(got[1], lon, places=4)

    def test_서비스가_판을_가른다(self):
        with mock.patch.object(gmrt, "_get", return_value=Reply(body=b"png")) as get:
            gmrt.get_map({"layers": "gmrt:np_mask", "crs": "EPSG:3995", "bbox": "0,0,1,1", "width": "256", "height": "256"})
        url, params = get.call_args.args
        self.assertEqual(url, "https://www.gmrt.org/services/mapserver/wms_NP_mask")
        self.assertEqual((params["layers"], params["srs"], params["version"]), ("North_Polar_Bathymetry", "EPSG:3995", "1.1.1"))

    def test_누른_자리는_점_서비스로(self):
        params = {"crs": "EPSG:3031", "bbox": "-2631354.938,1593624.634,-2630354.938,1594624.634",
                  "width": "100", "height": "100", "i": "49.5", "j": "49.5"}
        with mock.patch.object(gmrt, "_get", return_value=Reply(ctype="application/json", data={"elevation": "-1234.4"})) as get:
            got = gmrt.get_feature_info(params)
        url, query = get.call_args.args
        self.assertEqual(url, "https://www.gmrt.org/services/PointServer")
        self.assertEqual((query["latitude"], query["longitude"]), ("-62.22340", "-58.78690"))
        self.assertEqual(got["features"][0]["properties"]["수심 (m)"], "1,234")

    def test_문이_등록되었다(self):
        spec = doors.specs()["gmrt"]
        self.assertIs(spec.relay, gmrt)
        self.assertTrue(spec.projected)
        self.assertFalse(spec.globe)            # 3857 을 그려 주지 않는다


class Catalog(TestCase):
    def test_씨앗(self):
        for region, prefix in (("antarctica", "gmrt:sp"), ("arctic_ocean", "gmrt:np")):
            seed = json.loads((DATA / f"gmrt_{region}_layers.json").read_text(encoding="utf-8"))
            self.assertEqual(seed["_지역"], region)
            names = [row["name"] for row in seed["레이어"]]
            self.assertEqual(names, [prefix, prefix + "_mask"])
            self.assertTrue(all(gmrt.knows(n) for n in names))

    def test_행은_투영과_출처를_싣는다(self):
        from django.core.management import call_command
        call_command("seed_catalog", verbosity=0)
        rows = {}
        for group in self.client.get("/GSM/catalog/").json().get("groups", []):
            for layer in group["layers"]:
                rows[layer["name"]] = layer
        self.assertEqual(rows["gmrt:sp"]["projection"], "EPSG:3031")
        self.assertEqual(rows["gmrt:np_mask"]["projection"], "EPSG:3995")
        self.assertIn("not for navigation", rows["gmrt:np"]["attribution"])
