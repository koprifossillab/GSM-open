"""받아 두는 자료원의 명세 — `<DB 옆>/sources.json` (jikhanjung P02).

**문이 아니다.** 상류를 부르지 않고, 사람이 정하는 것(조건·주기·돌리는 곳·명령·산출물)을 적은 JSON 한 장을 읽는다.
받은 차례마다의 기록(받은 때·결과·행 수)은 여기 두지 않는다 — 돌아가며 바뀌는 것은 기록 표(`store.sqlite`, P02 2 단계)의 몫이다.

- **씨앗** `data/sources.seed.json` — 컨테이너가 뜰 때(`manage.py sources_seed`) 운영 명세가 없으면 옮겨 놓고, 있으면 씨앗에만 있는
  `id` 를 덧붙이기만 한다. 사람이 고친 줄은 덮지 않는다(`seed_catalog` 가 손질한 제목을 지키는 것과 같다)
- **이력** — 읽을 때 파일이 앞서 본 판과 다르면 그 판을 `<DB 옆>/sources_history/` 에 떠 둔다. 관리 화면에 계정이 없어 명세는
  서버에서 손으로 고친다 — 누가 언제 고쳤는지는 이 떠 둔 판과 파일 주인이 말한다
- **틀린 줄은 건너뛴다** — 칸이 틀리거나 빠진 줄은 빼고 `problems` 에 적는다. 파일째 못 읽으면 마지막으로 떠 둔 판을 쓴다.
  뷰어는 멈추지 않는다

지금 있는 파이썬 표(`datastatus.ITEMS`·`static_site.UPSTREAMS`·`views.LAB_ONLY`·`views.NO_STORE`)는 그대로 둔다 —
손댈 일이 생길 때 하나씩 옮긴다(docs/자료_적재_구조.md "명세는 JSON 으로"). 어긋나면 `coverage()` 가 알린다.
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .i18n import msg

KINDS = ("fetch", "build", "file", "once")
RUNS_ON = ("container", "host", "person")
SCHEDULES = ("hourly", "weekly", "monthly-first-monday", "manual", "once")
FLAGS = ("nc", "sold", "lab_only", "no_store")

#: 이만큼 넘게 된 적이 없으면 늦었다 (시간). manual·once 는 늦지 않는다 — 화면(P02 3 단계)이 쓴다
LATE_HOURS = {"hourly": 3, "weekly": 9 * 24, "monthly-first-monday": 40 * 24}

_ID = re.compile(r"^[a-z0-9_]+$")
_lock = threading.Lock()
_cache = {"key": None, "spec": None}


def path() -> Path:
    return Path(settings.SOURCES_PATH)


def history_dir() -> Path:
    return path().parent / "sources_history"


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
        out.append(msg("받거나 굽는 자료원인데 commands 가 비었다"))
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
        self.origin = origin              # file · history · seed · none
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


# ── 읽기 ────────────────────────────────────────────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _latest_history():
    folder = history_dir()
    try:
        found = sorted(p for p in folder.glob("*.json") if p.is_file())
    except OSError:
        return None
    return found[-1] if found else None


def _keep_history(data: bytes, sha: str):
    """앞서 떠 둔 판과 다르면 이 판을 떠 둔다. 못 쓰면 조용히 넘어간다 — 읽기를 막지 않는다."""
    last = _latest_history()
    if last is not None and last.stem.endswith(sha[:12]):
        return
    folder = history_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{sha[:12]}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError:
        pass


def _parse(data: bytes):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def load(keep_history: bool = True) -> Spec:
    """운영 명세를 읽는다. 파일이 바뀌지 않았으면 들고 있던 것을 준다."""
    p = path()
    try:
        st = p.stat()
        key = (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(p), None, None)
    with _lock:
        if _cache["key"] == key and _cache["spec"] is not None:
            return _cache["spec"]
        spec = _read(p, keep_history)
        _cache.update(key=key, spec=spec)
        return spec


def _read(p: Path, keep_history: bool) -> Spec:
    now = datetime.now()
    try:
        data = p.read_bytes()
    except OSError:
        data = None
    if data is not None:
        raw = _parse(data)
        if raw is not None:
            sha = _sha(data)
            if keep_history:
                _keep_history(data, sha)
            rows, problems = _check(raw)
            return Spec(rows, problems, "file", sha, now)
        broken = [("", [msg("명세 파일을 JSON 으로 읽지 못했다 — 마지막으로 떠 둔 판을 쓴다")])]
        last = _latest_history()
        if last is not None:
            older = last.read_bytes()
            rows, problems = _check(_parse(older) or {})
            return Spec(rows, broken + problems, "history", _sha(older), now)
        return Spec([], broken, "none", "", now)
    # 운영 명세가 아직 없다(개발 장비·시험) — 씨앗을 읽는다
    try:
        data = seed_path().read_bytes()
    except OSError:
        return Spec([], [("", [msg("명세도 씨앗도 없다")])], "none", "", now)
    rows, problems = _check(_parse(data) or {})
    return Spec(rows, problems, "seed", _sha(data), now)


# ── 씨앗 ────────────────────────────────────────────────────────────

def seed() -> dict:
    """씨앗을 운영 명세에 옮긴다. 없으면 통째로, 있으면 씨앗에만 있는 id 를 끝에 덧붙인다.

    돌려주는 것 — {"created": bool, "added": [id…], "differs": [id…]}. `differs` 는 씨앗과 운영의 같은 id 가 다른 줄이다
    (덮지 않았다 — 옮길지는 사람이 정한다).
    """
    seed_raw = _parse(seed_path().read_bytes()) or {}
    seed_rows = [r for r in seed_raw.get("sources") or [] if isinstance(r, dict)]
    p = path()
    try:
        live_data = p.read_bytes()
    except OSError:
        live_data = None
    if live_data is None:
        _write(p, seed_raw)
        return {"created": True, "added": [r.get("id") for r in seed_rows], "differs": []}
    live_raw = _parse(live_data)
    if not isinstance(live_raw, dict) or not isinstance(live_raw.get("sources"), list):
        # 사람이 고치다 깬 파일을 씨앗으로 덮지 않는다 — 읽기가 떠 둔 판으로 버티고, 사람이 고친다
        return {"created": False, "added": [], "differs": [], "broken": True}
    live_ids = {r.get("id"): r for r in live_raw["sources"] if isinstance(r, dict)}
    added = [r for r in seed_rows if r.get("id") not in live_ids]
    differs = [r["id"] for r in seed_rows if r.get("id") in live_ids and live_ids[r["id"]] != r]
    if added:
        live_raw["sources"].extend(added)
        _write(p, live_raw)
    return {"created": False, "added": [r.get("id") for r in added], "differs": differs}


def _write(p: Path, raw: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o664)            # 무리(paleoadmin)가 손으로 고칠 수 있게
    except OSError:
        pass
    os.replace(tmp, p)


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
        out.append(f"명령 {c} 가 어느 자료원에도 없다")
    for c in sorted(named - on_disk):
        out.append(f"자료원이 적은 명령 {c} 가 없다")
    outputs = {o for r in rows for o in r.get("outputs", [])}
    for item in datastatus.ITEMS:
        if item.key not in outputs:
            out.append(f"구운 자료 {item.key} 가 어느 자료원의 outputs 에도 없다")
    lab = {i.key for i in datastatus.ITEMS if i.lab}
    for r in rows:
        flagged = "lab_only" in r.get("flags", [])
        mine = set(r.get("outputs", [])) & {i.key for i in datastatus.ITEMS}
        if mine and flagged != bool(mine & lab):
            out.append(f"{r['id']} 의 lab_only 가 datastatus 의 연구실 내부용 표시와 다르다")
    return out
