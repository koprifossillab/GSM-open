"""남극·북극 — GIBS 날마다 영상 (wetherilli 427). 상류를 부르지 않는다."""
import datetime
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import basemaps, tiles

JPEG = b"\xff\xd8\xff\xe0fake"
STATIC = Path(__file__).resolve().parent.parent / "static" / "viewer"


def ago(days):
    return (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=days)).isoformat()


class Door(SimpleTestCase):
    def test_아는_타일(self):
        self.assertTrue(basemaps.knows_gibs_daily("3031", "VIIRS_NOAA20_CorrectedReflectance_TrueColor", "2026-01-10", 5, 63, 63))
        self.assertFalse(basemaps.knows_gibs_daily("3031", "VIIRS_NOAA20_CorrectedReflectance_TrueColor", "2026-01-10", 6, 0, 0))   # 250m 은 5 까지
        self.assertTrue(basemaps.knows_gibs_daily("3413", "VIIRS_NOAA20_L3_Sea_Ice_Daily", "2026-01-10", 3, 15, 15))
        self.assertFalse(basemaps.knows_gibs_daily("3413", "VIIRS_NOAA20_L3_Sea_Ice_Daily", "2026-01-10", 4, 0, 0))   # 1km 은 3 까지
        self.assertFalse(basemaps.knows_gibs_daily("4326", "MODIS_Terra_CorrectedReflectance_TrueColor", "2026-01-10", 0, 0, 0))
        self.assertFalse(basemaps.knows_gibs_daily("3031", "BlueMarble_ShadedRelief_Bathymetry", "2026-01-10", 0, 0, 0))

    def test_날짜(self):
        self.assertIsNone(basemaps.gibs_daily_date("1999-12-31"))          # MODIS 첫날 앞
        self.assertIsNone(basemaps.gibs_daily_date(ago(-5)))               # 닷새 뒤
        self.assertIsNone(basemaps.gibs_daily_date("2026-02-30"))
        self.assertIsNotNone(basemaps.gibs_daily_date(ago(-1)))            # 한국의 오늘은 UTC 의 내일일 수 있다
        self.assertTrue(basemaps.gibs_daily_fresh(ago(1)))
        self.assertFalse(basemaps.gibs_daily_fresh(ago(10)))

    def test_주소는_정적_판과_같다(self):
        with mock.patch.object(basemaps, "_get", return_value=JPEG) as get:
            basemaps.gibs_daily_tile("3031", "MODIS_Terra_CorrectedReflectance_Bands367", "2026-01-10", 2, 3, 1)
        self.assertEqual(get.call_args.args[1], "https://gibs.earthdata.nasa.gov/wmts/epsg3031/best/MODIS_Terra_CorrectedReflectance_Bands367"
                                                "/default/2026-01-10/250m/2/1/3.jpeg")
        self.assertTrue(get.call_args.kwargs["empty_404"])


class View(SimpleTestCase):
    def test_지난_날은_날짜를_열쇠에_넣어_담는다(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(basemaps, "_get", return_value=JPEG) as get:
            one = self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/2026-01-10/1/1/2.jpeg")
            again = self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/2026-01-10/1/1/2.jpeg")
            other = self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/2026-01-11/1/1/2.jpeg")
        self.assertEqual((one.status_code, again.status_code, other.status_code), (200, 200, 200))
        self.assertEqual(one["X-GSM-Cache"], "miss")
        self.assertEqual(again["X-GSM-Cache"], "hit")
        self.assertEqual(other["X-GSM-Cache"], "miss")                  # 다른 날은 다른 열쇠
        self.assertEqual(get.call_count, 2)

    def test_차는_날은_담지_않는다(self):
        url = f"/GSM/gibs/3413/MODIS_Terra_CorrectedReflectance_TrueColor/{ago(1)}/0/0/0.jpeg"
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(basemaps, "_get", return_value=JPEG) as get:
            first = self.client.get(url)
            self.client.get(url)
        self.assertEqual(first["Cache-Control"], "no-store")
        self.assertEqual(get.call_count, 2)

    def test_못_받은_칸은_투명하게(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp), \
                mock.patch.object(basemaps, "_get", side_effect=basemaps.BasemapError("닿지 못했다")):
            got = self.client.get("/GSM/gibs/3413/VIIRS_NOAA20_L3_Sea_Ice_Daily/2026-01-10/1/1/2.png")
        self.assertEqual(got.content, tiles.blank_tile(512, 512))
        self.assertEqual(got["Cache-Control"], "no-store")

    def test_모르는_타일은_404(self):
        self.assertEqual(self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/2026-01-10/6/0/0.jpeg").status_code, 404)
        self.assertEqual(self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/2026-01-10/0/0/0.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/gibs/3031/VIIRS_NOAA20_CorrectedReflectance_TrueColor/1990-01-10/0/0/0.jpeg").status_code, 404)


class Script(SimpleTestCase):
    def test_화면의_이름은_문의_표와_같다(self):
        js = (STATIC / "map.js").read_text(encoding="utf-8")
        block = js[js.index("// 날마다 영상 (wetherilli 427)"):js.index("BASEMAPS.esri_antarctic = {")]
        names = re.findall(r'layer: "(\w+)", ext: "(\w+)", matrix: "(\w+)", zoom: (\d), lag: (\d)', block)
        self.assertEqual({n: (e, m, int(z), int(l)) for n, e, m, z, l in names}, basemaps.GIBS_DAILY)

    def test_공유_링크가_날짜를_싣는다(self):
        self.assertIn('"d"', (STATIC / "share.js").read_text(encoding="utf-8"))
