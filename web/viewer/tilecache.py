"""받아온 타일을 디스크에 둔다. 같은 것을 두 번 받지 않으려는 것이다.

**왜 두는가.** 지질도는 잘 바뀌지 않는다 — 5만 지질도의 도폭은 1977 년에
찍힌 것도 그대로다. 그런데 브라우저가 지도를 조금만 움직여도 타일 요청이
수십 개씩 나간다. 상류에 그만큼 다시 묻는 것은 느리고, 이용제한("지나치게
잦은 호출")에도 가깝다. 한 번 받은 것은 우리가 들고 있으면 된다.

**받은 것은 계속 보탠다.** 2026-09-27 부터 캐시를 스스로 버리지 않는다 —
다음에 같은 자리를 볼 때 상류를 타지 않게 하려는 것이다 (devlog 007).
그래도 **새 것이 이긴다**(CLAUDE.md "받아온 것의 순위") 는 지킨다.

1. 나이(`GSM_TILE_CACHE_MAX_AGE_DAYS`, 기본 3 년)가 지나면 **상류에 다시
   묻고 새 것으로 덮는다.** 상류가 못 주면 그때만 옛것을 낸다 — 빈 타일보다
   묵은 지질도가 낫다
2. 지우지 않는다. 대신 디스크 여유가 `GSM_TILE_CACHE_MIN_FREE_BYTES`
   (기본 5 GB) 밑이면 **더 담지 않는다.** 캐시 때문에 장비가 멈추면 안 된다
3. 받은 그대로만 둔다. 고쳐 쓰거나 다시 내주지 않는다. 속성(`info`)만은
   기하를 떼고 둔다 — 팝업이 쓰지 않는 폴리곤 좌표가 한 응답에 수천 개다

줄이고 싶으면 사람이 `manage.py prune_tiles` 를 부른다. 저절로 돌지 않는다.

**열쇠에 상류 주소를 넣지 않는다.** 개발 스위치를 켜고 받은 타일과 인증키로
받은 타일은 같은 그림이다(뒤에 선 GeoServer 가 하나다). 열쇠를 갈라 두면
키가 나온 날 받아둔 것을 전부 버리게 된다.
"""
import hashlib
import logging
import os
import shutil
import threading
import time
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

#: 열쇠에 넣는 변수. 여기 없는 것은 그림을 바꾸지 않는다고 본다.
#: `key`(인증키)가 빠져 있는 것이 요점이다 — 누가 받았든 같은 그림이다.
KEY_PARAMS = ("layers", "styles", "srs", "crs", "bbox", "width", "height",
              "format", "transparent", "bgcolor", "version", "layer",
              # 속성(`info`) 요청에만 있는 것. 타일 요청에는 없으므로 타일의
              # 열쇠는 바뀌지 않는다 — 받아둔 타일을 버리지 않는다
              "query_layers", "x", "y", "i", "j", "feature_count", "buffer",
              "info_format")

#: 담는 것의 갈래와 파일 끝. 지도·범례는 PNG, 속성은 JSON 이다.
SUFFIXES = (".png", ".json")


def enabled() -> bool:
    return bool(settings.TILE_CACHE_DIR)


def key_for(kind: str, params: dict) -> str:
    """`kind` 는 `map`·`legend`·`info`. 섞지 않으려고 둔다."""
    parts = [kind]
    for name in KEY_PARAMS:
        value = params.get(name)
        if value not in (None, ""):
            parts.append(f"{name}={str(value).strip().lower()}")
    return hashlib.sha256("&".join(parts).encode("utf-8")).hexdigest()


def key_text(kind: str, text: str) -> str:
    """검색어처럼 WMS 변수가 아닌 것의 열쇠. `kind` 로 갈래를 가른다."""
    return hashlib.sha256(f"{kind}&{text.strip().lower()}".encode("utf-8")).hexdigest()


def _path(key: str, suffix: str = ".png") -> Path:
    # 두 자씩 두 번 갈라 담는다. 한 디렉토리에 수십만 개가 쌓이면
    # 디렉토리 읽기 자체가 느려진다.
    root = Path(settings.TILE_CACHE_DIR)
    return root / key[:2] / key[2:4] / f"{key}{suffix}"


def _files():
    for suffix in SUFFIXES:
        yield from Path(settings.TILE_CACHE_DIR).rglob(f"*{suffix}")


def get(key: str, suffix: str = ".png", *, stale: bool = False, max_age: int = None):
    """들고 있으면 바이트를, 없으면 None.

    늙은 것은 평소에 None 이다 — 상류에 다시 물으라는 뜻이다. 상류가 못 줄
    때 `stale=True` 로 다시 부르면 늙은 것도 내준다.

    `max_age`(초)는 늙었다고 볼 나이를 따로 준다. 날마다 바뀌는 자료(암맥
    기록, devlog 026)가 쓴다 — 받은 것을 3 년 들고 있으면 안 된다.
    """
    if not enabled():
        return None
    path = _path(key, suffix)
    try:
        stat = path.stat()
    except OSError:
        return None

    if max_age is None:
        max_age = settings.TILE_CACHE_MAX_AGE_DAYS * 86400
    if not stale and max_age > 0 and (time.time() - stat.st_mtime) > max_age:
        return None                     # 늙었다. 지우지 않는다 — 새 것이 덮는다

    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None

    # 언제 마지막으로 쓰였는지 남긴다. prune 이 이것을 보고 고른다.
    try:
        os.utime(path, (time.time(), stat.st_mtime))
    except OSError:
        pass
    return data


_warned_full = False


def _room_left(root: Path) -> bool:
    """디스크에 더 담아도 되는가. 여유가 한계 밑이면 한 번만 로그를 남긴다."""
    global _warned_full
    floor = settings.TILE_CACHE_MIN_FREE_BYTES
    if floor <= 0:
        return True
    try:
        free = shutil.disk_usage(root if root.exists() else root.parent).free
    except OSError:
        return True
    if free >= floor:
        _warned_full = False
        return True
    if not _warned_full:
        log.warning("디스크 여유가 %d MB 라 캐시에 더 담지 않는다",
                    free // (1024 * 1024))
        _warned_full = True
    return False


def put(key: str, content: bytes, suffix: str = ".png") -> None:
    """디스크가 꽉 차거나 권한이 없어도 **멈추지 않는다** — 캐시는 덤이다."""
    if not enabled() or not content:
        return
    path = _path(key, suffix)
    if not _room_left(Path(settings.TILE_CACHE_DIR)):
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 반쯤 쓰다 만 파일을 읽는 일이 없도록 옆에 쓰고 옮긴다. 임시 이름에 프로세스·스레드를
        # 붙인다 — 워커가 스레드를 두면(034) 같은 타일을 둘이 한꺼번에 쓸 수 있다
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.part")
        tmp.write_bytes(content)
        tmp.replace(path)
    except OSError as exc:
        log.warning("타일을 캐시에 두지 못했다 (%s): %s", key[:12], exc)


def stats() -> dict:
    """`prune_tiles` 와 시험이 쓴다."""
    if not enabled():
        return {"enabled": False, "count": 0, "bytes": 0}
    count = total = 0
    for path in _files():
        try:
            total += path.stat().st_size
            count += 1
        except OSError:
            continue
    return {"enabled": True, "count": count, "bytes": total}


def prune(max_bytes: int = None, max_age_days: int = None) -> dict:
    """늙은 것을 먼저 버리고, 그래도 크면 **오래 안 쓰인 것부터** 버린다.

    지운 뒤의 수와 크기를 돌려준다.
    """
    if not enabled():
        return {"removed_age": 0, "removed_size": 0, "count": 0, "bytes": 0}

    max_bytes = settings.TILE_CACHE_MAX_BYTES if max_bytes is None else max_bytes
    max_age_days = (settings.TILE_CACHE_MAX_AGE_DAYS
                    if max_age_days is None else max_age_days)

    entries, now = [], time.time()
    for path in _files():
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((path, stat.st_size, stat.st_atime, stat.st_mtime))

    removed_age = 0
    if max_age_days > 0:
        limit = max_age_days * 86400
        keep = []
        for entry in entries:
            if (now - entry[3]) > limit:
                _unlink(entry[0])
                removed_age += 1
            else:
                keep.append(entry)
        entries = keep

    total = sum(e[1] for e in entries)
    removed_size = 0
    if max_bytes > 0 and total > max_bytes:
        entries.sort(key=lambda e: e[2])        # 오래 안 쓰인 것이 앞
        for path, size, _, _ in entries:
            if total <= max_bytes:
                break
            _unlink(path)
            total -= size
            removed_size += 1

    after = stats()
    return {"removed_age": removed_age, "removed_size": removed_size,
            "count": after["count"], "bytes": after["bytes"]}


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
