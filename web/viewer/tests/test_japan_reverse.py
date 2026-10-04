"""일본 좌표 → 주소 (wetherilli 230). 상류를 부르지 않는다 — 브라우저가 곧장 부르는 것이라 여기서는 표만 본다."""
import io
import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from viewer.management.commands import build_japan_muni

MUNI = """GSI.MUNI_ARRAY = {};
GSI.MUNI_ARRAY["1101"] = '1,北海道,1101,札幌市　中央区';
GSI.MUNI_ARRAY["13101"] = '13,東京都,13101,千代田区';
"""
TABLE = Path(settings.BASE_DIR) / "viewer" / "static" / "viewer" / "japan-muni.json"


class Muni(SimpleTestCase):
    def test_muni_js_읽기(self):
        self.assertEqual(build_japan_muni.parse(MUNI), {"1101": "北海道札幌市中央区", "13101": "東京都千代田区"})

    def test_꼴이_다르면_멈춘다(self):
        with self.assertRaises(CommandError):
            build_japan_muni.parse('GSI.MUNI_ARRAY["13101"] = \'13,東京都,99999,千代田区\';')

    def test_적은_파일은_받지_않는다(self):
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as f:
            f.write(MUNI)
        with self.assertRaises(CommandError):
            call_command("build_japan_muni", f.name, stdout=io.StringIO())

    def test_구운_표(self):
        table = json.loads(TABLE.read_text(encoding="utf-8"))
        self.assertGreater(len(table), 1800)
        # 상류의 muniCd 는 앞에 0 이 붙어 온다(01101) — 화면이 수로 바꿔 찾는다
        self.assertEqual((table["1101"], table["13101"], table["47201"]), ("北海道札幌市中央区", "東京都千代田区", "沖縄県那覇市"))

    def test_화면이_부른다(self):
        js = (Path(settings.BASE_DIR) / "viewer" / "static" / "viewer" / "map.js").read_text(encoding="utf-8")
        self.assertIn("mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress", js)
        self.assertIn('"japan-muni.json"', js)
