"""받은 원본을 날짜 폴더에 — 바뀐 판만, 최근 몇 벌만 (jikhanjung P02 4 단계).

지키는 것 — 같은 판이면 새 폴더 없이 확인한 때만, 바뀌면 새 폴더와 바뀐 수, 기록 표에 원본의 자리·판·바뀐 수, 지우기는 사람이 부를 때만·
가장 새 것은 남기고·날짜 폴더가 아닌 것은 건드리지 않는다, 명세의 자리를 설정의 자리로 옮긴다, 화면에 상류 판·바뀐 수·씨앗과 다른 줄.
"""
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import fetchlog, pbdb, rawstore, sources


def _at(day, hour=9):
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00").replace(tzinfo=timezone.utc)


def _entries(**bodies):
    return {name: {"file": f"{name}.json.gz", "body": body.encode()} for name, body in bodies.items()}


class Base(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.raw = self.dir / "demo" / "raw"
        over = override_settings(STORE_PATH=str(self.dir / "store.sqlite"), FETCH_LOG=True)
        over.enable()
        self.addCleanup(over.disable)
        env = mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "container"})
        env.start()
        self.addCleanup(env.stop)
        # 기록 표는 (데이터소스·시작한 때·어디서)가 같으면 한 줄 — 같은 초에 두 번 돌리는 시험이라 때를 하나씩 다르게
        ticks = iter(f"2026-10-06T00:00:{i:02d}+09:00" for i in range(60))
        now = mock.patch.object(fetchlog, "_now", side_effect=lambda: next(ticks))
        now.start()
        self.addCleanup(now.stop)

    def logged(self):
        from viewer.models import FetchRun
        return [fetchlog.as_dict(r) for r in FetchRun.objects.order_by("id")]


class Save(Base):
    def test_같은_판이면_새_폴더_없이_확인한_때만(self):
        with fetchlog.record("demo", "fetch_demo"):
            folder, fresh = rawstore.save(self.raw, _entries(a="1", b="2"), {"source": "시험"}, _at("2026-10-01"), where="demo/raw")
        self.assertTrue(fresh)
        self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20261001"])
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"], "시험")
        self.assertEqual(manifest["files"]["a"]["sha256"], hashlib.sha256(b"1").hexdigest())
        with fetchlog.record("demo", "fetch_demo"):
            again, fresh = rawstore.save(self.raw, _entries(a="1", b="2"), {}, _at("2026-11-01"), where="demo/raw")
        self.assertFalse(fresh)
        self.assertEqual(again, folder)
        self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20261001"])
        self.assertEqual(len(json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["checked"]), 1)
        first, second = self.logged()
        self.assertEqual((first["raw_path"], first["changed"]), ("demo/raw/20261001", 2))      # 앞 판이 없으면 모두
        self.assertEqual((second["raw_path"], second["changed"]), ("demo/raw/20261001", 0))
        self.assertEqual(first["raw_sha256"], second["raw_sha256"])

    def test_바뀌면_새_폴더와_바뀐_수(self):
        with fetchlog.record("demo", "fetch_demo"):
            rawstore.save(self.raw, _entries(a="1", b="2"), {}, _at("2026-10-01"))
        with fetchlog.record("demo", "fetch_demo"):
            folder, fresh = rawstore.save(self.raw, _entries(a="1", b="3"), {}, _at("2026-11-01"))
        self.assertTrue(fresh)
        self.assertEqual(rawstore.latest(self.raw), folder)
        self.assertEqual(self.logged()[-1]["changed"], 1)
        self.assertFalse(any(p.name.endswith(".part") for p in self.raw.iterdir()))

    def test_같은_날_두_번째는_새것이_이긴다(self):
        rawstore.save(self.raw, _entries(a="1"), {}, _at("2026-10-01", 9))
        folder, _ = rawstore.save(self.raw, _entries(a="2"), {}, _at("2026-10-01", 15))
        self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20261001"])
        self.assertEqual(json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["files"]["a"]["sha256"],
                         hashlib.sha256(b"2").hexdigest())


class Prune(Base):
    def make(self, *days):
        for day in days:
            (self.raw / day).mkdir(parents=True)
            (self.raw / day / "manifest.json").write_text("{}", encoding="utf-8")
        (self.raw / "README").mkdir()                       # 날짜 폴더가 아닌 것
        (self.raw / ".20260101.part").mkdir()

    def test_최근_몇_벌만_남긴다(self):
        self.make("20260101", "20260201", "20260301", "20260401", "20260501")
        gone = rawstore.prune(self.raw, keep=3, dry_run=True)
        self.assertEqual([p.name for p in gone], ["20260101", "20260201"])
        self.assertEqual(len(rawstore.versions(self.raw)), 5)          # dry-run 은 지우지 않는다
        rawstore.prune(self.raw, keep=3)
        self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20260301", "20260401", "20260501"])
        self.assertTrue((self.raw / "README").is_dir())
        self.assertTrue((self.raw / ".20260101.part").is_dir())

    def test_가장_새_것은_언제나_남는다(self):
        self.make("20260101", "20260201")
        rawstore.prune(self.raw, keep=0)
        self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20260201"])

    def test_매니페스트가_없는_날짜_폴더는_세지도_지우지도_않는다(self):
        """#379 검토 — 구운 산출물도 날짜 폴더다(ERA5 의 wind/era5/20050601/). 명세의 raw 를 잘못 적어도 지우지 않는다"""
        for day in ("20050601", "20050602", "20050603", "20050604", "20050605"):
            (self.raw / day).mkdir(parents=True)
            (self.raw / day / "10m.png").write_bytes(b"x")
        self.assertEqual(rawstore.versions(self.raw), [])
        self.assertEqual(rawstore.prune(self.raw, keep=1), [])
        self.assertEqual(len([p for p in self.raw.iterdir() if p.is_dir()]), 5)

    def test_확인한_때는_최근_것만(self):
        """#379 검토 — 같은 판을 받을 때마다 checked 가 늘기만 했다"""
        with mock.patch.object(rawstore, "CHECKED_KEEP", 3):
            for i in range(1, 7):
                folder, _ = rawstore.save(self.raw, _entries(a="1"), {}, _at(f"2026-10-0{i}"))
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["checked"]), 3)
        self.assertEqual(manifest["checked_count"], 5)
        self.assertEqual(list(folder.glob("*.tmp")), [])            # 바꿔치기 — 임시 파일이 남지 않는다

    def test_명령은_명세의_날짜_폴더만_본다(self):
        self.make("20260101", "20260201", "20260301", "20260401")
        (self.dir / "earth").mkdir()
        (self.dir / "earth" / "pbdb.csv").write_text("x")
        sources._put([
            {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
             "runs_on": "container", "schedule": "manual", "license": "x", "raw": "demo/raw"},
            {"id": "flat", "name": {"ko": "평", "en": "Flat"}, "kind": "fetch", "commands": ["fetch_flat"],
             "runs_on": "container", "schedule": "manual", "license": "x", "raw": "earth/pbdb.csv"},
        ], "seed")
        with override_settings(DEMO_DIR=str(self.dir / "demo"), EARTH_DIR=str(self.dir / "earth")):
            out = io.StringIO()
            call_command("prune_raw", "--dry-run", stdout=out)
            self.assertIn("demo: 4 벌", out.getvalue())
            self.assertIn("지울 것 20260101", out.getvalue())
            self.assertNotIn("flat", out.getvalue())
            self.assertEqual(len(rawstore.versions(self.raw)), 4)
            call_command("prune_raw", stdout=io.StringIO())
            self.assertEqual([p.name for p in rawstore.versions(self.raw)], ["20260201", "20260301", "20260401"])
        self.assertTrue((self.dir / "earth" / "pbdb.csv").exists())


class Resolve(SimpleTestCase):
    def test_첫_마디가_설정의_자리면_그것을(self):
        with override_settings(KIGAM50K_DIR="/srv/a/kigam50k", EARTH_DIR="/srv/b/earth"):
            self.assertEqual(rawstore.resolve("kigam50k/raw"), Path("/srv/a/kigam50k/raw"))
            self.assertEqual(rawstore.resolve("earth/quakes.csv"), Path("/srv/b/earth/quakes.csv"))

    def test_그_밖은_DB_옆(self):
        with override_settings(DATABASES={"default": {"NAME": "/srv/c/GSM.db"}}):
            self.assertEqual(rawstore.resolve("없는자리/x"), Path("/srv/c/없는자리/x"))
            self.assertEqual(rawstore.label("/srv/c/earth/q.csv"), "earth/q.csv")
            self.assertEqual(rawstore.label("/home/someone/q.csv"), "q.csv")


class PbdbDigest(SimpleTestCase):
    def test_받는_대로_셈한다(self):
        dest = Path(tempfile.mkdtemp()) / "c.csv"
        answer = mock.MagicMock(status_code=200, url="https://paleobiodb.org/…")
        answer.__enter__.return_value = answer
        answer.iter_content.return_value = [b"collection_no\n", b"1\n"]
        digest = hashlib.sha256()
        with mock.patch.object(pbdb.requests, "get", return_value=answer), mock.patch.object(pbdb.usage, "record"):
            pbdb.download(dest, digest=digest)
        self.assertEqual(digest.hexdigest(), hashlib.sha256(b"collection_no\n1\n").hexdigest())


class Screen(Base):
    """관리 화면 — 상류 판·바뀐 수, 씨앗과 다른 줄 (P02 §6·§9)."""

    def setUp(self):
        super().setUp()
        row = {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
               "runs_on": "container", "schedule": "manual", "license": "x"}
        seed = self.dir / "seed.json"
        seed.write_text(json.dumps({"sources": [row]}), encoding="utf-8")
        over = override_settings(SOURCES_SEED=seed)
        over.enable()
        self.addCleanup(over.disable)
        sources._put([{**row, "license": "사람이 고친 조건"}], "import")
        fetchlog.write({"source": "demo", "started_at": "2026-10-06T00:00:00+09:00", "result": "ok",
                        "upstream_version": "v2026.09", "changed": 0})

    def test_상류_판과_바뀐_수_씨앗과_다른_줄(self):
        self.assertEqual(sources.seed_differs(sources.load().rows), {"demo": ["license"]})
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("상류 판 <span class=\"mono\">v2026.09</span>", page)
        self.assertIn("앞 판과 같다", page)
        self.assertIn("씨앗과 다른 줄 1", page)
        self.assertIn("씨앗과 다름 · <span class=\"mono\">license</span>", page)
        en = self.client.get("/GSM/manage/", HTTP_COOKIE="gsm_lang=en").content.decode()
        self.assertIn("same as the previous copy", en)
        self.assertIn("upstream version", en)
