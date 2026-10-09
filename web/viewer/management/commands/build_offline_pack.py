"""박스 하나의 타일을 오프라인 묶음(`.gsmpack`) 하나로 굽는다 (wetherilli P13·381).

    manage.py build_offline_pack jangseong --dry-run      # 장수·크기 어림, 예산에 맞춰 덜 줌
    manage.py build_offline_pack jangseong                # <DB 옆>/offline/jangseong-20261010.gsmpack

박스는 `data/offline_boxes.json` — 경위도 범위와 레이어마다 `[처음 줌, 마지막 줌]`(화면 줌). 적은 차례가 앞설 차례다.

- **받는 것은 화면이 부르는 것과 한 글자까지 같다** — KIGAM 은 `prewarm.plan_for` 의 계획(3857, 512 px WMS)을 빌려 캐시 열쇠가 같다.
  캐시에 있으면 그것을 쓰고, 없으면 문으로 받아 캐시에 담는다(큰 그림 한 장을 잘라 — `prewarm --meta 4` 와 같다)
- VWorld 배경은 `vworld.get_wmts_tile` 로 받는다 — 키는 문 안에서만이고, 지금처럼 서버 캐시에 담지 않는다(033). 굽다 멈췄을 때 다시
  받지 않게 받은 것을 `<출력>/.<박스>.parts.sqlite` 에 두었다가 다 구우면 지운다
- **빠르기는 미리 데우기와 같다**(devlog 010) — 상류에 1 초에 한 번, 차단 조짐이면 곧장 멈춘다. 연달아 3 번 실패해도 멈춘다
- **예산(`budget_mb`, 기본 200 MB)을 넘으면 뒤의 레이어부터 마지막 줌을 한 단계씩 내린다** — 받기 전에는 어림(캐시에 있는 타일의
  평균, 없으면 `GUESS_BYTES`)으로, 받은 뒤에는 실제 크기로. 덜어 낸 것은 머리의 `dropped` 에 레이어마다 빠진 첫 줌으로 적는다
- 묶음의 타일 열쇠는 **화면의 tileCoord** — KIGAM 은 512 px 격자라 화면 줌보다 하나 작고, VWorld 는 256 px 라 화면 줌 그대로다.
  머리의 `layers.<이름>.zooms` 는 그 격자의 줌이고 `tile_size` 가 격자를 밝힌다
- 빈 타일(투명 한 장, VWorld 의 자료 밖)은 넣지 않는다. **키는 머리에도 주소에도 없다**
"""
import datetime
import io
import json
import math
import sqlite3
import time
from pathlib import Path

from PIL import Image

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from gsmweb.version import VERSION
from viewer import kigam, offlinepack, tilecache, tilegrid, usage, vworld
from viewer.management.commands.prewarm import PREWARM_ERRORS, WmsPlan, plan_for
from viewer.models import Layer

#: 캐시에 견줄 것이 없을 때의 타일 한 장 어림(바이트). 2026-10-09 운영 캐시의 장성 둘레에서 잰 값에 가깝게 둔다
GUESS_BYTES = {"kigam": 60_000, "vworld:Base": 18_000, "vworld:Satellite": 22_000, "vworld": 18_000}
META = 4                       # KIGAM 큰 그림 한 변의 타일 수 — `prewarm --meta 4`
VWORLD_ATTRIBUTION = "VWorld (국토교통부 공간정보 오픈플랫폼)"
KIGAM_ATTRIBUTION = "한국지질자원연구원 지오빅데이터 오픈플랫폼"


def load_boxes(path=None) -> dict:
    data = json.loads(Path(path or settings.OFFLINE_BOXES_FILE).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def is_blank(data: bytes) -> bool:
    """투명 한 장인가. 읽지 못하면 빈 것이 아니다 — 넣어 둔다."""
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            alpha = image.convert("RGBA").getchannel("A")
            return alpha.getextrema()[1] == 0
    except (OSError, ValueError):
        pass
    return False


class KigamSource:
    """KIGAM WMS — 화면의 `wmsSource`(3857, `createXYZ({tileSize: 512})`). 화면 줌 s 는 격자 줌 s − 1 이다."""
    tile_size = 512
    remote = True

    def __init__(self, name, title):
        self.name, self.title = name, title
        self.plan = plan_for(name, "kigam")
        if not isinstance(self.plan, WmsPlan):
            raise CommandError(f"{name} 은 타일 레이어가 아니다")
        self.attribution = KIGAM_ATTRIBUTION
        self.kind = "kigam"
        self.type = "image/png"

    def grid_zoom(self, screen):
        return max(0, screen - 1)

    def tiles(self, bbox, z):
        return [(x, y) for _, x, y in tilegrid.tiles_for(bbox, z)]

    def cached(self, z, x, y):
        return tilecache.get(self.plan.key(z, x, y))

    def fetch(self, z, x, y):
        """그 타일을 품은 큰 그림 한 장을 받아 잘라 캐시에 담고, 이 타일을 돌려준다. 상류에 한 번."""
        self.plan.fetch_block(z, x // META, y // META, META)
        return self.cached(z, x, y)


class VWorldSource:
    """VWorld 배경 — 화면의 `vworldSource`(256 px XYZ). 격자 줌이 화면 줌이다. 서버 캐시에 담지 않는다(033)."""
    tile_size = 256
    remote = True

    def __init__(self, name, layer, parts):
        if layer not in vworld.WMTS_LAYERS:
            raise CommandError(f"VWorld 배경에 {layer} 가 없다 — {', '.join(vworld.WMTS_LAYERS)}")
        self.name, self.layer, self.parts = name, layer, parts
        self.title = f"VWorld {layer}"
        self.attribution = VWORLD_ATTRIBUTION
        self.kind = name
        self.type = "image/jpeg" if vworld.WMTS_LAYERS[layer] == "jpeg" else "image/png"

    def grid_zoom(self, screen):
        return screen

    def tiles(self, bbox, z):
        return [(x, y) for _, x, y in tilegrid.tiles_for(bbox, z)]     # 칸 수(2^z)로 세므로 256 px 에도 맞는다

    def cached(self, z, x, y):
        return self.parts.get(offlinepack.tile_key(self.name, z, x, y))

    def fetch(self, z, x, y):
        got = vworld.get_wmts_tile(self.layer, z, y, x)
        data = got[0] if got else b""
        self.parts.put(offlinepack.tile_key(self.name, z, x, y), data)
        return data


class Parts:
    """굽는 동안 받은 VWorld 타일 — 멈췄다 다시 부르면 이어진다. 빈 것도 적어 둔다(다시 묻지 않게)."""

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


class Command(BaseCommand):
    help = "박스 하나의 타일을 오프라인 묶음(.gsmpack)으로 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("box", help="data/offline_boxes.json 의 박스 이름")
        parser.add_argument("--dry-run", action="store_true", help="받지 않고 장수·크기만 어림한다")
        parser.add_argument("--out", help=f"출력 폴더 (기본 {settings.OFFLINE_DIR})")
        parser.add_argument("--rate", type=float, default=1.0, help="1 초에 몇 번 묻나 (최대 1)")

    def handle(self, *args, **o):
        boxes = load_boxes()
        if o["box"] not in boxes:
            raise CommandError(f"박스가 없다: {o['box']} — {', '.join(boxes)}")
        box = boxes[o["box"]]
        bbox = tuple(box["bbox"])
        out_dir = Path(o["out"] or settings.OFFLINE_DIR)
        budget = int(box.get("budget_mb", 200) * 1024 * 1024)
        gap = 1.0 / min(max(o["rate"], 0.1), 1.0)
        parts = Parts(out_dir / f".{o['box']}.parts.sqlite") if not o["dry_run"] else _NoParts()

        titles = dict(Layer.objects.filter(upstream="kigam").values_list("name", "title"))
        enabled = set(Layer.objects.filter(upstream="kigam", enabled=True).values_list("name", flat=True))
        sources, zooms, skipped = {}, {}, []
        for name, (first, last) in box["layers"].items():
            if name.startswith("vworld:"):
                src = VWorldSource(name, name.split(":", 1)[1], parts)
            elif name in enabled and isinstance(plan_for(name, "kigam"), WmsPlan):
                src = KigamSource(name, titles.get(name) or name)
            else:
                skipped.append(name)
                continue
            sources[name] = src
            zooms[name] = [src.grid_zoom(first), src.grid_zoom(last)]
        if skipped:
            self.stderr.write(f"건너뛴다(카탈로그에 없거나 꺼졌거나 타일이 아니다): {', '.join(skipped)}")
        order = list(sources)

        # 장수와 캐시에 있는 것 — 어림의 바탕
        counts, have, avg = {}, {}, {}
        for name, src in sources.items():
            seen = []
            for z in range(zooms[name][0], zooms[name][1] + 1):
                tiles = src.tiles(bbox, z)
                counts[(name, z)] = len(tiles)
                for x, y in tiles:
                    data = src.cached(z, x, y)
                    if data is not None:
                        have[name] = have.get(name, 0) + 1
                        if data:
                            seen.append(len(data))
            avg[name] = (sum(seen) / len(seen)) if len(seen) >= 20 else GUESS_BYTES.get(name, GUESS_BYTES.get(src.kind, 40_000))

        fitted, dropped, guess = fit_budget(order, zooms, lambda n, z: counts[(n, z)] * avg[n], budget)
        calls = 0
        for name in order:
            src = sources[name]
            n = sum(counts[(name, z)] for z in range(fitted[name][0], fitted[name][1] + 1))
            missing = n - have.get(name, 0)
            calls += math.ceil(missing / (META * META) * 1.5) if isinstance(src, KigamSource) else missing
            cut = f", 덜어 냄 줌 {dropped[name]}–{zooms[name][1]}" if name in dropped else ""
            self.stdout.write(f"  {name:32s} 격자 줌 {fitted[name][0]}–{fitted[name][1]} ({src.tile_size} px) "
                              f"타일 {n:,} · 캐시 {have.get(name, 0):,} · 한 장 {avg[name] / 1024:.0f} KB{cut}")
        self.stdout.write(f"어림 {guess / 1024 / 1024:.0f} MB / 예산 {budget / 1024 / 1024:.0f} MB, "
                          f"상류에 묻기 약 {calls:,} 번 ≈ {math.ceil(calls * gap / 60)} 분")
        if o["dry_run"]:
            return
        if any(isinstance(s, KigamSource) for s in sources.values()) and not kigam.has_key():
            raise CommandError("KIGAM 인증키가 없다")

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
                        except (*PREWARM_ERRORS, vworld.VWorldError) as exc:
                            fails += 1
                            in_a_row += 1
                            if usage.paused() or "차단" in str(exc):
                                stop = f"차단 조짐 — 멈춘다: {exc}"
                            elif in_a_row >= 3:
                                stop = f"연달아 3 번 실패 — 멈춘다: {exc}"
                            data = b""
                        time.sleep(max(0.0, gap - (time.monotonic() - started)))
                        if asked % 100 == 0:
                            self.stdout.write(f"  상류에 {asked:,} 번 — {name} 줌 {z}, 실패 {fails}")
                    if stop:
                        break
                    if data and not is_blank(data):
                        got[offlinepack.tile_key(name, z, x, y)] = (name, z, data)
                if stop:
                    break
            if stop:
                break
        if stop:
            raise CommandError(f"{stop} — 다시 부르면 이어서 받는다")

        # 받은 뒤의 실제 크기로 다시 맞춘다
        actual = {}
        for name, z, data in got.values():
            actual[(name, z)] = actual.get((name, z), 0) + len(data)
        fitted, more, size = fit_budget(order, fitted, lambda n, z: actual.get((n, z), 0), budget)
        for name, z in more.items():
            dropped[name] = min(dropped.get(name, z), z)
        keep = {k: v for k, v in got.items() if fitted[v[0]][0] <= v[1] <= fitted[v[0]][1]}

        built = datetime.date.today()
        header = {
            "box": o["box"], "title": box["title"], "built": built.isoformat(), "gsm": VERSION,
            "bbox": list(bbox), "region": box.get("region", ""),
            "note": "연구실 현장용 — 밖으로 나누지 않는다",
            "dropped": dropped,
            "layers": {name: {"title": sources[name].title, "grid": "EPSG:3857", "tile_size": sources[name].tile_size,
                              "type": sources[name].type, "zooms": fitted[name],
                              "attribution": sources[name].attribution}
                       for name in order if any(v[0] == name for v in keep.values())},
        }
        path = out_dir / f"{o['box']}-{built:%Y%m%d}{offlinepack.SUFFIX}"
        offlinepack.write(path, header, ((k, v[2]) for k, v in keep.items()))
        parts.remove()
        self.stdout.write(self.style.SUCCESS(
            f"{path} — 타일 {len(keep):,} 장, {path.stat().st_size / 1024 / 1024:.1f} MB, 상류에 {asked:,} 번, 실패 {fails}"))


class _NoParts:
    """어림만 할 때 — 받은 VWorld 가 있으면 읽되 새로 만들지 않는다."""

    def get(self, key):
        return None

    def remove(self):
        pass
