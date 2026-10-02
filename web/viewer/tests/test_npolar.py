"""노르웨이 극지연구소(NPI) — 스발바르·드로닝모드랜드의 문 (devlog 021).

NPI 를 실제로 부르지 않는다. 응답의 꼴은 2026-09-27 에 받아 본 그대로다 —
`identify` 는 열의 별칭을 이름으로 주고 빈 값을 `"Null"`·`" "` 로 준다.
"""
import base64
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import arcpoints, i18n, npolar, views
from viewer.models import Layer, LayerGroup

#: 롱이어비엔 둘레의 512 픽셀 타일 하나 (EPSG:3413)
TILE = {"layers": "npolar:svalbard_units", "crs": "EPSG:3413",
        "bbox": "1100000,-640000,1120000,-620000", "width": "512", "height": "512"}

#: identify 가 준 스발바르 1:25만 지질 단위 하나 (2026-09-27, 줄였다)
UNIT = {"Shape": "Polygon", "GEO_CODE": "1331", "NP2": "52", "NAME": "Basilika Formation",
        "NAVN": "Basilikaformasjonen", "TYPE": "lithostratigraphic unit",
        "SUPERIOR_U": "Van Mijenfjorden Group", "MAIN_LITHO": "shale, mudstone, siltstone",
        "AGE_PERIOD": "late Paleocene", "AGE_BASE": " ", "AGE_TOP": "Null",
        "DATING_MET": "fossils, palynology", "ACCURACY": "generalized from 1:100 000 scale",
        "FID": "13", "Shape_Area": "213113564,290348", "colourR": "255"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content,
                     url="https://geodata.npolar.no/…", json=lambda: body)


def png(color=(255, 0, 0, 255)):
    out = io.BytesIO()
    Image.new("RGBA", (20, 20), color).save(out, "PNG")
    return out.getvalue()


class Export(SimpleTestCase):
    """WMS `GetMap` 꼴 → MapServer `export`."""

    def test_지역의_투영으로_그대로_묻는다(self):
        url, sent = npolar.export_params(TILE)
        self.assertTrue(url.endswith("/Temadata/G_Geologi_Svalbard_S250_S750/MapServer/export"))
        self.assertEqual((sent["bboxSR"], sent["imageSR"]), (3413, 3413))
        self.assertEqual(sent["size"], "512,512")
        self.assertEqual(sent["layers"], "show:10,24")      # 1:75만·1:25만을 짝으로
        self.assertEqual(sent["f"], "image")

    def test_종이_지질도는_256_색으로(self):
        _, sent = npolar.export_params(dict(TILE, layers="npolar:svalbard_paper"))
        self.assertEqual(sent["format"], "png8")

    def test_모르는_투영은_묻지_않는다(self):
        with self.assertRaises(npolar.NpolarError):
            npolar.export_params(dict(TILE, crs="EPSG:25833"))

    def test_모르는_레이어도(self):
        with self.assertRaises(npolar.NpolarError):
            npolar.export_params(dict(TILE, layers="L_50K_Geology_Map"))

    def test_너무_큰_그림은_묻지_않는다(self):
        with self.assertRaises(npolar.NpolarError):
            npolar.export_params(dict(TILE, width="5000"))

    def test_그림이_아니면_오류(self):
        with mock.patch.object(npolar.requests, "get", return_value=response({"error": {}})), \
                mock.patch.object(npolar.usage, "record"):
            with self.assertRaises(npolar.NpolarError):
                npolar.get_map(TILE)

    def test_부르는_이를_밝힌다(self):
        with mock.patch.object(npolar.requests, "get",
                               return_value=response(content=b"\x89PNG", ctype="image/png")) as get, \
                mock.patch.object(npolar.usage, "record"):
            content, ctype = npolar.get_map(TILE)
        self.assertEqual(ctype, "image/png")
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], "GSM/0.1")


class Identify(SimpleTestCase):
    def test_누른_픽셀의_한가운데를_짚는다(self):
        _, sent = npolar.identify_params(dict(TILE, i="0", j="511"))
        x, y = (float(v) for v in sent["geometry"].split(","))
        self.assertAlmostEqual(x, 1100000 + 0.5 * 20000 / 512)
        self.assertAlmostEqual(y, -640000 + 0.5 * 20000 / 512)
        self.assertEqual(sent["layers"], "visible:10,24")   # 그 축척에서 보이는 것만
        self.assertEqual(sent["imageDisplay"], "512,512,96")

    def test_옛_WMS_의_X_Y_도_받는다(self):
        _, sent = npolar.identify_params(dict(TILE, x="256", y="256"))
        self.assertIn(",", sent["geometry"])

    def test_속성이_없는_레이어는_묻지_않는다(self):
        with self.assertRaises(npolar.NpolarError):
            npolar.identify_params(dict(TILE, layers="npolar:svalbard_paper", i="1", j="1"))

    def test_결과를_features_로(self):
        body = {"results": [{"layerId": 24, "layerName": "Geological units", "attributes": UNIT}]}
        with mock.patch.object(npolar.requests, "get", return_value=response(body)), \
                mock.patch.object(npolar.usage, "record"):
            data = npolar.get_feature_info(dict(TILE, i="10", j="10"))
        self.assertEqual(data["features"][0]["id"], "24.13")
        self.assertEqual(data["features"][0]["properties"]["NAME"], "Basilika Formation")


class Friendly(SimpleTestCase):
    def test_이름을_바꾸고_빈_것과_안쪽_열은_뺀다(self):
        props = npolar.friendly(UNIT)
        self.assertEqual(props["이름"], "Basilika Formation")
        self.assertEqual(props["노르웨이어 이름"], "Basilikaformasjonen")   # 옮기지 않는다
        self.assertNotIn("시대 하한", props)                              # " "
        self.assertNotIn("시대 상한", props)                              # "Null"
        self.assertNotIn("Shape_Area", props)
        self.assertEqual(list(props)[:2], ["이름", "노르웨이어 이름"])       # 표의 차례

    def test_한국어판은_지질시대를_옮긴다(self):
        self.assertEqual(npolar.friendly(UNIT)["지질시대"], "팔레오세 후기")
        self.assertEqual(npolar.friendly(UNIT, "en")["지질시대"], "late Paleocene")

    def test_빙하_전면은_날짜와_길이를_읽기_좋게(self):
        # 2026-09-30 에 크로네브린을 누르고 받은 그대로 — 소수점이 쉼표다 (wetherilli 094)
        props = npolar.friendly({"OBJECTID": "82", "Ident": "15511,2", "Name": "Kronebreen", "Date": "20230903",
                                 "Source": "T33XVH_20230903T133731_B08", "Length_km": "3,595676", "Year": "2023"})
        self.assertEqual(props, {"이름": "Kronebreen", "관측일": "2023-09-03",
                                 "원자료 (영상)": "T33XVH_20230903T133731_B08", "전면 길이 (km)": "3.60"})

    def test_주소는_링크로(self):
        props = npolar.friendly({"URL": "http://nhm2.uio.no/norges/litho/svalbard/gips.htm#cp50",
                                 "Stratigraphic Unit": "Cadellfjellet Member"})
        self.assertEqual(props["층서 사전"]["links"][0]["label"], "열기")
        self.assertEqual(props["층서명"], "Cadellfjellet Member")
        self.assertNotIn("층서 사전", npolar.friendly({"URL": "javascript:alert(1)"}))

    def test_팝업_이름은_모두_PROP_EN_에(self):
        labels = set(npolar.FRIENDLY.values())
        for spec in npolar.POINTS.values():
            labels |= set(arcpoints.labels(spec).values())
        self.assertEqual(sorted(label for label in labels if label not in i18n.PROP_EN), [])


class AgeKo(SimpleTestCase):
    """영문 ICS 명칭 → 한국어. 모르는 낱말이 섞이면 원문 그대로 (`i18n.age_ko`)."""

    def test_옮긴다(self):
        cases = {
            "late Paleocene": "팔레오세 후기",
            "Early Cretaceous": "백악기 전기",
            "Carboniferous - Permian": "석탄기~페름기",
            "Early - Middle Triassic": "트라이아스기 전기~중기",
            "Early-Middle Ordovician": "오르도비스기 전기~중기",
            "Late Triassic - Middle Jurassic": "트라이아스기 후기~쥐라기 중기",
            "Late Devonian or Early Carboniferous": "데본기 후기 또는 석탄기 전기",
            "Tonian and/or Cryogenian": "토노스기 및/또는 크리오스진기",
            "Bashkirian": "바시키르절",
            "Moscovian - early Kasimovian": "모스코바절~카시모프절 전기",
            "Neoproterozoic (?)": "신원생대(?)",
            "Eocene - ? Oligocene": "에오세~올리고세(?)",
            "Palaeoproterozoic": "고원생대",
            "Early Palaeozoic ?": "고생대 전기(?)",
        }
        for en, ko in cases.items():
            self.assertEqual(i18n.age_ko(en), ko, en)

    def test_모르는_낱말이_있으면_원문(self):
        for text in ("Ordovician, 450-475 my",
                     "Caledonian (?)", "Mesoproterozoic or earliest Neoproterozoic",
                     "Late Triasic - Middle Jurassic"):
            self.assertEqual(i18n.age_ko(text), text)

    def test_빈_값은_그대로(self):
        self.assertEqual(i18n.age_ko(""), "")
        self.assertIsNone(i18n.age_ko(None))


class Legend(SimpleTestCase):
    def test_칸을_이어_그림_한_장으로(self):
        body = {"layers": [
            {"layerId": 24, "legend": [
                {"label": "1331, Basilika Formation", "imageData": base64.b64encode(png()).decode()},
                {"label": "1332, Firkanten Formation", "imageData": "깨진 그림"}]},
            {"layerId": 10, "legend": [{"label": "안 그린다", "imageData": ""}]}]}
        with mock.patch.object(npolar.requests, "get", return_value=response(body)), \
                mock.patch.object(npolar.usage, "record"):
            content, ctype = npolar.get_legend("npolar:svalbard_units")
        image = Image.open(io.BytesIO(content))
        self.assertEqual(ctype, "image/png")
        self.assertEqual(image.height, npolar.ROW * 2 + npolar.PAD * 2)   # 24 의 두 칸만

    def test_범례가_없는_레이어(self):
        with self.assertRaises(npolar.NpolarError):
            npolar.get_legend("npolar:svalbard_paper")


class Points(SimpleTestCase):
    def feature(self, oid, **props):
        base = {"sampleName": "NP03939", "lithology": "Migmatite", "collectedYear": 2019,
                "rockArchive": "https://data.npolar.no/geology/sample/97a1", "image": "ftp://x",
                "ObjectId": oid}
        base.update(props)
        return {"type": "Feature", "id": oid, "geometry": {"type": "Point", "coordinates": [12.585, 78.957]},
                "properties": base}

    def test_장을_넘기며_끝까지_받는다(self):
        full = {"type": "FeatureCollection", "features": [self.feature(i) for i in range(npolar.PAGE)]}
        last = {"type": "FeatureCollection", "features": [self.feature(npolar.PAGE)]}
        with mock.patch.object(npolar.requests, "get", side_effect=[response(full), response(last)]) as get, \
                mock.patch.object(npolar.usage, "record"):
            rows = npolar.fetch("npolar:rock_archive", pause=0)
        self.assertEqual(len(rows), npolar.PAGE + 1)
        self.assertEqual(get.call_args.kwargs["params"]["resultOffset"], npolar.PAGE)
        self.assertIn("services3.arcgis.com", get.call_args.args[0])
        row = rows[0]
        self.assertEqual(row["properties"]["year"], "2019")
        self.assertNotIn("photo", row["properties"])                        # ftp 는 받지 않는다

    def test_장을_못_넘기는_레이어는_한_번에(self):
        body = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": 0, "geometry": {"type": "Point", "coordinates": [2.56, -72.01, 0]},
             "properties": {"FID": 0, "Locality": "SE 1", "Samples": " ", "Expedition": "NPI 2022"}}]}
        with mock.patch.object(npolar.requests, "get", return_value=response(body)) as get, \
                mock.patch.object(npolar.usage, "record"):
            rows = npolar.fetch("npolar:dml_sites")
        self.assertNotIn("resultOffset", get.call_args.kwargs["params"])
        self.assertEqual(rows[0]["properties"], {"site": "SE 1", "exp": "NPI 2022"})

    def test_200_에_실린_오류도_오류다(self):
        with mock.patch.object(npolar.requests, "get",
                               return_value=response({"error": {"message": "Pagination is not supported."}})), \
                mock.patch.object(npolar.usage, "record"):
            with self.assertRaises(npolar.NpolarError):
                npolar.fetch("npolar:dml_geochron", pause=0)

    def test_링크_열을_알린다(self):
        data = json.loads(npolar.body("npolar:rock_archive", b"[]"))
        self.assertEqual(data["links"], ["link", "photo"])
        self.assertEqual(data["style"], "rock")


class Places(SimpleTestCase):
    FEATURES = [
        {"geometry": {"coordinates": [15.63153, 78.22223]}, "properties": {"name": "Longyearbyen", "area": "Svalbard"}},
        {"geometry": {"coordinates": [15.65631, 78.14909]}, "properties": {"name": "Longyeardal", "area": "Svalbard"}},
        {"geometry": {"coordinates": [12.0253, 79.026]}, "properties": {"name": "Nordvågvatnet", "area": "Svalbard"}},
        {"geometry": {"coordinates": [16.0, 78.0]}, "properties": {"name": "Gamle Longyearbyen", "area": "Svalbard"}},
    ]

    def test_같은_이름_앞이_같은_것_들어_있는_것_차례(self):
        got = [r["title"] for r in npolar.match_places(self.FEATURES, "longyearbyen")]
        self.assertEqual(got, ["Longyearbyen", "Gamle Longyearbyen"])

    def test_노르웨이_글자를_접어서_찾는다(self):
        got = npolar.match_places(self.FEATURES, "nordvag")
        self.assertEqual(got[0]["title"], "Nordvågvatnet")
        self.assertEqual((got[0]["lat"], got[0]["lon"]), (79.026, 12.0253))


class View(TestCase):
    def setUp(self):
        views._place_index.clear()          # 지명 색인은 메모리에 남는다 (wetherilli 096)
        self.addCleanup(views._place_index.clear)
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-npi-"),
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="스발바르 지질 (NPI)", region="svalbard")
        for name in ("npolar:svalbard_units", "npolar:svalbard_paper", "npolar:rock_archive"):
            Layer.objects.create(name=name, title=name, group=g, upstream="npolar")

    def test_카탈로그(self):
        rows = {l["name"]: l for l in views._catalog()[0]["layers"]}
        self.assertEqual(rows["npolar:svalbard_units"]["projection"], "EPSG:3413")
        self.assertTrue(rows["npolar:svalbard_units"]["queryable"])
        self.assertFalse(rows["npolar:svalbard_paper"]["queryable"])      # 그림이라 속성이 없다
        self.assertEqual(rows["npolar:rock_archive"]["kind"], "points")
        self.assertEqual(rows["npolar:rock_archive"]["license"], "CC BY 4.0")
        self.assertIn("Norsk Polarinstitutt", rows["npolar:svalbard_units"]["attribution"])

    def test_타일은_한_번만_받는다(self):
        query = {k.upper(): v for k, v in TILE.items()}
        with mock.patch.object(npolar, "get_map", return_value=(b"\x89PNG", "image/png")) as up:
            r1 = self.client.get("/GSM/wms/", query)
            r2 = self.client.get("/GSM/wms/", query)
        self.assertEqual(up.call_count, 1)
        self.assertEqual((r1["X-GSM-Cache"], r2["X-GSM-Cache"]), ("miss", "hit"))

    def test_속성은_팝업_꼴로(self):
        data = {"features": [{"id": "24.13", "properties": UNIT}]}
        query = dict({k.upper(): v for k, v in TILE.items()}, QUERY_LAYERS=TILE["layers"], I="3", J="4")
        with mock.patch.object(npolar, "get_feature_info", return_value=data):
            ko = self.client.get("/GSM/featureinfo/", query).json()
            en = self.client.get("/GSM/featureinfo/", dict(query, lang="en"),
                                 HTTP_COOKIE="gsm_lang=en").json()
        self.assertEqual(ko["features"][0]["props"]["지질시대"], "팔레오세 후기")
        self.assertEqual(en["features"][0]["props"]["Geologic age"], "late Paleocene")
        self.assertEqual(en["features"][0]["props"]["Norwegian name"], "Basilikaformasjonen")

    def test_점_레이어(self):
        rows = [arcpoints.compact({"id": 1, "geometry": {"type": "Point", "coordinates": [12.5, 78.9]},
                                   "properties": {"sampleName": "NP1"}},
                                  npolar.POINTS["npolar:rock_archive"]["fields"])]
        with mock.patch.object(npolar, "fetch", return_value=rows) as up:
            r = self.client.get("/GSM/points/", {"layer": "npolar:rock_archive"})
            self.client.get("/GSM/points/", {"layer": "npolar:rock_archive"})
        self.assertEqual(up.call_count, 1)
        data = json.loads(r.content)
        self.assertEqual(data["features"][0]["properties"]["no"], "NP1")
        self.assertEqual(data["labels"]["no"], "시료 번호")

    def test_지명은_통째로_내주지_않는다(self):
        r = self.client.get("/GSM/points/", {"layer": views.PLACE_NAMES})
        self.assertEqual(r.status_code, 404)

    def test_지명_찾기(self):
        rows = json.dumps(Places.FEATURES).encode()
        with mock.patch.object(views, "point_features", return_value=rows):
            data = self.client.get("/GSM/placenames/", {"q": "longyearb"}).json()
        self.assertEqual(data["results"][0]["title"], "Longyearbyen")
        self.assertEqual(data["results"][0]["kind"], "name")

    def test_그린란드는_옛_철자와_덴마크어로도_찾는다(self):
        # 그린란드 지명(Nunat Aqqi)을 받은 꼴 — 이름 열이 넷이다 (wetherilli 096)
        rows = json.dumps([
            {"geometry": {"coordinates": [-51.736, 64.176]},
             "properties": {"name": "Nuuk", "da": "Godthåb", "kind": "By", "mun": "Sermersooq"}},
            {"geometry": {"coordinates": [-53.0, 70.0]},
             "properties": {"name": "Qeqertarsuaq", "old": "ĸeĸertarssuaĸ", "kind": "Ø"}},
        ]).encode()
        with mock.patch.object(views, "point_features", return_value=rows) as got:
            by_danish = self.client.get("/GSM/placenames/", {"q": "godthab", "region": "greenland"}).json()
            by_old = self.client.get("/GSM/placenames/", {"q": "qeqertarssuaq", "region": "greenland"}).json()
        self.assertEqual(got.call_args.args[0], "grportal:place_names")
        self.assertEqual(by_danish["results"][0]["title"], "Nuuk (Godthåb)")      # 화면은 괄호를 떼고 간다
        self.assertEqual(by_danish["results"][0]["sub"], "Godthåb · By · Sermersooq")
        self.assertEqual(by_old["results"][0]["title"], "Qeqertarsuaq (ĸeĸertarssuaĸ)")

    def test_북극_묶음은_품은_지역을_다_뒤지고_지명이_없는_지역은_건너뛴다(self):
        rows = json.dumps(Places.FEATURES).encode()
        with mock.patch.object(views, "point_features", return_value=rows) as got:
            self.client.get("/GSM/placenames/", {"q": "longyear", "region": "greenland,svalbard,jan_mayen,arctic_ocean"})
        self.assertEqual(sorted(c.args[0] for c in got.call_args_list),
                         ["grportal:place_names", "npolar:place_names"])

    def test_지명_색인은_메모리에_둔다(self):
        rows = json.dumps(Places.FEATURES).encode()
        with mock.patch.object(views, "point_features", return_value=rows) as got:
            self.client.get("/GSM/placenames/", {"q": "longyear"})
            self.client.get("/GSM/placenames/", {"q": "nordvag"})
        self.assertEqual(got.call_count, 1)

    def test_드로닝모드랜드_지명도_통째로_내주지_않는다(self):
        self.assertEqual(self.client.get("/GSM/points/", {"layer": "npolar:dml_place_names"}).status_code, 404)
        self.assertEqual(self.client.get("/GSM/points/", {"layer": "grportal:place_names"}).status_code, 404)

    def test_지명을_못_받으면_502(self):
        with mock.patch.object(npolar, "fetch", side_effect=npolar.NpolarError("x")):
            r = self.client.get("/GSM/placenames/", {"q": "longyear"})
        self.assertEqual(r.status_code, 502)


class Seed(TestCase):
    def test_씨앗과_문이_짝이_맞고_영어가_있다(self):
        for path in (views.settings.NPOLAR_CATALOG_SEED, views.settings.NPOLAR_DML_CATALOG_SEED):
            seed = json.loads(path.read_text(encoding="utf-8"))
            for row in seed["레이어"]:
                self.assertTrue(npolar.knows(row["name"]) or npolar.knows_points(row["name"]), row["name"])
                self.assertIn(row["name"], i18n.LAYER_EN)
            for group in seed["레이어군순서"]:
                self.assertIn(group, i18n.GROUP_EN)

    def test_스발바르와_남극에_넣는다(self):
        call_command("seed_catalog", stdout=mock.Mock())
        units = Layer.objects.get(name="npolar:svalbard_units")
        self.assertEqual((units.upstream, units.group.region), ("npolar", "svalbard"))
        self.assertIsNotNone(units.verified_at)                             # 한 장씩 받아 보고 넣었다
        dml = Layer.objects.get(name="npolar:dml_geochron")
        self.assertEqual(dml.group.region, "antarctica")
        # 드로닝모드랜드는 GeoMAP 뒤에 선다
        geomap = LayerGroup.objects.get(name="GeoMAP 지질도", region="antarctica")
        self.assertGreater(dml.group.order, geomap.order)


class Sheets(SimpleTestCase):
    """스발바르 도폭 스캔 (P01 6 단계) — 도폭 하나만 그리기, 도폭 경계 면."""

    SERVICE = {"layers": [
        {"id": 1, "name": "Kartbilder", "parentLayerId": -1},
        {"id": 2, "name": "A4G-Vasahalvøya_100_2007.tif", "parentLayerId": 1},
        {"id": 34, "name": "FG23G-NordaustlandetNE_200_2014.tif", "parentLayerId": 1},
        {"id": 35, "name": "FG23G-NordaustlandetNE_200_2014Storøya.tif", "parentLayerId": 1},
        {"id": 80, "name": "Papirkart_Med_Tegnforklaring", "parentLayerId": -1},
        {"id": 81, "name": "A4G-Vasahalvøya_med_tegnforklaring.tif", "parentLayerId": 80},
    ]}

    def setUp(self):
        npolar._sheet_memo.clear()

    def tearDown(self):
        npolar._sheet_memo.clear()

    def _table(self):
        from unittest import mock
        reply = mock.Mock(status_code=200)
        reply.json.return_value = self.SERVICE
        with mock.patch("viewer.npolar._get", return_value=reply):
            return npolar.sheet_rasters()

    def test_번호로_래스터를_모은다(self):
        self.assertEqual(self._table(), {"A4G": [2], "FG23G": [34, 35]})    # 범례 붙은 종이(80)는 뺀다

    def test_도폭_하나만_그린다(self):
        self._table()
        url, sent = npolar.export_params({"layers": "npolar:svalbard_sheets@FG23G", "crs": "EPSG:3413",
                                          "bbox": "0,-1200000,300000,-900000",
                                          "width": "512", "height": "512"})
        self.assertEqual(sent["layers"], "show:34,35")
        self.assertIn("G_Geologi_Kartblad", url)

    def test_모르는_도폭은_멈춘다(self):
        self._table()
        for name in ("npolar:svalbard_sheets@C6G", "npolar:svalbard_sheets@1;DROP"):
            with self.assertRaises(npolar.NpolarError):
                npolar.sheet_spec(name)

    def test_면을_받는다(self):
        from viewer import arcpoints
        feature = {"type": "Feature", "id": 3, "properties": {"KartNR": "A4G"},
                   "geometry": {"type": "Polygon", "coordinates": [[[10.123456789, 79.1], [11, 79.1],
                                                                    [11, 79.5], [10.123456789, 79.1]]]}}
        fields = {"code": arcpoints.field("KartNR", "도폭 번호")}
        self.assertIsNone(arcpoints.compact(feature, fields))                 # 점 레이어는 면을 버린다
        row = arcpoints.compact(feature, fields, areal=True)
        self.assertEqual(row["geometry"]["type"], "Polygon")
        self.assertEqual(row["geometry"]["coordinates"][0][0], [10.12346, 79.1])
        self.assertEqual(row["properties"], {"code": "A4G"})

    def test_사람_이메일_열은_받지_않는다(self):
        spec = npolar.POINTS["npolar:svalbard_sheet_index"]
        self.assertFalse(any("Folk" in f["from"] for f in spec["fields"].values()))
