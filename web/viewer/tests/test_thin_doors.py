"""coverage 가 가장 낮던 문 넷과 캐시의 실패 길 (wetherilli 349).

아일랜드(GSI)·말레이시아(JMG)·노바스코샤(NSGS)·사스카치원(SKGS) — 레이어 이름을 상류의 이름·번호로 옮기는 것,
WMS 변수를 REST 로 옮기는 셈(누른 화소의 가운데), 상류가 그림·JSON 이 아닌 것을 줄 때 멈추는 것을 본다.
상류는 부르지 않는다. 캐시는 읽지 못하거나 쓰지 못해도 멈추지 않는지 본다.
"""
import os
import tempfile
import time
from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from viewer import gsi, jmg, nsgs, skgs, tilecache

VIEW = {"crs": "EPSG:3857", "bbox": "0,0,1000,1000", "width": "100", "height": "100"}


def answer(status=200, ctype="image/png", content=b"\x89PNG", body=None):
    r = mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://upstream/x", elapsed=None)
    if body is not None:
        r.json.return_value = body
    else:
        r.json.side_effect = ValueError("not json")
    return r


class Quiet(SimpleTestCase):
    """usage 를 갈아 끼운다 — 시험이 상류 기록을 남기지 않게"""
    door = None

    def setUp(self):
        for name, value in (("record", None), ("paused", 0), ("looks_blocked", False)):
            p = mock.patch.object(self.door.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def get(self, *answers):
        return mock.patch.object(self.door.requests, "get", side_effect=list(answers))


class Gsi(Quiet):
    door = gsi

    def test_이름을_판과_상류_레이어로_가른다(self):
        self.assertEqual(gsi.split("gsi:1m:A,gsi:1m:B"), ("1m", "A,B"))
        for bad in ("gsi:5m:A", "gsi:1m:", "gsi:1m:A,gsi:100k:B"):
            with self.assertRaises(gsi.GsiError):
                gsi.split(bad)

    def test_판마다_다른_서비스로_묻는다(self):
        with self.get(answer()) as get:
            gsi.get_map(dict(VIEW, layers="gsi:100k:Bedrock"))
        url, params = get.call_args.args[0], get.call_args.kwargs["params"]
        self.assertIn(f"/{gsi.SHEETS['100k']}/MapServer/WMSServer", url)
        self.assertEqual((params["layers"], params["srs"], params["version"]), ("Bedrock", "EPSG:3857", "1.1.1"))

    def test_속성은_i_j_를_x_y_로(self):
        with self.get(answer(ctype="application/json", body={"features": [{"properties": {"a": 1}}]})) as get:
            got = gsi.get_feature_info(dict(VIEW, layers="gsi:1m:L", query_layers="gsi:1m:L", i="3", j="4"))
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["x"], params["y"], params["query_layers"]), ("3", "4", "L"))
        self.assertEqual(got, {"features": [{"properties": {"a": 1}}]})

    def test_실패를_알아본다(self):
        with self.get(answer(ctype="text/html")), self.assertRaises(gsi.GsiError):
            gsi.get_map(dict(VIEW, layers="gsi:1m:L"))
        with self.get(answer(ctype="text/xml")), self.assertRaises(gsi.GsiError):
            gsi.get_legend("gsi:1m:L")
        with self.get(answer(status=500)), self.assertRaises(gsi.GsiError):
            gsi.get_feature_info(dict(VIEW, layers="gsi:1m:L"))
        with self.get(answer(ctype="text/html")), self.assertRaises(gsi.GsiError):
            gsi.get_feature_info(dict(VIEW, layers="gsi:1m:L"))
        with self.get(requests.ConnectionError("down")), self.assertRaises(gsi.GsiError):
            gsi.get_map(dict(VIEW, layers="gsi:1m:L"))
        with mock.patch.object(gsi.usage, "paused", return_value=30), self.get() as get, self.assertRaises(gsi.GsiError):
            gsi.get_map(dict(VIEW, layers="gsi:1m:L"))
        get.assert_not_called()

    def test_범례(self):
        with self.get(answer()) as get:
            self.assertEqual(gsi.get_legend("gsi:1m:L"), (b"\x89PNG", "image/png"))
        self.assertEqual(get.call_args.kwargs["params"]["layer"], "L")


class Jmg(Quiet):
    door = jmg

    def test_주_열다섯을_한_장에(self):
        with self.get(answer()) as get:
            jmg.get_map(dict(VIEW, layers="jmg:age"))
        params = get.call_args.kwargs["params"]
        self.assertTrue(get.call_args.args[0].endswith("/MapServer/export"))
        self.assertEqual(params["layers"], "show:" + ",".join(str(i) for i in range(1, 30, 2)))
        self.assertEqual(params["size"], "100,100")

    def test_누른_화소의_가운데를_묻고_하나만(self):
        body = {"results": [{"layerName": "Perak", "attributes": {"LITHOLOGY": "Granite"}}, {"layerName": "Kedah", "attributes": {}}]}
        with self.get(answer(ctype="application/json", body=body)) as get:
            got = jmg.get_feature_info(dict(VIEW, layers="jmg:lithology", i="0", j="0"))
        self.assertEqual(get.call_args.kwargs["params"]["geometry"], "5.0,995.0")
        self.assertEqual(got["features"], [{"id": "Perak.0", "properties": {"LITHOLOGY": "Granite"}}])

    def test_잘못된_변수와_상류의_오류(self):
        for bad in ({"crs": "EPSG:4326"}, {"bbox": "a,b,c,d"}, {"bbox": "0,0,1"}, {"width": "9999"}):
            with self.assertRaises(jmg.JmgError):
                jmg.get_map(dict(VIEW, layers="jmg:age", **bad))
        with self.assertRaises(jmg.JmgError):
            jmg.get_map(dict(VIEW, layers="jmg:age,jmg:lithology"))
        with self.assertRaises(jmg.JmgError):
            jmg.get_feature_info(dict(VIEW, layers="jmg:age"))          # 누른 자리가 없다
        with self.get(answer(ctype="application/json", body={"error": {"code": 500}})), self.assertRaises(jmg.JmgError):
            jmg.get_feature_info(dict(VIEW, layers="jmg:age", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(jmg.JmgError):
            jmg.get_feature_info(dict(VIEW, layers="jmg:age", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(jmg.JmgError):
            jmg.get_map(dict(VIEW, layers="jmg:age"))
        with self.get(requests.Timeout("slow")), self.assertRaises(jmg.JmgError):
            jmg.get_map(dict(VIEW, layers="jmg:age"))
        with self.assertRaises(jmg.JmgError):
            jmg.get_legend("jmg:lithology")

    def test_목록_범례는_한_번_받아_담는다(self):
        legend = {"layers": [{"layerId": 0, "legend": [{"label": "Granite.", "imageData": "AAA", "contentType": "image/png"}]},
                             {"layerId": 2, "legend": [{"label": "Granite.", "imageData": "AAA", "contentType": "image/png"}]}]}
        with tempfile.TemporaryDirectory() as root, override_settings(TILE_CACHE_DIR=root, TILE_CACHE_MIN_FREE_BYTES=0):
            with self.get(answer(ctype="application/json", body=legend)) as get:
                first = jmg.legend_rows("jmg:lithology")
                second = jmg.legend_rows("jmg:lithology")
            self.assertEqual(get.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual([r["lithology"] for r in first], ["Granite"])
        with self.assertRaises(jmg.JmgError):
            jmg.legend_rows("jmg:age")

    def test_범례가_JSON_이_아니거나_오류면(self):
        with override_settings(TILE_CACHE_DIR=""):
            with self.get(answer(ctype="text/html")), self.assertRaises(jmg.JmgError):
                jmg.legend_rows("jmg:lithology")
            with self.get(answer(ctype="application/json", body={"error": {"code": 400}})), self.assertRaises(jmg.JmgError):
                jmg.legend_rows("jmg:lithology")


class Nsgs(Quiet):
    door = nsgs

    def test_화면의_투영을_그대로_넘긴다(self):
        with self.get(answer()) as get:
            nsgs.get_map(dict(VIEW, crs="EPSG:3978", layers="nsgs:9"))
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["bboxSR"], params["imageSR"], params["layers"]), ("3978", "3978", "show:9"))

    def test_누르기는_기반암만(self):
        with self.get() as get:
            self.assertEqual(nsgs.get_feature_info(dict(VIEW, layers="nsgs:9", i="1", j="1")), {"features": []})
        get.assert_not_called()
        body = {"results": [{"attributes": {"UNIT": "Meguma"}}]}
        with self.get(answer(ctype="application/json", body=body)) as get:
            got = nsgs.get_feature_info(dict(VIEW, layers="nsgs:11", i="99", j="99"))
        self.assertEqual(get.call_args.kwargs["params"]["geometry"], "995.0,5.0")
        self.assertEqual(got, {"features": [{"id": "nsgs.0", "properties": {"UNIT": "Meguma"}}]})

    def test_잘못된_변수와_상류의_오류(self):
        for bad in ({"crs": "CRS:84"}, {"bbox": "x"}, {"height": "0"}):
            with self.assertRaises(nsgs.NsgsError):
                nsgs.get_map(dict(VIEW, layers="nsgs:11", **bad))
        with self.assertRaises(nsgs.NsgsError):
            nsgs.get_map(dict(VIEW, layers="nsgs:1"))
        with self.assertRaises(nsgs.NsgsError):
            nsgs.get_feature_info(dict(VIEW, layers="nsgs:11", i="a"))
        with self.get(answer(status=500)), self.assertRaises(nsgs.NsgsError):
            nsgs.get_feature_info(dict(VIEW, layers="nsgs:11", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(nsgs.NsgsError):
            nsgs.get_feature_info(dict(VIEW, layers="nsgs:11", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(nsgs.NsgsError):
            nsgs.get_map(dict(VIEW, layers="nsgs:11"))
        with self.get(requests.ConnectionError("down")), self.assertRaises(nsgs.NsgsError):
            nsgs.get_map(dict(VIEW, layers="nsgs:11"))
        with mock.patch.object(nsgs.usage, "paused", return_value=5), self.assertRaises(nsgs.NsgsError):
            nsgs.get_map(dict(VIEW, layers="nsgs:11"))
        with self.assertRaises(nsgs.NsgsError):
            nsgs.get_legend("nsgs:11")


class Skgs(Quiet):
    door = skgs

    def test_WMS_번호로_옮긴다(self):
        with self.get(answer()) as get:
            skgs.get_map(dict(VIEW, layers="skgs:11"))
        self.assertEqual((get.call_args.kwargs["params"]["layers"], get.call_args.kwargs["params"]["styles"]), ("11", ""))
        with self.get(answer()) as get:
            skgs.get_legend("skgs:3")
        self.assertEqual(get.call_args.kwargs["params"]["layer"], "3")

    def test_속성은_geo_json_으로_단층은_누르지_않는다(self):
        with self.get() as get:
            self.assertEqual(skgs.get_feature_info(dict(VIEW, layers="skgs:11", query_layers="skgs:11")), {"features": []})
        get.assert_not_called()
        feats = [{"properties": {"LITHOLOGY": "granite"}}]
        with self.get(answer(ctype="application/geo+json", body={"features": feats})) as get:
            got = skgs.get_feature_info(dict(VIEW, layers="skgs:2", query_layers="skgs:2", i="1", j="1"))
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["query_layers"], params["info_format"]), ("2", "application/geo+json"))
        self.assertEqual(got, {"features": feats})

    def test_광물_산지는_REST_로(self):
        with self.get(answer(ctype="application/json", body={"error": {"code": 400}})), self.assertRaises(skgs.SkgsError):
            skgs.get_feature_info(dict(VIEW, layers="skgs:mines", query_layers="skgs:mines", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(skgs.SkgsError):
            skgs.get_map(dict(VIEW, layers="skgs:mines"))
        with self.assertRaises(skgs.SkgsError):
            skgs.get_legend("skgs:smdi")
        self.assertTrue(skgs.knows("skgs:mines") and skgs.knows("skgs:2") and not skgs.knows("skgs:9"))

    def test_상류의_오류(self):
        with self.get(answer(ctype="text/html")), self.assertRaises(skgs.SkgsError):
            skgs.get_map(dict(VIEW, layers="skgs:2"))
        with self.get(answer(ctype="text/html")), self.assertRaises(skgs.SkgsError):
            skgs.get_legend("skgs:2")
        with self.get(answer(status=502)), self.assertRaises(skgs.SkgsError):
            skgs.get_feature_info(dict(VIEW, layers="skgs:2", i="1", j="1"))
        with self.get(answer(ctype="text/html")), self.assertRaises(skgs.SkgsError):
            skgs.get_feature_info(dict(VIEW, layers="skgs:2", i="1", j="1"))
        with self.get(requests.ConnectionError("down")), self.assertRaises(skgs.SkgsError):
            skgs.get_map(dict(VIEW, layers="skgs:2"))
        with mock.patch.object(skgs.usage, "paused", return_value=5), self.assertRaises(skgs.SkgsError):
            skgs.get_map(dict(VIEW, layers="skgs:2"))
        with self.assertRaises(skgs.SkgsError):
            skgs.get_map(dict(VIEW, layers="skgs:2,skgs:3"))


class CacheFailures(SimpleTestCase):
    """캐시는 덤이다 — 읽지 못하고 쓰지 못해도 멈추지 않는다"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        o = override_settings(TILE_CACHE_DIR=self.root, TILE_CACHE_MIN_FREE_BYTES=0, TILE_CACHE_MAX_AGE_DAYS=0)
        o.enable()
        self.addCleanup(o.disable)

    def test_꺼져_있으면_아무것도_하지_않는다(self):
        with override_settings(TILE_CACHE_DIR=""):
            self.assertIsNone(tilecache.get("ab" * 32))
            tilecache.put("ab" * 32, b"x")
            self.assertEqual(tilecache.stats(), {"enabled": False, "count": 0, "bytes": 0})
            self.assertEqual(tilecache.prune()["count"], 0)

    def test_빈_파일과_읽지_못하는_파일은_없는_것(self):
        key = tilecache.key_text("t", "empty")
        path = tilecache._path(key)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"")
        self.assertIsNone(tilecache.get(key))
        path.write_bytes(b"x")
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("no")):
            self.assertIsNone(tilecache.get(key))
        with mock.patch.object(tilecache.os, "utime", side_effect=PermissionError("ro")):
            self.assertEqual(tilecache.get(key), b"x")              # 쓰인 때를 못 남겨도 내준다

    def test_쓰지_못해도_멈추지_않는다(self):
        key = tilecache.key_text("t", "ro")
        with mock.patch.object(Path, "write_bytes", side_effect=OSError("disk full")), self.assertLogs("viewer.tilecache", "WARNING"):
            tilecache.put(key, b"x")
        self.assertIsNone(tilecache.get(key))
        self.assertFalse(list(Path(self.root).rglob("*.part")))

    def test_여유를_재지_못하면_담는다(self):
        with override_settings(TILE_CACHE_MIN_FREE_BYTES=1), mock.patch.object(tilecache.shutil, "disk_usage", side_effect=OSError):
            self.assertTrue(tilecache._room_left(Path(self.root)))

    def test_늙은_것은_stale_로만(self):
        key = tilecache.key_text("t", "old")
        tilecache.put(key, b"old")
        past = time.time() - 10 * 86400
        os.utime(tilecache._path(key), (past, past))
        self.assertIsNone(tilecache.get(key, max_age=86400))
        self.assertEqual(tilecache.get(key, max_age=86400, stale=True), b"old")

    def test_줄이다가_사라진_파일은_건너뛴다(self):
        for n in range(3):
            tilecache.put(tilecache.key_text("t", str(n)), b"x" * 10)
        real = Path.stat
        gone = tilecache._path(tilecache.key_text("t", "1"))

        def flaky(self, *a, **k):
            if self == gone:
                raise FileNotFoundError(self)
            return real(self, *a, **k)
        with mock.patch.object(Path, "stat", flaky):
            self.assertEqual(tilecache.stats()["count"], 2)
            got = tilecache.prune(max_bytes=10, max_age_days=0)
        self.assertEqual((got["removed_size"], got["count"]), (1, 1))
        with mock.patch.object(Path, "unlink", side_effect=PermissionError):
            tilecache._unlink(gone)                                    # 지우지 못해도 멈추지 않는다


class UploadEdges(SimpleTestCase):
    """올린 파일은 남이 준 것이다 — 깨진 것은 사람이 읽을 까닭으로 멈추고, 일부만 깨졌으면 건너뛰고 센다 (wetherilli 349)"""

    def parse(self, name, text, crs_code="4326"):
        from viewer import pointsets
        return pointsets.parse(name, text if isinstance(text, bytes) else text.encode("utf-8"), crs_code)

    def fails(self, name, text, crs_code="4326"):
        from viewer import pointsets
        with self.assertRaises(pointsets.UploadError) as caught:
            self.parse(name, text, crs_code)
        return str(caught.exception.args[0].template)

    def test_글자를_읽지_못하면(self):
        self.assertIn("글자를 읽지 못했다", self.fails("a.csv", b"\x80\x80\xff"))

    def test_주소_열이_모두_비면(self):
        self.assertIn("주소 열", self.fails("a.csv", "이름,주소\n가,\n나,  \n"))

    def test_GeoJSON_에_features_가_없으면(self):
        self.assertIn("features 가 없다", self.fails("a.geojson", '{"type": "FeatureCollection", "features": []}'))
        self.assertIn("깨져 있다", self.fails("a.geojson", '{"type": '))

    def test_깨진_점은_건너뛰고_센다(self):
        import json
        doc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.0, 37.5]}, "properties": {"name": "서울"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": ["x"]}, "properties": {}},
            {"type": "Feature", "geometry": {"type": "MultiPoint", "coordinates": [[126.9, 35.1], [1], "bad"]}, "properties": {}},
            {"type": "Feature", "geometry": {"type": "GeometryCollection", "geometries": []}, "properties": {}}]}
        points, notes = self.parse("a.geojson", json.dumps(doc))
        self.assertEqual([(p["lat"], p["lon"]) for p in points], [(37.5, 127.0), (35.1, 126.9)])
        self.assertEqual(points[0]["label"], "서울")
        self.assertEqual(notes[-1].params["n"], 4)

    def test_꼭짓점이_너무_많으면_나눠_올리라고(self):
        import json
        from viewer import pointsets
        line = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[127 + i / 100, 37] for i in range(6)]}, "properties": {}}
        with mock.patch.object(pointsets, "MAX_VERTICES_TOTAL", 10):
            self.assertIn("꼭짓점이 모두", self.fails("a.geojson", json.dumps({"type": "FeatureCollection", "features": [line, line]})))

    def test_평면_좌표를_옮기지_못한_것은_건너뛴다(self):
        import json
        doc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [200000, 500000]}, "properties": {}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [["nested"], None]}, "properties": {}}]}
        points, notes = self.parse("a.geojson", json.dumps(doc), "5186")
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0]["lat"], 37.1, delta=0.05)          # 5186 은 북 600 000 m 가 38°
        self.assertEqual(notes[-1].params["n"], 1)
