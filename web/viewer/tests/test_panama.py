"""파나마 — STRI 의 MICI 1990 1:25만, 면·단층을 한 덩이씩 (wetherilli 253). 상류는 바꿔 끼운다."""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import stri, views

LINE = {"type": "LineString", "coordinates": [[-80.0, 8.5], [-79.9, 8.6]]}
POLY = {"type": "Polygon", "coordinates": [[[-80.0, 8.5], [-79.9, 8.5], [-79.9, 8.6], [-80.0, 8.5]]]}
UNITS = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": POLY, "properties": {"SIMBOLO": "TM-CATu", "GRUPO": "Cañazas", "FORMACION": "Tucué",
                                                        "FORMAS": "Volcánicas", "LEYENDA": "Andesitas/basaltos, lavas, brechas"}},
    {"type": "Feature", "geometry": POLY, "properties": {"SIMBOLO": "K-AR", "GRUPO": " ", "FORMACION": "Armila",
                                                        "FORMAS": "Plutónicas", "LEYENDA": "Intrusivos ultrabásicos"}}]}
LINES = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": LINE, "properties": {"OBJECTID": 1}}]}
LAYER = {"drawingInfo": {"renderer": {"uniqueValueInfos": [{"value": "TM-CATu", "symbol": {"color": [230, 152, 0, 255]}},
                                                           {"value": "K-AR", "symbol": {"color": [179, 169, 136, 255]}}]}}}


def response(body):
    return mock.Mock(status_code=200, headers={"content-type": "application/json"}, content=json.dumps(body).encode(),
                     url="https://x/", json=lambda: body)


def fake(url, params=None, **kw):
    if url.endswith("/13/query"):
        return response(UNITS)
    if url.endswith("/query"):
        return response(LINES)
    return response(LAYER)


class Ages(SimpleTestCase):
    def test_기호의_앞머리(self):
        self.assertEqual(stri.age_of("TM-CATu"), "Miocene")
        self.assertEqual(stri.age_of("PI/PS-Cv"), "Pliocene – Pleistocene")
        self.assertEqual(stri.age_of("No data"), "")


class Panama(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-panama-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_면과_단층(self):
        with mock.patch("viewer.stri.requests.get", side_effect=fake):
            geo = json.loads(stri.body(stri.GEOLOGY))
            lines = json.loads(stri.body(stri.FAULTS))
        first = geo["features"][0]["properties"]
        self.assertEqual((first["code"], first["color"], first["name"], first["age"]),
                         ("TM-CATu", "#e69800", "Tucué · Cañazas", "마이오세"))
        self.assertEqual(geo["features"][1]["properties"]["name"], "Armila")          # 빈 층군은 빼고
        self.assertEqual(lines["style"], "line")
        self.assertEqual({r["code"] for r in lines["legend"]}, {"3", "4", "5"})        # 단층 세 갈래

    def test_카탈로그와_점_레이어_길(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["stri:geology"]
        self.assertEqual((group["region"], layer["kind"], layer["style"]), ("panama", "points", "unit"))
        self.assertEqual(rows["stri:faults"][1]["style"], "line")
        with mock.patch("viewer.stri.requests.get", side_effect=fake):
            got = self.client.get("/GSM/points/", {"layer": "stri:faults"})
        self.assertEqual(got.status_code, 200)
