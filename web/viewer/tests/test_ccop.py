"""CCOP 동·동남아시아 200만 지질도 (wetherilli 108). 상류를 부르지 않는다 — HTML 의 꼴은 2026-09-30 에 받은 그대로다."""
import io
import math
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import gsj
from viewer.models import Layer

SEOUL_HTML = """<table border="1" cellpadding="3" cellspacing="0" width="300">
	<tr ><th class="nav" colspan="2">Geological Map of East Asia</th></tr>
<tr>
	<td width="40%">Geology</td>
	<td width="60%">J_Pf: Felsic Plutonic Rocks, Jurassic</td>
</tr>
</table>"""


def merc(lon, lat):
    r = 6378137.0
    return math.radians(lon) * r, r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


class Parse(SimpleTestCase):
    def test_표의_한_줄을_기호_암석_시대로(self):
        got = gsj.parse_ccop_html(SEOUL_HTML)
        self.assertEqual(got[0]["properties"], {"code": "J_Pf", "rock": "Felsic Plutonic Rocks", "age": "Jurassic"})
        self.assertEqual(gsj.ccop_friendly(got[0]["properties"]),
                         {"지질기호": "J_Pf", "암석": "Felsic Plutonic Rocks", "지질시대": "쥐라기"})

    def test_결과가_없으면_빈_목록(self):
        self.assertEqual(gsj.parse_ccop_html("GetFeatureInfo results:\n\n  Search returned no results.\n"), [])

    def test_누른_픽셀을_위경도로(self):
        x, y = merc(127.0, 37.6)
        lon, lat = gsj._clicked_lonlat({"bbox": f"{x - 5000},{y - 5000},{x + 5000},{y + 5000}", "width": "256",
                                        "height": "256", "i": "128", "j": "128", "crs": "EPSG:3857"})
        self.assertAlmostEqual(lon, 127.0, places=4)
        self.assertAlmostEqual(lat, 37.6, places=4)
        # 1.3.0 의 4326 은 위도가 먼저다
        lon, lat = gsj._clicked_lonlat({"bbox": "37,126,38,128", "width": "100", "height": "100", "i": "25",
                                        "j": "50", "crs": "EPSG:4326", "version": "1.3.0"})
        self.assertEqual((lon, lat), (126.5, 37.5))


class Views(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=io.StringIO())

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-ccop-"))   # 속성도 캐시에 담는다
        patch.enable()
        self.addCleanup(patch.disable)

    def test_씨앗(self):
        row = Layer.objects.get(name=gsj.CCOP_LAYER)
        self.assertEqual((row.upstream, row.group.region), ("ccop", "china"))

    def test_누르면_4326_으로_다시_묻는다(self):
        answer = mock.Mock(status_code=200, text=SEOUL_HTML, content=b"", url="…",
                           headers={"content-type": "text/html"})
        x, y = merc(127.0, 37.6)
        with mock.patch.object(gsj.requests, "get", return_value=answer) as get, \
             mock.patch.object(gsj.usage, "record"), mock.patch.object(gsj.usage, "paused", return_value=0):
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": gsj.CCOP_LAYER, "query_layers": gsj.CCOP_LAYER, "crs": "EPSG:3857",
                "bbox": f"{x - 5000},{y - 5000},{x + 5000},{y + 5000}", "width": 256, "height": 256,
                "i": 128, "j": 128, "request": "GetFeatureInfo"}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["srs"], sent["info_format"]), ("EPSG:4326", "text/html"))
        self.assertEqual(data["features"][0]["props"]["지질시대"], "쥐라기")
