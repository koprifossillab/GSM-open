"""NASA Moon Trek — 달의 문 (devlog 036, P05).

Trek 을 실제로 부르지 않는다. 응답의 꼴은 2026-09-29 에 받아 본 그대로다 — `identify` 는
열 이름을 `FIRST_Unit`·`FIRST_Un_1` 처럼 잘라 주고, 표고 `exportImage` 는 F32 TIFF 다.
"""
import io
import math
import json
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import i18n, trek, views

#: identify 가 준 앞면의 바다 한 조각 (2026-09-29, 줄였다)
MARE = {"FID": "6735", "Shape": "Polygon", "FIRST_Unit": "Im2", "FIRST_Un_1": "Imbrian",
        "FIRST_Un_2": "Upper Mare Unit", "UnitDescri": "Forms flat, smooth surfaces.",
        "Interpreta": "Basaltic lava flows", "Shape_Area": "3626548556360"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content,
                     url="https://trek.nasa.gov/moon/…", json=lambda: body)


def tiff(values, size=trek.DEM_SIZE):
    image = Image.new("F", (size, size))
    image.putdata(values)
    out = io.BytesIO()
    image.save(out, "TIFF")
    return out.getvalue()


class Grid(SimpleTestCase):
    """경위도 격자 — 줌 0 이 가로 2 장·세로 1 장이고 y 는 북쪽부터."""

    def test_줌_0_의_두_장(self):
        self.assertEqual(trek.tile_bbox(0, 0, 0), (-180.0, -90.0, 0.0, 90.0))
        self.assertEqual(trek.tile_bbox(0, 1, 0), (0.0, -90.0, 180.0, 90.0))

    def test_y_는_북쪽부터_센다(self):
        w, s, e, n = trek.tile_bbox(2, 4, 3)
        self.assertEqual((w, s, e, n), (0.0, -90.0, 45.0, -45.0))

    def test_격자_밖은_없다(self):
        self.assertTrue(trek.valid_tile(0, 1, 0))
        self.assertFalse(trek.valid_tile(0, 2, 0))
        self.assertFalse(trek.valid_tile(0, 0, 1))
        self.assertFalse(trek.valid_tile(trek.MAX_ZOOM + 1, 0, 0))


class Polar(SimpleTestCase):
    """극 격자 (052) — Trek 극 WMTS 의 것. 줌 0 이 한 장, 가운데가 극점. 경도 0 은 남극이 위, 북극이 아래."""

    def test_줌_0_은_한_장(self):
        h = trek.POLAR_HALF
        self.assertEqual(trek.polar_tile_bbox(0, 0, 0), (-h, -h, h, h))
        self.assertEqual(trek.polar_tile_bbox(1, 1, 0), (0.0, 0.0, h, h))
        self.assertTrue(trek.polar_valid(1, 1, 1))
        self.assertFalse(trek.polar_valid(0, 1, 0))

    def test_투영을_오가면_제자리(self):
        for pole, lat in (("n", 84.0), ("s", -87.5)):
            for lon in (-170.0, 0.0, 45.0, 179.0):
                x, y = trek.lonlat_to_polar(lon, lat, pole)
                back = trek.polar_to_lonlat(x, y, pole)
                self.assertAlmostEqual(back[0], lon, places=7)
                self.assertAlmostEqual(back[1], lat, places=7)

    def test_경도_0_의_쪽(self):
        self.assertGreater(trek.lonlat_to_polar(0, -80, "s")[1], 0)
        self.assertLess(trek.lonlat_to_polar(0, 80, "n")[1], 0)
        # 극에서 축척 1 — 남위 60° 는 931 km 남짓(Trek 극지 판의 범위)
        self.assertAlmostEqual(trek.lonlat_to_polar(90, -60, "s")[0], 931066, delta=10)

    def test_극지_판에_제_투영으로_묻는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(trek.get_polar_tile("units", "s", 1, 1, 0), b"png")
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/Unified_Global_Geologic_Map_of_the_Moon_Geologic_Units_SP/MapServer/export"))
        self.assertNotIn("bboxSR", params)
        self.assertEqual(params["bbox"], f"0.0,0.0,{trek.POLAR_HALF},{trek.POLAR_HALF}")
        with self.assertRaises(trek.TrekError):
            trek.get_polar_tile("units", "x", 0, 0, 0)


class Upstream(SimpleTestCase):

    def test_지질도는_달_경위도로_묻는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(trek.get_tile("units", 1, 2, 0), b"png")
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/Unified_Global_Geologic_Map_of_the_Moon_Geologic_Units/MapServer/export"))
        self.assertEqual((params["bboxSR"], params["imageSR"]), (104903, 104903))
        self.assertEqual(params["bbox"], "0.0,0.0,90.0,90.0")

    def test_그림이_아니면_오류(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"error": {"message": "x"}})):
            with self.assertRaises(trek.TrekError):
                trek.get_tile("units", 0, 0, 0)

    def test_모르는_레이어는_묻지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get, self.assertRaises(trek.TrekError):
            trek.get_tile("craters", 0, 0, 0)
        get.assert_not_called()

    def test_속성은_단위_시대_이름_설명_해석(self):
        body = {"results": [{"layerId": 0, "attributes": MARE}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(body)):
            hit = trek.identify(-15, 20)
        self.assertEqual(hit["unit"], "Im2")
        self.assertEqual([label for label, _ in hit["rows"]], ["단위", "시대", "이름", "설명", "해석"])
        self.assertEqual(hit["rows"][1][1], "Imbrian")

    def test_빈_자리는_None(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"results": []})):
            self.assertIsNone(trek.identify(0, 0))

    def test_ArcGIS_의_200_오류(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"error": {"message": "bad"}})):
            with self.assertRaises(trek.TrekError):
                trek.identify(0, 0)


class Dem(SimpleTestCase):

    def test_가장자리가_이웃과_겹치게_반_칸_넓혀_묻는다(self):
        raw = tiff([-1914.5] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            png = trek.dem_tile(0, 0, 0)
        w, s, e, n = (float(v) for v in get.call_args[1]["params"]["bbox"].split(","))
        half = 180 / 64 / 2
        self.assertAlmostEqual(w, -180 - half)
        self.assertAlmostEqual(n, 90 + half)
        image = Image.open(io.BytesIO(png)).convert("RGB")
        self.assertEqual(image.size, (trek.DEM_SIZE, trek.DEM_SIZE))
        r, g, b = image.getpixel((10, 10))
        self.assertAlmostEqual(r * 256 + g + b / 256 - 32768, -1914.5, places=1)

    def test_자료_밖은_0_m(self):
        raw = tiff([-3.4e38] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)):
            png = trek.dem_tile(0, 0, 0)
        r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel((0, 0))
        self.assertEqual(r * 256 + g + b / 256 - 32768, 0)


class FineDem(TestCase):
    """가까이서 쓰는 고운 표고 판 — 극 5 m·NAC (wetherilli 107)."""

    @staticmethod
    def tile(z, lon, lat):
        step = 180 / 2 ** z
        return z, int((lon + 180) // step), int((90 - lat) // step)

    @staticmethod
    def height(png, px=(10, 10)):
        r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel(px)
        return r * 256 + g + b / 256 - 32768

    def test_고운_판_고르기(self):
        self.assertIsNone(trek.dem_part(*self.tile(9, -11.3, -43.0)))            # 온 달 판의 줌
        self.assertEqual(trek.dem_part(*self.tile(15, -11.3, -43.0))[0], "LRO_NAC_DEM_43S349E_150cmp")
        self.assertIsNone(trek.dem_part(*self.tile(12, 0, 0)))                   # 고운 판이 없는 자리
        self.assertEqual(trek.dem_part(*self.tile(11, 0, -89.5))[0], "LRO_LOLA_DEM_SPole875_5mp_v04_EQ")
        self.assertEqual(trek.dem_part(*self.tile(10, 45, -80))[0], "LRO_LOLA_DEM_SPole75_30mp_v04_EQ")
        self.assertIsNone(trek.dem_part(*self.tile(12, 0, -89.5)))               # 5 m 판의 줌 끝 너머

    def test_극_5_m_는_반_m_단위(self):
        raw = tiff([-1443.0] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            png = trek.dem_tile(*self.tile(11, 0, -89.5))
        self.assertIn("LRO_LOLA_DEM_SPole875_5mp_v04_EQ", get.call_args[0][0])
        self.assertAlmostEqual(self.height(png), -721.5, places=1)

    def test_빈_칸은_온_달_판으로_메운다(self):
        empty = response(ctype="image/tiff", content=tiff([-3.4e38] * trek.DEM_SIZE ** 2))
        base = response(ctype="image/tiff", content=tiff([-3000.0] * trek.DEM_SIZE ** 2))
        with mock.patch("viewer.trek.requests.get", side_effect=[empty, base]) as get:
            png = trek.dem_tile(*self.tile(13, -11.64, -43.65))
        self.assertIn("LRO_NAC_DEM_43S349E", get.call_args_list[0][0][0])
        self.assertIn(trek.DEM_SERVICE, get.call_args_list[1][0][0])
        self.assertAlmostEqual(self.height(png), -3000.0, places=1)

    def test_줌_0_은_128_ppd(self):
        """256 ppd 판은 반구 한 장을 받지 않는다 — 0.21.0 부터 운영의 줌 0 이 502 였다."""
        raw = tiff([-1000.0] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            trek.dem_tile(0, 0, 0)
            trek.dem_tile(1, 0, 0)
        self.assertIn(trek.DEM_Z0_SERVICE, get.call_args_list[0][0][0])
        self.assertIn(trek.DEM_SERVICE, get.call_args_list[1][0][0])

    def test_화면이_받는_것(self):
        z, x, y = self.tile(12, 0, 0)
        with mock.patch("viewer.trek.requests.get") as get:
            self.assertEqual(self.client.get(reverse("viewer:moon-dem", args=[z, x, y])).status_code, 404)
        get.assert_not_called()
        html = self.client.get(reverse("viewer:moon")).content.decode()
        self.assertIn('id="dem-parts"', html)
        self.assertIn("-87.55", html)


class Places(SimpleTestCase):
    PLACES = [["Apollo", "Crater", -151.8, -36.1], ["Apollo 11", "Landing site", 23.48, 0.67],
              ["Tycho", "Crater", -11.36, -43.31], ["Tycho A", "Satellite Feature", -12.13, -39.94],
              ["Mare Tranquillitatis", "Mare", 31.4, 8.35]]

    def test_앞이_맞는_것이_먼저_착륙지가_맨_앞(self):
        got = trek.search_places(self.PLACES, "apollo")
        self.assertEqual([p["name"] for p in got], ["Apollo 11", "Apollo"])

    def test_들어_있는_것도_찾는다(self):
        self.assertEqual(trek.search_places(self.PLACES, "tranq")[0]["name"], "Mare Tranquillitatis")

    def test_빈_검색은_빈_답(self):
        self.assertEqual(trek.search_places(self.PLACES, "  "), [])

    def test_색인에서_지명과_착륙지를_추린다(self):
        docs = [
            {"itemType": "nomenclature", "title": "Tycho", "productType": "Crater, craters",
             "bbox": "-11.36,-43.31,-11.36,-43.31"},
            {"itemType": "nomenclature", "title": "Lacus Mortis", "productType": "Lacus, lac?à?½s",
             "bbox": "27.3,45,27.3,45"},
            {"itemType": "bookmark", "title": "Apollo 11", "bbox": "23.46,0.66,23.49,0.67"},
            {"itemType": "product", "title": "LRO WAC", "bbox": "-180,-90,180,90"},
            {"itemType": "nomenclature", "title": "Far", "productType": "Crater", "bbox": "200,10,200,10"},
        ]
        with mock.patch("viewer.trek.requests.get", return_value=response({"response": {"docs": docs}})):
            got = trek.fetch_places()
        self.assertEqual([p[0] for p in got], ["Apollo 11", "Far", "Lacus Mortis", "Tycho"])
        self.assertEqual(dict((p[0], p[1]) for p in got)["Lacus Mortis"], "Lacus")   # 깨진 복수는 버린다
        self.assertEqual(dict((p[0], p[2]) for p in got)["Far"], -160.0)             # 0–360 → −180–180


class MoonViews(TestCase):

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-trek-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_지질도_타일은_캐시에_담고_다시_묻지_않는다(self):
        url = reverse("viewer:moon-tile", args=["units", 1, 2, 0])
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            first = self.client.get(url)
            second = self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], second["X-GSM-Cache"]), ("miss", "hit"))
        self.assertEqual(get.call_count, 1)

    def test_격자_밖_타일은_404(self):
        self.assertEqual(self.client.get(reverse("viewer:moon-tile", args=["units", 0, 5, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:moon-tile", args=["nope", 0, 0, 0])).status_code, 404)

    def test_표고를_못_받으면_502(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(status=500, ctype="text/html", content=b"")):
            self.assertEqual(self.client.get(reverse("viewer:moon-dem", args=[0, 0, 0])).status_code, 502)

    def test_한국어판은_시대를_옮긴다(self):
        body = {"results": [{"attributes": MARE}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(body)):
            ko = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20}).json()
            self.client.cookies[i18n.COOKIE] = "en"
            en = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20}).json()
        self.assertIn(["시대", "임브리움기"], ko["rows"])
        self.assertIn(["Age", "Imbrian"], en["rows"])
        self.assertIn(["Name", "Upper Mare Unit"], en["rows"])       # 값은 옮기지 않는다

    def test_좌표가_없으면_400(self):
        self.assertEqual(self.client.get(reverse("viewer:moon-info"), {"lon": "x"}).status_code, 400)

    def test_지명_찾기는_저장소의_파일을_뒤진다(self):
        views._moon_places.cache_clear()
        self.addCleanup(views._moon_places.cache_clear)
        got = self.client.get(reverse("viewer:moon-places"), {"q": "apollo 11"}).json()["results"]
        self.assertEqual(got[0]["name"], "Apollo 11")
        self.assertEqual(got[0]["kind"], "Landing site")


class Legend(SimpleTestCase):
    """범례 49 칸 — 기호의 머리글자로 시대를 붙인다 (038)."""

    def test_기호와_시대(self):
        self.assertEqual(trek._unit_of("Copernican Crater, Secondary (Csc)"), "Csc")
        self.assertEqual(trek.age_of_unit("Csc"), "Copernican")
        self.assertEqual(trek.age_of_unit("EIp"), "Eratosthenian")     # 둘에 걸친 것은 앞 글자
        self.assertEqual(trek.age_of_unit("pNbm"), "Pre-Nectarian")
        self.assertEqual(trek.age_of_unit(""), "")

    def test_한국어판은_시대_머리를_옮긴다(self):
        body = {"layers": [{"legend": [
            {"label": "Imbrian Mare, Upper (Im2)", "imageData": "AAAA", "contentType": "image/png"},
            {"label": "pre-Nectarian Crater (pNc)", "imageData": "BBBB", "contentType": "image/png"}]}]}
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-trek-")), \
                mock.patch("viewer.trek.requests.get", return_value=response(body)):
            from django.test import Client
            items = Client().get(reverse("viewer:moon-legend")).json()["items"]
        self.assertEqual([(i["unit"], i["age"]) for i in items], [("Im2", "임브리움기"), ("pNc", "선넥타리스기")])
        self.assertTrue(items[0]["image"].startswith("data:image/png;base64,"))


class Landings(TestCase):
    """착륙·충돌 지점 (046) — 갈래마다 레이어 하나. 쪽 나누기 없이 통째로 받는다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-landings-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def fake(self, url, params=None, **kw):
        layer = int(url.rstrip("/").split("/")[-2])
        rows = {
            0: [{"geometry": {"x": 0.0, "y": 30.0}, "attributes": {"Spacecraft": "Luna 2", "Date": "   14 September 1959   ",
                                                              "Link": "https://nssdc…1959-014A"}}],
            2: [{"geometry": {"x": 23.47314, "y": 0.67416}, "attributes": {"Spacecraft": "Apollo 11 LM descent stage",
                                                                        "Date": "20 July 1969", "Link": ""}},
                {"geometry": {}, "attributes": {"Spacecraft": "좌표 없음"}}],
        }.get(layer, [])
        self.assertNotIn("resultRecordCount", params)             # 이 서버는 쪽 나누기를 받지 않는다
        return response({"features": rows})

    def test_갈래를_열쇠로_붙여_모은다(self):
        with mock.patch("viewer.trek.requests.get", side_effect=self.fake):
            sites = trek.landing_sites()
        self.assertEqual([(s["name"], s["kind"]) for s in sites],
                         [("Luna 2", "impact"), ("Apollo 11 LM descent stage", "crewed")])
        self.assertEqual(sites[0]["date"], "14 September 1959")

    def test_경로는_GeoJSON_이고_캐시에_담는다(self):
        with mock.patch("viewer.trek.requests.get", side_effect=self.fake) as get:
            first = self.client.get(reverse("viewer:moon-landings")).json()
            self.client.get(reverse("viewer:moon-landings"))
        self.assertEqual(get.call_count, 4)                          # 네 갈래를 한 번씩, 두 번째는 캐시
        self.assertEqual(first["features"][1]["geometry"]["coordinates"], [23.47314, 0.67416])
        self.assertEqual(first["features"][1]["properties"]["kind"], "crewed")

    def test_EVA_동선은_저장소의_씨앗(self):
        views._moon_eva.cache_clear()
        data = self.client.get(reverse("viewer:moon-eva")).json()
        missions = {f["properties"]["mission"] for f in data["features"]}
        self.assertEqual(missions, {"Apollo 11", "Apollo 12", "Apollo 14", "Apollo 15", "Apollo 16", "Apollo 17"})
        self.assertIn("Esri UK", data["source"])


class Profile(TestCase):
    """잰 선을 따라 높이 그래프 (wetherilli 100). Trek 은 부르지 않는다 — `lola_values` 를 바꿔 끼운다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-profile-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_대원을_따라_고르게_꼭짓점은_꼭(self):
        pts = trek.profile_points([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)], 21)
        self.assertEqual((pts[0][0], pts[0][1], pts[0][2]), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(pts[-1][0], 1.0, places=6)
        self.assertAlmostEqual(pts[-1][1], 1.0, places=6)
        one = trek.RADIUS * math.radians(1)                       # 적도의 1° 는 30.3 km
        self.assertAlmostEqual(pts[-1][2], 2 * one, delta=1)
        self.assertTrue(any(abs(p[0] - 1.0) < 1e-9 and abs(p[1]) < 1e-9 for p in pts))   # 꺾인 곳
        gaps = [b[2] - a[2] for a, b in zip(pts, pts[1:])]
        self.assertLess(max(gaps) - min(gaps), 1)                  # 고르게

    def test_날짜변경선을_건너도_짧은_길로(self):
        pts = trek.profile_points([(179.5, 0.0), (180.5, 0.0)], 5)
        self.assertAlmostEqual(pts[-1][2], trek.RADIUS * math.radians(1), delta=1)
        self.assertTrue(all(abs(abs(p[0]) - 180) <= 0.5 + 1e-9 for p in pts))

    def test_화면이_받는_것(self):
        with mock.patch("viewer.trek.lola_values", side_effect=lambda pts: {i: -1000.0 + i for i in pts if i != 3}) as get:
            r = self.client.get(reverse("viewer:moon-profile"), {"line": "-11.36,-43.31;-11.0,-43.4", "n": "10"})
            self.client.get(reverse("viewer:moon-profile"), {"line": "-11.36,-43.31;-11.0,-43.4", "n": "10"})
        self.assertEqual(get.call_count, 1)                        # 같은 선은 캐시가 낸다
        d = r.json()
        self.assertEqual(len(d["dist"]), len(d["elev"]))
        self.assertIsNone(d["elev"][3])                            # 못 읽은 점은 null
        self.assertEqual(d["elev"][0], -1000.0)
        self.assertEqual(d["source"], trek.ELEV_SOURCE)

    def test_선이_아니면_400(self):
        for line in ("", "1,2", "a,b;c,d", "0,95;1,1"):
            self.assertEqual(self.client.get(reverse("viewer:moon-profile"), {"line": line}).status_code, 400)

    def test_상류가_안_주면_502(self):
        with mock.patch("viewer.trek.lola_values", side_effect=trek.TrekError("x")):
            r = self.client.get(reverse("viewer:moon-profile"), {"line": "0,0;1,1"})
        self.assertEqual(r.status_code, 502)


class Values(TestCase):
    """누른 자리의 광물·원소·지각 두께 값 (wetherilli 103). Trek 은 부르지 않는다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-values-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def samples(self, value):
        body = {"samples": [{"locationId": 0, "value": value}]}
        return mock.Mock(status_code=200, url="…", headers={"content-type": "application/json"},
                         content=json.dumps(body).encode(), json=lambda: body)

    def test_판_이름에서_갈래(self):
        self.assertEqual(trek.value_key("moon", "Lunar_Kaguya_MIMap_MineralDeconv_FeOWeightPercent_50N50S_colorized"), "feo")
        self.assertEqual(trek.value_key("moon", "LP_GRS_Th_Clr_Global_2ppd"), "th")
        self.assertEqual(trek.value_key("moon", "LP_GRS_ClrTitaniumAbundance_2ppd"), "ti")
        self.assertEqual(trek.value_key("moon", "Model3_thick.eq"), "thick3")
        self.assertEqual(trek.value_key("moon", "Model3_cmi.eq"), "cmi3")              # wetherilli 236 부터 읽는다
        self.assertEqual(trek.value_key("mars", "LP_GRS_Th_Clr_Global_2ppd"), "")

    def test_비율은_백분율로(self):
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("0.152402669")) as get:
            got = trek.value_at("olivine", -15.6, 33.0)
        self.assertEqual(got["rows"][0], ["감람석", "15.2 wt%"])
        self.assertIn("Lunar_Kaguya_MIMap_MineralDeconv_OlivinePercent_50N50S/ImageServer/getSamples",
                      get.call_args[0][0])

    def test_범위_밖은_버린다(self):
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("-3.4e38")):
            self.assertEqual(trek.value_at("th", 0, 0), {"rows": []})

    def test_Kaguya_는_50도_밖을_묻지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get:
            self.assertEqual(trek.value_at("feo", 0, -80), {"rows": []})
        get.assert_not_called()

    def test_화면이_받는_것(self):
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("10.83")) as get:
            url = reverse("viewer:moon-values")
            ko = self.client.get(url, {"lon": "-15.6", "lat": "33", "key": "thick1"}).json()
            en = self.client.get(url, {"lon": "-15.6", "lat": "33", "key": "thick1"}, HTTP_COOKIE="gsm_lang=en").json()
        self.assertEqual(get.call_count, 1)                                     # 캐시
        self.assertEqual(ko["rows"][0], ["지각 두께", "10.8 km"])
        self.assertEqual(en["rows"][0], ["Crustal thickness", "10.8 km"])
        self.assertEqual(self.client.get(url, {"lon": "0", "lat": "0", "key": "nope"}).status_code, 400)


class MoonValuesRest(TestCase):
    """누른 자리의 값 — 남은 판 (wetherilli 236). 꼴은 2026-10-04 에 한 점씩 받은 그대로다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-moon-values-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def samples(self, value):
        body = {"samples": [{"locationId": 0, "value": value}]}
        return mock.Mock(status_code=200, url="…", headers={"content-type": "application/json"},
                         content=json.dumps(body).encode(), json=lambda: body)

    def test_판_이름에서_갈래(self):
        for label, key in (("Lunar_Kaguya_MIMap_MineralDeconv_OpticalMaturityIndex_50N50S", "omat"),
                           ("gggrx_1200a_boug_l660.eq", "grav:boug:660"), ("gggrx_1200a_degstr.eq", "grav:degstr"),
                           ("dgdr_Clrstd_cf_clc_cyl_128_jp2", "cf_std_128"), ("diviner_Clrtbol_max_anom", "tbol_max_anom"),
                           ("LRO_LOLA_ClrShade_Global_256ppd_v06", "moon_elev"), ("minirf_s1_Clr49dnorm_EQ", "minirf_cpr"),
                           ("LRO_NAC_ClrSlope_15m_43S349E_150cmp", "slope:LRO_NAC_Slope_15m_43S349E_150cmp"),
                           ("LRO_NAC_ClrCraterSlopesMasked_1mpp_SiteH", "slope:LRO_NAC_CraterSlopesMasked_1mpp_SiteH"),
                           ("diviner_Clrc3_c7_hour_10_14", "")):                 # 뜻을 모르는 판은 두었다
            self.assertEqual(trek.value_key("moon", label), key, label)

    def test_판이_여럿인_갈래는_열쇠에서_짓는다(self):
        self.assertEqual(trek.value_spec("grav:geoid:660")[1:4], ("gggrx_1200a_geoid_l660_eq", "지오이드 높이", "m"))
        self.assertEqual(trek.value_spec("slope:LRO_NAC_Slope_2_5mpp_Shioli")[0], "trekarcgis3")
        self.assertEqual(trek.value_spec("slope:LRO_NAC_Slope_15m_43S349E_150cmp")[0], "trekarcgis2")
        self.assertIsNone(trek.value_spec("grav:boug:x"))
        self.assertIsNone(trek.value_spec("slope:../etc"))

    def test_중력은_mGal_차수는_출처에(self):
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("171.3")) as get:
            got = trek.value_at("grav:boug:660", 20, 10)
        self.assertEqual(got["rows"], [["부게 중력 교란", "171.3 mGal"], ["출처", "GRAIL GRGM1200A · L660"]])
        self.assertIn("trekarcgis2/rest/services/gggrx_1200a_boug_l660_eq/ImageServer/getSamples", get.call_args[0][0])

    def test_한_자리만_덮는_판의_밖은_빈_값(self):
        error = {"error": {"code": 400, "message": "Invalid or missing input parameters."}}
        answer = mock.Mock(status_code=200, url="…", headers={"content-type": "application/json"},
                           content=json.dumps(error).encode(), json=lambda: error)
        with mock.patch("viewer.trek.requests.get", return_value=answer):
            self.assertEqual(trek.value_at("slope:LRO_NAC_Slope_15m_43S349E_150cmp", 10, -43), {"rows": []})
            with self.assertRaises(trek.TrekError):                              # 온 달 판의 오류는 오류다
                trek.value_at("tbol_max", 10, 10)

    def test_화면이_판이_여럿인_갈래를_묻는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("10.8")):
            got = self.client.get(reverse("viewer:moon-values"),
                                  {"lon": "-11.28", "lat": "-43", "key": "slope:LRO_NAC_Slope_15m_43S349E_150cmp"},
                                  HTTP_COOKIE="gsm_lang=en").json()
        self.assertEqual(got["rows"][0], ["Slope", "10.8 °"])


class MoonTrekMore(SimpleTestCase):
    """색인 밖의 판·남은 고운 지형 (wetherilli 150)."""

    def samples(self, value):
        body = {"samples": [{"locationId": 0, "value": value}]}
        return mock.Mock(status_code=200, url="…", headers={"content-type": "application/json"},
                         content=json.dumps(body).encode(), json=lambda: body)

    def test_KGRS_는_단위_없이_상대값(self):
        self.assertEqual(trek.value_key("moon", "KPLO_KGRS_Potassium_2ppd"), "kgrs_k")
        self.assertEqual(trek.value_key("moon", "KGRS_Th_LG_smooth"), "kgrs_th")
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("2.595001459")) as get:
            got = trek.value_at("kgrs_k", -15.6, 33.0)
        self.assertEqual(got["rows"][0], ["칼륨 상대값 (단위 미확인)", "2.60"])
        self.assertIn("trekarcgis3/rest/services/KPLO_KGRS_Potassium_2ppd/ImageServer/getSamples", get.call_args[0][0])

    def test_북극_판은_그_위도_밑을_묻지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get:
            self.assertEqual(trek.value_at("ice_today", 0, 60), {"rows": []})
            self.assertEqual(trek.value_at("np_feo", 0, -88), {"rows": []})
        get.assert_not_called()
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("1.186290026")):
            self.assertEqual(trek.value_at("ice_today", 90, 85)["rows"][0], ["얼음이 버틸 깊이 — 오늘의 자전축", "1.19 m"])
        with mock.patch("viewer.trek.requests.get", return_value=self.samples("-1")):     # 버틸 깊이가 없다
            self.assertEqual(trek.value_at("ice_paleo", 90, 85), {"rows": []})

    def test_색인_밖의_판이_목록에_든다(self):
        docs = [{"itemType": "product", "productLabel": "LP_GRS_Th_Global_2ppd", "title": "LP GRS Th"}]
        with mock.patch("viewer.trek.requests.get", return_value=response({"response": {"docs": docs}})):
            items = trek.catalog_items("moon")
        ids = [i["id"] for i in items]
        self.assertIn("KPLO_KGRS_Uranium_2ppd", ids)
        self.assertIn("np_ice_depth_new_240m_mat_today_27_Oct_2016", ids)
        self.assertNotIn("image", items[-1])
        with mock.patch("viewer.trek.requests.get") as get:
            path = trek.find_mapserver("moon", "", "np_feo_mlemelin_031417")
        get.assert_not_called()
        self.assertEqual(path, "trekarcgis/rest/services/np_feo_mlemelin_031417/ImageServer")

    def test_ImageServer_판은_exportImage(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            trek.map_tile("moon", "trekarcgis/rest/services/np_feo_mlemelin_031417/ImageServer", 3, 1, 0)
            trek.map_tile("moon", "trekarcgis3/rest/services/X/MapServer", 3, 1, 0)
        self.assertTrue(get.call_args_list[0][0][0].endswith("/ImageServer/exportImage"))
        self.assertTrue(get.call_args_list[1][0][0].endswith("/MapServer/export"))

    def test_남은_NAC_셋은_가까이서만(self):
        # 02N085E 한가운데 줌 12 — 그 판이다. 줌 9 는 늘 온 달 판
        x, y = int((85.25 + 180) / (180 / 2 ** 12)), int((90 - 2.1) / (180 / 2 ** 12))
        self.assertEqual(trek.dem_part(12, x, y)[0], "LRO_NAC_DEM_02N085E_150cmp")
        self.assertIsNone(trek.dem_part(9, x >> 3, y >> 3))
        names = [p[0] for p in trek.DEM_PARTS]
        self.assertIn("LRO_NAC_DEM_86S356E_3mp", names)
        self.assertNotIn("Apollo17_MetricCam_DEM_Global_1024ppd", names)
