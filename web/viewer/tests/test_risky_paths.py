"""시험이 지나가지 않던 위험한 길 (wetherilli 349) — 키·주소를 다루는 곳. coverage 로 찾았다.

상류를 부르지 않는다 — `requests.get` 과 이름 풀기를 갈아 끼운다. 지키는 것은 셋이다.
- 키는 오류 글·로그에 남지 않는다(예외 문구에 URL 이 실려 온다)
- 키가 없으면 묻지 않고, 묻지 않는 곳(GeoServer)에는 키를 싣지 않는다
- 연결 레이어의 문은 읽지 못하는 주소·이름·포트에서 멈추고, 끊기거나 넘겨받을 곳이 없을 때 까닭을 말한다
"""
import logging
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from viewer import kigam, linked, vworld
from viewer.tests.test_linked import HOSTS, Response, Session, resolves, sessions

KEY = "SECRET-KEY-1234"


def answer(status=200, ctype="image/png", content=b"\x89PNG", body=None):
    r = mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://data.kigam.re.kr/openapi/wms?key=" + KEY,
                  text=(content or b"").decode("latin-1"), elapsed=None)
    if body is not None:
        r.json.return_value = body
    else:
        r.json.side_effect = ValueError("not json")
    return r


class KigamKey(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(kigam.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False)
    def test_키가_없으면_묻지_않는다(self):
        with mock.patch.object(kigam.requests, "get") as get, self.assertRaises(kigam.UpstreamError) as caught:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        get.assert_not_called()
        self.assertIn("인증키가 없다", str(caught.exception))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_닿지_못한_까닭에_키가_없다(self):
        boom = requests.ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /openapi/wms?key={KEY}&layers=x")
        with mock.patch.object(kigam.requests, "get", side_effect=boom), self.assertRaises(kigam.UpstreamError) as caught:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertNotIn(KEY, str(caught.exception))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=True)
    def test_개발_스위치면_키를_싣지_않는다(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer()) as get:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertNotIn("key", get.call_args.kwargs["params"])

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_로그에_키가_없다(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer()), self.assertLogs("viewer.kigam", logging.INFO) as logs:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertFalse([line for line in logs.output if KEY in line])

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_그림이_아니면_오류(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html>error</html>")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_legend("L_250K_Geology_Map")

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_속성은_키_없이_GeoServer_로_JSON_이_아니면_오류(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")) as get, \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_feature_info({"layers": "L_250K_Geology_Map", "query_layers": "L_250K_Geology_Map"})
        self.assertNotIn("key", get.call_args.kwargs["params"])
        with mock.patch.object(kigam.requests, "get", return_value=answer(status=500, ctype="text/html", content=b"x")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_feature_info({"layers": "L_250K_Geology_Map"})

    def test_속성_길이_열렸는지_찔러보기(self):
        with override_settings(KIGAM_KEY=""):
            self.assertIn("인증키가 없어", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
        with override_settings(KIGAM_KEY=KEY):
            with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="application/json", body={"features": []})):
                self.assertTrue(kigam.probe_openapi_feature_info("L", "0,0,1,1").startswith("열렸다"))
            with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")):
                self.assertIn("아직 막혀 있다", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
            with mock.patch.object(kigam.requests, "get", return_value=answer(status=500, ctype="text/html", content=b"x")):
                self.assertIn("status=500", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
            boom = requests.ConnectionError(f"url: /openapi/wms?key={KEY}")
            with mock.patch.object(kigam.requests, "get", side_effect=boom):
                said = kigam.probe_openapi_feature_info("L", "0,0,1,1")
            self.assertIn("닿지 못했다", said)
            self.assertNotIn(KEY, said)


@override_settings(VWORLD_KEY=KEY)
class VWorldKey(SimpleTestCase):
    def test_국가중점데이터가_닿지_못한_까닭에_키가_없다(self):
        boom = requests.ConnectionError(f"Max retries exceeded with url: /ned/data/ladfrlList?key={KEY}&pnu=1")
        with mock.patch.object(vworld.requests, "get", side_effect=boom), self.assertRaises(vworld.VWorldError) as caught:
            vworld._ned(vworld.LAND_URL, {"pnu": "1"})
        self.assertNotIn(KEY, str(caught.exception))

    def test_국가중점데이터가_알아볼_수_없는_것을_주면(self):
        bad = mock.Mock(status_code=502, url=f"https://api.vworld.kr/ned?key={KEY}")
        bad.json.side_effect = ValueError("no")
        with mock.patch.object(vworld.requests, "get", return_value=bad), self.assertLogs("viewer.vworld", logging.INFO) as logs, \
             self.assertRaises(vworld.VWorldError):
            vworld._ned(vworld.LAND_URL, {"pnu": "1"})
        self.assertFalse([line for line in logs.output if KEY in line])


@override_settings(LINKED_ALLOW=[])
class LinkedEdges(SimpleTestCase):
    def setUp(self):
        for name in ("record",):
            p = mock.patch.object(linked.usage, name)
            p.start()
            self.addCleanup(p.stop)

    def test_읽지_못하는_주소·포트·이름(self):
        with self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("http://[::1")                       # 닫히지 않은 IPv6 괄호
        self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("http://api.example.org:99999/x")     # 포트가 범위 밖
        self.assertEqual(caught.exception.status, 400)
        with resolves(HOSTS), self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("https://nowhere.example.org/x")
        self.assertEqual(caught.exception.status, 502)
        with mock.patch("viewer.linked.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("not-an-ip", 443))]), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("https://odd.example.org/x")          # 풀린 것이 IP 가 아니다
        self.assertEqual(caught.exception.status, 502)

    def test_머리·질의_방식으로_키를_싣는다(self):
        headers = {}
        self.assertEqual(linked._with_auth("https://a/x", {"mode": "header", "name": "X-Api-Key", "key": KEY}, headers), "https://a/x")
        self.assertEqual(headers["X-Api-Key"], KEY)
        url = linked._with_auth("https://a/x?key=old&q=1", {"mode": "query", "name": "key", "key": KEY}, {})
        self.assertIn(f"key={KEY}", url)
        self.assertNotIn("old", url)                               # 같은 이름의 옛 값은 갈아 끼운다
        self.assertEqual(linked.redact("http://[::1", None), "?")

    def test_닿지_못하면_로그에_키_없이(self):
        auth = {"mode": "query", "name": "token", "key": KEY}
        boom = mock.Mock()
        boom.get.side_effect = requests.ConnectionError("down")
        boom.__enter__ = lambda s: s
        boom.__exit__ = lambda s, *a: False
        with resolves(HOSTS), mock.patch("viewer.linked._session", return_value=boom), \
             self.assertLogs("viewer.linked", logging.INFO) as logs, self.assertRaises(linked.LinkedError):
            linked.fetch("https://api.example.org/data.json", auth)
        self.assertFalse([line for line in logs.output if KEY in line])

    def test_빈_곳으로_넘기거나_주지_않으면_까닭을_말한다(self):
        with resolves(HOSTS), sessions({"https://api.example.org/a": Response(302, b"", {})}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/a", {"mode": "none"})
        self.assertIn("빈 곳", str(caught.exception.args[0].template))
        with resolves(HOSTS), sessions({"https://api.example.org/b": Response(500, b"oops")}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/b", {"mode": "none"})
        self.assertIn("주지 않았다", str(caught.exception.args[0].template))

    def test_받다가_끊기면(self):
        class Broken(Response):
            def iter_content(self, size):
                yield b"{"
                raise requests.ConnectionError("reset")
        with resolves(HOSTS), sessions({"https://api.example.org/c": Broken(200, b"")}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/c", {"mode": "none"})
        self.assertIn("끊겼다", str(caught.exception.args[0].template))
        self.assertTrue(Session.calls)


class TileRouteCache(SimpleTestCase):
    """타일 길의 캐시 차례 — 키가 없거나 상류가 못 주면 옛것, 자료를 파는 상류는 담지 않는다"""
    PARAMS = {"layers": "L_250K_Geology_Map", "srs": "EPSG:3857", "bbox": "0,0,1,1", "width": "256", "height": "256"}

    def setUp(self):
        import tempfile
        self.root = tempfile.mkdtemp()
        o = override_settings(TILE_CACHE_DIR=self.root, TILE_CACHE_MIN_FREE_BYTES=0, TILE_CACHE_MAX_AGE_DAYS=1, METATILE=False)
        o.enable()
        self.addCleanup(o.disable)

    def old(self, params, content=b"\x89PNG-old"):
        import os
        import time
        from viewer import tilecache, views
        key = views.map_cache_key(dict(params, format="image/png", transparent="true"))
        tilecache.put(key, content)
        past = time.time() - 30 * 86400
        os.utime(tilecache._path(key), (past, past))
        return key

    def call(self, params, upstream="kigam"):
        from viewer import views
        with mock.patch.object(views, "_upstream_of", return_value=upstream):
            return self.client.get("/GSM/wms/", params)

    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False)
    def test_키가_없으면_늙은_타일이라도_낸다(self):
        self.old(self.PARAMS)
        r = self.call(self.PARAMS)
        self.assertEqual((r.content, r["X-GSM-Cache"]), (b"\x89PNG-old", "hit"))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_상류가_못_주면_옛것을_낸다(self):
        self.old(self.PARAMS)
        with mock.patch.object(kigam, "get_map", side_effect=kigam.UpstreamError("down")):
            r = self.call(self.PARAMS)
        self.assertEqual((r.content, r["X-GSM-Cache"]), (b"\x89PNG-old", "hit"))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_새로_받은_것이_옛것을_덮는다(self):
        key = self.old(self.PARAMS)
        with mock.patch.object(kigam, "get_map", return_value=(b"\x89PNG-new", "image/png")):
            r = self.call(self.PARAMS)
        from viewer import tilecache
        self.assertEqual((r.content, r["X-GSM-Cache"]), (b"\x89PNG-new", "miss"))
        self.assertEqual(tilecache.get(key), b"\x89PNG-new")

    def test_자료를_파는_상류는_담지_않는다(self):
        from viewer import cgs, tilecache, views
        params = dict(self.PARAMS, layers="cgs:geology")
        with mock.patch.object(cgs, "get_map", return_value=(b"\x89PNG-cgs", "image/png")):
            r = self.call(params, upstream="cgs")
        self.assertEqual(r.content, b"\x89PNG-cgs")
        self.assertIsNone(tilecache.get(views.map_cache_key(dict(params, format="image/png", transparent="true"))))
        self.assertEqual(tilecache.stats()["count"], 0)


class InfoDispatch(SimpleTestCase):
    """속성 길이 상류마다 제 풀이(`friendly`)를 타는지 — 갈래가 일흔을 넘어 한 줄 빠뜨리면 날것의 열 이름이 팝업에 뜬다.
    coverage 로 보니 이 열여덟 갈래를 지나는 시험이 없었다"""
    #: 상류 → (풀이가 사는 곳, 함수 이름)
    TARGETS = {"geusarc": ("geus", "arc_friendly"), "gsjows": ("gsj", "gsjows_friendly"), "bgsgi": ("bgs", "geoindex_friendly"),
               **{n: (n, "friendly") for n in ("esdm", "jmg", "mgb", "dmr", "sgs", "gsiindia", "mris", "gns", "natt", "ispra", "lneg",
                                              "swisstopo", "iige", "georep", "ineter", "geosphere", "pig", "tno", "dov", "spw")}}

    def ask(self, upstream, features):
        from viewer import views
        door = views._Door.MODULES[upstream]
        with override_settings(TILE_CACHE_DIR=""), mock.patch.object(views, "_upstream_of", return_value=upstream), \
             mock.patch.object(door, "get_feature_info", return_value={"features": features}):
            return self.client.get("/GSM/featureinfo/", {"query_layers": "x", "layers": "x", "bbox": "0,0,1,1", "width": "9", "height": "9",
                                                         "i": "4", "j": "4"})

    def test_상류마다_제_풀이를_탄다(self):
        import importlib
        for upstream, (where, func) in self.TARGETS.items():
            with self.subTest(upstream=upstream):
                module = importlib.import_module(f"viewer.{where}")
                with mock.patch.object(module, func, return_value={"풀었다": upstream}) as fn:
                    r = self.ask(upstream, [{"id": "a.1", "properties": {"RAW": "v"}}])
                fn.assert_called_once()
                self.assertEqual(r.json()["features"][0]["props"], {"풀었다": upstream})

    @override_settings(KIGAM_KEY=KEY)
    def test_빈_것·잡음·겹친_것은_하나로(self):
        from viewer import views
        feats = [{"id": "admin_boundary.1", "properties": {"x": "1"}},          # 행정 경계는 잡음
                 {"id": "a.1", "properties": {"x": None, "y": "", "z": "null"}},   # 값이 다 비었다
                 {"id": "a.2", "properties": {"지층명": "옥천층군"}},
                 {"id": "a.3", "properties": {"지층명": "옥천층군"}}]               # 같은 속성은 하나로
        r = self.ask("kigam", feats)
        self.assertEqual([f["props"] for f in r.json()["features"]], [{"지층명": "옥천층군"}])

    @override_settings(KIGAM_KEY=KEY)
    def test_상류가_못_주면_까닭을_키_없이(self):
        from viewer import views
        boom = kigam.UpstreamError(f"상류에 닿지 못했다: {kigam.redact('url?key=' + KEY)}")
        with override_settings(TILE_CACHE_DIR=""), mock.patch.object(views, "_upstream_of", return_value="kigam"), \
             mock.patch.object(kigam, "get_feature_info", side_effect=boom):
            r = self.client.get("/GSM/featureinfo/", {"query_layers": "L", "layers": "L", "bbox": "0,0,1,1", "width": "9", "height": "9"})
        self.assertEqual(r.status_code, 502)
        self.assertNotIn(KEY, r.content.decode())
