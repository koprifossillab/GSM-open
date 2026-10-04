"""3D 에 유럽·일본 지질도, 온 지구 찾기에 화석 산지·지층·화산 (wetherilli 187). 상류를 부르지 않는다."""
import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import fossils, i18n, volcanoes
from viewer.tests.test_fossils import HEAD
from viewer.tests.test_volcanoes import written

MAP3D_JS = Path(__file__).resolve().parents[1] / "static" / "viewer" / "map3d.js"

#: 이름이 서로 걸치게 — "Hell Creek" 지층의 산지 둘과, 이름에만 Hell Creek 이 든 다른 지층의 산지 하나
ROWS = [
    '10,-106.9,47.6,"Hell Creek (AMNH general)","Hell Creek",Maastrichtian,,72.1,66.0,US,40,,,fluvial,\n',
    '11,-104.0,46.0,"Bug Creek","Hell Creek",Maastrichtian,,72.1,66.0,US,90,,,fluvial,\n',
    '12,-100.0,44.0,"Hell Creek","Pierre Shale",Campanian,,83.6,72.1,US,3,,,marine,\n',
    '13,-116.5,51.4,"Walcott Quarry","Burgess Shale",Wuliuan,,509.0,504.5,CA,500,,,marine,\n',
]


class Map3D(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=io.StringIO())
        self.page = self.client.get(reverse("viewer:map3d")).content.decode()

    def test_유럽_상류가_목록에(self):
        for name in ("bgs:BGS.50k.Bedrock", "brgm:LITHO_1M_SIMPLIFIEE", "egdi:GeologicUnitView_Age", "bgr:gk1000:0",
                     "igme:magna50:0", "gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM", "gsni:5",
                     "emodnet:bgr:quaternary_age"):
            self.assertIn(f'value="{name}"', self.page)
        # IGME 1:100만은 2D 가 4326 으로 받지만 3857 로 물어도 그린다(2026-10-04)
        self.assertIn('value="igme:geologico1m:0"', self.page)

    def test_줌과_범위를_싣는다(self):
        bgs = self.page[self.page.index('value="bgs:BGS.50k.Bedrock"'):].split(">", 1)[0]
        self.assertIn('data-min="13"', bgs)                               # 2D 처럼 가까이서만
        scan = self.page[self.page.index('value="brgm:SCAN_F_GEOL1M"'):].split(">", 1)[0]
        self.assertIn('data-last="11"', scan)                             # 2D 처럼 멀리서만

    def test_일본은_z_x_y_타일로(self):
        geology = self.page[self.page.index('value="gsj:geology"'):].split(">", 1)[0]
        self.assertIn('data-tiles="gsj/geology/{z}/{x}/{y}.png"', geology)

    def test_유럽_묶음(self):
        js = MAP3D_JS.read_text(encoding="utf-8")
        self.assertIn('europe: ["uk", "ireland", "france", "germany", "spain", "portugal", "italy", "switzerland"]', js)   # wetherilli 211
        self.assertIn("data-tiles", js)
        self.assertIn("layer.minzoom", js)


class Search(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-search-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        src = Path(self.dir) / "c.csv"
        src.write_text(HEAD + "".join(ROWS), encoding="utf-8")
        fossils.build(src, Path(self.dir) / fossils.FILE, log=lambda *_: None)
        written(self.dir)

    def find(self, q, lang="ko"):
        self.client.cookies[i18n.COOKIE] = lang
        return self.client.get(reverse("viewer:earth-places"), {"q": q}).json()

    def test_지층은_이름으로_묶고_화석이_많은_산지의_자리(self):
        got = self.find("Hell Creek")
        groups = [(h["group"], h["title"]) for h in got["results"]]
        # 같은 이름이 먼저 — 지층 Hell Creek 과 산지 Hell Creek, 그다음 앞이 같은 것
        self.assertEqual(groups[:3], [("formation", "Hell Creek"), ("fossil", "Hell Creek"),
                                      ("fossil", "Hell Creek (AMNH general)")])
        formation = got["results"][0]
        self.assertEqual((formation["lon"], formation["lat"]), (-104.0, 46.0))     # 화석 90 개인 Bug Creek
        self.assertIn("화석 산지 2 곳", formation["sub"])
        self.assertIn("마스트리히트절", formation["sub"])
        self.assertEqual(formation["kind"], "지층")
        self.assertEqual(got["sources"], ["Natural Earth 10 m", "PBDB"])

    def test_화산과_지명(self):
        got = self.find("fuji")
        volcano = [h for h in got["results"] if h["group"] == "volcano"]
        self.assertEqual(volcano[0]["title"], "Fujisan")
        self.assertEqual(volcano[0]["kind"], "화산")
        self.assertIn("마지막 분화 1707 년", volcano[0]["sub"])
        self.assertIn("GVP", got["sources"])

    def test_영어판(self):
        got = self.find("Creek", "en")
        kinds = {h["group"]: h["kind"] for h in got["results"]}
        self.assertEqual((kinds["formation"], kinds["fossil"]), ("Formation", "Fossil"))
        formation = [h for h in got["results"] if h["group"] == "formation"][0]
        self.assertEqual(formation["sub"], "2 fossil collections · Maastrichtian")

    def test_한_글자와_LIKE_기호는_찾지_않는다(self):
        self.assertEqual(fossils.search("H"), ([], []))
        self.assertEqual(fossils.search("%%")[0], [])
        self.assertEqual(volcanoes.search(""), [])

    def test_파일이_없어도_지명은_찾는다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            got = self.find("Baikal", "en")
        self.assertTrue(got["results"])
        self.assertEqual({h["group"] for h in got["results"]}, {"place"})
