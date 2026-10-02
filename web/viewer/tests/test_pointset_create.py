"""지도에서 찍은 점을 **목록으로 저장하는** 뷰를 시험한다.

파일 업로드와 달리 여기 들어오는 것은 브라우저가 만든 JSON 이라 꼴이 고를
것 같지만, 그렇지 않다. 저장 단추는 사람이 아무 때나 누르고(점이 하나도 없을
때도), 본문은 요청 하나로 얼마든 커질 수 있다. 그래서 **막는 자리마다**
시험을 둔다 — 버릴 좌표, 빈 목록, 못 읽는 본문, 너무 많은 점.

DB 에 행이 **생기는** 것을 보므로 `TestCase` 를 쓴다.
"""
import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from viewer.models import Point, PointSet, Shape


class 점묶음_저장(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("viewer:pointset-create")

    def post(self, payload):
        return self.client.post(
            self.url, json.dumps(payload), content_type="application/json")

    # ── 저장되는 것 ───────────────────────────────────────────────────

    def test_점_두_개를_보내면_점묶음이_생긴다(self):
        response = self.post({"name": "답사 지점", "color": "#112233", "points": [
            {"lat": 36.35, "lon": 127.38, "label": "갑천"},
            {"lat": 37.0, "lon": 128.0, "label": "둘째"},
        ]})
        self.assertEqual(response.status_code, 200)
        body = response.json()["pointset"]
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["name"], "답사 지점")
        self.assertEqual(body["color"], "#112233")

        pointset = PointSet.objects.get(pk=body["id"])
        self.assertEqual(pointset.points.count(), 2)
        first = pointset.points.first()
        self.assertEqual((first.lat, first.lon, first.label),
                         (36.35, 127.38, "갑천"))
        self.assertEqual(Point.objects.count(), 2)

    def test_이름을_안_주면_기본_이름이_붙는다(self):
        response = self.post({"points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["name"], "찍은 점")

    def test_빈_이름도_기본_이름이_붙는다(self):
        response = self.post({"name": "   ",
                              "points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.json()["pointset"]["name"], "찍은 점")

    def test_색을_안_주면_기본_색이_붙는다(self):
        response = self.post({"points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.json()["pointset"]["color"], "#27456f")

    def test_이름표가_200자를_넘으면_잘린다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38, "label": "가" * 250}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Point.objects.get().label, "가" * 200)

    # ── 버리는 것 ─────────────────────────────────────────────────────

    def test_위경도_범위를_벗어난_점은_버리고_나머지만_담는다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38},
            {"lat": 100.0, "lon": 127.38},     # 위도가 90 을 넘는다
            {"lat": 36.0, "lon": 200.0},       # 경도가 180 을 넘는다
            {"lat": 37.0, "lon": 128.0},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 2)
        self.assertEqual(
            sorted(p.lat for p in Point.objects.all()), [36.35, 37.0])

    def test_좌표가_숫자가_아니거나_빠진_점도_버린다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38},
            {"lat": "못읽음", "lon": 127.38},
            {"lon": 127.38},                   # 위도가 없다
            {"lat": None, "lon": None},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 1)

    # ── 막는 것 ───────────────────────────────────────────────────────

    def test_쓸_만한_좌표가_하나도_없으면_막는다(self):
        response = self.post({"points": [
            {"lat": 100.0, "lon": 127.38},
            {"lat": "못읽음", "lon": "못읽음"},
        ]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("쓸 만한 좌표가 없다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)
        self.assertEqual(Point.objects.count(), 0)

    def test_점이_비면_막는다(self):
        response = self.post({"name": "빈 것", "points": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("저장할 점이 없다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_points_가_아예_없어도_막는다(self):
        response = self.post({"name": "빈 것"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("저장할 점이 없다", response.json()["error"])

    def test_본문이_json_이_아니면_막는다(self):
        response = self.client.post(
            self.url, "점이 아니다", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("읽지 못했다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_한_번에_저장할_수_있는_수를_넘으면_막는다(self):
        rows = [{"lat": 36.0 + i / 100, "lon": 127.0} for i in range(3)]
        with patch("viewer.views.MAX_SAVED_POINTS", 2):
            response = self.post({"points": rows})
        self.assertEqual(response.status_code, 400)
        self.assertIn("2점까지", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_한계까지는_저장된다(self):
        rows = [{"lat": 36.0 + i / 100, "lon": 127.0} for i in range(2)]
        with patch("viewer.views.MAX_SAVED_POINTS", 2):
            response = self.post({"points": rows})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 2)

    def test_get_으로_부르면_막는다(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class Download(TestCase):
    """점묶음을 GeoJSON 으로 돌려받는다. 한글 이름이 파일명에서 깨지지 않는다."""

    def setUp(self):
        self.ps = PointSet.objects.create(name="갑천 노두/2026")
        Point.objects.create(pointset=self.ps, lat=36.35, lon=127.38,
                             label="갑천1", props={"암상": "충적층"})

    def url(self, extra=""):
        return f"/GSM/pointsets/{self.ps.id}/geojson/{extra}"

    def test_그냥_부르면_지도가_쓰는_JSON_이다(self):
        response = self.client.get(self.url())
        self.assertNotIn("Content-Disposition", response)
        feature = response.json()["features"][0]
        self.assertEqual(feature["geometry"]["coordinates"], [127.38, 36.35])
        self.assertEqual(feature["properties"]["이름표"], "갑천1")

    def test_download_면_파일로_내려준다(self):
        response = self.client.get(self.url("?download=1"))
        disposition = response["Content-Disposition"]
        self.assertTrue(disposition.startswith("attachment;"))
        self.assertIn(f'filename="pointset-{self.ps.id}.geojson"', disposition)
        # 빗금은 파일명에 못 쓰므로 _ 로 바꾸고, 한글은 RFC 5987 로 적는다
        from urllib.parse import quote
        self.assertIn("filename*=UTF-8''" + quote("갑천 노두_2026.geojson"), disposition)
        self.assertEqual(response.json()["name"], "갑천 노두/2026")

    def test_한글이_이스케이프되지_않는다(self):
        body = self.client.get(self.url("?download=1")).content.decode("utf-8")
        self.assertIn("충적층", body)


class Shapes(TestCase):
    """선·면 — 올린 GeoJSON 과 찍고 잰 것에서 온다. 내려받을 때 그대로 나온다."""

    LINE = {"type": "LineString", "coordinates": [[127.3, 36.3], [127.4, 36.4]]}
    BOX = {"type": "Polygon", "coordinates": [[[127.3, 36.3], [127.4, 36.3], [127.4, 36.4],
                                               [127.3, 36.4], [127.3, 36.3]]]}

    def test_올린_파일의_선_면이_모양으로_담긴다(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        body = json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.3, 36.3]}, "properties": {}},
            {"type": "Feature", "geometry": self.LINE, "properties": {"name": "경로"}},
            {"type": "Feature", "geometry": self.BOX, "properties": {}}]})
        got = self.client.post("/GSM/pointsets/upload/",
                               {"file": SimpleUploadedFile("a.geojson", body.encode())}).json()
        ps = got["pointset"]
        self.assertEqual((ps["count"], ps["lines"], ps["polygons"]), (1, 1, 1))
        feats = self.client.get(f"/GSM/pointsets/{ps['id']}/geojson/").json()["features"]
        self.assertEqual(sorted(f["geometry"]["type"] for f in feats), ["LineString", "Point", "Polygon"])
        line = next(f for f in feats if f["geometry"]["type"] == "LineString")
        self.assertEqual(line["properties"]["이름표"], "경로")

    def test_잡은_범위를_네모_그대로_저장한다(self):
        payload = {"name": "범위", "points": [],
                   "shapes": [{"geometry": self.BOX, "label": "범위 1", "props": {"넓이": "1 km²"}}]}
        got = self.client.post("/GSM/pointsets/create/", json.dumps(payload),
                               content_type="application/json").json()
        self.assertEqual(got["pointset"]["polygons"], 1)
        shape = Shape.objects.get()
        self.assertEqual(shape.label, "범위 1")
        self.assertEqual(shape.props, {"넓이": "1 km²"})
        self.assertAlmostEqual(shape.lat, 36.35)

    def test_이상한_모양은_버린다(self):
        payload = {"points": [{"lat": 36.3, "lon": 127.3}],
                   "shapes": [{"geometry": {"type": "Circle", "coordinates": [1, 2]}},
                              {"geometry": {"type": "LineString", "coordinates": [[999, 1], [2, 3]]}}]}
        got = self.client.post("/GSM/pointsets/create/", json.dumps(payload),
                               content_type="application/json").json()
        self.assertEqual((got["pointset"]["count"], got["pointset"]["lines"]), (1, 0))


class Deletion(TestCase):
    """지우면 기록과 사본이 남고, 잘못 지운 것은 되살린다."""

    def setUp(self):
        from viewer.models import PointSetDeletion  # noqa: F401
        self.ps = PointSet.objects.create(name="현장 A", color="#123456", source_filename="a.csv")
        Point.objects.create(pointset=self.ps, lat=36.3, lon=127.3, label="GS-01", props={"암상": "화강암"})
        Shape.objects.create(pointset=self.ps, kind="line", label="경로",
                             geometry={"type": "LineString", "coordinates": [[127.3, 36.3], [127.4, 36.4]]},
                             lat=36.35, lon=127.35, props={})

    def delete(self):
        return self.client.post(f"/GSM/pointsets/{self.ps.id}/delete/", HTTP_X_REAL_IP="10.0.0.7")

    def test_지우면_기록과_사본이_남는다(self):
        from viewer.models import PointSetDeletion
        self.assertEqual(self.delete().status_code, 200)
        self.assertFalse(PointSet.objects.exists())
        gone = PointSetDeletion.objects.get()
        self.assertEqual((gone.name, gone.client, gone.points, gone.lines), ("현장 A", "10.0.0.7", 1, 1))
        self.assertEqual(len(gone.snapshot["features"]), 2)

    def test_되살리면_그대로_돌아온다(self):
        from viewer.models import PointSetDeletion
        self.delete()
        gone = PointSetDeletion.objects.get()
        got = self.client.post(f"/GSM/pointsets/deleted/{gone.id}/restore/").json()
        self.assertEqual((got["pointset"]["count"], got["pointset"]["lines"]), (1, 1))
        ps = PointSet.objects.get()
        self.assertEqual((ps.name, ps.color), ("현장 A", "#123456"))
        p = ps.points.get()
        self.assertEqual((p.label, p.props), ("GS-01", {"암상": "화강암"}))
        self.assertEqual(ps.shapes.get().label, "경로")

    def test_한_기록은_한_번만_되살린다(self):
        from viewer.models import PointSetDeletion
        self.delete()
        gone = PointSetDeletion.objects.get()
        self.client.post(f"/GSM/pointsets/deleted/{gone.id}/restore/")
        second = self.client.post(f"/GSM/pointsets/deleted/{gone.id}/restore/")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(PointSet.objects.count(), 1)

    def test_목록은_사본을_싣지_않는다(self):
        self.delete()
        row = self.client.get("/GSM/pointsets/deleted/").json()["deleted"][0]
        self.assertEqual(row["name"], "현장 A")
        self.assertNotIn("snapshot", row)

    def test_명령으로도_보고_되살린다(self):
        from io import StringIO

        from django.core.management import call_command

        from viewer.models import PointSetDeletion
        self.delete()
        out = StringIO()
        call_command("deleted_pointsets", stdout=out)
        self.assertIn("현장 A", out.getvalue())
        call_command("deleted_pointsets", restore=PointSetDeletion.objects.get().id, stdout=out)
        self.assertEqual(PointSet.objects.get().points.count(), 1)
