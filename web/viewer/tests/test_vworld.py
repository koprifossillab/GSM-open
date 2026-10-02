"""주소·장소 찾기 — VWorld 로 나가는 두 번째 문.

VWorld 를 실제로 부르지 않는다. 응답의 꼴은 2026-09-27 에 받아 본 그대로다.
"""
import tempfile
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import vworld


def reply(items=None, status="OK", result=None):
    body = {"response": {"status": status,
                         "result": result if result is not None else {"items": items or []}}}
    return mock.Mock(url="https://api.vworld.kr/req/search?key=SECRET", status_code=200,
                     json=mock.Mock(return_value=body))


ROAD = {"address": {"road": "대전광역시 유성구 과학로 124 (가정동)", "parcel": "가정동 30"},
        "point": {"x": "127.3623", "y": "36.3776"}}
DISTRICT = {"title": "대전광역시 유성구", "point": {"x": "127.3564", "y": "36.3621"}}
DONG = {"title": "대전광역시 유성구 원내동", "point": {"x": "127.3164", "y": "36.2997"}}
PLACE = {"title": "지질박물관", "category": "박물관",
         "address": {"road": "대전광역시 유성구 과학로 124"},
         "point": {"x": "127.3634", "y": "36.3784"}}


def by_type(mapping):
    """요청의 type·category 를 보고 알맞은 가짜 응답을 준다."""
    def fake(url, params, **kw):
        key = (params.get("type"), params.get("category"))
        return reply(mapping.get(key, []))
    return fake


@override_settings(VWORLD_KEY="SECRET")
class Search(SimpleTestCase):
    def test_갈래마다_읽는다(self):
        fake = by_type({("address", "road"): [ROAD], ("place", None): [PLACE]})
        with mock.patch.object(vworld.requests, "get", side_effect=fake):
            rows = vworld.search("과학로 124")
        kinds = {r["kind"]: r for r in rows}
        self.assertEqual(kinds["road"]["title"], "대전광역시 유성구 과학로 124 (가정동)")
        self.assertEqual(kinds["road"]["sub"], "가정동 30")            # 도로명 곁에 지번
        self.assertEqual(kinds["place"]["title"], "지질박물관")
        self.assertAlmostEqual(kinds["road"]["lat"], 36.3776)

    def test_같은_이름은_하나로_친다(self):
        """한 번지에 건물이 여럿이면 같은 도로명이 건물마다 온다."""
        other = dict(ROAD, point={"x": "127.3634", "y": "36.3784"})
        fake = by_type({("address", "road"): [ROAD, other]})
        with mock.patch.object(vworld.requests, "get", side_effect=fake):
            rows = vworld.search("과학로 124")
        self.assertEqual(len(rows), 1)

    def test_넣은_말로_끝나는_행정구역이_맨_앞이다(self):
        fake = by_type({("district", "L4"): [DONG], ("district", "L2"): [DISTRICT]})
        with mock.patch.object(vworld.requests, "get", side_effect=fake):
            rows = vworld.search("유성구")
        self.assertEqual(rows[0]["title"], "대전광역시 유성구")

    def test_한_갈래가_실패해도_나머지는_준다(self):
        def fake(url, params, **kw):
            if params.get("type") == "place":
                raise vworld.requests.ConnectionError("끊겼다")
            return by_type({("address", "road"): [ROAD]})(url, params)
        with mock.patch.object(vworld.requests, "get", side_effect=fake):
            rows = vworld.search("과학로 124")
        self.assertEqual([r["kind"] for r in rows], ["road"])

    def test_다_실패하면_오류다(self):
        with mock.patch.object(vworld.requests, "get",
                               side_effect=vworld.requests.ConnectionError("끊겼다")):
            with self.assertRaises(vworld.VWorldError):
                vworld.search("과학로 124")

    def test_없으면_빈_목록(self):
        with mock.patch.object(vworld.requests, "get", return_value=reply(status="NOT_FOUND")):
            self.assertEqual(vworld.search("없는곳"), [])

    def test_오류_문구에_열쇠가_새지_않는다(self):
        err = vworld.requests.ConnectionError("https://api.vworld.kr/req/search?key=SECRET&q=a")
        with mock.patch.object(vworld.requests, "get", side_effect=err):
            with self.assertRaises(vworld.VWorldError) as ctx:
                vworld.search("a")
        self.assertNotIn("SECRET", str(ctx.exception))


@override_settings(VWORLD_KEY="SECRET")
class Reverse(SimpleTestCase):
    def test_도로명과_지번(self):
        result = [{"type": "road", "text": "대전광역시 유성구 과학로 124 (가정동,지질박물관)"},
                  {"type": "parcel", "text": "대전광역시 유성구 가정동 30"}]
        with mock.patch.object(vworld.requests, "get", return_value=reply(result=result)):
            got = vworld.reverse(36.3776, 127.3623)
        self.assertEqual(got["parcel"], "대전광역시 유성구 가정동 30")
        self.assertTrue(got["road"].startswith("대전광역시 유성구 과학로 124"))

    def test_바다는_빈_칸(self):
        with mock.patch.object(vworld.requests, "get", return_value=reply(status="NOT_FOUND")):
            self.assertEqual(vworld.reverse(34.0, 125.0), {"road": "", "parcel": ""})


class Views(SimpleTestCase):
    def setUp(self):
        patch = override_settings(VWORLD_KEY="SECRET", TILE_CACHE_MIN_FREE_BYTES=0,
                                  TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-vw-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_두_번째_검색은_VWorld_를_타지_않는다(self):
        rows = [{"kind": "road", "title": "과학로 124", "sub": "", "lat": 36.3, "lon": 127.3}]
        with mock.patch.object(vworld, "search", return_value=rows) as up:
            first = self.client.get("/GSM/search/", {"q": "과학로 124"}).json()
            second = self.client.get("/GSM/search/", {"q": "과학로 124"}).json()
        self.assertEqual(up.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(second["results"][0]["title"], "과학로 124")

    def test_빈_검색은_묻지_않는다(self):
        with mock.patch.object(vworld, "search") as up:
            got = self.client.get("/GSM/search/", {"q": "  "}).json()
        self.assertEqual(got, {"results": []})
        up.assert_not_called()

    @override_settings(VWORLD_KEY="")
    def test_열쇠가_없으면_503(self):
        response = self.client.get("/GSM/search/", {"q": "가정동"})
        self.assertEqual(response.status_code, 503)

    def test_좌표는_1m_에서_잘라_묻는다(self):
        with mock.patch.object(vworld, "reverse", return_value={"road": "r", "parcel": "p"}) as up:
            self.client.get("/GSM/whereis/", {"lat": "36.377601", "lon": "127.362304"})
            self.client.get("/GSM/whereis/", {"lat": "36.377603", "lon": "127.362301"})
        self.assertEqual(up.call_count, 1)
        up.assert_called_with(36.3776, 127.3623)

    def test_VWorld_가_막히면_502(self):
        with mock.patch.object(vworld, "search", side_effect=vworld.VWorldError("x")):
            response = self.client.get("/GSM/search/", {"q": "가정동"})
        self.assertEqual(response.status_code, 502)
