"""미국 주 지질도 셋 (wetherilli 291) — 네바다 NBMG·워싱턴 DNR·오리건 DOGAMI. 상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import usstates

LCC = {"crs": "EPSG:3978", "bbox": "-1988000,-903000,-1982000,-897000", "width": 101, "height": 101}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Door(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(usstates.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_REST_export_를_3978_로(self):
        with mock.patch.object(usstates.requests, "get", return_value=answer()) as get:
            usstates.DOGAMI.get_map(dict(LCC, layers="dogami:ogdc"))
        self.assertEqual(get.call_args.args[0], "https://gis.dogami.oregon.gov/arcgis/rest/services/Public/OGDC6/MapServer/export")
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["bboxSR"], sent["imageSR"], sent["layers"]), ("3978", "3978", "show:3,0,1"))
        with self.assertRaises(usstates.UsStatesError):
            usstates.NBMG.get_map(dict(LCC, layers="dogami:ogdc"))          # 문이 다른 상류의 레이어를 받지 않는다

    def test_워싱턴_1_50만은_단위_표를_붙인다(self):
        identify = {"results": [{"attributes": {"Map Unit": "Tc", "Label": "Tc"}}]}
        units = {"features": [{"attributes": {"Map_Unit": "Tc", "Name": "Tertiary continental sedimentary rocks", "Age": "Tertiary",
                                              "Description": "Pliocene gravel", "GeoMaterial": "Sedimentary material"}}]}
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-us-")), \
                mock.patch.object(usstates.requests, "get", side_effect=[answer(identify, "application/json"), answer(units, "application/json")]):
            got = usstates.WADNR.get_feature_info(dict(LCC, layers="wadnr:500k", query_layers="wadnr:500k", i=50, j=50))
        props = usstates.friendly(got["features"][0]["properties"])
        self.assertEqual((props["기호"], props["이름"], props["지질시대"]), ("Tc", "Tertiary continental sedimentary rocks", "제3기"))

    def test_속성(self):
        nv = usstates.friendly({"Name": "ALL UVIAL DEPOSITS", "Lithology": "Unconsolidated", "Geologic History": "Quaternary", "Unit Symbol": "Qa"})
        self.assertEqual((nv["기호"], nv["이름"], nv["지질시대"]), ("Qa", "All Uvial Deposits", "제4기"))
        oregon = usstates.friendly({"MAP_UNIT_L": "Tc", "AGE_NAME": "Eocene/Oligocene", "FORMATION": "Clarno Formation", "MEMBER": "No data"})
        self.assertEqual((oregon["지층"], oregon["지질시대"]), ("Clarno Formation", "에오세~올리고세"))
        self.assertEqual(usstates.friendly({"MAP_UNIT_100K": "Evb(t)", "MAP_UNIT_100K_SYMBOL": "Tertiary volcanic rocks"})["이름"],
                         "Tertiary volcanic rocks")


class Catalog(TestCase):
    def test_주_밖은_묻지_않는다(self):
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-us-cat-")):
            call_command("seed_catalog", stdout=io.StringIO())
            layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        for name in ("nbmg:geology", "wadnr:500k", "wadnr:100k", "dogami:ogdc"):
            self.assertEqual((layers[name]["projection"], layers[name]["clip"], layers[name]["legend"]), ("EPSG:3978", True, "list"))
        self.assertEqual(layers["dogami:ogdc"]["minZoom"], 7)
