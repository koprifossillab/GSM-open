"""관리 화면과 개인 레이어 (wetherilli P08·118).

개인 레이어는 브라우저에만 있다 — 서버가 할 일은 화면을 내주는 것뿐이다. 읽개(`personal.js`)는
node 가 있으면 node 로 시험한다(`tests/js/personal_check.js`). CI(ubuntu)에는 node 가 있다.
"""
import shutil
import subprocess
from pathlib import Path

from django.test import TestCase

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent / "static" / "viewer"


class ManagePage(TestCase):
    def test_관리_화면이_뜬다(self):
        r = self.client.get("/GSM/manage/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn("viewer/personal.js", html)
        self.assertIn("viewer/manage.js", html)
        self.assertIn('href="/GSM/map/"', html)

    def test_지도에_관리_단추와_개인_레이어_블록이_있다(self):
        html = self.client.get("/GSM/map/").content.decode("utf-8")
        self.assertIn('id="manage-btn"', html)
        self.assertIn('href="/GSM/manage/"', html)
        self.assertIn('id="personal-list"', html)
        # 반입한 것이 없으면 감춘 채 뜬다 — map.js 가 저장소를 읽고 연다 (wetherilli 120)
        self.assertIn('id="box-personal" hidden', html)
        # 관리 단추는 설정 단추의 왼쪽이다
        self.assertLess(html.index('id="manage-btn"'), html.index('id="gear"'))

    def test_영어판(self):
        self.client.cookies["gsm_lang"] = "en"
        html = self.client.get("/GSM/manage/").content.decode("utf-8")
        self.assertIn("Import personal layer", html)


class PersonalReader(TestCase):
    def test_읽개(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 가 없다")
        r = subprocess.run([node, str(HERE / "js" / "personal_check.js"), str(STATIC / "personal.js")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
        self.assertEqual(r.stdout.strip(), "ok")
