"""오프라인 묶음(.gsmpack) — GSM 안의 소스로 박스 굽기, 목록·내려받기 (wetherilli 381). 상류를 부르지 않는다.

꼴·자르기·예산·굽는 고리 자체의 시험은 패키지에 있다(`tools/gsmpack/tests`, wetherilli P16)."""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from PIL import Image

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from gsmpack import bake, format as offlinepack, grid
from viewer import kigam, tilegrid, vworld
from viewer.management.commands import build_offline_pack
from viewer.models import Layer, LayerGroup


def png(alpha=255, size=512):
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), (200, 100, 50, alpha)).save(buf, format="PNG")
    return buf.getvalue()


BOX = {"_note": "시험", "tiny": {"title": "작은 박스", "region": "korea", "bbox": [129.0, 37.0, 129.05, 37.05],
                                 "layers": {"L_50K_Geology_Map": [10, 12], "vworld:Base": [10, 12]},
                                 "units": ["L_50K_Geology_Map"], "budget_mb": 200}}

UNITS = {"features": [
    {"id": "l_50k_geology_litho_latest.7", "geometry": {"type": "MultiPolygon", "coordinates": [[[
        [129.0, 37.0], [129.05, 37.0], [129.05, 37.05], [129.0, 37.05], [129.0, 37.0]]]]},
     "properties": {"시대": "현생누대 고생대 캄브리아기", "지층": "풍촌석회암층", "기호": "CEp", "설명": None,
                    "도폭": '장성[1967]<a href="https://doi.org/10.22747/x">(수치지질도)</a>'}},
    {"id": "l_50k_geology_litho_latest.8", "geometry": {"type": "Polygon", "coordinates": [
        [[129.0123456789, 37.0], [129.02, 37.0], [129.02, 37.01], [129.0123456789, 37.0]]]},
     "properties": {"지층": "화절층", "기호": "CEw"}},
    {"id": "l_50k_geology_boundary_latest.1", "geometry": {"type": "MultiLineString", "coordinates": [[[129, 37], [129.1, 37]]]},
     "properties": {"유형": "지질경계"}}]}


class Build(TestCase):
    """가짜 타일로 굽고 다시 읽는다 — 상류를 부르지 않는다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.boxes = root / "boxes.json"
        self.boxes.write_text(json.dumps(BOX), encoding="utf-8")
        group = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만 지질도", group=group, upstream="kigam")
        self.settings = override_settings(OFFLINE_BOXES_FILE=self.boxes, OFFLINE_DIR=str(root / "offline"),
                                          TILE_CACHE_DIR=str(root / "tiles"), VWORLD_KEY="SECRET-VW", KIGAM_KEY="SECRET-KG")
        self.settings.enable()
        self.kigam_calls = []
        self.info_calls = []
        patches = [
            mock.patch.object(build_offline_pack.KigamSource, "fetch", lambda s, z, x, y: self.kigam_calls.append(z) or png()),
            # 바다처럼 자료 밖(투명)도 하나 섞는다 — 넣지 않아야 한다
            mock.patch.object(vworld, "get_wmts_tile", lambda layer, z, y, x: None if (x + y) % 5 == 0 else (b"\x89PNG-vw" * 100, "image/png")),
            mock.patch.object(kigam, "has_key", lambda: True),
            mock.patch.object(kigam, "describe_layer", lambda name: ["geoOpen:l_50k_geology_litho_latest",
                                                                      "geoOpen:l_50k_geology_fault_latest"]),
            mock.patch.object(kigam, "wfs_in_bbox", lambda t, bbox: self.info_calls.append((t, bbox)) or UNITS),
            mock.patch.object(build_offline_pack.time, "sleep", lambda s: None),
            mock.patch.object(bake.time, "sleep", lambda s: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.settings.disable()
        self.tmp.cleanup()

    def build(self, *args):
        out = io.StringIO()
        call_command("build_offline_pack", "tiny", *args, stdout=out, stderr=io.StringIO())
        return out.getvalue()

    def test_굽고_다시_읽기(self):
        self.build()
        packs = list(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        self.assertEqual(len(packs), 1)
        head, _ = offlinepack.read_header(packs[0])
        self.assertEqual(head["layers"]["L_50K_Geology_Map"]["zooms"], [9, 11])     # 512 px 격자 — 화면 줌보다 하나 작다
        self.assertEqual(head["layers"]["L_50K_Geology_Map"]["tile_size"], 512)
        self.assertEqual(head["layers"]["vworld:Base"]["zooms"], [10, 12])
        self.assertEqual(head["dropped"], {})
        key = next(k for k in head["tiles"] if k.startswith("L_50K_Geology_Map/11/"))
        # 작은 박스라 타일이 다 가장자리다 — 박스 밖은 비우고 안은 받은 그림 그대로 (wetherilli 385)
        image = Image.open(io.BytesIO(offlinepack.read_tile(packs[0], key))).convert("RGBA")
        self.assertIn((200, 100, 50, 255), [c for _, c in image.getcolors(512 * 512)])
        # 자료 밖의 VWorld 칸은 넣지 않는다
        for k in head["tiles"]:
            if k.startswith("vworld:Base/"):
                z, x, y = (int(v) for v in k.split("/")[1:])
                self.assertNotEqual((x + y) % 5, 0)
        # 다 구우면 받다 둔 VWorld 를 지운다
        self.assertEqual(list(Path(settings.OFFLINE_DIR).glob(".*parts*")), [])

    def test_지층_면을_담는다(self):
        """누른 자리의 속성은 박스 범위의 지층 면(WFS)으로 — 면만, 속성은 서버처럼 추려서 (wetherilli 384)"""
        self.build()
        path = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        head, base = offlinepack.read_header(path)
        units = head["units"]["L_50K_Geology_Map"]
        self.assertEqual(units["key"], "@units/L_50K_Geology_Map")
        self.assertEqual(units["types"], ["geoOpen:l_50k_geology_litho_latest"])          # 지층(litho)만 — 단층은 아니다
        self.assertEqual(self.info_calls, [("geoOpen:l_50k_geology_litho_latest", (129.0, 37.0, 129.05, 37.05))])
        shapes = json.loads(offlinepack.read_tile(path, units["key"], (head, base)))
        self.assertEqual(len(shapes["features"]), 2)                                       # 선은 버린다
        first = shapes["features"][0]["properties"]
        self.assertEqual(first["props"]["지층"], "풍촌석회암층")
        self.assertNotIn("설명", first["props"])                                            # 빈 값은 버린다
        self.assertEqual(first["props"]["도폭"]["links"][0]["url"], "https://doi.org/10.22747/x")   # 링크는 갈라 둔다
        self.assertIn("props_en", first)
        self.assertEqual(shapes["features"][1]["geometry"]["coordinates"][0][0], [129.01235, 37.0])   # 소수 다섯 자리

    def test_머리에_키가_없다(self):
        self.build()
        raw = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack")).read_bytes()
        self.assertNotIn(b"SECRET", raw)

    def test_어림만(self):
        text = self.build("--dry-run")
        self.assertIn("어림", text)
        self.assertEqual(self.kigam_calls, [])
        self.assertFalse(Path(settings.OFFLINE_DIR).exists() and any(Path(settings.OFFLINE_DIR).iterdir()))

    def test_예산을_넘으면_뒤의_레이어부터_줌을_던다(self):
        BOX_SMALL = json.loads(json.dumps(BOX))
        BOX_SMALL["tiny"]["budget_mb"] = 0.05           # 50 KB 남짓 — 줌을 덜어야 한다
        self.boxes.write_text(json.dumps(BOX_SMALL), encoding="utf-8")
        self.build()
        head, _ = offlinepack.read_header(next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack")))
        self.assertIn("vworld:Base", head["dropped"])                     # 뒤의 것(VWorld)부터
        self.assertLess(head["layers"]["vworld:Base"]["zooms"][1], 12)
        path = next(Path(settings.OFFLINE_DIR).glob("tiny-*.gsmpack"))
        _, base = offlinepack.read_header(path)
        self.assertLessEqual(path.stat().st_size - base, 0.05 * 1024 * 1024)   # 지층 면까지 쳐서 예산 안이다


class Grid(SimpleTestCase):
    def test_패키지의_격자가_tilegrid_와_같다(self):
        """패키지는 viewer 를 타지 않으려고 3857 격자 셈을 옮겨 두었다 — 둘이 어긋나면 캐시 열쇠가 어긋난다 (wetherilli P16)"""
        for bbox in [(129.0, 37.0, 129.25, 37.17), (124.5, 33.0, 131.0, 38.7), (-180, -85, 180, 85)]:
            for z in (0, 5, 9, 14):
                if z > 9 and bbox[2] - bbox[0] > 1:
                    continue
                self.assertEqual(grid.tiles_for(bbox, z), [(x, y) for _, x, y in tilegrid.tiles_for(bbox, z)])


class Page(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        offlinepack.write(Path(self.tmp.name) / "jangseong-20261010.gsmpack",
                          {"box": "jangseong", "title": "장성 도폭 (태백)", "built": "2026-10-10", "bbox": [129, 37, 129.25, 37.17]},
                          [("L/1/0/0", b"abc")])

    def test_목록과_내려받기(self):
        with override_settings(OFFLINE_DIR=self.tmp.name, PUBLIC=False):
            page = self.client.get("/GSM/offline/")
            self.assertContains(page, "장성 도폭 (태백)")
            self.assertEqual(self.client.get("/GSM/offline/?format=json").json()["packs"][0]["tiles"], 1)
            got = self.client.get("/GSM/offline/jangseong-20261010.gsmpack")
            self.assertEqual(got.status_code, 200)
            self.assertTrue(b"".join(got.streaming_content).startswith(b"GSMPACK1"))
            got.close()
            self.assertEqual(self.client.get("/GSM/offline/nope-20261010.gsmpack").status_code, 404)

    def test_밖에_연_판에서는_닫는다(self):
        with override_settings(OFFLINE_DIR=self.tmp.name, PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/offline/").status_code, 404)
            self.assertEqual(self.client.get("/GSM/offline/jangseong-20261010.gsmpack").status_code, 404)


@override_settings(PUBLIC=False)
class ViaGsm(TestCase):
    """노트북의 `gsmpack bake --via` 가 묻는 길 — 주소의 꼴과 지층 면 (wetherilli 407)."""

    @classmethod
    def setUpTestData(cls):
        group = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만 지질도", group=group, upstream="kigam")
        Layer.objects.create(name="L_Off", title="꺼진 것", group=group, upstream="kigam", enabled=False)

    def test_주소의_꼴이_화면의_캐시_열쇠와_같다(self):
        """굽는 쪽이 꼴에 칸의 범위를 채운 주소를 서버가 받으면, 미리 데우기·굽기가 담는 열쇠와 한 글자까지 같아야 캐시가 맞는다 (029)"""
        from urllib.parse import parse_qsl, urlsplit
        from viewer import views
        from viewer.management.commands.prewarm import plan_for
        spec = self.client.get("/GSM/offline/plan/?layer=L_50K_Geology_Map").json()
        self.assertEqual((spec["tile_size"], spec["zoom_offset"], spec["kind"], spec["title"]), (512, -1, "kigam", "5만 지질도"))
        plan = plan_for("L_50K_Geology_Map", "kigam")
        for z, x, y in [(9, 436, 198), (14, 13990, 6370), (15, 27983, 12741)]:
            url = spec["url"].format(z=z, x=x, y=y, bbox=grid.bbox_text(grid.cell_extent(z, x, y)))
            query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
            self.assertTrue(url.startswith("wms/?"))
            self.assertEqual(views.map_cache_key(kigam.clean_params(query)), plan.key(z, x, y))

    def test_vworld_와_굽지_못하는_레이어(self):
        spec = self.client.get("/GSM/offline/plan/?layer=vworld:Satellite").json()
        self.assertEqual((spec["url"], spec["type"], spec["tile_size"], spec["zoom_offset"]),
                         ("vworld/Satellite/{z}/{y}/{x}.jpeg", "image/jpeg", 256, 0))
        for name in ("vworld:Nope", "L_Off", "L_없다"):
            self.assertEqual(self.client.get(f"/GSM/offline/plan/?layer={name}").status_code, 404, name)

    def test_지층_면(self):
        with mock.patch.object(kigam, "describe_layer", lambda name: ["geoOpen:l_50k_geology_litho_latest", "geoOpen:x_fault"]), \
                mock.patch.object(kigam, "wfs_in_bbox", lambda t, bbox: UNITS), \
                mock.patch.object(build_offline_pack.time, "sleep", lambda s: None):
            got = self.client.get("/GSM/offline/units/?layer=L_50K_Geology_Map&bbox=129,37,129.03,37.05").json()
        self.assertEqual(got["types"], ["geoOpen:l_50k_geology_litho_latest"])
        self.assertEqual(len(got["features"]), 2)                      # 선은 버린다
        first = got["features"][0]["properties"]
        self.assertEqual(first["props"]["도폭"]["links"][0]["url"], "https://doi.org/10.22747/x")
        self.assertIn("props_en", first)
        flat = json.dumps(got["features"][0]["geometry"]["coordinates"])
        self.assertNotIn("129.05", flat)                               # 박스로 잘랐다

    def test_상류가_못_주면_502(self):
        def broken(name):
            raise ValueError("JSON 이 아니다")
        with mock.patch.object(kigam, "describe_layer", broken):
            got = self.client.get("/GSM/offline/units/?layer=L_50K_Geology_Map&bbox=129,37,129.03,37.05")
        self.assertEqual(got.status_code, 502)

    def test_지층_면의_범위를_가린다(self):
        for bbox in ("", "129,37,129", "129,37,128,38", "126,34,129,37.05"):
            self.assertEqual(self.client.get(f"/GSM/offline/units/?layer=L_50K_Geology_Map&bbox={bbox}").status_code, 400, bbox)
        self.assertEqual(self.client.get("/GSM/offline/units/?layer=vworld:Base&bbox=129,37,129.03,37.05").status_code, 404)

    def test_밖에_연_판에서는_닫는다(self):
        with override_settings(PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/offline/plan/?layer=L_50K_Geology_Map").status_code, 404)
            self.assertEqual(self.client.get("/GSM/offline/units/?layer=L_50K_Geology_Map&bbox=129,37,129.03,37.05").status_code, 404)

    def test_안내_타일에는_표가_붙는다(self):
        """굽는 쪽은 안내 타일(키가 없다)을 이 표로 실패로 읽는다 — 진짜 타일에는 붙지 않는다"""
        with override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False, TILE_CACHE_DIR=tempfile.mkdtemp()):
            got = self.client.get("/GSM/wms/?" + "&".join(f"{k}={v}" for k, v in tilegrid.wms_params("L_50K_Geology_Map", 9, 436, 198).items()))
        self.assertEqual(got["X-GSM-Notice"], "1")


REQUEST = {"title": "작은 요청", "requester": "시험", "note": "현장", "bbox": [129.0, 37.0, 129.05, 37.05],
           "layers": {"vworld:Base": [10, 12], "L_50K_Geology_Map": [10, 12]}}


@override_settings(PUBLIC=False)
class Request(TestCase):
    """요청 화면·어림·승인 (wetherilli 408) — 굽기는 `Queue` 가 본다."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        group = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만 지질도", group=group, upstream="kigam")
        Layer.objects.create(name="L_1M_Geology_Map", title="100만 지질도", group=group, upstream="kigam")
        cls.staff = get_user_model().objects.create_user("staff", password="pw", is_staff=True)
        cls.plain = get_user_model().objects.create_user("plain", password="pw")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(OFFLINE_DIR=self.tmp.name, TILE_CACHE_DIR=self.tmp.name)
        patch.enable()
        self.addCleanup(patch.disable)
        self.spawned = []
        p = mock.patch("viewer.offlinereq.spawn", lambda: self.spawned.append(1))
        p.start()
        self.addCleanup(p.stop)

    def post(self, url, body):
        return self.client.post(url, json.dumps(body), content_type="application/json")

    def test_화면은_범위를_채우고_세트를_고른다(self):
        page = self.client.get("/GSM/offline/request/?bbox=129,37,129.05,37.05")
        self.assertContains(page, 'value="129.05"')
        self.assertContains(page, 'data-name="L_50K_Geology_Map"')
        self.assertContains(page, 'data-name="vworld:Satellite"')
        names = [r["name"] for r in page.context["layers"]]
        self.assertLess(names.index("L_50K_Geology_Map"), names.index("vworld:Base"))       # 지질도가 앞선다
        self.assertTrue(next(r for r in page.context["layers"] if r["name"] == "L_50K_Geology_Map")["on"])
        self.assertFalse(next(r for r in page.context["layers"] if r["name"] == "vworld:white")["on"])

    def test_요청_한_줄(self):
        from viewer.models import OfflinePackRequest
        got = self.post("/GSM/offline/request/", REQUEST).json()
        row = OfflinePackRequest.objects.get(pk=got["id"])
        self.assertEqual((row.status, row.requester, row.box_name), ("waiting", "시험", f"req{row.pk}"))
        self.assertEqual(list(row.box["layers"]), ["L_50K_Geology_Map", "vworld:Base"])         # 고른 차례가 아니라 정한 차례
        self.assertEqual(row.box["units"], ["L_50K_Geology_Map"])
        self.assertEqual(row.box["budget_mb"], 200)
        self.assertEqual(self.spawned, [])                                                       # 승인 전에는 굽지 않는다

    def test_요청을_가린다(self):
        bad = [dict(REQUEST, bbox=[129.0, 37.0, 129.4, 37.1]),                  # 도폭 하나보다 넓다
               dict(REQUEST, bbox=[140.0, 37.0, 140.1, 37.1]),                  # 한국 밖
               dict(REQUEST, layers={"L_없다": [10, 12]}),
               dict(REQUEST, layers={"L_50K_Geology_Map": [12, 10]}),
               dict(REQUEST, layers={"L_50K_Geology_Map": [10, 19]}),
               dict(REQUEST, layers={}),
               dict(REQUEST, requester=" ")]
        for body in bad:
            self.assertEqual(self.post("/GSM/offline/request/", body).status_code, 400, body)

    def test_어림(self):
        got = self.post("/GSM/offline/request/estimate/", REQUEST).json()
        self.assertIn("L_50K_Geology_Map", got["lines"][0])
        self.assertEqual(got["dropped"], {})
        self.assertGreater(got["calls"], 0)

    def test_승인은_staff_만(self):
        from viewer.models import OfflinePackRequest
        pk = self.post("/GSM/offline/request/", REQUEST).json()["id"]
        url = f"/GSM/offline/request/{pk}/decide/"
        self.assertEqual(self.client.post(url, {"action": "approve"}).status_code, 403)
        self.client.force_login(self.plain)
        self.assertEqual(self.client.post(url, {"action": "approve"}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.post(url, {"action": "approve"}), "/GSM/manage/?tab=offline", fetch_redirect_response=False)
        row = OfflinePackRequest.objects.get(pk=pk)
        self.assertEqual((row.status, row.approved_by), ("approved", "staff"))
        self.assertEqual(self.spawned, [1])
        self.client.post(url, {"action": "reject"})
        self.assertEqual(OfflinePackRequest.objects.get(pk=pk).status, "rejected")
        self.assertEqual(self.client.post(url, {"action": "reject"}).status_code, 400)          # 거절한 것을 또 거절하지 않는다

    def test_관리_탭(self):
        self.post("/GSM/offline/request/", REQUEST)
        page = self.client.get("/GSM/manage/")
        self.assertContains(page, 'data-tab="offline"')
        self.assertContains(page, "작은 요청")
        self.assertNotContains(page, 'name="action" value="approve"')                        # 로그인하지 않으면 단추가 없다
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/GSM/manage/"), 'name="action" value="approve"')

    def test_밖에_연_판에서는_닫는다(self):
        with override_settings(PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/offline/request/").status_code, 404)
            self.assertEqual(self.post("/GSM/offline/request/", REQUEST).status_code, 404)
            self.assertEqual(self.post("/GSM/offline/request/estimate/", REQUEST).status_code, 404)
            self.assertNotContains(self.client.get("/GSM/manage/"), 'data-tab="offline"')


class Queue(Build):
    """일꾼(`--queue`) — 승인된 요청을 하나씩 굽고 상태를 적는다. 상류는 `Build` 의 가짜다 (wetherilli 408)."""

    def request(self, status="approved", **box):
        from viewer.models import OfflinePackRequest
        return OfflinePackRequest.objects.create(requester="시험", status=status, box=dict(BOX["tiny"], **box))

    def test_승인된_것을_굽는다(self):
        from viewer.models import OfflinePackRequest as Req
        done, waiting = self.request(), self.request(status="waiting")
        call_command("build_offline_pack", "--queue", stdout=io.StringIO(), stderr=io.StringIO())
        done.refresh_from_db()
        self.assertEqual(done.status, Req.DONE)
        self.assertTrue(done.pack.startswith(f"req{done.pk}-") and (Path(settings.OFFLINE_DIR) / done.pack).is_file())
        self.assertIn("타일", done.last_line)
        self.assertIsNotNone(done.finished_at)
        self.assertEqual(Req.objects.get(pk=waiting.pk).status, Req.WAITING)                   # 승인하지 않은 것은 두고
        self.assertIn(done.pack, self.client.get("/GSM/offline/").content.decode())            # 목록에 뜬다

    def test_끊긴_것부터_잇는다(self):
        from viewer.models import OfflinePackRequest as Req
        later, cut = self.request(), self.request(status="baking")
        out = io.StringIO()
        call_command("build_offline_pack", "--queue", stdout=out, stderr=io.StringIO())
        text = out.getvalue()
        self.assertLess(text.index(f"req{cut.pk}"), text.index(f"req{later.pk}"))
        self.assertEqual({r.status for r in Req.objects.all()}, {Req.DONE})

    def test_실패는_적고_다음으로(self):
        from viewer.models import OfflinePackRequest as Req
        broken = self.request(layers={"L_50K_Geology_Map": [10, 10]})
        fine = self.request()
        with mock.patch.object(kigam, "has_key", lambda: False):
            call_command("build_offline_pack", "--queue", stdout=io.StringIO(), stderr=io.StringIO())
        broken.refresh_from_db(), fine.refresh_from_db()
        self.assertEqual((broken.status, fine.status), (Req.FAILED, Req.FAILED))
        self.assertIn("인증키", broken.last_line)

    def test_다른_일꾼이_돌면_곧장_끝난다(self):
        from viewer import offlinereq
        from viewer.models import OfflinePackRequest as Req
        row = self.request()
        with offlinereq.queue_lock() as mine:
            self.assertTrue(mine)
            out = io.StringIO()
            call_command("build_offline_pack", "--queue", stdout=out, stderr=io.StringIO())
        self.assertIn("다른 일꾼", out.getvalue())
        self.assertEqual(Req.objects.get(pk=row.pk).status, Req.APPROVED)
