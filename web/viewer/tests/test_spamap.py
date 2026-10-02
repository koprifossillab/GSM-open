"""남극–에이트켄 분지 지질도의 속성 — 원본 GeoTIFF 에서 누른 자리를 읽는다 (wetherilli 081).

원본(112 MB)은 저장소에 없다. 같은 꼴(팔레트·LZW·GeoTIFF 지오 변환)의 작은 그림을 Pillow 로 만들어 쓴다 — 투영의
가운데(남위 53°·서경 157.5°)가 칸 (100, 60) 에 오게 원점을 잡았다.
"""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageDraw, TiffImagePlugin

from viewer import spamap

RES = 5.0
WHITE, NPNC, NPNC_70, BLACK, SLUMPED, ODD = 0, 1, 2, 3, 4, 5


def write_map(path: Path):
    """200×120 칸. 왼쪽 반은 NpNc 의 범례 색, 오른쪽 반은 그것을 70% 로 얹은 색, 가운데 세로로 검은 경계선,
    맨 위 줄은 흰 바탕(지도 밖), (150, 100) 둘레는 무너진 물질 무늬."""
    im = Image.new("P", (200, 120), NPNC)
    im.putpalette([255, 255, 255, 176, 99, 48, 200, 146, 111, 0, 0, 0, 215, 255, 210, 12, 200, 34] + [0, 0, 0] * 250)
    draw = ImageDraw.Draw(im)
    draw.rectangle((100, 0, 199, 119), fill=NPNC_70)
    draw.rectangle((0, 0, 199, 9), fill=WHITE)
    draw.rectangle((98, 10, 99, 119), fill=BLACK)
    draw.rectangle((148, 98, 152, 102), fill=SLUMPED)
    draw.point((30, 30), fill=ODD)
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (RES, RES, 0.0)
    ifd[33922] = (0.0, 0.0, 0.0, -100 * RES, 60 * RES, 0.0)
    im.save(path, compression="tiff_lzw", tiffinfo=ifd)


class SpaMap(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gsm-spa-"))
        patch = override_settings(MOON_DIR=str(self.dir))
        patch.enable()
        self.addCleanup(patch.disable)
        spamap._open.cache_clear()

    def lonlat(self, col, row):
        """칸 가운데 → 달 경위도. 1 km 안쪽이라 평면으로 어림해도 칸을 벗어나지 않는다."""
        import math
        dx, dy = (col + 0.5 - 100) * RES, (60 - row - 0.5) * RES
        lat = spamap.LAT0 + math.degrees(dy / spamap.R)
        lon = spamap.LON0 + math.degrees(dx / (spamap.R * math.cos(math.radians(spamap.LAT0))))
        return lon, lat

    def test_파일이_없으면_안내(self):
        self.assertFalse(spamap.available())
        data = self.client.get(reverse("viewer:moon-info"), {"lon": "-150", "lat": "-30", "layer": "spa"}).json()
        self.assertEqual(data["rows"], [])
        self.assertTrue(data["note"])

    def test_LZW_를_Pillow_와_같이_푼다(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        head = spamap._head()
        with open(spamap.source(), "rb") as f:
            f.seek(head["offsets"][0])
            data = spamap.lzw(f.read(head["counts"][0]))
        with Image.open(spamap.source()) as im:
            self.assertEqual(data[:200 * head["rows"]], im.tobytes()[:len(data)])

    def test_색으로_단위를_가린다(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        units = spamap._head()["units"]
        self.assertEqual(units[NPNC], "NpNc")          # 범례 색 그대로
        self.assertEqual(units[NPNC_70], "NpNc")       # 70% 로 얹은 색
        for i in (WHITE, BLACK, ODD):                  # 바탕·선·아무 단위도 아닌 색
            self.assertNotIn(i, units)

    def test_누른_자리(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        hit = spamap.identify(*self.lonlat(50, 60))
        self.assertEqual(hit["unit"], "NpNc")
        self.assertEqual(hit["rows"][:3], [["단위", "NpNc"], ["이름", "Nectarian - Pre-Nectarian crater"],
                                           ["시대", "Nectarian–Pre-Nectarian"]])
        self.assertEqual(hit["color"], "#b06330")

    def test_선_위를_누르면_둘레의_단위(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        self.assertEqual(spamap.identify(*self.lonlat(98, 60))["unit"], "NpNc")

    def test_무늬가_있으면_지표_특징도(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        hit = spamap.identify(*self.lonlat(150, 100))
        self.assertEqual(hit["unit"], "NpNc")
        self.assertIn(["지표 특징", "Slumped material"], hit["rows"])

    def test_지도_밖(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        self.assertIsNone(spamap.identify(*self.lonlat(50, 2)))       # 흰 바탕
        self.assertIsNone(spamap.identify(20.0, 60.0))                  # 그림 밖

    def test_화면이_받는_것(self):
        write_map(self.dir / spamap.SOURCE_NAME)
        lon, lat = self.lonlat(50, 60)
        data = self.client.get(reverse("viewer:moon-info"),
                               {"lon": f"{lon:.6f}", "lat": f"{lat:.6f}", "layer": "spa"}).json()
        self.assertEqual(data["rows"][2], ["시대", "넥타리스기–선넥타리스기"])
        items = self.client.get(reverse("viewer:moon-legend"), {"layer": "spa"}).json()["items"]
        self.assertEqual(len(items), len(spamap.UNITS))
        self.assertEqual(items[0], {"unit": "Cc", "label": "Copernican crater (Cc)", "age": "코페르니쿠스기",
                                    "color": "#fde754"})
