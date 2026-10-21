"""굽는 고리 — 가짜 소스로 굽고, 예산을 맞추고, 멈췄다 잇는다. 상류를 부르지 않는다."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gsmpack import bake, format, grid

from .helpers import png

BOX = {"title": "작은 박스", "region": "korea", "bbox": [129.0, 37.0, 129.05, 37.05],
       "layers": {"a": [10, 12], "b": [10, 12]}, "budget_mb": 200}


class FakeSource:
    tile_size = 256
    type = "image/png"
    attribution = "시험"

    def __init__(self, name, parts, fail=lambda z, x, y: None):
        self.name = self.title = self.kind = name
        self.parts, self.fail, self.asked = parts, fail, []

    def grid_zoom(self, screen):
        return screen

    def tiles(self, bbox, z):
        return grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return self.parts.get(format.tile_key(self.name, z, x, y))

    def fetch(self, z, x, y):
        self.asked.append((z, x, y))
        self.fail(z, x, y)
        data = png(size=256)
        self.parts.put(format.tile_key(self.name, z, x, y), data)
        return data


class Bake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        sleep = mock.patch.object(bake.time, "sleep", lambda s: None)
        sleep.start()
        self.addCleanup(sleep.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def sources(self, parts, **kw):
        return {"a": FakeSource("a", parts, **kw), "b": FakeSource("b", parts)}

    def test_굽고_다시_읽기(self):
        parts = bake.Parts(bake.parts_path(self.out, "tiny"))
        plan = bake.Plan("tiny", BOX, self.sources(parts))
        self.assertIn("어림", plan.lines[-1])
        units = {"a": (bake.units_body([{"type": "Feature"}]), ["t:litho"])}
        done = bake.bake(plan, self.out, parts, units=lambda bbox, gap: units, extra={"gsm": "9.9"}, log=lambda s: None)
        head, base = format.read_header(done["path"])
        self.assertEqual(head["gsm"], "9.9")
        self.assertEqual(head["layers"]["a"]["zooms"], [10, 12])
        self.assertEqual(head["units"]["a"]["key"], "@units/a")
        self.assertIn(b"Feature", format.read_tile(done["path"], "@units/a", (head, base)))
        self.assertFalse(parts.path.exists())                                   # 다 구우면 parts 를 지운다

    def test_차단이면_멈추고_다시_부르면_잇는다(self):
        parts = bake.Parts(bake.parts_path(self.out, "tiny"))
        calls = []

        def fail(z, x, y):
            calls.append(z)
            if len(calls) == 3:
                raise bake.FetchError("429", blocked=True)

        srcs = self.sources(parts, fail=fail)
        with self.assertRaises(bake.BakeError):
            bake.bake(bake.Plan("tiny", BOX, srcs), self.out, parts, log=lambda s: None)
        first = len(srcs["a"].asked)
        self.assertEqual(first, 3)                                              # 차단 조짐에 곧장 멈춘다
        srcs = self.sources(parts)
        bake.bake(bake.Plan("tiny", BOX, srcs), self.out, parts, log=lambda s: None)
        self.assertEqual(len(srcs["a"].asked), sum(len(grid.tiles_for(BOX["bbox"], z)) for z in (10, 11, 12)) - 2)   # 받은 둘은 다시 묻지 않는다

    def test_연달아_세_번_실패면_멈춘다(self):
        parts = bake.NoParts()

        def fail(z, x, y):
            raise bake.FetchError("500")

        srcs = self.sources(parts, fail=fail)
        with self.assertRaises(bake.BakeError):
            bake.bake(bake.Plan("tiny", BOX, srcs), self.out, parts, log=lambda s: None)
        self.assertEqual(len(srcs["a"].asked), 3)


class FitBudget(unittest.TestCase):
    def test_차례(self):
        zooms, dropped, total = bake.fit_budget(["a", "b"], {"a": [5, 8], "b": [5, 8]}, lambda n, z: 4 ** (z - 5), 30)
        self.assertEqual(zooms, {"a": [5, 7], "b": [5, 5]})             # b 를 처음 줌까지 내린 뒤에야 a 를 던다
        self.assertEqual(dropped, {"b": 6, "a": 8})
        self.assertLessEqual(total, 30)


class Estimate(unittest.TestCase):
    """한 장 크기는 줌마다 따로 어림한다 — 얕은 줌의 큰 그림으로 깊은 줌을 어림하면 받기도 전에 덜린다 (wetherilli 404)"""

    def test_표는_가장_가까운_줌(self):
        self.assertEqual(bake.guess_bytes("kigam", 15), 17_000)
        self.assertEqual(bake.guess_bytes("kigam", 16), 17_000)          # 표 밖의 깊은 줌은 가장 깊은 값
        self.assertEqual(bake.guess_bytes("vworld:Hybrid", 16), 4_000)
        self.assertEqual(bake.guess_bytes("모름", 12), bake.GUESS_OTHER)

    def test_캐시의_평균은_그_줌에만(self):
        class Cached(FakeSource):
            kind = "kigam"

            def cached(self, z, x, y):
                return b"x" * 200_000 if z == 10 else None               # 얕은 줌만 캐시에 있다 — 큰 그림

        box = dict(BOX, bbox=[127.0, 35.0, 128.5, 36.0], layers={"a": [10, 12]})
        src = Cached("a", bake.NoParts())
        src.kind = "kigam"
        plan = bake.Plan("t", box, {"a": src})
        self.assertGreaterEqual(plan.counts[("a", 10)], bake.MIN_SAMPLES)
        self.assertEqual(plan.avg[("a", 10)], 200_000)
        self.assertEqual(plan.avg[("a", 12)], 100_000)                   # 깊은 줌은 캐시의 큰 그림이 아니라 표의 값
