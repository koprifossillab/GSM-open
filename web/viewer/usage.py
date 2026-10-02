"""상류 호출을 센다 — 그리고 차단 조짐이 보이면 스스로 쉰다.

**한계를 재지 않는다.** KIGAM 은 수치를 밝히지 않고, 재다 넘으면 서버 IP 가
막힌다 — 그러면 타일·범례·속성이 다 멈춘다. 그래서 두 가지만 한다.

1. 날마다 몇 번 물었는지, 차단 조짐이 몇 번 있었는지 센다 (`UpstreamDay`)
2. 차단 조짐이 5 분 안에 3 번 보이면 **10 분 동안 상류에 묻지 않는다.**
   막히기 시작했을 때 계속 두드려 일을 키우지 않으려는 것이다. 그동안은
   캐시가 내주고, 캐시에 없는 자리는 안내 타일이 뜬다

세는 일이 실패해도 **지도는 멈추지 않는다** — 세는 것은 덤이다.
"""
import logging
import threading
import time
from collections import deque

from django.db.models import F
from django.utils import timezone

log = logging.getLogger(__name__)

BLOCK_WINDOW = 300      # 이 초 안에
BLOCK_LIMIT = 3         # 이만큼 차단 조짐이 보이면
PAUSE_SECONDS = 600     # 이만큼 쉰다

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


def record(upstream: str, ok: bool, blocked: bool = False, count: int = 1) -> None:
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
        UpstreamDay.objects.filter(pk=row.pk).update(**{field: F(field) + count})
    except Exception as exc:                      # 세는 것은 덤이다
        log.debug("호출을 세지 못했다: %s", exc)


def reset() -> None:
    """시험이 쓴다."""
    global _paused_until
    with _lock:
        _recent_blocks.clear()
        _paused_until = 0.0
