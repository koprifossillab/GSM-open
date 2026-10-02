"""달 점묶음 — 몸을 가른다 (devlog 037).

달 좌표를 지구 화면에 그리면 엉뚱한 곳에 뜬다. 지구 화면은 `earth` 만, 달 화면은 `moon` 만.
표고는 달이면 LOLA(`trek`)로 간다. Trek 을 실제로 부르지 않는다.
"""
import json
import re
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from viewer import pointsets, trek
from viewer.models import PointSet, PointSetDeletion

APOLLO = "name,lat,lon\nApollo 11,0.6742,23.4731\nApollo 17,20.1911,30.7723\n"


def upload(client, text, name="apollo.csv", **extra):
    return client.post(reverse("viewer:pointset-upload"),
                       {"file": SimpleUploadedFile(name, text.encode()), **extra})


class Body(TestCase):

    def test_달에서_올리면_달_점묶음이다(self):
        r = upload(self.client, APOLLO, body="moon")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["pointset"]["body"], "moon")
        self.assertEqual(PointSet.objects.get().body, "moon")

    def test_몸을_안_적으면_지구다(self):
        upload(self.client, APOLLO)
        upload(self.client, APOLLO, body="jupiter")          # 모르는 몸 — 화성은 058 에서 몸이 되었다
        self.assertEqual(set(PointSet.objects.values_list("body", flat=True)), {"earth"})

    def test_지구_화면에는_달_점묶음이_없다(self):
        upload(self.client, APOLLO, name="moon.csv", body="moon")
        upload(self.client, APOLLO, name="earth.csv")
        earth = self.client.get(reverse("viewer:pointset-index")).json()["pointsets"]
        moon = self.client.get(reverse("viewer:pointset-index"), {"body": "moon"}).json()["pointsets"]
        self.assertEqual([p["name"] for p in earth], ["earth"])
        self.assertEqual([p["name"] for p in moon], ["moon"])
        for view, want in (("viewer:map", "earth"), ("viewer:map3d", "earth"), ("viewer:moon", "moon")):
            html = self.client.get(reverse(view)).content.decode()
            data = re.search(r'id="pointset-data" type="application/json">(.*?)</script>', html).group(1)
            self.assertEqual([p["name"] for p in json.loads(data)], [want], view)

    def test_지우고_되살려도_달이다(self):
        upload(self.client, APOLLO, body="moon")
        ps = PointSet.objects.get()
        self.client.post(reverse("viewer:pointset-delete", args=[ps.id]))
        gone = PointSetDeletion.objects.get()
        self.assertEqual(gone.body, "moon")
        restored = self.client.post(reverse("viewer:pointset-restore", args=[gone.id])).json()["pointset"]
        self.assertEqual(restored["body"], "moon")

    def test_찍은_점도_몸을_적는다(self):
        r = self.client.post(reverse("viewer:pointset-create"), json.dumps(
            {"name": "착륙지", "body": "moon", "points": [{"lat": 0.67, "lon": 23.47}]}),
            content_type="application/json")
        self.assertEqual(r.json()["pointset"]["body"], "moon")


class LunarParse(TestCase):

    def test_달은_GeoJSON_이_밝힌_지구_평면_좌표계를_듣지_않는다(self):
        doc = {"type": "FeatureCollection",
               "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::5186"}},
               "features": [{"type": "Feature", "properties": {"name": "Tycho"},
                             "geometry": {"type": "Point", "coordinates": [-11.36, -43.31]}}]}
        points, _ = pointsets.parse("tycho.geojson", json.dumps(doc).encode(), lunar=True)
        self.assertEqual((points[0]["lat"], points[0]["lon"]), (-43.31, -11.36))

    def test_달은_고른_평면_좌표계도_듣지_않는다(self):
        points, _ = pointsets.parse("a.csv", APOLLO.encode(), crs_code="5186", lunar=True)
        self.assertAlmostEqual(points[0]["lat"], 0.6742)


class LunarElevation(TestCase):

    def test_달_점묶음의_표고는_LOLA_로(self):
        upload(self.client, APOLLO, body="moon")
        ps = PointSet.objects.get()
        body = {"samples": [{"locationId": 0, "value": "-1931.1875"}, {"locationId": 1, "value": "-2380.5"}]}
        fake = mock.Mock(status_code=200, headers={}, content=b"{}", url="https://trek…", json=lambda: body)
        with mock.patch("viewer.trek.requests.get", return_value=fake) as get, \
                mock.patch("viewer.elevation.elevations") as earth:
            r = self.client.post(reverse("viewer:pointset-elevation", args=[ps.id]))
        self.assertEqual(r.json()["filled"], 2)
        earth.assert_not_called()
        self.assertIn("getSamples", get.call_args[0][0])
        point = ps.points.get(label="Apollo 11")
        self.assertEqual((point.elev, point.elev_source, point.elev_datum),
                         (-1931.2, trek.ELEV_SOURCE, trek.ELEV_DATUM))

    def test_표고가_실린_사본을_되살리면_제_칸으로(self):
        upload(self.client, APOLLO, body="moon")
        ps = PointSet.objects.get()
        ps.points.update(elev=-1931.2, elev_source=trek.ELEV_SOURCE, elev_datum=trek.ELEV_DATUM)
        self.client.post(reverse("viewer:pointset-delete", args=[ps.id]))
        gone = PointSetDeletion.objects.get()
        self.client.post(reverse("viewer:pointset-restore", args=[gone.id]))
        point = PointSet.objects.get().points.first()
        self.assertEqual((point.elev, point.elev_datum), (-1931.2, "moon-sphere"))
