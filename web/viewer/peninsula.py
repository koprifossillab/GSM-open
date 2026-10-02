"""한반도 지질도 — 좌표가 붙은 그림 한 장을 **우리가 잘라 낸다** (devlog 027·028).

026 의 "한반도 지질도 (스캔)" 과 같은 지도를 QGIS 로 뽑은 판이 둘 있다. 상류가 아니라
**우리 디스크의 파일**이라 문이 아니다 — `requests` 가 없다. `geomap.py`·`janmayen.py`
와 같은 자리다.

    판        원본                                    그림            한 화소   레이어
    음영판    Geospatial PDF (NAS KimSunho/geomap!!!!.pdf, 2026-07)    JPEG 9975×17310   59 m   peninsula:shaded
    민판      PNG + 월드파일 (NAS KimSunho/geomap_new_5179.*, 2026-09)  PNG 8865×12403    85 m   peninsula:plain

둘 다 **그림의 격자가 곧 5179(UTM-K) 격자**다 — PDF 의 네 모서리를 5179 로 옮기면
반듯한 사각형이고, 월드파일은 5179 를 적었고 돌림이 없다. 그래서 다시 굽지 않고
**5179 그대로 자르고**, 화면(OpenLayers)이 3857 로 옮겨 그린다. 026 의 카카오 격자와
같은 길이다. 격자는 원점이 왼쪽 위, 256 px, `max_zoom` 이 원본 해상도, 한 줌 내릴
때마다 두 배다.

**원본이 적은 좌표를 그대로 믿지 않는다.** 둘 다 누가 QGIS 에서 손으로 맞춘 꼴이라
OSM 해안선과 대 보면 한쪽으로 몰려 어긋난다.

- 음영판 — 일곱 해안에서 늘 **355 m 북쪽**, 가로로 0.134% 늘어나 있었다. 가로는 한 줄
  (오차 = −1380.9 + 0.001343·x), 세로는 한 값으로 고쳤다. 남는 어긋남 가로 ±70 · 세로 ±120 m (027)
- 민판 — 가로 **0.267%**, 세로 **0.137%** 늘어나 있었다(열 해안, 두 방향 모두 한 줄).
  고친 뒤 남는 어긋남은 RMS 가로 48 · 세로 90 m, 한 곳씩 빼고 맞춰도 ±250 m 안이다 (028)

재는 눈금(한 화소 55~80 m)과 1:100만 원도의 선 굵기(0.2 mm = 200 m) 안이다. 원본이
적은 범위(`stated`)는 **판을 알아보는 데만** 쓰고, 격자는 고친 범위로 짓는다.

억 단위 화소를 요청마다 풀 수는 없어서 **미리 잘라 둔다** (`manage.py build_peninsula`).
서버는 잘라 둔 파일을 내주기만 한다.

**출처를 모른다** — 연구실(KOPRI)이 그린 CorelDRAW 벡터가 원본으로 보이지만 그것이
어느 출판 지도를 따랐는지 모른다 (026 §4). 스캔판처럼 밖에 열지 않는다.
"""
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

#: 잘라 둔 타일의 꼴. WebP 는 투명을 품고 PNG 의 몇 분의 일이다
FORMAT = "webp"
TILE = 256
#: 원본이 적은 모서리가 `stated` 에서 이만큼(m) 넘게 어긋나면 다른 지도로 보고 멈춘다
TOLERANCE = 1.0


@dataclass(frozen=True)
class Sheet:
    """판 하나 — 원본 한 장과 그것을 잘라 둔 5179 격자."""
    name: str               # 레이어 이름
    source: str             # 원본을 찾는 glob (`GSM_PENINSULA_DIR` 안)
    folder: str             # 잘라 둔 것이 드는 폴더 이름
    attribution: str        # 화면이 레이어 곁에 적는 출처
    stated: tuple           # 원본이 적은 범위 (x0, x1, y0, y1) — 판을 알아보는 데만
    extent: tuple           # 해안선에 대 고친 범위 (x0, x1, y0, y1). 고치면 타일을 다시 자른다
    width: int              # 원본 그림의 화소
    height: int
    max_zoom: int           # 원본 해상도. 2^max_zoom × 256 이 긴 변을 넘어 z0 이 한 장이다

    @property
    def res(self) -> float:
        """격자의 해상도는 가로 화소를 따른다. 세로는 자를 때 원본의 세로 화소로 따로 잰다."""
        x0, x1, _, _ = self.extent
        return (x1 - x0) / self.width

    def resolution(self, z: int) -> float:
        return self.res * 2 ** (self.max_zoom - z)

    def grid_size(self, z: int) -> tuple:
        """줌 z 의 (가로, 세로) 장 수."""
        x0, x1, y0, y1 = self.extent
        span = TILE * self.resolution(z)
        return math.ceil((x1 - x0) / span), math.ceil((y1 - y0) / span)

    def valid_tile(self, z: int, x: int, y: int) -> bool:
        if not 0 <= z <= self.max_zoom:
            return False
        cols, rows = self.grid_size(z)
        return 0 <= x < cols and 0 <= y < rows

    def tile_bbox(self, z: int, x: int, y: int) -> tuple:
        """(서, 남, 동, 북) — 5179 미터."""
        x0, _, _, y1 = self.extent
        span = TILE * self.resolution(z)
        west, north = x0 + x * span, y1 - y * span
        return west, north - span, west + span, north

    def grid(self) -> dict:
        """화면에 알릴 격자. 원점은 범위의 왼쪽 위다."""
        x0, x1, y0, y1 = self.extent
        return {"extent": [x0, y0, x1, y1],
                "resolutions": [self.resolution(z) for z in range(self.max_zoom + 1)]}

    # ── 자리 ──

    def tiles_dir(self) -> Path:
        return root() / self.folder

    def available(self) -> bool:
        return self.tiles_dir().is_dir()

    def tile_path(self, z: int, x: int, y: int) -> Path:
        return self.tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}"

    def source_file(self):
        """잘라 낼 원본. 여럿이면 이름이 가장 뒤인 것. 없으면 None."""
        found = sorted(root().glob(self.source)) if root().is_dir() else []
        return found[-1] if found else None

    def read_tile(self, z: int, x: int, y: int):
        """잘라 둔 타일(바이트). 그 자리가 비어 있으면(바다) None."""
        try:
            return self.tile_path(z, x, y).read_bytes()
        except FileNotFoundError:
            return None


SHADED = Sheet(
    name="peninsula:shaded", source="*.pdf", folder="tiles", attribution="KOPRI · QGIS 2026-07",
    stated=(696747.7005, 1283821.5458, 1546278.5933, 2564814.9308),
    extent=(697193.0552, 1283478.5767, 1545923.5933, 2564459.9308),
    width=9975, height=17310, max_zoom=7)

PLAIN = Sheet(
    name="peninsula:plain", source="*.png", folder="tiles-plain", attribution="KOPRI · QGIS 2026-09",
    stated=(615849.8701, 1367461.6497, 1511744.6543, 2563322.8723),
    extent=(616523.9352, 1366131.5376, 1512268.4183, 2562409.5188),
    width=8865, height=12403, max_zoom=6)

SHEETS = {s.name: s for s in (SHADED, PLAIN)}
LAYERS = set(SHEETS)


def root() -> Path:
    return Path(settings.PENINSULA_DIR)


# ── 원본 읽기 — 공간 라이브러리 없이 (geomap.py 머리글과 같은 까닭) ──────────

def read_pdf(data: bytes) -> tuple:
    """Geospatial PDF 에서 (JPEG 바이트, 좌표계 번호, 모서리 위경도 넷) 을 꺼낸다.

    QGIS 가 쓴 꼴만 안다 — 쪽 하나에 `/DCTDecode` 그림 하나, `/Measure` 하나.
    다른 꼴이면 `PeninsulaError`.
    """
    m = re.search(rb"/Subtype\s*/Image(.{0,400}?)>>\s*stream\r?\n", data, re.S)
    if not m or b"/DCTDecode" not in m.group(1):
        raise PeninsulaError("PDF 에 JPEG 그림이 없다")
    start = m.end()
    length = re.search(rb"/Length\s+(\d+)(\s+0\s+R)?", m.group(1))
    if length and length.group(2):
        ref = re.search(rb"\b" + length.group(1) + rb"\s+0\s+obj\s*(\d+)", data)
        size = int(ref.group(1)) if ref else None
    else:
        size = int(length.group(1)) if length else None
    end = start + size if size else data.find(b"endstream", start)
    jpeg = data[start:end]
    if not jpeg.startswith(b"\xff\xd8"):
        raise PeninsulaError("PDF 의 그림이 JPEG 가 아니다")

    epsg = re.search(rb"/EPSG\s+(\d+)", data)
    gpts = re.search(rb"/GPTS\s*\[([^\]]+)\]", data)
    if not epsg or not gpts:
        raise PeninsulaError("PDF 에 좌표(/Measure)가 없다")
    nums = [float(v) for v in gpts.group(1).split()]
    if len(nums) != 8:
        raise PeninsulaError("PDF 의 모서리가 넷이 아니다")
    corners = [(nums[i], nums[i + 1]) for i in range(0, 8, 2)]      # (위도, 경도)
    return jpeg, int(epsg.group(1)), corners


def check_corners(sheet: Sheet, epsg: int, corners) -> None:
    """PDF 의 모서리(위경도)가 판의 `stated` 와 맞는지 본다. 격자는 화면과 약속한 것이라 바꾸지 않는다."""
    from . import crs
    if epsg != 5179:
        raise PeninsulaError(f"좌표계가 5179 가 아니다 ({epsg})")
    _check(sheet, [crs.from_latlon("5179", lat, lon) for lat, lon in corners])


def world_corners(text: str, size: tuple) -> list:
    """월드파일(.pgw) 여섯 줄과 그림 크기로 네 모서리(5179)를 잰다.

    월드파일의 원점은 왼쪽 위 **화소의 가운데**다 — 모서리는 반 화소 바깥이다.
    돌림(둘째·셋째 줄)이 있으면 5179 격자가 아니라 멈춘다."""
    try:
        a, d, b, e, c, f = (float(v) for v in text.split())
    except ValueError:
        raise PeninsulaError("월드파일이 여섯 수가 아니다") from None
    if d or b or a <= 0 or e >= 0:
        raise PeninsulaError("월드파일에 돌림이 있다 — 5179 격자가 아니다")
    w, h = size
    x0, y1 = c - a / 2, f - e / 2
    x1, y0 = x0 + w * a, y1 + h * e
    return [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]


def check_world(sheet: Sheet, text: str, size: tuple) -> None:
    _check(sheet, world_corners(text, size))


def _check(sheet: Sheet, corners) -> None:
    # 모서리 하나하나가 범위의 네 귀 가운데 하나에 붙어야 한다 — 두른 사각형만 보면
    # 한 귀가 안쪽으로 비틀린 것을 놓친다
    x0, x1, y0, y1 = sheet.stated
    want = [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]
    worst = max(min(max(abs(x - wx), abs(y - wy)) for wx, wy in want) for x, y in corners)
    if worst > TOLERANCE:
        raise PeninsulaError(f"원본의 범위가 격자와 {worst:.1f} m 어긋난다 — 다른 판이다")


def open_source(sheet: Sheet, path):
    """원본을 열어 좌표를 확인하고 그림(PIL)을 낸다. PDF 면 속의 JPEG, PNG 면 옆의 `.pgw`."""
    from PIL import Image
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        jpeg, epsg, corners = read_pdf(path.read_bytes())
        check_corners(sheet, epsg, corners)
        image = Image.open(io.BytesIO(jpeg))
    else:
        world = path.with_suffix(".pgw")
        if not world.exists():
            raise PeninsulaError(f"월드파일이 없다 — {world.name}")
        image = Image.open(path)
        check_world(sheet, world.read_text(), image.size)
    if image.size != (sheet.width, sheet.height):
        raise PeninsulaError(f"그림이 {image.size} 다 — {sheet.width}×{sheet.height} 를 기다렸다")
    return image


# ── 자르기 ────────────────────────────────────────────────────────────

#: 이보다 밝고 무채색이면 빈 자리(흰 바탕)로 보고 투명하게 한다
WHITE = 248
GREY = 6


def transparent_white(image):
    """흰 바탕을 투명하게 한 RGBA. JPEG 라 바탕이 255 에서 조금씩 흔들린다."""
    from PIL import ImageChops
    rgb = image.convert("RGB")
    r, g, b = rgb.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)
    bright = low.point(lambda v: 255 if v >= WHITE else 0)
    flat = ImageChops.subtract(high, low).point(lambda v: 255 if v <= GREY else 0)
    alpha = ImageChops.invert(ImageChops.multiply(bright, flat))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def cut(sheet: Sheet, level_image, factor: int, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). `level_image` 는 원본을 `factor` 배 줄인 것이다.
    그림 밖은 투명하다. 다 투명하면 None."""
    from PIL import Image
    x0, _, y0, y1 = sheet.extent
    west, south, east, north = sheet.tile_bbox(z, x, y)
    sx = sheet.res * factor                        # 줄인 그림의 가로 한 화소(m)
    sy = (y1 - y0) / sheet.height * factor
    w, h = level_image.size
    left, top = (west - x0) / sx, (y1 - north) / sy
    right, bottom = (east - x0) / sx, (y1 - south) / sy
    # 그림 밖을 잘라 내고, 남은 조각이 타일의 어디에 앉는지 잰다
    cl, ct, cr, cb = max(left, 0), max(top, 0), min(right, w), min(bottom, h)
    if cr <= cl or cb <= ct:
        return None
    px = TILE / (right - left)
    py = TILE / (bottom - top)
    ox, oy = round((cl - left) * px), round((ct - top) * py)
    ow, oh = round((cr - left) * px) - ox, round((cb - top) * py) - oy
    if ow < 1 or oh < 1:
        return None
    piece = level_image.resize((ow, oh), Image.LANCZOS, box=(cl, ct, cr, cb))
    tile = Image.new("RGBa", (TILE, TILE), (0, 0, 0, 0))
    tile.paste(piece, (ox, oy))
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile


def encode(tile) -> bytes:
    buf = io.BytesIO()
    tile.save(buf, format="WEBP", quality=82, method=4)
    return buf.getvalue()


class PeninsulaError(RuntimeError):
    pass
