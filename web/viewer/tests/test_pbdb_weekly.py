"""PBDB 를 매주 바뀐 것만 받아 덮는다 (jikhanjung 026).

지키는 것 — 바뀐 산지를 `collection_no` 로 덮고·더하고·지운 표시는 빼고, 열이 다르면 덮지 않는다, 바뀐 것의 시작 날은 마지막으로 된 차례의
하루 앞, `--changed` 는 덮고 다시 굽고 날짜 폴더에 남긴다, 받아 둔 CSV 가 없거나 열이 다르면 통째로, 문은 `all_records` 대신 날짜를.
"""
import csv
import io
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import fetchlog, fossils, pbdb

HEAD = ["collection_no", "lng", "lat", "collection_name", "max_ma", "min_ma"]


def _csv(path, rows, head=HEAD):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return [(r["collection_no"], r["collection_name"]) for r in csv.DictReader(fh)]


class Merge(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.src, self.changes = self.dir / "all.csv", self.dir / "changes.csv"
        _csv(self.src, [[1, 0, 0, "하나", 10, 5], [2, 0, 0, "둘", 10, 5], [3, 0, 0, "셋", 10, 5]])

    def test_덮고_더하고_차례는_지킨다(self):
        _csv(self.changes, [[2, 0, 0, "둘 고침", 10, 5], [9, 0, 0, "아홉", 10, 5]])
        got = fossils.merge_changes(self.src, self.changes)
        self.assertEqual((got["replaced"], got["added"], got["deleted"], got["rows"]), (1, 1, 0, 4))
        self.assertEqual(_read(self.src), [("1", "하나"), ("2", "둘 고침"), ("3", "셋"), ("9", "아홉")])

    def test_지운_표시면_뺀다(self):
        _csv(self.changes, [[3, 0, 0, "셋", 10, 5, "deleted"]], head=HEAD + ["_status"])
        got = fossils.merge_changes(self.src, self.changes)
        self.assertEqual((got["deleted"], got["rows"]), (1, 2))
        self.assertEqual([no for no, _ in _read(self.src)], ["1", "2"])

    def test_열이_다르면_덮지_않는다(self):
        _csv(self.changes, [[2, 0, 0, "둘", 10, 5, "x"]], head=HEAD + ["새 열"])
        before = self.src.read_bytes()
        with self.assertRaises(fossils.MergeError):
            fossils.merge_changes(self.src, self.changes)
        self.assertEqual(self.src.read_bytes(), before)
        self.assertFalse(list(self.dir.glob("*.merging")))

    def test_바뀐_것이_없으면_그대로(self):
        _csv(self.changes, [])
        got = fossils.merge_changes(self.src, self.changes)
        self.assertEqual((got["replaced"], got["added"], got["rows"]), (0, 0, 3))


class Door(SimpleTestCase):
    def test_바뀐_것만은_all_records_대신_날짜(self):
        answer = mock.MagicMock(status_code=200, url="https://paleobiodb.org/…")
        answer.__enter__.return_value = answer
        answer.iter_content.return_value = [b"collection_no\n"]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pbdb.requests, "get", return_value=answer) as get, \
                mock.patch.object(pbdb.usage, "record"):
            pbdb.download(Path(d) / "c.csv", since=date(2026, 10, 1))
        params = get.call_args.kwargs["params"]
        self.assertNotIn("all_records", params)
        self.assertEqual(params["colls_modified_after"], "2026-10-01")
        self.assertEqual(params["show"], pbdb.QUERY["show"])                   # 열은 통째 받기와 같다


@override_settings(FETCH_LOG=True)
class Command(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        over = override_settings(EARTH_DIR=str(self.dir / "earth"), STORE_PATH=str(self.dir / "store.sqlite"))
        over.enable()
        self.addCleanup(over.disable)
        env = mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "container"})
        env.start()
        self.addCleanup(env.stop)
        (self.dir / "earth").mkdir()
        self.src = self.dir / "earth" / "pbdb_collections.csv"
        build = mock.patch.object(fossils, "build", return_value={"rows": 9, "plated": 9, "skipped": 0, "seconds": 0.1})
        self.build = build.start()
        self.addCleanup(build.stop)

    def fake_download(self, rows, head=HEAD):
        calls = []

        def download(dest, timeout=900, digest=None, since=None):
            calls.append(since)
            _csv(dest, rows, head)
            return 100
        return download, calls

    def test_바뀐_것만_받아_덮고_다시_굽고_날짜_폴더에(self):
        _csv(self.src, [[1, 0, 0, "하나", 10, 5]])
        fetchlog.write({"source": "pbdb", "command": "fetch_pbdb", "started_at": "2026-10-05T03:10:00+09:00", "result": "ok"})
        download, calls = self.fake_download([[1, 0, 0, "하나 고침", 10, 5], [2, 0, 0, "둘", 10, 5]])
        with mock.patch.object(pbdb, "download", side_effect=download):
            out = io.StringIO()
            call_command("fetch_pbdb", "--changed", stdout=out)
        self.assertEqual(calls, [date(2026, 10, 4)])                           # 마지막으로 된 차례의 하루 앞
        self.assertEqual(_read(self.src), [("1", "하나 고침"), ("2", "둘")])
        self.build.assert_called_once()
        self.assertTrue(list((self.dir / "earth" / "pbdb_changes").glob("*/manifest.json")))
        self.assertIn("바꾼 1 · 새로 1 · 뺀 0", out.getvalue())
        run = fetchlog.latest()["pbdb"]["last"]
        self.assertEqual((run["result"], run["changed"], run["rows"]), ("ok", 2, 9))
        self.assertTrue(run["raw_path"].startswith("earth/pbdb_changes/"))

    def test_받아_둔_CSV_가_없으면_통째로(self):
        download, calls = self.fake_download([[1, 0, 0, "하나", 10, 5]])
        with mock.patch.object(pbdb, "download", side_effect=download):
            call_command("fetch_pbdb", "--changed", stdout=io.StringIO())
        self.assertEqual(calls, [None])

    def test_열이_다르면_통째로(self):
        _csv(self.src, [[1, 0, 0, "하나", 10, 5]])
        sinces = []

        def download(dest, timeout=900, digest=None, since=None):
            sinces.append(since)
            if since is not None:
                _csv(dest, [[1, 0, 0, "하나", 10, 5, "x"]], HEAD + ["새 열"])
            else:
                _csv(dest, [[1, 0, 0, "통째", 10, 5]])
            return 100
        with mock.patch.object(pbdb, "download", side_effect=download):
            call_command("fetch_pbdb", "--changed", "--since", "2026-10-01", stdout=io.StringIO())
        self.assertEqual(sinces, [date(2026, 10, 1), None])
        self.assertEqual(_read(self.src), [("1", "통째")])

    def test_주간_백업은_매주_부른다(self):
        script = (Path(__file__).resolve().parents[3] / "deploy/scripts/weekly_backup.sh").read_text(encoding="utf-8")
        self.assertIn("run fetch_pbdb 1800 --changed", script)
        self.assertIn("run fetch_pbdb 3600 ", script)
