"""바람 — 굽기·목록·주소, 그리고 두 문의 푸는 길 (koprifossillab P02).

상류는 부르지 않는다. GFS 는 GRIB2 를 ecCodes 로 직접 만들어 풀어 보고, ERA5 는 blosc 덩이를 직접 만들어 "층만 잘라 받기" 를
흉내 낸다. 둘 다 numpy·ecCodes·numcodecs 가 있어야 돈다 — CI 는 `requirements-wind.txt` 를 깔고, 없는 곳에서는 건너뛴다.

**운영 이미지에는 numpy 가 없다.** 그래서 바람 모듈이 맨 위에서 numpy 를 부르지 않는지도 본다.
"""
import ast
import datetime as dt
import importlib.util
import json
import struct
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django.test import SimpleTestCase, override_settings

from viewer import era5, gfs, gmgsi, wind

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HAS_ECCODES = importlib.util.find_spec("eccodes") is not None
HAS_NUMCODECS = importlib.util.find_spec("numcodecs") is not None
HAS_H5PY = importlib.util.find_spec("h5py") is not None
VIEWER = Path(wind.__file__).parent


class 이미지에는_numpy_가_없다(SimpleTestCase):
    def test_바람_모듈은_맨_위에서_numpy_를_부르지_않는다(self):
        heavy = {"numpy", "eccodes", "numcodecs", "PIL", "h5py"}
        for name in ("wind.py", "gfs.py", "era5.py", "gmgsi.py"):
            tree = ast.parse((VIEWER / name).read_text(encoding="utf-8"))
            for node in tree.body:                      # 맨 위만 — 함수 안에서 부르는 것은 괜찮다
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                        [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for n in names:
                    self.assertNotIn(n.split(".")[0], heavy, f"{name} 가 맨 위에서 {n} 을 부른다")


class 자리와_목록(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(WIND_DIR=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_주소의_꼴(self):
        self.assertTrue(wind.valid("gfs", "2026100100", "10m"))
        self.assertTrue(wind.valid("era5", "20050601", "250hPa"))
        self.assertFalse(wind.valid("gfs", "20050601", "10m"))       # GFS 는 시각까지
        self.assertFalse(wind.valid("era5", "2005060100", "10m"))
        self.assertFalse(wind.valid("gfs", "2026100100", "500hPa"))

    def test_목록이_없으면_빈_목록에_출처를_붙인다(self):
        index = wind.read_index("gfs")
        self.assertEqual(index["times"], [])
        self.assertIn("GFS", index["credit"])

    def test_목록은_시각_차례로(self):
        wind.write_index("gfs", [{"t": "2026100106"}, {"t": "2026100100"}])
        self.assertEqual([e["t"] for e in wind.read_index("gfs")["times"]], ["2026100100", "2026100106"])

    def test_가장_새_것만_남긴다(self):
        stamps = [f"20261001{h:02d}" for h in (0, 6, 12, 18)]
        for s in stamps:
            (Path(self.tmp.name) / "gfs" / s).mkdir(parents=True)
        wind.write_index("gfs", [{"t": s} for s in stamps])
        self.assertEqual(wind.prune("gfs", 2), stamps[:2])
        self.assertEqual([e["t"] for e in wind.read_index("gfs")["times"]], stamps[2:])
        self.assertFalse((Path(self.tmp.name) / "gfs" / stamps[0]).exists())
        self.assertTrue((Path(self.tmp.name) / "gfs" / stamps[3]).exists())

    def test_목록_주소(self):
        wind.write_index("era5", [{"t": "20050601", "10m": {"u": [-1, 1], "v": [-2, 2]}}])
        body = self.client.get("/GSM/earth/wind/").json()
        self.assertEqual(set(body), {"gfs", "era5", "gmgsi"})
        self.assertEqual(body["era5"]["times"][0]["t"], "20050601")
        self.assertIn("Copernicus", body["era5"]["credit"])

    def test_PNG_주소(self):
        path = wind.png_path("gfs", "2026100100", "10m")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\x89PNG fake")
        got = self.client.get("/GSM/earth/wind/gfs/2026100100/10m.png")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/GSM/earth/wind/gfs/2026100106/10m.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/earth/wind/era5/2026100100/10m.png").status_code, 404)

    @skipUnless(HAS_NUMPY, "numpy 가 없다 — 운영 이미지")
    def test_굽기는_경도를_돌리고_값을_되돌릴_수_있다(self):
        import numpy as np
        from PIL import Image
        lon = np.arange(1440) * 0.25                      # 경도 0 부터
        u = np.tile(np.where(lon < 180, 10.0, -10.0), (721, 1)).astype("f4")
        v = np.tile(np.linspace(-5, 5, 721)[:, None], (1, 1440)).astype("f4")
        entry = wind.write_time("gfs", "2026100100", {"10m": (u, v)})
        self.assertEqual(entry["10m"]["u"], [-10.0, 10.0])
        img = np.asarray(Image.open(wind.png_path("gfs", "2026100100", "10m")))
        self.assertEqual(img.shape, (721, 1440, 3))
        # 열 0 이 경도 −180(원본의 180°, 값 −10), 열 720 이 경도 0(값 +10)
        self.assertEqual(img[0, 0, 0], 0)
        self.assertEqual(img[0, 720, 0], 255)
        self.assertEqual(img[0, 0, 1], 0)                 # 맨 위(위도 90)가 v 의 최솟값
        self.assertFalse((Path(self.tmp.name) / "gfs" / "2026100100.part").exists())

    @skipUnless(HAS_NUMPY, "numpy 가 없다 — 운영 이미지")
    def test_빈_값이_섞이면_굽지_않는다(self):
        import numpy as np
        u = np.zeros((721, 1440), "f4")
        u[0, 0] = np.nan
        with self.assertRaises(ValueError):
            wind.encode(u, np.zeros((721, 1440), "f4"))


class GFS(SimpleTestCase):
    def test_가까운_지난_판부터(self):
        now = dt.datetime(2026, 10, 1, 5, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(gfs.recent_cycles(now, 3), ["2026100100", "2026093018", "2026093012"])

    def test_받는_것은_두_높이의_u_v(self):
        q = gfs.params("2026100106")
        self.assertEqual(q["dir"], "/gfs.20261001/06/atmos")
        self.assertEqual(q["file"], "gfs.t06z.pgrb2.0p25.f000")
        for key in ("var_UGRD", "var_VGRD", "lev_10_m_above_ground", "lev_250_mb"):
            self.assertEqual(q[key], "on")

    def test_예보_장의_파일과_유효_시각(self):
        self.assertEqual(gfs.params("2026100106", 9)["file"], "gfs.t06z.pgrb2.0p25.f009")
        self.assertEqual(gfs.valid_time("2026100118", 12), "2026100206")       # 날을 넘는다
        self.assertEqual(gfs.FORECAST_HOURS[0], 0)
        self.assertGreaterEqual(gfs.FORECAST_HOURS[-1], 12)                     # 다음 판이 올라오기까지를 덮는다

    def test_아직_없는_판은_None(self):
        fake = mock.Mock(status_code=404, content=b"<html>no file</html>")
        with mock.patch("viewer.gfs.requests.get", return_value=fake), mock.patch("viewer.gfs.usage.record") as rec:
            self.assertIsNone(gfs.download("2026100106"))
        rec.assert_called_once_with("gfs", ok=True)         # 실패로 세지 않는다

    def test_막히면_멈춘다(self):
        fake = mock.Mock(status_code=403, content=b"forbidden")
        with mock.patch("viewer.gfs.requests.get", return_value=fake), mock.patch("viewer.gfs.usage.record"):
            with self.assertRaises(gfs.GfsError):
                gfs.download("2026100106")

    @skipUnless(HAS_ECCODES and HAS_NUMPY, "ecCodes 가 없다")
    def test_GRIB2_를_풀어_높이마다_u_v(self):
        import eccodes
        import numpy as np
        msgs = []
        for short, level_type, level, value in (("10u", "heightAboveGround", 10, 3.0), ("10v", "heightAboveGround", 10, -4.0),
                                                ("u", "isobaricInhPa", 250, 50.0), ("v", "isobaricInhPa", 250, -7.0)):
            h = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            for key, val in (("Ni", 1440), ("Nj", 721), ("latitudeOfFirstGridPointInDegrees", 90),
                             ("longitudeOfFirstGridPointInDegrees", 0), ("latitudeOfLastGridPointInDegrees", -90),
                             ("longitudeOfLastGridPointInDegrees", 359.75), ("iDirectionIncrementInDegrees", 0.25),
                             ("jDirectionIncrementInDegrees", 0.25), ("typeOfLevel", level_type), ("level", level),
                             ("shortName", short)):
                eccodes.codes_set(h, key, val)
            eccodes.codes_set_values(h, np.full(1440 * 721, value))
            msgs.append(eccodes.codes_get_message(h))
            eccodes.codes_release(h)
        out = gfs.decode(b"".join(msgs))
        self.assertEqual(set(out), {"10m", "250hPa"})
        self.assertAlmostEqual(float(out["10m"][0][100, 100]), 3.0, places=2)
        self.assertAlmostEqual(float(out["250hPa"][1][0, 0]), -7.0, places=2)
        self.assertEqual(out["10m"][0].shape, (721, 1440))


class ERA5(SimpleTestCase):
    def test_시간_번호는_1900_년부터(self):
        self.assertEqual(era5.time_index(dt.datetime(1900, 1, 2)), 24)
        self.assertEqual(era5.PRESSURE_LEVELS.index(250), 16)

    @skipUnless(HAS_NUMCODECS and HAS_NUMPY, "numcodecs 가 없다")
    def test_층만_잘라_받아도_통째와_같다(self):
        """37 층 덩이를 직접 눌러 두고, Range 요청을 그 바이트로 흉내 낸다. 받은 바이트도 센다."""
        import numpy as np
        from numcodecs import blosc
        # 바람처럼 매끄러운 값 — 눌린다. 블록 표를 읽고 그 층의 블록만 받는 길
        z, y, x = np.meshgrid(np.arange(37), np.linspace(-1, 1, 721), np.linspace(0, 6, 1440), indexing="ij")
        cube = (np.sin(x + z) * 30 + y * 5).astype("<f4")
        self._check(cube, blosc.compress(cube.tobytes(), b"lz4", 5, blosc.SHUFFLE, 4))

    @skipUnless(HAS_NUMCODECS and HAS_NUMPY, "numcodecs 가 없다")
    def test_눌리지_않은_덩이도(self):
        """누를 수 없는 값이면 blosc 는 덩이를 그대로 담는다(memcpy) — 블록 표가 없다."""
        import numpy as np
        from numcodecs import blosc
        cube = np.random.default_rng(0).normal(size=(37, 721, 1440)).astype("<f4")
        packed = blosc.compress(cube.tobytes(), b"lz4", 5, blosc.SHUFFLE, 4)
        self.assertTrue(packed[2] & 0x02)
        self._check(cube, packed)

    def _check(self, cube, packed):
        import numpy as np
        asked = []

        def fake_get(url, byte_range=None):
            lo, hi = byte_range
            asked.append(hi - lo + 1)
            return packed[lo:hi + 1]

        with mock.patch("viewer.era5._get", side_effect=fake_get):
            plane = np.frombuffer(era5._level_plane("http://x/u/0.0.0.0", 16), dtype="<f4").reshape(721, 1440)
        np.testing.assert_array_equal(plane, cube[16])
        self.assertLess(sum(asked), len(packed) / 10)      # 덩이의 열 분의 일도 안 받는다


class 백업_목록(SimpleTestCase):
    def test_지금의_바람은_구운_것_목록에서_뺀다(self):
        script = (VIEWER.parents[1] / "deploy" / "scripts" / "weekly_backup.sh").read_text(encoding="utf-8")
        self.assertIn("wind/gfs/.*", script)
        self.assertIn("wind/gmgsi/.*", script)              # 위성 구름도 한 시간마다 바뀐다


class 시험용_목록_꼴(SimpleTestCase):
    def test_목록은_JSON_이다(self):
        with tempfile.TemporaryDirectory() as d, override_settings(WIND_DIR=d):
            wind.write_index("gfs", [{"t": "2026100100"}])
            data = json.loads((Path(d) / "gfs" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(data["width"], 1440)
        self.assertEqual(data["levels"], ["10m", "250hPa"])


@override_settings()
class 지금의_바람_받기(SimpleTestCase):
    """`fetch_gfs_wind` — 상류와 굽기를 흉내 낸다. 판마다 어느 장을 받는지, 새 판이 이기는지 (koprifossillab 008)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(WIND_DIR=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)
        self.asked = []

    def run_cmd(self, up, now):
        """`up` — 올라와 있는 (판, 예보 시간). `now` — 그때의 UTC."""
        from django.core.management import call_command

        def fake_download(cycle, fh=0):
            self.asked.append((cycle, fh))
            return b"GRIB" if (cycle, fh) in up else None

        def fake_write(source, stamp, fields, clouds=None):
            (Path(self.tmp.name) / source / stamp).mkdir(parents=True, exist_ok=True)
            return {"t": stamp, "clouds": ["total"]}

        class FakeNow(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        with mock.patch("viewer.gfs.download", side_effect=fake_download), \
             mock.patch("viewer.gfs.decode_all", return_value=({}, {})), \
             mock.patch("viewer.wind.write_time", side_effect=fake_write), \
             mock.patch("viewer.management.commands.fetch_gfs_wind.dt.datetime", FakeNow):
            call_command("fetch_gfs_wind", pause=0, stdout=mock.Mock())
        return {e["t"]: (e["run"], e["fh"]) for e in wind.read_index("gfs")["times"]}

    def test_가장_새_판의_분석과_예보를_받는다(self):
        now = dt.datetime(2026, 10, 1, 10, 40, tzinfo=dt.timezone.utc)
        up = {("2026100106", h) for h in gfs.FORECAST_HOURS}
        got = self.run_cmd(up, now)
        self.assertEqual(got["2026100106"], ("2026100106", 0))
        self.assertEqual(got["2026100118"], ("2026100106", 12))

    def test_분석이_아직이면_앞_판으로(self):
        now = dt.datetime(2026, 10, 1, 13, 0, tzinfo=dt.timezone.utc)     # 12 판은 아직
        up = {("2026100106", h) for h in gfs.FORECAST_HOURS}
        got = self.run_cmd(up, now)
        self.assertIn(("2026100112", 0), self.asked)
        self.assertNotIn(("2026100112", 3), self.asked)                   # 분석이 없으면 예보를 묻지 않는다
        self.assertEqual(got["2026100112"], ("2026100106", 6))            # 그 시각은 앞 판의 예보로

    def test_새_판이_같은_시각을_이긴다(self):
        up = {("2026100106", h) for h in gfs.FORECAST_HOURS}
        self.run_cmd(up, dt.datetime(2026, 10, 1, 11, 0, tzinfo=dt.timezone.utc))
        up |= {("2026100112", h) for h in gfs.FORECAST_HOURS}
        got = self.run_cmd(up, dt.datetime(2026, 10, 1, 17, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(got["2026100112"], ("2026100112", 0))            # 06 판의 +6 예보가 12 판의 분석으로
        self.assertEqual(got["2026100109"], ("2026100106", 3))            # 12 판이 내지 않는 시각은 그대로

    def test_빠진_장만_다시_받는다(self):
        now = dt.datetime(2026, 10, 1, 10, 40, tzinfo=dt.timezone.utc)
        self.run_cmd({("2026100106", 0), ("2026100106", 3)}, now)
        self.asked.clear()
        self.run_cmd({("2026100106", h) for h in gfs.FORECAST_HOURS}, now)
        self.assertEqual(self.asked, [("2026100106", h) for h in (6, 9, 12)])

    def test_구름이_없는_장은_다시_받는다(self):
        """0.35 까지 받은 장에는 구름이 없다 — 구름을 받으려고 그 판을 다시 받는다 (koprifossillab 011)."""
        now = dt.datetime(2026, 10, 1, 10, 40, tzinfo=dt.timezone.utc)
        wind.write_index("gfs", [{"t": gfs.valid_time("2026100106", h), "run": "2026100106", "fh": h}
                                 for h in gfs.FORECAST_HOURS])
        self.run_cmd({("2026100106", h) for h in gfs.FORECAST_HOURS}, now)
        self.assertEqual(self.asked, [("2026100106", h) for h in gfs.FORECAST_HOURS])

    def test_오래된_것은_지운다(self):
        stamps = ["2026092800", "2026093006", "2026100106"]
        for s in stamps:
            (Path(self.tmp.name) / "gfs" / s).mkdir(parents=True)
        wind.write_index("gfs", [{"t": s, "run": s, "fh": 0} for s in stamps])
        self.assertEqual(wind.prune_before("gfs", "2026093000"), ["2026092800"])
        self.assertFalse((Path(self.tmp.name) / "gfs" / "2026092800").exists())


class 구름(SimpleTestCase):
    """구름량 — 주소·굽기·GFS 의 순간값 고르기·ERA5 덧굽기 (koprifossillab 011)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(WIND_DIR=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_구름_주소의_꼴(self):
        for kind in wind.CLOUD_KINDS:
            self.assertTrue(wind.valid("gfs", "2026100106", f"cloud-{kind}"))
        self.assertFalse(wind.valid("gfs", "2026100106", "cloud-fog"))
        path = Path(self.tmp.name) / "era5" / "20050601" / "cloud-low.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\x89PNG fake")
        self.assertEqual(self.client.get("/GSM/earth/wind/era5/20050601/cloud-low.png").status_code, 200)
        self.assertEqual(self.client.get("/GSM/earth/wind/era5/20050601/cloud-fog.png").status_code, 404)

    def test_GFS_요청에_구름_변수와_층(self):
        q = gfs.params("2026100106", 3)
        for key in ("var_TCDC", "var_LCDC", "var_MCDC", "var_HCDC", "lev_entire_atmosphere", "lev_low_cloud_layer",
                    "lev_middle_cloud_layer", "lev_high_cloud_layer"):
            self.assertEqual(q[key], "on")

    @skipUnless(HAS_NUMPY, "numpy 가 없다 — 운영 이미지")
    def test_회색으로_굽고_경도를_돌린다(self):
        import numpy as np
        from PIL import Image
        lon = np.arange(1440) * 0.25
        frac = np.tile(np.where(lon < 180, 1.0, 0.0), (721, 1)).astype("f4")
        entry = wind.write_time("gfs", "2026100106", {}, {"total": frac, "low": frac * 0.5})
        self.assertEqual(entry["clouds"], ["total", "low"])
        img = np.asarray(Image.open(wind.png_path("gfs", "2026100106", "cloud-total")))
        self.assertEqual(img.shape, (721, 1440))
        self.assertEqual(img[0, 0], 0)          # 열 0 = 경도 −180 = 원본의 180°(구름 없음)
        self.assertEqual(img[0, 720], 255)      # 열 720 = 경도 0(구름 가득)

    @skipUnless(HAS_NUMPY, "numpy 가 없다 — 운영 이미지")
    def test_이미_구운_날에_구름만_덧굽는다(self):
        import numpy as np
        stamp_dir = Path(self.tmp.name) / "era5" / "20050601"
        stamp_dir.mkdir(parents=True)
        (stamp_dir / "10m.png").write_bytes(b"wind")
        kinds = wind.add_clouds("era5", "20050601", {k: np.zeros((721, 1440), "f4") for k in wind.CLOUD_KINDS})
        self.assertEqual(kinds, list(wind.CLOUD_KINDS))
        self.assertEqual((stamp_dir / "10m.png").read_bytes(), b"wind")      # 바람은 그대로
        self.assertTrue((stamp_dir / "cloud-high.png").exists())
        self.assertFalse(list(stamp_dir.glob("*.part")))

    @skipUnless(HAS_ECCODES and HAS_NUMPY, "ecCodes 가 없다")
    def test_GFS_의_순간값만_고른다(self):
        import eccodes
        import numpy as np

        def message(short, tol, value, step_type="instant", level=0):
            h = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            for key, val in (("Ni", 1440), ("Nj", 721), ("latitudeOfFirstGridPointInDegrees", 90),
                             ("longitudeOfFirstGridPointInDegrees", 0), ("latitudeOfLastGridPointInDegrees", -90),
                             ("longitudeOfLastGridPointInDegrees", 359.75), ("iDirectionIncrementInDegrees", 0.25),
                             ("jDirectionIncrementInDegrees", 0.25), ("typeOfLevel", tol), ("level", level)):
                eccodes.codes_set(h, key, val)
            if step_type == "avg":
                eccodes.codes_set(h, "stepType", "avg")
                eccodes.codes_set(h, "startStep", 0)
                eccodes.codes_set(h, "endStep", 3)
            eccodes.codes_set(h, "shortName", short)
            eccodes.codes_set_values(h, np.full(1440 * 721, value))
            out = eccodes.codes_get_message(h)
            eccodes.codes_release(h)
            return out

        msgs = [message("10u", "heightAboveGround", 1.0, level=10), message("10v", "heightAboveGround", 2.0, level=10),
                message("u", "isobaricInhPa", 3.0, level=250), message("v", "isobaricInhPa", 4.0, level=250),
                message("tcc", "isobaricInhPa", 99.0, level=250),        # 기압면의 구름량 — 거른다
                message("lcc", "lowCloudLayer", 40.0), message("lcc", "lowCloudLayer", 90.0, "avg")]
        winds, clouds = gfs.decode_all(b"".join(msgs))
        self.assertEqual(set(winds), {"10m", "250hPa"})
        self.assertEqual(set(clouds), {"low"})
        self.assertAlmostEqual(float(clouds["low"][0, 0]), 0.40, places=2)    # 순간값, 퍼센트 -> 비율


class 위성_구름(SimpleTestCase):
    """NOAA GMGSI — 열쇠·주소·메르카토르 펴기·굽기·받기 (koprifossillab 012)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(WIND_DIR=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_열쇠의_시각(self):
        key = "GMGSI_LW/2026/10/01/10/GLOBCOMPLIR_v3r0_blend_s202610011000000_e202610011009599_c202610011033586.nc"
        self.assertEqual(gmgsi.stamp_of(key), "2026100110")

    def test_주소는_sat_만(self):
        self.assertTrue(wind.valid("gmgsi", "2026100110", "sat"))
        self.assertFalse(wind.valid("gmgsi", "2026100110", "10m"))
        self.assertFalse(wind.valid("gfs", "2026100110", "sat"))
        path = Path(self.tmp.name) / "gmgsi" / "2026100110" / "sat.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\x89PNG fake")
        self.assertEqual(self.client.get("/GSM/earth/wind/gmgsi/2026100110/sat.png").status_code, 200)
        self.assertIn("gmgsi", self.client.get("/GSM/earth/wind/").json())

    @skipUnless(HAS_H5PY and HAS_NUMPY, "h5py 가 없다")
    def test_메르카토르를_경위도로_편다(self):
        """날짜변경선부터 도는 경도, 행마다 간격이 다른 위도 — 북반구 동경 쪽만 밝게 칠해 두고 편 뒤 자리를 본다."""
        import io

        import h5py
        import numpy as np
        nx, ny = 500, 300
        lon = (180 + np.arange(nx) * 360 / nx + 180) % 360 - 180          # 180 부터
        merc = np.linspace(np.log(np.tan(np.pi / 4 + np.radians(72.7) / 2)), -np.log(np.tan(np.pi / 4 + np.radians(72.7) / 2)), ny)
        lat = np.degrees(2 * np.arctan(np.exp(merc)) - np.pi / 2)
        data = np.where((lat[:, None] > 0) & (lon[None, :] > 0), 250.0, 50.0).astype("f4")[None]
        buf = io.BytesIO()
        with h5py.File(buf, "w") as f:
            f["data"] = data
            f["lat"] = np.repeat(lat[:, None], nx, axis=1).astype("f4")
            f["lon"] = np.repeat(lon[None, :], ny, axis=0).astype("f4")
        grid = gmgsi.decode(buf.getvalue())
        self.assertEqual(grid.shape, (gmgsi.HEIGHT, gmgsi.WIDTH))
        self.assertEqual(grid[0, 0], 0)                          # 위도 72.7° 너머는 비운다
        self.assertGreater(grid[600, 2700], 200)                 # 북위 30° 동경 90° — 밝다
        self.assertLess(grid[600, 900], 100)                     # 북위 30° 서경 90° — 어둡다
        self.assertLess(grid[1200, 2700], 100)                   # 남위 30° 동경 90° — 어둡다

    @skipUnless(HAS_NUMPY, "numpy 가 없다 — 운영 이미지")
    def test_맑은_곳은_비우고_구름만_희게(self):
        import numpy as np
        from PIL import Image
        gray = np.zeros((1800, 3600), np.uint8)
        gray[:, 1800:] = 250
        gray[:, :900] = 90                                       # 맑은 열대 바다쯤
        wind.write_sat("2026100110", gray)
        img = np.asarray(Image.open(wind.png_path("gmgsi", "2026100110", "sat")))
        self.assertEqual(img.shape, (1800, 3600, 4))
        self.assertEqual(img[900, 100, 3], 0)
        self.assertGreater(img[900, 2000, 3], 200)
        self.assertEqual(tuple(img[900, 2000, :3]), (255, 255, 255))

    def test_받기는_가장_새_장_하나(self):
        from django.core.management import call_command

        class FakeNow(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt.datetime(2026, 10, 1, 11, 10, tzinfo=dt.timezone.utc)

        asked = []

        def fake_key(hour):
            asked.append(hour.strftime("%Y%m%d%H"))
            return None if hour.hour == 11 else f"GMGSI_LW/x_s{hour:%Y%m%d%H}00000_e.nc"

        def fake_write(stamp, gray):
            (Path(self.tmp.name) / "gmgsi" / stamp).mkdir(parents=True, exist_ok=True)
            return {"t": stamp}

        with mock.patch("viewer.gmgsi.hour_key", side_effect=fake_key), \
             mock.patch("viewer.gmgsi.download", return_value=b"x"), \
             mock.patch("viewer.gmgsi.decode", return_value=None), \
             mock.patch("viewer.wind.write_sat", side_effect=fake_write), \
             mock.patch("viewer.management.commands.fetch_gmgsi.dt.datetime", FakeNow):
            call_command("fetch_gmgsi", stdout=mock.Mock())
            call_command("fetch_gmgsi", stdout=mock.Mock())
        self.assertEqual([e["t"] for e in wind.read_index("gmgsi")["times"]], ["2026100110"])
        self.assertEqual(asked, ["2026100111", "2026100110", "2026100111"])     # 둘째는 10 시가 있어 멈춘다
