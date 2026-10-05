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


class IrgmFaults(SimpleTestCase):
    """카메룬 단층 — 상류의 기본 스타일이 없는 기호 파일을 찾다 깨져 스타일을 우리가 보낸다 (wetherilli 308)"""

    def test_단층은_SLD_BODY_로(self):
        from viewer import brgm
        with mock.patch.object(brgm.usage, "record"), mock.patch.object(brgm.usage, "paused", return_value=0), \
                mock.patch.object(brgm.requests, "get", return_value=answer()) as get:
            brgm.irgm_get_map({"layers": "irgm:CMR_IRGM_1M_Failles", "crs": "EPSG:4326", "version": "1.3.0",
                               "bbox": "2,9,11,16", "width": 256, "height": 256})
        sent = get.call_args.kwargs["params"]
        self.assertIn("<LineSymbolizer>", sent["SLD_BODY"])
        self.assertEqual(sent["bbox"], "9,2,16,11")                     # 1.3.0 의 4326 은 위도가 먼저다
        with mock.patch.object(brgm.usage, "record"), mock.patch.object(brgm.usage, "paused", return_value=0), \
                mock.patch.object(brgm.requests, "get", return_value=answer()) as get:
            brgm.irgm_get_map({"layers": "irgm:CMR_IRGM_1M_UnitesGeologiques", "crs": "EPSG:4326", "bbox": "9,2,16,11",
                               "width": 256, "height": 256})
        self.assertNotIn("SLD_BODY", get.call_args.kwargs["params"])
