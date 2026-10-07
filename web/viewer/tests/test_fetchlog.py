"""받은 차례의 기록 — `GSM.db` 의 `FetchRun` (jikhanjung P02 2 단계, P03 에서 store.sqlite 의 fetch_log 를 옮겼다).

지키는 것 — 명령이 끝나면 한 줄(된 것·깨진 것 모두), 명령이 아는 것을 보탤 수 있다, 호스트는 기록 표에 쓰지 않는다,
호스트가 남긴 것을 옮겨 적되 두 번 적지 않는다, 장부가 깨져도 명령은 돈다, 관리 화면·healthz.
"""
import io
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from viewer import fetchlog, sources
from viewer.models import FetchRun

DEMO = {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
        "runs_on": "container", "schedule": "manual", "license": "x"}
WIND = {"id": "wind", "name": {"ko": "바람", "en": "Wind"}, "kind": "fetch", "commands": ["fetch_gfs_wind"],
        "runs_on": "host", "schedule": "hourly", "license": "x"}


class Base(TestCase):
    """명세는 씨앗(데모·바람 둘)에서 읽는다 — 표가 비었으니. 호스트가 남기는 파일은 STORE_PATH 옆(임시 자리)에."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.seed = self.dir / "seed.json"
        self.seed.write_text(json.dumps({"sources": [DEMO, WIND]}), encoding="utf-8")
        over = override_settings(STORE_PATH=str(self.dir / "store.sqlite"), SOURCES_PATH=str(self.dir / "none.json"),
                                 SOURCES_SEED=self.seed, FETCH_LOG=True)
        over.enable()
        self.addCleanup(over.disable)
        env = mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "container"})
        env.start()
        self.addCleanup(env.stop)

    def rows(self):
        return [fetchlog.as_dict(r) for r in FetchRun.objects.order_by("id")]

    def put(self, *rows):
        """명세를 표에 — 씨앗이 아니라 운영의 명세로 읽히게"""
        sources._put(list(rows), "seed")


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
        with mock.patch.object(FetchRun.objects, "bulk_create", side_effect=DatabaseError("database is locked")):
            with fetchlog.record("demo", "fetch_demo"):
                done = True
        self.assertTrue(done)

    def test_호스트는_기록_표에_쓰지_않는다(self):
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host", "GSM_HOURLY_JOB": "1"}):
            with fetchlog.record("wind", "fetch_gfs_wind", "hourly"):
                pass                                         # hourly.sh 가 부른 일 — hourly_status.json 이 남긴다
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            with fetchlog.record("era5", "build_era5_wind", "manual"):
                pass                                         # 사람이 부른 일 — jsonl 에 한 줄
            with fetchlog.record("araon", "fetch_araon", "hourly"):
                pass                                         # 매시 일이라도 손으로 부른 것(--past)은 jsonl 에 (#369 검토 5)
        self.assertEqual(FetchRun.objects.count(), 0)
        lines = (self.dir / "fetch_log_host.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["source"] for x in lines], ["era5", "araon"])

    def test_호스트는_DB_를_열지_않는다(self):
        """사람, 2026-10-07 — 호스트가 DB 를 건드려야 하면 컨테이너를 거친다. 호스트의 명령은 파일만 남긴다"""
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}), \
                mock.patch.object(sources, "load", side_effect=AssertionError("호스트가 명세를 읽었다")), \
                mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle", side_effect=lambda *a, **k: None), \
                override_settings(KIGAM50K_DIR=str(self.dir / "k")), CaptureQueriesContext(connection) as ctx:
            call_command("fetch_kigam50k", stdout=io.StringIO())          # apps.py 의 감싸기 — 명세를 읽지 않고 명령 이름을
            from viewer import usage
            usage.record("kopri", ok=True, elapsed=1.2)                  # 상류 호출 수 — 파일에
            with self.assertRaises(RuntimeError):
                fetchlog.write({"source": "x", "started_at": "2026-10-06T00:00:00+09:00", "result": "ok"})
            self.assertEqual(fetchlog.sync(), 0)
            for name in ("sources_log", "sources_import", "sources_seed", "sources_backfill", "prune_raw"):
                with self.assertRaisesRegex(CommandError, "컨테이너 안에서"):
                    call_command(name, stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(ctx.captured_queries, [])
        [line] = (self.dir / "fetch_log_host.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(line)["source"], "fetch_kigam50k")
        self.assertTrue((self.dir / "upstream_host.jsonl").exists())

    def test_호스트의_설정은_DB_엔진이_없다(self):
        import subprocess
        import sys
        web = Path(__file__).resolve().parents[2]
        code = ("import django; django.setup()\n"
                "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])\n"
                "from viewer.models import DataSource\n"
                "try:\n    DataSource.objects.count()\nexcept Exception as e:\n    print(type(e).__name__)\n")
        env = {**os.environ, "GSM_RUN_PLACE": "host", "DJANGO_SETTINGS_MODULE": "gsmweb.settings", "GSM_SECRET_KEY": "x"}
        out = subprocess.run([sys.executable, "-c", code], cwd=web, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.stdout.split(), ["django.db.backends.dummy", "ImproperlyConfigured"], out.stderr[-500:])

    def test_때를_못_읽는_줄은_버린다(self):
        self.assertEqual(fetchlog.write_many([{"source": "demo", "started_at": "어제", "result": "ok"},
                                              {"source": "demo", "started_at": "2026-10-06T00:00:00", "result": "ok"}]), 1)
        self.assertEqual(self.rows()[0]["started_at"], "2026-10-06T00:00:00+09:00")   # 시간대가 없으면 이 서버의 것


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
        one = json.dumps({"source": "era5", "started_at": "2026-10-05T01:00:00+09:00", "result": "ok"})
        two = json.dumps({"source": "era5", "started_at": "2026-10-05T02:00:00+09:00", "result": "ok"})
        p.write_text(one + "\n" + two[:10], encoding="utf-8")      # 둘째 줄은 아직 덜 적혔다
        self.assertEqual(fetchlog.sync(), 1)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(two[10:] + "\n")
        self.assertEqual(fetchlog.sync(), 1)
        self.assertEqual(sorted(r["started_at"][11:13] for r in self.rows()), ["01", "02"])

    def test_장부에_못_적어도_옮겨_적기는_죽지_않는다(self):
        """#369 검토 4 — 장부의 잘못에 sources_log·sources_backfill 이 죽었다"""
        (self.dir / "hourly_status.json").write_text(json.dumps({"jobs": {
            "fetch_gfs_wind": {"at": "2026-10-06T16:40:02+09:00", "result": "ok", "seconds": 2}}}), encoding="utf-8")
        with mock.patch.object(FetchRun.objects, "bulk_create", side_effect=DatabaseError("database is locked")):
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


class FromHost(Base):
    """호스트가 남긴 파일을 컨테이너가 들인다 (P03) — 명령 이름은 데이터소스로, 상류 호출 수는 UpstreamDay 로."""

    def test_명령_이름을_데이터소스로(self):
        (self.dir / "fetch_log_host.jsonl").write_text("\n".join(json.dumps(r) for r in (
            {"source": "fetch_gfs_wind", "command": "fetch_gfs_wind", "started_at": "2026-10-07T01:00:00+09:00", "result": "ok"},
            {"source": "wind", "command": "fetch_gfs_wind", "started_at": "2026-10-07T02:00:00+09:00", "result": "ok"},  # 옛 줄
            {"source": "build_모르는것", "started_at": "2026-10-07T03:00:00+09:00", "result": "ok"},
        )) + "\n", encoding="utf-8")
        self.assertEqual(fetchlog.sync(), 3)
        self.assertEqual(sorted(r["source"] for r in self.rows()), ["build_모르는것", "wind", "wind"])

    def test_상류_호출_수를_한_번만_더한다(self):
        from viewer import usage
        from viewer.models import UpstreamDay
        self.addCleanup(usage.reset)       # 차단 조짐 수는 프로세스에 남는다 — 같은 일꾼의 다른 시험이 "쉬는 중" 에 걸리지 않게
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            usage.record("kopri", ok=True, elapsed=1.2)
            usage.record("kopri", ok=False)
            usage.record("kopri", ok=False, blocked=True)
        self.assertFalse(UpstreamDay.objects.exists())
        fetchlog.sync()
        fetchlog.sync()                                   # 두 번 더하지 않는다
        row = UpstreamDay.objects.get(upstream="kopri")
        self.assertEqual((row.ok, row.fail, row.blocked, row.timed), (1, 1, 1, 1))


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

    def test_명세의_명령이면_그_데이터소스로(self):
        self.put(DEMO, {**WIND, "commands": ["fetch_kigam50k"]})
        with override_settings(KIGAM50K_DIR=str(self.dir / "k")), \
                mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle", side_effect=lambda *a, **k: None):
            call_command("fetch_kigam50k", stdout=io.StringIO())
        self.assertEqual(self.rows()[0]["source"], "wind")

    def test_시험에서는_끈다(self):
        with override_settings(FETCH_LOG=False), \
                mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle", side_effect=lambda *a, **k: None):
            call_command("fetch_kigam50k", stdout=io.StringIO())
        self.assertEqual(FetchRun.objects.count(), 0)

    def test_감싸기는_한_번뿐이다(self):
        self.assertTrue(getattr(BaseCommand.execute, "_gsm_recorded", False))


class Overview(Base):
    """관리 화면의 "데이터소스" 탭과 healthz (P02 3 단계)."""

    def setUp(self):
        super().setUp()
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
        self.assertIn('href="/GSM/admin/viewer/datasource/"', page)     # 명세는 admin 에서 고친다 (P03)
        en = self.client.get("/GSM/manage/", HTTP_COOKIE="gsm_lang=en").content.decode()
        self.assertIn("counted 100 · received 80", en)
        self.assertIn(">Wind<", en)                         # 이름은 명세의 en

    def test_화면에는_경로와_열쇠를_내지_않는다(self):
        """#373 검토 1 — 명령의 마지막 줄·예외 글이 걸러지지 않고 계정을 묻지 않는 화면에 떴다"""
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
        self.put({**DEMO, "flags": ["lab_only"]}, WIND)
        with override_settings(PUBLIC=True):
            ids = [r["row"]["id"] for r in sources.overview(sync=False)["rows"]]
        self.assertNotIn("demo", ids)
        self.assertIn("wind", ids)

    def test_healthz_에_수(self):
        data = self.client.get("/GSM/healthz/").json()
        self.assertEqual(data["sources"]["late"], 1)
        self.assertEqual(data["sources"]["failed"], 1)
        self.assertEqual(data["sources"]["total"], 2)


class Followup(Base):
    """#373 검토의 "나중에" 넷 — 영어판의 코드 값·늦음의 빈틈·성능·자잘한 것."""

    def test_시간대가_달라도_때의_순서로(self):
        """검토 6 — 글자로 정렬해 호스트(+09:00)와 컨테이너(UTC)가 섞이면 순서가 틀렸다. 이제 UTC 로 적힌다(P03)"""
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T10:00:00+09:00", "result": "ok"})    # 01:00Z
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T02:00:00+00:00", "result": "fail"})  # 02:00Z — 나중
        got = fetchlog.latest()["demo"]
        self.assertEqual(got["last"]["result"], "fail")
        self.assertEqual(got["last"]["started_at"], "2026-10-06T11:00:00+09:00")    # 바깥에는 이 서버의 시간대로
        self.assertEqual(got["first"]["result"], "ok")
        self.assertEqual([h["result"] for h in fetchlog.history("demo")], ["fail", "ok"])

    def test_시간대만_다른_같은_때는_한_줄(self):
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T10:00:00+09:00", "result": "ok"})
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T01:00:00+00:00", "result": "ok"})
        self.assertEqual(FetchRun.objects.count(), 1)

    def test_건너뜀은_된_것으로_치지_않는다(self):
        """검토 6 — skip 을 된 것으로 쳐 늦음이 가려질 수 있었다"""
        fetchlog.write({"source": "wind", "started_at": "2026-10-06T00:00:00+09:00", "result": "skip"})
        self.assertIsNone(fetchlog.latest()["wind"]["last_ok"])

    def test_한_번도_된_적_없는_매시_일은_첫_차례부터_잰다(self):
        """검토 6 — 처음부터 깨진 매시 일은 깨짐으로만 떠 늦음에 안 잡혔다"""
        now = datetime.now().astimezone()
        for hours in (10, 0.2):
            fetchlog.write({"source": "wind", "started_at": (now - timedelta(hours=hours)).isoformat(timespec="seconds"),
                            "result": "fail"})
        ov = {r["row"]["id"]: r for r in sources.overview(sync=False)["rows"]}
        self.assertTrue(ov["wind"]["late"])
        self.assertTrue(ov["wind"]["failed"])
        self.assertFalse(sources.is_late({"schedule": "hourly"}, None,
                                         first={"started_at": (now - timedelta(hours=1)).isoformat()}))

    def test_지난_차례는_한_번에(self):
        """검토 7 — 데이터소스마다 연결을 열었다. 이제 질의 수가 데이터소스 수와 상관없다"""
        for i in range(25):
            fetchlog.write({"source": "demo", "started_at": f"2026-10-{1 + i % 9:02d}T{i % 24:02d}:00:00+09:00", "result": "ok"})
        fetchlog.write({"source": "wind", "started_at": "2026-10-06T00:00:00+09:00", "result": "ok"})
        got = fetchlog.history_many(["demo", "wind", "없음"], 20)
        self.assertEqual(len(got["demo"]), 20)
        self.assertEqual(got["demo"], fetchlog.history("demo", 20))
        self.assertEqual(len(got["wind"]), 1)
        self.assertNotIn("없음", got)
        stamps = [h["started_at"] for h in got["demo"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))           # 새것부터
        with CaptureQueriesContext(connection) as ctx:
            sources.overview(sync=False)
        self.assertLessEqual(len(ctx.captured_queries), 8)

    def test_healthz_는_구운_파일을_보지_않는다(self):
        """검토 7 — healthz 가 datastatus.rows() 를 두 번 불렀다"""
        from viewer import datastatus
        with mock.patch.object(datastatus, "rows", wraps=datastatus.rows) as rows:
            self.client.get("/GSM/healthz/")
        rows.assert_not_called()

    def test_영어판은_코드_값과_고정_문장을_옮긴다(self):
        """검토 4 — origin·result·seed 와 장부가 한국어로 적은 고정 문장이 그대로 떴다"""
        fetchlog.write({"source": "wind", "started_at": "2026-10-06T00:00:00+09:00", "result": "ok", "origin": "hourly",
                        "note": "마지막으로 된 차례"})
        self.assertEqual(str(fetchlog.note_text("명세가 바뀌었다 — a.json")), "명세가 바뀌었다 — a.json")
        ko = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("매시 차례", ko)
        self.assertIn("저장소의 씨앗", ko)                    # 표가 비어 명세를 씨앗에서 읽었다
        en = self.client.get("/GSM/manage/", HTTP_COOKIE="gsm_lang=en").content.decode()
        for text in ("Last successful run", "hourly run", "the repository seed", ">ok<"):
            self.assertIn(text, en)
        for text in ('mg-said">마지막으로 된 차례', "<small>hourly ·", "seed 을"):    # 페이지에 실린 번역표에는 원문이 있다
            self.assertNotIn(text, en)

    def test_명세가_없으면_안내가_뜬다(self):
        """검토 8 — origin 이 none 이면 빈 표만 섰다"""
        with override_settings(SOURCES_SEED=self.dir / "없는씨앗.json"):
            page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("manage.py sources_seed", page)

    def test_펼치는_줄과_산출물의_설명(self):
        """검토 8 — aria-expanded, 산출물 칸에 datastatus 의 무엇·만드는 명령"""
        self.put({**DEMO, "outputs": ["earth/pbdb.sqlite"]}, WIND)
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('class="mg-src-toggle" aria-expanded="false" aria-controls="mg-src-more-demo"', page)
        self.assertNotIn('role="button"', page)            # 표의 줄은 줄로 둔다 — 펼치는 것은 이름 칸의 단추 (#375 검토)
        self.assertIn('id="mg-src-more-demo"', page)
        self.assertIn('class="mg-out-what"', page)
        self.assertIn('← <span class="mono">fetch_pbdb', page)          # 만드는 명령은 펼친 줄에 — title 은 휴대폰에서 볼 길이 없다 (#375 검토)

    def test_결과는_따로_칸(self):
        """성공·실패는 마지막 실행 칸에 섞지 않고 따로 칸에 (사람, 2026-10-06)"""
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T00:00:00+09:00", "result": "fail", "note": "상류 500"})
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('<th>마지막 실행</th><th>결과</th><th>마지막 성공</th>', page)
        self.assertRegex(page, r'<td data-label="결과"><span class="mg-res fail">실패</span>\s*<small class="mg-said">상류 500')
        self.assertIn('colspan="7"', page)
