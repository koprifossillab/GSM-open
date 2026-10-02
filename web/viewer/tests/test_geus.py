"""그린란드 — GEUS 로 나가는 세 번째 문과 지역 나누기.

GEUS 를 실제로 부르지 않는다. text/plain 속성의 꼴은 2026-09-27 에 받아 본
그대로다.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import geus
from viewer.models import Layer, LayerGroup

PLAIN = """GetFeatureInfo results:

Layer 'grl_g500_lithostr_search'
  Feature 733: 
    id_hidden = '733'
    gu_mapcode = 'PRP-KEr'
    gu_name = 'Rapakivi Suite'
    ics_min_age_num = '1600.000000'
    ics_max_age_num = '2500.000000'
    rgb = '51 51 153'
    report_link = 'https://data.geus.dk/greenlanddb/webresources/geologic-unit/PRP-KEr'
"""


class Plain(SimpleTestCase):
    def test_text_plain_을_읽는다(self):
        got = geus.parse_plain(PLAIN)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "grl_g500_lithostr_search.733")
        self.assertEqual(got[0]["properties"]["gu_name"], "Rapakivi Suite")

    def test_없으면_빈_목록(self):
        self.assertEqual(geus.parse_plain("GetFeatureInfo results:\n\n  Search returned no results.\n"), [])

    def test_사람이_읽을_이름으로(self):
        props = geus.friendly(geus.parse_plain(PLAIN)[0]["properties"])
        self.assertEqual(props["지질 단위"], "Rapakivi Suite")
        self.assertEqual(props["최소 연대 (Ma)"], "1600")           # .000000 을 뗀다
        self.assertNotIn("id_hidden", props)
        self.assertNotIn("rgb", props)


@override_settings(GEUS_WHOAMI="someone@example.org", GEUS_MAPNAME="greenland_portal")
class Door(SimpleTestCase):
    def test_부르는_이를_밝히고_로그에는_적지_않는다(self):
        resp = mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=b"\x89PNG",
                         url="https://x/3857.jsp?whoami=someone@example.org&layers=a")
        with mock.patch.object(geus.requests, "get", return_value=resp) as get, \
                self.assertLogs("viewer.geus", "INFO") as logs:
            geus.get_map({"layers": "a", "crs": "EPSG:3857"})
        sent = get.call_args.kwargs["params"]
        self.assertEqual(sent["whoami"], "someone@example.org")
        self.assertEqual(sent["srs"], "EPSG:3857")                 # 1.3.0 의 CRS → 1.1.1 의 SRS
        self.assertNotIn("someone@example.org", "\n".join(logs.output))


class Routing(TestCase):
    """레이어의 상류를 보고 문을 고른다."""

    def setUp(self):
        import tempfile
        # 캐시를 비운 채로 — 앞선 실행이 담아 둔 타일이 나가면 문을 타지 않는다
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-geus-"),
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="지질도", region="greenland")
        Layer.objects.create(name="grl_g500_lithostr_search", title="50만", group=g, upstream="geus")
        k = LayerGroup.objects.create(name="지질도", region="korea")    # 이름이 같아도 된다
        Layer.objects.create(name="L_50K_Geology_Map", title="5만", group=k)

    def test_그린란드_타일은_GEUS_로(self):
        with mock.patch.object(geus, "get_map", return_value=(b"\x89PNG", "image/png")) as up:
            r = self.client.get("/GSM/wms/", {"LAYERS": "grl_g500_lithostr_search", "BBOX": "0,0,1,1",
                                              "WIDTH": "256", "HEIGHT": "256"})
        self.assertEqual(r.status_code, 200)
        up.assert_called_once()

    def test_그린란드_속성은_GEUS_로_가서_이름을_바꾼다(self):
        feats = {"features": geus.parse_plain(PLAIN)}
        with mock.patch.object(geus, "get_feature_info", return_value=feats):
            got = self.client.get("/GSM/featureinfo/", {"QUERY_LAYERS": "grl_g500_lithostr_search",
                                                        "BBOX": "0,0,1,1", "I": "1", "J": "1"}).json()
        self.assertEqual(got["features"][0]["props"]["지질 단위"], "Rapakivi Suite")

    def test_카탈로그에_지역이_실린다(self):
        regions = {g["region"] for g in self.client.get("/GSM/catalog/").json()["groups"]}
        self.assertEqual(regions, {"greenland", "korea"})
