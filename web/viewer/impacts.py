"""지구 충돌구와 거대 화성암 지대(LIP) — 오늘의 지구에, LIP 는 그때의 지구에도 (wetherilli 283).

| 판 | 원본 | 조건 | 꼴 |
|---|---|---|---|
| 충돌구 | Wikidata — "충돌구"(Q55818)와 그 아래 갈래 가운데 지구 밖 천체(P376)가 아닌 것, 좌표(P625)·지름(P2386)·생긴 때(P571) | **CC0** | 점 |
| LIP | EarthByte GPlates 2.3 자료의 `IgneousProvinces.zip` — Johansson, Zahirovic & Müller 2018 (GRL doi:10.1029/2017GL076691) 화산 지대 2 526 면 | **CC BY 4.0** (같은 자리 `License.txt`) | 면 |

원본은 NAS `N:\\GSM\\sources\\earth\\impacts\\`(SPARQL 답을 2026-10-05 에 떠 둔 JSON)·`…\\earthbyte\\` 에 두고 `manage.py build_impacts`
가 `data/earth_impacts.json` 으로 굽는다 — 저장소의 파일이라 문이 아니다. Wikidata 를 화면이 부를 때 묻지 않는다.

- **충돌구는 Wikidata 다** — Earth Impact Database(뉴브런즈윅대)는 조건을 적지 않았고, 통계를 낸 두 논문(Osinski 외 2022 ESR·Kenkmann 2021 MAPS)의
  표는 비상업(CC BY-NC-ND·BY-NC)이다. Wikidata 는 CC0 이지만 지름은 3 분의 1, 연대는 열 곳에만 있다 — 그래서 오늘의 레이어로만 둔다
- **LIP 는 그때의 지구에도 옮긴다** — 원본의 판 번호는 EarthByte 모형의 것이라 우리 판 회전(PALEOMAP, `paleo.py`)에는 맞지 않는다. 그래서 면의
  **가운데가 오늘 담기는 PALEOMAP 대륙 조각**(`paleo.plate_at`)을 그 면의 판으로 삼고, 생긴 때(`FROMAGE`)부터 그 판의 회전으로 꼭짓점을 옮긴다 —
  화석 산지(098)와 같은 셈이다. 가운데가 바다 밑이면(해양 고원·해산열) 판이 없어 오늘에만 그린다. **계산이지 관측이 아니다**
- 색은 생긴 때의 기(紀) — 신생대 노랑 … 원생대 분홍(ICS 의 색). 반쯤 비치게
그리는 법을 고치면 `RENDERER` 를 올린다.
"""
import functools
import io
import json
import math
import re
import zipfile

from django.conf import settings

from . import geomap, paleo
from .i18n import msg, t
from .tectonics import simplify

RENDERER = "1"
MAX_ZOOM = 7
CITE_IMPACTS = "Wikidata (CC0) — impact craters on Earth"
CITE_LIPS = "Johansson, Zahirovic & Müller 2018 (GRL) · EarthByte GPlates 2.3 · CC BY 4.0"
LIP_MEMBER = "IgneousProvinces/Johansson_2018/SHP/Johansson_etal_2018_VolcanicProvinces_v2"
#: 생긴 때(Ma, 이상) → (색, 범례 글) — ICS 의 기 색
PERIODS = (
    (0, "#f9f97f", msg("신생대 (66 Ma 안쪽)")), (66, "#7fc64e", msg("백악기")), (145, "#34b2c9", msg("쥐라기")),
    (201, "#812b92", msg("트라이아스기")), (252, "#f04028", msg("페름기")), (299, "#67a599", msg("석탄기")),
    (359, "#cb8c37", msg("데본기·실루리아기")), (444, "#009270", msg("오르도비스기·캄브리아기")), (539, "#f73563", msg("원생대")),
)


def period_of(age: float) -> tuple:
    best = PERIODS[0]
    for row in PERIODS:
        if age >= row[0]:
            best = row
    return best


def _rgb(hexa: str) -> tuple:
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


def legend(kind: str, lang: str = "ko") -> list:
    if kind == "impacts":
        return [{"color": "#c0392b", "name": t(msg("충돌구 — 원의 크기는 지름"), lang)}]
    return [{"color": c, "name": t(label, lang)} for _, c, label in PERIODS]


# ── 굽기 ─────────────────────────────────────────────────────────────

_POINT = re.compile(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


def read_wikidata(path) -> list:
    """SPARQL 답(JSON) → 충돌구 `[{id, name, lon, lat, km, country, ma}]`. 같은 항목이 여러 줄이면 하나로(나라·생긴 때가 여럿이면 첫 것)."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["results"]["bindings"]
    out = {}
    for row in rows:
        qid = row["c"]["value"].rsplit("/", 1)[-1]
        if qid in out:
            continue
        m = _POINT.match(row.get("coord", {}).get("value", ""))
        if not m:
            continue
        km = row.get("diam", {}).get("value")
        age = row.get("age", {}).get("value", "")
        ma = None
        if age.startswith("-"):                          # `-66000000-01-01T00:00:00Z` → 66 Ma
            try:
                ma = round(int(age[1:].split("-")[0]) / 1e6, 3)
            except ValueError:
                ma = None
        name = row.get("cLabel", {}).get("value", "")
        out[qid] = {"id": qid, "name": "" if name == qid else name, "lon": round(float(m.group(1)), 4), "lat": round(float(m.group(2)), 4),
                    "km": float(km) if km else None, "country": row.get("countryLabel", {}).get("value", ""), "ma": ma}
    return sorted(out.values(), key=lambda r: -(r["km"] or 0))


def read_lips(zip_path) -> list:
    """EarthByte `IgneousProvinces.zip` → LIP `[{name, ma, pid, reach, polys}]`. 판(PALEOMAP)은 면의 가운데로 고른다."""
    from . import geo3al
    model = paleo.model()
    zf = zipfile.ZipFile(zip_path)
    shapes = geo3al.read_polygons(zf.read(LIP_MEMBER + ".shp"))
    rows = geo3al.read_dbf(zf.read(LIP_MEMBER + ".dbf"))
    out = []
    for rings, row in zip(shapes, rows):
        if row is None or not rings:
            continue
        polys = []
        for poly in geo3al.group_rings(rings):
            conv = []
            for ring in poly:
                pts = simplify([(x, y) for x, y in ring], 0.01)
                flat, prev = [], None
                for x, y in pts:
                    q = (round(x, 2), round(y, 2))
                    if q != prev:
                        flat += [q[0], q[1]]
                        prev = q
                if len(flat) >= 8:
                    conv.append(flat)
            if conv:
                polys.append(conv)
        if not polys:
            continue
        outer = polys[0][0]
        clon, clat = sum(outer[0::2]) / (len(outer) // 2), sum(outer[1::2]) / (len(outer) // 2)
        plate = model.plate_at(clon, clat) if model else None
        try:
            ma = float(row.get("FROMAGE") or 0)
        except ValueError:
            ma = 0.0
        name = " ".join(str(row.get("NAME") or "").split())
        out.append({"name": name, "ma": round(ma, 1), "pid": plate["pid"] if plate else None,
                    "reach": plate["reach"] if plate else None, "polys": polys})
    return out


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def data():
    try:
        with open(settings.IMPACTS_FILE, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return None
    for item in doc["lips"]:
        xs = [v for p in item["polys"] for v in p[0][0::2]]
        ys = [v for p in item["polys"] for v in p[0][1::2]]
        item["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return doc


def available() -> bool:
    return data() is not None


def _hex(value: str, alpha: int = 255) -> tuple:
    return _rgb(value) + (alpha,)


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


@functools.lru_cache(maxsize=24)
def lips_at(age: float) -> list:
    """`age` Ma 의 지구에 놓인 LIP — `[(item, polys)]`. 0 은 모두 오늘의 자리에, 그 밖은 생긴 것(`ma ≥ age`)만 판의 회전으로 옮긴 자리에.
    판이 없거나(바다 밑) 판이 거기까지 못 가면 뺀다."""
    doc = data() or {"lips": []}
    if age <= 0:
        return [(item, item["polys"]) for item in doc["lips"]]
    model = paleo.model()
    out = []
    for item in doc["lips"]:
        if item["ma"] < age or item["pid"] is None or age > (item["reach"] or 0) + 1e-9:
            continue
        q = model.rotations.rotation(item["pid"], age)
        if q is None:
            continue
        back = paleo._conjugate(model._now(item["pid"]))
        polys = []
        for rings in item["polys"]:
            moved = []
            for flat in rings:
                ring = []
                for i in range(0, len(flat), 2):
                    lon, lat = paleo.turn(q, *paleo.turn(back, flat[i], flat[i + 1]))
                    ring += [lon, lat]
                # 날짜변경선을 넘는 고리는 이어 적는다 — 타일이 ±360 을 따로 본다
                for i in range(2, len(ring), 2):
                    d = ring[i] - ring[i - 2]
                    ring[i] -= 360.0 * round(d / 360.0)
                moved.append(ring)
            polys.append(moved)
        out.append((item, polys))
    return out


def render_tile(layer: str, age: float, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장. 충돌구는 지름의 원, LIP 는 생긴 기의 색으로 반쯤 비치게."""
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    ss = 2
    size = paleo.TILE * ss
    scale = size / span
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    doc = data() or {"impacts": [], "lips": []}
    if layer == "impacts":
        base = (1.6 if z <= 2 else 2.2 if z <= 4 else 3.0) * ss
        for shift in (-360.0, 0.0, 360.0):
            for r in doc["impacts"]:
                cx, cy = (r["lon"] + shift - west) * scale, (north - r["lat"]) * scale
                km = r["km"] or 0
                rad = max(base, km / 111.32 / 2 * scale) if km else base     # 지름이 화면보다 크면 실제 크기로
                if -rad <= cx <= size + rad and -rad <= cy <= size + rad:
                    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(192, 57, 43, 90 if km and rad > base else 200),
                                 outline=(110, 20, 15, 230), width=ss)
    else:
        for shift in (-360.0, 0.0, 360.0):
            tr = (west - shift, north, scale, scale)
            for item, polys in lips_at(age):
                colour = period_of(item["ma"])[1]
                rule = {"fill": _hex(colour, 150), "outline": (60, 40, 30, 170), "width": 1}
                for rings in polys:
                    xs, ys = rings[0][0::2], rings[0][1::2]
                    if max(xs) + shift < west or min(xs) + shift > west + span or max(ys) < north - span or min(ys) > north:
                        continue
                    size_px = max(max(xs) - min(xs), max(ys) - min(ys)) * scale
                    geomap._fill_polygon(image, draw, [list(r) for r in rings], rule, tr, size_px, ss)
    out = image.resize((paleo.TILE, paleo.TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def impact_near(lon: float, lat: float, radius: float):
    """누른 자리에서 `radius`° 안 또는 그 충돌구의 둘레 안의 가장 가까운 충돌구"""
    doc = data()
    if doc is None:
        return None
    cos = max(0.05, math.cos(math.radians(lat)))
    best = None
    for r in doc["impacts"]:
        d = math.hypot((((r["lon"] - lon + 180) % 360) - 180) * cos, r["lat"] - lat)
        reach = max(radius, (r["km"] or 0) / 111.32 / 2)
        if d <= reach and (best is None or d < best[0]):
            best = (d, r)
    return best[1] if best else None


def lip_at(lon: float, lat: float, age: float = 0.0):
    """누른 자리를 담는 LIP(그 연대의 자리로). 여럿이면 젊은 것"""
    hits = []
    for item, polys in lips_at(age):
        for rings in polys:
            for shift in (0.0, -360.0, 360.0):
                if geomap.polygon_contains([list(r) for r in rings], lon + shift, lat):
                    hits.append(item)
                    break
    return min(hits, key=lambda i: i["ma"]) if hits else None
