"""phyloserver — 연구실의 암맥 기록을 받는 문 (devlog 026).

phyloserver 를 실제로 부르지 않는다. 기록의 꼴은 2026-09-28 에
`/dikesync/dike-records/?format=json` 이 준 그대로다.
"""
import json
import os
import tempfile
import time
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import phyloserver, tilecache, views
from viewer.models import Layer, LayerGroup


def record(pk=6227, **over):
    row = {"id": pk, "unique_id": "1hR3eeNqHb", "symbol": "Jkad", "stratum": "산성암맥",
           "rock_type": "산성암", "era": "중생대", "map_sheet": "홍천",
           "address": "강원특별자치도 홍천군 영귀미면 덕치리 413", "distance": 140.0,
           "angle": 233.29999999999995, "angle_from_endpoints": 51.234,
           "lat_1": 37.71266227013399, "lng_1": 127.92837603867402,
           "lat_2": 37.7135, "lng_2": 127.9297, "memo": None, "is_deleted": False}
    row.update(over)
    return row


def reply(rows, status=200):
    return mock.Mock(status_code=status, json=lambda: rows)


class RockClass(SimpleTestCase):
    def test_갈래_낱말을_먼저_믿는다(self):
        self.assertEqual(phyloserver.rock_class("산성암 규장암 석영맥"), "acid")
        self.assertEqual(phyloserver.rock_class("염기성암맥류: 섬록암 및 빈암"), "basic")
        self.assertEqual(phyloserver.rock_class("엽기성암맥"), "basic")      # 적을 때의 오타
        self.assertEqual(phyloserver.rock_class("맥암류: 준성암"), "intermediate")

    def test_석영은_홀로면_맥이고_반암이면_산성이다(self):
        self.assertEqual(phyloserver.rock_class("석영"), "vein")
        self.assertEqual(phyloserver.rock_class("석영맥"), "vein")
        self.assertEqual(phyloserver.rock_class("석영반암"), "acid")
        self.assertEqual(phyloserver.rock_class("석영, 화강암, 반화강암(aplite) 및 규장암"), "acid")

    def test_섞인_이름은_염기성이_먼저다(self):
        self.assertEqual(phyloserver.rock_class("반암과 황반암"), "basic")

    def test_이름이_없으면_지층을_본다(self):
        self.assertEqual(phyloserver.rock_class("", "경상계 불국사층군 산성암맥"), "acid")
        self.assertEqual(phyloserver.rock_class("반암"), "other")


@override_settings(PHYLOSERVER_URL="http://phylo.test")
class Feature(SimpleTestCase):
    def test_끝점이_둘이면_선이고_주향을_싣는다(self):
        f = phyloserver.dike_feature(record())
        self.assertEqual(f["geometry"]["type"], "LineString")
        self.assertEqual(f["geometry"]["coordinates"][0], [127.92838, 37.71266])
        self.assertEqual(f["properties"]["strike"], 51.2)
        self.assertEqual(f["properties"]["cls"], "acid")
        self.assertEqual(f["properties"]["link"], "http://phylo.test/dikesync/web/dike-records/6227/")
        self.assertNotIn("memo", f["properties"])                       # 빈 값은 뺀다

    def test_끝점이_하나면_점이고_주향이_없다(self):
        f = phyloserver.dike_feature(record(lat_2=None, lng_2=None, angle_from_endpoints=None))
        self.assertEqual(f["geometry"]["type"], "Point")
        self.assertNotIn("strike", f["properties"])

    def test_들어온_angle_은_쓰지_않는다(self):
        f = phyloserver.dike_feature(record(angle_from_endpoints=None))
        self.assertNotIn("strike", f["properties"])

    def test_지운_기록과_좌표가_틀린_기록은_버린다(self):
        self.assertIsNone(phyloserver.dike_feature(record(is_deleted=True)))
        self.assertIsNone(phyloserver.dike_feature(record(lat_1=0, lng_1=0)))
        self.assertIsNone(phyloserver.dike_feature(record(lat_1=127.9, lng_1=37.7)))   # 뒤바뀐 것

    def test_끝점만_틀리면_점으로_남긴다(self):
        f = phyloserver.dike_feature(record(lat_2=0, lng_2=0))
        self.assertEqual(f["geometry"]["type"], "Point")


@override_settings(PHYLOSERVER_URL="http://phylo.test")
class Fetch(SimpleTestCase):
    def test_한_번에_받고_읽기만_한다(self):
        with mock.patch.object(phyloserver.requests, "get",
                               return_value=reply([record(1), record(2, is_deleted=True)])) as get, \
                mock.patch.object(phyloserver.usage, "record"):
            got = phyloserver.fetch(phyloserver.DIKES)
        self.assertEqual(len(got), 1)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], "http://phylo.test/dikesync/dike-records/?format=json")
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], "GSM/0.1")

    def test_목록이_아니면_오류다(self):
        with mock.patch.object(phyloserver.requests, "get", return_value=reply({"results": []})), \
                mock.patch.object(phyloserver.usage, "record"):
            with self.assertRaises(phyloserver.PhyloserverError):
                phyloserver.fetch(phyloserver.DIKES)

    @override_settings(PHYLOSERVER_URL="")
    def test_주소가_없으면_부르지_않는다(self):
        with mock.patch.object(phyloserver.requests, "get") as get:
            with self.assertRaises(phyloserver.PhyloserverError):
                phyloserver.fetch(phyloserver.DIKES)
        get.assert_not_called()


class View(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(TILE_CACHE_DIR=self.tmp.name, PHYLOSERVER_URL="http://phylo.test")
        patcher.enable()
        self.addCleanup(patcher.disable)
        group = LayerGroup.objects.create(name="커스텀 지질도", region="korea")
        Layer.objects.create(name=phyloserver.DIKES, title="암맥 기록", group=group, upstream="phyloserver")

    def get(self, rows):
        with mock.patch.object(phyloserver.requests, "get", return_value=reply(rows)) as get, \
                mock.patch.object(phyloserver.usage, "record"):
            response = self.client.get("/GSM/points/", {"layer": phyloserver.DIKES})
        return response, get

    def test_한_덩이로_준다(self):
        response, _ = self.get([record(1)])
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["style"], "dike")
        self.assertEqual(data["labels"]["strike"], "주향 (끝점에서 잰 값)")
        self.assertEqual(len(data["features"]), 1)

    def test_하루가_지나면_다시_묻는다(self):
        self.get([record(1)])
        _, get = self.get([record(1)])
        get.assert_not_called()                                         # 캐시에서
        key = views._point_key(phyloserver.DIKES)
        path = tilecache._path(key, ".json")
        old = time.time() - phyloserver.FRESH_SECONDS - 60
        os.utime(path, (old, old))
        _, get = self.get([record(1), record(2)])
        self.assertEqual(get.call_count, 1)

    def test_phyloserver_가_못_주면_옛것을_낸다(self):
        self.get([record(1)])
        path = tilecache._path(views._point_key(phyloserver.DIKES), ".json")
        old = time.time() - phyloserver.FRESH_SECONDS - 60
        os.utime(path, (old, old))
        with mock.patch.object(phyloserver.requests, "get", return_value=reply(None, status=502)), \
                mock.patch.object(phyloserver.usage, "record"):
            response = self.client.get("/GSM/points/", {"layer": phyloserver.DIKES})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)["features"]), 1)

    def test_카탈로그에서_점_레이어로_선다(self):
        row = next(l for g in views._catalog() for l in g["layers"] if l["name"] == phyloserver.DIKES)
        self.assertEqual(row["kind"], "points")
        self.assertEqual(row["style"], "dike")
        self.assertFalse(row["queryable"])


class ScanTile(TestCase):
    """한반도 지질도 — 카카오 격자 타일을 번호 그대로 중계한다."""

    def setUp(self):
        patcher = override_settings(PHYLOSERVER_URL="http://phylo.test")
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_격자_밖은_묻지_않는다(self):
        name = "phyloserver:peninsula"
        self.assertTrue(phyloserver.valid_scan_tile(name, 13, 1, 4))
        self.assertFalse(phyloserver.valid_scan_tile(name, 13, 2, 0))          # 가로 2 장뿐
        self.assertTrue(phyloserver.valid_scan_tile(name, 7, 127, 319))
        self.assertFalse(phyloserver.valid_scan_tile(name, 6, 0, 0))
        with mock.patch.object(phyloserver.requests, "get") as get:
            response = self.client.get("/GSM/phyloserver/peninsula/13/2_0.png")
        self.assertEqual(response.status_code, 404)
        get.assert_not_called()

    def test_번호_그대로_넘긴다(self):
        png = b"\x89PNG fake"
        resp = mock.Mock(status_code=200, content=png, headers={"Content-Type": "image/png"})
        with mock.patch.object(phyloserver.requests, "get", return_value=resp) as get, \
                mock.patch.object(phyloserver.usage, "record"):
            response = self.client.get("/GSM/phyloserver/peninsula/9/12_34.png")
        self.assertEqual(response.content, png)
        self.assertEqual(get.call_args.args[0], "http://phylo.test/media/geolmap/map_tiles/9/12_34.png")

    def test_없는_자리는_투명한_타일이다(self):
        with mock.patch.object(phyloserver.requests, "get", return_value=mock.Mock(status_code=404)), \
                mock.patch.object(phyloserver.usage, "record"):
            response = self.client.get("/GSM/phyloserver/peninsula/13/0_0.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, views.tiles.blank_tile(256, 256))

    def test_범례는_KIGAM_에_묻지_않는다(self):
        with mock.patch.object(views.kigam, "get_legend") as legend:
            response = self.client.get("/GSM/legend/", {"layer": "phyloserver:peninsula"})
        self.assertEqual(response.status_code, 404)
        legend.assert_not_called()
