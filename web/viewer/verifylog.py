"""레이어 대조(`verify_layers`)의 기록 — `<DB 옆>/verify/<날짜>.json` 에 남기고 지난번과 견준다 (wetherilli 314). 문이 아니다.

- 하루에 한 파일이다. 같은 날 여러 번(상류를 나눠) 돌리면 그날 파일에 레이어마다 덮어 보탠다
- **새로 깨진 것** — 이번에 빈 그림·오류인 레이어 가운데, 그보다 앞선 기록에서 마지막으로 그림이던 것. 상류를 나눠 돌려도 레이어마다 제 앞 기록과 견준다
- 관리 화면은 마지막 파일의 갈래 수와 새로 깨진 수만 보인다 — 레이어 이름과 수뿐이다
"""
import datetime
import json
import os
from collections import Counter
from pathlib import Path

from django.conf import settings

BROKEN = ("빈 그림", "오류")
#: 범례 대조의 기록 이름 앞머리 — `verify_layers --legends` (wetherilli 367)
LEGEND_PREFIX = "legend:"


def root() -> Path:
    return Path(settings.VERIFY_DIR)


def files() -> list:
    """날짜 차례(오래된 것 먼저)의 기록 파일"""
    try:
        return sorted(p for p in root().glob("????-??-??.json"))
    except OSError:
        return []


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"layers": {}}


def record(results: dict, day: datetime.date = None) -> Path:
    """`{레이어: {"upstream", "kind", "note"}}` 를 그날 파일에 보탠다. 옆에 쓰고 옮긴다"""
    day = day or datetime.date.today()
    path = root() / f"{day:%Y-%m-%d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load(path) if path.exists() else {"layers": {}}
    data.setdefault("layers", {}).update(results)
    data["day"] = f"{day:%Y-%m-%d}"
    data["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    tmp = path.with_name(f"{path.name}.{os.getpid()}.part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def diff(paths: list = None) -> dict:
    """마지막 기록과 그 앞의 기록들 — {"day", "previous", "newly": [(레이어, 앞 날짜, 이번 갈래, 기록)], "fixed": [(레이어, 앞 날짜, 앞 갈래)]}"""
    paths = files() if paths is None else paths
    if not paths:
        return {"day": None, "previous": None, "newly": [], "fixed": []}
    latest = load(paths[-1])
    older = [(p.stem, load(p)["layers"]) for p in paths[:-1]]
    newly, fixed, seen = [], [], set()
    for name, now in sorted(latest.get("layers", {}).items()):
        before = next(((day, layers[name]) for day, layers in reversed(older) if name in layers), None)
        if before is None or before[1].get("kind") == "건너뜀":
            continue
        seen.add(before[0])
        was, kind = before[1].get("kind"), now.get("kind")
        if was == "그림" and kind in BROKEN:
            newly.append((name, before[0], kind, now.get("note", "")))
        elif was in BROKEN and kind == "그림":
            fixed.append((name, before[0], was))
    return {"day": paths[-1].stem, "previous": max(seen) if seen else None, "newly": newly, "fixed": fixed}


def summary() -> dict:
    """관리 화면의 한 줄 — 마지막 날짜·갈래 수·새로 깨진 수. 기록이 없으면 None"""
    paths = files()
    if not paths:
        return None
    layers = load(paths[-1]).get("layers", {})
    # 범례 대조(`legend:` 로 시작, wetherilli 367)는 타일의 수에 섞지 않는다 — 새로 깨진 것에는 든다
    counts = Counter(row.get("kind") for name, row in layers.items() if not name.startswith(LEGEND_PREFIX))
    legends = Counter(row.get("kind") for name, row in layers.items() if name.startswith(LEGEND_PREFIX))
    got = diff(paths)
    return {"day": paths[-1].stem, "drawn": counts["그림"], "empty": counts["빈 그림"], "error": counts["오류"],
            "skipped": counts["건너뜀"], "newly": len(got["newly"]), "fixed": len(got["fixed"]),
            "legends": legends["그림"], "legend_broken": legends["빈 그림"] + legends["오류"]}
