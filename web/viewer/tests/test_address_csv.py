"""주소만 적힌 CSV 를 점묶음으로 (wetherilli 152). 상류를 부르지 않는다 — VWorld 의 답은 2026-10-02 에 받은 꼴이다."""
import json
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import pointsets, usage, views, vworld
from viewer.models import PointSet

CSV = "시료번호,주소,암상\nS1,대전광역시 유성구 과학로 124,화강암\nS2,,편마암\nS3,없는주소 123,사암\n"


def vw(status="OK", point=None, refined=""):
    body = {"status": status}
    if point:
        body["result"] = {"point": {"x": str(point[1]), "y": str(point[0])}}
        body["refined"] = {"text": refined}
    return mock.Mock(status_code=200, url="https://api.vworld.kr/req/address?key=SECRET",
                     json=mock.Mock(return_value={"response": body}))


class Parse(SimpleTestCase):
    def test_위경도가_없고_주소가_있으면_줄들을_돌려준다(self):
        with self.assertRaises(pointsets.NeedsAddresses) as caught:
            pointsets.parse("s.csv", CSV.encode("utf-8"))
        need = caught.exception
        self.assertEqual(need.column, "주소")
        self.assertEqual([r["line"] for r in need.rows], [2, 4])
        self.assertEqual(need.blank, [3])
        self.assertEqual(need.rows[0]["values"]["암상"], "화강암")

    def test_위경도가_있으면_예전대로(self):
        points, _ = pointsets.parse("s.csv", "lat,lon,주소\n36.3,127.3,대전\n".encode("utf-8"))
        self.assertEqual(points[0]["props"]["주소"], "대전")


@override_settings(VWORLD_KEY="test-key")
class Geocode(SimpleTestCase):
    def test_도로명이_없으면_지번으로(self):
        answers = [vw("NOT_FOUND"), vw(point=(36.3789, 127.3610), refined="대전광역시 유성구 가정동 30")]
        with mock.patch.object(vworld.requests, "get", side_effect=answers) as get, \
             mock.patch.object(usage, "record"):
            got = vworld.geocode("대전 유성구 가정동 30")
        self.assertEqual([c.kwargs["params"]["type"] for c in get.call_args_list], ["road", "parcel"])
        self.assertEqual(got, {"lat": 36.3789, "lon": 127.3610, "kind": "parcel", "matched": "대전광역시 유성구 가정동 30"})

    def test_둘_다_없으면_None(self):
        with mock.patch.object(vworld.requests, "get", side_effect=[vw("NOT_FOUND"), vw("NOT_FOUND")]), \
             mock.patch.object(usage, "record"):
            self.assertIsNone(vworld.geocode("없는주소 123"))


@override_settings(VWORLD_KEY="test-key")
class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-geocode-"))
        patch.enable()
        self.addCleanup(patch.disable)
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_올리면_점묶음_대신_줄들(self):
        r = self.client.post(reverse("viewer:pointset-upload"),
                             {"file": SimpleUploadedFile("s.csv", CSV.encode("utf-8"))})
        self.assertEqual(r.status_code, 200)
        job = r.json()["geocode"]
        self.assertEqual((job["column"], len(job["rows"]), job["blank"], job["chunk"]), ("주소", 2, [3], views.GEOCODE_CHUNK))
        self.assertFalse(PointSet.objects.exists())

    @override_settings(VWORLD_KEY="")
    def test_열쇠가_없으면_까닭(self):
        r = self.client.post(reverse("viewer:pointset-upload"),
                             {"file": SimpleUploadedFile("s.csv", CSV.encode("utf-8"))})
        self.assertEqual(r.status_code, 400)
        self.assertIn("VWorld", r.json()["error"])

    def test_달에서는_주소를_찾지_않는다(self):
        r = self.client.post(reverse("viewer:pointset-upload"),
                             {"file": SimpleUploadedFile("s.csv", CSV.encode("utf-8")), "body": "moon"})
        self.assertEqual(r.status_code, 400)

    def test_줄이_많으면_나눠_올리라고(self):
        many = "주소\n" + "".join(f"대전 {i}\n" for i in range(pointsets.MAX_ADDRESS_ROWS + 1))
        r = self.client.post(reverse("viewer:pointset-upload"), {"file": SimpleUploadedFile("m.csv", many.encode())})
        self.assertEqual(r.status_code, 400)

    def _geocode(self, addresses):
        return self.client.post(reverse("viewer:pointset-geocode"), json.dumps({"addresses": addresses}),
                                content_type="application/json")

    def test_좌표를_주고_같은_주소는_다시_묻지_않는다(self):
        with mock.patch.object(vworld, "geocode", side_effect=[{"lat": 36.37, "lon": 127.36, "kind": "road",
                                                                "matched": "과학로 124"}, None]) as geo:
            first = self._geocode(["대전광역시 유성구 과학로 124", "없는주소 123"]).json()
            again = self._geocode(["대전광역시 유성구 과학로 124", "없는주소 123"]).json()
        self.assertEqual(first["results"][0]["lat"], 36.37)
        self.assertIsNone(first["results"][1])
        self.assertEqual(again, first)
        self.assertEqual(geo.call_count, 2)                 # 못 찾은 것도 담아 두어 다시 묻지 않는다

    def test_한_번에_보내는_줄에_한도(self):
        self.assertEqual(self._geocode(["a"] * (views.GEOCODE_CHUNK + 1)).status_code, 400)
        self.assertEqual(self._geocode([]).status_code, 400)

    def test_VWorld_가_거절하면_멈추고_찾은_것까지(self):
        with mock.patch.object(vworld, "geocode", side_effect=[{"lat": 1.0, "lon": 2.0, "kind": "road", "matched": ""},
                                                               vworld.VWorldError("VWorld 가 거절했다: LIMIT")]):
            r = self._geocode(["가", "나", "다"])
        self.assertEqual(r.status_code, 502)
        self.assertEqual(len(r.json()["results"]), 1)

    def test_좌표를_붙인_CSV_를_다시_올리면_점묶음(self):
        fixed = "시료번호,주소,암상,위도,경도,찾은 주소\nS1,대전광역시 유성구 과학로 124,화강암,36.3776,127.3623,과학로 124\n"
        r = self.client.post(reverse("viewer:pointset-upload"),
                             {"file": SimpleUploadedFile("s.csv", fixed.encode("utf-8")), "name": "시료"})
        self.assertEqual(r.status_code, 200)
        ps = PointSet.objects.get()
        point = ps.points.get()
        self.assertEqual((point.label, point.props["찾은 주소"], point.props["암상"]), ("S1", "과학로 124", "화강암"))
