"""최근 지진 — USGS 실시간 피드(지난 7 일 M2.5 이상)를 매시 받아 둔다 (wetherilli 292). 상류는 바꿔 끼운다."""
import datetime
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from viewer import earthpoints, recentquakes, usgs

NOW = 1_759_600_000_000                       # 피드를 지은 때(ms)
FEED = {"metadata": {"generated": NOW}, "features": [
    {"id": "us1", "properties": {"mag": 4.6, "magType": "mb", "time": NOW - 30 * 60000, "place": "near Jeju", "type": "earthquake"},
     "geometry": {"coordinates": [126.5, 33.2, 10.0]}},
    {"id": "us2", "properties": {"mag": 2.7, "magType": "ml", "time": NOW - 5 * 3600000, "place": "Gyeongju", "type": "earthquake"},
     "geometry": {"coordinates": [129.2, 35.8, 12.5]}},
    {"id": "us3", "properties": {"mag": 3.1, "magType": "ml", "time": NOW - 4 * 86400000, "place": "far", "type": "earthquake"},
     "geometry": {"coordinates": [-120.0, 36.0, 5.0]}},
    {"id": "ex1", "properties": {"mag": 2.9, "time": NOW, "place": "quarry", "type": "quarry blast"},
     "geometry": {"coordinates": [127.0, 37.0, 0.0]}}]}


class Recent(TestCase):
    def setUp(self):
        root = tempfile.mkdtemp(prefix="gsm-recent-")
        for patch in (override_settings(EARTH_DIR=root), override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-recent-tc-"))):
            patch.enable()
            self.addCleanup(patch.disable)
        r = mock.Mock(status_code=200, content=json.dumps(FEED).encode(), url=usgs.FEED, json=lambda: FEED,
                      elapsed=datetime.timedelta(seconds=0.4))
        with mock.patch.object(usgs.requests, "get", return_value=r) as get:
            call_command("fetch_recent_quakes", stdout=io.StringIO())
        self.assertEqual(get.call_count, 1)
        earthpoints._body.cache_clear()
        self.addCleanup(earthpoints._body.cache_clear)

    def test_받아_줄인다(self):
        data = json.loads(Path(recentquakes.path()).read_text())
        self.assertEqual([q["id"] for q in data["quakes"]], ["us1", "us2", "us3"])     # 발파는 뺀다
        self.assertEqual(data["generated"], NOW)

    def test_지난_시간의_칸(self):
        self.assertEqual([recentquakes.age_class(NOW - h * 3600000, NOW) for h in (0.5, 5, 96)], [0, 1, 2])
        self.assertEqual(recentquakes.colour(0), (0xff, 0x2d, 0x95))

    def test_타일과_누르기(self):
        got = self.client.get("/GSM/earth/recentquakes/tiles/2/6/1.png")             # 제주(126.5°E)를 덮는 칸 — 서쪽 끝 −180° + 6 × 45° = 90°E
        self.assertEqual(got.status_code, 200)
        self.assertTrue(any(p[3] for p in Image.open(io.BytesIO(got.content)).convert("RGBA").getdata()))
        hits = self.client.get("/GSM/earth/recentquakes/at/", {"lon": 126.5, "lat": 33.2, "r": 0.5}).json()["hits"]
        self.assertEqual(hits[0]["id"], "us1")
        self.assertIn("최근 지진", hits[0]["name"])

    def test_지역_탭은_고리(self):
        d = json.loads(earthpoints.body("earth:recentquakes_korea"))
        self.assertEqual([f["properties"]["code"] for f in d["features"]], ["r1", "r0"])  # 오래된 것 먼저, 최근 것이 위
        self.assertEqual({r["shape"] for r in d["legend"]}, {"ring"})
        self.assertEqual(d["features"][1]["properties"]["time"], recentquakes.when(NOW - 30 * 60000))
