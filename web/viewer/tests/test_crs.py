"""평면 좌표계 — TM·UTM·옛 Bessel 중부원점.

기준값은 2026-09-27 에 pyproj(PROJ 9)로 뽑아 박아 두었다. 운영 이미지에는
pyproj 가 없다 — 없어도 되게 `crs.py` 를 짰고, 이 값으로 그것을 지킨다.
GRS80 좌표계는 1 cm 안쪽, Bessel(옛 측지계)은 PROJ 가 고르는 옮기기 식과
달라 8 cm 남짓 어긋난다 — 1 m 안쪽이면 받는다.
"""
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from viewer import crs, pointsets

REFERENCE = [
    ("5186", 36.3776, 127.3623, 232509.934, 420005.056),  # 대전 지질박물관
    ("5186", 33.4996, 126.5312, 156437.520, 100758.481),  # 제주
    ("5186", 37.48, 130.9, 545020.894, 549435.754),       # 울릉도
    ("5179", 36.3776, 127.3623, 987648.856, 1820024.919),
    ("5179", 33.4996, 126.5312, 910010.546, 1501279.789),
    ("5179", 37.48, 130.9, 1300652.575, 1947739.115),
    ("32652", 36.3776, 127.3623, 353098.858, 4027076.529),
    ("32652", 37.48, 130.9, 667993.991, 4149817.747),
    ("5187", 36.3776, 127.3623, 53040.074, 421189.985),
    ("5187", 33.4996, 126.5312, -29436.192, 103389.361),
    ("5174", 36.3776, 127.3623, 232438.481, 319698.329),
    ("5174", 33.4996, 126.5312, 156361.102, 450.982),
    ("5174", 37.48, 130.9, 544953.694, 449124.473),
]


class Projection(SimpleTestCase):
    def tolerance(self, code):
        return 1.0 if crs.SYSTEMS[code][7] else 0.01          # m

    def test_위경도에서_평면으로(self):
        for code, lat, lon, e, n in REFERENCE:
            got_e, got_n = crs.from_latlon(code, lat, lon)
            self.assertAlmostEqual(got_e, e, delta=self.tolerance(code), msg=code)
            self.assertAlmostEqual(got_n, n, delta=self.tolerance(code), msg=code)

    def test_평면에서_위경도로(self):
        for code, lat, lon, e, n in REFERENCE:
            got_lat, got_lon = crs.to_latlon(code, e, n)
            deg = self.tolerance(code) / 111000
            self.assertAlmostEqual(got_lat, lat, delta=deg, msg=code)
            self.assertAlmostEqual(got_lon, lon, delta=deg * 1.3, msg=code)

    def test_왕복은_제자리로(self):
        """GRS80 은 1 mm 안쪽. 옛 측지계는 헬머트 역변환을 부호만 뒤집어 근사하므로
        1 cm 안쪽이다 — 옛 자료 자체의 정밀도보다 훨씬 작다."""
        for code in crs.SYSTEMS:
            e, n = crs.from_latlon(code, 36.5, 127.8)
            lat, lon = crs.to_latlon(code, e, n)
            places = 6 if crs.SYSTEMS[code][7] else 8
            self.assertAlmostEqual(lat, 36.5, places=places, msg=code)
            self.assertAlmostEqual(lon, 127.8, places=places, msg=code)


class Resolve(SimpleTestCase):
    def test_수_둘을_꺼낸다(self):
        self.assertEqual(crs.two_numbers("232509.9 420005.1"), (232509.9, 420005.1))
        self.assertEqual(crs.two_numbers("232,509.9, 420,005.1"), (232509.9, 420005.1))
        self.assertIsNone(crs.two_numbers("232509"))

    def test_적힌_차례가_맞으면_그대로(self):
        lat, lon, swapped = crs.resolve("5186", 232509.934, 420005.056)
        self.assertFalse(swapped)
        self.assertAlmostEqual(lat, 36.3776, places=5)

    def test_측량_관례로_적혀도_읽는다(self):
        """측량은 X 가 북쪽이다. 뒤집어서 한반도 안이면 그쪽으로 읽는다."""
        lat, lon, swapped = crs.resolve("5179", 1820024.919, 987648.856)
        self.assertTrue(swapped)
        self.assertAlmostEqual(lon, 127.3623, places=5)

    def test_어느_쪽도_한반도_밖이면_None(self):
        self.assertIsNone(crs.resolve("5186", 9e6, 9e6))


class Views(SimpleTestCase):
    def test_좌표_칸이_TM_을_받는다(self):
        """적은 차례(동 북)가 목록의 첫째다."""
        got = self.client.get("/GSM/coords/parse/", {"q": "232509.9 420005.1", "crs": "5186"}).json()
        first = got["candidates"][0]
        self.assertEqual(first["order"], "en")
        self.assertAlmostEqual(first["lat"], 36.3776, places=4)

    def test_한쪽만_말이_되면_곧장_간다(self):
        # UTM-K 는 동·북의 자릿수가 달라 뒤바꾸면 한반도 밖이다
        got = self.client.get("/GSM/coords/parse/", {"q": "987648.856 1820024.919", "crs": "5179"}).json()
        self.assertAlmostEqual(got["lat"], 36.3776, places=4)
        self.assertFalse(got["swapped"])

    def test_두_차례가_다_말이_되면_둘을_준다(self):
        got = self.client.get("/GSM/coords/parse/", {"q": "420005.056 232509.934", "crs": "5186"}).json()
        self.assertEqual(sorted(c["order"] for c in got["candidates"]), ["en", "ne"])
        ne = next(c for c in got["candidates"] if c["order"] == "ne")
        self.assertAlmostEqual(ne["lat"], 36.3776, places=4)

    def test_이름을_붙이면_곧장_간다(self):
        for q in ("N 420005.056 E 232509.934", "동=232509.934, 북=420005.056"):
            got = self.client.get("/GSM/coords/parse/", {"q": q, "crs": "5186"}).json()
            self.assertAlmostEqual(got["lat"], 36.3776, places=4, msg=q)

    def test_좌표계를_안_고르면_예전_그대로(self):
        got = self.client.get("/GSM/coords/parse/", {"q": "36.3776, 127.3623"}).json()
        self.assertAlmostEqual(got["lon"], 127.3623)

    def test_엉뚱한_TM_은_까닭을_말한다(self):
        response = self.client.get("/GSM/coords/parse/", {"q": "9000000 9000000", "crs": "5186"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("중부원점", response.json()["error"])

    def test_팝업용_평면_좌표(self):
        got = self.client.get("/GSM/coords/project/",
                              {"crs": "5186", "lat": "36.3776", "lon": "127.3623"}).json()
        self.assertAlmostEqual(got["east"], 232509.93, delta=0.02)
        self.assertAlmostEqual(got["north"], 420005.06, delta=0.02)


class Upload(TestCase):
    def post(self, name, body, code):
        return self.client.post("/GSM/pointsets/upload/", {
            "file": SimpleUploadedFile(name, body.encode("utf-8")), "crs": code}).json()

    def test_TM_으로_찍힌_표(self):
        got = self.post("a.csv", "시료,x,y\n박물관,232509.934,420005.056\n", "5186")
        self.assertEqual(got["pointset"]["count"], 1)
        from viewer.models import Point
        p = Point.objects.get()
        self.assertAlmostEqual(p.lat, 36.3776, places=5)
        self.assertEqual(p.label, "박물관")
        self.assertIn("중부원점 (GRS80) 동", p.props)      # 원래 좌표도 남긴다

    def test_측량_관례_X좌표는_북쪽(self):
        got = self.post("a.csv", "X좌표,Y좌표\n420005.056,232509.934\n", "5186")
        self.assertEqual(got["pointset"]["count"], 1)
        from viewer.models import Point
        self.assertAlmostEqual(Point.objects.get().lat, 36.3776, places=5)
        self.assertTrue(got["notes"][0].startswith("'X좌표' 를 북쪽"))

    def test_그냥_x_y_는_GIS_관례이고_그렇게_읽었다고_말한다(self):
        got = self.post("a.csv", "x,y\n232509.934,420005.056\n", "5186")
        self.assertEqual(got["pointset"]["count"], 1)
        self.assertTrue(got["notes"][0].startswith("'x' 를 동쪽"))

    def test_이름이_동_북이면_그대로(self):
        got = self.post("a.csv", "northing,easting\n420005.056,232509.934\n", "5186")
        from viewer.models import Point
        self.assertAlmostEqual(Point.objects.get().lon, 127.3623, places=5)
        self.assertEqual(got["notes"], [])

    def test_TM_인데_위경도로_올리면_일러준다(self):
        got = self.post("a.csv", "lat,lon\n420005.056,232509.934\n", "4326")
        self.assertIn("좌표계를 고른다", got["error"])

    def test_GeoJSON_이_밝힌_좌표계가_이긴다(self):
        body = json.dumps({"type": "FeatureCollection",
                           "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::5186"}},
                           "features": [{"type": "Feature", "properties": {},
                                         "geometry": {"type": "Point", "coordinates": [232509.934, 420005.056]}}]})
        items, _ = pointsets.parse("a.geojson", body.encode(), crs_code="4326")
        self.assertAlmostEqual(items[0]["lat"], 36.3776, places=5)

    def test_영어판에서는_좌표계_이름도_영어로(self):
        self.client.cookies["gsm_lang"] = "en"
        response = self.client.get("/GSM/coords/parse/", {"q": "9000000 9000000", "crs": "5186"})
        self.assertIn("Korea Central Belt", response.json()["error"])
