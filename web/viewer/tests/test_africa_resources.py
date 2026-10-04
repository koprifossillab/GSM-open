"""남아공의 광업·자원 지역 (wetherilli 285) — 같은 DPME 서비스의 레이어 0·1·2. 상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import cgs, views

WMS = {"crs": "EPSG:3857", "bbox": "3000000,-3000000,3001200,-2998800", "width": 101, "height": 101}


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Door(SimpleTestCase):
    def test_레이어_번호(self):
        with mock.patch.object(cgs.requests, "get", return_value=answer()) as get:
            cgs.get_map(dict(WMS, layers="cgs:uranium"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:2")

    def test_속성(self):
        self.assertEqual(cgs.friendly({"OBJECTID": 1, "Name": " ", "Fields": "Mozaan group", "resource": "Uranium"}),
                         {"광종": "Uranium", "층군": "Mozaan group"})
        self.assertEqual(cgs.friendly({"OID": 1, "Name": "New mining"}), {"광업 지역": "New mining"})

    def test_파는_자료는_담지_않는다(self):
        self.assertIn("cgs", views.NO_STORE)


class Catalog(TestCase):
    def test_석탄은_누르지_않는다(self):
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-af-res-")):
            call_command("seed_catalog", stdout=io.StringIO())
            layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"] for l in g["layers"]}
        self.assertFalse(layers["cgs:coal"]["queryable"])
        self.assertNotIn("queryable", {k: v for k, v in layers["cgs:uranium"].items() if v is False})
