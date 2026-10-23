"""굽는 고리 — 가짜 소스로 굽고, 예산을 맞추고, 멈췄다 잇는다. 상류를 부르지 않는다."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gsmpack import bake, format, grid, landmask

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


    def test_받지_못한_열쇠를_머리와_로그에(self):
        parts = bake.Parts(bake.parts_path(self.out, "tiny"))
        hole = (12, *grid.tiles_for(BOX["bbox"], 12)[0])

        def fail(z, x, y):
            if (z, x, y) == hole:
                raise bake.FetchError("500")

        lines = []
        done = bake.bake(bake.Plan("tiny", BOX, self.sources(parts, fail=fail)), self.out, parts, log=lines.append)
        key = format.tile_key("a", *hole)
        self.assertEqual(done["missing"], [key])
        self.assertEqual(done["fails"], 1)
        head, _ = format.read_header(done["path"])
        self.assertEqual(head["missing"], [key])
        self.assertNotIn(key, head["tiles"])
        self.assertEqual(lines[-1], f"받지 못한 타일 1 — {key}")             # 수만이 아니라 어느 칸인지

    def test_다_받으면_머리에_칸이_없다(self):
        parts = bake.NoParts()
        lines = []
        done = bake.bake(bake.Plan("tiny", BOX, self.sources(parts)), self.out, parts, log=lines.append)
        self.assertNotIn("missing", format.read_header(done["path"])[0])
        self.assertEqual(lines[-1], "받지 못한 타일 없음")

    def test_이웃이_채운_칸은_못_받은_것이_아니다(self):
        """KIGAM 은 큰 그림 한 장으로 이웃 열다섯을 받는다 — 못 받은 칸이 뒤에 채워지면 받지 못한 것이 아니다"""
        parts = bake.Parts(bake.parts_path(self.out, "tiny"))
        tiles = grid.tiles_for(BOX["bbox"], 12)
        first, second = (12, *tiles[0]), (12, *tiles[1])
        state = {"failed": False}

        def fail(z, x, y):
            if (z, x, y) == first and not state["failed"]:
                state["failed"] = True
                raise bake.FetchError("500")
            if (z, x, y) == second:
                parts.put(format.tile_key("a", *first), png(size=256))       # 큰 그림이 이웃을 함께 담는다

        done = bake.bake(bake.Plan("tiny", BOX, self.sources(parts, fail=fail)), self.out, parts, log=lambda s: None)
        self.assertEqual(done["missing"], [])
        self.assertIn(format.tile_key("a", *first), format.read_header(done["path"])[0]["tiles"])

    def test_덜어_낸_줌의_구멍은_적지_않는다(self):
        parts = bake.NoParts()

        def fail(z, x, y):
            if z == 12 and (x + y) % 2:
                raise bake.FetchError("500")

        plan = bake.Plan("tiny", BOX, self.sources(parts, fail=fail))
        with mock.patch.object(bake, "fit_budget", side_effect=[({"a": [10, 11], "b": [10, 12]}, {"a": 12}, 0)]):
            done = bake.bake(plan, self.out, parts, log=lambda s: None)
        self.assertGreater(done["fails"], 0)
        self.assertEqual(done["missing"], [])


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


class Sea(unittest.TestCase):
    """바다 칸은 덜 센다 — 바다가 넓은 박스에서 어림이 30 % 넘쳤다 (wetherilli 406·409)"""
    LAND = [127.0, 36.0, 127.2, 36.2]           # 충청 내륙
    SEA = [129.6, 35.6, 129.8, 35.8]            # 포항 앞바다
    COAST = [127.8, 34.8, 128.0, 35.0]          # 남해 — 반쯤 바다

    def plan(self, bbox, share=None, name="vworld:Base"):
        src = FakeSource(name, bake.NoParts())
        if share is not None:
            src.sea_share = share
        return bake.Plan("t", dict(BOX, bbox=bbox, layers={name: [12, 14]}), {name: src})

    def test_땅_몫(self):
        self.assertEqual(landmask.fraction(self.LAND), 1.0)
        self.assertEqual(landmask.fraction(self.SEA), 0.0)
        self.assertTrue(0.3 < landmask.fraction(self.COAST) < 0.7)
        self.assertEqual(landmask.fraction([140.0, 40.0, 140.1, 40.1]), 1.0)          # 마스크 밖은 모른다 — 땅으로 센다
        self.assertEqual(landmask.fraction([129.70, 35.70, 129.7001, 35.7001]), 0.0)  # 칸보다 작은 네모도 센다

    def test_칸은_박스_안쪽만_본다(self):
        z, (x, y) = 9, grid.tiles_for(self.SEA, 9)[0]                 # 줌 9 칸은 육지까지 덮지만 박스 안은 바다뿐이다
        self.assertEqual(landmask.tile_fraction(z, x, y, self.SEA), 0.0)
        self.assertGreater(landmask.tile_fraction(z, x, y, [-180, -85, 180, 85]), 0.0)

    def test_바다_칸은_바다_몫만큼(self):
        land, sea = self.plan(self.LAND), self.plan(self.SEA)
        self.assertEqual(sum(sea.sea.values()), sum(sea.counts.values()))
        self.assertEqual(land.sea, {})
        for z in (12, 13, 14):
            self.assertAlmostEqual(sea.bytes[("vworld:Base", z)],
                                   sea.counts[("vworld:Base", z)] * bake.guess_bytes("vworld:Base", z) * bake.SEA_SHARE["vworld:Base"])
            self.assertEqual(land.bytes[("vworld:Base", z)], land.counts[("vworld:Base", z)] * bake.guess_bytes("vworld:Base", z))
        self.assertIn("바다", sea.lines[0])

    def test_해안은_땅이_든_칸만큼(self):
        coast = self.plan(self.COAST)
        full = sum(coast.counts[("vworld:Base", z)] * bake.guess_bytes("vworld:Base", z) for z in (12, 13, 14))
        self.assertLess(coast.guess, full)
        self.assertGreater(coast.guess, full * landmask.fraction(self.COAST))           # 반쪽 칸을 반으로 세지 않는다 — 넘치는 쪽

    def test_표에_없는_레이어는_덜지_않는다(self):
        sea = self.plan(self.SEA, name="Bouguer_Gravity_Raster_2018")                   # 바다도 칠하는 레이어
        self.assertEqual(sea.sea, {})
        self.assertEqual(self.plan(self.SEA, share=0).guess, 0)                         # 소스가 밝히면 그것을 따른다

    def test_가진_것은_실제_크기로(self):
        class Cached(FakeSource):
            def cached(self, z, x, y):
                return b"" if (x + y) % 2 else b"x" * 1000             # 반은 빈 타일 — 묶음에 들지 않는다

        src = Cached("vworld:Base", bake.NoParts())
        plan = bake.Plan("t", dict(BOX, bbox=self.LAND, layers={"vworld:Base": [13, 13]}), {"vworld:Base": src})
        tiles = grid.tiles_for(self.LAND, 13)
        self.assertEqual(plan.bytes[("vworld:Base", 13)], 1000 * sum(1 for x, y in tiles if not (x + y) % 2))
