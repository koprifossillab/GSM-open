"""해류 — 구워 둔 표층 u·v 텍스처의 자리와 목록, 그리고 굽기 (koprifossillab 014).

문이 아니다. 받는 것은 `ecco.py` 가 하고, 여기는 받은 표층을 PNG 로 굽고 목록을 적는다. 꼴은 바람(`wind.py`)을 따랐다 —
화면의 입자 그리기가 같은 셈을 쓴다.

- **굽기(`bake`)는 호스트에서만 돈다** — numpy 를 쓴다(cron 의 전용 venv). 컨테이너는 자리와 목록만 읽는다
- 한 장 = 한 날(3 일 평균)·표층(5 m). 1440×720, **경도 −180 부터**, 위도 89.875 → −89.875(칸 가운데, 0.25°). 바람의 721 줄과
  한 줄 다르다
- R=u·G=v 를 그 장의 최솟값·최댓값으로 0–255 에, **B 는 바다 가리개**(255 바다·0 육지). 되돌릴 값은 `index.json` 에
- 자리 — `<OCEAN_DIR>/ecco2/<YYYYMMDD>/surface.png`, `<OCEAN_DIR>/ecco2/index.json`

ECCO2 유속 파일의 **경도는 머리에 적힌 것과 다르다** — 머리는 0.125° 부터라 적지만 자료는 107.5° 남짓 밀려 있다. 같은 날의
해수면 온도(경도가 머리와 맞는다)의 육지와 맞춰 `UVEL` 은 430 열, `VVEL` 은 429 열, 둘 다 위도 한 줄 밀린 것을 찾았다 —
유속이 칸 가장자리에 놓인 엇갈린 격자라 반 칸이 갈린다(docs/ECCO2_해류_시각화.md §10). 1996·2006·2012·2018 이 다 같았다.
"""
import io
import json
import os
import re
import shutil
from pathlib import Path

from django.conf import settings

SOURCES = ("ecco2",)
WIDTH, HEIGHT = 1440, 720
STAMP = re.compile(r"^\d{8}$")
#: 유속 파일이 머리보다 밀린 열·줄 — (경도 열, 위도 줄). `np.roll` 에 그대로 준다
SHIFT = {"u": (430, -1), "v": (429, -1)}
#: 남쪽 끝 줄 수 — 남극 안쪽(−89.875·−89.625)인데 쓰레기 값(1e35 까지)이 든다. 통째로 육지로 둔다
JUNK_ROWS = 2
#: 그래도 이보다 빠른 칸은 버린다. 실제 해류는 2 m/s 남짓이 가장 빠르다(2006-06-17 에 1.5 m/s 넘는 칸이 바다의 0.01 %)
MAX_SPEED = 3.0
CREDIT = {"ecco2": "ECCO2 cube92 (NASA JPL·MIT) · Menemenlis et al. 2008"}


def root() -> Path:
    return Path(settings.OCEAN_DIR)


def png_path(source: str, stamp: str) -> Path:
    return root() / source / stamp / "surface.png"


def valid(source: str, stamp: str) -> bool:
    return source in SOURCES and bool(STAMP.match(stamp))


def read_index(source: str) -> dict:
    """출처의 목록. 없거나 깨졌으면 빈 목록."""
    try:
        data = json.loads((root() / source / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("times", [])
    data["source"] = source
    data["credit"] = CREDIT[source]
    return data


def write_index(source: str, times: list) -> None:
    """`times` — `[{"t": 날짜, "u": [최소, 최대], "v": [...]}]`. 날짜 차례로 적는다."""
    path = root() / source / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"source": source, "width": WIDTH, "height": HEIGHT, "depth_m": 5, "days": 3,
            "times": sorted(times, key=lambda e: e["t"])}
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def encode(u_raw: bytes, v_raw: bytes) -> tuple:
    """`ecco.surface` 둘(큰 끝 float32, 남쪽 줄부터, 머리보다 밀린 경도) -> (PNG 바이트, {"u": [최소, 최대], "v": [...]}).
    **호스트에서만** — numpy 를 쓴다."""
    import numpy as np
    from PIL import Image

    fields = {}
    for name, raw in (("u", u_raw), ("v", v_raw)):
        grid = np.frombuffer(raw, dtype=">f4").reshape(HEIGHT, WIDTH).astype(np.float32)
        grid[:JUNK_ROWS] = 0                    # 남극 안쪽 — 쓰레기 값(1e35 까지)이 든다
        cols, rows = SHIFT[name]
        grid = np.roll(np.roll(grid, cols, axis=1), rows, axis=0)
        grid[rows:] = 0 if rows < 0 else grid[rows:]   # 위도를 밀면 남쪽 끝 줄이 북쪽 끝으로 넘어온다 — 지운다
        fields[name] = grid
    u, v = fields["u"], fields["v"]
    bad = ~(np.isfinite(u) & np.isfinite(v)) | (np.abs(u) > MAX_SPEED) | (np.abs(v) > MAX_SPEED)
    u[bad] = 0
    v[bad] = 0
    land = (u == 0) & (v == 0)                 # 육지는 0 으로 온다(FillValue 가 아니다)
    if land.all():
        raise ValueError("바다가 한 칸도 없다")
    # 남쪽 줄부터·경도 0 부터 -> 북쪽 줄부터·경도 −180 부터 (화면이 바람과 같은 셈을 쓰게)
    u, v, land = (np.flipud(np.roll(a, WIDTH // 2, axis=1)) for a in (u, v, land))
    rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    scale = {}
    for i, (name, grid) in enumerate((("u", u), ("v", v))):
        sea = grid[~land]
        lo, hi = float(sea.min()), float(sea.max())
        span = hi - lo or 1.0
        rgb[..., i] = np.rint((np.clip(grid, lo, hi) - lo) / span * 255).astype(np.uint8)
        scale[name] = [round(lo, 4), round(hi, 4)]
    rgb[..., 2] = np.where(land, 0, 255)
    out = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(out, "PNG", optimize=True)
    return out.getvalue(), scale


def write_time(source: str, stamp: str, u_raw: bytes, v_raw: bytes) -> dict:
    """한 날을 굽고 목록 한 줄을 낸다. 옆 자리에 다 쓴 뒤 바꿔 끼운다."""
    png, scale = encode(u_raw, v_raw)
    final = root() / source / stamp
    tmp = root() / source / f"{stamp}.part"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    (tmp / "surface.png").write_bytes(png)
    shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)
    return {"t": stamp, **scale}
