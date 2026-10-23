"""캐나다 — NRCan 1:500만(Wheeler)·온타리오 OGS (wetherilli 204). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-04 에 받아 본 그대로다 — NRCan GetFeatureInfo 는 GeoJSON(영어·프랑스어 열이 짝으로), OGS 는 REST identify.
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import crs, nrcan, ogs, tilegrid, views


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/", json=lambda: body)


WMS = {"layers": "ogs:3", "query_layers": "ogs:3", "crs": "EPSG:3978", "bbox": "1000000,-200000,1100000,-100000",
       "width": "256", "height": "256", "i": "127", "j": "127", "format": "image/png"}


class Nrcan(SimpleTestCase):
    def test_레이어_이름을_번호로_3978_그대로(self):
        with mock.patch("viewer.nrcan.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            nrcan.get_map({"layers": "nrcan:wheeler", "crs": "EPSG:3978", "bbox": "0,0,1,1", "width": "512", "height": "512"})
        params = get.call_args[1]["params"]
        self.assertEqual((params["layers"], params["crs"], params["version"]), ("0", "EPSG:3978", "1.3.0"))

    def test_모르는_레이어는_묻지_않는다(self):
        with self.assertRaises(nrcan.NrcanError):
            nrcan.get_map({"layers": "nrcan:other"})

    def test_속성은_영어_열만_가장_잘게_가른_시대(self):
        props = {"UNIT": "lS*", "RXTP": "sedimentary rocks", "SUBRXTP": "undivided sedimentary rocks", "ERA": "Paleozoic",
                 "PERIOD": "Silurian", "EPOCH": " ", "GEOLPROV": "Hudson Bay Lowlands", "TPRCH": "roches sédimentaires",
                 "NAME": " ", "OBJECTID": "13439"}
        out = nrcan.friendly(props)
        self.assertEqual(out["지질시대"], "실루리아기")
        self.assertEqual(out["지질구"], "Hudson Bay Lowlands")
        self.assertNotIn("이름", out)
        self.assertNotIn("roches sédimentaires", out.values())
        self.assertEqual(nrcan.friendly(props, "en")["지질시대"], "Silurian")


class Ogs(SimpleTestCase):
    def test_누른_화소를_그_투영의_좌표로_identify(self):
        p = ogs.identify_params(WMS)
        self.assertEqual(p["sr"], "3978")
        self.assertEqual(p["layers"], "all:57")                      # WMS 3 = REST 57
        x, y = (float(v) for v in p["geometry"].split(","))
        self.assertAlmostEqual(x, 1000000 + 127.5 * 100000 / 256, places=3)      # 화소의 가운데
        self.assertAlmostEqual(y, -100000 - 127.5 * 100000 / 256, places=3)
        with self.assertRaises(ogs.OgsError):
            ogs.identify_params(dict(WMS, crs="EPSG:4326"))

    def test_속성(self):
        hit = {"results": [{"layerId": 57, "attributes": {
            "OBJECTID": "16919", "TYPE_P": "28c", "UNITNAME_P": " ", "ROCKTYPE_P": "Lapilli tuff, breccia",
            "STRAT_P": "Whitewater Group; Onaping Formation", "EON_P": "PROTEROZOIC (0.542 Ga to 2.50 Ga)",
            "ERA_P": "PALEOPROTEROZOIC (1.6 Ga to 2.5 Ga)", "PERIOD_P": " ", "PROVINCE_P": "SOUTHERN and SUPERIOR"}}]}
        with mock.patch("viewer.ogs.requests.get", return_value=response(hit)) as get:
            data = ogs.get_feature_info(WMS)
        self.assertTrue(get.call_args[0][0].endswith("/MapServer/identify"))
        props = ogs.friendly(data["features"][0]["properties"])
        self.assertEqual(props["지질시대"], "고원생대 (1.6 Ga to 2.5 Ga)")
        self.assertEqual((props["기호"], props["층서"]), ("28c", "Whitewater Group; Onaping Formation"))
        self.assertNotIn("이름", props)
        quaternary = ogs.friendly({"UNIT_NAME": "Glaciofluvial ice-contact deposits", "AGE": "Pleistocene",
                                   "MATERIAL": "gravel and sand"}, "en")
        self.assertEqual(quaternary, {"이름": "Glaciofluvial ice-contact deposits", "지질시대": "Pleistocene",
                                      "물질": "gravel and sand"})

    def test_상류의_오류(self):
        with mock.patch("viewer.ogs.requests.get", return_value=response({"error": {"message": "bad"}})):
            with self.assertRaises(ogs.OgsError):
                ogs.get_feature_info(WMS)


class Lambert(SimpleTestCase):
    def test_캐나다_람베르트_격자(self):
        self.assertEqual(tilegrid.forward(-95.0, 49.0, "EPSG:3978"), (0.0, 0.0))     # 원점
        x, y = tilegrid.forward(-81.0, 46.6, "EPSG:3978")
        lat, lon = crs.lcc_to_latlon(x, y, -95.0, 49.0, 77.0, lat0=49.0)
        self.assertAlmostEqual((lat, lon)[0], 46.6, places=6)
        box = tilegrid.projected_bbox((-95.16, 41.67, -74.32, 56.86), "EPSG:3978")
        self.assertLess(box[0], 0)
        self.assertGreater(box[2], 1_500_000)


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_캐나다_탭에_3978_로(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name in ("nrcan:wheeler", "ogs:3", "ogs:6"):
            group, layer = rows[name]
            self.assertEqual(group["region"], "canada", name)
            self.assertEqual(layer["projection"], "EPSG:3978", name)
        self.assertEqual(rows["nrcan:wheeler"][1]["upstream"], "nrcan")
        en = {l["name"]: l["title"] for g in views._catalog("en") for l in g["layers"]}
        self.assertEqual(en["ogs:3"], "Ontario bedrock (1:250k)")

    def test_미리_데우기는_3978_격자(self):
        from viewer.management.commands import prewarm
        plan = prewarm.plan_for("nrcan:wheeler", "nrcan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.grid.crs, "EPSG:3978")

    def test_북극_지질도는_북극해_탭에_3413_로(self):
        """wetherilli 414 — 북극 묶음에도 든다(map.js 의 REGIONS.arctic.includes). 넓으면 느려 처음 줌을 둔다"""
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["nrcan:arctic"]
        self.assertEqual((group["region"], layer["upstream"], layer["projection"]), ("arctic_ocean", "nrcan", "EPSG:3413"))
        self.assertEqual((layer["legend"], layer["legendUrl"], layer["minZoom"]), ("extent", "nrcan/legend/", 3))
        from viewer.management.commands import prewarm
        self.assertEqual(prewarm.plan_for("nrcan:arctic", "nrcan").grid.crs, "EPSG:3413")

    def test_3D_는_3857_로(self):
        self.assertIn("nrcan", views.MAP3D_WMS)
        self.assertIn("ogs", views.MAP3D_WMS)


class NrcanServices(SimpleTestCase):
    """같은 서버의 다른 서비스 — 편찬 지질도·핵심 광물·유망도 (wetherilli 250)"""

    def test_서비스마다_주소(self):
        with mock.patch("viewer.nrcan.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            nrcan.get_map({"layers": "nrcan:critical", "crs": "EPSG:3978", "bbox": "0,0,1,1", "width": "512", "height": "512"})
        self.assertTrue(get.call_args.args[0].endswith("/NRCan/critical_minerals_en/MapServer/WMSServer"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "0,1,2,3")
        with mock.patch("viewer.nrcan.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            nrcan.get_map({"layers": "nrcan:wheeler", "crs": "EPSG:3978", "bbox": "0,0,1,1", "width": "512", "height": "512"})
        self.assertIn("geological_map_canada_wheeler_en", get.call_args.args[0])

    def test_유망도_래스터는_누르지_않는다(self):
        with mock.patch("viewer.nrcan.requests.get") as get:
            self.assertEqual(nrcan.get_feature_info(dict(WMS, layers="nrcan:ree", query_layers="nrcan:ree")), {"features": []})
        get.assert_not_called()

    def test_편찬_지질도는_칸을_범례로_푼다(self):
        """CGMC(wetherilli 320) — REST identify 의 OBJECTID − 1 이 범례의 차례. 범례는 한 번만 받는다"""
        legend = response({"layers": [{"legend": [{"label": "mixed volcanic"}, {"label": "felsic volcanic"},
                                                  {"label": "intermediate intrusive"}]}]})
        hit = response({"results": [{"attributes": {"Pixel Value": "4", "OBJECTID": "3", "Count": "1"}}]})
        nodata = response({"results": [{"attributes": {"Pixel Value": "NoData"}}]})
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()), \
             mock.patch("viewer.nrcan.requests.get", side_effect=[hit, legend, hit, nodata]) as get:
            first = nrcan.get_feature_info(dict(WMS, layers="nrcan:cgmc", query_layers="nrcan:cgmc"))
            again = nrcan.get_feature_info(dict(WMS, layers="nrcan:cgmc", query_layers="nrcan:cgmc"))
            empty = nrcan.get_feature_info(dict(WMS, layers="nrcan:cgmc", query_layers="nrcan:cgmc"))
        self.assertEqual(first, again)
        self.assertEqual(nrcan.friendly(first["features"][0]["properties"]), {"암상": "intermediate intrusive"})
        self.assertEqual(empty, {"features": []})
        sent = get.call_args_list[0]
        self.assertTrue(sent.args[0].endswith("/rest/services/NRCan/cdn_geol_compil_en/MapServer/identify"))
        self.assertEqual(sent.kwargs["params"]["sr"], "3978")
        x, y = (float(v) for v in sent.kwargs["params"]["geometry"].split(","))
        self.assertAlmostEqual(x, 1000000 + 127.5 * 100000 / 256)
        self.assertAlmostEqual(y, -100000 - 127.5 * 100000 / 256)

    def test_핵심_광물(self):
        props = {"Operation Group": "Mines and other primary producing sites", "Property Name": "Beaver Brook",
                 "Operator Owners": "Hunan Nonferrous Metals Corporation Limited", "Province/Territory": "Newfoundland and Labrador",
                 "Commodities": "Antimony", "Development Stage": "Past producer", "Activity Status": "On hold / suspended",
                 "Website": "Not available/Pas disponible"}
        out = nrcan.friendly(props)
        self.assertEqual((out["이름"], out["광종"], out["개발 단계"]), ("Beaver Brook", "Antimony", "Past producer"))
        self.assertNotIn("누리집", out)


class NrcanArctic(SimpleTestCase):
    """북극 지질도 1:500만 — 같은 서버의 `international_polar_year_en`, 북극 탭의 3413 으로 곧장 (wetherilli 414).
    속성·통계 응답의 꼴은 2026-10-22 에 받아 본 그대로다"""

    PROPS = {"MAP_LABEL": "KQ2", "AGE_DESCRI": "Cretaceous and younger (145.5 - 0.0 Ma)", "EON": "Phanerozoic",
             "SETTING": "Sedimentary: undivided", "LITHOLOGY": "Sedimentary and/or volcanic rock: undivided",
             "METAMORPHI": "Not known", "DOMAIN_R_1": "Arctic-North Atlantic region",
             "DOMAIN_R_2": "Iceland, North Atlantic, East Greenland volcanic belt", "DOMAIN_R_3": "Oceanic basin",
             "SOURCE_LOC": "Greenland and adjacent offshore", "COMPILATIO": "Hamann et al., 2005", "IPY_CODE": "130010100",
             "COLOUR": "Spearmint 7"}

    def test_해저를_맨_밑에_3413_그대로(self):
        with mock.patch("viewer.nrcan.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            nrcan.get_map({"layers": "nrcan:arctic", "crs": "EPSG:3413", "bbox": "0,-2000000,1000000,-1000000",
                           "width": "256", "height": "256"})
        self.assertTrue(get.call_args.args[0].endswith("/NRCan/international_polar_year_en/MapServer/WMSServer"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "1,0,2,3")
        self.assertEqual(get.call_args[1]["params"]["crs"], "EPSG:3413")

    def test_속성은_시대만_옮긴다(self):
        out = nrcan.friendly(self.PROPS)
        self.assertEqual(out["기호"], "KQ2")
        self.assertEqual(out["지질시대"], "백악기 이후 (145.5–0.0 Ma)")
        self.assertEqual(out["지구조 구역"], "Arctic-North Atlantic region · Iceland, North Atlantic, East Greenland volcanic belt"
                                          " · Oceanic basin")
        self.assertNotIn("변성 정도", out)                     # "Not known" 은 적지 않는다
        self.assertEqual(nrcan.friendly(self.PROPS, "en")["지질시대"], "Cretaceous and younger (145.5 - 0.0 Ma)")

    def test_시대_괄호를_떼어_옮긴다(self):
        self.assertEqual(nrcan.arctic_age("middle and late Paleoproterozoic (Orosirian and Statherian) (2050 - 1600 Ma)"),
                         "고원생대 중기 및 후기 (오로세이라기 및 스타테로스기) (2050–1600 Ma)")
        self.assertEqual(nrcan.arctic_age("Mesoarchean and Neoarchean (3200 - 2500 Ma)"), "중시생대 및 신시생대 (3200–2500 Ma)")
        self.assertEqual(nrcan.arctic_age("something odd (12 - 3 Ma)"), "something odd (12–3 Ma)")

    def test_보는_범위의_범례(self):
        """네 레이어에 통계를 POST 로 묻고(고리가 길어 GET 은 404) 같은 단위는 넓이를 더한다. 색은 칠하기 규칙에서"""
        def stats(*rows):
            return response({"features": [{"attributes": dict(zip(("MAP_LABEL", "COLOUR", "AGE_DESCRI", "LITHOLOGY", "area"), r))}
                                          for r in rows]})
        sea = stats(("KQ4", "Spearmint 7", "Cretaceous and younger (145.5 - 0.0 Ma)", "Sandstone", 5.0),
                    ("m15", "143", "Archean and Paleoproterozoic (4000 - 1600 Ma)", "Undivided crystalline rocks", 2.0))
        land = stats(("m15", "143", "Archean and Paleoproterozoic (4000 - 1600 Ma)", "Undivided crystalline rocks", 7.0))
        empty = stats()
        renderer = lambda *pairs: response({"drawingInfo": {"renderer": {"uniqueValueInfos": [   # noqa: E731
            {"value": v, "symbol": {"color": c}} for v, c in pairs]}}})
        with override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()), \
             mock.patch("viewer.nrcan.requests.post", side_effect=[sea, empty, land, empty]) as post, \
             mock.patch("viewer.nrcan.requests.get", side_effect=[renderer(("Spearmint 7", [166, 255, 77, 255])),
                                                                  renderer(("143", [230, 153, 178, 255])),
                                                                  renderer(), renderer()]) as get:
            res = self.client.get("/GSM/nrcan/legend/", {"layer": "nrcan:arctic", "bbox": "-60,70,-40,80"})
            again = self.client.get("/GSM/nrcan/legend/", {"layer": "nrcan:arctic", "bbox": "-60,70,-40,80"})
        self.assertEqual(res.status_code, 200)
        rows = res.json()["rows"]
        self.assertEqual([r["symbol"] for r in rows], ["m15", "KQ4"])
        self.assertEqual(rows[0]["color"], "#e699b2")
        self.assertEqual(rows[1]["age"], "백악기 이후 (145.5–0.0 Ma)")
        self.assertEqual(again.json(), res.json())
        self.assertEqual(post.call_count, 4)                   # 두 번째는 캐시에서
        self.assertEqual(get.call_count, 4)
        sent = post.call_args_list[0]
        self.assertTrue(sent.args[0].endswith("/rest/services/NRCan/international_polar_year_en/MapServer/1/query"))
        ring = json.loads(sent.kwargs["data"]["geometry"])["rings"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertGreater(len(ring), 50)

    def test_범례는_북극_지질도만(self):
        self.assertEqual(self.client.get("/GSM/nrcan/legend/", {"layer": "nrcan:wheeler", "bbox": "0,0,1,1"}).status_code, 400)
