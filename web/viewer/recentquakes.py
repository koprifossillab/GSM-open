"""최근 지진 — USGS 실시간 피드(지난 7 일 M2.5 이상)를 받아 둔 파일에서 (wetherilli 292). 문이 아니다.

`manage.py fetch_recent_quakes`(호스트 cron 의 `hourly.sh`, 한 시간에 한 번)가 `usgs.fetch_recent` 로 `<EARTH_DIR>/quakes_recent.json` 을 쓴다.
화면이 부를 때는 이 파일만 읽는다.

**지난 지진(`quakes.py`, M5 이상 1900 년부터)과 섞이지 않게** — 지난 지진은 속을 채운 원에 **진원 깊이**의 색(빨강·노랑·파랑)이다. 최근 지진은
**속이 빈 고리**에 **얼마나 지났나**의 색(자홍·보라·회청)이다. 이름도 "최근 지진 (7 일)" 로 따로 둔다.
"""
import functools
import io
import json
import math
import time
from pathlib import Path

from django.conf import settings

from . import paleo
from .i18n import msg, t

FILE = "quakes_recent.json"
#: 그리는 법 — 색·크기를 고치면 올린다. 판(`version`)에 든다
RENDERER = "1"
#: 지난 시간 — (시간 미만, 색, 범례 글). 받은 때(`generated`)에서 잰다 — 타일이 그 판에 묶여 한 시간 안에 바뀌지 않는다
AGES = (
    (1, "#ff2d95", msg("지난 한 시간")),
    (24, "#b04fd6", msg("지난 하루")),
    (24 * 8, "#7f8c9a", msg("지난 일주일")),
)


def path() -> Path:
    return Path(settings.EARTH_DIR) / FILE


@functools.lru_cache(maxsize=2)
def _load(mtime):
    data = json.loads(path().read_text(encoding="utf-8"))
    return data.get("generated") or int(mtime * 1000), data.get("quakes") or []


def data():
    """`(받은 때 ms, 지진들)`. 파일이 없으면 None"""
    try:
        return _load(path().stat().st_mtime)
    except (OSError, ValueError):
        return None


def available() -> bool:
    return data() is not None


def generated() -> str:
    d = data()
    return str(d[0]) if d else ""


def age_class(ms, now_ms) -> int:
    hours = max(0.0, (now_ms - (ms or 0)) / 3600000)
    for i, (below, _, _) in enumerate(AGES):
        if hours < below:
            return i
    return len(AGES) - 1


def colour(i: int) -> tuple:
    hexa = AGES[i][1]
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko") -> list:
    return [{"color": c, "name": t(name, lang)} for _, c, name in AGES]


def points(west: float, south: float, east: float, north: float) -> list:
    d = data()
    if d is None:
        return []
    return [q for q in d[1] if west <= q["lon"] <= east and south <= q["lat"] <= north]


def _radius(z: int, mag: float) -> float:
    base = 1.6 if z <= 1 else 2.1 if z <= 3 else 2.8 if z <= 5 else 3.6
    return base * (1 + max(0.0, mag - 2.5) * 0.35)


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자 한 장 — 속이 빈 고리. 오래된 것을 먼저, 최근 것을 위에 그린다"""
    from PIL import Image, ImageDraw

    d = data()
    now = d[0] if d else int(time.time() * 1000)
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    pad = _radius(z, 9.5) * k / scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(q["lon"] + shift, q["lat"], q["mag"], age_class(q["ms"], now))
                  for q in points(w, north - span - pad, e, north + pad)]
    found.sort(key=lambda p: (-p[3], p[2]))
    for lon, lat, mag, age in found:
        cx, cy, rad = (lon - west) * scale, (north - lat) * scale, _radius(z, mag) * k
        width = max(2, int(rad * 0.35))
        draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(20, 20, 20, 170), width=width + 2)
        draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=colour(age) + (235,), width=width)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(lon: float, lat: float, radius: float, limit: int = 5) -> list:
    """누른 자리에서 `radius`° 안의 최근 지진 — 가까운 것부터. 날짜 바뀜선 너머도."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for shift in (-360.0, 0.0, 360.0):
        for q in points(lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius):
            d2 = ((q["lon"] - lon - shift) * cos) ** 2 + (q["lat"] - lat) ** 2
            if d2 <= radius * radius:
                out.append((d2, -q["mag"], q))
    out.sort(key=lambda h: (h[0], h[1]))
    return [q for _, _, q in out[:limit]]


def when(ms) -> str:
    """UTC 의 `YYYY-MM-DD HH:MM`"""
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime((ms or 0) / 1000))
