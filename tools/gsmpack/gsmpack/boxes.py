"""박스 표 — `{박스 이름: {title, region, bbox, layers: {레이어: [처음 줌, 마지막 줌]}, units, budget_mb}}`. `_` 로 시작하는 칸은 주석이다."""
import json
from pathlib import Path


def load(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}
