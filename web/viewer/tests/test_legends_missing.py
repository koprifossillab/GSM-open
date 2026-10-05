"""누르기·범례가 둘 다 없던 레이어 — 대만 민감구역·GA 지구물리 격자·페루 부게 이상 (wetherilli 336). 상류를 부르지 않는다."""
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import ga, gsmma, ingemmet, twopen

SQUARE = {"type": "Polygon", "coordinates": [[[120.0, 23.0], [121.0, 23.0], [121.0, 24.0], [120.0, 24.0], [120.0, 23.0]]]}
CSV = ("﻿No.,地質敏感區類型,地質敏感區編號,地質敏感區名稱,公告日期,文號,座標系統1,座標系統2,下載連結\n"
       "1,活動斷層地質敏感區,F0001,車籠埔斷層,103年1月20日,經地字第1號,中央經線121,TWD97,x\n"
       "6,山崩與地滑地質敏感區,L0002,南投縣-01,103年3月31日,經地字第2號,中央經線121,TWD97,x\n"
       "18,山崩與地滑地質敏感區,L0002,南投縣-02,103年12月31日,經地字第3號,中央經線121,TWD97,x\n")


def answer(body=None, status=200):
    r = mock.Mock(status_code=status, content=b"{}", url="…", headers={"content-type": "application/json"})
    r.json = lambda: body
    return r


class Sensitive(SimpleTestCase):
    def test_공고_목록과_이름(self):
        notices = gsmma.sensitive_notices(CSV)
        self.assertEqual(notices["F0001"], {"name": "車籠埔斷層", "date": "103年1月20日", "doc": "經地字第1號"})
        self.assertEqual(notices["L0002"]["name"], "南投縣")
        self.assertEqual(notices["L0002"]["date"], "103年3月31日 · 103年12月31日")
        self.assertEqual(gsmma.sensitive_code({"gid": "18092-L0002_2"}), "L0002")
        self.assertEqual(gsmma.sensitive_code({"Gid": "1070-L0001"}), "L0001")
        self.assertEqual(gsmma.sensitive_names('E("F0001","車籠埔斷層",p),E("H0003","暖暖壺穴",d)'),
                         [("F0001", "車籠埔斷層"), ("H0003", "暖暖壺穴")])

    def test_모아_둔_면에서_누른다(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(TAIWAN_OPEN_DIR=folder):
            twopen.write_sensitive([
                ("F:車籠埔斷層", [{"kind": "F", "code": "F0001", "name": "車籠埔斷層", "town": "", "date": "103年1月20日", "doc": "",
                                  "geometry": SQUARE}]),
                ("L:南投縣:仁愛鄉", [{"kind": "L", "code": "L0002", "name": "南投縣", "town": "仁愛鄉", "date": "", "doc": "",
                                    "geometry": {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]}}]),
            ], Path(folder) / twopen.SENSITIVE_FILE)
            self.assertEqual(twopen.sensitive_at("G", 120.5, 23.5), [])
            self.assertEqual(twopen.sensitive_at("F", 122.0, 23.5), [])
            q = {"layers": "gsmma:sensitive_fault", "query_layers": "gsmma:sensitive_fault", "crs": "EPSG:4326", "version": "1.3.0",
                 "bbox": "23,120,24,121", "width": 256, "height": 256, "i": 128, "j": 128}
            got = gsmma.get_feature_info(q)["features"]
            self.assertEqual(len(got), 1)
            self.assertEqual(gsmma.friendly(got[0]["properties"]),
                             {"갈래": "활성단층 민감구역", "구역": "車籠埔斷層", "구역 번호": "F0001", "공고일": "103年1月20日"})
            self.assertEqual(gsmma.friendly(got[0]["properties"], "en")["갈래"], "Active fault sensitive area")
            self.assertTrue(gsmma.queryable("gsmma:sensitive_landslide"))

    def test_파일이_없으면_빈_것(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(TAIWAN_OPEN_DIR=folder):
            self.assertEqual(twopen.sensitive_at("F", 120.5, 23.5), [])


class Grids(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ga.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_GA_방사능은_값_격자_셋(self):
        body = {"features": [{"properties": {"GRAY_INDEX": 1.6198}}, {"properties": {"GRAY_INDEX": 26.74}},
                             {"properties": {"GRAY_INDEX": -3.4e38}}]}
        with mock.patch.object(ga.requests, "get", return_value=answer(body)) as get:
            got = ga.get_feature_info({"layers": "ga:radiometric", "query_layers": "ga:radiometric", "crs": "EPSG:3857",
                                       "bbox": "0,0,1,1", "width": 256, "height": 256, "i": 1, "j": 1})
        self.assertIn("radmap_v4_2019_filtered_ppmth", get.call_args.kwargs["params"]["query_layers"])
        self.assertEqual(ga.friendly(got["features"][0]["properties"]), {"칼륨 (%)": "1.62", "토륨 (ppm)": "26.7"})
        self.assertTrue(ga.queryable("ga:gravity"))

    def test_페루_부게_이상(self):
        body = {"results": [{"attributes": {"Stretch.Pixel Value": "-313.663544"}}]}
        with mock.patch.object(ingemmet, "_get", return_value=answer(body)):
            rows = ingemmet.resource_attributes("ingemmet:bouguer", -12.0, -75.0, 0.01)
        self.assertEqual(ingemmet.resource_friendly("ingemmet:bouguer", rows[0]), {"부게 이상 (mGal)": "-313.7"})
        self.assertTrue(ingemmet.knows_resource("ingemmet:bouguer"))


AREA = {"kind": "F", "code": "F0001", "name": "車籠埔斷層", "town": "", "date": "", "doc": "", "geometry": SQUARE}


class SensitiveRetry(SimpleTestCase):
    """끊기면 다시 묻고, 못 받은 것은 건너뛰어 적고, 다시 부르면 잇는다 (wetherilli 346)"""

    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(gsmma.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.slept = []

    def sleep(self, s):
        self.slept.append(s)

    def test_끊기면_쉬었다_다시_묻는다(self):
        ok = answer({"features": []})
        with mock.patch.object(gsmma.requests, "get", side_effect=[gsmma.requests.exceptions.SSLError("UNEXPECTED_EOF"), ok]) as get:
            r = gsmma._sensitive_get("https://x/", {}, 2.0, self.sleep)
        self.assertIs(r, ok)
        self.assertEqual(get.call_count, 2)
        self.assertIn(gsmma.SENSITIVE_RETRY[0], self.slept)

    def test_끝내_못_받으면_오류_차단이면_곧장(self):
        with mock.patch.object(gsmma.requests, "get", side_effect=gsmma.requests.exceptions.ConnectionError("끊김")) as get:
            with self.assertRaisesRegex(gsmma.GsmmaError, "끝내 받지 못했다"):
                gsmma._sensitive_get("https://x/", {}, 2.0, self.sleep)
        self.assertEqual(get.call_count, 1 + len(gsmma.SENSITIVE_RETRY))
        blocked = answer({}, status=403)
        blocked.content = b"Request Blocked"
        with mock.patch.object(gsmma.requests, "get", return_value=blocked) as get, \
                mock.patch.object(gsmma.usage, "looks_blocked", return_value=True):
            with self.assertRaisesRegex(gsmma.GsmmaError, "차단"):
                gsmma._sensitive_get("https://x/", {}, 2.0, self.sleep)
        self.assertEqual(get.call_count, 1)

    def test_받은_것은_건너뛰고_못_받은_것은_적고_잇는다(self):
        script = 'E("F0001","車籠埔斷層",p),E("F0002","池上斷層",p)'
        page = answer(None)
        page.text = script
        notices = answer(None)
        notices.content = CSV.encode("utf-8")

        def get(url, params=None, **kw):
            if url.endswith(".csv"):
                return notices
            if url.endswith(".js"):
                return page
            if url.endswith("LTown"):
                return answer({"data": []})
            if params.get("name") == "池上斷層":
                raise gsmma.requests.exceptions.SSLError("UNEXPECTED_EOF")
            return answer({"features": [{"geometry": SQUARE, "properties": {}}]})

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / twopen.SENSITIVE_FILE
            db, done, _ = twopen.open_sensitive(path)
            missing = []
            with mock.patch.object(gsmma.requests, "get", side_effect=get):
                for key, areas in gsmma.fetch_sensitive(gap=0, sleep=self.sleep, done=done, missing=missing):
                    twopen.add_sensitive(db, key, areas)
            self.assertEqual([k for k, _ in missing], ["F:池上斷層"])
            self.assertEqual(twopen.close_sensitive(db, path, missing), 1)
            self.assertTrue(path.exists(), "받은 만큼 파일을 쓴다")
            self.assertTrue(path.with_suffix(".part").exists(), "못 받은 것이 남으면 .part 를 남긴다")
            # 다시 부르면 받은 것은 묻지 않는다
            db, done, before = twopen.open_sensitive(path)
            self.assertEqual(done, {"F:車籠埔斷層"})
            self.assertEqual([k for k, _ in before], ["F:池上斷層"])
            asked = []

            def again(url, params=None, **kw):
                asked.append((params or {}).get("name"))
                return get(url, params) if (params or {}).get("name") != "池上斷層" else answer({"features": [{"geometry": SQUARE}]})

            missing = []
            with mock.patch.object(gsmma.requests, "get", side_effect=again):
                for key, areas in gsmma.fetch_sensitive(gap=0, sleep=self.sleep, done=done, missing=missing):
                    twopen.add_sensitive(db, key, areas)
            self.assertNotIn("車籠埔斷層", asked)
            self.assertEqual(twopen.close_sensitive(db, path, missing), 2)
            self.assertFalse(path.with_suffix(".part").exists())

    def test_옛_판의_part_는_버린다(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / twopen.SENSITIVE_FILE
            old = sqlite3.connect(path.with_suffix(".part"))
            old.executescript("CREATE TABLE area (id INTEGER PRIMARY KEY, kind TEXT); INSERT INTO area VALUES (1, 'F');")
            old.close()
            db, done, missing = twopen.open_sensitive(path)
            self.assertEqual((done, missing, db.execute("SELECT count(*) FROM area").fetchone()[0]), (set(), [], 0))
            db.close()
