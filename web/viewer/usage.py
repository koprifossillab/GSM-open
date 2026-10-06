"""상류 호출을 센다 — 그리고 차단 조짐이 보이면 스스로 쉰다.

**한계를 재지 않는다.** KIGAM 은 수치를 밝히지 않고, 재다 넘으면 서버 IP 가
막힌다 — 그러면 타일·범례·속성이 다 멈춘다. 그래서 두 가지만 한다.

1. 날마다 몇 번 물었는지, 차단 조짐이 몇 번 있었는지 센다 (`UpstreamDay`)
2. 차단 조짐이 5 분 안에 3 번 보이면 **10 분 동안 상류에 묻지 않는다.**
   막히기 시작했을 때 계속 두드려 일을 키우지 않으려는 것이다. 그동안은
   캐시가 내주고, 캐시에 없는 자리는 안내 타일이 뜬다

3. 걸린 시간도 센다(wetherilli 290) — 문이 받은 응답의 `elapsed` 를 칸(`TIME_BUCKETS`)으로 나눠 날마다 더한다. 주소·키는 적지 않는다
   — 상류의 이름과 초만 남는다. 느린 상류를 고를 때(메타타일, wetherilli 287) 이것을 본다

세는 일이 실패해도 **지도는 멈추지 않는다** — 세는 것은 덤이다.
"""
import logging
import sys
import threading
import time
from collections import deque

from django.db.models import F
from django.utils import timezone

log = logging.getLogger(__name__)

BLOCK_WINDOW = 300      # 이 초 안에
BLOCK_LIMIT = 3         # 이만큼 차단 조짐이 보이면
PAUSE_SECONDS = 600     # 이만큼 쉰다

#: 걸린 시간의 칸 — 위 끝(초). 마지막 칸(`t9`)은 34 초 너머다. `UpstreamDay.t0`…`t9`
TIME_BUCKETS = (0.5, 1, 2, 3, 5, 8, 13, 21, 34)

#: 화면에서 온 요청이 아닌 프로세스 — `manage.py <명령>` 으로 뜬 대조(`verify_layers`)·미리 데우기(`prewarm`)·받기(`fetch_*`) 따위 (wetherilli 363).
#: 화면은 gunicorn(운영)·`runserver`(개발)로 돌고, 명령은 늘 제 프로세스로 뜨므로 프로세스 하나에 한 번 정한다. 시험은 화면 쪽으로 친다
def _is_batch(argv) -> bool:
    return len(argv) > 1 and str(argv[0]).endswith("manage.py") and argv[1] not in ("runserver", "test")


BATCH = _is_batch(sys.argv)

_lock = threading.Lock()
_recent_blocks = deque()
_paused_until = 0.0


def looks_blocked(status: int, head: bytes = b"") -> bool:
    """차단의 얼굴. 403·429, 그리고 방화벽의 `400 Request Blocked`."""
    if status in (403, 429):
        return True
    return status == 400 and b"Request Blocked" in (head or b"")[:1000]


def paused() -> float:
    """쉬는 중이면 남은 초, 아니면 0."""
    left = _paused_until - time.time()
    return left if left > 0 else 0.0


def seconds_of(elapsed):
    """`requests` 의 `Response.elapsed`(timedelta) 또는 초 → 초. 못 읽으면 None(시험의 Mock 따위)"""
    if elapsed is None:
        return None
    try:
        value = float(elapsed.total_seconds() if hasattr(elapsed, "total_seconds") else elapsed)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value < 86400 else None


def bucket(value: float) -> int:
    for i, top in enumerate(TIME_BUCKETS):
        if value < top:
            return i
    return len(TIME_BUCKETS)


def record(upstream: str, ok: bool, blocked: bool = False, count: int = 1, elapsed=None) -> None:
    global _paused_until
    if blocked:
        now = time.time()
        with _lock:
            _recent_blocks.append(now)
            while _recent_blocks and now - _recent_blocks[0] > BLOCK_WINDOW:
                _recent_blocks.popleft()
            if len(_recent_blocks) >= BLOCK_LIMIT and not paused():
                _paused_until = now + PAUSE_SECONDS
                _recent_blocks.clear()
                log.warning("%s 에서 차단 조짐이 %d 번 — %d 분 동안 묻지 않는다",
                            upstream, BLOCK_LIMIT, PAUSE_SECONDS // 60)
    try:
        from .models import UpstreamDay
        row, _ = UpstreamDay.objects.get_or_create(day=timezone.localdate(), upstream=upstream)
        field = "blocked" if blocked else ("ok" if ok else "fail")
        changes = {field: F(field) + count}
        if BATCH:
            changes["batch"] = F("batch") + count
        took = seconds_of(elapsed)
        if took is not None:
            slot = f"t{bucket(took)}"
            changes.update(timed=F("timed") + 1, seconds=F("seconds") + took, **{slot: F(slot) + 1})
        UpstreamDay.objects.filter(pk=row.pk).update(**changes)
    except Exception as exc:                      # 세는 것은 덤이다
        log.debug("호출을 세지 못했다: %s", exc)


def reset() -> None:
    """시험이 쓴다."""
    global _paused_until
    with _lock:
        _recent_blocks.clear()
        _paused_until = 0.0


# ── 보이기 — `upstream_stats` 와 관리 화면이 함께 쓴다 (wetherilli 290·295) ─────────

BUCKET_FIELDS = [f"t{i}" for i in range(len(TIME_BUCKETS) + 1)]


def p95(counts) -> str:
    """칸마다의 건수 → p95 가 든 칸의 위 끝(`≤3`). 마지막 칸이면 `>34`. 잰 것이 없으면 `—`"""
    total = sum(counts)
    if not total:
        return "—"
    need, run = 0.95 * total, 0
    for i, n in enumerate(counts):
        run += n
        if run >= need:
            return f"≤{TIME_BUCKETS[i]:g}" if i < len(TIME_BUCKETS) else f">{TIME_BUCKETS[-1]:g}"
    return "—"


def mean(seconds, timed) -> str:
    return f"{seconds / timed:.1f}" if timed else "—"


def summary(days: int = 7) -> list:
    """상류마다 오늘과 지난 `days` 일(오늘 포함)의 건수·실패·잰 건수·평균·p95 — 지난 기간의 평균이 느린 차례(잰 것이 없으면 뒤).
    `[{"name", "today": {...}, "span": {...}}]` — 칸은 `count`(성공+실패+차단)·`fail`(실패+차단)·`timed`·`mean`·`p95`·`batch`(그 가운데 명령이 낸 것,
    wetherilli 363). 이름과 수뿐이다"""
    import datetime
    from .models import UpstreamDay
    today = timezone.localdate()
    since = today - datetime.timedelta(days=days - 1)
    out = {}
    for r in UpstreamDay.objects.filter(day__gte=since):
        row = out.setdefault(r.upstream, {"today": [0, 0, 0, 0.0, [0] * len(BUCKET_FIELDS), 0],
                                          "span": [0, 0, 0, 0.0, [0] * len(BUCKET_FIELDS), 0]})
        counts = [getattr(r, f) for f in BUCKET_FIELDS]
        for part in (["today", "span"] if r.day == today else ["span"]):
            agg = row[part]
            agg[0] += r.ok + r.fail + r.blocked
            agg[1] += r.fail + r.blocked
            agg[2] += r.timed
            agg[3] += r.seconds
            agg[4] = [a + b for a, b in zip(agg[4], counts)]
            agg[5] += r.batch

    def shape(agg):
        count, fail, timed, seconds, counts, batch = agg
        return {"count": count, "fail": fail, "timed": timed, "mean": mean(seconds, timed), "p95": p95(counts), "batch": batch,
                "_sort": seconds / timed if timed else -1.0}
    rows = [{"name": name, "today": shape(v["today"]), "span": shape(v["span"])} for name, v in out.items()]
    rows.sort(key=lambda r: (-r["span"]["_sort"], r["name"]))
    return rows

