"""남극 IBCSO v2 — 9354 원본을 3031 격자로 자르기 (047).

두 평사도법은 표준위도만 달라 곱셈 하나로 오간다. 그 배율이 맞으면 원본의 화소가 제자리에 간다.
"""
import io
import math
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import geomap, ibcso


def ps_south(lat, lon, lat_ts):
    """남극 평사도법 (WGS84, 경도 0 이 위) — 표준위도만 바꿔 부른다."""
    a, e = 6378137.0, geomap._E
    phi, pc = math.radians(-lat), math.radians(lat_ts)
    t = lambda p: math.tan(math.pi / 4 - p / 2) / ((1 - e * math.sin(p)) / (1 + e * math.sin(p))) ** (e / 2)
    m = lambda p: math.cos(p) / math.sqrt(1 - (e * math.sin(p)) ** 2)
    rho = a * m(pc) * t(phi) / t(pc)
    lam = math.radians(lon)
    return rho * math.sin(lam), rho * math.cos(lam)


class Grid(SimpleTestCase):
    def test_배율은_3031_과_9354_의_거리_비(self):
        for lat, lon in [(-77.85, 166.67), (-62.22, -58.79), (-89.0, 45.0)]:
            x31, y31 = geomap.lonlat_to_3031(lon, lat)
            x93, y93 = ps_south(lat, lon, 65.0)
            self.assertAlmostEqual(x31 / x93, ibcso.SCALE, places=9)
            self.assertAlmostEqual(y31 / y93, ibcso.SCALE, places=9)

    def test_한_점이_원본의_제_화소에_간다(self):
        lat, lon, z = -77.85, 166.67, 6                     # 맥머도
        x31, y31 = geomap.lonlat_to_3031(lon, lat)
        tx, ty = geomap.tile_of(z, x31, y31)
        left, top, right, bottom = ibcso.source_box(z, tx, ty)
        x93, y93 = ps_south(lat, lon, 65.0)
        col, row = (x93 + 4800000) / 500, (4800000 - y93) / 500
        self.assertTrue(left <= col <= right and top <= row <= bottom)

    def test_z0_은_원본의_가운데를_덮는다(self):
        left, top, right, bottom = ibcso.source_box(0, 0, 0)
        self.assertAlmostEqual((left + right) / 2, 9600, places=6)
        self.assertAlmostEqual((top + bottom) / 2, 9600, places=6)
        self.assertLess(left, 9600 - 6000)                  # 남위 60° 넘어까지

    def test_자르기_밖은_투명(self):
        level = Image.new("RGBa", (600, 600), (40, 80, 120, 255))     # 원본의 1/32
        tile = ibcso.cut(level, 32, 0, 0, 0)
        self.assertEqual(tile.size, (256, 256))
        self.assertEqual(tile.getpixel((128, 128))[3], 255)
        self.assertIsNone(ibcso.cut(Image.new("RGBa", (600, 600), (0, 0, 0, 0)), 32, 0, 0, 0))


class View(TestCase):
    def test_잘라_두지_않았으면_안내_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            r = self.client.get("/GSM/ibcso/bed/3/2/2.webp")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_잘라_둔_것을_내고_없는_자리는_빈_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            p = Path(d) / "tiles-ice" / "3" / "2" / "2.webp"
            p.parent.mkdir(parents=True)
            buf = io.BytesIO()
            Image.new("RGBA", (256, 256), (1, 2, 3, 255)).save(buf, "WEBP")
            p.write_bytes(buf.getvalue())
            r = self.client.get("/GSM/ibcso/ice/3/2/2.webp")
            self.assertEqual(r["Content-Type"], "image/webp")
            r = self.client.get("/GSM/ibcso/ice/3/0/0.webp")
            self.assertEqual(r["Content-Type"], "image/png")

    def test_줌_밖과_모르는_판은_404(self):
        self.assertEqual(self.client.get("/GSM/ibcso/bed/7/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/ibcso/bed/2/4/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/ibcso/nope/2/0/0.webp").status_code, 404)


class Dem(SimpleTestCase):
    """수치 격자 — 3D 의 지형 (051). 16 비트 타일로 잘라 두고, 3857 로 펴서 Terrarium 으로 낸다."""

    def grid(self, rows):
        from PIL import ImageMath
        image = Image.new("I", (len(rows[0]), len(rows)))
        image.putdata([v for row in rows for v in row])
        fill = ImageMath.lambda_eval(lambda a: a["float"](a["notequal"](a["v"], ibcso.DEM_NODATA)), v=image)
        value = ImageMath.lambda_eval(lambda a: a["float"](a["v"]) * a["f"], v=image, f=fill)
        return value, fill

    def test_자르고_풀면_같은_값(self):
        value, fill = self.grid([[-4321, 1234], [ibcso.DEM_NODATA, 0]])
        data = ibcso.encode_dem(ibcso.cut_dem(value, fill, 0, 0))
        v, f = ibcso.decode_dem(data)
        self.assertEqual(v.getpixel((0, 0)), -4321)
        self.assertEqual(v.getpixel((1, 0)), 1234)
        self.assertEqual(v.getpixel((1, 1)), 0)
        self.assertEqual(f.getpixel((0, 1)), 0)          # 빈 곳
        self.assertEqual(f.getpixel((1, 1)), 1)          # 해수면 0 m 는 빈 곳이 아니다
        self.assertEqual(f.getpixel((5, 5)), 0)          # 격자 밖

    def test_줄일_때_빈_곳은_평균에서_뺀다(self):
        value, fill = self.grid([[-100, -300], [ibcso.DEM_NODATA, ibcso.DEM_NODATA]])
        v, f = ibcso.halve(value, fill)
        self.assertAlmostEqual(v.getpixel((0, 0)), -200)
        self.assertEqual(f.getpixel((0, 0)), 1)

    def test_다_비면_None(self):
        value, fill = self.grid([[ibcso.DEM_NODATA]])
        self.assertIsNone(ibcso.cut_dem(value, fill, 0, 0))

    def test_단계_6_은_원본_그대로(self):
        self.assertEqual(ibcso.dem_res(6), 500)
        self.assertEqual(ibcso.dem_tiles(6), 75)
        self.assertEqual(ibcso.dem_tiles(0), 2)
        x, y = ibcso.to_9354(-77.85, 166.67)
        self.assertAlmostEqual(x, ps_south(-77.85, 166.67, 65.0)[0], delta=0.01)
        self.assertAlmostEqual(y, ps_south(-77.85, 166.67, 65.0)[1], delta=0.01)


class DemView(TestCase):
    """`dem/` 가 남위 50° 남쪽을 IBCSO 로 낸다. 잘라 둔 것이 없으면 AWS 로 넘긴다."""

    def build(self, d, kind, value):
        """단계 0~6 을 한 값으로 채운 타일 — 어느 단계를 골라도 걸린다."""
        from PIL import ImageMath
        sheet = ibcso.DEMS[kind]
        flat = Image.new("F", (256, 256), float(value))
        ones = Image.new("F", (256, 256), 1.0)
        data = ibcso.encode_dem(ibcso.cut_dem(flat, ones, 0, 0))
        for level in range(ibcso.DEM_MAX_LEVEL + 1):
            for x in range(ibcso.dem_tiles(level)):
                for y in range(ibcso.dem_tiles(level)):
                    p = Path(d) / sheet.folder / str(level) / str(x) / f"{y}.png"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(data)

    def decode(self, png):
        r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel((128, 128))
        return r * 256 + g + b / 256 - 32768

    def test_남극_바다는_IBCSO_로_낸다(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d, TILE_CACHE_DIR=d + "/cache"):
            self.build(d, "ice", -3000)
            self.build(d, "bed", -3500)
            # 웨들해 (남위 65°, 서경 30°) z6
            r = self.client.get("/GSM/dem/6/26/47.png")
            self.assertEqual(r.status_code, 200)
            self.assertAlmostEqual(self.decode(r.content), -3000, delta=0.01)
            r = self.client.get("/GSM/dem/bed/6/26/47.png")
            self.assertAlmostEqual(self.decode(r.content), -3500, delta=0.01)

    def test_잘라_두지_않았으면_AWS(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d, TILE_CACHE_DIR=d + "/cache"):
            r = self.client.get("/GSM/dem/6/26/47.png")
        self.assertEqual(r.status_code, 302)
        self.assertIn("elevation-tiles-prod", r["Location"])

    def test_북쪽은_bed_도_AWS(self):
        r = self.client.get("/GSM/dem/bed/6/54/24.png")          # 한반도
        self.assertEqual(r.status_code, 302)

    def test_3D_배경을_잘라_두지_않았으면_안내_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            r = self.client.get("/GSM/warp/ibcso/ice/3/2/6.png")
            self.assertEqual(r["Cache-Control"], "no-store")
            r = self.client.get("/GSM/warp/ibcso/ice/3/2/2.png")      # 남위 50° 북쪽 — 빈 타일
            self.assertEqual(r.status_code, 200)
            self.assertNotEqual(r.get("Cache-Control"), "no-store")


def write_dem_tile(d, kind, level, x, y, image_f, fill_f):
    p = Path(d) / ibcso.DEMS[kind].folder / str(level) / str(x) / f"{y}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(ibcso.encode_dem(ibcso.cut_dem(image_f, fill_f, 0, 0)))


def tile_of_point(lat, lon):
    col, row = ibcso._pixel_of(lat, lon)
    return int(col // 256), int(row // 256), col % 256, row % 256


#: 맥머도 앞 로스 빙붕 — 얼음 위와 해저가 다르다
ROSS = (-78.5, 175.0)


class Depths(SimpleTestCase):
    """누른 자리의 수심·표고 (070) — 잘라 둔 수치 타일(단계 6)에서 읽는다."""

    def test_두_판을_읽는다(self):
        tx, ty, _, _ = tile_of_point(*ROSS)
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            ones = Image.new("F", (256, 256), 1.0)
            write_dem_tile(d, "ice", 6, tx, ty, Image.new("F", (256, 256), 42.0), ones)
            write_dem_tile(d, "bed", 6, tx, ty, Image.new("F", (256, 256), -623.0), ones)
            got = ibcso.depths({"a": ROSS, "north": (-40.0, 0.0)})
        self.assertEqual(got, {"a": {"ice": 42, "bed": -623}})

    def test_이웃을_섞는다(self):
        tx, ty, fx, fy = tile_of_point(*ROSS)
        ramp = Image.new("F", (256, 256))
        ramp.putdata([float(x * 10) for y in range(256) for x in range(256)])   # 오른쪽으로 한 화소에 10 m
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            write_dem_tile(d, "bed", 6, tx, ty, ramp, Image.new("F", (256, 256), 1.0))
            got = ibcso.depths({"a": ROSS})["a"]["bed"]
        # 화소 가운데가 +0.5 다. 가장자리 화소가 아니면 쌍선형은 (fx − 0.5)·10 이다
        if 1 <= fx <= 255:
            self.assertAlmostEqual(got, round((fx - 0.5) * 10), delta=1)

    def test_빈_곳이_섞이면_가까운_화소(self):
        tx, ty, fx, fy = tile_of_point(*ROSS)
        value = Image.new("F", (256, 256), -500.0)
        fill = Image.new("F", (256, 256), 1.0)
        # 누른 화소의 오른쪽 이웃을 비운다
        px, py = int(fx), int(fy)
        nx = min(255, px + 1) if fx - px >= 0.5 else px
        fill.putpixel((nx, py), 0.0)
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            write_dem_tile(d, "bed", 6, tx, ty, value, fill)
            got = ibcso.depths({"a": ROSS})
        if (nx, py) != (px, py):
            self.assertEqual(got["a"]["bed"], -500)

    def test_잘라_두지_않았으면_빈_것(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            self.assertEqual(ibcso.depths({"a": ROSS}), {})


class Tid(SimpleTestCase):
    """자료 출처(TID, 071) — 번호라 섞지 않는다."""

    def test_번호를_팔레트로_칠한다(self):
        codes = Image.new("L", (4, 1))
        codes.putdata([0, 11, 41, ibcso.TID_NONE])
        painted = ibcso.tid_paint(codes)
        palette = painted.getpalette()
        index = painted.getpixel((1, 0))
        self.assertEqual(tuple(palette[index * 3:index * 3 + 3]), ibcso.TID_CLASSES[11][1])
        self.assertEqual(painted.getpixel((0, 0)), 0)           # 육지는 칠하지 않는다
        self.assertEqual(painted.getpixel((3, 0)), 0)           # 빈 곳도

    def test_자를_때_섞지_않는다(self):
        codes = Image.new("L", (600, 600), 11)
        codes.paste(41, (0, 0, 300, 600))
        painted = ibcso.tid_paint(codes)
        tile = ibcso.cut_tid(painted, 32, 0, 0, 0)
        used = {i for _, i in tile.getcolors()}
        lut, _ = ibcso._tid_palette()
        self.assertTrue(used <= {0, lut[11], lut[41]})         # 두 갈래 사이의 색이 생기지 않는다
        data = ibcso.encode_tid(tile)
        self.assertEqual(Image.open(io.BytesIO(data)).info.get("transparency"), 0)

    def test_다_빈_타일은_None(self):
        self.assertIsNone(ibcso.cut_tid(ibcso.tid_paint(Image.new("L", (600, 600), 0)), 32, 0, 0, 0))
        self.assertIsNone(ibcso.cut_tid_raw(Image.new("L", (300, 300), ibcso.TID_NONE), 0, 0))

    def test_누른_자리의_번호(self):
        tx, ty, _, _ = tile_of_point(*ROSS)
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            p = Path(d) / "tid-raw" / "6" / str(tx) / f"{ty}.png"
            p.parent.mkdir(parents=True)
            Image.new("L", (256, 256), 70).save(p)
            self.assertEqual(ibcso.tid_at({"a": ROSS, "b": (-10.0, 0.0)}), {"a": 70})
        self.assertEqual(ibcso.tid_label(70), "미리 만든 격자")
        self.assertEqual(ibcso.tid_label(0), "육지")

    def test_범례는_세_묶음(self):
        legend = ibcso.tid_legend("en")
        self.assertEqual([g["name"] for g in legend["groups"]],
                         ["Direct measurements", "Indirect measurements", "Mixed or unknown source"])
        self.assertEqual(sum(len(g["rows"]) for g in legend["groups"]), len(ibcso.TID_CLASSES))


class DepthView(TestCase):
    def test_수심과_자료_출처(self):
        tx, ty, _, _ = tile_of_point(*ROSS)
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            ones = Image.new("F", (256, 256), 1.0)
            write_dem_tile(d, "bed", 6, tx, ty, Image.new("F", (256, 256), -623.0), ones)
            p = Path(d) / "tid-raw" / "6" / str(tx) / f"{ty}.png"
            p.parent.mkdir(parents=True)
            Image.new("L", (256, 256), 11).save(p)
            r = self.client.get("/GSM/ibcso/depth/", {"lat": ROSS[0], "lon": ROSS[1]})
            self.assertEqual(r.json(), {"bed": -623, "tid": "멀티빔 측심"})
            r = self.client.get("/GSM/ibcso/info/", {"lat": ROSS[0], "lon": ROSS[1]})
            self.assertEqual(r.json()["features"][0]["props"],
                             {"자료 출처": "멀티빔 측심", "TID": 11, "해저·빙저 (m)": -623})
        self.assertEqual(self.client.get("/GSM/ibcso/depth/", {"lat": "x"}).status_code, 400)

    def test_자료_밖은_빈_것(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            self.assertEqual(self.client.get("/GSM/ibcso/depth/", {"lat": 37, "lon": 127}).json(), {})
            self.assertEqual(self.client.get("/GSM/ibcso/info/", {"lat": 37, "lon": 127}).json(),
                             {"features": []})

    def test_TID_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            r = self.client.get("/GSM/ibcso/tid/3/2/2.png")
            self.assertEqual(r["Cache-Control"], "no-store")           # 잘라 두지 않았다 — 안내 타일
            (Path(d) / "tiles-tid").mkdir()
            r = self.client.get("/GSM/ibcso/tid/3/2/2.png")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/GSM/ibcso/tid/7/0/0.png").status_code, 404)

    def test_남극_점묶음에_수심을_붙이고_되살리면_뗀다(self):
        from viewer.models import Point, PointSet, PointSetDeletion
        tx, ty, _, _ = tile_of_point(*ROSS)
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            ones = Image.new("F", (256, 256), 1.0)
            write_dem_tile(d, "ice", 6, tx, ty, Image.new("F", (256, 256), 42.0), ones)
            write_dem_tile(d, "bed", 6, tx, ty, Image.new("F", (256, 256), -623.0), ones)
            ps = PointSet.objects.create(name="로스")
            Point.objects.create(pointset=ps, lat=ROSS[0], lon=ROSS[1], label="J9")
            Point.objects.create(pointset=ps, lat=37.5, lon=127.0, label="서울")
            feats = self.client.get(f"/GSM/pointsets/{ps.id}/geojson/").json()["features"]
            self.assertEqual(feats[0]["properties"]["해저·빙저(IBCSO)"], -623)
            self.assertEqual(feats[0]["properties"]["얼음 두께(IBCSO)"], 665)
            self.assertNotIn("해저·빙저(IBCSO)", feats[1]["properties"])
            self.client.post(f"/GSM/pointsets/{ps.id}/delete/")
            gone = PointSetDeletion.objects.get()
            self.client.post(f"/GSM/pointsets/deleted/{gone.id}/restore/")
            back = PointSet.objects.get(name="로스")
            self.assertEqual(back.points.get(label="J9").props, {})
