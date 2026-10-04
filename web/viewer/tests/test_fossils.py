"""화석 산지 — PBDB 를 굽고 연대마다 그 자리에 찍는다 (wetherilli 098).

PBDB 를 실제로 부르지 않는다. CSV 의 꼴은 2026-09-30 에 `colls/list.csv?show=loc,paleoloc,strat,geo,time,ref` 로 받은 그대로다.
"""
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import fossils, pbdb

HEAD = ("collection_no,lng,lat,collection_name,formation,early_interval,late_interval,max_ma,min_ma,cc,n_occs,"
        "paleolng,paleolat,environment,primary_reference\n")
ROWS = [
    # 서울 가까이 — 판 604. 페름기 말–트라이아스기 초 (250 Ma 를 품는다)
    '1,126.98,37.57,서울 산지,"Pyeongan Sup.",Changhsingian,Induan,254.1,249.9,KR,12,105.0,30.6,"marginal marine",Kim 2001\n',
    # 태평양 한가운데 — 판 조각 밖. 오늘만 뜬다
    "2,-150,0,해저 산지,,Maastrichtian,,72.1,66.0,,3,,,deep subtidal,\n",
    # 20 ka 를 품는 제4기 산지
    "3,-105.3,40.0,볼더 산지,,Late Pleistocene,,0.129,0.0117,US,5,-104.9,40.1,fluvial,\n",
]


def baked(folder) -> Path:
    src = Path(folder) / "c.csv"
    src.write_text(HEAD + "".join(ROWS), encoding="utf-8")
    out = Path(folder) / fossils.FILE
    fossils.build(src, out, log=lambda *_: None)
    return out


class Build(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-fossils-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)

    def test_판을_붙여_굽는다(self):
        rows = {r["no"]: r for r in fossils.db().execute("SELECT * FROM coll")}
        self.assertEqual(rows[1]["pid"], 604)
        self.assertIsNone(rows[2]["pid"])

    def test_오늘은_모두_오늘의_자리에(self):
        self.assertEqual(sorted(p[2] for p in fossils.points(0, -180, -90, 180, 90)), [1, 2, 3])

    def test_1_Ma_안쪽은_그_연대를_품은_산지만_오늘의_자리에(self):
        got = fossils.points(0.02, -180, -90, 180, 90)
        self.assertEqual([(p[2], p[0]) for p in got], [(3, -105.3)])

    def test_1_Ma_부터는_그때의_자리에(self):
        fossils._moved.cache_clear()
        got = fossils.points(250, -180, -90, 180, 90)
        self.assertEqual([p[2] for p in got], [1])          # 바다 밑 산지는 옛 연대에 뜨지 않는다
        self.assertAlmostEqual(got[0][0], 105.01, delta=0.05)
        self.assertAlmostEqual(got[0][1], 30.58, delta=0.05)

    def test_누른_자리_둘레(self):
        fossils._moved.cache_clear()
        hits = fossils.near(250, 105.0, 30.6, 0.2)
        self.assertEqual([row["no"] for row, _ in hits], [1])
        self.assertEqual(fossils.near(250, 0, 0, 0.2), [])

    def test_색은_기의_색(self):
        self.assertEqual(fossils.colour(252), (240, 64, 40))      # 페름기
        self.assertEqual(fossils.colour(0.07), (249, 249, 127))   # 제4기


class Door(SimpleTestCase):
    def test_받아_적는다(self):
        dest = Path(tempfile.mkdtemp()) / "c.csv"
        answer = mock.MagicMock(status_code=200, url="https://paleobiodb.org/…")
        answer.__enter__.return_value = answer
        answer.iter_content.return_value = [b"collection_no\n", b"1\n"]
        with mock.patch.object(pbdb.requests, "get", return_value=answer) as get, \
             mock.patch.object(pbdb.usage, "record"):
            self.assertEqual(pbdb.download(dest), 16)
        self.assertEqual(dest.read_bytes(), b"collection_no\n1\n")
        self.assertIn("all_records", get.call_args.kwargs["params"])

    def test_굽기만(self):
        folder = tempfile.mkdtemp()
        src = Path(folder) / "c.csv"
        src.write_text(HEAD + ROWS[0], encoding="utf-8")
        with override_settings(EARTH_DIR=folder), mock.patch.object(pbdb, "download") as download:
            out = io.StringIO()
            call_command("fetch_pbdb", csv=str(src), stdout=out)
        download.assert_not_called()
        self.assertIn("1 곳", out.getvalue())

    def test_산지_쪽은_displayCollectionDetails(self):
        # basicCollectionSearch 는 2026-10-01 에 403 을 준다 (wetherilli 112)
        self.assertEqual(pbdb.collection_url(1000),
                         "https://paleobiodb.org/classic/displayCollectionDetails?collection_no=1000")


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-fossils-")
        patch = override_settings(EARTH_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-fossils-t-"))
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)
        fossils._moved.cache_clear()

    def test_타일(self):
        url = reverse("viewer:earth-fossil-tile", kwargs={"ka": 250000, "z": 0, "x": 1, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        im = Image.open(io.BytesIO(first.content)).convert("RGBA")
        self.assertGreater(im.getextrema()[3][1], 200)            # 점이 찍혔다

    def test_누르면_산지(self):
        data = self.client.get(reverse("viewer:earth-fossil-at"),
                               {"lon": 105.0, "lat": 30.6, "age": 250, "r": 0.2}).json()
        hit = data["hits"][0]
        rows = dict(hit["rows"])
        self.assertEqual((hit["no"], rows["산지"], rows["연대 (Ma)"]), (1, "서울 산지", "254.1 – 249.9"))
        self.assertEqual(rows["시대"], "창싱절~인더스절")
        self.assertIn("PBDB 의 옛 자리", rows)
        self.assertTrue(hit["link"].endswith("collection_no=1"))

    def test_파일이_없으면_빈_타일(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            r = self.client.get(reverse("viewer:earth-fossil-tile", kwargs={"ka": 0, "z": 0, "x": 0, "y": 0}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(r.content)).convert("RGBA").getextrema()[3], (0, 0))


class Density(TestCase):
    """밀도 열지도 (wetherilli 286) — 점 레이어와 같은 고르기를 1° 칸에 센다"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-fossils-")
        patch = override_settings(EARTH_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-fossils-t-"))
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)
        fossils._moved.cache_clear()
        fossils.density_image.cache_clear()
        self.addCleanup(fossils.density_image.cache_clear)

    def test_칸을_센다(self):
        _, top = fossils.density_image(0.0)
        self.assertEqual(top, 1)                                      # 세 산지가 다른 칸에 하나씩
        _, top = fossils.density_image(250.0)
        self.assertEqual(top, 1)                                      # 250 Ma 는 서울 산지 하나(그때의 자리로)
        _, top = fossils.density_image(500.0)
        self.assertEqual(top, 0)                                      # 품은 산지가 없다

    def test_그때의_자리에_칠한다(self):
        im, _ = fossils.density_image(250.0)
        moved = fossils.points(250, -180, -90, 180, 90)[0]
        i, j = int(moved[0] + 180), int(90 - moved[1])
        self.assertGreater(im.getpixel((i, j))[3], 100)
        self.assertEqual(im.getpixel((int(126.98 + 180), int(90 - 37.57)))[3] > 100,
                         (i, j) == (int(126.98 + 180), int(90 - 37.57)))   # 오늘의 자리는 (옮겨지지 않았다면) 비어 있다

    def test_타일과_화면(self):
        url = reverse("viewer:earth-fossil-density-tile", kwargs={"ka": 0, "z": 0, "x": 1, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        self.assertGreater(Image.open(io.BytesIO(first.content)).convert("RGBA").getextrema()[3][1], 100)
        self.assertEqual(self.client.get(url.replace("/0/0/1/0.png", "/0/9/1/0.png")).status_code, 404)
        self.assertIn('"fossildensity": [{"color"', self.client.get("/GSM/earth/").content.decode())
