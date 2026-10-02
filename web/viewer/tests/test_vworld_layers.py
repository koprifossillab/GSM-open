""""지질 참고" 레이어군 — VWorld WMS 중계와 단층 벡터 (devlog 020).

VWorld 를 실제로 부르지 않는다. 응답의 꼴은 2026-09-27 에 받아 본 그대로다.
"""
import json
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import vworld
from viewer.models import Layer, LayerGroup

PNG = b"\x89PNG\r\n\x1a\n"

#: WFS 가 준 꼴 그대로 (대전 둘레 1° 칸의 첫 모양)
FAULT = {
    "type": "Feature", "id": "lt_l_gimsfault.156",
    "geometry": {"type": "MultiLineString",
                 "coordinates": [[[127.74783212, 36.12606255], [127.74581312, 36.12121181]]]},
    "geometry_name": "ag_geom",
    "properties": {"legend": "1", "leng": "730.793851084"},
    "bbox": [127.74581312, 36.12121181, 127.74783212, 36.12606255],
}


def resp(content=b"", ctype="image/png", status=200, body=None):
    r = mock.Mock(status_code=status, headers={"content-type": ctype}, content=content,
                  url="https://api.vworld.kr/req/wms?key=SECRET&layers=a")
    r.json = mock.Mock(return_value=body)
    return r


@override_settings(VWORLD_KEY="SECRET")
class Door(SimpleTestCase):
    def test_타일_열쇠는_서버가_붙이고_로그에는_적지_않는다(self):
        with mock.patch.object(vworld.requests, "get", return_value=resp(PNG)) as get, \
                self.assertLogs("viewer.vworld", "INFO") as logs:
            content, ctype = vworld.get_map({"layers": "LT_C_WKMSTRM", "crs": "EPSG:3857"})
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["key"], "SECRET")
        self.assertEqual(sent["layers"], "lt_c_wkmstrm")     # 대문자면 VWorld 가 예외를 준다
        self.assertEqual(sent["styles"], "")
        self.assertEqual(sent["version"], "1.3.0")
        self.assertNotIn("domain", sent)
        self.assertEqual(content, PNG)
        self.assertNotIn("SECRET", "\n".join(logs.output))

    def test_그림이_아니면_오류(self):
        with mock.patch.object(vworld.requests, "get",
                               return_value=resp(b"<ServiceExceptionReport/>", "text/xml")):
            with self.assertRaises(vworld.VWorldError):
                vworld.get_map({"layers": "lt_c_wkmstrm"})

    def test_WFS_는_위도가_먼저이고_곁가지를_뗀다(self):
        body = {"type": "FeatureCollection", "features": [FAULT, dict(FAULT, geometry=None)]}
        with mock.patch.object(vworld.requests, "get",
                               return_value=resp(ctype="application/json", body=body)) as get:
            got = vworld.get_features("lt_l_gimsfault", 127, 36, 128, 37)
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["bbox"], "36,127,37,128,EPSG:4326")
        self.assertEqual(sent["srsname"], "EPSG:4326")
        self.assertEqual(len(got["features"]), 1)             # 기하 없는 것은 버린다
        f = got["features"][0]
        self.assertEqual(f["id"], "lt_l_gimsfault.156")
        self.assertNotIn("bbox", f)
        self.assertNotIn("geometry_name", f)
        self.assertEqual(f["geometry"]["type"], "MultiLineString")

    @override_settings(VWORLD_KEY="")
    def test_열쇠가_없으면_묻지_않는다(self):
        with mock.patch.object(vworld.requests, "get") as get:
            with self.assertRaises(vworld.VWorldError):
                vworld.get_map({"layers": "lt_c_wkmstrm"})
        get.assert_not_called()


class Friendly(SimpleTestCase):
    def test_읽을_것만_한국어_이름으로(self):
        got = vworld.friendly({"riv_cd": "3001490", "riv_nm": "갑천", "riv_level": "국가하천",
                               "cat_cde": "CAT000", "inadm": 1})
        self.assertEqual(got, {"하천명": "갑천", "하천 등급": "국가하천"})

    def test_단층의_길이는_반올림한다(self):
        self.assertEqual(vworld.friendly(FAULT["properties"]), {"구분": "1", "길이 (m)": "731"})

    def test_표에_없는_열뿐이면_그대로_둔다(self):
        self.assertEqual(vworld.friendly({"mnum": "138000044150"}), {"mnum": "138000044150"})

    def test_토양도의_label_은_레이어마다_뜻이_다르다(self):
        props = {"code_ad": 4, "label": ">100"}
        self.assertEqual(vworld.friendly(props, "lt_c_asitsoildep"), {"유효토심 (cm)": ">100"})
        self.assertEqual(vworld.friendly(props, "LT_C_ASITSOILDRA"), {"배수 등급": ">100"})

    def test_모르는_지정_연도는_싣지_않는다(self):
        props = {"dyear": "0000", "ucode": "UOC530", "uname": "문화재자료구역", "sigg_name": "고성군"}
        self.assertEqual(vworld.friendly(props, "lt_c_uo301"), {"지구": "문화재자료구역", "시군구": "고성군"})

    def test_공역은_이름과_고도만(self):
        props = {"prohibited": "<FNT name='TW Cen MT'>RK P518</FNT>", "prh_lbl_1": "RK P518",
                 "prh_lbl_2": "UNL", "prh_lbl_3": "GND", "prh_typ": "1"}
        self.assertEqual(vworld.friendly(props, "lt_c_aisprhc"),
                         {"공역": "RK P518", "상한 고도": "UNL", "하한 고도": "GND"})


class Views(TestCase):
    def setUp(self):
        patch = override_settings(VWORLD_KEY="SECRET", TILE_CACHE_MIN_FREE_BYTES=0,
                                  TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-vwl-"))
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="지질 참고", region="korea", order=100)
        box = dict(bbox_west=124.5, bbox_south=33.0, bbox_east=131.0, bbox_north=38.7)
        Layer.objects.create(name="lt_c_wkmstrm", title="하천망", group=g, upstream="vworld", **box)
        Layer.objects.create(name="lt_l_gimsfault", title="단층", group=g, upstream="vworld",
                             kind="vector", **box)
        Layer.objects.create(name="lt_l_gimsdepth", title="지하수 등수심선", group=g, upstream="vworld",
                             kind="vector", **box)

    def test_타일은_VWorld_문으로_가고_캐시에_담긴다(self):
        q = {"LAYERS": "lt_c_wkmstrm", "BBOX": "0,0,1,1", "WIDTH": "512", "HEIGHT": "512"}
        with mock.patch.object(vworld, "get_map", return_value=(PNG, "image/png")) as up:
            first = self.client.get("/GSM/wms/", q)
            second = self.client.get("/GSM/wms/", q)
        self.assertEqual(up.call_count, 1)
        self.assertEqual(first["X-GSM-Cache"], "miss")
        self.assertEqual(second["X-GSM-Cache"], "hit")

    def test_속성은_한국어_이름으로(self):
        data = {"features": [{"id": "lt_c_wkmstrm.1",
                              "properties": {"riv_nm": "갑천", "riv_cd": "3001490"}}]}
        with mock.patch.object(vworld, "get_feature_info", return_value=data):
            got = self.client.get("/GSM/featureinfo/", {"QUERY_LAYERS": "lt_c_wkmstrm",
                                                        "BBOX": "0,0,1,1", "I": "1", "J": "1"}).json()
        self.assertEqual(got["features"][0]["props"], {"하천명": "갑천"})

    def test_칸_하나를_받아_두_번째는_상류를_타지_않는다(self):
        fc = {"type": "FeatureCollection", "features": [
            {k: v for k, v in FAULT.items() if k not in ("bbox", "geometry_name")}]}
        with mock.patch.object(vworld, "get_features", return_value=fc) as up:
            first = self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127", "lat": "36"})
            second = self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127", "lat": "36"})
        self.assertEqual(up.call_count, 1)
        up.assert_called_with("lt_l_gimsfault", 127, 36, 128, 37)
        self.assertEqual(first.json(), second.json())
        f = first.json()["features"][0]
        self.assertEqual(f["properties"]["legend"], "1")             # 선 모양은 이것으로 가른다
        self.assertEqual(f["properties"]["_popup"], {"구분": "1", "길이 (m)": "731"})
        self.assertIn("max-age", first["Cache-Control"])

    def test_영어판은_팝업_이름을_옮긴다(self):
        fc = {"type": "FeatureCollection", "features": [FAULT]}
        self.client.cookies["gsm_lang"] = "en"
        with mock.patch.object(vworld, "get_features", return_value=fc):
            got = self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127", "lat": "36"}).json()
        self.assertEqual(got["features"][0]["properties"]["_popup"], {"Class": "1", "Length (m)": "731"})

    def test_레이어_범위_밖의_칸은_묻지_않는다(self):
        with mock.patch.object(vworld, "get_features") as up:
            got = self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "10", "lat": "50"}).json()
        up.assert_not_called()
        self.assertEqual(got["features"], [])

    def test_엉뚱한_요청은_거절한다(self):
        self.assertEqual(self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "x", "lat": "36"}).status_code, 400)
        self.assertEqual(self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "200", "lat": "36"}).status_code, 400)
        # 타일 레이어는 벡터 문으로 받지 않는다
        self.assertEqual(self.client.get("/GSM/vector/", {"layer": "lt_c_wkmstrm", "lon": "127", "lat": "36"}).status_code, 404)

    def test_상류가_못_주면_502(self):
        with mock.patch.object(vworld, "get_features", side_effect=vworld.VWorldError("x")):
            r = self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127", "lat": "36"})
        self.assertEqual(r.status_code, 502)

    def test_카탈로그에_상류와_그리는_법이_실린다(self):
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows["lt_l_gimsfault"]["kind"], "vector")
        self.assertEqual(rows["lt_l_gimsfault"]["cell"], 1)
        self.assertEqual(rows["lt_c_wkmstrm"]["upstream"], "vworld")
        self.assertNotIn("cell", rows["lt_c_wkmstrm"])
        self.assertNotIn("minZoom", rows["lt_l_gimsfault"])
        self.assertEqual((rows["lt_l_gimsdepth"]["cell"], rows["lt_l_gimsdepth"]["minZoom"]), (0.125, 11))

    def test_등수심선은_작은_칸으로_받아_솎아_담는다(self):
        # 5 m 마다 찍힌 점 — 0.0005° 안의 것은 버리고 끝점은 둔다 (077)
        pts = [[127.1 + i * 0.00005, 36.1] for i in range(41)]
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": "lt_l_gimsdepth.1", "properties": {"legend": "20", "info": "1"},
             "geometry": {"type": "MultiLineString", "coordinates": [pts]}}]}
        q = {"layer": "lt_l_gimsdepth", "lon": "127.125", "lat": "36"}
        with mock.patch.object(vworld, "get_features", return_value=fc) as up:
            first = self.client.get("/GSM/vector/", q).json()
            self.client.get("/GSM/vector/", q)
        self.assertEqual(up.call_count, 1)
        up.assert_called_with("lt_l_gimsdepth", 127.125, 36, 127.25, 36.125)
        line = first["features"][0]["geometry"]["coordinates"][0]
        self.assertLess(len(line), 7)                                # 41 점이 다섯 남짓으로
        self.assertEqual(line[-1], [127.102, 36.1])
        self.assertEqual(first["features"][0]["properties"]["_popup"], {"지하수 등수심 (m)": "20"})
        # 칸의 서남 모서리가 아니면 거절한다 — 1° 칸 레이어는 여전히 정수만
        self.assertEqual(self.client.get("/GSM/vector/", {**q, "lon": "127.2"}).status_code, 400)
        self.assertEqual(self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127.25",
                                                          "lat": "36"}).status_code, 400)

    def test_1도_칸의_캐시_열쇠는_앞_판과_같다(self):
        from viewer import tilecache, views
        fc = {"type": "FeatureCollection", "features": []}
        with mock.patch.object(vworld, "get_features", return_value=fc):
            self.client.get("/GSM/vector/", {"layer": "lt_l_gimsfault", "lon": "127", "lat": "36"})
        self.assertIsNotNone(views._cache_get(tilecache.key_text("vector", "lt_l_gimsfault|127|36|1")))

    @override_settings(VWORLD_KEY="")
    def test_열쇠가_없으면_목록에서_뺀다(self):
        groups = self.client.get("/GSM/catalog/").json()["groups"]
        self.assertFalse(any(l["upstream"] == "vworld" for g in groups for l in g["layers"]))


class Seed(TestCase):
    def test_씨앗이_지질_참고를_넣는다(self):
        call_command("seed_catalog", stdout=StringIO())
        fault = Layer.objects.get(name="lt_l_gimsfault")
        self.assertEqual(fault.upstream, "vworld")
        self.assertEqual(fault.kind, "vector")
        self.assertIsNotNone(fault.verified_at)                     # 씨앗을 만들 때 쏴 봤다
        self.assertEqual(fault.group.region, "korea")
        # KIGAM 의 레이어군과 차례가 겹치지 않는다 — 한국 목록의 맨 뒤
        korea = [g.name for g in LayerGroup.objects.filter(region="korea")]
        self.assertEqual(korea[-4:], ["지질 참고", "보호구역", "토양·산림", "재해·공역"])
        self.assertEqual(Layer.objects.get(name="L_50K_Geology_Map").kind, "wms")

    def test_씨앗의_레이어는_모두_영어_제목이_있다(self):
        from django.conf import settings

        from viewer import i18n
        seed = json.loads(settings.VWORLD_CATALOG_SEED.read_text(encoding="utf-8"))
        for row in seed["레이어"]:
            self.assertIn(row["name"], i18n.LAYER_EN)
        for name in seed["레이어군순서"]:
            self.assertIn(name, i18n.GROUP_EN)


@override_settings(VWORLD_KEY="SECRET")
class Basemap(SimpleTestCase):
    """배경지도(WMTS) 중계 — 브라우저가 곧장 못 받을 때만 온다 (033)."""

    def test_열쇠는_경로에_붙고_로그에는_적지_않는다(self):
        with mock.patch.object(vworld.requests, "get", return_value=resp(PNG)) as get, \
                self.assertLogs("viewer.vworld", "INFO") as logs:
            content, ctype = vworld.get_wmts_tile("white", 10, 402, 874)
        self.assertEqual(get.call_args.args[0],
                         "https://api.vworld.kr/req/wmts/1.0.0/SECRET/white/10/402/874.png")
        self.assertEqual((content, ctype), (PNG, "image/png"))
        self.assertNotIn("SECRET", "\n".join(logs.output))

    def test_위성은_jpeg(self):
        with mock.patch.object(vworld.requests, "get",
                               return_value=resp(b"\xff\xd8", "image/jpeg")) as get:
            vworld.get_wmts_tile("Satellite", 10, 402, 874)
        self.assertTrue(get.call_args.args[0].endswith("/Satellite/10/402/874.jpeg"))

    def test_남극_기지_테마는_자리_차례를_바꿔_부른다(self):
        # 중계 주소는 배경지도처럼 z/y/x 로 오고, 테마는 z/x/y 로 부른다 (wetherilli 093)
        with mock.patch.object(vworld.requests, "get", return_value=resp(PNG)) as get:
            r = self.client.get("/GSM/vworld/AntarcticaSejong/15/22987/10866.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.args[0],
                         "https://api.vworld.kr/req/wmts/1.0.0/SECRET/Satellite/themes/cities/2013/"
                         "AntarcticaSejong/15/10866/22987.png")

    def test_자료_밖의_XML_은_빈_자리(self):
        with mock.patch.object(vworld.requests, "get",
                               return_value=resp(b"<xml/>", "application/xml;charset=UTF-8")):
            self.assertIsNone(vworld.get_wmts_tile("Base", 15, 1000, 1000))

    def test_닿지_못한_오류에도_열쇠가_없다(self):
        boom = vworld.requests.ConnectionError("https://api.vworld.kr/req/wmts/1.0.0/SECRET/Base/1/1/1.png reset")
        with mock.patch.object(vworld.requests, "get", side_effect=boom):
            with self.assertRaises(vworld.VWorldError) as ctx:
                vworld.get_wmts_tile("Base", 1, 1, 1)
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_뷰는_모르는_레이어를_묻지_않는다(self):
        with mock.patch.object(vworld.requests, "get") as get:
            r = self.client.get("/GSM/vworld/Bogus/7/50/109.png")
        self.assertEqual(r.status_code, 404)
        get.assert_not_called()

    def test_뷰는_자료_밖을_투명_타일로_낸다(self):
        with mock.patch.object(vworld.requests, "get",
                               return_value=resp(b"<xml/>", "application/xml")):
            r = self.client.get("/GSM/vworld/Base/15/1000/1000.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
