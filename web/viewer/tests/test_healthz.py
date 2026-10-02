"""`/healthz/` 를 시험한다 (koprifossillab 002).

볼 것은 셋 — 레이어가 없으면 unhealthy(503), 백업 기록이 없거나 멈췄거나 낡았으면 degraded(200),
다 괜찮으면 ok. 백업 기록은 `weekly_backup.sh` 가 적는 꼴 그대로 만든다.
"""
import datetime
import json
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from viewer.models import Layer, LayerGroup

URL = "/GSM/healthz/"


def _record(path: Path, *, days_ago: float = 0, **fields):
    at = datetime.datetime.now().astimezone() - datetime.timedelta(days=days_ago)
    record = {"at": at.isoformat(timespec="seconds"), "result": "ok", "step": "fetch", "note": "다 했다",
              "backup": "/data/GSM/backups/GSM.20260930.tar.gz", "built": "same",
              "nas": "ok", "tiles": "ok", "sources": "ok", "fetch": "fetch_kopri"}
    record.update(fields)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


class 헬스(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.status = Path(self.tmp.name) / "backup_status.json"
        self.hourly = Path(self.tmp.name) / "hourly_status.json"
        patcher = override_settings(BACKUP_STATUS_FILE=str(self.status), HOURLY_STATUS_FILE=str(self.hourly),
                                    WIND_DIR=str(Path(self.tmp.name) / "wind"))
        patcher.enable()
        self.addCleanup(patcher.disable)
        # 매시 받기는 처음부터 괜찮게 두고, 그것을 보는 시험만 망가뜨린다 (koprifossillab 013)
        self._hourly()
        self._fresh()

    def _hourly(self, hours_ago=0.2, **jobs):
        now = datetime.datetime.now().astimezone() - datetime.timedelta(hours=hours_ago)
        at = now.isoformat(timespec="seconds")
        entries = {name: {"at": at, "result": "ok", "code": 0, "seconds": 3, "note": "할 일 없음", "last_ok": at}
                   for name in ("fetch_gfs_wind", "fetch_gmgsi", "fetch_araon")}
        for name, result in jobs.items():
            entries[name].update(result=result, code=1, note="상류가 500 으로 답했다")
        self.hourly.write_text(json.dumps({"at": at, "jobs": entries}), encoding="utf-8")

    def _fresh(self, gfs_hours=5, gmgsi_hours=1):
        from viewer import wind

        def stamp(hours):
            t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
            return t.strftime("%Y%m%d%H")
        with override_settings(WIND_DIR=str(Path(self.tmp.name) / "wind")):
            wind.write_index("gfs", [{"t": stamp(gfs_hours), "run": stamp(gfs_hours), "fh": 0}])
            wind.write_index("gmgsi", [{"t": stamp(gmgsi_hours)}])

    def _layer(self):
        group = LayerGroup.objects.create(name="지질도")
        Layer.objects.create(name="L_250K_Geology_Map", title="25만 지질도", group=group)

    def get(self):
        response = self.client.get(URL)
        return response.status_code, response.json()

    def test_레이어가_없으면_unhealthy(self):
        _record(self.status)
        code, body = self.get()
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "unhealthy")

    def test_다_괜찮으면_ok(self):
        self._layer()
        _record(self.status, days_ago=1)
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["db"]["layer"], 1)
        self.assertEqual(body["notes"], [])
        self.assertEqual(body["backup"]["age_days"], 1.0)

    def test_백업_기록이_없으면_degraded(self):
        self._layer()
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIsNone(body["backup"])

    def test_백업이_멈췄으면_degraded(self):
        self._layer()
        _record(self.status, result="fail", step="built", note="tar 실패")
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIn("built", body["notes"][0])

    def test_백업이_여드레를_넘으면_degraded(self):
        self._layer()
        _record(self.status, days_ago=9)
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")

    def test_NAS_가_실패하면_degraded(self):
        self._layer()
        _record(self.status, nas="fail", tiles="fail")
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")
        self.assertIn("nas, tiles", body["notes"][0])

    def test_깨진_기록도_죽지_않는다(self):
        self._layer()
        self.status.write_text("{깨진", encoding="utf-8")
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")

    def test_매시_받기의_기록이_없으면_degraded(self):
        self._layer()
        _record(self.status)
        self.hourly.unlink()
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(any("hourly.sh" in n for n in body["notes"]))

    def test_매시_받기가_멈추면_degraded(self):
        self._layer()
        _record(self.status)
        self._hourly(hours_ago=3)
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(any("cron" in n for n in body["notes"]))

    def test_한_일이_실패하면_degraded(self):
        self._layer()
        _record(self.status)
        self._hourly(fetch_gmgsi="fail")
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(any(n.startswith("fetch_gmgsi") for n in body["notes"]))

    def test_받아_둔_것이_낡으면_degraded(self):
        self._layer()
        _record(self.status)
        self._fresh(gfs_hours=20)
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["hourly"]["fresh"]["gfs"]["age_hours"] >= 19, True)
        self.assertTrue(any(n.startswith("gfs") for n in body["notes"]))

    def test_캐시하지_않는다(self):
        self._layer()
        _record(self.status)
        self.assertEqual(self.client.get(URL)["Cache-Control"], "no-store")
