"""다누리 KMAG 궤적 (wetherilli 377) — KPDS 의 문과 줄여 담은 sqlite."""
import io
import tempfile
import zipfile

import json
from datetime import timedelta
from unittest import mock
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from viewer import kmag, kpds

URL = "https://kpds.test/kpds"
HEAD = "UTC,X_SEL,Y_SEL,Z_SEL,Bx_SEL,By_SEL,Bz_SEL,X_SSE,Y_SSE,Z_SSE,Bx_SSE,By_SSE,Bz_SSE\n"


def day_csv(start="2025-03-31T00:00:00", n=40):
    """적도 위 고도 60 km 를 동쪽으로 도는 궤도 — 4 초마다 0.05°."""
    import math
    from datetime import datetime, timedelta
    t0 = datetime.fromisoformat(start)
    lines = [HEAD]
    for k in range(n):
        lon = math.radians(10 + 0.05 * k)
        r = kmag.RADIUS + 60
        b = "-99999,-99999,-99999" if k == 8 else "3,4,0"
        lines.append(f"{(t0 + timedelta(seconds=4 * k)).isoformat()}.000,{r * math.cos(lon):.2f},{r * math.sin(lon):.2f},0,"
                     f"{b},0,0,0,0,0,0\n")
    return "".join(lines)


class Parse(SimpleTestCase):
    def test_32_초마다_한_점(self):
        pts = kmag.parse(day_csv())
        self.assertEqual(len(pts), 5)                              # 40 행 × 4 초 = 160 초
        sec, lon, lat, alt, b = pts[0]
        self.assertAlmostEqual(lon, 10.0, places=3)
        self.assertAlmostEqual(lat, 0.0, places=3)
        self.assertAlmostEqual(alt, 60.0, places=1)
        self.assertEqual(b, 5.0)
        self.assertIsNone(pts[1][4])                               # 빈 값은 |B| 만 비운다

    def test_달에서_먼_자리는_버린다(self):
        far = HEAD + "2022-09-02T00:00:00.000,300000,0,0,1,1,1,0,0,0,0,0,0\n"
        self.assertEqual(kmag.parse(far), [])


class Store(SimpleTestCase):
    def setUp(self):
        patch = override_settings(KPDS_DIR=tempfile.mkdtemp(prefix="gsm-kmag-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_없으면_비었다(self):
        self.assertFalse(kmag.available())
        self.assertEqual(kmag.tracks(-180, -90, 180, 90), [])
        self.assertIsNone(kmag.nearest(0, 0))
        self.assertEqual(kmag.stamp(), "")

    def test_더하고_읽는다(self):
        conn = kmag.connect(write=True)
        self.assertEqual(kmag.add_day(conn, "A", kmag.parse(day_csv())), 5)
        self.assertEqual(kmag.add_day(conn, "A", kmag.parse(day_csv())), 0)      # 같은 날은 한 번만
        kmag.add_day(conn, "B", kmag.parse(day_csv("2025-03-31T01:00:00")))
        conn.close()
        lines = kmag.tracks(0, -5, 20, 5)
        self.assertEqual(len(lines), 2)                            # 한 시간 벌어진 두 궤적은 잇지 않는다
        hit = kmag.nearest(10.05, 0.01)
        self.assertEqual(hit["b"], 5.0)
        self.assertEqual(hit["alt"], 60.0)
        self.assertTrue(hit["time"].startswith("2025-03-31 00:00:"))
        self.assertIsNone(kmag.nearest(100, 50))
        self.assertEqual(kmag.summary()["days"], 2)


class Answer:
    def __init__(self, body):
        self.content = body if isinstance(body, bytes) else json.dumps(body).encode() if not isinstance(body, str) else body.encode()
        self.status_code = 200
        self.elapsed = timedelta(seconds=0.1)

    def json(self):
        return json.loads(self.content)


def fake_kpds(listing, files):
    """KPDS 를 흉내 낸다 — 부른 것을 `calls` 에 적는다."""
    calls = []

    def request(self, method, url, **kw):
        calls.append((method, url, kw))
        if url.endswith("/search_view/levelproduct"):
            return Answer("ok")
        if url.endswith("/search/dataTableList"):
            return Answer(listing)
        name = url.rsplit("/", 1)[-1]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for fname, body in files[name].items():
                z.writestr(fname, body)
        return Answer(buf.getvalue())
    return calls, mock.patch.object(kpds.requests.Session, "request", request)


@override_settings(KPDS_URL=URL)
class Door(SimpleTestCase):
    def test_목록은_썸네일을_버리고_내려받기는_zip_을_푼다(self):
        listing = {"recordsFiltered": 1, "data": [
            {"_id": ["7"], "identifierS": "urn:kari:kpds:kplo.kmag:data.cal:x", "metaFileName": ["X_CAL_M_01.xml"],
             "startDate": ["2025-03-31T00:00:00Z"], "allFileSize": [10], "imgSrc": "data:image/png;base64,AAAA"}]}
        calls, patch = fake_kpds(listing, {"X_CAL_M_01": {"X_CAL_M_01.csv": "a,b\n"}})
        with patch:
            s = kpds.session()
            total, rows = kpds.search(s, "kmag", "Calibrated")
            got = kpds.download(s, "X_CAL_M_01.xml")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["meta"], "X_CAL_M_01.xml")
        self.assertNotIn("imgSrc", rows[0])
        self.assertEqual(calls[1][2]["data"]["param[processing_level_ss]"], "(Calibrated)")
        self.assertEqual(calls[1][2]["data"]["param[_txt]"], "(*kmag*)")
        self.assertEqual(got, {"X_CAL_M_01.csv": b"a,b\n"})

    def test_명령은_새_날만_받는다(self):
        listing = {"recordsFiltered": 1, "data": [{"_id": ["7"], "metaFileName": ["D1_CAL_M_01.xml"]}]}
        calls, patch = fake_kpds(listing, {"D1_CAL_M_01": {"D1_CAL_M_01.csv": day_csv()}})
        with patch, override_settings(KPDS_DIR=tempfile.mkdtemp(prefix="gsm-kmag-")):
            call_command("fetch_kmag", stdout=io.StringIO())
            call_command("fetch_kmag", stdout=io.StringIO())
            self.assertEqual(kmag.summary()["points"], 5)
        self.assertEqual(len([c for c in calls if "/download/" in c[1]]), 1)


class Moon(SimpleTestCase):
    """달 화면 — 궤적 타일과 누른 자리 (wetherilli 378)."""

    def setUp(self):
        patch = override_settings(KPDS_DIR=tempfile.mkdtemp(prefix="gsm-kmag-"))
        patch.enable()
        self.addCleanup(patch.disable)
        kmag._orbit_count.cache_clear()

    def add(self, n=400):
        conn = kmag.connect(write=True)
        kmag.add_day(conn, "kplo_kmag_250331", kmag.parse(day_csv(n=n)))
        conn.close()

    def png(self, url):
        from PIL import Image
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        return Image.open(io.BytesIO(r.content)).convert("RGBA")

    def test_파일이_없으면_안내_타일(self):
        img = self.png("/GSM/moon/tiles/kmag/0/1/0.png")
        self.assertEqual(img.getpixel((5, 5))[3], 235)               # 안내 타일의 바탕

    def test_궤적을_한_색으로_긋는다(self):
        self.add()
        img = self.png("/GSM/moon/tiles/kmag/0/1/0.png")              # 동반구 — 적도의 경도 10–13°
        y = 128                                                        # 적도
        x = int((11 - 0) / 180 * 256)
        r, g, b, a = img.getpixel((x, y))
        self.assertGreater(a, 0)
        self.assertGreater(b, r)                                       # |B| 와 상관없는 한 색(하늘빛)
        self.assertEqual(self.png("/GSM/moon/tiles/kmag/0/0/0.png").getextrema()[3], (0, 0))   # 서반구는 비었다

    def test_극_타일(self):
        self.add()
        self.assertEqual(self.client.get("/GSM/moon/ptiles/n/kmag/0/0/0.png").status_code, 200)
        self.assertEqual(self.client.get("/GSM/moon/ptiles/n/kmag/0/5/0.png").status_code, 404)

    def test_누른_자리(self):
        self.add()
        rows = dict(self.client.get("/GSM/moon/info/?layer=kmag&lon=10.02&lat=0.1").json()["rows"])
        self.assertEqual(rows["시각"], "2025-03-31 00:00:00 UTC")
        self.assertEqual(rows["고도"], "60.0 km")
        self.assertEqual(rows["자기장 세기 |B|"], "5.00 nT")
        self.assertIn("지각 자기 이상이 아니다", rows["주의"])
        empty = dict(self.client.get("/GSM/moon/info/?layer=kmag&lon=10.4&lat=0").json()["rows"])
        self.assertEqual(empty["자기장 세기 |B|"], "—")                   # 빈 값은 자리만
        far = self.client.get("/GSM/moon/info/?layer=kmag&lon=-100&lat=40").json()
        self.assertEqual(far["rows"], [])
        self.assertIn("note", far)

    def test_영어판(self):
        self.add()
        self.client.cookies["gsm_lang"] = "en"
        rows = dict(self.client.get("/GSM/moon/info/?layer=kmag&lon=10.02&lat=0.1").json()["rows"])
        self.assertIn("Field strength |B|", rows)
        self.assertIn("not a crustal magnetic anomaly", rows["Note"])

    def test_넓게_보면_궤도를_솎는다(self):
        self.add()
        self.assertEqual(kmag._orbits(0), 1)                           # 하루치 열둘 — 끝(240)보다 적다
        with mock.patch.object(kmag, "_orbit_count", return_value=12000):
            self.assertEqual(kmag._orbits(0), 50)
            self.assertEqual(kmag._orbits(6), 1)
