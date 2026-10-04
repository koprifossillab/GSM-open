"""정적 판에 콜롬비아 1:50만을 실을 수 있게 — 고르면 싣는다 (wetherilli 201). 상류를 부르지 않는다."""
import importlib.util
import io
import json
import pathlib

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import sgc, static_tables, views

SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "deploy" / "static_site.py"


def static_site():
    spec = importlib.util.spec_from_file_location("static_site", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Colombia(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=io.StringIO())

    def names(self, spec):
        with override_settings(STATIC_SITE=spec):
            return {l["name"] for g in views._static_catalog(views._catalog("ko")) for l in g["layers"]}

    def test_콜롬비아_판만_서고_CGMW_는_빠진다(self):
        names = self.names({"regions": ["colombia"], "upstreams": ["sgc"]})
        self.assertIn("sgc:co:3", names)
        self.assertFalse(any(n.startswith("sgc:sa:") for n in names))

    def test_기본으로는_싣지_않는다(self):
        site = static_site()
        self.assertNotIn("colombia", site.REGIONS)
        self.assertNotIn("sgc", site.UPSTREAMS)
        self.assertEqual(site.OPTIONAL["colombia"], (["colombia"], ["sgc"]))
        names = self.names({"regions": site.REGIONS, "upstreams": site.UPSTREAMS})
        self.assertFalse(any(n.startswith("sgc:") for n in names))

    def test_표에는_열린_판만(self):
        table = static_tables.tables()["sgc"]
        self.assertEqual(set(table["sheets"]), {"co"})
        self.assertNotIn("CGMW", table["attribution"])
        self.assertNotIn("Sur_America", json.dumps(table))
        self.assertTrue(sgc.static_ok("sgc:co:60"))
        self.assertFalse(sgc.static_ok("sgc:sa:8"))
