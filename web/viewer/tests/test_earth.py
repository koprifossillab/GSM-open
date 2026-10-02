"""온 지구 — Macrostrat 의 문과 화면 (wetherilli P06·086).

Macrostrat 을 실제로 부르지 않는다. 응답의 꼴은 2026-09-30 에 받아 본 그대로다 — 콜로라도(1:50만 주 지질도)와
서울(GSC 세계 지질도, tiny 판에만 있다).
"""
import io
import json
import tempfile
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import macrostrat

#: 콜로라도 볼더 서쪽을 medium 판으로 물으면 (2026-09-30, 줄였다)
BOULDER = {"source_id": 133, "name": "Granitic rocks of 1700-m.y. age group", "strat_name": "Boulder Creek Granite",
           "lith": "Major:{granite}", "descrip": "", "b_int_name": "Paleoproterozoic", "t_int_name": "Paleoproterozoic",
           "b_age": 2500, "t_age": 1600, "color": "#F74370"}
#: 서울 — tiny 판의 세계 지질도에만 있다
SEOUL = {"source_id": 154, "name": "Precambrian crystalline metamorphic rocks", "strat_name": "",
         "lith": "crystalline metamorphic rocks", "descrip": "", "b_int_name": "Precambrian",
         "t_int_name": "Precambrian", "b_age": 4000, "t_age": 541, "color": "#F04370"}
CHORLTON = "Chorlton, L.B. Generalized geology of the world … Geological Survey of Canada, Open File 5529."


def answer(data, refs=None, status=200):
    body = {"success": {"v": 2, "license": "CC-BY 4.0", "data": data, "refs": refs or {}}}
    return mock.Mock(status_code=status, headers={"content-type": "application/json"}, content=b"{}",
                     url="https://macrostrat.org/api/v2/…", json=lambda: body)


def png(color=None, box=None):
    """256 타일. `color` 가 없으면 빈 타일, `box` 를 주면 그 네모만 칠한다."""
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    if color:
        im.paste(color, box or (0, 0, 256, 256))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class Scales(SimpleTestCase):
    def test_줌마다_축척(self):
        self.assertEqual([macrostrat.scale_of(z) for z in (0, 2, 3, 5, 6, 9, 10, 16)],
                         ["tiny", "tiny", "small", "small", "medium", "medium", "large", "large"])

    def test_찾는_차례는_제_축척_다음_거친_것(self):
        self.assertEqual(macrostrat.search_order(7), ["medium", "small", "tiny"])
        self.assertEqual(macrostrat.search_order(1), ["tiny"])


class Identify(SimpleTestCase):
    def setUp(self):
        patch = mock.patch.object(macrostrat.usage, "record")
        patch.start()
        self.addCleanup(patch.stop)

    def test_제_축척에_있으면_거기서(self):
        with mock.patch.object(macrostrat.requests, "get", side_effect=[answer([BOULDER])]) as get:
            got = macrostrat.identify(-105.3, 40.0, 7)
        self.assertEqual(get.call_args.kwargs["params"]["scale"], "medium")
        u = got["units"][0]
        self.assertEqual((u["age"], u["b_age"], u["t_age"], u["scale"]), ("고원생대", 2500, 1600, "medium"))

    def test_없으면_거친_축척으로(self):
        # 서울 — medium·small 에 없고 tiny 에만 있다. 타일도 줌 5 를 늘려 깐다(`fill`)
        with mock.patch.object(macrostrat.requests, "get",
                               side_effect=[answer([]), answer([]), answer([SEOUL], {"154": CHORLTON})]) as get:
            got = macrostrat.identify(126.98, 37.57, 8)
        self.assertEqual([c.kwargs["params"]["scale"] for c in get.call_args_list], ["medium", "small", "tiny"])
        self.assertEqual(got["units"][0]["age"], "선캄브리아시대")
        self.assertEqual(got["refs"], {"154": CHORLTON})

    def test_영어판은_시대를_옮기지_않는다(self):
        with mock.patch.object(macrostrat.requests, "get", side_effect=[answer([BOULDER])]):
            self.assertEqual(macrostrat.identify(-105.3, 40.0, 7, "en")["units"][0]["age"], "Paleoproterozoic")

    def test_끊긴_받기는_다시_묻는다(self):
        # 상류 캐시가 처음 묻는 큰 타일을 보내다 끊는다 — 쉬었다 다시 물으면 온다
        tile = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=b"\x89PNG", url="…")
        broken = requests.exceptions.ChunkedEncodingError("IncompleteRead")
        with mock.patch.object(macrostrat.requests, "get", side_effect=[broken, tile]), \
             mock.patch.object(macrostrat.time, "sleep") as sleep:
            self.assertEqual(macrostrat.get_tile(8, 52, 98), b"\x89PNG")
        sleep.assert_called_once_with(1)


class Fill(SimpleTestCase):
    def test_빈_곳에_거친_대역을_늘려_깐다(self):
        tiles = {(8, 218, 100): png(), (5, 27, 12): png((240, 67, 112, 255))}
        out = Image.open(io.BytesIO(macrostrat.fill(8, 218, 100, lambda *k: tiles[k]))).convert("RGBA")
        self.assertEqual(out.getpixel((128, 128)), (240, 67, 112, 255))

    def test_고운_판이_위에_온다(self):
        # 왼쪽 반만 medium 판이 있다 — 거기는 제 색, 오른쪽은 줌 5 의 색
        tiles = {(7, 109, 50): png((10, 20, 30, 255), (0, 0, 128, 256)), (5, 27, 12): png((240, 67, 112, 255))}
        out = Image.open(io.BytesIO(macrostrat.fill(7, 109, 50, lambda *k: tiles[k]))).convert("RGBA")
        self.assertEqual(out.getpixel((10, 10)), (10, 20, 30, 255))
        self.assertEqual(out.getpixel((250, 10)), (240, 67, 112, 255))

    def test_늘려도_계단이_없고_없는_색이_없다(self):
        # 대각선으로 두 단위가 맞닿은 조상 — 줌 5 에서 줌 11 로(64 배) 늘린다 (wetherilli 105)
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        px = im.load()
        for j in range(256):
            for i in range(256):
                px[i, j] = (240, 67, 112, 255) if i > j else (0, 160, 80, 255)
        out = macrostrat.enlarge(im, (100, 100, 104, 104))
        colours = {c for _, c in out.getcolors(1 << 16)}
        self.assertEqual(colours, {(240, 67, 112, 255), (0, 160, 80, 255)})
        # 경계는 대각선이다 — 가장 가까운 칸으로 늘렸다면 64 칸마다 계단이 섰을 것이다
        edge = [next(i for i in range(256) if out.getpixel((i, j))[0] == 240) for j in (10, 40, 70, 100, 130)]
        steps = [b - a for a, b in zip(edge, edge[1:])]
        self.assertTrue(all(20 <= s <= 40 for s in steps), edge)

    def test_가는_선은_늘리지_않는다(self):
        im = Image.new("RGBA", (256, 256), (240, 67, 112, 255))
        for j in range(256):
            im.putpixel((102, j), (0, 0, 0, 255))              # 단층 — 한 칸짜리 검은 선
        out = macrostrat.enlarge(im, (96, 96, 108, 108))
        self.assertEqual({c for _, c in out.getcolors(1 << 16)}, {(240, 67, 112, 255)})

    def test_다_칠해졌거나_small_대역이면_조상을_묻지_않는다(self):
        full = png((1, 2, 3, 255))
        self.assertEqual(macrostrat.fill(8, 1, 1, lambda *k: {(8, 1, 1): full}[k]), full)
        empty = png()
        self.assertEqual(macrostrat.fill(4, 1, 1, lambda *k: {(4, 1, 1): empty}[k]), empty)


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-earth-")
        patch = override_settings(TILE_CACHE_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_화면이_선다(self):
        r = self.client.get(reverse("viewer:earth"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "earth.js")

    def test_누르기는_단위마다_표(self):
        hit = {"units": [macrostrat.unit_row(SEOUL, "tiny")], "refs": {"154": CHORLTON}}
        with mock.patch.object(macrostrat, "identify", return_value=hit) as identify:
            data = self.client.get(reverse("viewer:earth-info"), {"lon": 126.98, "lat": 37.57, "z": 8}).json()
            self.client.get(reverse("viewer:earth-info"), {"lon": 126.98, "lat": 37.57, "z": 7})
        self.assertEqual(identify.call_count, 1)             # 같은 축척이면 캐시가 답한다
        rows = dict(data["units"][0]["rows"])
        self.assertEqual((rows["시대"], rows["연대 (Ma)"], rows["원도"]), ("선캄브리아시대", "4000 – 541", CHORLTON))
        self.assertEqual((data["units"][0]["b_age"], data["units"][0]["t_age"]), (4000, 541))

    def test_타일은_담아_둔다(self):
        with mock.patch.object(macrostrat, "get_tile", return_value=png((1, 2, 3, 255))) as get:
            first = self.client.get(reverse("viewer:earth-tile", args=[3, 6, 3]))
            again = self.client.get(reverse("viewer:earth-tile", args=[3, 6, 3]))
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        self.assertEqual(get.call_count, 1)

    def test_상류가_못_주면_안내_타일(self):
        with mock.patch.object(macrostrat, "get_tile", side_effect=macrostrat.MacrostratError("x")):
            r = self.client.get(reverse("viewer:earth-tile", args=[3, 6, 3]))
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_범례는_기의_색(self):
        rows = [{"name": "제4기", "en": "Quaternary", "b_age": 2.58, "t_age": 0, "color": "#F9F97F"}]
        with mock.patch.object(macrostrat, "legend", return_value=rows):
            self.assertEqual(self.client.get(reverse("viewer:earth-legend")).json()["rows"], rows)
