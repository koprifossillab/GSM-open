"""받은 차례의 기록 — `<DB 옆>/store.sqlite` 의 `fetch_log` (jikhanjung P02 2 단계).

**문이 아니다.** 받아 두는 데이터소스(`sources.json`, P02 1 단계)마다 **받은 차례 하나가 한 줄**이다 — 언제·결과·걸린 초·마지막 말·
상류가 센 수 대 받은 수·원본 자리와 sha·구운 판. 사람이 정하는 것(조건·주기)은 명세에, 돌아가며 바뀌는 것은 여기에 둔다.
`store.sqlite` 는 뒤의 적재(②)가 데이터소스마다 표를 더할 그 파일이다 — Django 의 `GSM.db` 에는 넣지 않는다(백업이 부푼다).

누가 쓰나
- **컨테이너의 `fetch_*`·`build_*`** — `apps.py` 가 명령의 `execute` 를 감싸 끝날 때 한 줄을 적는다. 명령은 아는 것을 `note()` 로
  보탠다(`rows`·`expected`·`raw_path` …). 명령 마흔다섯을 하나하나 고치지 않으려고 한 자리에서 감쌌다
- **호스트**(`run.sh` 가 `GSM_RUN_PLACE=host`)는 **sqlite 를 만들지도 쓰지도 않는다** — 컨테이너와 한 파일에 쓰지 않게(검토의 "잠금").
  읽을 때는 읽기 전용으로 열고, 없으면 빈 것이다. `hourly.sh` 가 부른 일(`GSM_HOURLY_JOB=1`)은 `hourly_status.json` 이 남기고, 그 밖에
  호스트에서 부른 일(ERA5·ECCO2, 손으로 부른 `run.sh fetch_araon --past` 따위)은 `fetch_log_host.jsonl` 에 한 줄을 덧붙인다.
  컨테이너가 화면·healthz 를 그릴 때 둘을 옮겨 적는다(`sync()`) — jsonl 은 읽은 자리를 기억해 새 줄만 읽는다
"""
import contextlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetch_log (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    command          TEXT NOT NULL DEFAULT '',
    started_at       TEXT NOT NULL,
    seconds          REAL,
    result           TEXT NOT NULL,          -- ok · fail · skip
    note             TEXT NOT NULL DEFAULT '',
    upstream_version TEXT NOT NULL DEFAULT '',
    expected         INTEGER,                -- 상류가 센 수
    rows             INTEGER,                -- 받은(적재한) 수
    changed          INTEGER,
    raw_path         TEXT NOT NULL DEFAULT '',
    raw_sha256       TEXT NOT NULL DEFAULT '',
    built_at         TEXT NOT NULL DEFAULT '',
    built_by         TEXT NOT NULL DEFAULT '',
    estimated        INTEGER NOT NULL DEFAULT 0,  -- 1 이면 지난 것을 파일 stat 으로 어림한 줄
    origin           TEXT NOT NULL DEFAULT 'container',  -- container · hourly · host · backfill · spec
    UNIQUE (source, started_at, origin)
);
CREATE INDEX IF NOT EXISTS fetch_log_source ON fetch_log (source, started_at);
CREATE TABLE IF NOT EXISTS fetch_log_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""

#: 명령이 `note()` 로 보탤 수 있는 칸
FIELDS = ("upstream_version", "expected", "rows", "changed", "raw_path", "raw_sha256", "built_at", "built_by")
COLUMNS = ("source", "command", "started_at", "seconds", "result", "note", "estimated", "origin", *FIELDS)
_DEFAULTS = {"command": "", "note": "", "estimated": 0, "origin": "container", "upstream_version": "",
             "raw_path": "", "raw_sha256": "", "built_at": "", "built_by": ""}

_local = threading.local()


def store_path() -> Path:
    return Path(settings.STORE_PATH)


def host_log_path() -> Path:
    return store_path().parent / "fetch_log_host.jsonl"


def hourly_status_path() -> Path:
    return store_path().parent / "hourly_status.json"


def on_host() -> bool:
    return os.environ.get("GSM_RUN_PLACE") == "host"


def from_hourly() -> bool:
    """`hourly.sh` 가 부른 일 — 그 결과는 `hourly_status.json` 이 남긴다"""
    return os.environ.get("GSM_HOURLY_JOB") == "1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── 열기 ────────────────────────────────────────────────────────────

@contextlib.contextmanager
def connect():
    """쓰는 연결 — 컨테이너만. 표는 열 때마다 `IF NOT EXISTS` 로 — 파일을 지우거나 되살려도 오래 떠 있는 일꾼이 다시 짓는다."""
    if on_host():
        raise RuntimeError("호스트는 store.sqlite 에 쓰지 않는다")
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    db = sqlite3.connect(p, timeout=10)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        if new:
            try:
                os.chmod(p, 0o664)
            except OSError:
                pass
        yield db
        db.commit()
    finally:
        db.close()


@contextlib.contextmanager
def reader():
    """읽는 연결 — 파일을 만들지 않는다. 없으면 None. 호스트는 읽기 전용으로 연다."""
    p = store_path()
    if not p.exists():
        yield None
        return
    if on_host():
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    else:
        db = sqlite3.connect(p, timeout=10)
    try:
        db.row_factory = sqlite3.Row
        try:
            db.execute("SELECT 1 FROM fetch_log LIMIT 1")
        except sqlite3.Error:                     # 표가 아직 없다
            yield None
            return
        yield db
    finally:
        db.close()


def _values(row: dict) -> list:
    values = [row.get(c) for c in COLUMNS]
    return [_DEFAULTS.get(c) if v is None and c in _DEFAULTS else v for c, v in zip(COLUMNS, values)]


_INSERT = f"INSERT OR IGNORE INTO fetch_log ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})"


def write(row: dict):
    """한 줄을 적는다. 같은 (데이터소스·시작한 때·어디서)는 한 번만."""
    with connect() as db:
        db.execute(_INSERT, _values(row))


def write_many(rows, db=None) -> int:
    """여럿을 한 연결·한 트랜잭션에. 새로 적힌 줄 수."""
    if db is None:
        with connect() as conn:
            return write_many(rows, conn)
    before = db.total_changes
    db.executemany(_INSERT, [_values(r) for r in rows])
    return db.total_changes - before


# ── 명령이 끝날 때 ─────────────────────────────────────────────────

def note(**fields):
    """도는 명령이 아는 것을 보탠다 — `fetchlog.note(rows=…, expected=…)`. 기록 중이 아니면 아무 일도 없다."""
    current = getattr(_local, "current", None)
    if current is not None:
        current.update({k: v for k, v in fields.items() if k in FIELDS})


@contextlib.contextmanager
def record(source: str, command: str, schedule: str = "manual"):
    """명령 하나를 감싼다. 끝나면 결과·초·마지막 말을 적는다. 예외는 `fail` 로 적고 다시 던진다.

    기록이 실패해도 명령의 결과를 바꾸지 않는다 — 장부가 일을 막으면 안 된다.
    """
    started, t0 = _now(), time.monotonic()
    extra = {}
    previous = getattr(_local, "current", None)
    _local.current = extra
    tail = _Tail()
    result, last = "ok", ""
    try:
        yield tail
    except SystemExit as exc:
        result = "ok" if not exc.code else "fail"
        raise
    except BaseException as exc:
        result, last = "fail", f"{type(exc).__name__}: {exc}"[:300]
        raise
    finally:
        _local.current = previous
        row = {"source": source, "command": command, "started_at": started,
               "seconds": round(time.monotonic() - t0, 1), "result": result,
               "note": last or tail.last, **extra}
        try:
            if on_host():
                if not from_hourly():             # hourly.sh 가 부른 것은 hourly_status.json 이 남긴다
                    _append_host(row)
            else:
                write(row)
        except Exception:                         # noqa: BLE001 — 장부가 일을 막으면 안 된다
            pass


class _Tail:
    """명령의 출력을 그대로 넘기며 마지막 빈 줄 아닌 것을 기억한다."""

    def __init__(self, out=None):
        self.out = out
        self.last = ""

    def write(self, text):
        for line in str(text).splitlines():
            if line.strip():
                self.last = line.strip()[:300]
        if self.out is not None:
            return self.out.write(text)
        return len(text)

    def flush(self):
        if self.out is not None and hasattr(self.out, "flush"):
            self.out.flush()

    def isatty(self):
        return bool(self.out is not None and hasattr(self.out, "isatty") and self.out.isatty())


def _append_host(row: dict):
    p = host_log_path()
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as fh:            # 한 줄 덧붙이기는 쪼개지지 않는다
        fh.write(line)


# ── 옮겨 적기 ───────────────────────────────────────────────────────

def _shift(at: str, seconds) -> str:
    """`hourly.sh` 의 `at` 은 끝난 때다 — 걸린 초만큼 당겨 시작한 때로"""
    try:
        end = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return at
    try:
        return (end - timedelta(seconds=float(seconds or 0))).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return at


def _hourly_rows(spec_rows, db=None) -> list:
    """`hourly_status.json` 의 일마다 — 마지막 차례, 그리고 그것이 실패라면 마지막으로 된 차례(`last_ok`)도."""
    by_command = {c: r for r in spec_rows for c in r.get("commands", [])}
    try:
        jobs = json.loads(hourly_status_path().read_text(encoding="utf-8")).get("jobs") or {}
    except (OSError, ValueError, AttributeError):
        return []
    rows = []
    for command, job in jobs.items():
        source = by_command.get(command)
        if not source or not isinstance(job, dict) or not job.get("at"):
            continue
        result = {"ok": "ok", "skip": "skip"}.get(job.get("result"), "fail")
        rows.append({"source": source["id"], "command": command, "started_at": _shift(job["at"], job.get("seconds")),
                     "seconds": job.get("seconds"), "result": result, "note": str(job.get("note") or "")[:300],
                     "origin": "hourly"})
        last_ok = job.get("last_ok")
        if last_ok and last_ok != job["at"]:
            # 옮기기 전에 성공 뒤 실패가 오면 성공 줄이 빠진다. 그 성공을 이미 옮겼다면 같은 줄이 되어야 한다 —
            # `at` 처럼 시작한 때로 당긴다(`last_ok_seconds`). 그것이 없는 옛 상태 파일이면 이미 옮긴 성공이 있는지 본다
            took = job.get("last_ok_seconds")
            if took is not None:
                rows.append({"source": source["id"], "command": command, "started_at": _shift(last_ok, took),
                             "seconds": took, "result": "ok", "note": "마지막으로 된 차례", "origin": "hourly"})
            elif not _hourly_ok_near(db, source["id"], last_ok):
                rows.append({"source": source["id"], "command": command, "started_at": last_ok, "result": "ok",
                             "note": "마지막으로 된 차례 — 끝난 때 (걸린 초는 모른다)", "origin": "hourly"})
    return rows


#: `hourly.sh` 가 일 하나에 주는 초(`LIMIT`) — 끝난 때에서 이만큼 안쪽에 시작한 성공은 같은 차례다
HOURLY_LIMIT = 900


def _hourly_ok_near(db, source: str, end: str) -> bool:
    """`end` 에 끝난 매시 성공을 이미 옮겨 적었나 — 시작한 때가 `end` 에서 `HOURLY_LIMIT` 초 안쪽인 성공 줄"""
    if db is None:
        return False
    found = db.execute("SELECT 1 FROM fetch_log WHERE source = ? AND origin = 'hourly' AND result = 'ok' "
                       "AND started_at BETWEEN ? AND ? LIMIT 1", (source, _shift(end, HOURLY_LIMIT), end)).fetchone()
    return found is not None


def _host_rows(db) -> list:
    """jsonl 에서 지난번에 읽은 자리 뒤의 줄만. 파일이 줄었으면(바뀌었으면) 처음부터."""
    p = host_log_path()
    try:
        size = p.stat().st_size
    except OSError:
        return []
    got = dict(db.execute("SELECT k, v FROM fetch_log_meta WHERE k = 'host_offset'").fetchall())
    offset = int(got.get("host_offset", 0) or 0)
    if offset > size:
        offset = 0
    rows = []
    with open(p, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1                   # 덜 적힌 마지막 줄은 다음 차례에
    for line in data[:end].decode("utf-8", "replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("source") and row.get("started_at"):
            rows.append({**row, "origin": "host"})
    db.execute("INSERT OR REPLACE INTO fetch_log_meta (k, v) VALUES ('host_offset', ?)", (str(offset + end),))
    return rows


def sync(spec_rows=None) -> int:
    """호스트가 남긴 것(`hourly_status.json`·`fetch_log_host.jsonl`)을 `fetch_log` 로. 옮긴 줄 수.

    호스트에서는 하지 않고, 기록이 꺼져 있으면(시험) 하지 않는다. 장부를 못 열면 0 — 부르는 쪽을 죽이지 않는다.
    """
    if on_host() or not getattr(settings, "FETCH_LOG", True):
        return 0
    if spec_rows is None:
        from . import sources
        spec_rows = sources.load().rows
    try:
        with connect() as db:
            rows = _hourly_rows(spec_rows, db) + _host_rows(db)
            return write_many(rows, db) if rows else 0
    except (sqlite3.Error, OSError):
        return 0


# ── 화면에 내기 ─────────────────────────────────────────────────────

#: 쿼리에 실리면 지우는 값 — 상류 requests 예외는 주소 전체를 담는다(#373 검토 1)
_SECRET_QUERY = re.compile(r"(?i)\b(key|apikey|api_key|token|access_token|whoami|password|passwd|secret|auth)=[^&\s\"'<>]+")
#: 자료 자리 밖의 절대 경로 — 이름만 남긴다. 주소 안의 경로(`https://…/data/…`)는 건드리지 않는다
_ABS_PATH = re.compile(r"(?<![\w:/.])/(?:srv|home|data\d*|tmp|app|opt|var|root|mnt|nfs|usr)/[^\s\"'<>,;()]*")


def _roots() -> list:
    """settings 의 자료 자리 → 화면에 낼 이름. 긴 것부터 — `<DB 옆>/earth` 가 `<DB 옆>` 보다 먼저 맞게"""
    found = {str(store_path().parent): "<DB 옆>"}
    for name in dir(settings):
        if name.endswith("_DIR") and name not in ("BASE_DIR", "REPO_DIR", "LOG_DIR"):
            value = getattr(settings, name, None)
            if isinstance(value, str) and value.startswith("/"):
                found.setdefault(value.rstrip("/"), f"<{name}>")
    return sorted(found.items(), key=lambda kv: -len(kv[0]))


def shown(text: str) -> str:
    """장부의 글(명령의 마지막 줄·예외 글)을 관리 화면에 낼 꼴로 — 열쇠 값을 지우고, 자료 자리는 `<DB 옆>/…` 로,
    그 밖의 절대 경로는 이름만. 관리 화면은 계정을 묻지 않는다 (#373 검토 1)"""
    if not text:
        return ""
    text = _SECRET_QUERY.sub(lambda m: f"{m.group(1)}=…", text)
    for root, label in _roots():
        text = text.replace(root + "/", label + "/").replace(root, label)
    return _ABS_PATH.sub(lambda m: m.group(0).rstrip("/").rsplit("/", 1)[-1], text)


# ── 읽기 ────────────────────────────────────────────────────────────

_LAST = """
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY source ORDER BY started_at DESC, id DESC) AS rn
    FROM fetch_log {where}
) WHERE rn = 1
"""


def latest() -> dict:
    """데이터소스마다 마지막 줄과 마지막으로 된(ok·skip) 줄 — {id: {"last": row, "last_ok": row}}. 파일이 없으면 빈 것."""
    out = {}
    try:
        with reader() as db:
            if db is None:
                return out
            for row in db.execute(_LAST.format(where="")):
                d = dict(row)
                d.pop("rn", None)
                out[d["source"]] = {"last": d, "last_ok": None}
            for row in db.execute(_LAST.format(where="WHERE result IN ('ok', 'skip')")):
                d = dict(row)
                d.pop("rn", None)
                out.setdefault(d["source"], {"last": None, "last_ok": None})["last_ok"] = d
    except (sqlite3.Error, OSError):
        return {}
    return out


def history(source: str, limit: int = 20) -> list:
    try:
        with reader() as db:
            if db is None:
                return []
            return [dict(r) for r in db.execute(
                "SELECT * FROM fetch_log WHERE source = ? ORDER BY started_at DESC, id DESC LIMIT ?", (source, limit))]
    except (sqlite3.Error, OSError):
        return []
