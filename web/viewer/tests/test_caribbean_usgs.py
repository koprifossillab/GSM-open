"""카리브 — USGS 카리브 지질도를 면 한 덩이로 (wetherilli 248). 상류는 바꿔 끼운다.

꼴은 2026-10-05 에 받아 본 그대로다 — 피처 서비스의 GeoJSON 쪽(2 000 개씩)과 칠하기 규칙(AGE 73 칸, 색이 빈 칸이 있다).
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import usgscarib, views

SQUARE = {"type": "Polygon", "coordinates": [[[-77.0, 18.0], [-76.9, 18.0], [-76.9, 18.1], [-77.0, 18.0]]]}
PAGE = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": SQUARE, "properties": {"AGE": "Tpm", "DESCRPTN": "Pliocene and Miocene strata"}},
    {"type": "Feature", "geometry": SQUARE, "properties": {"AGE": "Kv", "DESCRPTN": "Cretaceous volcanic rocks"}},
    {"type": "Feature", "geometry": SQUARE, "properties": {"AGE": " ", "DESCRPTN": ""}}]}
LAYER = {"drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "AGE", "uniqueValueInfos": [
    {"value": "Tpm", "label": "Tpm Pliocene and Miocene strata", "symbol": {"color": [230, 164, 138, 255]}},
    {"value": "Kv", "label": "Kv Cretaceous volcanic rocks", "symbol": {"color": None}},
    {"value": "Und", "label": "Und Undetermined", "symbol": {"color": [225, 225, 225, 255]}}]}}}


def response(body):
    return mock.Mock(status_code=200, headers={"content-type": "application/json"}, content=json.dumps(body).encode(),
                     url="https://x/", json=lambda: body)


class Caribbean(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-carib-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def fake(self, url, params=None, **kw):
        return response(PAGE if url.endswith("/query") else LAYER)

    def test_한_덩이(self):
        with mock.patch("viewer.usgscarib.requests.get", side_effect=self.fake) as get:
            out = json.loads(usgscarib.body("usgscarib:geology"))
            calls = get.call_count
            json.loads(usgscarib.body("usgscarib:geology"))
            self.assertEqual(get.call_count, calls)                           # 두 번째는 캐시에서
        self.assertEqual(out["style"], "unit")
        props = [f["properties"] for f in out["features"]]
        self.assertEqual(props[0], {"code": "Tpm", "color": "#e6a48a", "desc": "Pliocene and Miocene strata"})
        self.assertEqual(props[1]["color"], "#7fc64e")                       # 색이 빈 칸은 시대 글자(K)로 갈음
        self.assertEqual(props[2]["code"], "Und")                            # 빈 기호는 Und
        self.assertEqual({r["code"] for r in out["legend"]}, {"Tpm", "Kv", "Und"})

    def test_점_레이어_길과_카탈로그(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["usgscarib:geology"]
        self.assertEqual((group["region"], layer["kind"], layer["render"]), ("caribbean", "points", "image"))
        with mock.patch("viewer.usgscarib.requests.get", side_effect=self.fake):
            got = self.client.get("/GSM/points/", {"layer": "usgscarib:geology"})
        self.assertEqual((got.status_code, got["Content-Type"]), (200, "application/geo+json"))
