"""화성 (devlog 058) — 달 화면을 옮긴 것. 문은 같은 `trek.py` 의 `mars_*` 다.

Trek 을 실제로 부르지 않는다. 응답의 꼴은 2026-09-29 에 Mars Trek 에서 받아 본 그대로다 —
SIM 3292 의 `identify` 는 `Unit`·`UnitDesc` 를 주고, 범례 이름에는 기호가 없다.
"""
import io
import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import marscraters, trek, zhurong
from viewer.models import PointSet, REGIONS
from viewer.tests.test_trek import response, tiff

GALE = {"FID": "774", "Unit": "AHi", "UnitDesc": "Amazonian and Hesperian impact unit", "SphArea_km": "87031.1"}


class Ages(SimpleTestCase):
    """화성의 지질시대 — 이름 앞머리에서 읽고, 둘에 걸친 것은 젊은 쪽으로 묶는다."""

    def test_이름_앞머리가_시대다(self):
        self.assertEqual(trek.mars_age("Early Hesperian basin unit"), "Early Hesperian")
        self.assertEqual(trek.mars_age("Amazonian and Hesperian impact unit"), "Amazonian and Hesperian")
        self.assertEqual(trek.mars_age("Noachian highland undivided unit"), "Noachian")

    def test_범례는_젊은_쪽으로_묶는다(self):
        self.assertEqual(trek.mars_period("Amazonian and Noachian"), "Amazonian")
        self.assertEqual(trek.mars_period("Late Noachian"), "Noachian")

    def test_한국어판(self):
        self.assertEqual(trek.mars_age_ko("Early Hesperian"), "헤스페리아기 전기")
        self.assertEqual(trek.mars_age_ko("Amazonian and Hesperian"), "아마조니스기–헤스페리아기")
        self.assertEqual(trek.mars_age_ko("Middle Noachian"), "노아키스기 중기")


class Upstream(SimpleTestCase):

    def test_지질도는_Mars_Trek_에_화성_경위도로_묻는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(trek.mars_tile(1, 2, 0), b"png")
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.startswith("https://trek.nasa.gov/mars/"))
        self.assertIn("SIM3292_Global_Geology/MapServer/export", url)
        self.assertEqual(params["bboxSR"], 104905)

    def test_속성은_단위_이름_그리고_시대(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"results": [{"attributes": GALE}]})):
            hit = trek.mars_identify(137.4, -4.6)
        self.assertEqual(hit["unit"], "AHi")
        self.assertEqual(hit["age"], "Amazonian and Hesperian")
        self.assertEqual(hit["rows"], [("단위", "AHi"), ("이름", "Amazonian and Hesperian impact unit")])

    def test_범례는_기호를_query_로_붙인다(self):
        legend = {"layers": [{"legend": [
            {"label": "Early Hesperian volcanic unit", "imageData": "AAA", "contentType": "image/png"},
            {"label": "Amazonian polar undivided unit", "imageData": "BBB", "contentType": "image/png"}]}]}
        codes = {"features": [{"attributes": {"Unit": "eHv", "UnitDesc": "Early Hesperian volcanic unit"}}]}
        with mock.patch("viewer.trek.requests.get", side_effect=[response(legend), response(codes)]):
            items = trek.mars_legend()
        self.assertEqual([(i["unit"], i["age"]) for i in items], [("eHv", "Hesperian"), ("", "Amazonian")])

    def test_표고는_화성의_범위만_받는다(self):
        # 올림푸스 몬스(21 km)는 달의 범위(±20 km)를 넘는다 — 화성은 따로 잰다. S16 의 자료 밖은 0 m
        raw = tiff([21000.0] * 10 + [-32768.0] * (trek.DEM_SIZE ** 2 - 10))
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            png = trek.mars_dem_tile(3, 1, 1)
        # 멀리서는 줄인 판이 있는 MOLA 128 ppd — 200 m 판은 넓게 물으면 400 을 준다
        self.assertIn(trek.MARS_DEM_COARSE, get.call_args[0][0])
        from PIL import Image
        import io
        px = Image.open(io.BytesIO(png)).getdata()
        decode = lambda p: p[0] * 256 + p[1] + p[2] / 256 - 32768
        self.assertAlmostEqual(decode(px[0]), 21000, places=0)
        self.assertEqual(decode(px[20]), 0)

    def test_가까이서는_200_m_판(self):
        raw = tiff([100.0] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            trek.mars_dem_tile(trek.MARS_DEM_FINE_ZOOM, 700, 300)
        self.assertIn(trek.MARS_DEM + "/", get.call_args[0][0])

    def test_착륙지는_임무를_붙여_모은다(self):
        page = {"features": [{"geometry": {"x": 137.44, "y": -4.59}, "attributes": {"name": "Bradbury Landing"}}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(page)) as get:
            sites = trek.mars_landings()
        self.assertEqual(get.call_count, len(trek.MARS_WAYPOINTS))
        curiosity = [s for s in sites if s["mission"] == "Curiosity"][0]
        self.assertEqual((curiosity["name"], curiosity["kind"]), ("Bradbury Landing", "rover"))

    def test_지명의_북마크는_착륙지만(self):
        docs = [{"itemType": "nomenclature", "title": "Gale", "productCat2": "Crater, craters",
                 "bbox": "137.8,-5.4,137.8,-5.4"},
                {"itemType": "bookmark", "title": "Curiosity Landing Site", "bbox": "136.8,-5.1,138.1,-4.1"},
                {"itemType": "bookmark", "title": "The Martian Path", "bbox": "-6,7,-5,8"},
                {"itemType": "bookmark", "title": "Viking 1", "bbox": "-48,22,-47,23"}]
        with mock.patch("viewer.trek.requests.get", return_value=response({"response": {"docs": docs}})) as get:
            places = trek.fetch_places("mars")
        self.assertIn("/mars/", get.call_args[0][0])
        self.assertEqual([p[:2] for p in places], [["Curiosity Landing Site", "Landing site"],
                                                   ["Gale", "Crater"], ["Viking 1", "Landing site"]])


class Polar(SimpleTestCase):
    """극 격자 (065) — Trek 화성 극 WMTS 의 것. 구의 반지름은 극 반지름이고, 반폭은 Capabilities 의 1 821 000 이
    아니라 1 809 300 이다(2026-09-30 에 극 타일과 `export` 를 맞대 보았다)."""

    def test_줌_0_은_한_장(self):
        h = trek.MARS_POLAR_HALF
        self.assertEqual(trek.mars_polar_tile_bbox(0, 0, 0), (-h, -h, h, h))
        self.assertEqual(trek.mars_polar_tile_bbox(1, 1, 0), (0.0, 0.0, h, h))

    def test_투영을_오가면_제자리(self):
        for pole, lat in (("n", 84.0), ("s", -87.5)):
            for lon in (-170.0, 0.0, 45.0, 179.0):
                x, y = trek.mars_lonlat_to_polar(lon, lat, pole)
                back = trek.mars_polar_to_lonlat(x, y, pole)
                self.assertAlmostEqual(back[0], lon, places=7)
                self.assertAlmostEqual(back[1], lat, places=7)

    def test_극지_판은_60_도까지(self):
        # 격자의 반폭(±1 809 300 m)이 극 반지름의 구에서 꼭 위도 60° 다 — 반폭과 반지름이 함께 맞다는 뜻
        _, lat = trek.mars_polar_to_lonlat(trek.MARS_POLAR_HALF, 0, "s")
        self.assertAlmostEqual(lat, -60.0, places=6)
        self.assertGreater(trek.mars_lonlat_to_polar(0, -80, "s")[1], 0)
        self.assertLess(trek.mars_lonlat_to_polar(0, 80, "n")[1], 0)

    def test_지질도는_극_평사도법_WKT_로_옮겨_그리게_한다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(trek.mars_polar_tile("s", 1, 1, 0), b"png")
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertIn("SIM3292_Global_Geology/MapServer/export", url)
        sr = json.loads(params["imageSR"])["wkt"]
        self.assertIn("Stereographic_South_Pole", sr)
        self.assertIn("3376200.0", sr)
        self.assertEqual(params["bboxSR"], params["imageSR"])
        self.assertEqual(params["bbox"], f"0.0,0.0,{trek.MARS_POLAR_HALF},{trek.MARS_POLAR_HALF}")
        self.assertIn("Stereographic_North_Pole", trek.MARS_POLAR_WKT["n"])
        with self.assertRaises(trek.TrekError):
            trek.mars_polar_tile("x", 0, 0, 0)


class MarsViews(TestCase):

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mars-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_지질도_타일은_캐시에_담고_다시_묻지_않는다(self):
        url = reverse("viewer:mars-tile", args=["units", 2, 3, 1])
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(self.client.get(url).content, b"png")
            self.assertEqual(self.client.get(url).content, b"png")
        self.assertEqual(get.call_count, 1)

    def test_극_타일도_캐시에_담는다(self):
        url = reverse("viewer:mars-polar-tile", args=["n", "units", 3, 2, 5])
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(self.client.get(url).content, b"png")
            self.assertEqual(self.client.get(url).content, b"png")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(self.client.get(reverse("viewer:mars-polar-tile", args=["s", "units", 0, 1, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:mars-polar-tile", args=["s", "nac", 0, 0, 0])).status_code, 404)

    def test_모르는_레이어와_격자_밖은_404(self):
        self.assertEqual(self.client.get(reverse("viewer:mars-tile", args=["contacts", 1, 0, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:mars-tile", args=["units", 0, 2, 0])).status_code, 404)

    def test_한국어판은_시대를_옮긴다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"results": [{"attributes": GALE}]})):
            data = self.client.get(reverse("viewer:mars-info"), {"lon": 137.4, "lat": -4.6}).json()
        self.assertEqual(data["unit"], "AHi")
        self.assertEqual(data["rows"][1], ["시대", "아마조니스기–헤스페리아기"])

    def test_로버_경로는_GeoJSON(self):
        page = {"features": [{"geometry": {"paths": [[[137.44, -4.59], [137.45, -4.6]]]}}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(page)):
            data = self.client.get(reverse("viewer:mars-traverses")).json()
        # Trek 의 넷에 저장소의 주룽이 붙는다 (066)
        self.assertEqual(len(data["features"]), len(trek.MARS_TRAVERSES) + 1)
        self.assertEqual(data["features"][0]["geometry"]["type"], "MultiLineString")
        self.assertEqual(data["features"][-1]["properties"]["임무"], "Zhurong")

    def test_착륙지에_주룽이_붙는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"features": []})):
            data = self.client.get(reverse("viewer:mars-landings")).json()
        names = [f["properties"]["이름표"] for f in data["features"] if f["properties"]["임무"] == "Zhurong"]
        self.assertEqual(names[0], "Zhurong Landing Site")
        self.assertTrue(names[1].startswith("Zhurong, sol "))

    def test_지명_찾기에_주룽_착륙지(self):
        data = self.client.get(reverse("viewer:mars-places"), {"q": "zhurong"}).json()
        self.assertEqual(data["results"][0]["name"], "Zhurong Landing Site")

    def test_지명_찾기는_저장소의_파일을_뒤진다(self):
        data = self.client.get(reverse("viewer:mars-places"), {"q": "gale"}).json()
        self.assertEqual(data["results"][0]["name"], "Gale")


class MarsView(TestCase):
    """화성 화면 — 달처럼 숨은 차림에서 들어가고, 제 아이콘·대기 화면을 쓴다."""

    def test_화성_화면이_제_스크립트와_아이콘을_싣는다(self):
        html = self.client.get(reverse("viewer:mars")).content.decode()
        self.assertIn('data-region="mars"', html)
        self.assertIn("viewer/mars.js", html)
        self.assertIn("viewer/emblem-mars.png", html)
        self.assertIn("viewer/splash-mars.gif", html)

    def test_온_지구도_제_아이콘과_대기_화면(self):
        # 온 지구 아이콘 (wetherilli 153)
        html = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertIn("viewer/emblem-earth.png", html)
        self.assertIn("viewer/splash-earth.gif", html)
        self.assertNotIn("viewer/emblem.svg", html)

    def test_달_화면도_제_아이콘과_대기_화면(self):
        html = self.client.get(reverse("viewer:moon")).content.decode()
        self.assertIn("viewer/emblem-moon.png", html)
        self.assertIn("viewer/splash-moon.gif", html)
        self.assertNotIn("viewer/emblem.svg", html)

    def test_2D_의_숨은_차림이_화성을_연다(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        menu = re.search(r'<nav class="hidden-menu" id="hidden-menu"[^>]*hidden>(.*?)</nav>', html, re.S)
        self.assertIn('href="/GSM/mars/"', menu.group(1))   # 지도는 map/ 에 산다 (wetherilli 113)

    def test_화성은_지역_탭이_아니다(self):
        self.assertNotIn("mars", dict(REGIONS))


class MarsPointSets(TestCase):
    """점묶음의 몸 — 화성 화면은 화성 것만, 표고는 MOLA–HRSC 로."""

    CSV = "name,lat,lon\nBradbury,-4.5895,137.4417\nJezero,18.4447,77.4508\n"

    def upload(self, **extra):
        return self.client.post(reverse("viewer:pointset-upload"),
                                {"file": SimpleUploadedFile("rovers.csv", self.CSV.encode()), **extra})

    def test_화성에서_올리면_화성_점묶음이고_지구에는_없다(self):
        self.assertEqual(self.upload(body="mars").json()["pointset"]["body"], "mars")
        self.upload()
        self.assertEqual(len(self.client.get(reverse("viewer:pointset-index"), {"body": "mars"}).json()["pointsets"]), 1)
        self.assertEqual(len(self.client.get(reverse("viewer:pointset-index")).json()["pointsets"]), 1)

    def test_표고는_MOLA_HRSC_로(self):
        self.upload(body="mars")
        ps = PointSet.objects.get()
        body = {"samples": [{"locationId": 0, "value": "-4494"}, {"locationId": 1, "value": "-2570"}]}
        fake = mock.Mock(status_code=200, headers={}, content=b"{}", url="https://trek…", json=lambda: body)
        with mock.patch("viewer.trek.requests.get", return_value=fake) as get, \
                mock.patch("viewer.elevation.elevations") as earth:
            r = self.client.post(reverse("viewer:pointset-elevation", args=[ps.id]))
        self.assertEqual(r.json()["filled"], 2)
        earth.assert_not_called()
        self.assertIn(trek.MARS_DEM, get.call_args[0][0])
        point = ps.points.get(label="Bradbury")
        self.assertEqual((point.elev, point.elev_source, point.elev_datum),
                         (-4494.0, trek.MARS_ELEV_SOURCE, trek.MARS_ELEV_DATUM))


#: 2CL 한 장의 꼴 — 솔 20 의 것에서 로버 자리 둘레만 남겼다
TWO_CL = """<Product_Observational><start_date_time>2021-06-03T09:01:52.514000Z</start_date_time>
<local_true_solar_time>00020 11:12:00</local_true_solar_time>
<Rover_Location><reference_frame>MARS_COORDINATE_SYSTEM</reference_frame>
<longitude unit="deg">109.908435</longitude><latitude unit="deg">25.083231</latitude></Rover_Location>
<Rover_Location_xyz><reference_frame>LANDING_SITE_COORDINATE_SYSTEM</reference_frame>
<x unit="m">-0.355912</x><y unit="m">-5.125183</y><z unit="m">0.424993</z></Rover_Location_xyz>
</Product_Observational>"""


class Zhurong(SimpleTestCase):
    """주룽 (066) — 논문의 자료에서 뽑은 미터 좌표를 HiRISE 착륙 지점에 붙인다."""

    def test_2CL_에서_솔과_자리를_읽는다(self):
        r = zhurong.read_2cl(TWO_CL)
        self.assertEqual((r["sol"], r["x"], r["y"]), (20, -0.355912, -5.125183))
        self.assertIsNone(zhurong.read_2cl("<x>1</x>"))

    def test_같은_자리의_사진은_한_번(self):
        r = zhurong.read_2cl(TWO_CL)
        later = dict(r, time="2021-06-04T00:00:00Z", x=r["x"] + 0.01)
        moved = dict(r, time="2021-06-05T00:00:00Z", sol=22, x=4.912, y=-13.157)
        got = zhurong.stops([moved, later, r])
        self.assertEqual(len(got), len(zhurong.EARLY) + 2)
        self.assertEqual(got[len(zhurong.EARLY)][0], 20)
        self.assertEqual(got[-1][:3], [22, 4.912, -13.157])

    def test_미터를_경위도로(self):
        origin = (109.925, 25.066)
        lon, lat = zhurong.to_lonlat(0, -1000, origin)
        self.assertEqual(lon, 109.925)
        self.assertAlmostEqual(lat, 25.066 - 1000 * 180 / (3.14159265 * trek.MARS_RADIUS), places=6)
        # 동쪽 1 km 는 위도의 cos 만큼 경도가 더 벌어진다
        lon, _ = zhurong.to_lonlat(1000, 0, origin)
        self.assertAlmostEqual((lon - 109.925) * 0.9058, 1000 * 180 / (3.14159265 * trek.MARS_RADIUS), places=5)

    def test_저장소의_경로는_착륙_지점에서_남쪽으로_1_9_km(self):
        line = zhurong.traverse()["paths"][0]
        self.assertEqual(line[0], [109.925, 25.066])
        self.assertLess(line[-1][1], 25.066 - 0.02)              # 남쪽으로 1.3 km 남짓 내려갔다
        data = zhurong.load()
        walked = sum(((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5 for a, b in zip(data["stops"], data["stops"][1:]))
        self.assertAlmostEqual(walked, 1900, delta=60)


#: Robbins 표의 머리와 세 줄 — 줄 끝은 원본처럼 CR 뿐이다. 게일(이름), 그 안의 작은 것, 날짜 변경선 위의 것
ROBBINS_HEAD = ("CRATER_ID\tLATITUDE_CIRCLE_IMAGE\tLONGITUDE_CIRCLE_IMAGE\tDIAM_CIRCLE_IMAGE\tDEPTH_RIMFLOOR_TOPOG\t"
                "MORPHOLOGY_CRATER_1\tMORPHOLOGY_EJECTA_1\tNUMBER_LOBES\tDEGRADATION_STATE\tCRATER_NAME")
ROBBINS_ROWS = ["23-000004\t-5.367\t137.811\t154.08\t4.72\tCpxCPk\t\t\t2\tGale",
                "23-100000\t-5.4\t137.4\t3.0\t0.2\tSmpl\tSLERS\t1\t4\t",
                "10-000001\t10.0\t179.99\t20.0\t\t\t\t\t\t"]


class MarsCraters(TestCase):
    """화성 크레이터 (067) — 표를 sqlite 로 굽고, 타일을 그리고, 누른 자리의 가장 작은 것을 찾는다."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-craters-")
        patch = override_settings(MARS_DIR=self.dir, TILE_CACHE_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        src = Path(self.dir) / "r.tab"
        src.write_text("\r".join([ROBBINS_HEAD] + ROBBINS_ROWS) + "\r", encoding="latin-1")
        # 굽는 쪽은 30 만 개 밑이면 멈춘다 — 시험에서는 문턱만 낮춘다
        with mock.patch("viewer.marscraters.MIN_ROWS", 1):
            self.assertEqual(marscraters.build(src, marscraters.data_file()), 3)

    def test_누른_자리를_품은_가장_작은_것(self):
        hit = marscraters.identify(137.4, -5.4)
        self.assertEqual(hit["id"], "23-100000")
        self.assertEqual(marscraters.identify(137.9, -5.3)["name"], "Gale")
        self.assertIsNone(marscraters.identify(0, 0))

    def test_날짜_변경선을_넘는_원(self):
        self.assertEqual(marscraters.identify(-179.99, 10.0)["id"], "10-000001")

    def test_타일은_큰_것만_멀리서(self):
        from PIL import Image
        png = marscraters.render_tile(0, 1, 0)                 # 줌 0 은 200 km 넘는 것만 — 여기엔 없다
        self.assertIsNone(Image.open(io.BytesIO(png)).getbbox())
        png = marscraters.render_tile(4, 28, 8)                # 게일 둘레 (경도 135–146°, 위도 0–−11°)
        self.assertIsNotNone(Image.open(io.BytesIO(png)).getbbox())

    def test_누르면_속성_표(self):
        data = self.client.get(reverse("viewer:mars-info"), {"lon": 137.9, "lat": -5.3, "layer": "craters"}).json()
        rows = dict(data["rows"])
        self.assertEqual((rows["이름"], rows["지름"], rows["보존 상태"]), ("Gale", "154.08 km", "2"))
        en = self.client.get(reverse("viewer:mars-info"), {"lon": 137.4, "lat": -5.4, "layer": "craters"},
                             HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertIn(["Preservation state", "4 — fresh"], en["rows"])

    def test_타일_길과_파일이_없을_때(self):
        self.assertEqual(self.client.get(reverse("viewer:mars-tile", args=["craters", 4, 28, 8]))["Content-Type"],
                         "image/png")
        self.assertEqual(self.client.get(reverse("viewer:mars-polar-tile", args=["s", "craters", 0, 0, 0])).status_code,
                         200)
        with override_settings(MARS_DIR=self.dir + "/none"):
            r = self.client.get(reverse("viewer:mars-tile", args=["craters", 1, 0, 0]))
            self.assertEqual(r["Cache-Control"], "no-store")
            note = self.client.get(reverse("viewer:mars-info"), {"lon": 1, "lat": 1, "layer": "craters"}).json()
            self.assertEqual(note["rows"], [])


class MarsTrekSeed(SimpleTestCase):
    """화성 Trek 씨앗 손질 (wetherilli 080) — 한글 제목, 화면에 이미 있는 판과 타일이 빈 판은 숨긴다."""

    def test_화면에_있는_판은_목록에_없다(self):
        ids = {l["id"] for g in trek.client_catalog("mars")["groups"] for l in g["layers"]}
        for dup in ("SIM3292_Global_Geology", "Perseverance_Traverse_Path", "curiosity_hirise_mosaic",
                    "HiRISE_Global", "CTX_beta01_uncontrolled_5m_Caltech"):
            self.assertNotIn(dup, ids)
        self.assertIn("TES_Thermal_Inertia", ids)

    def test_골짜기망과_사구는_우리_문으로(self):
        layers = {l["id"]: l for g in trek.client_catalog("mars")["groups"] for l in g["layers"]}
        self.assertEqual(layers["Hynek_Valley_Networks"]["kind"], "map")
        self.assertEqual(layers["Dune_Field"]["kind"], "map")
        self.assertTrue(trek.map_entry("mars", "Hynek_Valley_Networks"))

    def test_보이는_판은_모두_한글_제목이_있다(self):
        layers = [l for g in trek.client_catalog("mars")["groups"] for l in g["layers"]]
        self.assertEqual([l["title"] for l in layers if not l["ko"]], [])
