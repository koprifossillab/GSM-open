"""남호주 방사능 농도 격자 — 누른 자리의 K·Th·U (wetherilli 358).

진짜 격자(원소마다 650 MB) 대신 같은 꼴의 작은 ER Mapper ZIP 을 지어 굽고 읽는다.
"""
import io
import math
import tempfile
import zipfile
from array import array
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import austates, sarad

HEADER = """DatasetHeader Begin
	CoordinateSpace Begin
		Datum	= "GDA94"
		CoordinateType	= LATLONG
	CoordinateSpace End
	ByteOrder	= LSBFirst
	RasterInfo Begin
		CellType	= IEEE4ByteReal
		NrOfLines	= {rows}
		NrOfCellsPerLine	= {cols}
		NrOfBands	= 1
		NullCellValue	= -99999.00000000
		CellInfo Begin
			Xdimension	= 0.01
			Ydimension	= 0.01
		CellInfo End
		RegistrationCellX	= 0
		RegistrationCellY	= 0
		RegistrationCoord Begin
			Longitude	= 136:0:0.0
			Latitude	= -30:0:0.0
		RegistrationCoord End
	RasterInfo End
DatasetHeader End
"""


def grid_zip(path, element, rows=8, cols=8, value=lambda r, c: r + c / 10):
    """원소 하나의 ZIP — 칸 (r, c) 의 값은 `value(r, c)`, 오른쪽 아래 칸은 빈 곳"""
    body = array("f", (-99999.0 if (r, c) == (rows - 1, cols - 1) else value(r, c) for r in range(rows) for c in range(cols)))
    name = f"SA_RAD_{element}_2024_GDA94_DD"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name + ".ers", HEADER.format(rows=rows, cols=cols))
        zf.writestr(name, body.tobytes())
        zf.writestr("readme.txt", "x")
    return path


class Bake(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        o = override_settings(SARAD_DIR=str(self.tmp / "out"))
        o.enable()
        self.addCleanup(o.disable)

    def build(self, **kw):
        sources = [grid_zip(self.tmp / f"{e}.zip", e, **kw) for e in ("K", "Th", "U")]
        return sarad.build(sources, log=lambda *_: None)

    def test_네_칸에_하나를_고르고_자리를_맞춘다(self):
        meta = self.build()
        self.assertEqual(sorted(meta), ["k", "th", "u"])
        k = meta["k"]
        self.assertEqual((k["cols"], k["rows"], k["dx"]), (2, 2, 0.04))
        # 고른 칸은 원본 (2, 2) — 가운데가 136.025°E, −30.025°. 새 칸의 왼쪽 위 모서리는 그보다 반 칸(0.02°) 바깥
        self.assertAlmostEqual(k["west"], 136.005)
        self.assertAlmostEqual(k["north"], -30.005)
        self.assertTrue(sarad.available())

    def test_누른_자리의_값과_배율(self):
        self.build()
        # 원본 (2, 2) 의 값은 2.2 — 고른 첫 칸 안 어디를 눌러도 그 값
        got = sarad.value_at(-30.03, 136.03)
        self.assertEqual(got, {"칼륨 K (%)": 2.2, "토륨 eTh (ppm)": 2.2, "우라늄 eU (ppm)": 2.2})
        self.assertEqual(sarad.value_at(-30.06, 136.07)["칼륨 K (%)"], 6.6)     # 원본 (6, 6)
        self.assertEqual(sarad.value_at(-29.9, 136.03), {})                     # 격자 밖(북쪽)
        self.assertEqual(sarad.value_at(-30.03, 135.99), {})                    # 격자 밖(서쪽)

    def test_빈_곳은_없는_값(self):
        # 고른 칸이 빈 곳(−99999)이면 그 원소를 싣지 않는다
        sources = [grid_zip(self.tmp / "K.zip", "K", value=lambda r, c: -99999.0)]
        sarad.build(sources, log=lambda *_: None)
        self.assertEqual(sarad.value_at(-30.03, 136.03), {})

    def test_한_원소만_다시_구우면_보탠다(self):
        self.build()
        sarad.build([grid_zip(self.tmp / "K2.zip", "K", value=lambda r, c: 1.234)], log=lambda *_: None)
        got = sarad.value_at(-30.03, 136.03)
        self.assertEqual((got["칼륨 K (%)"], got["토륨 eTh (ppm)"]), (1.234, 2.2))

    def test_꼴이_다르면_멈춘다(self):
        bad = self.tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("SA_RAD_K_x.ers", HEADER.replace("IEEE4ByteReal", "Unsigned8BitInteger").format(rows=4, cols=4))
            zf.writestr("SA_RAD_K_x", b"\0" * 16)
        with self.assertRaises(sarad.SaradError):
            sarad.build([bad], log=lambda *_: None)
        short = self.tmp / "short.zip"
        with zipfile.ZipFile(short, "w") as zf:
            zf.writestr("SA_RAD_K_x.ers", HEADER.format(rows=4, cols=4))
            zf.writestr("SA_RAD_K_x", b"\0" * 8)
        with self.assertRaises(sarad.SaradError):
            sarad.build([short], log=lambda *_: None)

    def test_도분초(self):
        self.assertAlmostEqual(sarad._dms("129:0:4.986"), 129.001385, places=6)
        self.assertAlmostEqual(sarad._dms("-25:59:45.582"), -25.995995, places=6)


class Click(SimpleTestCase):
    """남호주 방사능 삼색을 누르면 상류 대신 우리 파일의 값"""

    def test_파일이_있어야_누른다(self):
        with mock.patch.object(sarad, "available", return_value=False):
            self.assertFalse(austates.queryable("gssa", "gssa:rad_rgb"))
        with mock.patch.object(sarad, "available", return_value=True):
            self.assertTrue(austates.queryable("gssa", "gssa:rad_rgb"))
            self.assertFalse(austates.is_unit("gssa", "gssa:rad_rgb"))      # 범위 범례를 뜨지 않는다
        self.assertFalse(austates.queryable("gssa", "gssa:grav"))              # 다른 영상은 그대로

    def test_누른_화소를_경위도로_옮겨_묻는다(self):
        # 3857 로 136.5°E, −30.5° 둘레 256 px 네모의 가운데 화소
        x = math.radians(136.5) * 6378137.0
        y = math.log(math.tan(math.pi / 4 + math.radians(-30.5) / 2)) * 6378137.0
        params = {"layers": "gssa:rad_rgb", "query_layers": "gssa:rad_rgb", "crs": "EPSG:3857",
                  "bbox": f"{x - 1000},{y - 1000},{x + 1000},{y + 1000}", "width": "256", "height": "256", "i": "127.5", "j": "127.5"}
        with mock.patch.object(sarad, "value_at", return_value={"칼륨 K (%)": 1.5}) as value_at, \
             mock.patch.object(austates.requests, "get") as get:
            got = austates.GSSA.get_feature_info(params)
        get.assert_not_called()
        lat, lon = value_at.call_args.args
        self.assertAlmostEqual(lat, -30.5, places=4)
        self.assertAlmostEqual(lon, 136.5, places=4)
        self.assertEqual(got, {"features": [{"id": "sarad.0", "properties": {"칼륨 K (%)": 1.5}}]})
        self.assertEqual(austates.gs_friendly({"칼륨 K (%)": 1.5}), {"칼륨 K (%)": 1.5})

    def test_빈_곳이면_속성이_없다(self):
        params = {"layers": "gssa:rad_rgb", "crs": "EPSG:4326", "version": "1.1.1", "bbox": "136,-31,137,-30",
                  "width": "10", "height": "10", "x": "5", "y": "5"}
        with mock.patch.object(sarad, "value_at", return_value={}) as value_at:
            self.assertEqual(austates.GSSA.get_feature_info(params), {"features": []})
        lat, lon = value_at.call_args.args
        self.assertAlmostEqual((lat, lon)[1], 136.55)
        with self.assertRaises(austates.AuStatesError):
            austates.GSSA.get_feature_info(dict(params, crs="EPSG:3031"))


class Elements(SimpleTestCase):
    """원소 낱장(wetherilli 366) — 누르면 그 원소를 앞에, 총계수는 격자가 없어 누르지 않는다"""
    VALUES = {"칼륨 K (%)": 1.5, "토륨 eTh (ppm)": 12.0, "우라늄 eU (ppm)": 3.0}
    PARAMS = {"crs": "EPSG:4326", "version": "1.1.1", "bbox": "136,-31,137,-30", "width": "10", "height": "10", "x": "5", "y": "5"}

    def test_누른_원소를_앞에(self):
        for name, first in (("gssa:rad_th", "토륨 eTh (ppm)"), ("gssa:rad_u", "우라늄 eU (ppm)"), ("gssa:rad_rgb", "칼륨 K (%)")):
            with self.subTest(name=name), mock.patch.object(sarad, "value_at", return_value=dict(self.VALUES)):
                props = austates.GSSA.get_feature_info(dict(self.PARAMS, layers=name))["features"][0]["properties"]
            self.assertEqual(next(iter(props)), first)
            self.assertEqual(props, self.VALUES)                    # 셋 다 곁에

    def test_총계수는_누르지_않고_영상은_상류로_그린다(self):
        with mock.patch.object(sarad, "available", return_value=True):
            self.assertFalse(austates.queryable("gssa", "gssa:rad_tc"))
            self.assertTrue(austates.queryable("gssa", "gssa:rad_k"))
            self.assertFalse(austates.is_unit("gssa", "gssa:rad_k"))
        with mock.patch.object(austates.requests, "get") as get:
            get.return_value = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=b"png", url="u", elapsed=None)
            austates.GSSA.get_map(dict(self.PARAMS, layers="gssa:rad_u"))
        self.assertTrue(get.call_args.args[0].startswith(austates.settings.GSSA_IMAGERY_URL))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "rad_u")
