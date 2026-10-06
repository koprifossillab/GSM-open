"""상류 응답 시간 (wetherilli 290) — 문이 받은 응답의 `elapsed` 를 날마다 칸으로 센다. `upstream_stats` 가 평균·p95 를 보인다."""
import datetime
import io
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from viewer import usage
from viewer.models import UpstreamDay


class Timing(TestCase):
    def test_칸과_합(self):
        for s in (0.2, 0.7, 2.5, 2.9, 40.0):
            usage.record("sgs", ok=True, elapsed=datetime.timedelta(seconds=s))
        usage.record("sgs", ok=True, elapsed=mock.Mock())          # 시험의 Mock 은 세지 않는다
        usage.record("sgs", ok=False)                               # 시간 없이 센 실패
        row = UpstreamDay.objects.get(upstream="sgs")
        self.assertEqual((row.ok, row.fail, row.timed), (6, 1, 5))
        self.assertAlmostEqual(row.seconds, 46.3)
        self.assertEqual([row.t0, row.t1, row.t3, row.t9], [1, 1, 2, 1])

    def test_문이_elapsed_를_넘긴다(self):
        from viewer import sgs
        r = mock.Mock(status_code=200, content=b"png", url="https://x", headers={"content-type": "image/png"},
                      elapsed=datetime.timedelta(seconds=4.2))
        with mock.patch.object(sgs.requests, "get", return_value=r), mock.patch.object(sgs.usage, "paused", return_value=0):
            sgs._get("https://x/WMSServer", {"service": "WMS"})
        row = UpstreamDay.objects.get(upstream="sgs")
        self.assertEqual((row.timed, row.t4), (1, 1))

    def test_upstream_stats(self):
        for s in [0.3] * 18 + [6.0, 30.0]:
            usage.record("ispra", ok=True, elapsed=s)
        usage.record("ga", ok=True, elapsed=0.4)
        out = io.StringIO()
        call_command("upstream_stats", stdout=out)
        text = out.getvalue()
        self.assertIn("상류별 걸린 시간", text)
        summary = text.split("상류별 걸린 시간")[1]
        self.assertLess(summary.index("ispra"), summary.index("ga"))   # 느린 차례
        line = next(l for l in summary.splitlines() if l.startswith("ispra"))
        self.assertIn("≤8", line)                                      # 20 건 가운데 19 째가 6 초 칸(5–8)
        self.assertIn("2.1", line)                                     # 평균 (5.4+6+30)/20 = 2.07


class Batch(TestCase):
    """명령(대조·미리 데우기·받기)이 낸 호출을 따로 센다 (wetherilli 363)"""

    def test_어느_프로세스가_명령인가(self):
        self.assertTrue(usage._is_batch(["manage.py", "verify_layers", "--all"]))
        self.assertTrue(usage._is_batch(["/app/web/manage.py", "prewarm"]))
        self.assertTrue(usage._is_batch(["manage.py", "fetch_pbdb"]))
        self.assertFalse(usage._is_batch(["manage.py", "runserver", "0:8000"]))
        self.assertFalse(usage._is_batch(["manage.py", "test", "viewer"]))
        self.assertFalse(usage._is_batch(["/usr/local/bin/gunicorn", "gsmweb.wsgi:application"]))
        self.assertFalse(usage.BATCH)                                    # 시험은 화면 쪽

    def test_명령이면_따로_더한다(self):
        usage.record("bgr", ok=True, elapsed=1.0)
        with mock.patch.object(usage, "BATCH", True):
            usage.record("bgr", ok=True, elapsed=1.0)
            usage.record("bgr", ok=False)
        row = UpstreamDay.objects.get(upstream="bgr")
        self.assertEqual((row.ok, row.fail, row.batch), (2, 1, 2))
        today = usage.summary()[0]["today"]
        self.assertEqual((today["count"], today["batch"]), (3, 2))

    def test_upstream_stats_와_관리_화면에_선다(self):
        with mock.patch.object(usage, "BATCH", True):
            for _ in range(5):
                usage.record("gns", ok=True, elapsed=0.4)
        usage.record("gns", ok=True, elapsed=0.4)
        out = io.StringIO()
        call_command("upstream_stats", stdout=out)
        head, line = [l for l in out.getvalue().splitlines() if "명령" in l or " gns " in l][:2]
        self.assertIn("명령", head)
        self.assertTrue(line.rstrip().endswith("5"))
        html = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("(명령 5)", html)
        self.assertIn("(commands 5)", self.client.get("/GSM/manage/", HTTP_ACCEPT_LANGUAGE="en").content.decode())
