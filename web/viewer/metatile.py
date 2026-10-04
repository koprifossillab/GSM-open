"""메타타일 — 느린 상류에서 큰 장 하나를 받아 화면의 칸으로 잘라 담는 공용 길 (wetherilli 282). 문이 아니다.

멕시코 지자기(SGM DatosAbiertos 7, wetherilli 244)는 요청 하나가 줌과 상관없이 10 초 넘게 걸린다 — 그리는 값이 아니라 요청마다 드는 값이다.
같은 네모를 1024 px 한 장으로 받으면 21.6 초라, 512 px 칸 넷을 한 번에 받으면 칸마다 받는 것(넷 × 11 초)의 절반이고, 이웃 칸은 캐시에서 곧 나온다.

- **화면이 부르는 주소와 캐시 열쇠는 그대로다.** 칸의 열쇠는 브라우저가 보낸 WMS 변수의 해시(`views.map_cache_key`)라 이웃 칸의 `bbox` 글자를
  서버가 똑같이 지을 수 없다(OpenLayers 가 쓴 소수 자리). 그래서 잘라 둔 조각은 **우리 열쇠**(레이어·칸 크기·z/x/y)로 담고, 칸 요청이 오면
  `map_cache_key` → 조각 열쇠 차례로 찾는다. 찾은 조각은 `views.wms` 가 제 열쇠로도 담는다
- 칸의 z/x/y 는 3857 의 `bbox` 에서 거꾸로 셈한다(OpenLayers `createXYZ` 의 격자). 격자에 맞지 않는 요청은 `None` — 부르는 쪽이 하던 대로 한 칸을 받는다
- **같은 메타타일을 동시에 두 번 받지 않는다** — 워커가 프로세스 여럿이라 캐시 자리 밑의 잠금 파일(`fcntl.flock`)로 막는다. 잠금을 얻은 뒤 조각을
  다시 찾아, 먼저 받은 워커가 담은 것이면 그것을 낸다
- 메타타일의 칸 수는 `META` 칸 × `META` 칸 — 큰 장이 `MAX_PX` 를 넘지 않게 칸 크기에서 정한다(512 px 칸이면 2 × 2, 256 px 칸이면 4 × 4)
"""
import fcntl
import io
import logging
import math
from pathlib import Path

from django.conf import settings

from . import tilecache

log = logging.getLogger(__name__)

R = 20037508.342789244
#: 큰 장의 한 변 — 멕시코 지자기는 1024 px 한 장이 21.6 초, 512 px 이 11 초 남짓이다(wetherilli 244)
MAX_PX = 1024
#: 칸의 bbox 가 격자에서 이만큼(칸 한 변의 비율) 어긋나도 같은 칸으로 본다 — 소수 자리 오차
TOLERANCE = 1e-6


def limit(table: dict, name: str):
    """메타타일 표(문마다 둔다 — 레이어 이름 또는 `:` 로 끝나는 앞머리 → 메타타일로 받는 가장 깊은 격자 줌, None 이면 모든 줌)에서
    그 레이어의 줌 끝. 표에 없으면 False (wetherilli 284)"""
    if name in table:
        return table[name]
    for prefix, last in table.items():
        if prefix.endswith(":") and name.startswith(prefix):
            return last
    return False


def tile_of(params: dict):
    """WMS 변수 → (z, x, y, 칸 px). 3857·정사각·격자에 맞는 칸이 아니면 None"""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in ("EPSG:3857", "EPSG:900913"):
        return None
    try:
        w, s, e, n = (float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, TypeError, ValueError):
        return None
    span = e - w
    if width != height or width <= 0 or span <= 0 or abs((n - s) - span) > span * TOLERANCE:
        return None
    z = round(math.log2(2 * R / span))
    if z < 0 or z > 22 or abs(2 * R / 2 ** z - span) > span * TOLERANCE:
        return None
    fx, fy = (w + R) / span, (R - n) / span
    x, y = round(fx), round(fy)
    if abs(fx - x) > 1e-4 or abs(fy - y) > 1e-4 or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return None
    return z, x, y, width


def meta_size(px: int) -> int:
    """메타타일 한 변의 칸 수"""
    return max(1, MAX_PX // px)


def piece_key(layer: str, px: int, z: int, x: int, y: int) -> str:
    return tilecache.key_text("meta", f"{layer}/{px}/{z}/{x}/{y}")


def _bbox(z: int, x0: int, y0: int, count: int) -> str:
    span = 2 * R / 2 ** z
    w, n = -R + x0 * span, R - y0 * span
    return ",".join(repr(v) for v in (w, n - span * count, w + span * count, n))


def _lock_path(layer: str, px: int, z: int, mx: int, my: int) -> Path:
    root = Path(settings.TILE_CACHE_DIR) / "locks"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{tilecache.key_text('meta-lock', f'{layer}/{px}/{z}/{mx}/{my}')}.lock"


def serve(layer: str, params: dict, fetch, *, max_zoom=None, errors=()):
    """칸 하나의 PNG — 잘라 둔 조각이 있으면 그것, 없으면 메타타일을 받아 잘라 담고 그 칸을 낸다.

    `fetch(bbox, width, height)` 는 큰 장의 (바이트, content-type) 를 주는 문의 함수다. 격자에 맞지 않는 칸, `max_zoom` 보다 깊은 칸이면 None —
    부르는 쪽이 하던 대로 받는다. **큰 장이 `errors` 로 실패하면 None** — 부르는 쪽이 칸 하나로 되받는다(EGDI 처럼 예외가 잦은 상류, wetherilli 284).
    그 밖의 문의 오류는 그대로 올린다."""
    from PIL import Image

    tile = tile_of(params) if tilecache.enabled() else None     # 담을 곳이 없으면 자를 까닭이 없다
    if tile is None:
        return None
    z, x, y, px = tile
    if max_zoom is not None and z > max_zoom:
        return None
    key = piece_key(layer, px, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return hit
    count = min(meta_size(px), 2 ** z)
    mx, my = x // count * count, y // count * count
    with open(_lock_path(layer, px, z, mx, my), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)              # 같은 메타타일을 받는 다른 워커를 기다린다
        try:
            hit = tilecache.get(key)
            if hit is not None:
                return hit
            try:
                content, _ = fetch(_bbox(z, mx, my, count), px * count, px * count)
            except errors as exc:
                log.info("메타타일 %s z%d (%d,%d) 을 받지 못해 칸 하나로 되받는다: %s", layer, z, mx, my, exc)
                return None
            big = Image.open(io.BytesIO(content)).convert("RGBA")
            if big.size != (px * count, px * count):
                big = big.resize((px * count, px * count))
            mine = None
            for j in range(count):
                for i in range(count):
                    buf = io.BytesIO()
                    big.crop((i * px, j * px, (i + 1) * px, (j + 1) * px)).save(buf, "PNG")
                    png = buf.getvalue()
                    tilecache.put(piece_key(layer, px, z, mx + i, my + j), png)
                    if (mx + i, my + j) == (x, y):
                        mine = png
            log.info("메타타일 %s z%d (%d,%d) %d×%d 칸을 잘라 담았다", layer, z, mx, my, count, count)
            return mine
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
