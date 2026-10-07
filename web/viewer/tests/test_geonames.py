"""온 세계의 도시 이름 — GeoNames cities1000 (wetherilli 374). 작은 표를 구워 찾기와 온 지구 찾기에 섞이는 것을 본다."""
import io
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from viewer import geonames

#: cities1000.txt 의 열 — id, 이름, ASCII 이름, 별칭, 위도, 경도, 갈래, 갈래 코드, 나라, 다른 나라, 도·주, …, 인구(15 째)
ROWS = [
    (3936456, "Lima", "Lima", "Lima,Lima City,리마", -12.04318, -77.02824, "PE", "15", 7737002),
    (4517009, "Lima", "Lima", "Lima,라이마", 40.74255, -84.10523, "US", "OH", 37290),
    (3848950, "Lima", "Lima", "Lima", -24.25, -57.0, "PY", "16", 1500),
    (2761369, "Vienna", "Vienna", "Vienna,Wien,비엔나,빈", 48.20849, 16.37208, "AT", "09", 1691468),
    (3939459, "Huancayo", "Huancayo", "", -12.06513, -75.20486, "PE", "12", 376657),
]
ADMIN1 = "PE.15\tLima Province\tLima Province\t1\nUS.OH\tOhio\tOhio\t2\nAT.09\tVienna\tVienna\t3\nPE.12\tJunín\tJunin\t4\n"
COUNTRIES = [("PE", "Peru", "페루"), ("US", "United States of America", "미국"), ("AT", "Austria", "오스트리아"),
             ("PY", "Paraguay", "파라과이")]


def line(gid, name, ascii_name, alts, lat, lon, cc, admin1, pop):
    cols = [str(gid), name, ascii_name, alts, str(lat), str(lon), "P", "PPL", cc, "", admin1, "", "", "", str(pop),
            "", "100", "America/Lima", "2026-01-01"]
    return "\t".join(cols)


class GeoNamesTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("cities1000.txt", "\n".join(line(*r) for r in ROWS) + "\n")
        (folder / "cities1000.zip").write_bytes(buf.getvalue())
        (folder / "admin1CodesASCII.txt").write_text(ADMIN1, encoding="utf-8")
        cls.override = override_settings(EARTH_DIR=cls.tmp.name)
        cls.override.enable()
        cls.built = geonames.build(folder, countries=COUNTRIES)

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        geonames._open.cache_clear()
        cls.tmp.cleanup()
        super().tearDownClass()


class Search(GeoNamesTestCase):
    def test_구운_수(self):
        self.assertEqual(self.built["rows"], 5)
        self.assertEqual(self.built["korean"], 3)

    def test_같은_이름은_인구_차례(self):
        hits = geonames.search("lima")
        self.assertEqual([h["sub"] for h in hits], ["Lima Province · 페루", "Ohio · 미국", "파라과이"])
        self.assertEqual(hits[0]["title"], "리마 (Lima)")

    def test_범위_안의_것이_앞선다(self):
        hits = geonames.search("lima", bbox=(-62, -30, -54, -20))       # 파라과이 둘레
        self.assertEqual(hits[0]["sub"], "파라과이")
        self.assertTrue(hits[0]["inside"])

    def test_날짜변경선을_넘는_범위(self):
        hits = geonames.search("lima", bbox=(170, -30, -60, 0))         # 서가 동보다 크다 — 남미 서쪽까지
        self.assertEqual(hits[0]["sub"], "Lima Province · 페루")

    def test_별칭으로(self):
        hit = geonames.search("wien")[0]
        self.assertEqual(hit["title"], "빈 (wien)")                      # 한글 별칭은 가나다 끝, 맞은 별칭을 곁들인다
        self.assertEqual(geonames.search("비엔나")[0]["title"], "비엔나")  # 찾은 말이 든 한글 별칭을 보인다

    def test_영어판(self):
        self.assertEqual(geonames.search("lima", "en")[0]["title"], "Lima")
        self.assertEqual(geonames.search("lima", "en")[0]["sub"], "Lima Province · Peru")

    def test_짧거나_없는_말(self):
        self.assertEqual(geonames.search("l"), [])
        self.assertEqual(geonames.search("zzzz"), [])

    def test_like_의_특수_글자(self):
        self.assertEqual(geonames.search("%%"), [])
        self.assertEqual(geonames.search("__"), [])


class EarthPlaces(GeoNamesTestCase):
    def test_온_지구_찾기에_섞인다(self):
        data = self.client.get("/GSM/earth/places/?q=huancayo").json()
        # Natural Earth 의 우앙카요와 같은 곳이라 GeoNames 의 것은 빠진다
        self.assertEqual([h["group"] for h in data["results"]].count("place"), 1)
        self.assertNotIn("city", [h["group"] for h in data["results"]])

    def test_도시만_있는_이름(self):
        data = self.client.get("/GSM/earth/places/?q=lima").json()
        paraguay = next(h for h in data["results"] if h.get("sub") == "파라과이")    # Natural Earth 에 없는 작은 마을
        self.assertEqual((paraguay["group"], paraguay["kind"]), ("city", "도시"))
        self.assertIn("GeoNames", data["sources"])
        self.assertNotIn("match", paraguay)
        self.assertEqual(data["results"][0]["title"], "리마 (Lima)")              # 수도는 Natural Earth 의 것이 남는다

    def test_범위를_주면_그_안의_것이_앞선다(self):
        data = self.client.get("/GSM/earth/places/?q=lima&bbox=-62,-30,-54,-20").json()
        self.assertEqual(data["results"][0]["sub"], "파라과이")

    def test_읽지_못하는_범위는_버린다(self):
        self.assertEqual(self.client.get("/GSM/earth/places/?q=lima&bbox=abc").status_code, 200)


class Missing(SimpleTestCase):
    @override_settings(EARTH_DIR="/nonexistent/gsm-earth")
    def test_파일이_없으면_빈_목록(self):
        geonames._open.cache_clear()
        self.assertEqual(geonames.search("lima"), [])
