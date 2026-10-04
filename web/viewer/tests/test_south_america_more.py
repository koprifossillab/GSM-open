"""남미 나머지 — 파라과이 VMME 와 USGS 남미 지질도 (wetherilli 256). 상류는 바꿔 끼운다.

꼴은 2026-10-05 에 받아 본 그대로다 — 둘 다 ArcGIS Online 피처 서비스의 GeoJSON 쪽.
"""
import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import usgscarib, views, vmme

POLY = {"type": "Polygon", "coordinates": [[[-57.6, -25.3], [-57.5, -25.3], [-57.5, -25.2], [-57.6, -25.3]]]}
PY = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": POLY, "properties": {"Cod_": "Q2", "Descrip_": "Sedimentos Cuaternarios"}},
    {"type": "Feature", "geometry": POLY, "properties": {"Cod_": "E", "Descrip_": "Grupo Itapucumi"}}]}
SA = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": POLY, "properties": {"GLG": "Cv"}},
    {"type": "Feature", "geometry": POLY, "properties": {"GLG": "Q"}},
    {"type": "Feature", "geometry": POLY, "properties": {"GLG": "U"}}]}
SA_LAYER = {"drawingInfo": {"renderer": {"uniqueValueInfos": [
    {"value": "Cv", "label": "Cv Cretaceous-Tertiary volcanics", "symbol": {"color": None}},
    {"value": "Q", "label": "Q Quaternary", "symbol": {"color": [255, 255, 207, 255]}},
    {"value": "U", "label": "U Unmapped Area", "symbol": {"color": [0, 0, 0, 0]}}]}}}


def response(body):
    return mock.Mock(status_code=200, headers={"content-type": "application/json"}, content=json.dumps(body).encode(),
                     url="https://x/", json=lambda: body)


class SouthAmericaMore(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-sa-more-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_파라과이(self):
        with mock.patch("viewer.vmme.requests.get", return_value=response(PY)):
            out = json.loads(vmme.body(vmme.NAME))
        first, second = (f["properties"] for f in out["features"])
        self.assertEqual((first["code"], first["age"], first["name"]), ("Q2", "제4기", "Sedimentos Cuaternarios"))
        self.assertNotIn("age", second)                                   # E 는 시대를 비워 둔다
        self.assertEqual([r["code"] for r in out["legend"]], ["Q2", "E"])  # 범례는 시대 차례

    def test_USGS_남미(self):
        fake = lambda url, params=None, **kw: response(SA if url.endswith("/query") else SA_LAYER)  # noqa: E731
        with mock.patch("viewer.usgscarib.requests.get", side_effect=fake):
            out = json.loads(usgscarib.body(usgscarib.SA_NAME))
        props = [f["properties"] for f in out["features"]]
        self.assertEqual(len(props), 2)                                    # U(미조사)는 싣지 않는다
        self.assertEqual((props[0]["color"], props[0]["desc"]), ("#f08a4b", "Cretaceous-Tertiary volcanics"))
        self.assertEqual(props[1]["color"], "#ffffcf")

    def test_탭과_묶음(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        self.assertEqual(rows["vmme:geology"][0]["region"], "paraguay")
        self.assertEqual(rows["usgscarib:sa:geology"][0]["region"], "colombia")
        self.assertEqual(rows["usgscarib:sa:geology"][1]["kind"], "points")
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        sa = re.search(r'south_america: \{ title: "남미".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        self.assertIn('"paraguay"', sa)
        with mock.patch("viewer.vmme.requests.get", return_value=response(PY)):
            got = self.client.get("/GSM/points/", {"layer": "vmme:geology"})
        self.assertEqual(got.status_code, 200)
