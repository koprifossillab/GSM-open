"""NASA Trek 판 목록 — 달·화성이 함께 쓰는 씨앗 (devlog 060).

Trek 을 실제로 부르지 않는다. `WMTSCapabilities.xml` 의 꼴은 2026-09-30 에 받아 본 그대로다 — 줌 0 을 `0` 으로
적는 판과 `1` 로 적는 판(Apollo 15 메트릭 카메라 신뢰도)이 있다.
"""
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import trek


def capabilities(levels, fmt="image/png"):
    """`levels` — `[(식별자, 가로, 세로)]`."""
    matrices = "".join(
        f"<TileMatrix><ows:Identifier>{i}</ows:Identifier><MatrixWidth>{w}.0</MatrixWidth>"
        f"<MatrixHeight>{h}.0</MatrixHeight></TileMatrix>" for i, w, h in levels)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1">'
        f"<Contents><Layer><Format>{fmt}</Format></Layer><TileMatrixSet>{matrices}"
        # 상류는 옛 격자를 주석으로 남겨 둔다 — 세지 않는다
        "<!--<TileMatrix><ows:Identifier>0</ows:Identifier><MatrixWidth>3</MatrixWidth>"
        "<MatrixHeight>2</MatrixHeight></TileMatrix>-->"
        "</TileMatrixSet></Contents></Capabilities>").encode()


def item(label, **kw):
    out = {"id": label, "title": label.replace("_", " "), "cat": "Mineralogy", "cat2": "Abundance",
           "mission": "Lunar Prospector", "instrument": "Gamma Ray Spectrometer", "coverage": "Global",
           "bbox": [-180.0, -90.0, 180.0, 90.0]}
    out.update(kw)
    return out


class Wmts(SimpleTestCase):
    def test_줌_끝과_포맷(self):
        xml = capabilities([(0, 2, 1), (1, 4, 2), (2, 8, 4)])
        self.assertEqual(trek.parse_wmts(xml), {"ext": "png", "max": 2, "z0": 0})

    def test_줌_0_을_1_로_적는_판(self):
        xml = capabilities([(1, 2, 1), (2, 4, 2), (3, 8, 4)])
        self.assertEqual(trek.parse_wmts(xml), {"ext": "png", "max": 2, "z0": 1})

    def test_jpeg(self):
        self.assertEqual(trek.parse_wmts(capabilities([(0, 2, 1)], "image/jpeg"))["ext"], "jpg")

    def test_경위도_격자가_아니면_없다(self):
        self.assertIsNone(trek.parse_wmts(capabilities([(0, 1, 1), (1, 2, 2)])))
        self.assertIsNone(trek.parse_wmts(b"<html>not xml"))

    def test_404_는_타일이_없는_판(self):
        r = mock.Mock(status_code=404, content=b"", url="…")
        with mock.patch("viewer.trek.requests.get", return_value=r):
            self.assertIsNone(trek.wmts_info("mars", "FanSurvey_2005_2008_clon0"))

    def test_타일_한_장은_범위_가운데의_줌_0(self):
        ok = mock.Mock(status_code=200, url="…", content=b"\x89PNG", headers={"content-type": "image/png"})
        with mock.patch("viewer.trek.requests.get", return_value=ok) as get:
            self.assertTrue(trek.tile_exists("mars", "JEZ", {"ext": "jpg", "z0": 1}, [77.2, 18.3, 77.6, 18.7]))
        self.assertEqual(get.call_args[0][0],
                         "https://trek.nasa.gov/tiles/Mars/EQ/JEZ/1.0.0/default/default028mm/1/0/1.jpg")
        gone = mock.Mock(status_code=404, url="…", content=b"", headers={"content-type": "text/html"})
        with mock.patch("viewer.trek.requests.get", return_value=gone) as get:
            self.assertFalse(trek.tile_exists("moon", "X", {"ext": "png", "z0": 0}, None))
        self.assertEqual([c[0][0][-18:] for c in get.call_args_list], ["default028mm/0/0/1.png"[-18:], "default028mm/0/0/0.png"[-18:]])
        # 가운데 쪽이 404 여도 다른 쪽에 있으면 있는 판이다 — 범위가 망가진 화성 CTX 11S289E
        with mock.patch("viewer.trek.requests.get", side_effect=[gone, ok]):
            self.assertTrue(trek.tile_exists("mars", "CTX", {"ext": "png", "z0": 0}, [-180.0, -90.0, 219.0, 90.0]))

    def test_타일_뿌리는_몸을_따른다(self):
        self.assertEqual(trek.tiles_root("moon"), "https://trek.nasa.gov/tiles/Moon/EQ")
        self.assertEqual(trek.tiles_root("mars"), "https://trek.nasa.gov/tiles/Mars/EQ")


class Hide(SimpleTestCase):
    """처음 들어올 때 숨길 판 — 착륙 공학용, 회색 짝, 이미 쓰는 것."""

    def test_과학_판은_보인다(self):
        self.assertFalse(trek.hidden_by_default("moon", item("LP_GRS_Th_Clr_Global_2ppd")))

    def test_숨기는_것(self):
        self.assertTrue(trek.hidden_by_default("moon", item("a", cat="Hazard")))
        self.assertTrue(trek.hidden_by_default("moon", item("b", cat="Topography", cat2="Confidence")))
        self.assertTrue(trek.hidden_by_default("moon", item("c", title="Kaguya LGM2011 Freeair Gravity, Greyscale")))
        self.assertTrue(trek.hidden_by_default("moon", item("Kaguya_TCortho_Mosaic_Global_4096ppd")))
        self.assertTrue(trek.hidden_by_default("mars", item("Mars_Viking_MDIM21_ClrMosaic_global_232m")))


@override_settings()
class Seed(TestCase):
    """`fetch_trek_catalog` — 사람이 손질한 칸은 지키고, 한 번 물은 판은 다시 묻지 않는다."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="gsm-trek-seed-"))
        (self.repo / "data").mkdir()
        patch = override_settings(REPO_DIR=self.repo)
        patch.enable()
        self.addCleanup(patch.disable)
        self.items = [item(f"layer_{i}") for i in range(120)]
        self.items.append(item("regional", coverage="Regional", bbox=[23.4, 0.1, 23.5, 1.1]))
        self.items.append(item("nowmts", cat="Landforms"))

    twins = {}

    def run_command(self, **kw):
        def wmts(body, label):
            return None if label == "nowmts" else {"ext": "png", "max": 5, "z0": 0}

        def polar_wmts(body, name, pole):
            return {"ext": "png", "max": 5, "box": [-931135, -931138, 931165, 931162]} if name == "layer_0_SP" else None
        with mock.patch("viewer.trek.catalog_items", return_value=self.items), \
                mock.patch("viewer.trek.wmts_info", side_effect=wmts) as probe, \
                mock.patch("viewer.trek.tile_exists", side_effect=lambda body, label, info, bbox, delay: label != "notiles"), \
                mock.patch("viewer.trek.find_mapserver",
                           side_effect=lambda body, uuid, label: "trekarcgis/rest/services/X/MapServer"
                           if label == "notiles" else ""), \
                mock.patch("viewer.trek.polar_twins", return_value=self.twins), \
                mock.patch("viewer.trek.polar_wmts_info", side_effect=polar_wmts) as self.polar_probe, \
                mock.patch("viewer.management.commands.fetch_trek_catalog.time.sleep"), \
                mock.patch("viewer.trek.time.sleep"):
            call_command("fetch_trek_catalog", "--body", "moon", stdout=StringIO(), stderr=StringIO(), **kw)
        return probe.call_count

    def seed(self):
        return {e["id"]: e for e in trek.load_catalog("moon")}

    def test_처음에는_모두_묻는다(self):
        self.assertEqual(self.run_command(), len(self.items))
        seed = self.seed()
        self.assertEqual(seed["layer_0"]["kind"], "tile")
        self.assertIsNone(seed["nowmts"]["kind"])

    def test_Capabilities_만_있고_타일이_없으면_MapServer(self):
        """화성 사구 지대·Hynek 골짜기망 — Capabilities 는 200, 타일은 404, MapServer 만 있다 (wetherilli 090)."""
        self.items.append(item("notiles", cat="Landforms"))
        self.run_command()
        seed = self.seed()
        self.assertEqual((seed["notiles"]["kind"], seed["notiles"]["ms"]), ("map", "trekarcgis/rest/services/X/MapServer"))
        self.assertEqual(seed["layer_0"]["kind"], "tile")

    def test_손질한_칸은_지킨다(self):
        self.run_command()
        path = trek.catalog_file("moon")
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in data["layers"]:
            if e["id"] == "layer_0":
                e["ko"], e["hide"] = "토륨 함량", True
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.run_command(), 0)                    # 다시 묻지 않는다
        self.assertEqual((self.seed()["layer_0"]["ko"], self.seed()["layer_0"]["hide"]), ("토륨 함량", True))

    def test_상류에서_사라진_판은_지운다(self):
        self.run_command()
        self.items.pop(0)
        self.run_command()
        self.assertNotIn("layer_0", self.seed())

    def test_화면에_내리는_목록(self):
        self.run_command()
        out = trek.client_catalog("moon")
        self.assertEqual(out["root"], "https://trek.nasa.gov/tiles/Moon/EQ")
        layers = {l["id"]: l for g in out["groups"] for l in g["layers"]}
        self.assertNotIn("nowmts", layers)                         # 타일이 없는 판은 내리지 않는다
        self.assertIsNone(layers["layer_0"]["bbox"])               # 몸 전체를 덮으면 거르지 않는다
        self.assertEqual(layers["regional"]["bbox"], [23.4, 0.1, 23.5, 1.1])
        self.assertEqual(out["groups"][0]["ko"], "광물·원소")
        self.assertTrue(layers["layer_0"]["legend"])                # 값을 칠한 갈래에는 범례 그림이 있다
        self.assertEqual(out["legend"], "https://trek.nasa.gov/moon/TrekWS/rest/cat/legend/stream?label=")

    def test_같은_자료를_다르게_그린_판은_우리_레이어를_가리킨다(self):
        self.items.append(item("Unified_Geologic_Map_of_the_Moon_RASTER", cat="Geology", cat2="Geologic Map"))
        self.run_command()
        layers = {l["id"]: l for g in trek.client_catalog("moon")["groups"] for l in g["layers"]}
        self.assertEqual(layers["Unified_Geologic_Map_of_the_Moon_RASTER"]["same"], "units")
        self.assertEqual(layers["layer_0"]["same"], "")

    def test_극지_짝(self):
        """극 WMTS 가 있으면 타일, 없고 MapServer 만 있으면 우리 문이 굽는 것 (wetherilli 085)."""
        self.twins = {"layer_0": {"s": ("trekarcgis3", "layer_0_SP", "ImageServer")},
                      "regional": {"s": ("trekarcgis3", "regional_SP", "MapServer"),
                                   "n": ("trekarcgis2", "regional_NP", "ImageServer")}}
        self.run_command()
        seed = self.seed()
        self.assertEqual(seed["layer_0"]["polar"], {"s": {"kind": "tile", "name": "layer_0_SP", "ext": "png", "max": 5,
                                                          "box": [-931135, -931138, 931165, 931162]}})
        self.assertEqual(seed["regional"]["polar"],
                         {"s": {"kind": "map", "ms": "trekarcgis3/rest/services/regional_SP/MapServer"}})
        self.assertNotIn("polar", seed["layer_1"])
        layers = {l["id"]: l for g in trek.client_catalog("moon")["groups"] for l in g["layers"]}
        self.assertEqual(layers["layer_0"]["polar"]["s"]["name"], "layer_0_SP")
        self.assertEqual(layers["regional"]["polar"], {"s": {"kind": "map"}})     # 경로는 내리지 않는다
        self.assertEqual(layers["layer_1"]["polar"], {})
        self.run_command()
        self.assertEqual(self.polar_probe.call_count, 0)                         # 한 번 물은 판은 다시 묻지 않는다

    def test_달_화면에_실린다(self):
        self.run_command()
        html = self.client.get(reverse("viewer:moon")).content.decode()
        self.assertIn('id="trek-data"', html)
        self.assertIn("layer_0", html)


class PolarWmts(SimpleTestCase):
    """극지 판의 `WMTSCapabilities.xml` — 2026-09-30 에 받은 `SPA_GeoMap_lqbal_et_al_SP` 의 꼴 (wetherilli 085)."""

    def caps(self, corner="-1095930 1095930"):
        matrices = "".join(
            f"<TileMatrix><ows:Identifier>{i}</ows:Identifier><TopLeftCorner>{corner}</TopLeftCorner>"
            f"<MatrixWidth>{2 ** (i + 1)}.0</MatrixWidth><MatrixHeight>{2 ** i}.0</MatrixHeight></TileMatrix>"
            for i in range(6))
        return ('<?xml version="1.0"?><Capabilities xmlns="http://www.opengis.net/wmts/1.0" '
                'xmlns:ows="http://www.opengis.net/ows/1.1"><Contents><Layer>'
                "<ows:BoundingBox><ows:LowerCorner>-931134.753 -931138.445</ows:LowerCorner>"
                "<ows:UpperCorner>931165.247 931161.555</ows:UpperCorner></ows:BoundingBox>"
                f"<Format>image/png</Format></Layer><TileMatrixSet>{matrices}</TileMatrixSet></Contents>"
                "</Capabilities>").encode()

    def test_줌_끝과_범위(self):
        self.assertEqual(trek.parse_polar_wmts(self.caps()),
                         {"ext": "png", "max": 5, "box": [-931135, -931138, 931165, 931162]})

    def test_격자가_다르면_없다(self):
        self.assertIsNone(trek.parse_polar_wmts(self.caps("-2000000 2000000")))
        self.assertIsNone(trek.parse_polar_wmts(b"<html>"))

    def test_극마다_뿌리가_다르다(self):
        r = mock.Mock(status_code=404, url="…", content=b"", headers={})
        with mock.patch("viewer.trek.requests.get", return_value=r) as get:
            self.assertIsNone(trek.polar_wmts_info("moon", "X_NP", "n"))
        self.assertEqual(get.call_args[0][0], "https://trek.nasa.gov/tiles/Moon/NP/X_NP/1.0.0/WMTSCapabilities.xml")

    def test_서비스_목록에서_짝을_찾는다(self):
        lists = {"trekarcgis": [{"name": "A_SP", "type": "ImageServer"}, {"name": "A", "type": "ImageServer"}],
                 "trekarcgis2": [{"name": "B_NP", "type": "MapServer"}], "trekarcgis3": []}

        def fake(url, params=None, **kw):
            body = {"services": lists[url.split("/")[-3]]}
            return mock.Mock(status_code=200, url=url, headers={}, content=b"", json=lambda: body)
        with mock.patch("viewer.trek.requests.get", side_effect=fake):
            self.assertEqual(trek.polar_twins("moon"), {"A": {"s": ("trekarcgis", "A_SP", "ImageServer")},
                                                        "B": {"n": ("trekarcgis2", "B_NP", "MapServer")}})


class PolarMap(TestCase):
    """극지 MapServer 짝 — 우리 문이 극 격자로 굽는다 (wetherilli 085)."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="gsm-trek-pmap-"))
        (self.repo / "data").mkdir()
        (self.repo / "data" / "moon_trek_layers.json").write_text(json.dumps({"layers": [
            dict(item("A3_Named_regions", cat="Landforms"), kind="map",
                 ms="trekarcgis2/rest/services/A3_Named_regions/MapServer",
                 polar={"s": {"kind": "map", "ms": "trekarcgis2/rest/services/A3_Named_regions_SP/MapServer"}}),
        ]}), encoding="utf-8")
        for patch in (override_settings(REPO_DIR=self.repo),
                      override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-trek-pmap-cache-"))):
            patch.enable()
            self.addCleanup(patch.disable)

    def test_극_격자로_묻는다(self):
        png = mock.Mock(status_code=200, headers={"Content-Type": "image/png"}, content=b"\x89PNG", url="…")
        with mock.patch("viewer.trek.requests.get", return_value=png) as get:
            r = self.client.get(reverse("viewer:trek-map-polar-tile", args=["moon", "A3_Named_regions", "s", 0, 0, 0]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args[0][0],
                         "https://trek.nasa.gov/moon/trekarcgis2/rest/services/A3_Named_regions_SP/MapServer/export")
        params = get.call_args[1]["params"]
        self.assertEqual(params["bbox"], "-1095930.0,-1095930.0,1095930.0,1095930.0")
        self.assertNotIn("bboxSR", params)                                       # 서비스의 투영(WKT)으로 읽는다

    def test_짝이_없는_극과_화성은_부르지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get:
            for args in (["moon", "A3_Named_regions", "n", 0, 0, 0], ["mars", "A3_Named_regions", "s", 0, 0, 0],
                         ["moon", "anything", "s", 0, 0, 0]):
                self.assertEqual(self.client.get(reverse("viewer:trek-map-polar-tile", args=args)).status_code, 404)
        get.assert_not_called()


class MapServer(TestCase):
    """WMTS 가 없는 판 — 씨앗에 `kind: map` 으로 적힌 것만 우리 문이 굽고 읽는다."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="gsm-trek-map-"))
        (self.repo / "data").mkdir()
        (self.repo / "data" / "mars_trek_layers.json").write_text(json.dumps({"layers": [
            dict(item("Hynek_Valley_Networks", cat="Landforms"), kind="map",
                 ms="trekarcgis/rest/services/Hynek_Valley_Networks/MapServer"),
            dict(item("THEMIS_night"), kind="tile", ext="png", max=9, z0=0),
        ]}), encoding="utf-8")
        for patch in (override_settings(REPO_DIR=self.repo),
                      override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-trek-map-cache-"))):
            patch.enable()
            self.addCleanup(patch.disable)

    def test_씨앗에_없는_판은_부르지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get:
            for label in ("THEMIS_night", "anything"):
                r = self.client.get(reverse("viewer:trek-map-tile", args=["mars", label, 0, 0, 0]))
                self.assertEqual(r.status_code, 404)
        get.assert_not_called()

    def test_타일은_export_로_굽고_캐시에_담는다(self):
        png = mock.Mock(status_code=200, headers={"Content-Type": "image/png"}, content=b"\x89PNG", url="…")
        with mock.patch("viewer.trek.requests.get", return_value=png) as get:
            url = reverse("viewer:trek-map-tile", args=["mars", "Hynek_Valley_Networks", 1, 2, 0])
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.get(url)
        self.assertEqual(get.call_count, 1)
        called = get.call_args[0][0]
        self.assertEqual(called, "https://trek.nasa.gov/mars/trekarcgis/rest/services/Hynek_Valley_Networks/MapServer/export")
        self.assertEqual(get.call_args[1]["params"]["bboxSR"], 104905)

    def test_속성은_열_이름_그대로(self):
        body = {"results": [{"layerName": "valleys", "attributes": {
            "FID": "3", "Shape": "Polyline", "Order": "4", "Name": "Warrego Valles", "Note": " "}}]}
        r = mock.Mock(status_code=200, headers={"content-type": "application/json"}, url="…",
                      content=json.dumps(body).encode(), json=lambda: body)
        with mock.patch("viewer.trek.requests.get", return_value=r):
            data = self.client.get(reverse("viewer:trek-map-info", args=["mars", "Hynek_Valley_Networks"]),
                                   {"lon": "-93.5", "lat": "-42.3", "z": "6"}).json()
        self.assertEqual(data["hits"], [{"layer": "valleys", "rows": [["Order", "4"], ["Name", "Warrego Valles"]]}])

    def test_서비스_찾기는_이름으로_되짚는다(self):
        """색인이 WMTS 라 적고 MapServer 만 둔 판 (Hynek, 2026-09-30)."""
        services = {"response": {"docs": [{"protocol": "WMTS", "endPoint": "https://trek.nasa.gov/tiles/Mars/EQ/X"}]}}

        def fake(url, params=None, **kw):
            body = services if "getLayerServices" in url else (
                {"layers": []} if url.endswith("trekarcgis2/rest/services/X/MapServer") else {"error": {"code": 404}})
            return mock.Mock(status_code=200, headers={"content-type": "application/json"}, url=url,
                             content=json.dumps(body).encode(), json=lambda: body)
        with mock.patch("viewer.trek.requests.get", side_effect=fake):
            self.assertEqual(trek.find_mapserver("mars", "u-1", "X"), "trekarcgis2/rest/services/X/MapServer")
