"""정적 판에 고를 수 있게 둔 것 — 유럽 넷(`arcwms.Door` 상류), 오늘 넓힌 미국·호주 (wetherilli 257). 상류를 부르지 않는다."""
import importlib.util
import io
import pathlib

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import geosphere, static_tables, views


def _site():
    spec = importlib.util.spec_from_file_location("static_site", pathlib.Path(__file__).resolve().parents[3] / "deploy" / "static_site.py")
    site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site)
    return site


class Optional(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=io.StringIO())

    def names(self, regions, upstreams):
        with override_settings(STATIC_SITE={"regions": regions, "upstreams": upstreams}):
            return {l["name"] for g in views._static_catalog(views._catalog("ko")) for l in g["layers"]}

    def test_기본값은_그대로(self):
        site = _site()
        for region in ("netherlands", "belgium", "austria", "poland"):
            self.assertNotIn(region, site.REGIONS)
        self.assertEqual(site.OPTIONAL["netherlands"], (["netherlands"], ["tno"]))
        self.assertEqual(site.OPTIONAL["belgium"], (["belgium"], ["dov", "spw"]))
        self.assertEqual(site.OPTIONAL["austria"], (["austria"], ["geosphere"]))
        self.assertEqual(site.OPTIONAL["poland"], (["poland"], ["pig"]))

    def test_고르면_WMS_로_도는_것만(self):
        got = self.names(["austria"], ["geosphere"])
        self.assertIn("geosphere:geology", got)
        self.assertNotIn(geosphere.UNITS50, got)                       # 1:5만은 REST 라 곧장 부를 길이 없다
        self.assertEqual(self.names(["netherlands"], ["tno"]), {"tno:geology"})
        self.assertTrue({"dov:tertiair_50k", "spw:geology"} <= self.names(["belgium"], ["dov", "spw"]))
        self.assertTrue({"pig:mgp500k", "pig:smgp50k"} <= self.names(["poland"], ["pig"]))

    def test_표는_문의_것을_그대로(self):
        t = static_tables.tables()
        for up in static_tables.ARC:
            layers = {name for door in t[up]["doors"] for name in door["layers"]}
            self.assertEqual(layers, static_tables.arc_layers(up))
        self.assertEqual(t["geosphere"]["legend"]["geosphere:geology"], "0")       # 서버의 `get_legend` 처럼 첫 레이어
        self.assertEqual(t["pig"]["legend"]["pig:mgp500k"], "11")                   # 폴란드는 마지막 레이어
        self.assertEqual(t["spw"]["legend"], {})                                    # 왈로니아는 범례를 두지 않는다
        self.assertEqual(t["tno"]["doors"][0]["infoParams"]["tno:geology"]["feature_count"], "1")

    def test_호주의_다른_서비스도_주소가_있다(self):
        # 지질구·핵심 광물·지구물리 격자(wetherilli 241) — 표에 없으면 정적 판에서 빈 레이어 이름으로 물었다
        other = static_tables.tables()["ga"]["other"]
        got = self.names(["australia"], ["ga"])
        self.assertTrue({n for n in got if not n.startswith(("ga:lith", "ga:age", "ga:faults"))} <= set(other))
