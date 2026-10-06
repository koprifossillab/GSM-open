"""대만 지질운 열린자료 (wetherilli 305) — 받기(`gsmma.fetch_open`)와 받아 둔 파일을 한 덩이로(`twopen`). 상류를 부르지 않는다."""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import gsmma, twopen, usage

SQUARE = {"type": "Polygon", "coordinates": [[[121.0, 24.0], [121.001, 24.0], [121.001, 24.001], [121.0, 24.001], [121.0, 24.0]]]}


def feature(geometry, **props):
    return {"type": "Feature", "geometry": geometry, "properties": props}


def write(folder, api, features):
    Path(folder, f"{api}.geojson").write_text(json.dumps({"type": "FeatureCollection", "fetched": "2026-10-05", "features": features},
                                                         ensure_ascii=False), encoding="utf-8")


class FetchOpen(SimpleTestCase):
    def answer(self, features=None, status=200):
        r = mock.Mock(status_code=status, content=b"{}", elapsed=None)
        r.json.return_value = {"features": features or []}
        return r

    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_끊기면_넷으로_나누고_겹친_것은_하나로(self):
        shared = feature({"type": "Point", "coordinates": [121.0, 24.0]}, CGPS_ID="GS01")
        calls = []

        def get(url, params, **kw):
            calls.append(params["bbox"])
            if len(calls) == 1:
                raise requests.Timeout("120 초")
            return self.answer([shared])
        with mock.patch.object(gsmma.requests, "get", side_effect=get):
            got = gsmma.fetch_open("CGPS", sleep=lambda s: None)
        self.assertEqual(len(calls), 5)
        self.assertEqual(got, [shared])                              # 네 네모가 모두 같은 것을 주어도 하나

    def test_나눠도_끊기면_구멍으로_적고_넘어간다(self):
        holes = []
        with mock.patch.object(gsmma.requests, "get", side_effect=requests.Timeout("120 초")), \
             mock.patch.object(gsmma, "OPEN_SPLITS", 1):
            got = gsmma.fetch_open("RockFall", sleep=lambda s: None, holes=holes)
        self.assertEqual((got, len(holes)), ([], 4))
        with mock.patch.object(gsmma.requests, "get", side_effect=requests.Timeout("120 초")), \
             mock.patch.object(gsmma, "OPEN_SPLITS", 0), self.assertRaises(gsmma.GsmmaError):
            gsmma.fetch_open("RockFall", sleep=lambda s: None)       # 구멍을 받을 곳이 없으면 오류

    def test_차단이면_멈춘다(self):
        with mock.patch.object(gsmma.requests, "get", return_value=self.answer(status=429)), \
             mock.patch.object(usage, "looks_blocked", return_value=True), self.assertRaises(gsmma.GsmmaError):
            gsmma.fetch_open("CGPS", sleep=lambda s: None)


class Body(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-twopen-")
        patch = override_settings(TAIWAN_OPEN_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        twopen.forget()
        self.addCleanup(twopen.forget)
        write(self.dir, "DebrisFlowDeposition", [feature(SQUARE, PROT_TARG="C3住宅聚落多於十棟", IDENTIFIER="許晉耀")])
        write(self.dir, "DebrisFlowFan", [feature(SQUARE, FAN_AREA=9.32, SITECHECK="N無")])
        write(self.dir, "DebrisFlowTrack", [])
        write(self.dir, "RockMassClassification", [feature(SQUARE, **{"強度分級": "III", "ST_C": "沖積層", "LITH_C": None})])

    def test_토석류는_갈래_셋을_한_레이어에(self):
        data = json.loads(twopen.body("gsmma:open:debris"))
        self.assertEqual([f["properties"]["code"] for f in data["features"]], ["DebrisFlowDeposition", "DebrisFlowFan"])
        self.assertEqual([r["code"] for r in data["legend"]], ["DebrisFlowDeposition", "DebrisFlowFan"])   # 없는 갈래는 범례에 없다
        self.assertEqual(data["features"][1]["properties"]["FAN_AREA"], "9.32")
        self.assertEqual(data["labels"]["PROT_TARG"], "보호 대상")
        en = json.loads(twopen.body("gsmma:open:debris", "en"))
        self.assertEqual(en["labels"]["PROT_TARG"], "Protected targets")
        self.assertEqual(en["legend"][0]["label"], "Debris-flow deposition zone")

    def test_암체_등급은_차례_색이고_짐작이라고_적는다(self):
        """I 이 단단한 쪽 — 지질운이 적은 뜻이 아니라 암상으로 짐작한 차례다 (wetherilli 370)"""
        write(self.dir, "RockMassClassification", [
            feature(SQUARE, **{"強度分級": "III", "ST_C": "沖積層", "LITH_C": None, "CHAR_C": "厚層粉砂岩層"}),
            feature(SQUARE, **{"強度分級": "I", "LITH_C": "安山岩"}),
            feature(SQUARE, **{"強度分級": "VII", "LITH_C": "頁岩"}),
            feature(SQUARE, **{"強度分級": None, "LITH_C": "水體"})])
        twopen.forget()
        data = json.loads(twopen.body("gsmma:open:rockmass"))
        props = data["features"][0]["properties"]
        self.assertEqual((props["code"], props["color"], props["CHAR_C"]), ("III", twopen.ROCKMASS["III"], "厚層粉砂岩層"))
        self.assertNotIn("LITH_C", props)                              # 빈 값은 싣지 않는다
        self.assertEqual(props["order"], "I 단단 → VII 무름 (암상으로 짐작)")
        self.assertNotIn("order", data["features"][3]["properties"])   # 등급 없는 면에는 풀이도 없다
        self.assertEqual(list(data["labels"])[:2], ["強度分級", "order"])   # 등급 바로 밑
        legend = {r["code"]: r["label"] for r in data["legend"]}
        self.assertEqual(legend, {"I": "등급 I — 가장 단단한 쪽 (암상으로 짐작)", "III": "등급 III",
                                  "VII": "등급 VII — 가장 무른 쪽 (암상으로 짐작)", "?": "등급 없음"})
        # 차례 색 — I 이 가장 진하고 VII 이 가장 옅다
        light = [sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in twopen.ROCKMASS.values()]
        self.assertEqual(light, sorted(light))
        en = json.loads(twopen.body("gsmma:open:rockmass", "en"))
        self.assertEqual((en["labels"]["order"], en["labels"]["CHAR_C"]), ("Class order", "Characteristics"))
        self.assertIn("inferred from lithology", en["features"][0]["properties"]["order"])

    def test_화면과_주소(self):
        call_command("seed_catalog", stdout=io.StringIO())
        r = self.client.get("/GSM/points/", {"layer": "gsmma:open:debris"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["features"]), 2)
        self.assertEqual(self.client.get("/GSM/points/", {"layer": "gsmma:open:cgps"}).status_code, 503)   # 받지 않은 것
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual((rows["gsmma:open:rockmass"]["kind"], rows["gsmma:open:rockmass"]["style"]), ("points", "unit"))
        self.assertTrue(rows["gsmma:open:coal"]["verified"])

    def test_받기_명령은_구멍을_파일에_적는다(self):
        def fake(api, gap, log, holes):
            holes.append([121.75, 24.75, 122.06, 25.13])
            return [feature({"type": "Point", "coordinates": [121.5, 25.0]}, CGPS_ID="GS01")]
        with mock.patch.object(gsmma, "fetch_open", side_effect=fake):
            call_command("fetch_taiwan_open", api="CGPS", stdout=io.StringIO())
        saved = json.loads(Path(self.dir, "CGPS.geojson").read_text(encoding="utf-8"))
        self.assertEqual((len(saved["features"]), saved["holes"]), (1, [[121.75, 24.75, 122.06, 25.13]]))


class Holes(TestCase):
    """구멍만 다시 받기 (wetherilli 328) — 더 잘게 나눠 받은 것을 보태고, 남은 작은 구멍을 다시 적는다"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-twopen-holes-")
        patch = override_settings(TAIWAN_OPEN_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        old = feature({"type": "Point", "coordinates": [121.0, 24.0]}, ACTIVITY="A新崩塌")
        Path(self.dir, "RockFall.geojson").write_text(json.dumps({"type": "FeatureCollection", "fetched": "2026-10-05",
                                                                  "holes": [[120.7, 22.5, 120.8, 22.6]], "features": [old]},
                                                                 ensure_ascii=False), encoding="utf-8")
        self.old = old

    def test_보태고_남은_구멍을_적는다(self):
        new = feature({"type": "Point", "coordinates": [120.75, 22.55]}, ACTIVITY="B偶爾")

        def fake(api, box, gap, log, holes, splits):
            self.assertEqual((api, box, splits), ("RockFall", (120.7, 22.5, 120.8, 22.6), 3))
            holes.append([120.70, 22.55, 120.71, 22.56])
            return [self.old, new]                                 # 이미 있는 것은 한 번만
        with mock.patch.object(gsmma, "fetch_open", side_effect=fake):
            call_command("fetch_taiwan_open", api="RockFall", holes=True, stdout=io.StringIO())
        saved = json.loads(Path(self.dir, "RockFall.geojson").read_text(encoding="utf-8"))
        self.assertEqual(len(saved["features"]), 2)
        self.assertEqual(saved["holes"], [[120.70, 22.55, 120.71, 22.56]])
        self.assertIn("holes_refetched", saved)

    def test_나누기_횟수를_넘겨받는다(self):
        calls = []

        def get(url, params, **kw):
            calls.append(params["bbox"])
            raise requests.Timeout("120 초")
        holes = []
        with mock.patch.object(gsmma.requests, "get", side_effect=get), \
             mock.patch.object(usage, "record"), mock.patch.object(usage, "paused", return_value=0):
            gsmma.fetch_open("RockFall", (120.7, 22.5, 120.8, 22.6), sleep=lambda s: None, holes=holes, splits=1)
        self.assertEqual((len(calls), len(holes)), (5, 4))         # 한 번 나눈 넷이 다 끊기면 구멍 넷
