"""지진 — USGS 를 5 년씩 받아 굽고, 규모 칸마다 찍고, 누르면 읽는다 (wetherilli 138).

USGS 를 실제로 부르지 않는다. CSV 의 꼴은 2026-10-02 에 `fdsnws/event/1/query?format=csv` 로 받은 그대로다.
"""
import datetime
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import quakes, usgs

HEAD = ("time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,"
        "depthError,magError,magNst,status,locationSource,magSource\n")
ROWS = [
    '2011-03-11T05:46:24.120Z,38.297,142.373,29,9.1,mww,541,9.5,2.357,1.16,official,official20110311054624120_30,'
    '2024-06-11T00:00:00.000Z,"2011 Great Tohoku Earthquake, Japan",earthquake,,,,,reviewed,iscgem,official\n',
    '2026-01-07T03:02:53.890Z,7.2449,126.8953,22,5.7,mww,160,28,1.318,1.08,us,us7000rn2z,'
    '2026-06-27T07:09:22.893Z,"35 km E of Santiago, Philippines",earthquake,7.94,1.873,0.047,44,reviewed,us,us\n',
    '2020-01-01T00:00:00.000Z,-20.0,179.99,580,5.2,mb,,,,,us,us_deep,2020-01-02T00:00:00.000Z,"Fiji Islands region",'
    'earthquake,,,,,reviewed,us,us\n',
    # 겹친 것 — 5 년 창의 끝과 다음 창의 처음
    '2020-01-01T00:00:00.000Z,-20.0,179.99,580,5.2,mb,,,,,us,us_deep,2020-01-02T00:00:00.000Z,"Fiji Islands region",'
    'earthquake,,,,,reviewed,us,us\n',
]


def baked(folder) -> Path:
    src = Path(folder) / "q.csv"
    src.write_text(HEAD + "".join(ROWS), encoding="utf-8")
    out = Path(folder) / quakes.FILE
    quakes.build(src, out, log=lambda *_: None)
    return out


class Build(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-quakes-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)

    def test_겹친_것은_한_번(self):
        self.assertEqual(quakes.db().execute("SELECT COUNT(*) FROM quake").fetchone()[0], 3)

    def test_규모_칸(self):
        everywhere = (-180, -90, 180, 90)
        self.assertEqual([r["id"] for r in quakes.points(["quake6"], *everywhere)], ["official20110311054624120_30"])
        self.assertEqual([r["id"] for r in quakes.points(["quake55"], *everywhere)], ["us7000rn2z"])
        self.assertEqual(len(quakes.points(["quake6", "quake55", "quake5"], *everywhere)), 3)
        self.assertEqual(quakes.points([], *everywhere), [])

    def test_색은_깊이(self):
        self.assertEqual([quakes.colour(d) for d in (10, 100, 580, None)],
                         [(228, 87, 46), (242, 193, 78), (59, 125, 216), (228, 87, 46)])


class Door(SimpleTestCase):
    def test_5_년씩(self):
        got = usgs.windows(today=datetime.date(2026, 10, 2))
        self.assertEqual(got[0], ("1900-01-01", "1905-01-01"))
        self.assertEqual(got[-1], ("2025-01-01", "2026-10-03"))
        self.assertEqual(len(got), 26)

    def test_받아_이어_적는다(self):
        dest = Path(tempfile.mkdtemp()) / "q.csv"
        first = mock.MagicMock(status_code=200, url="u", text=HEAD + ROWS[0])
        empty = mock.MagicMock(status_code=204, url="u", text="")
        second = mock.MagicMock(status_code=200, url="u", text=HEAD + ROWS[1])
        with mock.patch.object(usgs, "windows", return_value=[("a", "b"), ("b", "c"), ("c", "d")]), \
             mock.patch.object(usgs.requests, "get", side_effect=[first, empty, second]) as get, \
             mock.patch.object(usgs.usage, "record"):
            self.assertEqual(usgs.download(dest, log_line=lambda *_: None, pause=0), 2)
        self.assertEqual(dest.read_text(encoding="utf-8"), HEAD + ROWS[0] + ROWS[1])
        self.assertEqual(get.call_args.kwargs["params"]["minmagnitude"], 5.0)

    def test_실패하면_멈추고_옛_파일을_둔다(self):
        dest = Path(tempfile.mkdtemp()) / "q.csv"
        dest.write_text("옛것", encoding="utf-8")
        with mock.patch.object(usgs, "windows", return_value=[("a", "b")]), \
             mock.patch.object(usgs.requests, "get", return_value=mock.MagicMock(status_code=503, content=b"")), \
             mock.patch.object(usgs.usage, "record"):
            with self.assertRaises(usgs.UsgsError):
                usgs.download(dest, log_line=lambda *_: None, pause=0)
        self.assertEqual(dest.read_text(encoding="utf-8"), "옛것")

    def test_굽기만(self):
        folder = tempfile.mkdtemp()
        src = Path(folder) / "q.csv"
        src.write_text(HEAD + ROWS[0], encoding="utf-8")
        with override_settings(EARTH_DIR=folder), mock.patch.object(usgs, "download") as download:
            out = io.StringIO()
            call_command("fetch_quakes", csv=str(src), stdout=out)
        download.assert_not_called()
        self.assertIn("1 곳", out.getvalue())


class Views(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-quakes-")
        patch = override_settings(EARTH_DIR=self.dir, TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-quakes-t-"))
        patch.enable()
        self.addCleanup(patch.disable)
        baked(self.dir)

    def test_타일(self):
        url = reverse("viewer:earth-quake-tile", kwargs={"band": "quake6", "z": 0, "x": 1, "y": 0})
        first, again = self.client.get(url), self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], again["X-GSM-Cache"]), ("miss", "hit"))
        self.assertGreater(Image.open(io.BytesIO(first.content)).convert("RGBA").getextrema()[3][1], 150)

    def test_없는_칸(self):
        r = self.client.get(reverse("viewer:earth-quake-tile", kwargs={"band": "quake4", "z": 0, "x": 0, "y": 0}))
        self.assertEqual(r.status_code, 404)

    def test_누르면_켠_칸의_지진만(self):
        url = reverse("viewer:earth-quake-at")
        data = self.client.get(url, {"lon": 142.37, "lat": 38.3, "r": 0.2, "bands": "quake6"}).json()
        rows = dict(data["hits"][0]["rows"])
        self.assertEqual((data["hits"][0]["name"], rows["규모"], rows["일시 (UTC)"]), ("M9.1 지진", "9.1 mww", "2011-03-11 05:46"))
        self.assertTrue(data["hits"][0]["link"].endswith("/official20110311054624120_30"))
        self.assertEqual(self.client.get(url, {"lon": 142.37, "lat": 38.3, "r": 0.2, "bands": "quake5"}).json()["hits"], [])

    def test_날짜_바뀜선_너머도(self):
        data = self.client.get(reverse("viewer:earth-quake-at"),
                               {"lon": -179.99, "lat": -20, "r": 0.2, "bands": "quake5"}).json()
        self.assertEqual(dict(data["hits"][0]["rows"])["깊이 (km)"], "580")

    def test_영어판(self):
        data = self.client.get(reverse("viewer:earth-quake-at"), {"lon": 142.37, "lat": 38.3, "r": 0.2, "bands": "quake6"},
                               HTTP_ACCEPT_LANGUAGE="en").json()
        self.assertEqual(data["hits"][0]["name"], "M9.1 earthquake")
        self.assertIn("Magnitude", dict(data["hits"][0]["rows"]))

    def test_파일이_없으면_목록에_서지_않는다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            page = self.client.get(reverse("viewer:earth")).content.decode()
        self.assertIn('"quakes": []', page)
