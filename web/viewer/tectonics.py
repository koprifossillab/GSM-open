"""판 경계와 세계 지질구 — Hasterok 외 2022 를 오늘의 지구에 긋고 칠한다 (wetherilli 272).

원본은 Zenodo 5093930 "New maps of global geologic provinces and tectonic plates"(Hasterok, Halpin, Hand, Collins, Kreemer, Gard, Glorie 2022,
Earth-Science Reviews doi:10.1016/j.earscirev.2022.104069) — **CC BY 4.0**. 묶음은 1.2 GB(지구물리 격자·QGIS 판 포함)라 통째로 받지 않고
zip 의 목차를 Range 로 읽어 `plates&provinces/` 의 셰이프만 떼어 NAS `N:\\GSM\\sources\\earth\\hasterok2022\\` 에 두었다.
`manage.py build_tectonics <폴더>` 가 `data/earth_tectonics.json` 으로 굽는다 — 저장소의 파일이라 문이 아니다.

- **판 경계**(`boundaries`, 557 줄) — 갈래(`type`) 일곱: 확장 중심·확장대·섭입대·충상·좌수향·우수향 변환·추정. `level` 1 은 큰 판의
  경계라 굵게
- **세계 지질구**(`global_gprv`, 920 면) — 갈래(`prov_type`) 열여섯을 저자의 QGIS 판(`gprv_types.qml`)의 색으로, 반쯤 비치게 칠한다.
  누르면 이름·갈래·묶음·마지막 조산 운동·지각 갈래
- 0.01° 로 반올림하고 0.01° 안쪽의 꺾임은 덜어 낸다(Douglas–Peucker) — 1:1000 만 급 지도라 보이는 차이가 없다
- **오늘의 지구다.** 판 회전(`paleo.py`, PALEOMAP)과 섞지 않는다 — 판 나눔이 다른 모형이다
그리는 법을 고치면 `RENDERER` 를 올린다.
"""
import functools
import io
import json
import math

from django.conf import settings

from . import geomap, paleo
from .i18n import msg, t

RENDERER = "1"
MAX_ZOOM = 7
TOLERANCE = 0.01
#: 판 경계 갈래 → (색, 범례 글, 점선)
BOUNDARY_TYPES = {
    "spreading center": ("#e41a1c", msg("확장 중심 (해령)"), None),
    "extensional zone": ("#ff8c1a", msg("확장대·열곡"), None),
    "subduction zone": ("#1f5fbf", msg("섭입대"), None),
    "thrust": ("#9b30d9", msg("충상 (대륙 충돌)"), None),
    "sinistral transform": ("#1a9e4b", msg("좌수향 변환 단층"), None),
    "dextral transform": ("#5ccf5c", msg("우수향 변환 단층"), None),
    "inferred": ("#7a7a7a", msg("추정 경계"), (6, 5)),
}
#: 지질구 갈래 → (색 — 저자의 `gprv_types.qml`, 범례 글)
PROVINCE_TYPES = {
    "craton": ("#4b2bff", msg("강괴 (크라톤)")),
    "shield": ("#b39bd5", msg("순상지")),
    "passive margin": ("#65fff5", msg("수동형 대륙 연변")),
    "accretionary complex": ("#1f78b4", msg("부가 복합체")),
    "basin": ("#fdbf6f", msg("분지")),
    "foredeep basin": ("#a47158", msg("전면 분지")),
    "orogenic belt": ("#9feb58", msg("조산대")),
    "narrow rift": ("#fff939", msg("좁은 열곡")),
    "wide rift": ("#e5b636", msg("넓은 열곡")),
    "volcanic arc": ("#c43c39", msg("화산호")),
    "back-arc basin": ("#fb9a99", msg("배호 분지")),
    "ophiolite complex": ("#205712", msg("오피올라이트 복합체")),
    "magmatic province": ("#af0075", msg("거대 화성 구역")),
    "oceanic plateau": ("#232323", msg("해양 고원")),
    "oceanic back-arc basin": ("#7d8b8f", msg("해양 배호 분지")),
    "oceanic crust": ("#cee1ff", msg("해양 지각")),
}
CRUST = {"continental": msg("대륙 지각"), "transitional": msg("전이 지각"), "oceanic": msg("해양 지각")}
CITE = "Hasterok et al. 2022, Earth-Science Reviews · Zenodo 5093930 · CC BY 4.0"


# ── 굽기 ─────────────────────────────────────────────────────────────

def simplify(points, tol: float = TOLERANCE) -> list:
    """Douglas–Peucker(되풀이) — [(x, y)] → 끝점을 지키며 `tol` 안쪽의 꺾임을 덜어 낸다."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, at = -1.0, None
        for i in range(a + 1, b):
            x, y = points[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > best:
                best, at = d, i
        if at is not None and best > tol:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(points, keep) if k]


def _flat(points, closed: bool) -> list:
    pts = simplify(points)
    if closed and len(pts) < 4:
        return []
    out, prev = [], None
    for x, y in pts:
        p = (round(x, 2), round(y, 2))
        if p != prev:
            out += [p[0], p[1]]
            prev = p
    return out if len(out) >= (8 if closed else 4) else []


def build(folder) -> dict:
    """셰이프 둘(`global_gprv`·`boundaries`) → `{"provinces": […], "boundaries": […]}`"""
    from pathlib import Path

    from . import geo3al
    from .moonmap import _read_lines
    d = Path(folder)
    provinces = []
    shapes = geo3al.read_polygons((d / "global_gprv.shp").read_bytes())
    rows = geo3al.read_dbf((d / "global_gprv.dbf").read_bytes())
    for rings, row in zip(shapes, rows):
        if row is None or not rings:
            continue
        polys = []
        for poly in geo3al.group_rings(rings):
            conv = [r for r in (_flat(ring, True) for ring in poly) if r]
            if conv:
                polys.append(conv)
        if not polys:
            continue
        g = lambda k: str(row.get(k) or "").strip()          # noqa: E731
        provinces.append({"name": g("prov_name"), "type": g("prov_type"), "group": g("prov_group"), "orogen": g("lastorogen"),
                          "continent": g("continent"), "crust": g("crust_type"), "polys": polys})
    boundaries = []
    lines = _read_lines((d / "boundaries.shp").read_bytes())
    lrows = geo3al.read_dbf((d / "boundaries.dbf").read_bytes())
    for parts, row in zip(lines, lrows):
        if row is None or not parts:
            continue
        flat = [f for f in (_flat(p, False) for p in parts) if f]
        if not flat:
            continue
        boundaries.append({"type": str(row.get("type") or "").strip(), "level": int(row.get("level") or 2),
                           "plates": " / ".join(x for x in (str(row.get("plate1") or "").strip(),
                                                            str(row.get("plate2") or "").strip()) if x),
                           "comment": str(row.get("comment") or "").strip(), "parts": flat})
    return {"provinces": provinces, "boundaries": boundaries}


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def data():
    """`data/earth_tectonics.json` 에 겉네모를 붙여 둔 것. 파일이 없으면 None."""
    try:
        with open(settings.TECTONICS_FILE, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return None
    for item in doc["provinces"]:
        xs = [v for p in item["polys"] for v in p[0][0::2]]
        ys = [v for p in item["polys"] for v in p[0][1::2]]
        item["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    for item in doc["boundaries"]:
        xs = [v for p in item["parts"] for v in p[0::2]]
        ys = [v for p in item["parts"] for v in p[1::2]]
        item["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return doc


def available() -> bool:
    return data() is not None


def _hex(value: str, alpha: int = 255) -> tuple:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), alpha


def legend(layer: str, lang: str = "ko") -> list:
    if layer == "boundaries":
        return [{"color": c, "name": t(label, lang), "dash": bool(dash)} for c, label, dash in BOUNDARY_TYPES.values()]
    return [{"color": c, "name": t(label, lang)} for c, label in PROVINCE_TYPES.values()]


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장 — 지질구는 반쯤 비치게 칠하고, 판 경계는 갈래의 색으로 긋는다."""
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    ss = 2
    size = paleo.TILE * ss
    scale = size / span
    tr = (west, north, scale, scale)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    doc = data() or {"provinces": [], "boundaries": []}
    pad = 4 * ss / scale

    def touches(b):
        return not (b[2] < west - pad or b[0] > west + span + pad or b[3] < north - span - pad or b[1] > north + pad)

    if layer == "provinces":
        outline = (40, 40, 40, 150) if z >= 2 else (40, 40, 40, 90)
        for item in doc["provinces"]:
            if not touches(item["bbox"]):
                continue
            colour = PROVINCE_TYPES.get(item["type"], ("#bdbdbd", None))[0]
            rule = {"fill": _hex(colour, 140), "outline": outline, "width": 1}
            size_px = max(item["bbox"][2] - item["bbox"][0], item["bbox"][3] - item["bbox"][1]) * scale
            for rings in item["polys"]:
                geomap._fill_polygon(image, draw, [list(r) for r in rings], rule, tr, size_px, ss)
    else:
        order = list(BOUNDARY_TYPES)
        for item in sorted(doc["boundaries"], key=lambda b: (-b["level"], order.index(b["type"]) if b["type"] in order else 99)):
            if not touches(item["bbox"]):
                continue
            colour, _, dash = BOUNDARY_TYPES.get(item["type"], ("#555555", None, None))
            width = (2.4 if item["level"] == 1 else 1.4) * (1.0 if z <= 2 else 1.3)
            strokes = [{"color": _hex(colour), "width": width, "dash": list(dash) if dash else None}]
            for flat in item["parts"]:
                for run in geomap._clip_runs(geomap._to_px(list(flat), tr, 10 ** 6), size, size, 8 * ss):
                    geomap._stroke(draw, run, strokes, ss)
    out = image.resize((paleo.TILE, paleo.TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def province_at(lon: float, lat: float, lang: str = "ko"):
    """누른 자리의 지질구 — `{"name", "rows": [[이름, 값]…]}`. 없으면 None. 겹치면 작은 것이 이긴다"""
    doc = data()
    if doc is None:
        return None
    lon = ((lon + 180.0) % 360.0) - 180.0
    hits = []
    for item in doc["provinces"]:
        b = item["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
            if any(geomap.polygon_contains([list(r) for r in rings], lon, lat) for rings in item["polys"]):
                hits.append(((b[2] - b[0]) * (b[3] - b[1]), item))
    if not hits:
        return None
    item = min(hits, key=lambda h: h[0])[1]
    kind = PROVINCE_TYPES.get(item["type"])
    rows = [("갈래", t(kind[1], lang) if kind else item["type"]), ("묶음", item["group"]), ("마지막 조산 운동", item["orogen"]),
            ("대륙", item["continent"]), ("지각", t(CRUST[item["crust"]], lang) if item["crust"] in CRUST else item["crust"])]
    from . import i18n
    return {"name": item["name"], "rows": [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]}
