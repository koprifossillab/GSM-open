"""메타타일 — 느린 상류에서 큰 장 하나를 받아 화면의 칸으로 잘라 담는 공용 길 (wetherilli 282). 문이 아니다.

멕시코 지자기(SGM DatosAbiertos 7, wetherilli 244)는 요청 하나가 줌과 상관없이 10 초 넘게 걸린다 — 그리는 값이 아니라 요청마다 드는 값이다.
같은 네모를 1024 px 한 장으로 받으면 21.6 초라, 512 px 칸 넷을 한 번에 받으면 칸마다 받는 것(넷 × 11 초)의 절반이고, 이웃 칸은 캐시에서 곧 나온다.

- **화면이 부르는 주소와 캐시 열쇠는 그대로다.** 칸의 열쇠는 브라우저가 보낸 WMS 변수의 해시(`views.map_cache_key`)라 이웃 칸의 `bbox` 글자를
  서버가 똑같이 지을 수 없다(OpenLayers 가 쓴 소수 자리). 그래서 잘라 둔 조각은 **우리 열쇠**(레이어·칸 크기·z/x/y)로 담고, 칸 요청이 오면
  `map_cache_key` → 조각 열쇠 차례로 찾는다. 조각으로 낸 칸은 `views.wms` 가 제 열쇠로 **다시 담지 않는다** — 같은 그림을 두 벌 두게 되고,
  다음에 오면 조각 열쇠에서 곧 나온다(잠금 앞에서 찾는다, wetherilli 297)
- 칸의 z/x/y 는 `bbox` 에서 거꾸로 셈한다(OpenLayers 의 격자). 3857 에 더해 극지(3413·3031)·북극 람베르트(3575)·캐나다 람베르트(3978)·대만의
  4326 격자도 안다(`GRIDS`, wetherilli 307). 격자에 맞지 않는 요청은 `None` — 부르는 쪽이 하던 대로 한 칸을 받는다
- **같은 메타타일을 동시에 두 번 받지 않는다** — 워커가 프로세스 여럿이라 캐시 자리 밑의 잠금 파일(`fcntl.flock`)로 막는다. 잠금을 얻은 뒤 조각을
  다시 찾아, 먼저 받은 워커가 담은 것이면 그것을 낸다. 기다림은 `METATILE_LOCK_WAIT` 초까지다 — 넘으면 `Busy` (wetherilli 300)
- 메타타일의 칸 수는 `META` 칸 × `META` 칸 — 큰 장이 `MAX_PX` 를 넘지 않게 칸 크기에서 정한다(512 px 칸이면 2 × 2, 256 px 칸이면 4 × 4)
"""
import fcntl
import io
import logging
import math
import time
from pathlib import Path

from django.conf import settings

from . import tilecache, tilegrid

log = logging.getLogger(__name__)

R = 20037508.342789244
#: 큰 장의 한 변 — 멕시코 지자기는 1024 px 한 장이 21.6 초, 512 px 이 11 초 남짓이다(wetherilli 244)
MAX_PX = 1024
#: 칸의 bbox 가 격자에서 이만큼(칸 한 변의 비율) 어긋나도 같은 칸으로 본다 — 소수 자리 오차
TOLERANCE = 1e-6


class Busy(RuntimeError):
    """같은 메타타일을 받는 다른 요청을 `METATILE_LOCK_WAIT` 초 기다려도 끝나지 않았다 — 바깥 한계(nginx) 안에 답하려고 멈춘다 (wetherilli 300).
    부르는 쪽은 "느리다" 안내 타일을 낸다. 받는 요청은 끝까지 받아 담으므로 다음에 부르면 나온다"""


def slow(exc) -> bool:
    """상류가 늦어서 생긴 오류인가 — 잠금 기다림(`Busy`), 또는 문이 감싼 `requests` 의 시간 초과. 문만 `requests` 를 들이므로 갈래의 이름으로 본다"""
    seen = 0
    while exc is not None and seen < 5:
        if isinstance(exc, Busy) or any(c.__name__ == "Timeout" and c.__module__.startswith("requests") for c in type(exc).__mro__):
            return True
        exc, seen = exc.__cause__ or exc.__context__, seen + 1
    return False


def _acquire(lock, wait: float) -> None:
    """`wait` 초 안에 잠금을 얻지 못하면 `Busy`. 막는 `flock` 에는 한계가 없어 0.2 초마다 되묻는다"""
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise Busy(f"메타타일 잠금을 {wait:g} 초 기다렸다")
            time.sleep(0.2)


def limit(table: dict, name: str):
    """메타타일 표(문마다 둔다 — 레이어 이름 또는 `:` 로 끝나는 앞머리 → 메타타일로 받는 가장 깊은 격자 줌, None 이면 모든 줌)에서
    그 레이어의 줌 끝. 표에 없으면 False (wetherilli 284)"""
    if name in table:
        return table[name]
    for prefix, last in table.items():
        if prefix.endswith(":") and name.startswith(prefix):
            return last
    return False


#: 격자 — 투영 → (원점 x, 원점 y(위), 줌 0 의 칸 한 변, 줌 0 의 칸 수(가로, 세로)). 화면(`map.js`)의 격자를 옮긴 것이다 (wetherilli 307)
#: 3857 은 `createXYZ`, 극지·캐나다·북극 람베르트는 `npolarSource` 의 `createXYZ({extent})`(`tilegrid.EXTENT`), 4326 은 대만의 `TAIWAN_GRID`
#: (줌 0 이 180° 네모 두 장). 스페인 IGME 1:100만도 4326 이지만 줌 0 이 360° 한 장인 격자다 — 같은 칸이 여기서는 줌이 하나 크게 셈해질 뿐 칸은 같다
GRIDS = {
    "EPSG:3857": (-R, R, 2 * R, (1, 1)),
    "EPSG:900913": (-R, R, 2 * R, (1, 1)),
    "EPSG:4326": (-180.0, 90.0, 180.0, (2, 1)),
}
for _crs, (_x0, _y0, _x1, _y1) in tilegrid.EXTENT.items():
    if _crs != "EPSG:4326":
        GRIDS[_crs] = (_x0, _y1, _x1 - _x0, (1, 1))
#: WMS 1.3.0 에서 위도가 먼저인 투영 — 브라우저가 bbox 를 남,서,북,동 으로 적는다
LAT_FIRST = ("EPSG:4326",)


def _lat_first(crs: str, params: dict) -> bool:
    return crs in LAT_FIRST and str(params.get("version") or "1.3.0") != "1.1.1"


def cell(params: dict):
    """WMS 변수 → (투영, z, x, y, 칸 px). 아는 격자의 정사각 칸이 아니면 None (wetherilli 307)"""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in GRIDS:
        return None
    try:
        a, b, c, d = (float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, TypeError, ValueError):
        return None
    w, s, e, n = (b, a, d, c) if _lat_first(crs, params) else (a, b, c, d)
    x0, y0, span0, (cols, rows) = GRIDS[crs]
    span = e - w
    if width != height or width <= 0 or span <= 0 or abs((n - s) - span) > span * TOLERANCE:
        return None
    z = round(math.log2(span0 / span))
    if z < 0 or z > 22 or abs(span0 / 2 ** z - span) > span * TOLERANCE:
        return None
    fx, fy = (w - x0) / span, (y0 - n) / span
    x, y = round(fx), round(fy)
    if abs(fx - x) > 1e-4 or abs(fy - y) > 1e-4 or not (0 <= x < cols * 2 ** z and 0 <= y < rows * 2 ** z):
        return None
    return crs, z, x, y, width


def tile_of(params: dict):
    """WMS 변수 → (z, x, y, 칸 px). 아는 격자의 칸이 아니면 None"""
    got = cell(params)
    return got[1:] if got else None


def meta_size(px: int) -> int:
    """메타타일 한 변의 칸 수"""
    return max(1, MAX_PX // px)


def _tag(crs: str) -> str:
    """열쇠에 넣는 투영 — 3857 은 비워 앞 판의 열쇠를 그대로 둔다. 한 레이어를 투영 둘로 부르는 일이 있어(북극 탭 3413·유럽 3857) 가른다"""
    return "" if crs in ("EPSG:3857", "EPSG:900913") else f"{crs}/"


def piece_key(layer: str, px: int, z: int, x: int, y: int, crs: str = "EPSG:3857") -> str:
    return tilecache.key_text("meta", f"{_tag(crs)}{layer}/{px}/{z}/{x}/{y}")


def stale(layer: str, params: dict):
    """나이가 지난 조각이라도 — 상류가 못 줄 때 빈 자리보다 옛것을 내려고 (`tilecache.get(stale=True)` 의 짝, wetherilli 297)"""
    got = cell(params) if tilecache.enabled() else None
    if got is None:
        return None
    crs, z, x, y, px = got
    return tilecache.get(piece_key(layer, px, z, x, y, crs), stale=True)


def _bbox(z: int, x0: int, y0: int, count: int, crs: str = "EPSG:3857", lat_first: bool = False) -> str:
    gx, gy, span0, _ = GRIDS[crs]
    span = span0 / 2 ** z
    w, n = gx + x0 * span, gy - y0 * span
    s, e = n - span * count, w + span * count
    return ",".join(repr(v) for v in ((s, w, n, e) if lat_first else (w, s, e, n)))


def _lock_path(layer: str, px: int, z: int, mx: int, my: int, crs: str = "EPSG:3857") -> Path:
    root = Path(settings.TILE_CACHE_DIR) / "locks"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{tilecache.key_text('meta-lock', f'{_tag(crs)}{layer}/{px}/{z}/{mx}/{my}')}.lock"


def serve(layer: str, params: dict, fetch, *, max_zoom=None, errors=()):
    """칸 하나의 PNG — 잘라 둔 조각이 있으면 그것, 없으면 메타타일을 받아 잘라 담고 그 칸을 낸다.

    `fetch(bbox, width, height)` 는 큰 장의 (바이트, content-type) 를 주는 문의 함수다. 격자에 맞지 않는 칸, `max_zoom` 보다 깊은 칸이면 None —
    부르는 쪽이 하던 대로 받는다. **큰 장이 `errors` 로 실패하면 None** — 부르는 쪽이 칸 하나로 되받는다(EGDI 처럼 예외가 잦은 상류, wetherilli 284).
    **시간 초과는 되받지 않고 올린다** — 문 한계를 두 번 기다리면 nginx 한계를 넘는다(wetherilli 300). 그 밖의 문의 오류는 그대로 올린다."""
    from PIL import Image

    got = cell(params) if tilecache.enabled() else None     # 담을 곳이 없으면 자를 까닭이 없다
    if got is None:
        return None
    crs, z, x, y, px = got
    if max_zoom is not None and z > max_zoom:
        return None
    key = piece_key(layer, px, z, x, y, crs)
    hit = tilecache.get(key)
    if hit is not None:
        return hit
    count = min(meta_size(px), 2 ** z)
    mx, my = x // count * count, y // count * count
    with open(_lock_path(layer, px, z, mx, my, crs), "w") as lock:
        _acquire(lock, settings.METATILE_LOCK_WAIT)   # 같은 메타타일을 받는 다른 워커를 기다린다 — 한계까지만
        try:
            hit = tilecache.get(key)
            if hit is not None:
                return hit
            try:
                content, _ = fetch(_bbox(z, mx, my, count, crs, _lat_first(crs, params)), px * count, px * count)
            except errors as exc:
                if slow(exc):
                    raise                                 # 늦은 것은 칸 하나로 되받지 않는다 — 한 번 더 기다리면 바깥 한계를 넘는다 (wetherilli 300)
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
                    tilecache.put(piece_key(layer, px, z, mx + i, my + j, crs), png)
                    if (mx + i, my + j) == (x, y):
                        mine = png
            log.info("메타타일 %s z%d (%d,%d) %d×%d 칸을 잘라 담았다", layer, z, mx, my, count, count)
            return mine
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
