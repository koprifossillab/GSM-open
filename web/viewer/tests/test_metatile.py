"""메타타일 — 큰 장을 한 번 받아 칸으로 잘라 담는다 (wetherilli 282). 상류는 바꿔 끼운다."""
import io
import tempfile
from pathlib import Path
import threading
import time
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import metatile, sgm, views

R = metatile.R


def wms(z, x, y, px=512, layer="sgm:datos:7"):
    """OpenLayers `createXYZ` 격자의 한 칸을 브라우저처럼 — 소수 자리는 JS 가 쓰는 꼴(17 자리)과 다를 수 있다"""
    span = 2 * R / 2 ** z
    w, n = -R + x * span, R - y * span
    return {"layers": layer, "crs": "EPSG:3857", "bbox": f"{w:.10f},{n - span:.10f},{w + span:.10f},{n:.10f}",
            "width": str(px), "height": str(px), "format": "image/png", "transparent": "true", "version": "1.3.0"}


def quadrants(px):
    """2×2 칸마다 다른 색 — 어느 조각이 어디서 잘렸는지 본다"""
    big = Image.new("RGBA", (px * 2, px * 2))
    for j in range(2):
        for i in range(2):
            big.paste((40 + 100 * i, 40 + 100 * j, 0, 255), (i * px, j * px, (i + 1) * px, (j + 1) * px))
    buf = io.BytesIO()
    big.save(buf, "PNG")
    return buf.getvalue()


class Metatile(SimpleTestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_격자의_칸(self):
        self.assertEqual(metatile.tile_of(wms(8, 57, 112)), (8, 57, 112, 512))
        off = wms(8, 57, 112)
        w, s, e, n = (float(v) for v in off["bbox"].split(","))
        off["bbox"] = f"{w + 100},{s},{e + 100},{n}"                                # 격자에서 어긋났다
        self.assertIsNone(metatile.tile_of(off))
        self.assertIsNone(metatile.tile_of(dict(wms(8, 57, 112), crs="EPSG:4326")))

    def test_한_번_받아_넷으로(self):
        calls = []

        def fetch(bbox, w, h):
            calls.append((bbox, w, h))
            return quadrants(512), "image/png"
        a = metatile.serve("L", wms(8, 57, 113), fetch)                               # 메타타일 (56,112) 의 오른쪽 아래
        b = metatile.serve("L", wms(8, 56, 112), fetch)                               # 왼쪽 위 — 캐시에서
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (1024, 1024))
        self.assertEqual(Image.open(io.BytesIO(a)).convert("RGBA").getpixel((5, 5)), (140, 140, 0, 255))
        self.assertEqual(Image.open(io.BytesIO(b)).convert("RGBA").getpixel((5, 5)), (40, 40, 0, 255))
        w, s, e, n = (float(v) for v in calls[0][0].split(","))
        span = 2 * R / 2 ** 8
        self.assertAlmostEqual(w, -R + 56 * span, places=3)
        self.assertAlmostEqual(n, R - 112 * span, places=3)
        self.assertAlmostEqual(e - w, 2 * span, places=3)

    def test_동시에_두_번_받지_않는다(self):
        calls = []

        def fetch(bbox, w, h):
            calls.append(bbox)
            time.sleep(0.3)
            return quadrants(512), "image/png"
        out = []
        threads = [threading.Thread(target=lambda t=t: out.append(metatile.serve("L", wms(9, 100 + t % 2, 200), fetch)))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(out))


class View(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-view-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_지자기는_메타타일로(self):
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url=url)
        with mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            first = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 56, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
            second = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 57, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(len(sent), 1)                                                # 이웃 칸은 상류를 타지 않는다
        self.assertEqual(sent[0]["size"], "1024,1024")
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        self.assertEqual((rows["sgm:datos:7"]["minZoom"], rows["sgm:datos:7"]["queryable"]), (8, False))

    def test_끄는_스위치(self):
        """`GSM_METATILE_OFF` 면 칸 하나씩 받던 앞의 길로 (wetherilli 299)"""
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(256), url=url)
        with override_settings(METATILE=False), mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 56, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual(sent[0]["size"], "512,512")

    def test_조각을_두_벌_담지_않고_옛것으로_되받는다(self):
        """조각으로 낸 칸은 브라우저 열쇠로 다시 담지 않는다 — 다음에도 조각에서 나오고, 상류가 못 줄 때는 조각의 옛것이 나온다 (wetherilli 297)"""
        q = {k.upper(): v for k, v in wms(8, 56, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"}
        ok = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url="u")
        with mock.patch.object(sgm.requests, "get", return_value=ok), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            self.client.get("/GSM/wms/", q)
        files = list(Path(settings.TILE_CACHE_DIR).rglob("*.png"))
        self.assertEqual(len(files), 4)                                               # 조각 넷뿐 — 낸 칸의 둘째 벌이 없다
        with mock.patch.object(sgm.requests, "get", side_effect=AssertionError("상류를 타면 안 된다")):
            again = self.client.get("/GSM/wms/", q)
        self.assertEqual(again.status_code, 200)
        piece = metatile.piece_key("sgm:datos:7", 512, 8, 56, 112)
        aged = lambda key, suffix=".png", stale=False, max_age=None: b"OLD" if stale and key == piece else None   # 모두 나이가 지났다
        with mock.patch.object(views.tilecache, "get", side_effect=aged), \
             mock.patch.object(sgm.requests, "get", side_effect=sgm.requests.ConnectionError("x")), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            old = self.client.get("/GSM/wms/", q)
        self.assertEqual(old.content, b"OLD")

    def test_다른_레이어는_그대로(self):
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(256), url=url)
        with mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 56, 112, layer="sgm:8").items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual(sent[0]["size"], "512,512")


class Wider(TestCase):
    """메타타일 넓히기 (wetherilli 284) — SGC 넓은 줌, EGDI 의 되받기, prewarm 의 메타타일 블록"""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-wide-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_표(self):
        self.assertIsNone(metatile.limit(views.METATILE, "sgm:datos:7"))
        self.assertEqual(metatile.limit(views.METATILE, "sgc:sa:8"), 6)
        self.assertIsNone(metatile.limit(views.METATILE, "egdi:GeologicUnitView_Age"))
        self.assertIs(metatile.limit(views.METATILE, "sgm:8"), False)

    def test_줌_끝_너머와_실패는_칸_하나로(self):
        calls = []

        def fetch(bbox, w, h):
            calls.append(w)
            return quadrants(512), "image/png"
        self.assertIsNone(metatile.serve("sgc:sa:8", wms(7, 40, 60, layer="sgc:sa:8"), fetch, max_zoom=6))
        self.assertEqual(calls, [])                                                   # 깊은 줌은 메타타일을 받지 않는다

        def broken(bbox, w, h):
            raise sgm.SgmError("서비스 예외")
        self.assertIsNone(metatile.serve("L", wms(5, 3, 4), broken, errors=(sgm.SgmError,)))
        with self.assertRaises(sgm.SgmError):                                          # 적지 않은 오류는 그대로 올린다
            metatile.serve("L", wms(5, 3, 4), broken)

    def test_EGDI_가_실패하면_칸을_되받는다(self):
        from viewer import egdi
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        sizes = []

        def fake(url, params=None, **kw):
            sizes.append(params["width"])
            if params["width"] == 1024:
                return mock.Mock(status_code=200, headers={"content-type": "application/vnd.ogc.se_xml"}, content=b"<x/>", url=url)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(256), url=url)
        with mock.patch.object(egdi.requests, "get", side_effect=fake), \
             mock.patch.object(egdi.usage, "record"), mock.patch.object(egdi.usage, "paused", return_value=0):
            got = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(5, 16, 10, layer="egdi:GeologicUnitView_Lithology").items()}
                                  | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual(got.status_code, 200)
        self.assertEqual(sizes, [1024, "512"])                                        # 큰 장이 실패하고 칸 하나를 받았다

    def test_prewarm_은_화면과_같은_블록으로(self):
        from viewer.management.commands import prewarm
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        plan = prewarm.plan_for("sgm:datos:7", "sgm")
        self.assertIsInstance(plan, prewarm.MetaPlan)
        self.assertEqual(plan.block(4), 2)                                            # --meta 를 따르지 않는다
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params["size"])
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url=url)
        with mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            self.assertEqual(plan.fetch_block(8, 28, 56, plan.block(4)), 4)
            # 화면이 이웃 칸을 부르면 prewarm 이 담은 것이 나온다 — 상류를 타지 않는다
            got = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 57, 113).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual(sent, ["1024,1024"])
        self.assertEqual(got.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(got.content)).convert("RGBA").getpixel((5, 5)), (140, 140, 0, 255))


class Table(TestCase):
    """메타타일 표의 줄마다 (wetherilli 287) — 카탈로그의 레이어에 걸리고, 3857 WMS 이고(브라우저가 곧장 받는 타일·점이 아니다),
    서버 캐시에 담지 않는 상류(`NO_STORE`)가 아니다 — 메타타일은 조각을 캐시에 담는다"""

    def test_줄마다_맞는_레이어(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = [l for g in views._catalog("ko") for l in g["layers"]]
        for entry in views.METATILE:
            hit = [l for l in rows if l["name"] == entry or (entry.endswith(":") and l["name"].startswith(entry))]
            self.assertTrue(hit, entry)
            for l in hit:
                self.assertIn(l.get("projection"), metatile.GRIDS, l["name"])          # 메타타일이 아는 격자로 부르는 레이어만 (wetherilli 307)
                self.assertFalse(l.get("tiles") or l.get("kind") == "points", l["name"])
                self.assertNotIn(l["upstream"], views.NO_STORE, l["name"])


class Polar(TestCase):
    """극지·대만 격자 (wetherilli 307) — 화면의 격자(`tilegrid.Grid`·`TAIWAN_GRID`)와 같은 칸을 알아보고, 큰 장의 bbox 를 그 격자로 짓는다"""
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-polar-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_극지_격자의_칸(self):
        from viewer import tilegrid
        for crs in ("EPSG:3413", "EPSG:3031", "EPSG:3575", "EPSG:3978"):
            params = tilegrid.Grid(crs).wms_params("x", 5, 9, 14)
            self.assertEqual(metatile.cell(params), (crs, 5, 9, 14, 512))
        p = tilegrid.Grid("EPSG:3413").wms_params("x", 5, 9, 14)
        w, s, e, n = (float(v) for v in metatile._bbox(5, 8, 14, 2, "EPSG:3413").split(","))
        tw, ts, te, tn = (float(v) for v in p["bbox"].split(","))
        self.assertAlmostEqual(w, tw - (te - tw))                 # 블록의 서쪽은 한 칸 왼쪽, 북쪽은 그 칸의 북쪽
        self.assertAlmostEqual(n, tn)
        self.assertAlmostEqual(e - w, 2 * (te - tw))

    def test_대만_4326_은_위도가_먼저(self):
        span = 180 / 2 ** 7
        x, y = 214, 46
        w, n = -180 + x * span, 90 - y * span
        params = {"crs": "EPSG:4326", "version": "1.3.0", "bbox": f"{n - span!r},{w!r},{n!r},{w + span!r}", "width": "512", "height": "512"}
        self.assertEqual(metatile.cell(params), ("EPSG:4326", 7, x, y, 512))
        s0, w0, n0, e0 = (float(v) for v in metatile._bbox(7, 214, 46, 2, "EPSG:4326", lat_first=True).split(","))
        self.assertAlmostEqual((w0, n0, e0 - w0, n0 - s0), (w, n, 2 * span, 2 * span))

    def test_열쇠는_투영을_가른다(self):
        self.assertEqual(metatile.piece_key("a", 512, 1, 2, 3), metatile.piece_key("a", 512, 1, 2, 3, "EPSG:3857"))   # 앞 판의 열쇠 그대로
        self.assertNotEqual(metatile.piece_key("a", 512, 1, 2, 3), metatile.piece_key("a", 512, 1, 2, 3, "EPSG:3413"))

    def test_그린란드는_3413_큰_장_하나로(self):
        from viewer import geus, tilegrid
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url=url, elapsed=None)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        g = tilegrid.Grid("EPSG:3413")
        with mock.patch.object(geus.requests, "get", side_effect=fake), mock.patch.object(geus.usage, "paused", return_value=0):
            for x in (8, 9):
                q = {k.upper(): v for k, v in g.wms_params("geusarc:g100k_ssw", 5, x, 14).items()}
                got = self.client.get("/GSM/wms/", q)
                self.assertEqual(got.status_code, 200)
        self.assertEqual(len(sent), 1)                                                # 이웃 칸은 상류를 타지 않는다
        self.assertEqual((sent[0]["size"], sent[0]["bboxSR"]), ("1024,1024", "3413"))

    def test_prewarm_도_3413_블록으로(self):
        """미리 데우기의 메타타일 계획이 극지 격자에서도 화면과 같은 블록을 받고, 화면 길이 찾는 조각 열쇠에 담는다 (wetherilli 309)"""
        from viewer import geus, tilegrid
        from viewer.management.commands import prewarm
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        plan = prewarm.plan_for("geusarc:g100k_ssw", "geusarc")
        self.assertIsInstance(plan, prewarm.MetaPlan)
        self.assertEqual(plan.grid.crs, "EPSG:3413")
        sent = []

        def fake(url, params=None, **kw):
            sent.append((params["size"], params["bboxSR"]))
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url=url, elapsed=None)
        with mock.patch.object(geus.requests, "get", side_effect=fake), mock.patch.object(geus.usage, "paused", return_value=0):
            self.assertEqual(plan.fetch_block(5, 4, 7, plan.block(4)), 4)
        self.assertEqual(sent, [("1024,1024", "3413")])
        for x, y in ((8, 14), (9, 14), (8, 15), (9, 15)):
            self.assertIsNotNone(metatile.tilecache.get(metatile.piece_key("geusarc:g100k_ssw", 512, 5, x, y, "EPSG:3413")))
        # 화면 길이 그 블록의 칸을 셈하면 같은 조각 열쇠다
        cell = metatile.cell(tilegrid.Grid("EPSG:3413").wms_params("geusarc:g100k_ssw", 5, 9, 15))
        self.assertEqual(cell, ("EPSG:3413", 5, 9, 15, 512))

