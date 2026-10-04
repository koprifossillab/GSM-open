"""시료 지점의 VWorld 둘레 (074) — 도로명·지번·읍면동·가장 가까운 단층·둘레 지명.

상류는 부르지 않는다 — `vworld._get` 을 갈아 끼워 자료 이름마다 정해 둔 것을 준다.
"""
import json
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import vworld
from viewer.models import Point, PointSet, PointSetDeletion

KIGAM = (36.376, 127.366)


def fake_get(url, params):
    if url == vworld.ADDRESS_URL:
        return [{"type": "road", "text": "대전광역시 유성구 과학로 124"},
                {"type": "parcel", "text": "대전광역시 유성구 가정동 30"}]
    data = params.get("data")
    if data == "LT_C_ADEMD_INFO":
        return {"featureCollection": {"features": [{"properties": {"full_nm": "대전광역시 유성구 가정동"}}]}}
    if data == "LT_L_GIMSFAULT":
        # 동쪽 0.01° (≈ 896 m) 에 남북으로 선 단층 하나, 멀리 하나
        lon = KIGAM[1] + 0.01
        return {"featureCollection": {"features": [
            {"geometry": {"type": "MultiLineString", "coordinates": [[[lon, 36.3], [lon, 36.5]]]}},
            {"geometry": {"type": "LineString", "coordinates": [[127.6, 36.3], [127.6, 36.5]]}}]}}
    if data == "LT_P_NSNMSSITENM":
        return {"featureCollection": {"features": [
            {"geometry": {"type": "Point", "coordinates": [KIGAM[1], KIGAM[0] + 0.009]},
             "properties": {"land_kpyo": "유디미"}},
            {"geometry": {"type": "Point", "coordinates": [KIGAM[1], KIGAM[0] + 0.015]},
             "properties": {"land_kpyo": "먼골"}}]}}
    if data in vworld.PROTECTED or data == "LP_PA_CBND_BUBUN":
        return {}               # 보호구역 밖, 필지 모름 (wetherilli 173 — 아래 `Land` 가 따로 본다)
    raise AssertionError(data)


class Facts(SimpleTestCase):
    def test_넷을_모은다(self):
        with patch.object(vworld, "_get", fake_get), patch.object(vworld.usage, "record"):
            got = vworld.point_facts(*KIGAM)
        self.assertEqual(got["road"], "대전광역시 유성구 과학로 124")
        self.assertEqual(got["emd"], "대전광역시 유성구 가정동")
        self.assertAlmostEqual(got["fault_m"], 896, delta=5)
        self.assertEqual(got["place"], "유디미")
        self.assertAlmostEqual(got["place_m"], 995, delta=5)

    def test_하나가_실패해도_나머지(self):
        def half(url, params):
            if params.get("data") == "LT_L_GIMSFAULT":
                raise vworld.VWorldError("x")
            return fake_get(url, params)
        with patch.object(vworld, "_get", half), patch.object(vworld.usage, "record"):
            got = vworld.point_facts(*KIGAM)
        self.assertNotIn("fault_m", got)
        self.assertIn("emd", got)

    def test_다_실패하면_오류(self):
        def fail(url, params):
            raise vworld.VWorldError("x")
        with patch.object(vworld, "_get", fail), patch.object(vworld.usage, "record"):
            with self.assertRaises(vworld.VWorldError):
                vworld.point_facts(*KIGAM)

    def test_한국_둘레(self):
        self.assertTrue(vworld.in_korea(*KIGAM))
        self.assertFalse(vworld.in_korea(-62.2, -58.8))


def feats(*props):
    return {"featureCollection": {"features": [{"properties": p} for p in props]}}


class Land(SimpleTestCase):
    """보호구역·지목·소유구분 (wetherilli 173). 2026-10-02 에 설악산 대청봉에서 받은 꼴을 옮겼다"""

    def got(self, ned=None, extra=None):
        table = {"LT_C_WGISNPGUG": feats({"park_name": "설악산"}),
                 "LT_C_UO301": feats({"uname": "국가지정문화재구역", "remark": "설악산천연보호구역", "alias": "천연기념물 제171호"}),
                 "LT_C_UF901": feats({"uname": "핵심구역"}, {"uname": "백두대간보호지역"}),
                 "LT_C_UQ114": feats({"uname": "자연환경보전지역"}),
                 "LP_PA_CBND_BUBUN": feats({"pnu": "5183031021200010000"})}
        table.update(extra or {})

        def get(url, params):
            return table[params["data"]] if params.get("data") in table else fake_get(url, params)
        ned = ned or {"ladfrlVOList": {"ladfrlVOList": [{"lndcgrCodeNm": "임야", "posesnSeCodeNm": "국유지",
                                                         "cnrsPsnCo": "0"}], "error": ""}}
        counted = []
        with patch.object(vworld, "_get", get), patch.object(vworld, "_ned", lambda url, params: ned), \
                patch.object(vworld.usage, "record", lambda *a, **k: counted.append(k)):
            return vworld.point_facts(*KIGAM), counted

    def test_넷의_이름을_잇는다(self):
        got, _ = self.got()
        self.assertEqual(got["protected"], "국립공원 설악산 · 국가지정문화재구역 설악산천연보호구역(천연기념물 제171호)"
                                           " · 백두대간보호지역 핵심구역 · 자연환경보전지역")

    def test_지목과_소유구분(self):
        got, _ = self.got()
        self.assertEqual((got["jimok"], got["owner"]), ("임야", "국유지"))

    def test_소유자_이름은_싣지_않는다(self):
        got, _ = self.got()
        self.assertFalse({"cnrsPsnCo", "posesnSeCode"} & set(got))

    def test_토지는_두_번으로_센다(self):
        _, counted = self.got()
        self.assertEqual(counted, [{"ok": True, "count": 10}])

    def test_대장이_거절하면_토지만_빠진다(self):
        got, counted = self.got(ned={"ladfrlVOList": {"error": "INVALID_KEY", "message": "x"}})
        self.assertNotIn("jimok", got)
        self.assertIn("protected", got)
        self.assertIn({"ok": False, "count": 2}, counted)

    def test_보호구역_밖이면_빠진다(self):
        got, _ = self.got(extra={d: {} for d in vworld.PROTECTED})
        self.assertNotIn("protected", got)

    def test_되살리면_제_칸으로(self):
        from viewer import pointsets, views
        place = {"protected": "자연환경보전지역", "jimok": "임야", "owner": "국유지"}
        props = views._place_props(place)
        self.assertEqual(props["지목(VWorld)"], "임야")
        self.assertEqual(pointsets._place_from(dict(props)), place)


@override_settings(VWORLD_KEY="test")
class Fill(TestCase):
    def setUp(self):
        self.ps = PointSet.objects.create(name="야장")
        Point.objects.create(pointset=self.ps, lat=KIGAM[0], lon=KIGAM[1], label="S1")
        Point.objects.create(pointset=self.ps, lat=-62.2, lon=-58.8, label="세종")

    def test_한국_점만_채우고_GeoJSON_에_싣는다(self):
        with patch.object(vworld, "_get", fake_get):
            r = self.client.post(f"/GSM/pointsets/{self.ps.id}/places/")
        self.assertEqual(r.json()["filled"], 1)
        self.assertEqual(r.json()["pointset"]["placed"], 1)
        feats = self.client.get(f"/GSM/pointsets/{self.ps.id}/geojson/").json()["features"]
        props = {f["properties"]["이름표"]: f["properties"] for f in feats}
        self.assertEqual(props["S1"]["읍면동(VWorld)"], "대전광역시 유성구 가정동")
        self.assertAlmostEqual(props["S1"]["가까운 단층(VWorld, m)"], 896, delta=5)
        self.assertEqual(props["S1"]["둘레 지명(VWorld)"], "유디미 · 995 m")
        self.assertNotIn("읍면동(VWorld)", props["세종"])

    def test_되살리면_제_칸으로(self):
        with patch.object(vworld, "_get", fake_get):
            self.client.post(f"/GSM/pointsets/{self.ps.id}/places/")
        before = Point.objects.get(label="S1").place
        self.client.post(f"/GSM/pointsets/{self.ps.id}/delete/")
        self.client.post(f"/GSM/pointsets/deleted/{PointSetDeletion.objects.get().id}/restore/")
        p = Point.objects.get(label="S1")
        self.assertEqual(p.props, {})
        self.assertEqual({k: v for k, v in p.place.items()},
                         {k: v for k, v in before.items() if k != "at"})

    def test_찍어_저장하면_곧바로_채운다(self):
        with patch.object(vworld, "_get", fake_get):
            r = self.client.post("/GSM/pointsets/create/", json.dumps(
                {"name": "찍은 점", "points": [{"lat": KIGAM[0], "lon": KIGAM[1], "label": "a"}]}),
                content_type="application/json")
        self.assertEqual(r.json()["pointset"]["placed"], 1)

    def test_열쇠가_없으면_묻지_않는다(self):
        with override_settings(VWORLD_KEY=""), patch.object(vworld, "_get") as get:
            r = self.client.post("/GSM/pointsets/create/", json.dumps(
                {"name": "찍은 점", "points": [{"lat": KIGAM[0], "lon": KIGAM[1], "label": "a"}]}),
                content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.client.post(f"/GSM/pointsets/{self.ps.id}/places/").status_code, 503)
        get.assert_not_called()

    def test_VWorld_가_실패해도_저장은_된다(self):
        def fail(url, params):
            raise vworld.VWorldError("x")
        with patch.object(vworld, "_get", fail):
            r = self.client.post("/GSM/pointsets/create/", json.dumps(
                {"name": "찍은 점", "points": [{"lat": KIGAM[0], "lon": KIGAM[1], "label": "a"}]}),
                content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.client.post(f"/GSM/pointsets/{self.ps.id}/places/").status_code, 502)
