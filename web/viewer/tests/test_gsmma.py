"""대만 GSMMA 지질도 (wetherilli 136). 상류를 부르지 않는다 — 지질운의 꼴은 2026-10-02 에 받은 그대로다."""
import io
import json
import math
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import gsmma, i18n
from viewer.models import Layer, LayerGroup

#: 타이베이 한 점(121.5401, 25.0301)을 지질운 `Stratum` 에 물었을 때의 꼴 — 면은 줄였다
TAIPEI = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "geometry": {"type": "Polygon", "coordinates": [[[121.53, 25.02], [121.55, 25.02], [121.55, 25.04],
                                                       [121.53, 25.04], [121.53, 25.02]]]},
     "properties": {"Code": "6020", "Name": "沖積層", "Note": "礫石，砂及粘土", "Time": "全新世", "Abbrev": "a"}},
    {"type": "Feature",
     "geometry": {"type": "Polygon", "coordinates": [[[121.56, 25.02], [121.57, 25.02], [121.57, 25.04],
                                                       [121.56, 25.02]]]},
     "properties": {"Code": "5110", "Name": "南港層", "Note": None, "Time": "中新世中期", "Abbrev": "Nk"}},
]}


class Ages(SimpleTestCase):
    def test_중국어_시대를_옮긴다(self):
        for zh, ko, en in (("全新世", "홀로세", "Holocene"),
                           ("中新世晚期", "마이오세 후기", "Late Miocene"),
                           ("上新世－更新世", "플라이오세~플라이스토세", "Pliocene – Pleistocene"),
                           ("早期至中期始新世", "에오세 전기~중기", "Early Eocene – Middle Eocene"),
                           ("中新世早期至中期", "마이오세 전기~중기", "Early Miocene – Middle Miocene"),
                           ("晚古生代至中生代（？）", "고생대 후기~중생대(?)", "Late Paleozoic – Mesozoic (?)"),
                           ("始新世或更早", "에오세 또는 그 이전", "Eocene or earlier"),
                           ("時代不詳", "시대 미상", "Age unknown")):
            self.assertEqual((i18n.age_zh(zh), i18n.age_zh(zh, "en")), (ko, en), zh)

    def test_모르는_글자가_있으면_원문(self):
        self.assertEqual(i18n.age_zh("寒武紀"), "寒武紀")
        self.assertEqual(i18n.age_zh("全新世全新世"), "全新世全新世")


class Door(SimpleTestCase):
    def test_카탈로그_이름을_상류_레이어로_엮는다(self):
        got = gsmma._upstream_layers("gsmma:geology_1m")
        self.assertEqual(got, "WMS/1M_Geomap_strata_1986,WMS/1M_Geomap_strata_boundary_1986")
        with self.assertRaises(gsmma.GsmmaError):
            gsmma._upstream_layers("gsmma:nope")

    def test_누른_픽셀을_위경도로_4326_은_위도가_먼저(self):
        lon, lat = gsmma.clicked_lonlat({"bbox": "25,121,26,122", "width": "100", "height": "100", "i": "25",
                                         "j": "50", "crs": "EPSG:4326", "version": "1.3.0"})
        self.assertEqual((lon, lat), (121.25, 25.5))

    def test_점을_품은_면만(self):
        self.assertTrue(gsmma.contains(TAIPEI["features"][0]["geometry"], 121.54, 25.03))
        self.assertFalse(gsmma.contains(TAIPEI["features"][1]["geometry"], 121.54, 25.03))
        hole = {"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
                                                    [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]}
        self.assertFalse(gsmma.contains(hole, 2, 2))
        self.assertTrue(gsmma.contains(hole, 0.5, 0.5))


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsmma-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())

    def test_씨앗과_영어(self):
        rows = Layer.objects.filter(upstream="gsmma")
        self.assertEqual({r.name for r in rows}, set(gsmma.LAYERS))
        self.assertEqual({r.group.region for r in rows}, {"taiwan"})
        for row in rows:
            self.assertIn(row.name, i18n.LAYER_EN)
        for group in LayerGroup.objects.filter(region="taiwan"):
            self.assertIn(group.name, i18n.GROUP_EN)

    def test_카탈로그는_4326_으로_받고_범례가_없다(self):
        groups = self.client.get(reverse("viewer:catalog")).json()["groups"]
        rows = {l["name"]: l for g in groups for l in g["layers"] if l["upstream"] == "gsmma"}
        self.assertEqual(rows["gsmma:geology_50k"]["projection"], "EPSG:4326")
        self.assertTrue(rows["gsmma:geology_1m"]["noLegend"])
        self.assertTrue(rows["gsmma:geology_50k"]["queryable"])
        self.assertFalse(rows["gsmma:geology_1m"]["queryable"])

    def test_그림은_상류_레이어로_바꿔_넘긴다(self):
        answer = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
        with mock.patch.object(gsmma.requests, "get", return_value=answer) as get, \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            r = self.client.get(reverse("viewer:wms"), {
                "LAYERS": "gsmma:geology_250k", "CRS": "EPSG:4326", "VERSION": "1.3.0", "REQUEST": "GetMap",
                "BBOX": "22.5,120,23.25,120.75", "WIDTH": 512, "HEIGHT": 512, "FORMAT": "image/png"})
        self.assertEqual(r.status_code, 200)
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["layers"], "WMS/250K_Geomap_strata_1974,WMS/250K_Geomap_strata_boundary_1974,"
                                         "WMS/250K_Geomap_fault_1974")
        self.assertEqual((sent["crs"], sent["bbox"]), ("EPSG:4326", "22.5,120,23.25,120.75"))

    def test_누르면_지질운에_묻고_시대를_옮긴다(self):
        answer = mock.Mock(status_code=200, content=b"", url="…", headers={"content-type": "application/json"})
        answer.json.return_value = json.loads(json.dumps(TAIPEI))
        params = {"layers": "gsmma:geology_50k", "query_layers": "gsmma:geology_50k", "crs": "EPSG:4326",
                  "version": "1.3.0", "bbox": "25.02,121.53,25.04,121.55", "width": 200, "height": 200,
                  "i": 100, "j": 100, "request": "GetFeatureInfo"}
        with mock.patch.object(gsmma.requests, "get", return_value=answer) as get, \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            data = self.client.get(reverse("viewer:featureinfo"), params).json()
            en = self.client.get(reverse("viewer:featureinfo"), params, HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertTrue(get.call_args.args[0].endswith("/Stratum"))
        self.assertEqual(data["features"], [{"id": "gsmma.Stratum.0", "props": {
            "지층명": "沖積層", "암상": "礫石，砂及粘土", "지질시대": "홀로세", "기호": "a"}}])
        self.assertIn("Holocene", en["features"][0]["props"].values())
        self.assertEqual(get.call_count, 1)          # 둘째는 캐시에서 — 말만 다르다

    def test_속성이_없는_레이어는_묻지_않는다(self):
        with mock.patch.object(gsmma.requests, "get") as get:
            data = gsmma.get_feature_info({"query_layers": "gsmma:geology_1m", "bbox": "25,121,26,122",
                                           "crs": "EPSG:4326", "width": 10, "height": 10, "i": 5, "j": 5})
        self.assertEqual(data, {"features": []})
        get.assert_not_called()


class Second(TestCase):
    """둘째 판 (wetherilli 141) — 점 속성, 3857 로 펴기, 3D."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsmma2-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())

    def _answer(self, data):
        answer = mock.Mock(status_code=200, content=b"", url="…", headers={"content-type": "application/json"})
        answer.json.return_value = data
        return answer

    def test_점은_픽셀만큼_넓게_묻고_가까운_것부터(self):
        springs = {"features": [
            {"geometry": {"type": "Point", "coordinates": [121.60, 25.10]},
             "properties": {"SpaName": "먼 곳", "Temperature": 40}},
            {"geometry": {"type": "Point", "coordinates": [121.5001, 25.0001]},
             "properties": {"SpaName": "四磺子坪", "SpaPH": 1.93, "Temperature": 59.5, "Type": "酸性硫酸鹽泉"}}]}
        with mock.patch.object(gsmma.requests, "get", return_value=self._answer(springs)) as get, \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            data = gsmma.get_feature_info({"query_layers": "gsmma:hot_springs", "crs": "EPSG:4326", "version": "1.3.0",
                                           "bbox": "24.9,121.4,25.1,121.6", "width": 200, "height": 200,
                                           "i": 100, "j": 100})
        box = [float(v) for v in get.call_args.kwargs["params"]["bbox"].split(",")]
        self.assertAlmostEqual(box[2] - box[0], 0.016, places=6)            # 한 픽셀 0.001° × 8 × 2
        self.assertEqual(data["features"][0]["properties"]["SpaName"], "四磺子坪")
        self.assertEqual(gsmma.friendly(data["features"][0]["properties"])["수온 (°C)"], "59.5")

    def test_사면_방향의_칸_글자를_뗀다(self):
        slope = {"features": [{"geometry": {"type": "Polygon", "coordinates": [[[121, 25], [122, 25], [122, 26],
                                                                                 [121, 25]]]},
                               "properties": {"MAP_NAME": "貓空", "SLOPE_DIR": "B東南", "Identifier": "누군가"}}]}
        with mock.patch.object(gsmma.requests, "get", return_value=self._answer(slope)), \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            data = gsmma.get_feature_info({"query_layers": "gsmma:dip_slope", "crs": "EPSG:4326", "version": "1.3.0",
                                           "bbox": "25.2,121.6,25.4,121.8", "width": 10, "height": 10,
                                           "i": 5, "j": 5})
        self.assertEqual(data["features"][0]["properties"], {"MAP_NAME": "貓空", "SLOPE_DIR": "東南"})

    def test_3857_은_4326_으로_받아_줄만_다시_고른다(self):
        from PIL import Image
        # 받는 그림: 위에서 아래로 줄마다 빨강 값이 0..255 — 어느 줄을 골랐는지 읽힌다
        src = Image.new("RGBA", (4, 256))
        for row in range(256):
            for x in range(4):
                src.putpixel((x, row), (row, 0, 0, 255))
        buf = io.BytesIO()
        src.save(buf, "PNG")
        answer = mock.Mock(status_code=200, content=buf.getvalue(), url="…", headers={"content-type": "image/png"})
        y0, y1 = 0.0, 6378137.0 * math.log(math.tan(math.pi / 4 + math.radians(60) / 2))     # 적도 ~ 북위 60°
        with mock.patch.object(gsmma.requests, "get", return_value=answer) as get, \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            png, ctype = gsmma.get_map({"layers": "gsmma:geology_1m", "crs": "EPSG:3857", "width": "4",
                                        "height": "128", "bbox": f"0,{y0},100000,{y1}"})
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["crs"], sent["height"]), ("EPSG:4326", 256))
        self.assertEqual([round(float(v), 6) for v in sent["bbox"].split(",")][:3], [0.0, 0.0, 60.0])
        out = Image.open(io.BytesIO(png))
        top, middle, bottom = out.getpixel((0, 0))[0], out.getpixel((0, 64))[0], out.getpixel((0, 127))[0]
        # 메르카토르의 가운데 줄은 위도 60° 의 절반(30°)보다 북쪽(약 36.7°)이다 — 받은 그림의 위쪽 40% 언저리
        self.assertEqual(top, 0)
        self.assertGreaterEqual(bottom, 254)          # 맨 아랫줄의 가운데는 적도보다 조금 북쪽이다
        self.assertTrue(90 < middle < 115, middle)

    def test_3D_목록에_대만이_든다(self):
        r = self.client.get(reverse("viewer:map3d"))
        self.assertContains(r, "gsmma:geology_50k")


class Legend(TestCase):
    """범례 (wetherilli 142) — 지층 면과 그림을 맞대어 견본을 뜬다."""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsmma3-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())

    def _answers(self):
        """지질운: 왼쪽 반 沖積層·오른쪽 반 南港層. 그림: 왼쪽 반 노랑·오른쪽 반 초록."""
        from PIL import Image
        left = {"type": "Polygon", "coordinates": [[[121.0, 25.0], [121.05, 25.0], [121.05, 25.1], [121.0, 25.1],
                                                     [121.0, 25.0]]]}
        right = {"type": "Polygon", "coordinates": [[[121.05, 25.0], [121.1, 25.0], [121.1, 25.1], [121.05, 25.1],
                                                      [121.05, 25.0]]]}
        strata = mock.Mock(status_code=200, content=b"", url="…", headers={"content-type": "application/json"})
        strata.json.return_value = {"features": [
            {"geometry": left, "properties": {"Name": "沖積層", "Abbrev": "a", "Time": "全新世", "Note": "礫石"}},
            {"geometry": right, "properties": {"Name": "南港層", "Abbrev": "Nk", "Time": "中新世中期"}},
            {"geometry": left, "properties": {"Name": "沖積層", "Abbrev": "a", "Time": "全新世", "Note": "礫石"}}]}
        # 범위가 0.1° × 0.2° 라 문은 512 × 1024 로 묻는다 — 받는 그림도 그 크기다
        image = Image.new("RGBA", (512, 1024), (255, 253, 166, 255))
        image.paste((124, 205, 124, 255), (256, 0, 512, 1024))
        buf = io.BytesIO()
        image.save(buf, "PNG")
        picture = mock.Mock(status_code=200, content=buf.getvalue(), url="…", headers={"content-type": "image/png"})
        return lambda url, **kw: strata if "geologycloud" in url else picture

    def test_보는_범위의_지층을_견본과_함께(self):
        with mock.patch.object(gsmma.requests, "get", side_effect=self._answers()), \
             mock.patch.object(gsmma.usage, "record"), mock.patch.object(gsmma.usage, "paused", return_value=0):
            data = self.client.get(reverse("viewer:gsmma-legend"),
                                   {"layer": "gsmma:geology_50k", "bbox": "121.0,25.0,121.1,25.2"}).json()
        rows = data["rows"]
        self.assertEqual([r["symbol"] for r in rows], ["a", "Nk"])               # 많이 나온 차례
        self.assertEqual((rows[0]["color"], rows[1]["color"]), ("#fffda6", "#7ccd7c"))
        self.assertEqual(rows[0]["lithology"], "沖積層 (礫石)")
        self.assertEqual(rows[1]["age"], "마이오세 중기")
        self.assertTrue(rows[0]["swatch"].startswith("data:image/png;base64,"))

    def test_넓으면_들어오라고_한다(self):
        with mock.patch.object(gsmma.requests, "get") as get:
            r = self.client.get(reverse("viewer:gsmma-legend"), {"layer": "gsmma:geology_50k",
                                                                  "bbox": "120.0,23.0,121.5,24.5"})
        self.assertEqual(r.status_code, 422)
        get.assert_not_called()

    def test_카탈로그는_범위_범례를_알린다(self):
        groups = self.client.get(reverse("viewer:catalog")).json()["groups"]
        rows = {l["name"]: l for g in groups for l in g["layers"] if l["upstream"] == "gsmma"}
        self.assertEqual((rows["gsmma:geology_50k"]["legend"], rows["gsmma:geology_50k"]["legendUrl"]),
                         ("extent", "gsmma/legend/"))
        self.assertTrue(rows["gsmma:geology_1m"]["noLegend"])

    def test_오목한_면도_안의_점을(self):
        # ㄷ 자 — 가운데가 비었다
        u = {"type": "Polygon", "coordinates": [[[0, 0], [3, 0], [3, 1], [1, 1], [1, 2], [3, 2], [3, 3], [0, 3],
                                                  [0, 0]]]}
        for x, y in gsmma.inner_points(u):
            self.assertTrue(gsmma.contains(u, x, y), (x, y))
