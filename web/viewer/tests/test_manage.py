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

    def test_공개_예시가_경고_없이_읽힌다(self):
        """docs/personal_layer/examples — AI 가 GSM-open 을 읽고 양식을 배우는 예시다 (wetherilli 399)"""
        node = shutil.which("node")
        if not node:
            self.skipTest("node 가 없다")
        examples = HERE.parents[2] / "docs" / "personal_layer" / "examples"
        r = subprocess.run([node, str(HERE / "js" / "personal_examples_check.js"), str(STATIC / "personal.js"), str(examples)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
        self.assertEqual(r.stdout.strip(), "ok")

    def test_공개_스키마가_예시와_맞는다(self):
        """schema.json 의 머리 열쇠·금지 열 이름이 예시와 어긋나지 않는다 — jsonschema 없이 굵은 것만"""
        import json
        root = HERE.parents[2] / "docs" / "personal_layer"
        schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
        allowed = set(schema["$defs"]["header"]["properties"])
        banned = set(schema["$defs"]["column"]["properties"]["key"]["not"]["enum"])
        for path in sorted((root / "examples").glob("*.geojson")):
            with self.subTest(path.name):
                doc = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(doc["gsm"]["format"], schema["$defs"]["header"]["properties"]["format"]["const"])
                self.assertLessEqual(set(doc["gsm"]), allowed)
                for f in doc["features"]:
                    self.assertFalse(set(f["properties"]) & banned)


class Visits(TestCase):
    """접속 기록 (wetherilli 399) — 화면을 연 것만 세고, 접속 주소는 staff 만 본다"""

    def test_화면만_센다(self):
        from viewer.models import VisitDay
        self.client.get("/GSM/map/", REMOTE_ADDR="10.0.0.7")
        self.client.get("/GSM/map/", REMOTE_ADDR="10.0.0.7")
        self.client.get("/GSM/earth/", HTTP_X_REAL_IP="10.0.0.8")
        self.client.get("/GSM/healthz/")
        row = VisitDay.objects.get(screen="map")
        self.assertEqual((row.client, row.count), ("10.0.0.7", 2))
        self.assertEqual(VisitDay.objects.get(screen="earth").client, "10.0.0.8")
        self.assertEqual(VisitDay.objects.count(), 2, "타일·healthz 는 세지 않는다")

    def test_1_년이_지난_줄은_지운다(self):
        import datetime

        from django.utils import timezone

        from viewer import visits
        from viewer.models import VisitDay
        old = timezone.localdate() - datetime.timedelta(days=visits.KEEP_DAYS + 1)
        VisitDay.objects.create(day=old, screen="map", client="10.0.0.1", count=3, last_at=timezone.now())
        visits._pruned_on = None
        self.client.get("/GSM/map/")
        self.assertFalse(VisitDay.objects.filter(day=old).exists())

    def test_접속_주소는_staff_만_본다(self):
        from django.contrib.auth.models import User
        self.client.get("/GSM/moon/", REMOTE_ADDR="10.9.8.7")
        html = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('data-tab="visits"', html)
        self.assertIn('id="mg-visits"', html)
        self.assertNotIn("10.9.8.7", html)
        User.objects.create_user("kim", password="pw", is_staff=True)
        self.client.login(username="kim", password="pw")
        html = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('id="mg-visit-clients"', html)
        self.assertIn("10.9.8.7", html)

    def test_밖에_연_판은_세지도_보이지도_않는다(self):
        from django.test import override_settings

        from viewer.models import VisitDay
        with override_settings(PUBLIC=True):
            self.client.get("/GSM/map/")
            html = self.client.get("/GSM/manage/").content.decode()
        self.assertFalse(VisitDay.objects.exists())
        self.assertNotIn('data-tab="visits"', html)


class ImportTool(TestCase):
    def test_도구_묶음의_링크_자리가_반입이다(self):
        """패널 밑의 "관리" 단추를 찾기 어렵다 — 도구 묶음에서 곧장 관리 화면으로 간다 (wetherilli 399)"""
        html = self.client.get("/GSM/map/").content.decode()
        self.assertIn('id="tool-import" href="/GSM/manage/"', html)
        self.assertNotIn('id="tool-share"', html)
