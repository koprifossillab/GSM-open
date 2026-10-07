"""받은 차례의 기록 — `GSM.db` 의 `FetchRun` (jikhanjung P02 2 단계, P03 에서 `store.sqlite` 의 `fetch_log` 를 옮겼다).

**문이 아니다.** 받아 두는 데이터소스(`DataSource`)마다 **받은 차례 하나가 한 줄**이다 — 언제·결과·걸린 초·마지막 말·
상류가 센 수 대 받은 수·원본 자리와 sha·구운 판. 사람이 정하는 것(조건·주기)은 명세에, 돌아가며 바뀌는 것은 여기에 둔다.
받은 판의 정보(파일·sha256)는 원본 폴더의 `manifest.json` 이 지니고, 줄의 `raw_path` 가 그 폴더를 가리킨다.
바깥에 내는 꼴(줄의 dict, `started_at` 은 이 서버 시간대의 ISO 글)은 파일 시절 그대로다 — 부르는 쪽을 고치지 않으려고.

누가 쓰나
- **컨테이너의 `fetch_*`·`build_*`** — `apps.py` 가 명령의 `execute` 를 감싸 끝날 때 한 줄을 적는다. 명령은 아는 것을 `note()` 로
  보탠다(`rows`·`expected`·`raw_path` …). 명령 마흔다섯을 하나하나 고치지 않으려고 한 자리에서 감쌌다
- **호스트**(`run.sh` 가 `GSM_RUN_PLACE=host`)는 **`FetchRun` 에 쓰지 않는다** — 읽기만 한다. `hourly.sh` 가 부른 일(`GSM_HOURLY_JOB=1`)은
  `hourly_status.json` 이 남기고, 그 밖에 호스트에서 부른 일(ERA5·ECCO2, 손으로 부른 `run.sh fetch_araon --past` 따위)은
  `fetch_log_host/<날짜>.jsonl` 에 한 줄을 덧붙인다. 컨테이너가 옮겨 적는다(`sync()`) — jsonl 은 읽은 자리를 기억해 새 줄만 읽는다
"""
import contextlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.utils import timezone as dj_tz

from .i18n import msg

log = logging.getLogger(__name__)

#: 명령이 `note()` 로 보탤 수 있는 칸
FIELDS = ("upstream_version", "expected", "rows", "changed", "raw_path", "raw_sha256", "built_at", "built_by")
COLUMNS = ("source", "command", "started_at", "seconds", "result", "note", "estimated", "origin", *FIELDS)
_DEFAULTS = {"command": "", "note": "", "estimated": 0, "origin": "container", "upstream_version": "",
             "raw_path": "", "raw_sha256": "", "built_at": "", "built_by": ""}

_local = threading.local()


def store_path() -> Path:
    return Path(settings.STORE_PATH)


#: 호스트가 남기는 jsonl 의 폴더 — 날마다 한 파일(`<폴더>/<YYYYMMDD>.jsonl`, jikhanjung 023). 컨테이너가 다 들인 지난 날의 파일은 지운다
HOST_LOG = "fetch_log_host"       # 호스트에서 부른 일의 기록(손으로 부른 것)
HOST_USAGE = "upstream_host"      # 호스트가 센 상류 호출 수(`usage.py`)
#: 다 들인 파일도 이만큼 지난 날의 것만 지운다 — 어제 것은 자정을 넘겨 도는 일이 아직 쓸 수 있다
HOST_KEEP_DAYS = 1


def host_dir(name: str) -> Path:
    return store_path().parent / name


def host_log_path() -> Path:
    """옛 한 파일(`fetch_log_host.jsonl`) — 날마다 나누기 전의 것. 다 들일 때까지 읽고 지운다"""
    return store_path().parent / f"{HOST_LOG}.jsonl"


def append_day(name: str, row: dict):
    """호스트가 `<DB 옆>/<name>/<오늘>.jsonl` 에 한 줄을 덧붙인다. 폴더는 무리가 쓸 수 있게(컨테이너가 다 들인 파일을 지운다)"""
    from django.utils import timezone as dj_tz
    folder = host_dir(name)
    if not folder.is_dir():
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(folder, 0o2775)
        except OSError:
            pass
    p = folder / f"{dj_tz.localdate():%Y%m%d}.jsonl"
    new = not p.exists()
    with open(p, "a", encoding="utf-8") as fh:            # 한 줄 덧붙이기는 쪼개지지 않는다
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if new:
        try:
            os.chmod(p, 0o664)
        except OSError:
            pass


def hourly_status_path() -> Path:
    return store_path().parent / "hourly_status.json"


def on_host() -> bool:
    return os.environ.get("GSM_RUN_PLACE") == "host"


def refuse_on_host(command: str):
    """DB 를 여는 명령은 호스트에서 돌리지 않는다(P03) — 컨테이너에서 부르라고 알리고 멈춘다"""
    if on_host():
        from django.core.management.base import CommandError
        raise CommandError(f"호스트는 GSM.db 를 열지 않는다 — 컨테이너 안에서 부른다: "
                           f"docker compose exec web python manage.py {command}")


def from_hourly() -> bool:
    """`hourly.sh` 가 부른 일 — 그 결과는 `hourly_status.json` 이 남긴다"""
    return os.environ.get("GSM_HOURLY_JOB") == "1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── 쓰기 ────────────────────────────────────────────────────────────

def _dt(text):
    """줄의 `started_at`(ISO 글) → 시간대가 붙은 때. 시간대가 없으면 이 서버의 것으로. 못 읽으면 None"""
    if isinstance(text, datetime):
        value = text
    else:
        try:
            value = datetime.fromisoformat(str(text))
        except (TypeError, ValueError):
            return None
    return dj_tz.make_aware(value) if dj_tz.is_naive(value) else value


def _obj(row: dict):
    from .models import FetchRun
    when = _dt(row.get("started_at"))
    if when is None or not row.get("source") or not row.get("result"):
        return None
    values = {c: row.get(c) for c in COLUMNS if c != "started_at"}
    values = {c: (_DEFAULTS.get(c) if v is None and c in _DEFAULTS else v) for c, v in values.items()}
    values["estimated"] = bool(values.get("estimated"))
    for c in ("note", "upstream_version", "raw_path", "raw_sha256", "built_at", "built_by", "command"):
        values[c] = str(values.get(c) or "")
    return FetchRun(started_at=when, **values)


def write(row: dict):
    """한 줄을 적는다. 같은 (데이터소스·시작한 때·어디서)는 한 번만. 호스트는 쓰지 않는다."""
    write_many([row])


def write_many(rows) -> int:
    """여럿을 한 트랜잭션에. 새로 적힌 줄 수."""
    from .models import FetchRun
    if on_host():
        raise RuntimeError("호스트는 기록 표에 쓰지 않는다")
    objs = [o for o in (_obj(r) for r in rows) if o is not None]
    if not objs:
        return 0
    with transaction.atomic():
        before = FetchRun.objects.count()
        FetchRun.objects.bulk_create(objs, ignore_conflicts=True)
        return FetchRun.objects.count() - before


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
                # hourly.sh 가 부른 일도 남긴다 — `note()` 로 보탠 값(받은 수·판·바뀐 수)은 이 프로세스만 안다. hourly_status.json 은
                # bash 가 써서 종료 코드·초·마지막 말뿐이다. 같은 차례가 두 줄이 되지 않게 표시하고 옮길 때 하나로 (jikhanjung 024)
                _append_host({**row, "hourly": True} if from_hourly() else row)
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
    append_day(HOST_LOG, row)


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


def _hourly_rows(spec_rows, check: bool = False) -> list:
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
                     "origin": "hourly", "_end": job["at"]})
        last_ok = job.get("last_ok")
        if last_ok and last_ok != job["at"]:
            # 옮기기 전에 성공 뒤 실패가 오면 성공 줄이 빠진다. 그 성공을 이미 옮겼다면 같은 줄이 되어야 한다 —
            # `at` 처럼 시작한 때로 당긴다(`last_ok_seconds`). 그것이 없는 옛 상태 파일이면 이미 옮긴 성공이 있는지 본다
            took = job.get("last_ok_seconds")
            if took is not None:
                rows.append({"source": source["id"], "command": command, "started_at": _shift(last_ok, took),
                             "seconds": took, "result": "ok", "note": "마지막으로 된 차례", "origin": "hourly", "_end": last_ok})
            elif not (check and _hourly_ok_near(source["id"], last_ok)):
                rows.append({"source": source["id"], "command": command, "started_at": last_ok, "result": "ok",
                             "note": "마지막으로 된 차례 — 끝난 때 (걸린 초는 모른다)", "origin": "hourly", "_end": last_ok})
    return rows


#: `hourly.sh` 가 일 하나에 주는 초(`LIMIT`) — 끝난 때에서 이만큼 안쪽에 시작한 성공은 같은 차례다
HOURLY_LIMIT = 900


def _hourly_ok_near(source: str, end: str) -> bool:
    """`end` 에 끝난 매시 성공을 이미 옮겨 적었나 — 시작한 때가 `end` 에서 `HOURLY_LIMIT` 초 안쪽인 성공 줄"""
    from .models import FetchRun
    stop = _dt(end)
    if stop is None:
        return False
    return FetchRun.objects.filter(source=source, origin="hourly", result="ok",
                                   started_at__range=(stop - timedelta(seconds=HOURLY_LIMIT), stop)).exists()


def new_lines(path: Path, mark: str) -> list:
    """덧붙이기만 하는 jsonl 에서 지난번에 읽은 자리(`FetchRunMark` 의 `mark`) 뒤의 줄만 — dict 의 목록. 파일이 줄었으면(바뀌었으면)
    처음부터, 덜 적힌 마지막 줄은 다음 차례에. 호스트가 남긴 파일을 컨테이너가 들일 때 쓴다(기록·상류 호출 수)"""
    from .models import FetchRunMark
    try:
        size = path.stat().st_size
    except OSError:
        return []
    got = FetchRunMark.objects.filter(key=mark).first()
    offset = int(got.value) if got and got.value.isdigit() else 0
    if offset > size:
        offset = 0
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    rows = []
    for line in data[:end].decode("utf-8", "replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    FetchRunMark.objects.update_or_create(key=mark, defaults={"value": str(offset + end)})
    return rows


def drain(name: str, legacy_mark: str) -> list:
    """호스트가 남긴 jsonl 들의 새 줄 — 옛 한 파일(`<name>.jsonl`)과 날마다의 파일(`<name>/<YYYYMMDD>.jsonl`), dict 의 목록.

    다 들인(읽은 자리가 끝인) 파일은 지운다 — 날마다의 것은 `HOST_KEEP_DAYS` 보다 지난 날의 것만, 옛 한 파일은 하루 넘게 손대지 않은 것만.
    **지우기는 커밋 뒤에** — 부르는 쪽의 트랜잭션이 깨지면 자리도 되돌아가니 파일이 남아야 다음에 다시 읽는다 (jikhanjung 023)
    """
    from django.utils import timezone as dj_tz
    rows, done = [], []
    legacy = store_path().parent / f"{name}.jsonl"
    if legacy.exists():
        rows += new_lines(legacy, legacy_mark)
        try:
            stale = time.time() - legacy.stat().st_mtime > 86400
        except OSError:
            stale = False
        if stale and _fully_read(legacy, legacy_mark):
            done.append((legacy, legacy_mark))
    folder = host_dir(name)
    if folder.is_dir():
        oldest = dj_tz.localdate() - timedelta(days=HOST_KEEP_DAYS)
        for p in sorted(folder.glob("*.jsonl")):
            mark = f"{name}/{p.stem}"
            rows += new_lines(p, mark)
            try:
                day = datetime.strptime(p.stem, "%Y%m%d").date()
            except ValueError:
                continue
            if day < oldest and _fully_read(p, mark):
                done.append((p, mark))
    if done:
        transaction.on_commit(lambda: _remove(done))
    return rows


def _fully_read(path: Path, mark: str) -> bool:
    from .models import FetchRunMark
    got = FetchRunMark.objects.filter(key=mark).first()
    try:
        return bool(got) and got.value.isdigit() and int(got.value) >= path.stat().st_size
    except OSError:
        return False


def _remove(done):
    from .models import FetchRunMark
    for path, mark in done:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:                     # 지우지 못하면 남긴다 — 읽은 자리가 있어 두 번 들이지 않는다
            log.warning("다 들인 호스트 기록을 지우지 못했다 (%s): %s", path.name, exc)
            continue
        FetchRunMark.objects.filter(key=mark).delete()


def _host_rows() -> list:
    """호스트 기록(jsonl)의 새 줄 — `hourly.sh` 가 부른 일(`"hourly": true`)은 origin `hourly`, 그 밖은 `host`"""
    out = []
    for r in drain(HOST_LOG, "host_offset"):
        if not (r.get("source") and r.get("started_at")):
            continue
        hourly = bool(r.pop("hourly", False))
        out.append({**r, "origin": "hourly" if hourly else "host"})
    return out


def _seen_run(source: str, end, batch) -> bool:
    """`end` 에 끝난 매시 차례를 jsonl 이 이미 가져왔나 — 이번에 함께 옮기는 줄이나 표에, 같은 데이터소스의 origin `hourly` 줄이
    `end` 에서 `HOURLY_LIMIT` 초 안쪽에 시작한 것. 그러면 hourly_status.json 의 줄(값이 모자란 것)은 버린다 (jikhanjung 024)"""
    from .models import FetchRun
    stop = _dt(end)
    if stop is None:
        return False
    start = stop - timedelta(seconds=HOURLY_LIMIT)
    for r in batch:
        when = _dt(r.get("started_at"))
        if r["source"] == source and when is not None and start <= when <= stop:
            return True
    return FetchRun.objects.filter(source=source, origin="hourly", started_at__range=(start, stop)).exists()


def sync(spec_rows=None) -> int:
    """호스트가 남긴 것(`hourly_status.json`·`fetch_log_host/`)을 `FetchRun` 으로, `upstream_host/` 를 `UpstreamDay` 로. 옮긴 기록 줄 수.

    호스트에서는 하지 않고, 기록이 꺼져 있으면(시험) 하지 않는다. 못 적으면 0 — 부르는 쪽을 죽이지 않는다.
    """
    if on_host():
        return 0
    # 호스트가 센 상류 호출(`upstream_host/`)은 기록을 끄든 말든 들인다 — 호스트는 UpstreamDay 에 쓰지 않는다(P03, jikhanjung 018)
    from . import usage
    usage.sync_host()
    if not getattr(settings, "FETCH_LOG", True):
        return 0
    if spec_rows is None:
        from . import sources
        spec_rows = sources.load().rows
    # 호스트는 명세를 읽지 않아 명령 이름을 데이터소스 자리에 적어 둔다(P03) — 여기서 데이터소스로 바꾼다
    by_command = {c: r["id"] for r in spec_rows for c in r.get("commands", [])}
    ids = {r["id"] for r in spec_rows}
    moved = 0
    try:
        with transaction.atomic():
            host = [{**r, "source": by_command.get(r["source"], r["source"]) if r["source"] not in ids else r["source"]}
                    for r in _host_rows()]
            # jsonl 이 가져온 매시 차례(값이 다 있다)가 이긴다 — hourly_status.json 의 줄은 jsonl 이 없을 때(시간을 넘겨 죽었을 때 따위)만
            from_jsonl = [r for r in host if r["origin"] == "hourly"]
            status = [r for r in _hourly_rows(spec_rows, True)
                      if not _seen_run(r["source"], r.pop("_end"), from_jsonl)]
            rows = status + host
            moved = write_many(rows) if rows else 0
    except (DatabaseError, OSError):
        moved = 0
    return moved


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

def as_dict(run) -> dict:
    """`FetchRun` → 파일 시절의 줄 꼴. `started_at` 은 이 서버 시간대의 ISO 글"""
    d = {c: getattr(run, c) for c in COLUMNS if c != "started_at"}
    d["id"] = run.pk
    d["started_at"] = dj_tz.localtime(run.started_at).isoformat(timespec="seconds")
    d["estimated"] = int(bool(run.estimated))
    return d


def _ranked(qs, desc=True):
    """데이터소스마다 차례를 매긴다 — 때로(UTC 로 적혀 시간대가 섞여도 맞다, #375), 같으면 나중에 적힌 것"""
    order = [F("started_at").desc(), F("id").desc()] if desc else [F("started_at").asc(), F("id").asc()]
    return qs.annotate(rn=Window(RowNumber(), partition_by=[F("source")], order_by=order))


def latest() -> dict:
    """데이터소스마다 마지막 줄·마지막으로 된(`ok`) 줄·첫 줄 — {id: {"last", "last_ok", "first"}}.

    `skip` 은 된 것으로 치지 않는다 — 치면 건너뛰기만 거듭하는 일의 늦음이 가려진다(#373 검토 6). 첫 줄은 한 번도 된 적 없는
    일이 언제부터 그랬는지 재려고 둔다. 표가 아직 없으면(마이그레이션 전) 빈 것.
    """
    from .models import FetchRun
    out = {}
    try:
        for run in _ranked(FetchRun.objects.all()).filter(rn=1):
            out[run.source] = {"last": as_dict(run), "last_ok": None, "first": None}
        for run in _ranked(FetchRun.objects.filter(result="ok")).filter(rn=1):
            out[run.source]["last_ok"] = as_dict(run)
        for run in _ranked(FetchRun.objects.all(), desc=False).filter(rn=1):
            out[run.source]["first"] = as_dict(run)
    except DatabaseError:
        return {}
    return out


def history(source: str, limit: int = 20) -> list:
    return history_many([source], limit).get(source, [])


def history_many(sources, limit: int = 20) -> dict:
    """여러 데이터소스의 지난 차례를 질의 하나로 — {id: [줄 …]}, 새것부터 (#373 검토 7)."""
    from .models import FetchRun
    ids = list(dict.fromkeys(sources))
    if not ids:
        return {}
    out = {}
    try:
        runs = _ranked(FetchRun.objects.filter(source__in=ids)).filter(rn__lte=limit).order_by("source", "-started_at", "-id")
        for run in runs:
            out.setdefault(run.source, []).append(as_dict(run))
    except DatabaseError:
        return {}
    return out


# ── 화면에 낼 때 ────────────────────────────────────────────────────

#: 장부가 스스로 적는 고정 문장 — 장부에는 한국어 원문으로 두고 화면이 옮긴다 (#373 검토 4)
NOTE_TEXTS = {m.template: m for m in (
    msg("마지막으로 된 차례"),
    msg("마지막으로 된 차례 — 끝난 때 (걸린 초는 모른다)"),
    msg("산출물 파일의 고친 날로 어림했다"),
)}
SPEC_NOTE = "명세가 바뀌었다 — "


def note_text(text: str):
    """장부의 note 를 화면의 글로 — 고정 문장은 `msg` 로 돌려 영어판이 옮기게, 그 밖의 것(명령의 말)은 그대로."""
    text = text or ""
    if text in NOTE_TEXTS:
        return NOTE_TEXTS[text]
    if text.startswith(SPEC_NOTE):
        return msg("명세가 바뀌었다 — {name}", name=text[len(SPEC_NOTE):])
    return text
