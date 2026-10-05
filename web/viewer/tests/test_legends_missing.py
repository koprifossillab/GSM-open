"""누르기·범례가 둘 다 없던 레이어 — 대만 민감구역·GA 지구물리 격자·페루 부게 이상 (wetherilli 336). 상류를 부르지 않는다."""
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import ga, gsmma, ingemmet, twopen

SQUARE = {"type": "Polygon", "coordinates": [[[120.0, 23.0], [121.0, 23.0], [121.0, 24.0], [120.0, 24.0], [120.0, 23.0]]]}
CSV = ("﻿No.,地質敏感區類型,地質敏感區編號,地質敏感區名稱,公告日期,文號,座標系統1,座標系統2,下載連結\n"
       "1,活動斷層地質敏感區,F0001,車籠埔斷層,103年1月20日,經地字第1號,中央經線121,TWD97,x\n"
       "6,山崩與地滑地質敏感區,L0002,南投縣-01,103年3月31日,經地字第2號,中央經線121,TWD97,x\n"
       "18,山崩與地滑地質敏感區,L0002,南投縣-02,103年12月31日,經地字第3號,中央經線121,TWD97,x\n")


def answer(body=None, status=200):
    r = mock.Mock(status_code=status, content=b"{}", url="…", headers={"content-type": "application/json"})
    r.json = lambda: body
    return r


class Sensitive(SimpleTestCase):
    def test_공고_목록과_이름(self):
        notices = gsmma.sensitive_notices(CSV)
        self.assertEqual(notices["F0001"], {"name": "車籠埔斷層", "date": "103年1月20日", "doc": "經地字第1號"})
        self.assertEqual(notices["L0002"]["name"], "南投縣")
        self.assertEqual(notices["L0002"]["date"], "103年3月31日 · 103年12月31日")
        self.assertEqual(gsmma.sensitive_code({"gid": "18092-L0002_2"}), "L0002")
        self.assertEqual(gsmma.sensitive_code({"Gid": "1070-L0001"}), "L0001")
        self.assertEqual(gsmma.sensitive_names('E("F0001","車籠埔斷層",p),E("H0003","暖暖壺穴",d)'),
                         [("F0001", "車籠埔斷層"), ("H0003", "暖暖壺穴")])

    def test_모아_둔_면에서_누른다(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(TAIWAN_OPEN_DIR=folder):
            twopen.write_sensitive([
                {"kind": "F", "code": "F0001", "name": "車籠埔斷層", "town": "", "date": "103年1月20日", "doc": "", "geometry": SQUARE},
                {"kind": "L", "code": "L0002", "name": "南投縣", "town": "仁愛鄉", "date": "", "doc": "",
                 "geometry": {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]}},
            ], Path(folder) / twopen.SENSITIVE_FILE)
            self.assertEqual(twopen.sensitive_at("G", 120.5, 23.5), [])
            self.assertEqual(twopen.sensitive_at("F", 122.0, 23.5), [])
            q = {"layers": "gsmma:sensitive_fault", "query_layers": "gsmma:sensitive_fault", "crs": "EPSG:4326", "version": "1.3.0",
                 "bbox": "23,120,24,121", "width": 256, "height": 256, "i": 128, "j": 128}
            got = gsmma.get_feature_info(q)["features"]
            self.assertEqual(len(got), 1)
            self.assertEqual(gsmma.friendly(got[0]["properties"]),
                             {"갈래": "활성단층 민감구역", "구역": "車籠埔斷層", "구역 번호": "F0001", "공고일": "103年1月20日"})
            self.assertEqual(gsmma.friendly(got[0]["properties"], "en")["갈래"], "Active fault sensitive area")
            self.assertTrue(gsmma.queryable("gsmma:sensitive_landslide"))

    def test_파일이_없으면_빈_것(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(TAIWAN_OPEN_DIR=folder):
            self.assertEqual(twopen.sensitive_at("F", 120.5, 23.5), [])


class Grids(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ga.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_GA_방사능은_값_격자_셋(self):
        body = {"features": [{"properties": {"GRAY_INDEX": 1.6198}}, {"properties": {"GRAY_INDEX": 26.74}},
                             {"properties": {"GRAY_INDEX": -3.4e38}}]}
        with mock.patch.object(ga.requests, "get", return_value=answer(body)) as get:
            got = ga.get_feature_info({"layers": "ga:radiometric", "query_layers": "ga:radiometric", "crs": "EPSG:3857",
                                       "bbox": "0,0,1,1", "width": 256, "height": 256, "i": 1, "j": 1})
        self.assertIn("radmap_v4_2019_filtered_ppmth", get.call_args.kwargs["params"]["query_layers"])
        self.assertEqual(ga.friendly(got["features"][0]["properties"]), {"칼륨 (%)": "1.62", "토륨 (ppm)": "26.7"})
        self.assertTrue(ga.queryable("ga:gravity"))

    def test_페루_부게_이상(self):
        body = {"results": [{"attributes": {"Stretch.Pixel Value": "-313.663544"}}]}
        with mock.patch.object(ingemmet, "_get", return_value=answer(body)):
            rows = ingemmet.resource_attributes("ingemmet:bouguer", -12.0, -75.0, 0.01)
        self.assertEqual(ingemmet.resource_friendly("ingemmet:bouguer", rows[0]), {"부게 이상 (mGal)": "-313.7"})
        self.assertTrue(ingemmet.knows_resource("ingemmet:bouguer"))
