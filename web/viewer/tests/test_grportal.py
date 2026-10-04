"""그린란드 정부 포털 — 점을 통째로 받는 네 번째 문.

포털을 실제로 부르지 않는다. 응답의 꼴은 2026-09-27 에 받아 본 그대로다
(`f=geojson`, 한 장에 2 000 점, 더 있으면 `exceededTransferLimit`).
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import grportal, i18n, views
from viewer.models import Layer, LayerGroup


def feature(fid, lon=-22.3419997584601, lat=70.5526333267045, **props):
    base = {"sample_no": "05EH-15", "age_num": 397.3, "uncertaint": "       1.7",
            "formation": " ", "details": "http://data.geus.dk/gg_detail/?cat=gcr&id=59"}
    base.update(props)
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": base}


def page(features, more=False):
    body = {"type": "FeatureCollection", "features": features}
    if more:
        body["properties"] = {"exceededTransferLimit": True}
    return mock.Mock(status_code=200, content=json.dumps(body).encode(), json=lambda: body)


class Compact(SimpleTestCase):
    fields = grportal.LAYERS["grportal:geochron"]["fields"]

    def test_빈칸을_떼고_빈_값은_뺀다(self):
        got = grportal.compact(feature(1), self.fields)
        self.assertEqual(got["properties"]["err"], "1.7")
        self.assertEqual(got["properties"]["age"], 397.3)
        self.assertNotIn("fm", got["properties"])                    # " " 뿐이었다
        self.assertEqual(got["geometry"]["coordinates"], [-22.342, 70.55263])

    def test_http_가_아닌_주소는_받지_않는다(self):
        got = grportal.compact(feature(1, details="javascript:alert(1)"), self.fields)
        self.assertNotIn("link", got["properties"])

    def test_점이_아니면_버린다(self):
        f = feature(1)
        f["geometry"] = None
        self.assertIsNone(grportal.compact(f, self.fields))

    def test_시료의_색은_rgb_에서(self):
        fields = grportal.LAYERS["grportal:samples"]["fields"]
        got = grportal.compact({"id": 1, "geometry": {"type": "Point", "coordinates": [0, 0]},
                                "properties": {"rgb": "220 220 0", "material_s": "   Black sand\r\nBlack sand"}},
                               fields)
        self.assertEqual(got["properties"]["color"], "#dcdc00")
        self.assertEqual(got["properties"]["mat"], "Black sand Black sand")


class Fetch(SimpleTestCase):
    def test_장을_넘기며_끝까지_받는다(self):
        pages = [page([feature(1), feature(2)], more=True), page([feature(3)])]
        with mock.patch.object(grportal, "PAGE", 2), \
                mock.patch.object(grportal.requests, "get", side_effect=pages) as get, \
                mock.patch.object(grportal.usage, "record"):
            got = grportal.fetch("grportal:geochron", pause=0)
        self.assertEqual([f["id"] for f in got], [1, 2, 3])
        self.assertEqual([c.kwargs["params"]["resultOffset"] for c in get.call_args_list], [0, 2])
        first = get.call_args_list[0]
        self.assertEqual(first.kwargs["headers"]["User-Agent"], "GSM/0.1")
        self.assertEqual(first.kwargs["params"]["outSR"], "4326")
        self.assertIn("geochron/FeatureServer/0/query", first.args[0])

    def test_200_에_실린_오류도_오류다(self):
        body = {"error": {"code": 400, "message": "Invalid query"}}
        resp = mock.Mock(status_code=200, content=json.dumps(body).encode(), json=lambda: body)
        with mock.patch.object(grportal.requests, "get", return_value=resp), \
                mock.patch.object(grportal.usage, "record"):
            with self.assertRaises(grportal.PortalError):
                grportal.fetch("grportal:geochron", pause=0)


class Areas(SimpleTestCase):
    """면과 갈래 색 — 광물 잠재 구역·불안정 사면·매스무브먼트·다이아몬드 산출지 (wetherilli 089)."""

    def test_면은_레이어_번호와_줄이기를_붙여_받는다(self):
        square = {"type": "Feature", "id": None,
                  "geometry": {"type": "Polygon", "coordinates": [[[-50, 70], [-49, 70], [-49, 71], [-50, 70]]]},
                  "properties": {"OBJECTID": 7, "Placename": "Sermikassak", "heights": 580}}
        with mock.patch.object(grportal.requests, "get", return_value=page([square])) as get, \
                mock.patch.object(grportal.usage, "record"):
            got = grportal.fetch("grportal:unstable_slopes", pause=0)
        self.assertEqual(got[0]["geometry"]["type"], "Polygon")
        self.assertEqual(got[0]["id"], 7)                              # FID 가 아니라 OBJECTID
        self.assertEqual(got[0]["properties"], {"place": "Sermikassak", "h": 580.0})
        call = get.call_args_list[0]
        self.assertIn("_WFL1/FeatureServer/2/query", call.args[0])
        self.assertEqual(call.kwargs["params"]["maxAllowableOffset"], 0.0001)
        self.assertEqual(call.kwargs["params"]["orderByFields"], "OBJECTID ASC")

    def test_옛_레이어의_캐시_열쇠는_그대로다(self):
        self.assertTrue(grportal.signature("grportal:geochron").startswith("geochron|FID|"))
        self.assertTrue(grportal.signature("grportal:unstable_slopes").startswith(
            "Map_of_unstable_slopes_and_registered_mass_movements_WFL1/2|OBJECTID|g=0.0001|"))

    def test_모르는_값_마이너스_999_는_뺀다(self):
        fields = grportal.LAYERS["grportal:diamond_occurrences"]["fields"]
        got = grportal.compact({"id": 1, "geometry": {"type": "Point", "coordinates": [-52, 65]},
                                "properties": {"STRIKE": -999, "DIP": 90, "DIAM_GRADE": " "}}, fields)
        self.assertEqual(got["properties"], {"dip": 90.0})

    def test_갈래를_가르고_범례를_싣는다(self):
        rows = [{"type": "Feature", "id": i, "geometry": {"type": "Point", "coordinates": [-52, 65]},
                 "properties": {"rock": rock}}
                for i, rock in enumerate(["Kimberlitic", "Carbonatite_Kimberlitic", "Lamproitic",
                                          "Lamprophyre_Ultramafic", "Kimberlitic", "Not_Reported"])]
        body = json.loads(grportal.body("grportal:diamond_occurrences", json.dumps(rows).encode()))
        self.assertEqual(body["style"], "class")
        self.assertEqual([f["properties"]["code"] for f in body["features"]],
                         ["kimb", "carb", "lampo", "lampr", "kimb", "other"])
        self.assertEqual([(r["code"], r["count"]) for r in body["legend"]],
                         [("kimb", 2), ("carb", 1), ("lampo", 1), ("lampr", 1), ("other", 1)])
        self.assertIn("rock", body["labels"])

    def _codes(self, name, props_list):
        rows = [{"type": "Feature", "id": i, "geometry": {"type": "Point", "coordinates": [-52, 65]}, "properties": p}
                for i, p in enumerate(props_list)]
        body = json.loads(grportal.body(name, json.dumps(rows).encode()))
        return [f["properties"]["code"] for f in body["features"]]

    def test_시추공_보고_없음은_만나지_못했다와_가른다(self):
        # `Not_Reported` 도 `No` 로 시작한다 (wetherilli 157)
        self.assertEqual(self._codes("grportal:diamond_drillholes", [{"kim": "Yes"}, {"kim": "No"}, {"kim": "Not_Reported"}]),
                         ["yes", "no", "nr"])

    def test_농도는_값의_구간으로(self):
        self.assertEqual(self._codes("grportal:diamond_indicators",
                                     [{"pkg": 130783.3}, {"pkg": 100}, {"pkg": 99.9}, {"pkg": 1}, {"pkg": 0.5}, {}]),
                         ["c100", "c100", "c10", "c1", "c0", "c0"])
        self.assertEqual(self._codes("grportal:diamond_per_kg", [{"pkg": 3.5}, {"pkg": 0.3}, {"pkg": 0.05}, {"pkg": 0}]),
                         ["d1", "d025", "d005", "d0"])

    def test_석류석은_G10D_G10_G9_차례로(self):
        self.assertEqual(self._codes("grportal:garnet_classes",
                                     [{"g10d": 1, "g10": 22, "g9": 67}, {"g10d": 0, "g10": 3}, {"g9": 5}, {"g11": 9}]),
                         ["g10d", "g10", "g9", "other"])

    def test_화학_갈래는_가장_많은_것(self):
        # `{"top": 열, "of": [열…]}` — 같으면 표의 앞 줄 (wetherilli 178)
        self.assertEqual(self._codes("grportal:spinel_classes",
                                     [{"cid": 1, "per": 5, "uncl": 2}, {"cid": 3, "per": 3}, {"uncl": 4}, {"cid": 0}]),
                         ["per", "cid", "uncl", "other"])

    def test_암맥은_선으로_받는다(self):
        fields = grportal.LAYERS["grportal:diamond_dykes"]["fields"]
        line = {"id": 1, "geometry": {"type": "LineString", "coordinates": [[-51.174471, 66.301862], [-51.18539, 66.30184]]},
                "properties": {"RockGroup": "Kimberlite", "LocalityNa": "Pyramidefjeld"}}
        got = grportal.compact(line, fields, areal=True)
        self.assertEqual(got["geometry"]["type"], "LineString")
        self.assertIsNone(grportal.compact(line, fields))                     # 점 레이어는 선을 받지 않는다
        self.assertEqual(self._codes("grportal:diamond_dykes", [{"rock": "Kimberlite"}, {"rock": " "}]), ["kimb", "other"])

    def test_DED_는_이용_조건이_적혀_있다(self):
        self.assertIn("CC BY 4.0", grportal.license_of("grportal:diamond_drillholes"))
        self.assertIn("CC BY 4.0", grportal.license_of("grportal:diamond_occurrences"))
        self.assertEqual(grportal.license_of("grportal:geochron"), "")

    def test_갈래가_없는_옛_레이어는_그대로_싼다(self):
        body = json.loads(grportal.body("grportal:geochron", b"[]"))
        self.assertEqual(body["style"], "age")
        self.assertNotIn("legend", body)

    def test_범례_이름도_영어가_있다(self):
        for spec in grportal.LAYERS.values():
            if "classes" in spec:
                for row in list(spec["classes"]["table"]) + [spec["classes"]["else"]]:
                    self.assertIn(row[1], {**i18n.EN, **i18n.PROP_EN}, row[1])

    def test_작성_중인_지도는_캐시를_30_일만_믿는다(self):
        self.assertEqual(grportal.fresh_seconds("grportal:unstable_slopes"), 30 * 86400)
        self.assertIsNone(grportal.fresh_seconds("grportal:geochron"))


class Words(SimpleTestCase):
    """팝업 이름·레이어·레이어군의 영어가 표에 있다 (CLAUDE.md "영어판")."""

    def test_팝업_이름은_모두_PROP_EN_에(self):
        for name in grportal.LAYERS:
            for label in grportal.labels(name).values():
                self.assertIn(label, i18n.PROP_EN, label)

    def test_레이어와_레이어군(self):
        seed = json.loads((views.settings.GRPORTAL_CATALOG_SEED).read_text(encoding="utf-8"))
        for row in seed["레이어"]:
            self.assertIn(row["name"], i18n.LAYER_EN)
            self.assertIn(row["name"], grportal.LAYERS)              # 씨앗과 문이 짝이 맞다
        for group in seed["레이어군순서"]:
            self.assertIn(group, i18n.GROUP_EN)


class View(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-grp-"),
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="시료·연대 (정부 포털)", region="greenland")
        Layer.objects.create(name="grportal:geochron", title="연대측정", group=g, upstream="grportal")

    def test_카탈로그에_점_레이어라고_적는다(self):
        layer = views._catalog()[0]["layers"][0]
        self.assertEqual(layer["kind"], "points")
        self.assertFalse(layer["queryable"])                        # /featureinfo/ 를 부르지 않는다
        self.assertEqual(layer["style"], "age")
        self.assertIn("6ddb07fed184429cab4c8a3f1326d644", layer["source"])

    def test_한_번_받으면_다시_묻지_않는다(self):
        with mock.patch.object(grportal, "fetch", return_value=[grportal.compact(
                feature(7), grportal.LAYERS["grportal:geochron"]["fields"])]) as up:
            r1 = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
            r2 = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
        self.assertEqual(up.call_count, 1)
        self.assertEqual(r1.status_code, 200)
        data = json.loads(r2.content)
        self.assertEqual(data["features"][0]["id"], 7)
        self.assertEqual(data["labels"]["age"], "연대 (Ma)")
        self.assertEqual(data["style"], "age")

    def test_줄여서_보낸다(self):
        # 점이 넉넉해야 한다. Django 는 줄인 것에 무작위 바이트를 덧대어(BREACH 막이)
        # 짧은 본문은 줄인 쪽이 더 길어지는 때가 있고, 그러면 줄이지 않고 보낸다
        rows = [grportal.compact(feature(i), grportal.LAYERS["grportal:geochron"]["fields"])
                for i in range(50)]
        with mock.patch.object(grportal, "fetch", return_value=rows):
            r = self.client.get("/GSM/points/", {"layer": "grportal:geochron"},
                                HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(r["Content-Encoding"], "gzip")

    def test_상류가_못_주면_옛것을_낸다(self):
        with mock.patch.object(grportal, "fetch", return_value=[]):
            views.point_features("grportal:geochron")
        with mock.patch.object(grportal, "fetch", side_effect=grportal.PortalError("x")):
            data = views.point_features("grportal:geochron", refresh=True)
        self.assertEqual(data, b"[]")

    def test_옛것도_없으면_502(self):
        with mock.patch.object(grportal, "fetch", side_effect=grportal.PortalError("x")):
            r = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
        self.assertEqual(r.status_code, 502)

    def test_모르는_레이어는_404(self):
        r = self.client.get("/GSM/points/", {"layer": "L_50K_Geology_Map"})
        self.assertEqual(r.status_code, 404)


class Seed(TestCase):
    def test_씨앗이_그린란드에_점_레이어를_넣는다(self):
        call_command("seed_catalog", stdout=mock.Mock())
        layer = Layer.objects.get(name="grportal:samples")
        self.assertEqual(layer.upstream, "grportal")
        self.assertEqual(layer.group.region, "greenland")
        self.assertEqual(layer.group.name, "시료·연대 (정부 포털)")


class Geochem(SimpleTestCase):
    """지화학 넷 — 연속값 레이어 (wetherilli 159). 0 은 분석하지 않은 것, 음수는 검출 한계 밑."""

    def test_assay_는_0_을_빼고_음수를_둔다(self):
        from viewer import arcpoints
        self.assertIsNone(arcpoints.clean(0, "assay"))
        self.assertEqual(arcpoints.clean(-10, "assay"), -10)
        self.assertEqual(arcpoints.clean("62", "assay"), 62)

    def test_넷이_같은_원소_표를_받는다(self):
        for key in ("soil", "heavy", "companies", "scree"):
            spec = grportal.LAYERS[f"grportal:geochem_{key}"]
            self.assertEqual(spec["style"], "value")
            self.assertEqual(spec["fields"]["cu"], {"from": "cu_ppm_num", "label": "", "kind": "assay"})
        self.assertEqual(grportal.LAYERS["grportal:geochem_scree"]["fields"]["link"]["from"], "details")
        # 원소 열은 팝업 이름이 없다 — 일흔다섯을 다 올리지 않는다
        self.assertNotIn("cu", grportal.labels("grportal:geochem_soil"))

    def test_덩이에_값이_있는_원소만_싣는다(self):
        features = [{"type": "Feature", "id": 1, "geometry": {"type": "Point", "coordinates": [-45, 62]},
                     "properties": {"sample": "a", "cu": 62, "u": -0.5}},
                    {"type": "Feature", "id": 2, "geometry": {"type": "Point", "coordinates": [-46, 62]},
                     "properties": {"sample": "b", "cu": 12}}]
        data = json.loads(grportal.body("grportal:geochem_soil", json.dumps(features).encode()))
        self.assertEqual(data["style"], "value")
        self.assertEqual(data["default"], "cu")
        # 우라늄은 검출 한계 밑뿐이라 칠할 값이 없다 — 고르개에 싣지 않는다
        self.assertEqual(data["values"], [{"key": "cu", "label": "Cu", "unit": "ppm", "n": 2, "below": 0}])
        self.assertEqual(len(data["features"]), 2)

    def test_원소_이름의_영어(self):
        for _, _, label, _ in grportal.ELEMENTS:
            if any("가" <= ch <= "힣" for ch in label):
                self.assertIn(label, i18n.EN, label)


class WholeRock(TestCase):
    """전암 화학 3 만 점 (wetherilli 163) — 쉼표 소수의 원소 무게 퍼센트, 고른 원소만 잘라 준다."""

    def test_퍼센트를_화면_단위로(self):
        from viewer import arcpoints
        self.assertEqual(arcpoints.clean("0,0044", "pct_ppm"), 44.0)          # 구리 0.0044 % = 44 ppm
        self.assertEqual(arcpoints.clean("3e-06", "pct_ppb"), 30.0)           # 금 30 ppb
        self.assertEqual(arcpoints.clean("22,88", "pct_wt"), 22.88)
        self.assertIsNone(arcpoints.clean("NULL", "pct_ppm"))                 # 분석하지 않은 것
        self.assertEqual(arcpoints.clean("-0,01", "pct_ppm"), -100.0)         # 검출 한계 밑, 한계 100 ppm
        self.assertEqual(arcpoints.clean("0", "pct_ppm"), arcpoints.BELOW_UNKNOWN)
        self.assertEqual(arcpoints.clean("-1", "pct_ppm"), arcpoints.BELOW_UNKNOWN)

    def test_고른_원소의_점만_잘라_준다(self):
        features = [{"type": "Feature", "id": i, "geometry": {"type": "Point", "coordinates": [-45, 61]},
                     "properties": {"sample": str(i), "anal": "1", **props}}
                    for i, props in enumerate(({"cu": 44.0, "u": 2.0}, {"cu": -100.0}, {"si": 22.9}))]
        raw = json.dumps(features).encode()
        data = json.loads(grportal.value_slice("grportal:whole_rock", raw, "cu"))
        self.assertEqual((data["slice"], data["total"], len(data["features"])), ("cu", 3, 2))
        self.assertEqual(data["features"][0]["properties"], {"sample": "0", "anal": "1", "cu": 44.0})
        self.assertEqual({v["key"]: (v["n"], v["below"]) for v in data["values"]}, {"si": (1, 0), "cu": (1, 1), "u": (1, 0)})
        # 모르는 원소면 처음 원소(구리)로
        self.assertEqual(json.loads(grportal.value_slice("grportal:whole_rock", raw, "zz"))["slice"], "cu")

    def test_화면이_받는_것(self):
        features = [{"type": "Feature", "id": 1, "geometry": {"type": "Point", "coordinates": [-45, 61]},
                     "properties": {"sample": "1", "u": 2.3}}]
        with mock.patch.object(views, "point_features", return_value=json.dumps(features).encode()):
            data = json.loads(self.client.get("/GSM/points/", {"layer": "grportal:whole_rock", "value": "u"}).content)
        self.assertEqual(data["slice"], "u")
        self.assertEqual(len(data["features"]), 1)
