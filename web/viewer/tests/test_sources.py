"""받아 두는 데이터소스의 명세 (jikhanjung P02 1 단계).

지키는 것 — 씨앗이 코드와 어긋나지 않는다(명령·구운 자료가 빠짐없이 어느 데이터소스에 든다), 씨앗은 사람이 고친 줄을 덮지
않는다, 틀린 줄은 건너뛰고 뷰어는 멈추지 않는다, 명세가 바뀌면 그 판을 떠 둔다.
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from viewer import i18n, sources


def _row(**over):
    row = {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
           "runs_on": "container", "schedule": "manual", "license": "CC BY 4.0"}
    row.update(over)
    return row


class Seed(SimpleTestCase):
    """저장소의 씨앗 — 운영 명세의 처음 판이다."""

    def setUp(self):
        sources._cache.update(key=None, spec=None)

    def test_씨앗의_모든_줄이_검사를_지난다(self):
        with override_settings(SOURCES_PATH="/nonexistent/sources.json"):
            spec = sources.load(keep_history=False)
        self.assertEqual(spec.origin, "seed")
        self.assertEqual(spec.problems, [])
        self.assertGreater(len(spec.rows), 40)

    def test_명령과_구운_자료가_빠짐없이_든다(self):
        """새 fetch_*·build_* 명령이나 datastatus 항목을 더하고 씨앗에 안 적으면 여기서 깨진다"""
        with override_settings(SOURCES_PATH="/nonexistent/sources.json"):
            spec = sources.load(keep_history=False)
        self.assertEqual(sources.coverage(spec.rows), [])

    def test_영어_이름이_다_있다(self):
        raw = json.loads(Path(sources.seed_path()).read_text(encoding="utf-8"))
        for row in raw["sources"]:
            self.assertTrue(row["name"]["en"].strip(), row["id"])
            self.assertNotRegex(row["name"]["en"], r"[가-힣]", row["id"])


class FileDir(SimpleTestCase):
    def setUp(self):
        sources._cache.update(key=None, spec=None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.live = self.dir / "sources.json"
        self.seedfile = self.dir / "seed.json"
        self.override = override_settings(SOURCES_PATH=str(self.live), SOURCES_SEED=self.seedfile)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: sources._cache.update(key=None, spec=None))

    def write_seed(self, rows):
        self.seedfile.write_text(json.dumps({"sources": rows}, ensure_ascii=False), encoding="utf-8")

    def write_live(self, rows):
        self.live.write_text(json.dumps({"sources": rows}, ensure_ascii=False), encoding="utf-8")
        sources._cache.update(key=None, spec=None)


class SeedInto(FileDir):
    def test_없으면_씨앗째_놓는다(self):
        self.write_seed([_row(id="a"), _row(id="b")])
        done = sources.seed()
        self.assertTrue(done["created"])
        self.assertEqual([r["id"] for r in sources.load().rows], ["a", "b"])

    def test_있으면_씨앗에만_있는_id_만_덧붙이고_고친_줄은_덮지_않는다(self):
        self.write_seed([_row(id="a", license="CC BY 4.0"), _row(id="b")])
        self.write_live([_row(id="a", license="사람이 고친 조건")])
        done = sources.seed()
        self.assertEqual(done["added"], ["b"])
        self.assertEqual(done["differs"], ["a"])
        rows = sources.load().by_id()
        self.assertEqual(rows["a"]["license"], "사람이 고친 조건")
        self.assertIn("b", rows)

    def test_깨진_운영_명세는_씨앗으로_덮지_않는다(self):
        self.write_seed([_row(id="a")])
        self.live.write_text("{ 고치다 만 것", encoding="utf-8")
        done = sources.seed()
        self.assertTrue(done.get("broken"))
        self.assertEqual(self.live.read_text(encoding="utf-8"), "{ 고치다 만 것")

    def test_명령이_돈다(self):
        self.write_seed([_row(id="a")])
        call_command("sources_seed", stdout=_Sink(), stderr=_Sink())
        self.assertTrue(self.live.exists())


class Load(FileDir):
    def test_틀린_줄은_건너뛰고_까닭을_적는다(self):
        self.write_live([_row(id="good"), _row(id="Bad Id"), _row(id="nolicense", license=""),
                         _row(id="good"), _row(id="flag", flags=["secret"])])
        spec = sources.load()
        self.assertEqual([r["id"] for r in spec.rows], ["good"])
        where = [w for w, _ in spec.problems]
        self.assertEqual(where, ["Bad Id", "nolicense", "good", "flag"])
        for _, found in spec.problems:            # 화면에 영어로도 뜬다
            for m in found:
                self.assertNotEqual(i18n.t(m, "en"), m.template, m.template)

    def test_파일째_깨지면_마지막으로_떠_둔_판을_쓴다(self):
        self.write_live([_row(id="a")])
        sources.load()                                    # 이 판을 떠 둔다
        self.live.write_text("[ 깨짐", encoding="utf-8")
        sources._cache.update(key=None, spec=None)
        spec = sources.load()
        self.assertEqual(spec.origin, "history")
        self.assertEqual([r["id"] for r in spec.rows], ["a"])
        self.assertTrue(spec.problems)

    def test_바뀐_판만_떠_둔다(self):
        self.write_live([_row(id="a")])
        sources.load()
        sources._cache.update(key=None, spec=None)
        sources.load()                                    # 같은 판 — 또 뜨지 않는다
        self.assertEqual(len(list(sources.history_dir().glob("*.json"))), 1)
        self.write_live([_row(id="a"), _row(id="b")])
        sources.load()
        self.assertEqual(len(list(sources.history_dir().glob("*.json"))), 2)

    def test_빈_목록과_맨_위_꼴(self):
        self.live.write_text(json.dumps({"자료원": []}), encoding="utf-8")
        spec = sources.load()
        self.assertEqual(spec.rows, [])
        self.assertTrue(spec.problems)


class Coverage(SimpleTestCase):
    def test_빠진_명령과_없는_명령을_알린다(self):
        rows = [_row(id="a", commands=["fetch_없는것"], outputs=[])]
        lines = sources.coverage(rows)
        self.assertTrue(any("fetch_없는것" in x for x in lines))
        self.assertTrue(any("fetch_pbdb" in x for x in lines))


class _Sink:
    def write(self, *_):
        pass

    def flush(self):
        pass
