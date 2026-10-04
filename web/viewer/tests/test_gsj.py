"""일본 — GSJ 심리스 지질도 V2 의 문 (devlog 024).

GSJ 를 실제로 부르지 않는다. 응답의 꼴은 2026-09-28 에 받아 본 그대로다 —
빈 자리의 타일은 `blank.png` 로 301, 빈 자리의 범례는 `symbol` 이 null 인 200.
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import gsj, i18n, views
from viewer.models import Layer, LayerGroup

#: 후지산 둘레를 누르면 오는 것 (2026-09-28)
FUJI = {"title": "新生代 第四紀 完新世,玄武岩 溶岩・火砕岩", "symbol": "H_vbs_al", "value": "70658f",
        "r": 112, "g": 101, "b": 143,
        "formationAge_ja": "新生代 第四紀 完新世", "formationAge_en": "Cenozoic Quaternary Holocene",
        "group_ja": "火成岩", "group_en": "Igneous rocks",
        "lithology_ja": "玄武岩 溶岩・火砕岩", "lithology_en": "basalt lava & pyroclastic rocks"}
#: 간략판(type=level2)으로 물으면 — 대분류가 곧 암상이고 `group_en` 이 없다.
#: `value` 는 원본의 색이라 `r·g·b`(간략판의 색)와 어긋난다
LEVEL2 = {"title": "…", "symbol": "Pg-N_a", "value": "a9dbd8", "r": 192, "g": 192, "b": 192,
          "formationAge_ja": "新第三紀・古第三紀", "formationAge_en": "Neogene and Paleogene",
          "lithology_ja": "付加体", "lithology_en": "Accretionary complex"}
#: 바다를 누르면
EMPTY = {"title": ",", "symbol": None, "value": "000000", "r": None, "g": None, "b": None,
         "formationAge_en": None, "group_en": None, "lithology_en": None}


def response(body=None, *, status=200, ctype="application/json", content=None, headers=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype, **(headers or {})},
                     content=content, text=content.decode("latin-1"), url="https://gbank.gsj.jp/…",
                     json=lambda: body)


def upstream(*answers):
    """`requests.get` 을 막고 차례로 답한다. 부른 것을 돌려받으려면 `as get`."""
    return mock.patch.object(gsj.requests, "get", side_effect=list(answers))


class Tiles(SimpleTestCase):
    def setUp(self):
        patch = mock.patch.object(gsj.usage, "record")
        patch.start()
        self.addCleanup(patch.stop)

    def test_자리_차례는_z_y_x(self):
        with upstream(response(ctype="image/png", content=b"\x89PNG")) as get:
            gsj.get_tile("gsj:geology", 11, 1812, 808)
        url = get.call_args.args[0]
        self.assertTrue(url.endswith("/tiles/11/808/1812.png"), url)
        self.assertEqual(get.call_args.kwargs["params"], {"layer": "g"})
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_간략판은_type_을_붙인다(self):
        with upstream(response(ctype="image/png", content=b"\x89PNG")) as get:
            gsj.get_tile("gsj:geology_level2", 6, 56, 25)
        self.assertEqual(get.call_args.kwargs["params"], {"layer": "g", "type": "level2"})

    def test_빈_자리는_따라가지_않고_빈_타일(self):
        blank = response(status=301, ctype="text/html", content=b"",
                         headers={"location": "https://gbank.gsj.jp/seamless/v2/api/1.3/blank.png"})
        with upstream(blank) as get:
            png = gsj.get_tile("gsj:faults", 11, 1812, 808)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(png, gsj.blank_tile())

    def test_그리지_않는_줌은_묻지_않는다(self):
        with upstream() as get:
            png = gsj.get_tile("gsj:symbols", 9, 454, 202)            # 기호는 줌 11 부터
        self.assertEqual(get.call_count, 0)
        self.assertEqual(png, gsj.blank_tile())

    def test_그림이_아니면_오류(self):
        error = response({"code": "104", "message": {"en": "z has to be 0-13"}}, status=400)
        with upstream(error), self.assertRaises(gsj.GsjError):
            gsj.get_tile("gsj:geology", 13, 1, 1)

    def test_타일_범위(self):
        self.assertTrue(gsj.valid_tile("gsj:geology", 13, 8191, 0))
        self.assertFalse(gsj.valid_tile("gsj:geology", 14, 0, 0))     # 상류가 줌 13 까지다
        self.assertFalse(gsj.valid_tile("gsj:geology", 2, 4, 0))
        self.assertFalse(gsj.valid_tile("gsj:nope", 2, 0, 0))


class Legend(SimpleTestCase):
    def setUp(self):
        patch = mock.patch.object(gsj.usage, "record")
        patch.start()
        self.addCleanup(patch.stop)

    def test_누른_자리(self):
        with upstream(response(FUJI)) as get:
            row = gsj.point_legend("gsj:geology", 35.36, 138.73)
        self.assertEqual(get.call_args.kwargs["params"], {"point": "35.360000,138.730000"})
        self.assertEqual(row["symbol"], "H_vbs_al")

    def test_바다는_None(self):
        with upstream(response(EMPTY)):
            self.assertIsNone(gsj.point_legend("gsj:geology", 33.0, 129.0))

    def test_범위는_남서북동_차례에_줌을_함께(self):
        """줌을 안 주면 상류가 줌 13 으로 세어 넓은 범위를 400 으로 돌려보낸다."""
        with upstream(response([FUJI, EMPTY])) as get:
            rows = gsj.extent_legend("gsj:geology", (138.5, 35.0, 139.3, 35.8), 17)
        self.assertEqual(get.call_args.kwargs["params"], {"box": "35.00,138.50,35.80,139.30", "z": 13})
        self.assertEqual([r["symbol"] for r in rows], ["H_vbs_al"])     # 빈 칸은 뺀다

    def test_간략판은_통째로(self):
        with upstream(response([LEVEL2])) as get:
            gsj.extent_legend("gsj:geology_level2", None, 5)
        self.assertEqual(get.call_args.kwargs["params"], {"type": "level2"})

    def test_넓으면_오류(self):
        with upstream(response({"code": "1", "message": {}}, status=400)), self.assertRaises(gsj.GsjError):
            gsj.extent_legend("gsj:geology", (130, 30, 140, 40), 13)


class Friendly(SimpleTestCase):
    def test_한국어판(self):
        props = gsj.friendly(FUJI, "ko")
        self.assertEqual(props, {
            "지질시대": "신생대 제4기 홀로세",
            "암상": "basalt lava & pyroclastic rocks",      # GSJ 가 붙인 영어 — 우리가 옮기지 않는다
            "구분": "화성암",
            "기호": "H_vbs_al",
            "암상 (원문)": "玄武岩 溶岩・火砕岩",
        })

    def test_영어판은_상류의_영어(self):
        props = gsj.friendly(FUJI, "en")
        self.assertEqual(props["지질시대"], "Cenozoic Quaternary Holocene")
        self.assertEqual(props["구분"], "Igneous rocks")

    def test_절_이름은_한글판을_따른다(self):
        row = dict(FUJI, formationAge_en="Mesozoic Early Cretaceous Aptian - Albian")
        self.assertEqual(gsj.friendly(row, "ko")["지질시대"], "중생대 백악기 전기 압트절~알바절")

    def test_옛_이름이_섞이면_원문(self):
        row = dict(FUJI, formationAge_en="Paleozoic Cambrian Series 3 - Ordovician Middle")
        self.assertEqual(gsj.friendly(row, "ko")["지질시대"], row["formationAge_en"])

    def test_간략판은_대분류가_암상(self):
        props = gsj.friendly(LEVEL2, "ko")
        self.assertEqual(props["암상"], "부가체")
        self.assertEqual(props["지질시대"], "신진기 및 고진기")
        self.assertNotIn("구분", props)

    def test_범례_칸의_색은_그_판의_색(self):
        self.assertEqual(gsj.legend_row(LEVEL2)["color"], "#c0c0c0")
        self.assertEqual(gsj.legend_row(FUJI)["color"], "#70658f")

    def test_대분류(self):
        self.assertEqual(gsj.group_ko("Accretionary complexes"), "부가체")
        self.assertEqual(gsj.group_ko("Metamorphic rock"), "변성암")
        self.assertEqual(gsj.group_ko("Something else"), "Something else")


class AgeStacked(SimpleTestCase):
    """GSJ 가 실제로 준 값들이다 (범례 2 416 칸의 시대 112 가지에서, 2026-09-28)."""

    CASES = {
        "Cenozoic Quaternary Holocene": "신생대 제4기 홀로세",
        "Cenozoic Quaternary Late Pleistocene": "신생대 제4기 플라이스토세 후기",
        "Mesozoic Early Triassic - Late Triassic": "중생대 트라이아스기 전기~트라이아스기 후기",
        "Mesozoic Jurassic Early - Middle": "중생대 쥐라기 전기~중기",
        "Paleozoic Ordovician Late - Early Devonian": "고생대 오르도비스기 후기~데본기 전기",
        "Paleozoic Cambrian - Ordovician": "고생대 캄브리아기~오르도비스기",
        "Neogene and Paleogene": "신진기 및 고진기",
        # 절(Age) 이름이 섞이면 통째로 원문 (devlog 021 의 규칙)
        "Cenozoic Neogene Miocene late Burdigalian - late Serravallian":
            "신생대 신진기 마이오세 부르디갈라절 후기~세라발레절 후기",
        "Paleozoic Late Devonian - Permian Cisuralian": "고생대 데본기 후기~페름기 시스우랄세",
        # 꾸밈말이 겹치면 원문 — "플라이스토세 후기 후기" 는 읽히지 않는다
        "Cenozoic Quaternary late Late Pleistocene - Holocene":
            "Cenozoic Quaternary late Late Pleistocene - Holocene",
    }

    def test_값들(self):
        for en, ko in self.CASES.items():
            self.assertEqual(i18n.age_ko_stacked(en), ko, en)

    def test_빈_값(self):
        self.assertEqual(i18n.age_ko_stacked(""), "")
        self.assertIsNone(i18n.age_ko_stacked(None))


class View(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsj-"),
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="심리스 지질도 (GSJ)", region="japan")
        for name in gsj.LAYERS:
            Layer.objects.create(name=name, title=name, group=g, upstream="gsj")

    def test_카탈로그(self):
        rows = {l["name"]: l for l in views._catalog()[0]["layers"]}
        geology = rows["gsj:geology"]
        self.assertEqual(geology["tiles"], "gsj/geology/{z}/{x}/{y}.png")
        self.assertEqual((geology["minZoom"], geology["maxZoom"], geology["legend"]), (0, 13, "extent"))
        self.assertTrue(geology["queryable"])
        self.assertIn("Geological Survey of Japan", geology["attribution"])
        faults = rows["gsj:faults"]
        self.assertEqual((faults["minZoom"], faults["legend"]), (10, "none"))
        self.assertFalse(faults["queryable"])                          # 선이라 속성이 없다

    def test_타일은_한_번만_받는다(self):
        with mock.patch.object(gsj, "get_tile", return_value=b"\x89PNG") as up:
            r1 = self.client.get("/GSM/gsj/geology/11/1812/808.png")
            r2 = self.client.get("/GSM/gsj/geology/11/1812/808.png")
        self.assertEqual(up.call_count, 1)
        up.assert_called_with("gsj:geology", 11, 1812, 808)
        self.assertEqual((r1["X-GSM-Cache"], r2["X-GSM-Cache"]), ("miss", "hit"))

    def test_없는_타일은_404(self):
        self.assertEqual(self.client.get("/GSM/gsj/geology/14/0/0.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/gsj/nope/1/0/0.png").status_code, 404)

    def test_상류가_못_주면_안내_타일을_담지_않는다(self):
        with mock.patch.object(gsj, "get_tile", side_effect=gsj.GsjError("x")):
            r = self.client.get("/GSM/gsj/geology/11/1812/808.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_속성은_팝업_꼴로(self):
        query = {"layer": "gsj:geology", "lat": "35.36", "lon": "138.73"}
        with mock.patch.object(gsj, "point_legend", return_value=FUJI) as up:
            ko = self.client.get("/GSM/gsj/info/", query).json()
            en = self.client.get("/GSM/gsj/info/", dict(query, lang="en"), HTTP_COOKIE="gsm_lang=en").json()
        self.assertEqual(up.call_count, 1)                                 # 둘째는 캐시에서
        self.assertEqual(ko["features"][0]["props"]["지질시대"], "신생대 제4기 홀로세")
        self.assertEqual(en["features"][0]["props"]["Geologic age"], "Cenozoic Quaternary Holocene")
        self.assertEqual(en["features"][0]["props"]["Lithology (original)"], "玄武岩 溶岩・火砕岩")

    def test_바다를_누르면_빈_목록(self):
        with mock.patch.object(gsj, "point_legend", return_value=None):
            data = self.client.get("/GSM/gsj/info/", {"layer": "gsj:geology", "lat": "33", "lon": "129"}).json()
        self.assertEqual(data["features"], [])

    def test_속성이_없는_레이어는_묻지_않는다(self):
        r = self.client.get("/GSM/gsj/info/", {"layer": "gsj:faults", "lat": "33", "lon": "129"})
        self.assertEqual(r.status_code, 400)

    def test_범위_범례(self):
        rows = [dict(FUJI, symbol=f"S{i}") for i in range(gsj.MAX_LEGEND + 5)]
        query = {"layer": "gsj:geology", "bbox": "138.5012,35.0,139.3,35.8", "z": "9"}
        with mock.patch.object(gsj, "extent_legend", return_value=rows) as up:
            data = self.client.get("/GSM/gsj/legend/", query).json()
            self.client.get("/GSM/gsj/legend/", dict(query, bbox="138.4999,35.0,139.3,35.8"))
        self.assertEqual(up.call_count, 1)                   # 소수 둘째 자리로 잘라 캐시가 맞는다
        up.assert_called_with("gsj:geology", [138.5, 35.0, 139.3, 35.8], 9)
        self.assertEqual(len(data["rows"]), gsj.MAX_LEGEND)
        self.assertEqual(data["more"], 5)
        self.assertEqual(data["rows"][0]["age"], "신생대 제4기 홀로세")

    def test_범례가_없는_레이어(self):
        r = self.client.get("/GSM/gsj/legend/", {"layer": "gsj:faults"})
        self.assertEqual(r.status_code, 400)

    def test_범례를_못_받으면_502(self):
        with mock.patch.object(gsj, "extent_legend", side_effect=gsj.GsjError("x")):
            r = self.client.get("/GSM/gsj/legend/", {"layer": "gsj:geology", "bbox": "1,2,3,4", "z": "5"})
        self.assertEqual(r.status_code, 502)


class Seed(TestCase):
    def test_씨앗과_문이_짝이_맞고_영어가_있다(self):
        seed = json.loads(views.settings.GSJ_CATALOG_SEED.read_text(encoding="utf-8"))
        self.assertEqual({row["name"] for row in seed["레이어"]}, set(gsj.LAYERS))
        for row in seed["레이어"]:
            self.assertIn(row["name"], i18n.LAYER_EN)
        for group in seed["레이어군순서"]:
            self.assertIn(group, i18n.GROUP_EN)

    def test_일본에_넣는다(self):
        call_command("seed_catalog", stdout=mock.Mock())
        layer = Layer.objects.get(name="gsj:geology")
        self.assertEqual((layer.upstream, layer.group.region), ("gsj", "japan"))
        self.assertIsNotNone(layer.verified_at)                         # 한 장씩 받아 보고 넣었다


class GsjOws(TestCase):
    """GSJ 의 다른 WMS — 1:200만 지질도·부게 중력·지구화학도 (wetherilli 255)"""

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-gsjows-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(gsj.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def png(self):
        r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
        return r

    def test_호스트가_둘(self):
        with mock.patch.object(gsj.requests, "get", return_value=self.png()) as get:
            gsj.gsjows_get_map({"layers": "gsjows:geochem:Cu", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertEqual(get.call_args.args[0], "https://gbank.gsj.jp/ows/geochemmap")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "Cu")
        with mock.patch.object(gsj.requests, "get", return_value=self.png()) as get:
            gsj.gsjows_get_map({"layers": "gsjows:japan2m", "crs": "EPSG:3857", "bbox": "0,0,1,1", "width": 256, "height": 256})
        self.assertEqual((get.call_args.args[0], get.call_args.kwargs["params"]["layers"]), ("https://ows.gsj.jp/ows/geologicmap2000k", "area,line"))

    def test_범례는_그림_누르기는_없다(self):
        with mock.patch.object(gsj.requests, "get", return_value=self.png()) as get:
            gsj.gsjows_get_legend("gsjows:gravity")
        self.assertEqual(get.call_args.kwargs["params"]["layer"], "GravityContour267")
        self.assertEqual(gsj.gsjows_get_feature_info({"layers": "gsjows:gravity"}), {"features": []})

    def test_카탈로그(self):
        self.assertEqual(Layer.objects.get(name="gsjows:geochem:Hg").group.region, "japan")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertIs(rows["gsjows:japan2m"]["queryable"], False)
        self.assertEqual(rows["gsjows:gravity"]["projection"], "EPSG:3857")
