"""수성 (wetherilli P10) — 화성 화면을 옮긴 것. 문은 같은 `trek.py` 의 `mercury_*` 다.

Trek 을 실제로 부르지 않는다. 응답의 꼴은 2026-10-02 에 Mercury Trek 에서 받아 본 그대로다 — ArcGIS 의 뿌리가
`arcgis/rest/services/mercury/` 이고, 표고는 정수(S16), 지명의 갈래는 `keyword` 에 있다.
"""
import re
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import trek
from viewer.models import PointSet, REGIONS
from viewer.tests.test_trek import response, tiff


class Upstream(SimpleTestCase):

    def test_표고는_Mercury_Trek_의_arcgis_뿌리로_묻는다(self):
        raw = tiff([4380.0] * 10 + [-32768.0] * (trek.DEM_SIZE ** 2 - 10))
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            png = trek.mercury_dem_tile(3, 1, 1)
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.startswith("https://trek.nasa.gov/mercury/arcgis/rest/services/mercury/"))
        self.assertIn(trek.MERCURY_DEM + "/ImageServer/exportImage", url)
        self.assertEqual(params["bboxSR"], 104974)
        from PIL import Image
        import io
        px = Image.open(io.BytesIO(png)).getdata()
        decode = lambda p: p[0] * 256 + p[1] + p[2] / 256 - 32768
        self.assertAlmostEqual(decode(px[0]), 4380, places=0)
        self.assertEqual(decode(px[20]), 0)              # S16 의 자료 밖은 0 m

    def test_지명의_갈래는_keyword_에서(self):
        docs = [{"itemType": "nomenclature", "title": "Caloris Planitia", "productType": "nomenclature",
                 "keyword": ["Planitia, planitiae"], "bbox": "162.7,31.5,162.7,31.5"},
                {"itemType": "nomenclature", "title": "Hun Kal", "productType": "nomenclature",
                 "keyword": ["Crater, craters"], "bbox": "-20.0,-0.6,-20.0,-0.6"},
                {"itemType": "product", "title": "MSGR MDIS, Mosaic Global", "bbox": "-180,-90,180,90"}]
        with mock.patch("viewer.trek.requests.get", return_value=response({"response": {"docs": docs}})) as get:
            places = trek.fetch_places("mercury")
        self.assertIn("/mercury/", get.call_args[0][0])
        self.assertEqual(get.call_args[1]["params"]["proj"], "urn:ogc:def:crs:EPSG::104974")
        self.assertEqual([p[:2] for p in places], [["Caloris Planitia", "Planitia"], ["Hun Kal", "Crater"]])

    def test_극지_짝은_찾지_않는다(self):
        # 수성에는 극지 판 타일이 없다(`tiles/Mercury/NP` 404) — 서비스 목록을 묻지 않는다
        with mock.patch("viewer.trek.requests.get") as get:
            self.assertEqual(trek.polar_twins("mercury"), {})
        get.assert_not_called()

    def test_판_목록의_뿌리(self):
        self.assertEqual(trek.tiles_root("mercury"), "https://trek.nasa.gov/tiles/Mercury/EQ")


class MercuryViews(TestCase):

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-mercury-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_표고는_캐시에_담고_다시_묻지_않는다(self):
        url = reverse("viewer:mercury-dem", args=[2, 3, 1])
        raw = tiff([100.0] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            first = self.client.get(url)
            second = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, second.content)
        self.assertEqual(get.call_count, 1)

    def test_줌_끝_너머와_격자_밖은_404(self):
        self.assertEqual(self.client.get(reverse("viewer:mercury-dem", args=[8, 0, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:mercury-dem", args=[0, 2, 0])).status_code, 404)

    def test_지명_찾기는_저장소의_파일을_뒤진다(self):
        data = self.client.get(reverse("viewer:mercury-places"), {"q": "caloris"}).json()
        self.assertIn("Caloris Planitia", [p["name"] for p in data["results"]])


class MercuryView(TestCase):
    """수성 화면 — 달·화성처럼 숨은 차림·몸 탭에서 들어가고, 제 아이콘·대기 화면을 쓴다."""

    def test_수성_화면이_제_스크립트를_싣는다(self):
        html = self.client.get(reverse("viewer:mercury")).content.decode()
        self.assertIn('data-region="mercury"', html)
        self.assertIn("viewer/mercury.js", html)
        self.assertIn("viewer/emblem-mercury.png", html)
        self.assertIn("viewer/splash-mercury.gif", html)

    def test_다른_화면에서_수성을_연다(self):
        for name in ("map", "earth", "moon", "mars"):
            html = self.client.get(reverse(f"viewer:{name}")).content.decode()
            menu = re.search(r'<nav class="hidden-menu" id="hidden-menu"[^>]*hidden>(.*?)</nav>', html, re.S)
            self.assertIn('href="/GSM/mercury/"', menu.group(1), name)

    def test_수성은_지역_탭이_아니다(self):
        self.assertNotIn("mercury", dict(REGIONS))


class MercuryPointSets(TestCase):
    """점묶음의 몸 — 수성 화면은 수성 것만, 표고는 MESSENGER 665 m 로."""

    CSV = "name,lat,lon\nCaloris,31.5,162.7\nHun Kal,-0.6,-20.0\n"

    def upload(self, **extra):
        return self.client.post(reverse("viewer:pointset-upload"),
                                {"file": SimpleUploadedFile("mercury.csv", self.CSV.encode()), **extra})

    def test_수성에서_올리면_수성_점묶음이고_지구에는_없다(self):
        self.assertEqual(self.upload(body="mercury").json()["pointset"]["body"], "mercury")
        self.upload()
        self.assertEqual(len(self.client.get(reverse("viewer:pointset-index"), {"body": "mercury"}).json()["pointsets"]), 1)
        self.assertEqual(len(self.client.get(reverse("viewer:pointset-index"), {"body": "mars"}).json()["pointsets"]), 0)
        self.assertEqual(len(self.client.get(reverse("viewer:pointset-index")).json()["pointsets"]), 1)

    def test_표고는_MESSENGER_로(self):
        self.upload(body="mercury")
        ps = PointSet.objects.get()
        body = {"samples": [{"locationId": 0, "value": "-2825"}, {"locationId": 1, "value": "-126"}]}
        fake = mock.Mock(status_code=200, headers={}, content=b"{}", url="https://trek…", json=lambda: body)
        with mock.patch("viewer.trek.requests.get", return_value=fake) as get, \
                mock.patch("viewer.elevation.elevations") as earth:
            r = self.client.post(reverse("viewer:pointset-elevation", args=[ps.id]))
        self.assertEqual(r.json()["filled"], 2)
        earth.assert_not_called()
        self.assertIn(trek.MERCURY_DEM + "/ImageServer/getSamples", get.call_args[0][0])
        point = ps.points.get(label="Caloris")
        self.assertEqual((point.elev, point.elev_source, point.elev_datum),
                         (-2825.0, trek.MERCURY_ELEV_SOURCE, trek.MERCURY_ELEV_DATUM))


class MercuryTrekSeed(SimpleTestCase):
    """수성 Trek 씨앗 — 화면의 배경과 같은 판은 숨기고, 타일이 빈 5M 지질 도폭은 목록에 없다."""

    def layers(self):
        return {l["id"]: l for g in trek.client_catalog("mercury")["groups"] for l in g["layers"]}

    def test_배경과_같은_판은_목록에_없다(self):
        layers = self.layers()
        for dup in trek.IN_USE["mercury"]:
            self.assertNotIn(dup, layers)
        self.assertIn("CrustalThickness_Map_HgM008_16ppd", layers)

    def test_5M_도폭은_타일이_비어_목록에_없다(self):
        self.assertFalse([k for k in self.layers() if k.startswith("Mercury_5M_")])

    def test_보이는_판은_모두_한글_제목이_있다(self):
        self.assertEqual([l["title"] for l in self.layers().values() if not l["ko"]], [])
