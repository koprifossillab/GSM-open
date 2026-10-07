"""받아 두는 데이터소스의 명세 — `DataSource` (jikhanjung P02 1 단계, P03 1 단계).

지키는 것 — 씨앗이 코드와 어긋나지 않는다(명령·구운 자료가 빠짐없이 어느 데이터소스에 든다), 씨앗은 사람이 고친 줄을 덮지
않는다, 틀린 줄은 건너뛰고 뷰어는 멈추지 않는다, 파일 시절의 명세·기록은 표가 비었을 때 한 번만 옮긴다, 고칠 때마다 이력이 남는다.
"""
import io
import json
import sqlite3
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import fetchlog, i18n, sources
from viewer.models import DataSource, DataSourceChange, FetchRun, FetchRunMark


def _row(**over):
    row = {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
           "runs_on": "container", "schedule": "manual", "license": "CC BY 4.0"}
    row.update(over)
    return row


class Seed(TestCase):
    """저장소의 씨앗 — 운영 명세의 처음 판이다."""

    def test_씨앗의_모든_줄이_검사를_지난다(self):
        spec = sources.load()
        self.assertEqual(spec.origin, "seed")              # 표가 비면 씨앗을 읽는다
        self.assertEqual(spec.problems, [])
        self.assertGreater(len(spec.rows), 40)

    def test_명령과_구운_자료가_빠짐없이_든다(self):
        """새 fetch_*·build_* 명령이나 datastatus 항목을 더하고 씨앗에 안 적으면 여기서 깨진다"""
        self.assertEqual(sources.coverage(sources.read_seed().rows), [])

    def test_영어_이름이_다_있다(self):
        raw = json.loads(Path(sources.seed_path()).read_text(encoding="utf-8"))
        for row in raw["sources"]:
            self.assertTrue(row["name"]["en"].strip(), row["id"])
            self.assertNotRegex(row["name"]["en"], r"[가-힣]", row["id"])

    def test_씨앗의_줄이_표를_오가도_같다(self):
        for row in sources.read_seed().rows:
            obj = DataSource(id=row["id"], **DataSource.fields_of(row))
            self.assertEqual(sources._normal(obj.as_row()), sources._normal(row), row["id"])


class Dir(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.live = self.dir / "sources.json"
        self.seedfile = self.dir / "seed.json"
        over = override_settings(SOURCES_PATH=str(self.live), SOURCES_SEED=self.seedfile,
                                 STORE_PATH=str(self.dir / "store.sqlite"))
        over.enable()
        self.addCleanup(over.disable)

    def write_seed(self, rows):
        self.seedfile.write_text(json.dumps({"sources": rows}, ensure_ascii=False), encoding="utf-8")

    def write_live(self, rows):
        self.live.write_text(json.dumps({"sources": rows}, ensure_ascii=False), encoding="utf-8")


class SeedInto(Dir):
    def test_비었으면_씨앗째_넣고_이력을_남긴다(self):
        self.write_seed([_row(id="a"), _row(id="b")])
        done = sources.seed()
        self.assertTrue(done["created"])
        spec = sources.load()
        self.assertEqual((spec.origin, [r["id"] for r in spec.rows]), ("db", ["a", "b"]))
        self.assertEqual(sorted(DataSourceChange.objects.values_list("source", "origin")), [("a", "seed"), ("b", "seed")])

    def test_차_있으면_씨앗에만_있는_id_만_덧붙이고_고친_줄은_덮지_않는다(self):
        self.write_seed([_row(id="a", license="CC BY 4.0"), _row(id="b")])
        sources._put([_row(id="a", license="사람이 고친 조건")], "import")
        done = sources.seed()
        self.assertEqual(done["added"], ["b"])
        self.assertEqual(done["differs"], ["a"])
        rows = sources.load().by_id()
        self.assertEqual(rows["a"]["license"], "사람이 고친 조건")
        self.assertEqual(list(rows), ["a", "b"])                     # 덧붙인 것은 끝에
        self.assertEqual(sources.seed_differs(list(rows.values())), {"a": ["license"]})

    def test_빠진_칸은_다르다고_치지_않는다(self):
        """씨앗은 빈 칸(flags·org…)을 적지 않고 표는 모든 칸을 갖는다 — 그것만으로 "씨앗과 다름" 이 뜨면 안 된다"""
        self.write_seed([_row(id="a")])
        sources.seed()
        self.assertEqual(sources.seed_differs(sources.load().rows), {})

    def test_명령이_돈다(self):
        self.write_seed([_row(id="a")])
        call_command("sources_seed", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertTrue(DataSource.objects.filter(pk="a").exists())


class ReadFile(Dir):
    """파일 시절의 운영 명세 — 옮겨 올 때만 읽는다."""

    def test_틀린_줄은_건너뛰고_까닭을_적는다(self):
        self.write_live([_row(id="good"), _row(id="Bad Id"), _row(id="nolicense", license=""),
                         _row(id="good"), _row(id="flag", flags=["secret"])])
        spec = sources.read_file()
        self.assertEqual([r["id"] for r in spec.rows], ["good"])
        self.assertEqual([w for w, _ in spec.problems], ["Bad Id", "nolicense", "good", "flag"])
        for _, found in spec.problems:            # 화면에 영어로도 뜬다
            for m in found:
                self.assertNotEqual(i18n.t(m, "en"), m.template, m.template)

    def test_파일째_깨지면_마지막으로_떠_둔_판을_쓴다(self):
        history = self.dir / "sources_history"
        history.mkdir()
        (history / "20261006-180628-aaaaaaaaaaaa.json").write_text(json.dumps({"sources": [_row(id="a")]}), encoding="utf-8")
        self.live.write_text("[ 깨짐", encoding="utf-8")
        spec = sources.read_file()
        self.assertEqual((spec.origin, [r["id"] for r in spec.rows]), ("history", ["a"]))
        self.assertTrue(spec.problems)

    def test_없으면_none(self):
        self.assertEqual(sources.read_file().origin, "none")


class Load(Dir):
    def test_표의_틀린_줄은_건너뛰고_뷰어는_돈다(self):
        """admin 은 저장 전에 검사하지만, 표를 손으로 고쳐 틀린 줄이 들어와도 화면은 선다"""
        self.write_seed([])
        sources._put([_row(id="a"), _row(id="b")], "import")
        DataSource.objects.filter(pk="b").update(schedule="가끔")
        spec = sources.load()
        self.assertEqual([r["id"] for r in spec.rows], ["a"])
        self.assertEqual([w for w, _ in spec.problems], ["b"])


class Import(Dir):
    def store(self, rows, offset=None):
        db = sqlite3.connect(self.dir / "store.sqlite")
        db.executescript("""CREATE TABLE fetch_log (id INTEGER PRIMARY KEY, source TEXT, command TEXT, started_at TEXT,
            seconds REAL, result TEXT, note TEXT DEFAULT '', upstream_version TEXT DEFAULT '', expected INTEGER, rows INTEGER,
            changed INTEGER, raw_path TEXT DEFAULT '', raw_sha256 TEXT DEFAULT '', built_at TEXT DEFAULT '', built_by TEXT DEFAULT '',
            estimated INTEGER DEFAULT 0, origin TEXT DEFAULT 'container');
            CREATE TABLE fetch_log_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);""")
        for r in rows:
            db.execute("INSERT INTO fetch_log (source, command, started_at, result, origin, estimated) VALUES (?,?,?,?,?,?)",
                       (r["source"], "", r["started_at"], r["result"], r.get("origin", "container"), r.get("estimated", 0)))
        if offset is not None:
            db.execute("INSERT INTO fetch_log_meta VALUES ('host_offset', ?)", (str(offset),))
        db.commit()
        db.close()

    def test_비었을_때만_명세를_옮긴다(self):
        self.write_live([_row(id="a", license="사람이 고친 조건"), _row(id="b"), _row(id="Bad")])
        done = sources.import_file()
        self.assertTrue(done["done"])
        self.assertEqual(done["added"], ["a", "b"])
        self.assertEqual(sources.load().by_id()["a"]["license"], "사람이 고친 조건")
        self.assertEqual(set(DataSourceChange.objects.values_list("origin", flat=True)), {"import"})
        self.assertIsNone(sources.last_change())                     # 옮겨 온 것은 "명세를 고친 때" 가 아니다
        self.write_live([_row(id="c")])
        self.assertFalse(sources.import_file()["done"])             # 두 번 옮겨 덮지 않는다
        self.assertEqual(sorted(DataSource.objects.values_list("id", flat=True)), ["a", "b"])

    def test_명령이_명세와_기록을_옮기고_씨앗보다_먼저다(self):
        self.write_seed([_row(id="a"), _row(id="s")])
        self.write_live([_row(id="a", license="사람이 고친 조건")])
        self.store([
            {"source": "a", "started_at": "2026-10-06T17:40:00+09:00", "result": "ok", "origin": "hourly"},
            {"source": "a", "started_at": "2026-10-06T08:40:00+00:00", "result": "ok", "origin": "hourly"},   # 같은 때 — 하나로
            {"source": "b", "started_at": "2026-10-05T04:44:00+09:00", "result": "ok", "origin": "backfill", "estimated": 1},
            {"source": "_spec", "started_at": "2026-10-06T18:06:28+09:00", "result": "ok", "origin": "spec"},
        ], offset=1234)
        out = io.StringIO()
        call_command("sources_import", "--dry-run", stdout=out)
        self.assertIn("명세 — 1 곳을 옮길 것", out.getvalue())
        self.assertIn("기록 — 3 줄을 옮길 것", out.getvalue())             # 명세가 바뀐 것을 적던 `_spec` 줄은 빼고
        self.assertEqual(DataSource.objects.count(), 0)                 # --dry-run 은 옮기지 않는다
        call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        call_command("sources_seed", stdout=io.StringIO(), stderr=io.StringIO())
        rows = sources.load().by_id()
        self.assertEqual(rows["a"]["license"], "사람이 고친 조건")          # 씨앗이 덮지 않았다
        self.assertIn("s", rows)                                       # 씨앗에만 있던 것은 덧붙었다
        runs = [fetchlog.as_dict(r) for r in FetchRun.objects.order_by("started_at")]
        self.assertEqual([(r["source"], r["started_at"]) for r in runs],
                         [("b", "2026-10-05T04:44:00+09:00"), ("a", "2026-10-06T17:40:00+09:00")])
        self.assertEqual(runs[0]["estimated"], 1)
        self.assertEqual(FetchRunMark.objects.get(key="host_offset").value, "1234")
        # 두 번째는 아무것도 하지 않는다
        call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(FetchRun.objects.count(), 2)

    def test_파일이_없으면_조용히(self):
        out = io.StringIO()
        call_command("sources_import", stdout=out, stderr=io.StringIO())
        self.assertIn("씨앗이 들어간다", out.getvalue())
        self.assertIn("store.sqlite 가 없다", out.getvalue())


class Admin(Dir):
    """admin 에서 고치면 앞뒤 줄이 이력에 남는다. 틀린 값은 저장되지 않는다."""

    def setUp(self):
        super().setUp()
        self.write_seed([])
        sources._put([_row(id="a")], "seed")
        self.user = User.objects.create_superuser("tester", "", "pw")
        self.client.force_login(self.user)

    def form(self, **over):
        row = _row(id="a", **over)
        data = {"id": "a", "order": 0, "name_ko": row["name"]["ko"], "name_en": row["name"]["en"], "org": "",
                "kind": row["kind"], "schedule": row["schedule"], "runs_on": row["runs_on"],
                "commands": json.dumps(row["commands"]), "license": row["license"], "flags": json.dumps(row.get("flags", [])),
                "outputs": "[]", "raw": "", "docs": "[]", "note": ""}
        return data

    def test_고치면_이력에_앞뒤가(self):
        r = self.client.post("/GSM/admin/viewer/datasource/a/change/", self.form(license="사람이 고친 조건"))
        self.assertEqual(r.status_code, 302)
        change = DataSourceChange.objects.filter(origin="admin").get()
        self.assertEqual((change.source, change.by, change.before["license"], change.after["license"]),
                         ("a", self.user, "CC BY 4.0", "사람이 고친 조건"))
        self.assertEqual(DataSource.objects.get(pk="a").updated_by, self.user)
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn("명세를 고친 때", page)

    def test_틀린_값은_저장되지_않는다(self):
        r = self.client.post("/GSM/admin/viewer/datasource/a/change/", self.form(schedule="가끔"))
        self.assertEqual(r.status_code, 200)                          # 폼이 다시 뜬다
        self.assertEqual(DataSource.objects.get(pk="a").schedule, "manual")
        self.assertFalse(DataSourceChange.objects.filter(origin="admin").exists())
        with self.assertRaises(ValidationError):
            DataSource(id="b", **DataSource.fields_of(_row(id="b", flags=["secret"]))).full_clean()

    def test_지우면_뒤가_빈_줄(self):
        self.client.post("/GSM/admin/viewer/datasource/a/delete/", {"post": "yes"})
        self.assertFalse(DataSource.objects.filter(pk="a").exists())
        change = DataSourceChange.objects.filter(origin="admin").get()
        self.assertIsNone(change.after)

    def test_기록은_읽기만(self):
        self.assertEqual(self.client.get("/GSM/admin/viewer/fetchrun/").status_code, 200)
        self.assertEqual(self.client.get("/GSM/admin/viewer/fetchrun/add/").status_code, 403)


class Coverage(SimpleTestCase):
    def test_빠진_명령과_없는_명령을_알린다(self):
        rows = [_row(id="a", commands=["fetch_없는것"], outputs=[])]
        lines = sources.coverage(rows)
        self.assertTrue(any("fetch_없는것" in x for x in lines))
        self.assertTrue(any("fetch_pbdb" in x for x in lines))


class Review381(Dir):
    """#381 검토 — 옮기기는 한 번 깨져도 다시, 지운 것은 되살리지 않는다, 밖에 연 판에는 admin 이 없다."""

    def test_씨앗이_먼저_들어갔어도_파일_쪽으로_덮는다(self):
        """옮기기가 깨진 사이 씨앗이 표를 채웠다 — 다음에 뜰 때 사람이 고친 파일의 줄이 이긴다. admin 에서 고친 줄은 둔다"""
        self.write_seed([_row(id="a"), _row(id="b"), _row(id="c")])
        self.write_live([_row(id="a", license="사람이 고친 조건"), _row(id="b", license="파일의 조건"), _row(id="f")])
        sources.seed()                                               # 옮기기보다 씨앗이 먼저 들어간 꼴
        user = User.objects.create_user("editor")
        obj = DataSource.objects.get(pk="b")
        before = obj.as_row()
        obj.license = "admin 에서 고친 조건"
        obj.save()
        sources.record_change("b", before, obj.as_row(), "admin", user)
        done = sources.import_file()
        self.assertEqual((done["added"], done["replaced"], done["kept"]), (["f"], ["a"], ["b"]))
        rows = sources.load().by_id()
        self.assertEqual((rows["a"]["license"], rows["b"]["license"]), ("사람이 고친 조건", "admin 에서 고친 조건"))
        change = DataSourceChange.objects.filter(source="a", origin="import").get()
        self.assertEqual((change.before["license"], change.after["license"]), ("CC BY 4.0", "사람이 고친 조건"))
        self.write_live([_row(id="a", license="또 고친 것")])
        self.assertFalse(sources.import_file()["done"])                # 표지가 있으면 두 번 옮기지 않는다

    def test_기록은_표에_줄이_있어도_옮긴다(self):
        Import.store(self, [{"source": "a", "started_at": "2026-10-06T17:40:00+09:00", "result": "ok"},
                            {"source": "a", "started_at": "2026-10-06T18:40:00+09:00", "result": "ok"}], offset=10)
        fetchlog.write({"source": "a", "started_at": "2026-10-07T10:00:00+09:00", "result": "ok"})   # 옮기기 전에 생긴 줄
        FetchRunMark.objects.create(key="host_offset", value="99")
        call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(FetchRun.objects.count(), 3)
        self.assertEqual(FetchRunMark.objects.get(key="host_offset").value, "99")   # 새 코드가 더 읽은 자리를 되돌리지 않는다

    def test_옮기다_깨져도_명령은_끝나고_다음에_다시(self):
        from unittest import mock
        self.write_live([_row(id="a")])
        from django.db import DatabaseError
        with mock.patch.object(sources, "_put", side_effect=DatabaseError("database is locked")):
            call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertFalse(FetchRunMark.objects.filter(key=sources.IMPORTED).exists())
        call_command("sources_import", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertTrue(DataSource.objects.filter(pk="a").exists())

    def test_지운_데이터소스는_씨앗이_되살리지_않는다(self):
        self.write_seed([_row(id="a"), _row(id="b")])
        sources.seed()
        user = User.objects.create_superuser("tester", "", "pw")
        self.client.force_login(user)
        self.client.post("/GSM/admin/viewer/datasource/b/delete/", {"post": "yes"})
        self.assertEqual(sources.seed()["added"], [])
        self.assertEqual(list(DataSource.objects.values_list("id", flat=True)), ["a"])
        self.assertEqual(DataSourceChange.objects.filter(source="b", after__isnull=True).get().by_name, "tester")

    def test_목록_칸을_비우면_빈_목록(self):
        obj = DataSource(id="a", **DataSource.fields_of(_row(id="a")))
        obj.flags, obj.outputs, obj.docs = None, "", None
        obj.full_clean()
        self.assertEqual((obj.flags, obj.outputs, obj.docs), ([], [], []))

    def test_밖에_연_판에는_admin_이_없다(self):
        import importlib

        from django.urls import clear_url_caches

        import gsmweb.urls
        self.write_seed([_row(id="a")])

        def reload():
            importlib.reload(gsmweb.urls)
            clear_url_caches()
        self.addCleanup(reload)
        with override_settings(PUBLIC=True):
            reload()
            self.assertEqual(self.client.get("/GSM/admin/").status_code, 404)
            page = self.client.get("/GSM/manage/").content.decode()
            self.assertNotIn("명세 고치기</a>", page)
        reload()
        self.assertEqual(self.client.get("/GSM/admin/").status_code, 302)       # 연구소 안에서는 로그인으로


class Followup383(Dir):
    def test_다_지워도_씨앗이_되살리지_않는다(self):
        self.write_seed([_row(id="a"), _row(id="b")])
        sources.seed()
        for pk in ("a", "b"):
            row = DataSource.objects.get(pk=pk).as_row()
            DataSource.objects.filter(pk=pk).delete()
            sources.record_change(pk, row, None, "admin")
        self.assertEqual(sources.seed()["added"], [])
        self.assertFalse(DataSource.objects.exists())
