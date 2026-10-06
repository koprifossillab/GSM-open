"""받은 차례의 기록 — store.sqlite 의 fetch_log (jikhanjung P02 2 단계).

지키는 것 — 명령이 끝나면 한 줄(된 것·깨진 것 모두), 명령이 아는 것을 보탤 수 있다, 호스트는 sqlite 에 쓰지 않는다,
호스트가 남긴 것을 옮겨 적되 두 번 적지 않는다, 장부가 깨져도 명령은 돈다.
"""
import io
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import SimpleTestCase, override_settings

from viewer import fetchlog, sources


class Base(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        seed = self.dir / "seed.json"
        seed.write_text(json.dumps({"sources": [
            {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
             "runs_on": "container", "schedule": "manual", "license": "x"},
            {"id": "wind", "name": {"ko": "바람", "en": "Wind"}, "kind": "fetch", "commands": ["fetch_gfs_wind"],
             "runs_on": "host", "schedule": "hourly", "license": "x"},
        ]}), encoding="utf-8")
        over = override_settings(STORE_PATH=str(self.dir / "store.sqlite"), SOURCES_PATH=str(self.dir / "none.json"),
                                 SOURCES_SEED=seed, FETCH_LOG=True)
        over.enable()
        self.addCleanup(over.disable)
        sources._cache.update(key=None, spec=None)
        self.addCleanup(lambda: sources._cache.update(key=None, spec=None))
        env = mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "container"})
        env.start()
        self.addCleanup(env.stop)

    def rows(self):
        db = sqlite3.connect(self.dir / "store.sqlite")
        db.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in db.execute("SELECT * FROM fetch_log ORDER BY id")]
        finally:
            db.close()


class Record(Base):
    def test_된_것을_적고_마지막_말과_보탠_칸을_남긴다(self):
        with fetchlog.record("demo", "fetch_demo") as tail:
            tail.write("받는다 …\n\n  1 234 곳을 구웠다\n")
            fetchlog.note(rows=1234, expected=1234, raw_path="earth/x.csv", 엉뚱한="버린다")
        [row] = self.rows()
        self.assertEqual((row["source"], row["result"], row["rows"], row["expected"]), ("demo", "ok", 1234, 1234))
        self.assertEqual(row["note"], "1 234 곳을 구웠다")
        self.assertEqual(row["raw_path"], "earth/x.csv")
        self.assertEqual(row["origin"], "container")

    def test_깨지면_fail_과_까닭을_적고_다시_던진다(self):
        with self.assertRaises(CommandError):
            with fetchlog.record("demo", "fetch_demo"):
                raise CommandError("상류가 500 을 줬다")
        [row] = self.rows()
        self.assertEqual(row["result"], "fail")
        self.assertIn("상류가 500", row["note"])

    def test_장부가_깨져도_명령은_돈다(self):
        with override_settings(STORE_PATH="/proc/못쓰는자리/store.sqlite"):
            with fetchlog.record("demo", "fetch_demo"):
                done = True
        self.assertTrue(done)

    def test_호스트는_sqlite_에_쓰지_않는다(self):
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host", "GSM_HOURLY_JOB": "1"}):
            with fetchlog.record("wind", "fetch_gfs_wind", "hourly"):
                pass                                         # hourly.sh 가 부른 일 — hourly_status.json 이 남긴다
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            with fetchlog.record("era5", "build_era5_wind", "manual"):
                pass                                         # 사람이 부른 일 — jsonl 에 한 줄
            with fetchlog.record("araon", "fetch_araon", "hourly"):
                pass                                         # 매시 일이라도 손으로 부른 것(--past)은 jsonl 에 (#369 검토 5)
        self.assertFalse((self.dir / "store.sqlite").exists())
        lines = (self.dir / "fetch_log_host.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["source"] for x in lines], ["era5", "araon"])

    def test_호스트는_읽기만_해도_파일을_만들지_않고_읽기_전용으로_연다(self):
        """#369 검토 1 — latest()·history() 가 connect() 로 파일·표를 만들었다"""
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            self.assertEqual(fetchlog.latest(), {})
            self.assertEqual(fetchlog.history("demo"), [])
            self.assertFalse((self.dir / "store.sqlite").exists())
            with self.assertRaises(RuntimeError):
                fetchlog.write({"source": "x", "started_at": "t", "result": "ok"})
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T00:00:00+09:00", "result": "ok"})
        before = (self.dir / "store.sqlite").stat().st_mtime_ns
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            self.assertIn("demo", fetchlog.latest())
            self.assertEqual(len(fetchlog.history("demo")), 1)
        self.assertEqual((self.dir / "store.sqlite").stat().st_mtime_ns, before)

    def test_장부_파일을_지워도_다시_짓는다(self):
        """#369 검토 6 — 표를 지었다는 기억이 프로세스에 남아 지운 뒤 소리 없이 끊겼다"""
        fetchlog.write({"source": "demo", "started_at": "a", "result": "ok"})
        (self.dir / "store.sqlite").unlink()
        fetchlog.write({"source": "demo", "started_at": "b", "result": "ok"})
        self.assertEqual([r["started_at"] for r in self.rows()], ["b"])


class Sync(Base):
    def test_hourly_status_와_호스트_기록을_한_번만_옮겨_적는다(self):
        (self.dir / "hourly_status.json").write_text(json.dumps({"jobs": {
            "fetch_gfs_wind": {"at": "2026-10-06T16:40:02+09:00", "result": "ok", "seconds": 2, "note": "할 일 없음",
                               "last_ok": "2026-10-06T16:40:02+09:00"},
            "fetch_모르는것": {"at": "2026-10-06T16:40:02+09:00", "result": "ok"},
        }}), encoding="utf-8")
        (self.dir / "fetch_log_host.jsonl").write_text(json.dumps(
            {"source": "era5", "command": "build_era5_wind", "started_at": "2026-10-05T10:00:00+09:00",
             "result": "ok", "seconds": 60}) + "\n깨진 줄\n", encoding="utf-8")
        self.assertEqual(fetchlog.sync(), 2)
        self.assertEqual(fetchlog.sync(), 0)             # 두 번 적지 않는다
        got = {(r["source"], r["origin"], r["started_at"]) for r in self.rows()}
        self.assertIn(("wind", "hourly", "2026-10-06T16:40:00+09:00"), got)   # at 은 끝난 때 — 걸린 초만큼 당긴다 (검토 3)
        self.assertIn(("era5", "host", "2026-10-05T10:00:00+09:00"), got)

    def test_실패_전의_성공도_옮긴다(self):
        """#369 검토 3 — 옮기기 전에 성공 뒤 실패가 오면 성공 줄이 빠졌다"""
        (self.dir / "hourly_status.json").write_text(json.dumps({"jobs": {
            "fetch_gfs_wind": {"at": "2026-10-06T16:40:05+09:00", "result": "fail", "seconds": 5, "note": "상류 500",
                               "last_ok": "2026-10-06T15:40:03+09:00"}}}), encoding="utf-8")
        fetchlog.sync()
        got = fetchlog.latest()["wind"]
        self.assertEqual(got["last"]["result"], "fail")
        self.assertEqual(got["last_ok"]["started_at"], "2026-10-06T15:40:03+09:00")

    def test_옮긴_성공을_실패_뒤에_또_적지_않는다(self):
        """#369 다시 검토 — 성공을 옮긴 뒤 실패가 오면 그 성공이 끝난 때로 한 줄 더 생겼다"""
        status = self.dir / "hourly_status.json"
        status.write_text(json.dumps({"jobs": {"fetch_gfs_wind": {
            "at": "2026-10-06T15:40:03+09:00", "result": "ok", "seconds": 3, "note": "",
            "last_ok": "2026-10-06T15:40:03+09:00", "last_ok_seconds": 3}}}), encoding="utf-8")
        fetchlog.sync()
        status.write_text(json.dumps({"jobs": {"fetch_gfs_wind": {
            "at": "2026-10-06T16:40:05+09:00", "result": "fail", "seconds": 5, "note": "상류 500",
            "last_ok": "2026-10-06T15:40:03+09:00", "last_ok_seconds": 3}}}), encoding="utf-8")
        fetchlog.sync()
        oks = [r["started_at"] for r in self.rows() if r["source"] == "wind" and r["result"] == "ok"]
        self.assertEqual(oks, ["2026-10-06T15:40:00+09:00"])

    def test_옛_상태_파일이어도_옮긴_성공을_또_적지_않는다(self):
        """`last_ok_seconds` 가 없는 옛 hourly_status.json — 이미 옮긴 성공이 끝난 때 안쪽에 있으면 건너뛴다"""
        status = self.dir / "hourly_status.json"
        status.write_text(json.dumps({"jobs": {"fetch_gfs_wind": {
            "at": "2026-10-06T15:40:03+09:00", "result": "ok", "seconds": 3, "last_ok": "2026-10-06T15:40:03+09:00"}}}),
            encoding="utf-8")
        fetchlog.sync()
        status.write_text(json.dumps({"jobs": {"fetch_gfs_wind": {
            "at": "2026-10-06T16:40:05+09:00", "result": "fail", "seconds": 5, "last_ok": "2026-10-06T15:40:03+09:00"}}}),
            encoding="utf-8")
        fetchlog.sync()
        oks = [r["started_at"] for r in self.rows() if r["source"] == "wind" and r["result"] == "ok"]
        self.assertEqual(oks, ["2026-10-06T15:40:00+09:00"])

    def test_호스트_기록은_읽은_자리_뒤만_읽는다(self):
        """#369 검토 7 — 부를 때마다 jsonl 전체를 읽었다. 덜 적힌 마지막 줄은 다음 차례에"""
        p = self.dir / "fetch_log_host.jsonl"
        one = json.dumps({"source": "era5", "started_at": "t1", "result": "ok"})
        two = json.dumps({"source": "era5", "started_at": "t2", "result": "ok"})
        p.write_text(one + "\n" + two[:10], encoding="utf-8")      # 둘째 줄은 아직 덜 적혔다
        self.assertEqual(fetchlog.sync(), 1)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(two[10:] + "\n")
        self.assertEqual(fetchlog.sync(), 1)
        self.assertEqual(sorted(r["started_at"] for r in self.rows()), ["t1", "t2"])

    def test_장부를_못_열어도_옮겨_적기는_죽지_않는다(self):
        """#369 검토 4 — sqlite3.Error 만 잡아 권한 오류에 sources_log·sources_backfill 이 죽었다"""
        with override_settings(STORE_PATH="/proc/못쓰는자리/store.sqlite"):
            self.assertEqual(fetchlog.sync(), 0)
            out, err = io.StringIO(), io.StringIO()
            call_command("sources_backfill", stdout=out, stderr=err)
            call_command("sources_log", stdout=out, stderr=err)

    def test_데이터소스마다_마지막과_마지막으로_된_것(self):
        for at, result in (("2026-10-01T00:00:00+09:00", "ok"), ("2026-10-02T00:00:00+09:00", "fail")):
            fetchlog.write({"source": "demo", "started_at": at, "result": result})
        got = fetchlog.latest()["demo"]
        self.assertEqual(got["last"]["result"], "fail")
        self.assertEqual(got["last_ok"]["started_at"][:10], "2026-10-01")
        self.assertEqual(len(fetchlog.history("demo")), 2)


class WrapsCommands(Base):
    def test_fetch_build_명령이_끝나면_한_줄이_생긴다(self):
        """apps.py 가 BaseCommand.execute 를 감쌌다 — 진짜 명령 하나로 본다(빈 자리라 할 일이 없다)"""
        out = io.StringIO()
        with override_settings(KIGAM50K_DIR=str(self.dir / "k")):
            call_command("sources_seed", "--check", stdout=io.StringIO(), stderr=io.StringIO())   # 기록 대상이 아니다
            with mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle",
                            side_effect=lambda *a, **k: None):
                call_command("fetch_kigam50k", stdout=out)
        rows = self.rows()
        self.assertEqual([(r["command"], r["result"]) for r in rows], [("fetch_kigam50k", "ok")])
        self.assertEqual(rows[0]["source"], "fetch_kigam50k")   # 이 시험의 명세에 없는 명령 — 이름을 데이터소스로

    def test_시험에서는_끈다(self):
        with override_settings(FETCH_LOG=False), \
                mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle", side_effect=lambda *a, **k: None):
            call_command("fetch_kigam50k", stdout=io.StringIO())
        self.assertFalse((self.dir / "store.sqlite").exists())

    def test_감싸기는_한_번뿐이다(self):
        self.assertTrue(getattr(BaseCommand.execute, "_gsm_recorded", False))


class SpecChange(Base):
    def test_명세가_바뀌면_기록_표에도_한_줄(self):
        live = self.dir / "live.json"
        with override_settings(SOURCES_PATH=str(live)):
            live.write_text(json.dumps({"sources": []}), encoding="utf-8")
            sources._cache.update(key=None, spec=None)
            sources.load()
        self.assertEqual([r["source"] for r in self.rows()], ["_spec"])

    def test_호스트가_먼저_읽어도_컨테이너가_이력과_줄을_남긴다(self):
        """#369 검토 2 — 호스트가 이력만 뜨고 _spec 줄을 건너뛰면, 뒤에 컨테이너는 "이미 뜬 판" 이라 아무것도 남기지 않았다"""
        live = self.dir / "live.json"
        history = self.dir / "sources_history"
        with override_settings(SOURCES_PATH=str(live)):
            live.write_text(json.dumps({"sources": []}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
                sources._cache.update(key=None, spec=None)
                sources.load()
            self.assertFalse(history.exists() and any(history.glob("*.json")), "호스트가 이력을 떴다")
            sources._cache.update(key=None, spec=None)
            sources.load()
        self.assertEqual(len(list(history.glob("*.json"))), 1)
        self.assertEqual([r["source"] for r in self.rows()], ["_spec"])


class Overview(Base):
    """관리 화면의 "데이터소스" 탭과 healthz (P02 3 단계)."""

    databases = {"default"}            # 관리 화면이 상류 응답 시간(UpstreamDay)을 읽는다 — 읽기만

    def setUp(self):
        super().setUp()
        from datetime import datetime, timedelta
        now = datetime.now().astimezone()
        old = (now - timedelta(hours=10)).isoformat(timespec="seconds")
        fresh = (now - timedelta(minutes=20)).isoformat(timespec="seconds")
        fetchlog.write({"source": "wind", "command": "fetch_gfs_wind", "started_at": old, "result": "ok",
                        "origin": "hourly"})                                        # 매시인데 10 시간 전 — 늦음
        fetchlog.write({"source": "demo", "command": "fetch_demo", "started_at": fresh, "result": "fail",
                        "note": "상류가 500", "expected": 100, "rows": 80})          # 깨짐, 센 수보다 적게

    def test_늦음_깨짐_센_수(self):
        ov = sources.overview(sync=False)
        by = {r["row"]["id"]: r for r in ov["rows"]}
        self.assertTrue(by["wind"]["late"])
        self.assertFalse(by["demo"]["late"])               # manual 은 늦지 않는다
        self.assertTrue(by["demo"]["failed"])
        self.assertEqual(ov["counts"]["late"], 1)
        self.assertEqual(ov["counts"]["failed"], 1)

    def test_관리_화면(self):
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('id="tab-sources"', page)
        self.assertNotIn('id="tab-data"', page)
        self.assertIn('data-tab="sources">데이터소스<', page)          # 한국어 표기는 "데이터소스" (사람, 2026-10-06)
        self.assertIn('data-src="wind"', page)
        self.assertIn("센 수 100 · 받은 수 80", page)
        self.assertIn("상류가 500", page)
        self.assertNotIn(str(self.dir), page)              # 절대 경로는 내지 않는다
        en = self.client.get("/GSM/manage/", HTTP_COOKIE="gsm_lang=en").content.decode()
        self.assertIn("counted 100 · received 80", en)
        self.assertIn(">Wind<", en)                         # 이름은 명세의 en

    def test_화면에는_경로와_열쇠를_내지_않는다(self):
        """#373 검토 1 — 명령의 마지막 줄·예외 글이 걸러지지 않고 계정을 묻지 않는 화면에 떴다"""
        from datetime import datetime
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        fetchlog.write({"source": "demo", "command": "fetch_demo", "started_at": now, "result": "fail",
                        "note": f"받았다 → {self.dir}/earth/x.json · /srv/GSM/db/kopri/araon.json · "
                                "https://example.org/wms?key=SECRET123&whoami=me@example.org&x=1"})
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertNotIn(str(self.dir), page)
        self.assertNotIn("/srv/GSM", page)
        self.assertNotIn("SECRET123", page)
        self.assertNotIn("me@example.org", page)
        self.assertIn("&lt;DB 옆&gt;/earth/x.json", page)
        self.assertIn("araon.json", page)
        self.assertIn("key=…", page)

    def test_shown(self):
        self.assertEqual(fetchlog.shown(""), "")
        self.assertEqual(fetchlog.shown("→ /home/someone/data/a.zip"), "→ a.zip")
        self.assertEqual(fetchlog.shown("https://h.org/data/a?token=abc"), "https://h.org/data/a?token=…")   # 주소 안의 경로는 둔다
        self.assertEqual(fetchlog.shown(f"{self.dir}/store.sqlite"), "<DB 옆>/store.sqlite")

    def test_healthz_는_장부에_쓰지_않는다(self):
        """#373 검토 2 — 공개 GET 마다 옮겨 적으며 쓰기 트랜잭션이 돌았다"""
        with mock.patch.object(fetchlog, "sync") as sync:
            self.client.get("/GSM/healthz/")
        sync.assert_not_called()

    def test_밖에_연_판에서는_내부용을_내린다(self):
        """#373 검토 5 — GSM_PUBLIC 이어도 연구실 내부용 데이터소스의 줄·지난 차례가 보였다"""
        live = self.dir / "public.json"
        rows = [{**r, "flags": ["lab_only"]} if r["id"] == "demo" else r for r in json.loads((self.dir / "seed.json").read_text())["sources"]]
        live.write_text(json.dumps({"sources": rows}), encoding="utf-8")
        with override_settings(SOURCES_PATH=str(live), PUBLIC=True):
            sources._cache.update(key=None, spec=None)
            ids = [r["row"]["id"] for r in sources.overview(sync=False)["rows"]]
        sources._cache.update(key=None, spec=None)
        self.assertNotIn("demo", ids)
        self.assertIn("wind", ids)

    def test_healthz_에_수(self):
        data = self.client.get("/GSM/healthz/").json()
        self.assertEqual(data["sources"]["late"], 1)
        self.assertEqual(data["sources"]["failed"], 1)
        self.assertEqual(data["sources"]["total"], 2)
