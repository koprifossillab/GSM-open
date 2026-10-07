"""받아 두는 데이터소스의 명세 — `GSM.db` 의 `DataSource` (jikhanjung P02, P03 에서 `<DB 옆>/sources.json` 을 옮겼다).

**문이 아니다.** 상류를 부르지 않고, 사람이 정하는 것(조건·주기·돌리는 곳·명령·산출물·원본 자리)을 읽고 검사한다.
받은 차례마다의 기록(받은 때·결과·행 수)은 여기 두지 않는다 — `fetchlog.py`(`FetchRun`)의 몫이다.

- **고치기** — 사람이 Django admin(`/GSM/admin/`, staff 계정)에서 고친다. 고칠 때마다 `DataSourceChange` 에 앞뒤 줄이 남는다
  (누가·언제). 관리 화면 탭에서 고치는 것은 P03 2 단계
- **씨앗** `data/sources.seed.json` — 컨테이너가 뜰 때(`manage.py sources_seed`) 표가 비었으면 씨앗째 넣고, 차 있으면 씨앗에만 있는
  `id` 를 덧붙이기만 한다. 사람이 고친 줄은 덮지 않는다(`seed_catalog` 가 손질한 제목을 지키는 것과 같다)
- **옮겨 오기** — 파일 시절의 운영 명세(`sources.json`)는 `manage.py sources_import` 가 표가 비었을 때 한 번 옮긴다(`import_file`)
- **틀린 줄은 건너뛴다** — admin 이 저장 전에 같은 검사(`problems_of`)를 하지만, 표를 손으로 고쳐 틀린 줄이 들어와도 빼고 `problems` 에
  적는다. 표가 비었거나 아직 없으면 씨앗을 읽는다. 뷰어는 멈추지 않는다

지금 있는 파이썬 표(`datastatus.ITEMS`·`static_site.UPSTREAMS`·`views.LAB_ONLY`·`views.NO_STORE`)는 그대로 둔다 —
손댈 일이 생길 때 하나씩 옮긴다(docs/자료_적재_구조.md). 어긋나면 `coverage()` 가 알린다.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .i18n import msg

KINDS = ("fetch", "build", "file", "once")
RUNS_ON = ("container", "host", "person")
SCHEDULES = ("hourly", "weekly", "monthly-first-monday", "manual", "once")
FLAGS = ("nc", "sold", "lab_only", "no_store")

#: 이만큼 넘게 된 적이 없으면 늦었다 (시간). manual·once 는 늦지 않는다 — 화면(P02 3 단계)이 쓴다
LATE_HOURS = {"hourly": 3, "weekly": 9 * 24, "monthly-first-monday": 40 * 24}

_ID = re.compile(r"^[a-z0-9_]+$")


def path() -> Path:
    """파일 시절의 운영 명세 — `sources_import` 가 한 번 옮긴다"""
    return Path(settings.SOURCES_PATH)


def seed_path() -> Path:
    return Path(settings.SOURCES_SEED)


# ── 검사 ────────────────────────────────────────────────────────────

def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def problems_of(row) -> list:
    """한 줄의 잘못. 비면 쓸 수 있다."""
    if not isinstance(row, dict):
        return [msg("줄이 객체가 아니다")]
    out = []
    rid = row.get("id")
    if not isinstance(rid, str) or not _ID.match(rid):
        out.append(msg("id 가 없거나 꼴이 틀렸다 (영어 소문자·숫자·밑줄)"))
    name = row.get("name")
    if not (isinstance(name, dict) and isinstance(name.get("ko"), str) and name.get("ko")
            and isinstance(name.get("en"), str) and name.get("en")):
        out.append(msg("name 에 ko·en 이 다 있어야 한다"))
    for key, allowed in (("kind", KINDS), ("runs_on", RUNS_ON), ("schedule", SCHEDULES)):
        if row.get(key) not in allowed:
            out.append(msg("{key} 는 {allowed} 가운데 하나다", key=key, allowed=" · ".join(allowed)))
    if not _strings(row.get("commands", [])) or not isinstance(row.get("commands"), list):
        out.append(msg("commands 는 명령 이름의 목록이다"))
    elif row.get("kind") in ("fetch", "build", "once") and not row["commands"]:
        out.append(msg("받거나 굽는 데이터소스인데 commands 가 비었다"))
    if not isinstance(row.get("license"), str) or not row.get("license"):
        out.append(msg("license 가 없다"))
    flags = row.get("flags", [])
    if not isinstance(flags, list) or any(f not in FLAGS for f in flags):
        out.append(msg("flags 는 {allowed} 가운데서 고른다", allowed=" · ".join(FLAGS)))
    for key in ("outputs", "docs"):
        if key in row and row[key] != [] and not _strings(row[key]):
            out.append(msg("{key} 는 글의 목록이다", key=key))
    for key in ("org", "raw", "note"):
        if key in row and not isinstance(row[key], str):
            out.append(msg("{key} 는 글이다", key=key))
    return out


class Spec:
    """읽은 명세 — 쓸 수 있는 줄, 건너뛴 줄의 까닭, 어디서 읽었나."""

    def __init__(self, rows, problems, origin, sha="", read_at=None):
        self.rows = rows                  # 쓸 수 있는 줄만, 파일의 차례대로
        self.problems = problems          # [(id 또는 "#번째", [msg…])]
        self.origin = origin              # db · seed · none (옮겨 올 때는 file · history)
        self.sha = sha
        self.read_at = read_at

    def by_id(self) -> dict:
        return {r["id"]: r for r in self.rows}


def _check(raw) -> tuple:
    rows, problems, seen = [], [], set()
    items = raw.get("sources") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return [], [("", [msg("맨 위에 sources 목록이 있어야 한다")])]
    for i, row in enumerate(items, start=1):
        where = row.get("id") if isinstance(row, dict) and isinstance(row.get("id"), str) else f"#{i}"
        found = problems_of(row)
        if not found and row["id"] in seen:
            found = [msg("id 가 겹친다")]
        if found:
            problems.append((where, found))
            continue
        seen.add(row["id"])
        rows.append(row)
    return rows, problems


# ── 파일 시절의 명세 (옮겨 올 때만) ───────────────────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def history_dir() -> Path:
    return path().parent / "sources_history"


def _latest_history():
    folder = history_dir()
    try:
        found = sorted(p for p in folder.glob("*.json") if p.is_file())
    except OSError:
        return None
    return found[-1] if found else None


def _parse(data: bytes):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def read_file(p: Path = None) -> Spec:
    """파일 시절의 운영 명세를 읽는다. 깨졌으면 마지막으로 떠 둔 판(`sources_history/`)을. 없으면 origin `none`."""
    p = p or path()
    now = datetime.now()
    try:
        data = p.read_bytes()
    except OSError:
        return Spec([], [], "none", "", now)
    raw = _parse(data)
    if raw is not None:
        rows, problems = _check(raw)
        return Spec(rows, problems, "file", _sha(data), now)
    broken = [("", [msg("명세 파일을 JSON 으로 읽지 못했다 — 마지막으로 떠 둔 판을 쓴다")])]
    last = _latest_history()
    if last is not None:
        older = last.read_bytes()
        rows, problems = _check(_parse(older) or {})
        return Spec(rows, broken + problems, "history", _sha(older), now)
    return Spec([], broken, "none", "", now)


def read_seed() -> Spec:
    now = datetime.now()
    try:
        data = seed_path().read_bytes()
    except OSError:
        return Spec([], [("", [msg("명세도 씨앗도 없다")])], "none", "", now)
    rows, problems = _check(_parse(data) or {})
    return Spec(rows, problems, "seed", _sha(data), now)


# ── 읽기 ────────────────────────────────────────────────────────────

def load(keep_history: bool = True) -> Spec:
    """명세를 읽는다 — `DataSource` 의 줄들. 표가 비었거나 아직 없으면(새 설치·마이그레이션 전·시험) 씨앗을.

    `keep_history` 는 파일 시절의 것이다(이력은 이제 `DataSourceChange` 가 고칠 때 남긴다) — 부르는 자리를 고치지 않으려고 받기만 한다.
    """
    from .models import DataSource
    try:
        objs = list(DataSource.objects.all())
    except DatabaseError:
        objs = []
    if not objs:
        return read_seed()
    rows, problems = [], []
    for obj in objs:
        row = obj.as_row()
        found = problems_of(row)
        if found:
            problems.append((obj.pk, found))
        else:
            rows.append(row)
    return Spec(rows, problems, "db", "", datetime.now())


def last_change():
    """명세를 마지막으로 고친 것 — `DataSourceChange` 한 줄, 없으면 None. 파일에서 옮겨 온 것(`import`)은 고친 것이 아니라 뺀다"""
    from .models import DataSourceChange
    try:
        return DataSourceChange.objects.exclude(origin="import").order_by("-at", "-id").first()
    except DatabaseError:
        return None


# ── 쓰기 — 씨앗·옮겨 오기·이력 ─────────────────────────────────────────

def record_change(source_id: str, before, after, origin: str, by=None):
    """명세의 이력 한 줄. `before`·`after` 는 줄(dict) 또는 None(새로 넣음·지움)"""
    from .models import DataSourceChange
    DataSourceChange.objects.create(source=source_id, before=before, after=after, origin=origin, by=by,
                                    by_name=by.get_username() if by is not None else "")


def _put(rows, origin: str, start: int = 0) -> list:
    """줄들을 표 끝에 넣고 이력을 남긴다. 검사를 지난 줄만. 넣은 id"""
    from .models import DataSource
    added = []
    for i, row in enumerate(rows):
        if problems_of(row):
            continue
        obj = DataSource(id=row["id"], order=start + i, **DataSource.fields_of(row))
        obj.save()
        record_change(obj.pk, None, obj.as_row(), origin)
        added.append(obj.pk)
    return added


def deleted_ids() -> set:
    """사람이 지운 데이터소스 — 이력의 마지막 줄이 지움(`after` 가 빈 것)인 id. 씨앗이 되살리지 않는다(#381 검토 2)"""
    from .models import DataSourceChange
    last = {}
    for source, after, at, pk in DataSourceChange.objects.values_list("source", "after", "at", "id").order_by("at", "id"):
        last[source] = after
    return {s for s, after in last.items() if after is None}


def seed() -> dict:
    """씨앗을 표에 넣는다. 비었으면 통째로, 차 있으면 씨앗에만 있는 id 를 끝에 덧붙인다.

    돌려주는 것 — {"created": bool, "added": [id…], "differs": [id…]}. `differs` 는 씨앗과 표의 같은 id 가 다른 줄이다
    (덮지 않았다 — 옮길지는 사람이 정한다). 사람이 지운 id 는 덧붙이지 않는다(`deleted_ids`).
    """
    from .models import DataSource
    seed_rows = read_seed().rows
    with transaction.atomic():
        have = {o.pk: o for o in DataSource.objects.all()}
        # 사람이 지운 id — 표가 다 비었어도(다 지웠어도) 되살리지 않는다. 새로 놓은 자리면 이력이 없어 비었다 (jikhanjung 018)
        gone = deleted_ids()
        if not have:
            return {"created": True, "added": _put([r for r in seed_rows if r["id"] not in gone], "seed"), "differs": []}
        start = max(o.order for o in have.values()) + 1
        added = _put([r for r in seed_rows if r["id"] not in have and r["id"] not in gone], "seed", start)
    differs = sorted(seed_differs([o.as_row() for o in have.values()]))
    return {"created": False, "added": added, "differs": differs}


IMPORTED = "sources_imported"


def import_file(p: Path = None) -> dict:
    """파일 시절의 운영 명세(`sources.json`)를 표로 — **한 번**. 끝나면 표지(`FetchRunMark` 의 `IMPORTED`)를 남긴다.

    "표가 비었나" 로 정하지 않는다 — 옮기다 실패하고 그 사이 씨앗이 들어가면 다시 기회가 없었다(#381 검토 1). 표지가 없으면:
    파일에만 있는 id 는 덧붙이고, 씨앗으로 들어간 줄이 파일과 다르면 **파일 쪽으로 덮는다**(파일이 사람이 고친 것이다) — 이력에 앞뒤를.
    admin 에서 고친 줄은 덮지 않고 알린다. 파일이 깨졌으면 마지막으로 떠 둔 판을, 파일이 없으면(새 설치) 표지만 남긴다.
    돌려주는 것 — {"done", "added", "replaced", "kept", "origin", "problems"}
    """
    from .models import DataSource, DataSourceChange, FetchRunMark
    out = {"done": False, "added": [], "replaced": [], "kept": [], "origin": "", "problems": []}
    if FetchRunMark.objects.filter(key=IMPORTED).exists():
        out["origin"] = "done"
        return out
    spec = read_file(p)
    out.update(origin=spec.origin, problems=spec.problems)
    with transaction.atomic():
        if spec.origin != "none" and spec.rows:
            have = {o.pk: o for o in DataSource.objects.all()}
            edited = set(DataSourceChange.objects.filter(origin__in=("admin", "tab")).values_list("source", flat=True))
            start = max((o.order for o in have.values()), default=-1) + 1
            new = [r for r in spec.rows if r["id"] not in have]
            out["added"] = _put(new, "import", start)
            for i, row in enumerate(spec.rows):
                obj = have.get(row["id"])
                if obj is None or _normal(obj.as_row()) == _normal(row):
                    continue
                if obj.pk in edited:
                    out["kept"].append(obj.pk)
                    continue
                before = obj.as_row()
                for k, v in DataSource.fields_of(row).items():
                    setattr(obj, k, v)
                obj.save()
                record_change(obj.pk, before, obj.as_row(), "import")
                out["replaced"].append(obj.pk)
        FetchRunMark.objects.update_or_create(key=IMPORTED, defaults={"value": spec.origin or "none"})
    out["done"] = True
    return out


def _normal(row: dict) -> dict:
    """견주기 위해 빠진 칸을 채운다 — 씨앗은 빈 칸을 적지 않고, 표는 모든 칸을 갖는다"""
    from .models import DataSource
    return {"id": row.get("id"), "name": row.get("name"), **{k: v for k, v in DataSource.fields_of(row).items()
                                                            if k not in ("name_ko", "name_en")}}


def seed_differs(rows) -> dict:
    """표의 줄 가운데 씨앗의 같은 id 와 다른 것 — {id: [다른 칸…]}. 씨앗을 고쳐도 있는 id 는 덮지 않으므로(사람이 고친 것을
    지키려고) 씨앗의 고침이 운영에 안 닿는다. 화면이 이것을 띄워 옮길지 사람이 정하게 한다 (P02 §9)"""
    by_id = {r["id"]: _normal(r) for r in read_seed().rows}
    out = {}
    for row in rows:
        other = by_id.get(row.get("id"))
        if other is None:
            continue
        mine = _normal(row)
        keys = sorted(k for k in set(mine) | set(other) if mine.get(k) != other.get(k))
        if keys:
            out[row["id"]] = keys
    return out


# ── 파이썬 표와 견주기 ─────────────────────────────────────────────

def commands_on_disk() -> set:
    folder = Path(__file__).resolve().parent / "management" / "commands"
    return {p.stem for p in folder.glob("*.py") if p.stem.startswith(("fetch_", "build_"))}


def coverage(rows) -> list:
    """명세와 코드가 어긋난 곳 — 시험과 `sources_seed` 가 알린다. 글의 목록."""
    from . import datastatus

    out = []
    on_disk = commands_on_disk()
    named = {c for r in rows for c in r.get("commands", [])}
    for c in sorted(on_disk - named):
        out.append(f"명령 {c} 가 어느 데이터소스에도 없다")
    for c in sorted(named - on_disk):
        out.append(f"데이터소스가 적은 명령 {c} 가 없다")
    outputs = {o for r in rows for o in r.get("outputs", [])}
    for item in datastatus.ITEMS:
        if item.key not in outputs:
            out.append(f"구운 자료 {item.key} 가 어느 데이터소스의 outputs 에도 없다")
    lab = {i.key for i in datastatus.ITEMS if i.lab}
    for r in rows:
        flagged = "lab_only" in r.get("flags", [])
        mine = set(r.get("outputs", [])) & {i.key for i in datastatus.ITEMS}
        if mine and flagged != bool(mine & lab):
            out.append(f"{r['id']} 의 lab_only 가 datastatus 의 연구실 내부용 표시와 다르다")
    return out


# ── 관리 화면 "데이터소스" 탭 (P02 3 단계) ──────────────────────────────

SCHEDULE_LABELS = {"hourly": msg("매시"), "weekly": msg("매주"), "monthly-first-monday": msg("매달 첫 월요일"),
                   "manual": msg("사람이"), "once": msg("한 번")}
RUNS_ON_LABELS = {"container": msg("컨테이너"), "host": msg("호스트"), "person": msg("사람 손")}
FLAG_LABELS = {"nc": msg("비상업"), "sold": msg("판매"), "lab_only": msg("내부용"), "no_store": msg("담지 않음")}
#: 장부의 코드 값 — 화면에는 이 이름으로 (#373 검토 4)
RESULT_LABELS = {"ok": msg("성공"), "fail": msg("실패"), "skip": msg("건너뜀")}
ORIGIN_LABELS = {"container": msg("컨테이너"), "hourly": msg("매시 차례"), "host": msg("호스트"),
                 "backfill": msg("어림"), "spec": msg("명세")}
#: 명세를 어디서 읽었나 — `db` 가 아니면 탭 머리에 띄운다
SPEC_ORIGIN_LABELS = {"seed": msg("저장소의 씨앗"), "none": msg("빈 명세")}


def _parse_time(text):
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def is_late(row: dict, last_ok, now=None, first=None) -> bool:
    """주기보다 오래 된 적이 없다. 기록이 아예 없는 것은 늦은 것이 아니라 "모름" 이다.

    **한 번도 된 적이 없으면 첫 차례부터 잰다** — 매시 일이 처음부터 깨져 있으면 "깨짐" 으로만 떠 늦음에 안 잡혔다(#373 검토 6).
    """
    hours = LATE_HOURS.get(row.get("schedule"))
    when = _parse_time((last_ok or first or {}).get("started_at"))
    if not hours or when is None:
        return False
    now = now or datetime.now(when.tzinfo)
    return (now - when).total_seconds() > hours * 3600


def overview(sync: bool = True, history: bool = True, files: bool = True) -> dict:
    """명세·기록 표·구운 파일을 엮은 한 장 — 관리 화면과 healthz 가 읽는다. 경로는 `<DB 옆>` 아래 이름만.

    healthz 는 수만 쓰므로 `history=False, files=False` — 지난 차례도 구운 파일의 stat 도 하지 않는다(#373 검토 7).
    """
    from . import datastatus, fetchlog

    spec = load()
    if sync:
        try:
            fetchlog.sync(spec.rows)
        except Exception:                     # noqa: BLE001 — 옮겨 적기가 깨져도 화면은 선다
            pass
    latest = fetchlog.latest()
    files = {r["key"]: r for r in datastatus.rows()} if files else {}
    # 밖에 연 판(`GSM_PUBLIC`)에서는 연구실 내부용을 내리지 않는다 — 이름·지난 차례·마지막 말까지 (#373 검토 5, `views.LAB_ONLY`)
    shown = [r for r in spec.rows if not (settings.PUBLIC and "lab_only" in r.get("flags", []))]
    rows, counts = [], {"total": len(shown), "late": 0, "failed": 0, "unknown": 0, "invalid": len(spec.problems)}
    for row in shown:
        got = latest.get(row["id"]) or {}
        last, last_ok = got.get("last"), got.get("last_ok")
        late = is_late(row, last_ok, first=got.get("first"))
        failed = bool(last and last["result"] == "fail")
        unknown = last is None and row.get("kind") != "file"
        counts["late"] += late
        counts["failed"] += failed
        counts["unknown"] += unknown
        outputs = []
        for key in row.get("outputs", []):
            f = files.get(key)
            if f is None:
                outputs.append({"key": key, "kind": "repo" if key.startswith(("data/", "static/")) else "other"})
            else:
                outputs.append({"key": key, "kind": "file", **f})
        rows.append({"row": row, "last": last, "last_ok": last_ok, "late": late, "failed": failed, "unknown": unknown,
                     "history": [], "outputs": outputs})
    if history:
        past = fetchlog.history_many([r["row"]["id"] for r in rows if r["last"]], 20)
        for r in rows:
            r["history"] = past.get(r["row"]["id"], [])
    # 씨앗과 다른 줄 — 표를 읽었을 때만(씨앗을 읽었으면 다를 것이 없다). healthz 는 보지 않는다
    differs = seed_differs(spec.rows) if (history and spec.origin == "db") else {}
    for r in rows:
        r["seed_differs"] = differs.get(r["row"]["id"], [])
    # 명세를 마지막으로 고친 때 — 이력 표에서. 파일 시절의 `_spec` 기록 줄은 이제 남기지 않는다
    change = last_change() if history else None
    spec_change = {"started_at": timezone.localtime(change.at).isoformat(timespec="seconds")} if change else None
    return {"rows": rows, "counts": counts, "problems": spec.problems, "origin": spec.origin,
            "spec_changed": spec_change, "seed_differs": len(differs)}
