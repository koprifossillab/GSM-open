"""오프라인 묶음(`.gsmpack`) — 박스 하나의 타일을 파일 하나로 잇는다 (wetherilli P13·381).

현장(망 없음·키 없음)에서 폰이 `Blob.slice` 로 읽게 라이브러리 없이 단순하게 둔다. 문이 아니다 — 타일은 부르는 쪽이 넘긴다.

```
0      8 B   "GSMPACK1"
8      4 B   머리 길이 N (uint32, little-endian)
12     N B   머리 JSON (UTF-8)
12+N   …     타일 바이트를 잇달아
```

머리의 `tiles` 는 `{"<레이어>/<z>/<x>/<y>": [시작, 길이]}` — 시작은 머리 뒤에서 센다. 열쇠는 화면의 타일 격자(OpenLayers 의
tileCoord, 위에서 아래로 y) 그대로다. 빈 타일은 넣지 않는다. **키는 어디에도 넣지 않는다.**
"""
import json
import struct
from pathlib import Path

MAGIC = b"GSMPACK1"
SUFFIX = ".gsmpack"


def tile_key(layer: str, z: int, x: int, y: int) -> str:
    return f"{layer}/{z}/{x}/{y}"


def write(path, header: dict, tiles) -> dict:
    """`tiles` 는 (열쇠, 바이트)를 차례로 내는 것. 머리의 `tiles` 는 여기서 채운다 — 머리 길이를 알아야 타일을 쓸 수 있어
    타일을 먼저 임시 파일에 잇고 머리를 지은 뒤 붙인다. 돌려주는 것은 쓴 머리."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = path.with_suffix(".body")
    index = {}
    offset = 0
    with open(body, "wb") as out:
        for key, data in tiles:
            if not data or key in index:
                continue
            out.write(data)
            index[key] = [offset, len(data)]
            offset += len(data)
    head = dict(header, tiles=index)
    raw = json.dumps(head, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp = path.with_suffix(".building")
    with open(tmp, "wb") as out, open(body, "rb") as src:
        out.write(MAGIC + struct.pack("<I", len(raw)) + raw)
        while chunk := src.read(1 << 20):
            out.write(chunk)
    body.unlink()
    tmp.replace(path)
    return head


def read_header(path) -> tuple:
    """(머리, 타일 바이트가 시작하는 자리). 꼴이 아니면 ValueError."""
    with open(path, "rb") as f:
        lead = f.read(12)
        if len(lead) < 12 or lead[:8] != MAGIC:
            raise ValueError(f"{path}: GSMPACK1 이 아니다")
        (n,) = struct.unpack("<I", lead[8:12])
        raw = f.read(n)
        if len(raw) < n:
            raise ValueError(f"{path}: 머리가 잘렸다")
    return json.loads(raw.decode("utf-8")), 12 + n


def read_tile(path, key: str, opened=None):
    """열쇠 하나의 바이트. 없으면 None — "그 자리에 그릴 것이 없다". `opened` 는 `read_header` 가 돌려준 것(여럿을 읽을 때)."""
    head, base = opened or read_header(path)
    where = head["tiles"].get(key)
    if where is None:
        return None
    with open(path, "rb") as f:
        f.seek(base + where[0])
        return f.read(where[1])


def listing(folder) -> list:
    """폴더의 묶음 — 이름·크기와 머리의 제목·날짜·범위·레이어. 머리를 읽지 못하는 것은 뺀다. 새것이 앞이다."""
    out = []
    for path in sorted(Path(folder).glob(f"*{SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            head, _ = read_header(path)
        except (OSError, ValueError):
            continue
        out.append({"file": path.name, "bytes": path.stat().st_size, "box": head.get("box", ""),
                    "title": head.get("title", path.stem), "built": head.get("built", ""), "bbox": head.get("bbox"),
                    "tiles": len(head.get("tiles", {})), "layers": list(head.get("layers", {})),
                    "dropped": head.get("dropped", {})})
    return out
