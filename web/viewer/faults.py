"""세계 활성단층 — GEM Global Active Faults 를 오늘의 지구에 긋는다 (wetherilli 279).

원본은 GitHub `GEMScienceTools/gem-global-active-faults` 의 `geojson/gem_active_faults_harmonized.geojson`(Styron & Pagani 2020,
Earthquake Spectra doi:10.1177/8755293020944182, 13 696 줄) — **CC BY-SA 4.0**. 같은 조건으로 나눠야 하므로 구운 파일과 그 타일도 CC BY-SA 4.0
이고 출처에 그렇게 적는다. NAS `N:\\GSM\\sources\\earth\\gem_faults\\` 에 두고 `manage.py build_faults <geojson>` 이 `<EARTH_DIR>/earth_faults.json`
(2.9 MB — 저장소에 두기에 커서 밖에)으로 굽는다. 우리 디스크의 파일이라 문이 아니다. 판 경계(`tectonics.py`)와 같은 꼴이다.

- 미끄럼 갈래(`slip_type`, 스물 남짓)를 여섯으로 묶는다(`KINDS`) — 정단층·역단층(섭입 포함)·주향이동(변환 포함)·사교·확장 해령·그 밖(습곡·모름)
- 해령은 PB2002 를 옮긴 것이라(`catalog_name` "Bird 2003") 판 경계 레이어와 겹친다 — 옅게 긋는다
- 누르면 가까운 단층 하나 — 이름·갈래·경사·경사 방향·레이크·미끄럼 속도·지진 발생 깊이·원 목록. 값은 `(가장 그럴듯한, 최소, 최대)` 꼴로
  적혀 있어 풀어 쓴다
- **오늘의 지구다**
그리는 법을 고치면 `RENDERER` 를 올린다.
"""
import functools
import io
import json
import math

from django.conf import settings

from . import geomap, paleo
from .i18n import msg, t
from .tectonics import simplify

RENDERER = "1"
MAX_ZOOM = 8
TOLERANCE = 0.005
CITE = "GEM Global Active Faults (Styron & Pagani 2020) · CC BY-SA 4.0"
#: 갈래 → (색, 범례 글, 굵기 비, 점선)
KINDS = {
    "normal": ("#e31a1c", msg("정단층"), 1.0, None),
    "reverse": ("#1f5fbf", msg("역단층·섭입"), 1.1, None),
    "strike": ("#1a9e4b", msg("주향이동·변환"), 1.0, None),
    "oblique": ("#ff8c1a", msg("사교 (주향이동+경사이동)"), 1.0, None),
    "ridge": ("#9e9e9e", msg("확장 해령"), 0.8, None),
    "other": ("#555555", msg("습곡·갈래 모름"), 0.8, (5, 4)),
}
#: 원본의 `slip_type` → 갈래
SLIP = {
    "Normal": "normal", "Normal-Dextral": "oblique", "Normal-Sinistral": "oblique", "Normal-Strike-Slip": "oblique",
    "Reverse": "reverse", "Subduction_Thrust": "reverse", "Thrust": "reverse", "Blind_Thrust": "reverse",
    "Reverse-Dextral": "oblique", "Reverse-Sinistral": "oblique", "Reverse-Strike-Slip": "oblique",
    "Dextral": "strike", "Sinistral": "strike", "Strike-Slip": "strike", "Dextral_Transform": "strike", "Sinistral_Transform": "strike",
    "Dextral-Reverse": "oblique", "Dextral-Normal": "oblique", "Sinistral-Reverse": "oblique", "Sinistral-Normal": "oblique",
    "Spreading_Ridge": "ridge",
}


def kind_of(slip) -> str:
    return SLIP.get(str(slip or "").strip(), "other")


def _triple(text) -> str:
    """`(1.55,0.8,2.22)` → `1.55 (0.8–2.22)`, `(38,,)` → `38`. 비면 빈 글"""
    def tidy(v):
        try:
            return f"{float(v):.4g}"                 # `11.1000003814697` → `11.1` (원본이 float32 를 글로 적었다)
        except ValueError:
            return v
    parts = [tidy(p.strip()) if p.strip() else "" for p in str(text or "").strip("() ").split(",")]
    if not parts or not parts[0]:
        return ""
    best, lo, hi = (parts + ["", "", ""])[:3]
    return f"{best} ({lo}–{hi})" if lo and hi else best


# ── 굽기 ─────────────────────────────────────────────────────────────

def build(geojson_path) -> dict:
    """GEM 의 GeoJSON → `{"faults": [{name, slip, kind, dip, dipdir, rake, rate, depth, catalog, parts}]}`"""
    with open(geojson_path, encoding="utf-8") as fh:
        src = json.load(fh)
    out = []
    for feat in src.get("features") or []:
        geom, p = feat.get("geometry") or {}, feat.get("properties") or {}
        lines = [geom.get("coordinates") or []] if geom.get("type") == "LineString" else geom.get("coordinates") or []
        parts = []
        for line in lines:
            pts = simplify([(c[0], c[1]) for c in line if len(c) >= 2], TOLERANCE)
            flat, prev = [], None
            for x, y in pts:
                q = (round(x, 3), round(y, 3))
                if q != prev:
                    flat += [q[0], q[1]]
                    prev = q
            if len(flat) >= 4:
                parts.append(flat)
        if not parts:
            continue
        upper, lower = _triple(p.get("upper_seis_depth")), _triple(p.get("lower_seis_depth"))
        out.append({"name": str(p.get("name") or "").strip(), "slip": str(p.get("slip_type") or "").strip(),
                    "kind": kind_of(p.get("slip_type")), "dip": _triple(p.get("average_dip")), "dipdir": str(p.get("dip_dir") or "").strip(),
                    "rake": _triple(p.get("average_rake")), "rate": _triple(p.get("net_slip_rate")),
                    "depth": f"{upper}–{lower}" if upper and lower else "", "catalog": str(p.get("catalog_name") or "").strip(),
                    "parts": parts})
    return {"faults": out}


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def data():
    try:
        with open(settings.FAULTS_FILE, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return None
    for item in doc["faults"]:
        xs = [v for p in item["parts"] for v in p[0::2]]
        ys = [v for p in item["parts"] for v in p[1::2]]
        item["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return doc


def available() -> bool:
    return data() is not None


def legend(lang: str = "ko") -> list:
    return [{"color": c, "name": t(label, lang), "dash": bool(dash)} for c, label, _, dash in KINDS.values()]


def _hex(value: str, alpha: int = 255) -> tuple:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), alpha


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장 — 갈래의 색으로 긋는다. 해령·그 밖을 먼저, 활동성 단층을 위에."""
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    ss = 2
    size = paleo.TILE * ss
    scale = size / span
    tr = (west, north, scale, scale)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = 4 * ss / scale
    order = ["ridge", "other", "normal", "strike", "oblique", "reverse"]
    width0 = 0.9 if z <= 2 else 1.2 if z <= 5 else 1.6
    for item in sorted((data() or {"faults": []})["faults"], key=lambda f: order.index(f["kind"])):
        b = item["bbox"]
        if b[2] < west - pad or b[0] > west + span + pad or b[3] < north - span - pad or b[1] > north + pad:
            continue
        colour, _, weight, dash = KINDS[item["kind"]]
        alpha = 150 if item["kind"] == "ridge" else 235
        strokes = [{"color": _hex(colour, alpha), "width": width0 * weight, "dash": list(dash) if dash else None}]
        for flat in item["parts"]:
            for run in geomap._clip_runs(geomap._to_px(list(flat), tr, 10 ** 6), size, size, 8 * ss):
                geomap._stroke(draw, run, strokes, ss)
    out = image.resize((paleo.TILE, paleo.TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _seg_dist(px, py, ax, ay, bx, by, cos):
    """경위도 점과 선분의 거리(° — 경도는 cos 위도로 줄인다)"""
    ax, bx, px = ax * cos, bx * cos, px * cos
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def near(lon: float, lat: float, radius: float, lang: str = "ko"):
    """누른 자리에서 `radius`° 안의 가장 가까운 단층 — `{"name", "rows"}`. 없으면 None"""
    doc = data()
    if doc is None:
        return None
    lon = ((lon + 180.0) % 360.0) - 180.0
    cos = max(0.05, math.cos(math.radians(lat)))
    best = None
    for item in doc["faults"]:
        b = item["bbox"]
        if b[0] - radius / cos > lon or b[2] + radius / cos < lon or b[1] - radius > lat or b[3] + radius < lat:
            continue
        for flat in item["parts"]:
            for i in range(0, len(flat) - 2, 2):
                d = _seg_dist(lon, lat, flat[i], flat[i + 1], flat[i + 2], flat[i + 3], cos)
                if d <= radius and (best is None or d < best[0]):
                    best = (d, item)
    if best is None:
        return None
    item = best[1]
    from . import i18n
    rows = [("갈래", t(KINDS[item["kind"]][1], lang)), ("미끄럼 (원문)", item["slip"].replace("_", " ")),
            ("경사 (°)", item["dip"]), ("경사 방향", item["dipdir"]), ("레이크 (°)", item["rake"]),
            ("미끄럼 속도 (mm/yr)", item["rate"]), ("지진 발생 깊이 (km)", item["depth"]), ("원 목록", item["catalog"])]
    return {"name": item["name"] or t(msg("이름 없는 단층"), lang), "color": KINDS[item["kind"]][0],
            "rows": [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]}
