"""관리 화면의 상류 응답 시간 (wetherilli 295) — `upstream_stats` 와 같은 값, 느린 차례, 이름과 수뿐."""
import datetime

from django.test import TestCase
from django.utils import timezone

from viewer import usage
from viewer.models import UpstreamDay


class Dashboard(TestCase):
    def setUp(self):
        for s in (0.3, 0.4, 0.5):
            usage.record("ga", ok=True, elapsed=s)
        for s in (6.0, 12.0):
            usage.record("ispra", ok=True, elapsed=s)
        usage.record("ispra", ok=False)
        usage.record("ispra", ok=False, blocked=True)
        # 사흘 전 — 지난 7 일에만 든다
        UpstreamDay.objects.create(day=timezone.localdate() - datetime.timedelta(days=3), upstream="sgs", ok=4, timed=4,
                                   seconds=8.0, t3=4)

    def test_요약(self):
        rows = usage.summary(7)
        self.assertEqual([r["name"] for r in rows], ["ispra", "sgs", "ga"])              # 지난 7 일 평균이 느린 차례
        ispra = rows[0]
        self.assertEqual((ispra["today"]["count"], ispra["today"]["fail"], ispra["today"]["mean"]), (4, 2, "9.0"))
        self.assertEqual(rows[1]["today"]["count"], 0)
        self.assertEqual((rows[1]["span"]["count"], rows[1]["span"]["p95"]), (4, "≤3"))

    def test_관리_화면(self):
        html = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('id="tab-upstream"', html)
        self.assertLess(html.index(">ispra<"), html.index(">ga<"))
        en = self.client.get("/GSM/manage/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
        self.assertIn("Upstream response times", en)
        self.assertNotIn("http", html.split('id="tab-upstream"')[1].split("</section>")[0])   # 주소가 없다


class Rollback(TestCase):
    def test_옛_코드도_행을_넣는다(self):
        """응답 시간 열을 모르는 v0.59 가 넣는 꼴 — 열에 db 기본값이 있어야 한다 (wetherilli 299)"""
        from django.db import connection
        with connection.cursor() as c:
            c.execute("INSERT INTO viewer_upstreamday (day, upstream, ok, fail, blocked) VALUES (%s, %s, 1, 0, 0)", ["2026-10-05", "old"])
        row = UpstreamDay.objects.get(upstream="old")
        self.assertEqual((row.timed, row.seconds, row.t9), (0, 0.0, 0))
