"""박스 하나를 묶음 하나로 굽는 고리 — 어림·예산 맞추기·받기·자르기·쓰기 (wetherilli 381·384·385, P16 에서 `build_offline_pack` 에서 옮겼다).

타일을 어디서 받을지는 모른다 — 부르는 쪽이 레이어마다 **소스**를 넘긴다. 소스가 가진 것

- `name`·`title`·`attribution`·`type`(타일의 media type)·`tile_size`(256·512)·`kind`(어림 표의 열쇠)
- `grid_zoom(화면 줌)` → 격자 줌, `tiles(bbox, z)` → 칸 `(x, y)` 들
- `cached(z, x, y)` → 이미 가진 바이트(빈 것은 b""), 없으면 None. 상류를 타지 않는다
- `fetch(z, x, y)` → 상류에서 받은 바이트. 못 받으면 `FetchError` — 차단 조짐이면 `blocked=True`
- `calls_for(빠진 장수)` → 상류에 묻는 어림 (고르지 않으면 장수 그대로)

**빠르기는 여기 하나다**(devlog 010) — 상류에 1 초에 한 번, 차단 조짐이면 곧장 멈추고 연달아 3 번 실패해도 멈춘다.
"""
import datetime
import json
import math
import sqlite3
import time
from pathlib import Path

from . import clip, format

#: 캐시에 견줄 것이 모자랄 때의 타일 한 장 어림(바이트) — 소스의 `kind` 마다 `{격자 줌: 바이트}`, 적지 않은 줌은 가장 가까운 줌의 값.
#: **한 장 크기는 줌마다 열 배 넘게 다르다**(5만 지질도는 격자 줌 10 이 226 KB, 15 가 17 KB) — 줌을 가리지 않고 한 값을 쓰면 깊은
#: 줌이 크게 잡혀 받기도 전에 덜린다. 2026-10-21 에 구운 묶음 둘(장성 2026-10-12·한국 2026-10-09)에서 레이어·줌마다 잰 것이다 (wetherilli 404)
GUESS_BYTES = {
    "kigam": {7: 150_000, 10: 158_000, 11: 190_000, 12: 100_000, 13: 58_000, 14: 32_000, 15: 17_000},
    "vworld:Base": {8: 15_000, 10: 15_000, 11: 38_000, 12: 28_000, 13: 21_000, 14: 26_000, 15: 44_000, 16: 26_000},
    "vworld:Satellite": {8: 16_000, 12: 13_000, 14: 12_500, 15: 13_500},
    "vworld:Hybrid": {8: 11_000, 11: 7_000, 12: 5_500, 13: 7_000, 14: 5_000, 15: 4_000},
}
GUESS_OTHER = 40_000           # 표에 없는 소스
MIN_SAMPLES = 20               # 캐시에서 이만큼 있는 줌만 캐시의 평균을 믿는다
NOTE = "연구실 현장용 — 밖으로 나누지 않는다"


class FetchError(Exception):
    """소스가 타일 하나를 받지 못했다. `blocked` 면 차단 조짐이다 — 곧장 멈춘다."""

    def __init__(self, message, blocked=False):
        super().__init__(message)
        self.blocked = blocked


class BakeError(Exception):
    """굽기를 멈췄다. 받은 것은 parts 에 남아 다시 부르면 이어진다."""


class Parts:
    """굽는 동안 받은 것 — 멈췄다 다시 부르면 이어진다. 빈 것도 적어 둔다(다시 묻지 않게)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("CREATE TABLE IF NOT EXISTS tile (k TEXT PRIMARY KEY, v BLOB)")

    def get(self, key):
        row = self.db.execute("SELECT v FROM tile WHERE k = ?", (key,)).fetchone()
        return None if row is None else bytes(row[0])

    def put(self, key, data):
        self.db.execute("INSERT OR REPLACE INTO tile VALUES (?, ?)", (key, data))
        self.db.commit()

    def remove(self):
        self.db.close()
        self.path.unlink(missing_ok=True)


class NoParts:
    """어림만 할 때 — 새로 만들지 않는다."""

    def get(self, key):
        return None

    def put(self, key, data):
        pass

    def remove(self):
        pass


def parts_path(out_dir, box_name) -> Path:
    return Path(out_dir) / f".{box_name}.parts.sqlite"


def guess_bytes(kind, z):
    """표의 어림 — 그 줌이 없으면 가장 가까운 줌(같으면 깊은 쪽)의 값."""
    table = GUESS_BYTES.get(kind)
    if not table:
        return GUESS_OTHER
    near = min(table, key=lambda k: (abs(k - z), -k))
    return table[near]


def fit_budget(order, zooms, sizes, budget):
    """`zooms` {레이어: [처음, 마지막]}(격자 줌)를 예산 안으로 줄인다 — 뒤의 레이어부터 마지막 줌을 한 단계씩.
    `sizes(레이어, 줌)` 은 그 줌의 바이트. 돌려주는 것은 (줄인 zooms, dropped {레이어: 빠진 첫 줌}, 어림 바이트)."""
    zooms = {n: list(z) for n, z in zooms.items()}
    dropped = {}

    def total():
        return sum(sizes(n, z) for n in order for z in range(zooms[n][0], zooms[n][1] + 1))

    for name in reversed(order):
        while total() > budget and zooms[name][1] > zooms[name][0]:
            dropped[name] = zooms[name][1]
            zooms[name][1] -= 1
    return zooms, dropped, total()


class Plan:
    """받기 전의 어림 — 레이어마다 격자 줌·장수·가진 것·한 장 크기, 예산에 맞춘 줌, 상류에 묻는 어림."""

    def __init__(self, box_name, box, sources, rate=1.0):
        self.box_name, self.box = box_name, box
        self.bbox = tuple(box["bbox"])
        self.budget = int(box.get("budget_mb", 200) * 1024 * 1024)
        self.gap = 1.0 / min(max(rate, 0.1), 1.0)
        self.sources = sources
        self.order = list(sources)
        self.zooms = {}
        for name, src in sources.items():
            first, last = box["layers"][name]
            self.zooms[name] = [src.grid_zoom(first), src.grid_zoom(last)]

        # 장수와 이미 가진 것 — 어림의 바탕. 한 장 크기는 줌마다 따로 어림한다(wetherilli 404)
        self.counts, self.have, self.avg = {}, {}, {}
        for name, src in sources.items():
            kind = src.kind if src.kind in GUESS_BYTES else name
            for z in range(self.zooms[name][0], self.zooms[name][1] + 1):
                tiles = src.tiles(self.bbox, z)
                self.counts[(name, z)] = len(tiles)
                seen = []
                for x, y in tiles:
                    data = src.cached(z, x, y)
                    if data is not None:
                        self.have[name] = self.have.get(name, 0) + 1
                        if data:
                            seen.append(len(data))
                self.avg[(name, z)] = (sum(seen) / len(seen)) if len(seen) >= MIN_SAMPLES else guess_bytes(kind, z)

        self.fitted, self.dropped, self.guess = fit_budget(self.order, self.zooms,
                                                           lambda n, z: self.counts[(n, z)] * self.avg[(n, z)], self.budget)
        self.calls = 0
        self.lines = []
        for name in self.order:
            src = sources[name]
            n = sum(self.counts[(name, z)] for z in range(self.fitted[name][0], self.fitted[name][1] + 1))
            missing = n - self.have.get(name, 0)
            self.calls += src.calls_for(missing) if hasattr(src, "calls_for") else missing
            cut = f", 덜어 냄 줌 {self.dropped[name]}–{self.zooms[name][1]}" if name in self.dropped else ""
            mb = sum(self.counts[(name, z)] * self.avg[(name, z)] for z in range(self.fitted[name][0], self.fitted[name][1] + 1))
            self.lines.append(f"  {name:32s} 격자 줌 {self.fitted[name][0]}–{self.fitted[name][1]} ({src.tile_size} px) "
                              f"타일 {n:,} · 캐시 {self.have.get(name, 0):,} · {mb / 1024 / 1024:.1f} MB{cut}")
        self.lines.append(f"어림 {self.guess / 1024 / 1024:.0f} MB / 예산 {self.budget / 1024 / 1024:.0f} MB, "
                          f"상류에 묻기 약 {self.calls:,} 번 ≈ {math.ceil(self.calls * self.gap / 60)} 분")


def bake(plan, out_dir, parts, *, units=None, extra=None, log=print, built=None) -> dict:
    """어림한 대로 받아 `<출력>/<박스>-<날짜>.gsmpack` 하나로 쓴다.

    - `units(bbox, gap)` → `{레이어: (GeoJSON 바이트, 피처 타입들)}` — 누른 자리의 지층 면(wetherilli 384). 예산에서 먼저 뗀다
    - `extra` 는 머리에 더할 것(`{"gsm": 판}` 따위). 키는 넣지 않는다
    - 돌려주는 것은 {path, tiles, asked, fails}. 멈추면 `BakeError` — 받은 것은 parts 에 남는다"""
    bbox, gap, order, sources = plan.bbox, plan.gap, plan.order, plan.sources
    fitted, dropped = plan.fitted, dict(plan.dropped)

    # 받기 — 앞설 차례부터, 줌이 얕은 것부터
    got = {}
    in_a_row = fails = asked = 0
    stop = None
    for name in order:
        src = sources[name]
        for z in range(fitted[name][0], fitted[name][1] + 1):
            for x, y in src.tiles(bbox, z):
                data = src.cached(z, x, y)
                if data is None:
                    started = time.monotonic()
                    asked += 1
                    try:
                        data = src.fetch(z, x, y) or b""
                        in_a_row = 0
                    except FetchError as exc:
                        fails += 1
                        in_a_row += 1
                        if exc.blocked:
                            stop = f"차단 조짐 — 멈춘다: {exc}"
                        elif in_a_row >= 3:
                            stop = f"연달아 3 번 실패 — 멈춘다: {exc}"
                        data = b""
                    time.sleep(max(0.0, gap - (time.monotonic() - started)))
                    if asked % 100 == 0:
                        log(f"  상류에 {asked:,} 번 — {name} 줌 {z}, 실패 {fails}")
                if stop:
                    break
                data = clip.clip_tile(data, z, x, y, bbox) if data else data
                if data and not clip.is_blank(data):
                    got[format.tile_key(name, z, x, y)] = (name, z, data)
            if stop:
                break
        if stop:
            break
    if stop:
        raise BakeError(f"{stop} — 다시 부르면 이어서 받는다")

    # 지층 면(속성)은 예산에서 먼저 뗀다 — 묶음 하나가 예산을 넘지 않게 타일 쪽을 던다 (wetherilli 384)
    gathered = units(bbox, gap) if units else {}
    reserved = sum(len(body) for body, _ in gathered.values())

    # 받은 뒤의 실제 크기로 다시 맞춘다
    actual = {}
    for name, z, data in got.values():
        actual[(name, z)] = actual.get((name, z), 0) + len(data)
    fitted, more, _ = fit_budget(order, fitted, lambda n, z: actual.get((n, z), 0), plan.budget - reserved)
    for name, z in more.items():
        dropped[name] = min(dropped.get(name, z), z)
    keep = {k: v for k, v in got.items() if fitted[v[0]][0] <= v[1] <= fitted[v[0]][1]}

    built = built or datetime.date.today()
    header = {"box": plan.box_name, "title": plan.box["title"], "built": built.isoformat(), **(extra or {}),
              "bbox": list(bbox), "region": plan.box.get("region", ""), "note": NOTE, "dropped": dropped,
              "layers": {name: {"title": sources[name].title, "grid": "EPSG:3857", "tile_size": sources[name].tile_size,
                                "type": sources[name].type, "zooms": fitted[name], "attribution": sources[name].attribution}
                         for name in order if any(v[0] == name for v in keep.values())}}
    if gathered:
        header["units"] = {name: {"key": f"@units/{name}", "types": types, "type": "application/geo+json"}
                           for name, (_, types) in gathered.items()}
    path = Path(out_dir) / f"{plan.box_name}-{built:%Y%m%d}{format.SUFFIX}"
    format.write(path, header, [*((k, v[2]) for k, v in keep.items()),
                                *((f"@units/{name}", body) for name, (body, _) in gathered.items())])
    parts.remove()
    return {"path": path, "tiles": len(keep), "asked": asked, "fails": fails}


def units_body(features) -> bytes:
    """지층 면 목록 → 묶음에 넣을 GeoJSON 바이트."""
    return json.dumps({"type": "FeatureCollection", "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
