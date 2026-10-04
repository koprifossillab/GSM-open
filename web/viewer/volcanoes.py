"""홀로세 화산 — GVP 의 화산 1 200 여 개를 경위도 타일에 세모로 찍고, 누른 자리의 화산을 읽는다 (wetherilli 134).

`manage.py fetch_gvp` 가 문(`gvp.py`)으로 받아 적은 `<EARTH_DIR>/gvp_volcanoes.json` 만 읽는다 — 화면이 부를 때 상류를
타지 않는다. 문이 아니다.

- **오늘의 레이어다.** 홀로세(1 만 1 700 년) 화산이라 판을 돌린 옛 지구에는 얹지 않는다 — 화면이 1 Ma 부터 끈다
- 세모의 색은 **마지막 분화**다 — 1900 년부터·1500–1899·서기 1–1499·기원전·모름. 오래된 것을 먼저, 최근 것이 위에
- 1 200 여 개라 sqlite 로 굽지 않는다. 파일을 한 번 읽어 메모리에 둔다(고친 때가 열쇠다)
"""
import functools
import io
import json
import math
from pathlib import Path

from django.conf import settings

from . import arcpoints, paleo
from .i18n import msg, t

FILE = "gvp_volcanoes.json"
#: 갈래 → 파일. 플라이스토세는 따로 받은 파일이다 (wetherilli 194)
FILES = {"holocene": FILE, "pleistocene": "gvp_pleistocene.json"}
RENDERER = "1"
#: 플라이스토세 화산의 세모 — 마지막 분화 열이 없어 한 색이다. 홀로세의 따뜻한 다섯 칸과 갈리게 보라
PLEISTOCENE = ("#8c6bb1", msg("플라이스토세 화산 — 분화 기록이 없다"))

#: 마지막 분화 — (이 해부터, 색, 범례 글). 위가 최근이다. 모르는 것은 `UNKNOWN`
ERAS = (
    (1900, "#d7191c", msg("1900 년부터")),
    (1500, "#f46d43", msg("1500–1899 년")),
    (1, "#fdae61", msg("서기 1–1499 년")),
    (-10 ** 6, "#fee08b", msg("기원전 (홀로세)")),
)
UNKNOWN = ("#bdbdbd", msg("분화 기록이 없다"))


def path(kind: str = "holocene") -> Path:
    return Path(settings.EARTH_DIR) / FILES[kind]


def era(last) -> int:
    """마지막 분화 해 → `ERAS` 의 칸. 모르면 `len(ERAS)`."""
    if last is None:
        return len(ERAS)
    for i, (since, _, _) in enumerate(ERAS):
        if last >= since:
            return i
    return len(ERAS) - 1


def colour(last, kind: str = "holocene") -> tuple:
    if kind == "pleistocene":
        hexa = PLEISTOCENE[0]
    else:
        i = era(last)
        hexa = ERAS[i][1] if i < len(ERAS) else UNKNOWN[0]
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(lang: str = "ko", kind: str = "holocene") -> list:
    """범례 — `[{color, name}]`."""
    if kind == "pleistocene":
        return [{"color": PLEISTOCENE[0], "name": t(PLEISTOCENE[1], lang)}]
    return [{"color": c, "name": t(name, lang)} for _, c, name in ERAS + ((None,) + UNKNOWN,)]


@functools.lru_cache(maxsize=2)
def _load(kind, mtime) -> dict:
    data = json.loads(path(kind).read_text(encoding="utf-8"))
    rows = data.get("volcanoes") or []
    return {"fetched": data.get("fetched", ""), "rows": rows, "by_no": {r["no"]: r for r in rows}}


def data(kind: str = "holocene"):
    """받아 둔 목록. 없으면 None."""
    try:
        return _load(kind, path(kind).stat().st_mtime)
    except (FileNotFoundError, ValueError):
        return None


def available(kind: str = "holocene") -> bool:
    return data(kind) is not None


def fetched(kind: str = "holocene") -> str:
    d = data(kind)
    return d["fetched"] if d else ""


def points(west: float, south: float, east: float, north: float, kind: str = "holocene") -> list:
    """그 네모 안의 화산 행."""
    d = data(kind)
    if d is None:
        return []
    return [r for r in d["rows"] if west <= r["lon"] <= east and south <= r["lat"] <= north]


def render_tile(z: int, x: int, y: int, kind: str = "holocene") -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장에 세모를 찍는다. 오래된·모르는 것을 먼저 — 최근 것이 위에 온다."""
    from PIL import Image, ImageDraw

    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    radius = (2.6 if z <= 1 else 3.4 if z <= 3 else 4.4 if z <= 5 else 5.4) * k
    pad = radius / scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    found = []
    for shift in (-360.0, 0.0, 360.0):
        w, e = west - shift - pad, west + span - shift + pad
        if e < -180 or w > 180:
            continue
        found += [(r["lon"] + shift, r["lat"], r.get("last")) for r in points(w, north - span - pad, e, north + pad, kind)]
    found.sort(key=lambda p: -era(p[2]))
    for lon, lat, last in found:
        cx, cy = (lon - west) * scale, (north - lat) * scale
        draw.polygon([(cx, cy - radius), (cx - radius * 0.95, cy + radius * 0.7), (cx + radius * 0.95, cy + radius * 0.7)],
                     fill=colour(last, kind) + (240,), outline=(30, 20, 20, 230), width=max(1, k // 2))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def near(lon: float, lat: float, radius: float, limit: int = 5, kinds=("holocene",)) -> list:
    """누른 자리에서 `radius`° 안의 화산 — 가까운 것부터. 행에 갈래(`kind`)를 붙인다."""
    cos = max(0.05, math.cos(math.radians(lat)))
    out = []
    for kind in kinds:
        for shift in (-360.0, 0.0, 360.0):
            for r in points(lon + shift - radius / cos, lat - radius, lon + shift + radius / cos, lat + radius, kind):
                d2 = ((r["lon"] - lon - shift) * cos) ** 2 + (r["lat"] - lat) ** 2
                if d2 <= radius * radius:
                    out.append((d2, dict(r, kind=kind)))
    out.sort(key=lambda h: h[0])
    return [r for _, r in out[:limit]]


def year_text(last):
    """마지막 분화 해를 사람이 읽게 — 음수는 기원전. 옮길 수 있는 `msg`."""
    if last is None:
        return ""
    return msg("기원전 {n} 년", n=-last) if last < 0 else msg("{n} 년", n=last)


def search(query: str, limit: int = 5) -> list:
    """`query` 가 이름에 든 화산 (wetherilli 187). 같은 이름 → 앞이 같은 것 → 들어 있는 것 차례."""
    d, q = data(), arcpoints.fold(query)
    if d is None or not q:
        return []
    ranked = []
    for r in d["rows"]:
        name = arcpoints.fold(r["name"])
        if q in name:
            ranked.append((0 if name == q else 1 if name.startswith(q) else 2, len(name), r))
    ranked.sort(key=lambda h: h[:2])
    return [r for _, _, r in ranked[:limit]]
