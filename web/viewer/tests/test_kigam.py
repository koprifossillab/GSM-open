"""상류로 나가는 문.

여기서 지키는 것은 둘이다 — **인증키가 새지 않는 것**, 그리고 **브라우저가
넘긴 변수를 그대로 믿지 않는 것**. 둘 다 밖으로 드러나면 고치기 늦다.
"""
from django.test import SimpleTestCase, override_settings

from viewer import catalog, kigam

CAPABILITIES = """<?xml version="1.0"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
 <Capability>
  <Layer>
   <Title>묶음</Title>
   <Layer queryable="1">
    <Name>geoOpen:L_250K_Geology_Map</Name>
    <Title>25만 지질도</Title>
    <CRS>EPSG:4326</CRS>
    <EX_GeographicBoundingBox>
     <westBoundLongitude>124.5</westBoundLongitude>
     <southBoundLatitude>33.0</southBoundLatitude>
     <eastBoundLongitude>131.9</eastBoundLongitude>
     <northBoundLatitude>39.0</northBoundLatitude>
    </EX_GeographicBoundingBox>
   </Layer>
   <Layer><Name>geoOpen:L_geochemMP_ZN</Name><Title>아연</Title></Layer>
   <Layer><Name>Coalfield:something_else</Name><Title>안 열린 것</Title></Layer>
  </Layer>
 </Capability>
</WMS_Capabilities>
"""


class Redact(SimpleTestCase):
    def test_인증키를_지운다(self):
        got = kigam.redact("https://x/wms?key=SECRET123&layers=a")
        self.assertNotIn("SECRET123", got)
        self.assertIn("layers=a", got)

    def test_대문자_KEY_도_지운다(self):
        self.assertNotIn("SECRET", kigam.redact("?KEY=SECRET&a=1"))

    def test_빈_것도_견딘다(self):
        self.assertEqual(kigam.redact(""), "")


class CleanParams(SimpleTestCase):
    def test_인증키는_브라우저에서_받지_않는다(self):
        """브라우저가 key 를 넣어 보내도 버린다. 키는 서버만 붙인다."""
        got = kigam.clean_params({"key": "가짜", "layers": "a"})
        self.assertNotIn("key", got)
        self.assertEqual(got["layers"], "a")

    def test_대소문자를_가리지_않는다(self):
        got = kigam.clean_params({"LAYERS": "a", "BBOX": "1,2,3,4"})
        self.assertEqual(got["layers"], "a")
        self.assertEqual(got["bbox"], "1,2,3,4")

    def test_모르는_변수는_버린다(self):
        got = kigam.clean_params({"layers": "a", "sql": "drop table"})
        self.assertEqual(set(got), {"layers"})


class Qualify(SimpleTestCase):
    def test_접두사가_없으면_그대로_둔다(self):
        params = {"layers": "L_250K_Geology_Map"}
        self.assertEqual(kigam._qualify(params, ""), params)

    def test_접두사를_붙인다(self):
        got = kigam._qualify({"layers": "L_250K_Geology_Map"}, "geoOpen:")
        self.assertEqual(got["layers"], "geoOpen:L_250K_Geology_Map")

    def test_여럿이면_각각_붙인다(self):
        got = kigam._qualify({"layers": "a,b"}, "geoOpen:")
        self.assertEqual(got["layers"], "geoOpen:a,geoOpen:b")

    def test_이미_붙은_것에_또_붙이지_않는다(self):
        got = kigam._qualify({"layers": "geoOpen:a,b"}, "geoOpen:")
        self.assertEqual(got["layers"], "geoOpen:a,geoOpen:b")

    def test_query_layers_에도_붙인다(self):
        got = kigam._qualify({"query_layers": "a"}, "geoOpen:")
        self.assertEqual(got["query_layers"], "geoOpen:a")


class Endpoint(SimpleTestCase):
    @override_settings(DEV_DIRECT_WMS=False, WMS_URL="https://x/openapi/wms")
    def test_기본은_문서화된_주소이고_접두사가_없다(self):
        url, prefix = kigam._endpoint()
        self.assertEqual(url, "https://x/openapi/wms")
        self.assertEqual(prefix, "")

    @override_settings(DEV_DIRECT_WMS=True, CAPABILITIES_URL="https://x/mgeo/geoserver/wms")
    def test_개발_스위치는_GeoServer_로_가고_접두사가_붙는다(self):
        url, prefix = kigam._endpoint()
        self.assertEqual(url, "https://x/mgeo/geoserver/wms")
        self.assertEqual(prefix, "geoOpen:")

    @override_settings(DEV_DIRECT_WMS=False, WMS_URL="https://x/openapi/wms",
                       CAPABILITIES_URL="https://x/mgeo/geoserver/wms")
    def test_속성은_키가_있어도_GeoServer_로_간다(self):
        url, prefix = kigam._endpoint("GetFeatureInfo")
        self.assertEqual(url, "https://x/mgeo/geoserver/wms")
        self.assertEqual(prefix, "geoOpen:")

    @override_settings(DEV_DIRECT_WMS=False, WMS_URL="https://x/openapi/wms")
    def test_타일과_범례는_문서화된_주소로_간다(self):
        for req in ("GetMap", "GetLegendGraphic"):
            self.assertEqual(kigam._endpoint(req), ("https://x/openapi/wms", ""))


class KeyGoesOnlyToOpenapi(SimpleTestCase):
    """키는 `/openapi/wms` 로만 나간다. GeoServer 로 흘리지 않는다."""

    def _sent(self, request):
        from unittest import mock
        with mock.patch.object(kigam.requests, "get") as get:
            get.return_value = mock.Mock(url="u", status_code=200, content=b"")
            kigam._get({"request": request, "layers": "a"})
        return get.call_args

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False)
    def test_타일에는_키가_붙는다(self):
        self.assertEqual(self._sent("GetMap").kwargs["params"]["key"], "abc")

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False)
    def test_속성에는_키가_안_붙는다(self):
        call = self._sent("GetFeatureInfo")
        self.assertNotIn("key", call.kwargs["params"])
        self.assertEqual(call.kwargs["params"]["layers"], "geoOpen:a")


class HasKey(SimpleTestCase):
    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False)
    def test_키도_스위치도_없으면_못_나간다(self):
        self.assertFalse(kigam.has_key())

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False)
    def test_키가_있으면_나간다(self):
        self.assertTrue(kigam.has_key())

    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=True)
    def test_스위치만_있어도_나간다(self):
        self.assertTrue(kigam.has_key())


class Catalog(SimpleTestCase):
    def test_열린_워크스페이스만_거둔다(self):
        seed = catalog.parse(CAPABILITIES)
        names = [l["name"] for l in seed["레이어"]]
        self.assertIn("L_250K_Geology_Map", names)
        self.assertIn("L_geochemMP_ZN", names)
        self.assertNotIn("something_else", names)   # Coalfield 워크스페이스

    def test_워크스페이스_접두사를_뗀다(self):
        seed = catalog.parse(CAPABILITIES)
        self.assertTrue(all(":" not in l["name"] for l in seed["레이어"]))

    def test_레이어군을_고른다(self):
        seed = catalog.parse(CAPABILITIES)
        by_name = {l["name"]: l for l in seed["레이어"]}
        self.assertEqual(by_name["L_250K_Geology_Map"]["group"], "지질도")
        self.assertEqual(by_name["L_geochemMP_ZN"]["group"], "지화학도")

    def test_범위를_읽는다(self):
        seed = catalog.parse(CAPABILITIES)
        by_name = {l["name"]: l for l in seed["레이어"]}
        self.assertEqual(by_name["L_250K_Geology_Map"]["bbox"],
                         [124.5, 33.0, 131.9, 39.0])
        self.assertIsNone(by_name["L_geochemMP_ZN"]["bbox"])

    def test_문서가_틀렸던_지화학도가_저마다_다른_이름이다(self):
        """안내 페이지는 이것들을 전부 L_geochemMP_V 로 적었다 (devlog 001)."""
        self.assertEqual(catalog.group_for("L_geochemMP_CU"), "지화학도")
        self.assertEqual(catalog.group_for("L_geochemMP_FE2O3"), "지화학도")


class KeyFromFile(SimpleTestCase):
    """인증키를 파일에서도 읽는다.

    배포한 자리의 `.env` 는 root 의 것이라 앱을 돌리는 사람이 못 고친다.
    그래서 쓸 수 있는 자리에 놓아도 읽게 했다 — 그 길이 살아 있는지 지킨다.
    """

    def test_파일에서_읽는다(self):
        import tempfile
        from pathlib import Path

        from gsmweb import settings as s

        with tempfile.TemporaryDirectory() as tmp:
            key_file = Path(tmp) / "kigam_key"
            key_file.write_text("  ABC123  \n", encoding="utf-8")
            with self.settings():
                import os
                old = os.environ.get("GSM_KIGAM_KEY_FILE")
                os.environ["GSM_KIGAM_KEY_FILE"] = str(key_file)
                try:
                    self.assertEqual(s._key_from_file(), "ABC123")
                finally:
                    if old is None:
                        os.environ.pop("GSM_KIGAM_KEY_FILE", None)
                    else:
                        os.environ["GSM_KIGAM_KEY_FILE"] = old

    def test_파일이_없으면_빈_값(self):
        import os

        from gsmweb import settings as s

        old = os.environ.get("GSM_KIGAM_KEY_FILE")
        os.environ["GSM_KIGAM_KEY_FILE"] = "/없는자리/kigam_key"
        try:
            self.assertEqual(s._key_from_file(), "")
        finally:
            if old is None:
                os.environ.pop("GSM_KIGAM_KEY_FILE", None)
            else:
                os.environ["GSM_KIGAM_KEY_FILE"] = old


class ProbeOpenapiFeatureInfo(SimpleTestCase):
    """`/openapi/wms` 가 속성을 열었는지 찔러보는 것. 제품의 길이 아니다."""

    def _reply(self, status, body=b"", ctype="application/json"):
        from unittest import mock
        r = mock.Mock(status_code=status, content=body, headers={"content-type": ctype})
        r.json.side_effect = (lambda: __import__("json").loads(body))
        return r

    def _probe(self, reply):
        from unittest import mock
        with mock.patch("viewer.kigam.requests.get", return_value=reply) as get, \
                mock.patch("viewer.kigam.usage.record"):
            got = kigam.probe_openapi_feature_info("L_250K_Geology_Map", "127,36,127.4,36.4")
        return got, get

    @override_settings(KIGAM_KEY="SECRET", WMS_URL="https://x/openapi/wms")
    def test_문서화된_주소로_키를_붙여_간다(self):
        got, get = self._probe(self._reply(500, b"error", "text/html"))
        self.assertTrue(got.startswith("아직 막혀 있다"))
        self.assertEqual(get.call_args.args[0], "https://x/openapi/wms")
        self.assertEqual(get.call_args.kwargs["params"]["key"], "SECRET")
        self.assertNotIn("SECRET", got)

    @override_settings(KIGAM_KEY="SECRET")
    def test_JSON_이_오면_열렸다(self):
        got, _ = self._probe(self._reply(200, b'{"features": []}'))
        self.assertTrue(got.startswith("열렸다"))

    @override_settings(KIGAM_KEY="SECRET")
    def test_200_이라도_JSON_이_아니면_막혀_있다(self):
        got, _ = self._probe(self._reply(200, b"<html>", "text/html"))
        self.assertTrue(got.startswith("아직 막혀 있다"))

    @override_settings(KIGAM_KEY="")
    def test_키가_없으면_부르지_않는다(self):
        got, get = self._probe(self._reply(200))
        get.assert_not_called()
        self.assertIn("인증키", got)


class Composed(SimpleTestCase):
    """층리 뺀 5만 지질도 — 그림만 낱레이어를 엮어 GeoServer 에서, 속성·범례는 묶음에 묻는다."""

    NAME = "L_50K_Geology_Map_NoAttitude"

    def _sent(self, params):
        from unittest import mock
        with mock.patch.object(kigam.requests, "get") as get:
            get.return_value = mock.Mock(url="u", status_code=200, content=b"")
            kigam._get(params)
        return get.call_args

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False,
                       WMS_URL="https://x/openapi/wms", CAPABILITIES_URL="https://x/mgeo/geoserver/wms")
    def test_그림은_낱레이어를_엮어_GeoServer_로_키_없이(self):
        call = self._sent({"request": "GetMap", "layers": self.NAME, "styles": "x"})
        sent = call.kwargs["params"]
        self.assertEqual(call.args[0], "https://x/mgeo/geoserver/wms")
        self.assertNotIn("key", sent)
        layers = sent["layers"].split(",")
        self.assertIn("Geology_map:l_50k_geology_litho_view_latest", layers)
        self.assertIn("Geology_map:l_50k_geology_fault_latest", layers)
        self.assertFalse(any("bedding" in n or "foliation" in n or "joint" in n for n in layers))
        self.assertEqual(sent["styles"], "")         # 낱레이어마다 제 기본 스타일

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False,
                       WMS_URL="https://x/openapi/wms", CAPABILITIES_URL="https://x/mgeo/geoserver/wms")
    def test_속성은_묶음에_묻는다(self):
        call = self._sent({"request": "GetFeatureInfo", "layers": self.NAME, "query_layers": self.NAME})
        sent = call.kwargs["params"]
        self.assertEqual(call.args[0], "https://x/mgeo/geoserver/wms")
        self.assertEqual(sent["layers"], "geoOpen:L_50K_Geology_Map")
        self.assertEqual(sent["query_layers"], "geoOpen:L_50K_Geology_Map")
        self.assertNotIn("key", sent)

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False,
                       WMS_URL="https://x/openapi/wms", CAPABILITIES_URL="https://x/mgeo/geoserver/wms")
    def test_범례는_묶음의_것을_제자리에서(self):
        call = self._sent({"request": "GetLegendGraphic", "layer": self.NAME})
        self.assertEqual(call.args[0], "https://x/openapi/wms")
        self.assertEqual(call.kwargs["params"]["layer"], "L_50K_Geology_Map")
        self.assertEqual(call.kwargs["params"]["key"], "abc")

    @override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False, WMS_URL="https://x/openapi/wms")
    def test_다른_레이어는_그대로다(self):
        call = self._sent({"request": "GetMap", "layers": "L_50K_Geology_Map"})
        self.assertEqual(call.args[0], "https://x/openapi/wms")
        self.assertEqual(call.kwargs["params"]["layers"], "L_50K_Geology_Map")
