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
