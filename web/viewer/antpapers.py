"""남극 논문 두 편의 벡터 레이어 — Armadillo 외 2026(동남극 부채꼴 분지 지대, EAFBP)·Gernon 외 2026(고지형 등고선) (wetherilli 435).

사람이 발표에서 두 논문의 그림과 모형을 GSM 위에서 설명하려 한다 — 개인 레이어(그 브라우저에만)가 아니라 남극 탭의 카탈로그에 늘 보이게.
`manage.py build_antarctic_papers <EAFBP.zip> [--fig2a <geojson>] [--fig4a <geojson>]` 이 numpy 없이 읽어
`data/antarctic_papers.json` 에 적는다(0.2 MB 남짓이라 저장소에 둔다). 화면이 부를 때는 이 파일만 읽는다. 문이 아니다.
**고지형 등고선만은 저장소 밖이다** — 34 연대를 다 뽑으니 2.8 MB 라(wetherilli 439), 래스터와 같은 zip 에서
`build_gernon_paleotopo` 가 `<GSM_GERNON_PALEOTOPO_DIR>/contours.json` 에 함께 굽는다.

- **Armadillo 외 2026**, *Nature Geoscience* 19:715–722, doi:10.1038/s41561-026-01991-6 — 자료는 figshare 25450219 (CC BY 4.0).
  빙저 선구조(셰이프, 경위도)·분지 가장자리와 이등분선·전단대 구조 선(xyz)은 자료 그대로다. 오일러 극 넷은 본문의 수치다.
  틀(남·북 TSCB 소원·해안 소원·벨지카 이등분선)은 **우리가 다시 그린 것** — 본문의 극 자리에서 선 자료까지 거리의 중앙값을 반지름으로
- **Gernon 외 2026**, *Science* 392:eadz6758, doi:10.1126/science.adz6758 — 자료는 Zenodo 19205651 (CC BY 4.0, 그림은 아니다).
  FastScape 모형의 고지형(3031, 5 km, 601×601, float32) 34 연대를 등고 0·1 000·1 500·2 000 m 로 뽑았다. 1 500 m 가 본문의 빙모 문턱이다.
  레이어는 하나(`antpapers:gernon_contours`)이고 연대는 화면의 연대 막대가 `?age=` 로 고른다 (wetherilli 439).
  Fig. 4A 의 빙상 범위(PISM, 6 Myr 간격 열두 장)는 papers-fig4a 가 그림에서 딴 GeoJSON 을 `--fig4a` 로 받는다 — 고른 연대에서
  3 Myr 안의 가장 가까운 장만 내고, 밖이면 비운다(`antpapers:gernon_ice`, wetherilli 440)
- 둘 다 해석·모형이지 관측이 아니다. **좌표는 오늘의 자리다** — 판을 돌리지 않았다
- Fig. 2a 의 해석선(자료가 없다)은 papers-fig2a 가 그림에서 딴 GeoJSON 을 `--fig2a` 로 받는다 — 없으면 그 레이어를 굽지 않는다
"""
import functools
import io
import json
import math
import time
import zipfile

from django.conf import settings

from . import geo3al, geomap, gernontopo, i18n, raised
from .i18n import msg

ARMADILLO_DOI = "https://doi.org/10.1038/s41561-026-01991-6"
ARMADILLO_DATA = "https://doi.org/10.6084/m9.figshare.25450219"
GERNON_DOI = "https://doi.org/10.1126/science.adz6758"
GERNON_DATA = "https://doi.org/10.5281/zenodo.19205651"
CREDIT = "Armadillo et al. 2026 (Nat. Geosci., CC BY 4.0) · Gernon et al. 2026 (Science; data Zenodo CC BY 4.0)"

#: 고지형의 연대(Ma) — 래스터와 같은 34 장 (wetherilli 439)
AGES = gernontopo.AGES
#: 연대를 따르는 레이어 둘 — 등고선(저장소 밖의 파일)과 Fig. 4A 빙상 범위(저장소의 파일)
CONTOURS = "antpapers:gernon_contours"
ICE = "antpapers:gernon_ice"
#: 빙상 범위는 6 Myr 간격이다 — 고른 연대에서 이만큼 안의 가장 가까운 장만 낸다
ICE_WINDOW = 3
#: 원본 격자 — 칸의 모서리가 원점이다(GeoTIFF 의 tiepoint)
GRID_N, GRID_X0, GRID_Y0, GRID_STEP = 601, -1002500.0, 2502500.0, 5000.0
#: 등고선을 줄이는 너비(칸) — 0.3 칸 = 1.5 km. 원본이 5 km 격자라 그 밑의 굴곡은 격자의 것이다
SIMPLIFY = 0.3

# 갈래 — (code, 이름, 색, 모양). 모양은 `map.js` 의 `classStyle` 이 읽는다
_S = lambda width, dash=None: {"shape": "stroke", "width": width, **({"dash": dash} if dash else {})}
CLASSES = {
    "antpapers:eafbp_faults": [("fault", msg("빙저 선구조"), "#3a3a3a", _S(1.2))],
    "antpapers:eafbp_basins": [("single", msg("분지 가장자리"), "#d62728", _S(1.8)),
                               ("bisect", msg("분지 이등분선"), "#d62728", _S(1.4, [6, 4]))],
    "antpapers:eafbp_tscb": [("C1", msg("남쪽 TSCB"), "#c71585", _S(2.4)),
                             ("C2", msg("북쪽 TSCB"), "#17a2b8", _S(2.4))],
    "antpapers:eafbp_frame": [("south", msg("남쪽 TSCB 소원"), "#c71585", _S(1.6, [8, 5])),
                              ("north", msg("북쪽 TSCB 소원"), "#17a2b8", _S(1.6, [8, 5])),
                              ("coast", msg("해안선 소원"), "#1f77b4", _S(1.6, [8, 5])),
                              ("bisector", msg("벨지카 이등분선 (≈동경 130°)"), "#ff7f0e", _S(1.6, [2, 4]))],
    "antpapers:eafbp_poles": [("ep", msg("EAFBP 오일러 극 (분지 가장자리)"), "#ff7f0e", {"shape": "star"}),
                              ("south", msg("남쪽 TSCB 소원의 극"), "#c71585", {"shape": "star"}),
                              ("north", msg("북쪽 TSCB 소원의 극"), "#17a2b8", {"shape": "star"}),
                              ("coast", msg("해안선 소원의 극"), "#1f77b4", {"shape": "star"})],
    "antpapers:eafbp_fig2a": [("fan", msg("부채꼴 구조 (Fan)"), "#2ca02c", _S(2.0)),
                              ("fault", msg("단층 (Fau)"), "#9467bd", _S(2.0)),
                              ("fz", msg("대륙 주변부 단열대"), "#8c564b", _S(1.6, [6, 4])),
                              ("other", msg("그 밖의 해석선"), "#7f7f7f", _S(1.4))],
}
#: 등고마다 색상을 갈라 겹쳐도 읽히게 — 바다 쪽 파랑에서 높을수록 초록·빨강·보라. 고지형 래스터(갈색 계열) 위에서도 갈려 보인다.
#: 1 500 m 는 본문의 빙모 문턱이라 굵게 (wetherilli 438)
LEVELS = [("0", msg("해안선 (0 m)"), "#2166ac", _S(1.4)),
          ("1000", msg("1 000 m"), "#1a9850", _S(1.6)),
          ("1500", msg("1 500 m — 빙모가 생기는 문턱"), "#d73027", _S(3.0)),
          ("2000", msg("2 000 m"), "#7b3294", _S(1.8))]
CLASSES[CONTOURS] = LEVELS
CLASSES[ICE] = [("ice", msg("빙상 범위 (PISM 모형)"), "#1f78b4", {"shape": "area"})]
#: 연대를 따르는 레이어 → 고를 수 있는 연대. 화면의 연대 막대가 카탈로그 행의 `ages` 로 받는다
TIMED = {CONTOURS: AGES, ICE: AGES}
#: 본문의 극 자리 (위도, 경도) — 오차 타원은 MATLAB 을 돌려야 해서 넣지 않았다
POLES = {"ep": (-86.4, 129.9), "south": (-84.2, 130.8), "north": (-83.1, 129.5), "coast": (-81.7, 115.1)}
#: 해안 소원을 잴 해안선 점의 경도 — 케이프 애데어에서 프리즈 만까지
COAST_LON = (70.0, 172.0)
LABELS = {"kind": "갈래", "name": "이름", "basin": "분지", "side": "쪽", "radius": "반지름", "where": "출처",
          "level": "등고선", "age": "연대", "area": "넓이", "note": "그린 법", "link": "논문", "data": "자료"}
#: 이름표로 쓸 열 — 분지 이름을 선 위에 적는다(`map.js` 의 `labelBy`)
LABEL_BY = {"antpapers:eafbp_basins": "basin", "antpapers:eafbp_fig2a": "name"}


class AntPapersError(RuntimeError):
    pass


def path():
    return settings.ANTARCTIC_PAPERS_FILE


def contours_path():
    """고지형 등고선 — 저장소 밖, 래스터 옆 (wetherilli 439)"""
    return gernontopo.root() / "contours.json"


def _file(name: str):
    return contours_path() if name == CONTOURS else path()


def knows(name: str) -> bool:
    return name in CLASSES


def available(name: str = "") -> bool:
    if name == CONTOURS:
        return contours_path().exists()
    if not path().exists():
        return False
    return not name or name in (data() or {}).get("layers", {})


# ── 굽기 — 읽기 ───────────────────────────────────────────────────────

def _zip(data: bytes) -> dict:
    """zip → {끝 이름: 바이트}. 저자 zip 은 꼭대기 폴더가 있기도 없기도 해서 맨 끝 이름으로 찾는다"""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AntPapersError(f"zip 이 아니다: {exc}") from exc
    return {info.filename.rsplit("/", 1)[-1]: z.read(info) for info in z.infolist() if not info.is_dir()}


def _need(files: dict, name: str) -> bytes:
    if name not in files:
        raise AntPapersError(f"{name} 가 없다")
    return files[name]


def read_xyz_lines(text: str) -> list:
    """MATLAB 의 xyz(`Line <이름>` 머리, 줄마다 위도 경도) → [(이름, [[경도, 위도], …])]"""
    out, cur = [], None
    for raw in text.splitlines():
        p = raw.split()
        if not p:
            continue
        if p[0].lstrip("/") == "Line":
            cur = (p[1] if len(p) > 1 else "", [])
            out.append(cur)
            continue
        try:
            lat, lon = float(p[0]), float(p[1])
        except (ValueError, IndexError):
            continue
        if cur is None:
            cur = ("", [])
            out.append(cur)
        cur[1].append([lon, lat])
    return [(name, pts) for name, pts in out if len(pts) >= 2]


def _r(pts, nd=4):
    return [[round(x, nd), round(y, nd)] for x, y in pts]


# 구면의 거리·방위 — 소원을 그린다
def _dist_az(lat1, lon1, lat2, lon2):
    a, b, c, d = map(math.radians, (lat1, lon1, lat2, lon2))
    dist = math.acos(max(-1.0, min(1.0, math.sin(a) * math.sin(c) + math.cos(a) * math.cos(c) * math.cos(d - b))))
    az = math.atan2(math.sin(d - b) * math.cos(c), math.cos(a) * math.sin(c) - math.sin(a) * math.cos(c) * math.cos(d - b))
    return math.degrees(dist), math.degrees(az) % 360


def _dest(lat, lon, az, dist):
    lat, lon, az, dist = map(math.radians, (lat, lon, az, dist))
    lat2 = math.asin(math.sin(lat) * math.cos(dist) + math.cos(lat) * math.sin(dist) * math.cos(az))
    lon2 = lon + math.atan2(math.sin(az) * math.sin(dist) * math.cos(lat), math.cos(dist) - math.sin(lat) * math.sin(lat2))
    return [(math.degrees(lon2) + 540) % 360 - 180, math.degrees(lat2)]


def _span(azimuths):
    """방위들이 덮는 호 — 가장 큰 빈틈의 반대쪽. (시작, 끝) 끝 > 시작"""
    a = sorted(azimuths)
    gap, k = max(((a[(k + 1) % len(a)] - a[k]) % 360, k) for k in range(len(a)))
    start = a[(k + 1) % len(a)]
    return start, start + 360 - gap


def small_circle(pole, points, pad=5.0, steps=200):
    """극에서 점들까지 거리의 중앙값을 반지름으로, 점들이 덮는 방위(±pad°)만큼의 소원 → (선, 반지름 km)"""
    lat, lon = pole
    da = [_dist_az(lat, lon, y, x) for x, y in points]
    dists = sorted(d for d, _ in da)
    radius = dists[len(dists) // 2]
    a0, a1 = _span([az for _, az in da])
    a0, a1 = a0 - pad, a1 + pad
    line = [_dest(lat, lon, a0 + (a1 - a0) * t / steps, radius) for t in range(steps + 1)]
    return line, round(math.radians(radius) * 6371)


def convert_eafbp(data: bytes) -> dict:
    """EAFBP.zip → 레이어 다섯 {이름: [갈래, 속성, 꼴, 좌표]}"""
    files = _zip(data)
    if b"GEOGCS" not in _need(files, "faults_all_ln.prj") or b"PROJCS" in files["faults_all_ln.prj"]:
        raise AntPapersError("빙저 선구조의 좌표가 경위도가 아니다")
    try:
        shapes = raised.read_lines(_need(files, "faults_all_ln.shp"))
    except raised.RaisedError as exc:
        raise AntPapersError(f"빙저 선구조: {exc}") from exc
    faults = []
    for k, parts in enumerate(shapes):
        for part in parts:
            if len(part) >= 2:
                faults.append(["fault", {"name": str(k)}, "L", _r(part)])
    if len(faults) < 100:
        raise AntPapersError(f"빙저 선구조가 너무 적다 ({len(faults)})")

    def xyz(name):
        return read_xyz_lines(_need(files, name).decode("latin-1"))

    basins = []
    for fn, code in (("all_single.xyz", "single"), ("all_bisect.xyz", "bisect")):
        for name, pts in xyz(fn):
            side = {"E": "E", "W": "W"}.get(name[-1:]) if name[-2:-1] == "_" else None
            basins.append([code, {"name": name, "basin": name.rsplit("_", 1)[0] if side else name, **({"side": side} if side else {})},
                           "L", _r(pts)])
    tscb, belts = [], {"C1": [], "C2": []}
    for fn, code in (("C1_segments_def_NEW.xyz", "C1"), ("C2_segments_NEW.xyz", "C2")):
        for name, pts in xyz(fn):
            tscb.append([code, {"name": name}, "L", _r(pts)])
            belts[code] += pts
    if not basins or not belts["C1"] or not belts["C2"]:
        raise AntPapersError("분지 가장자리나 전단대 선이 없다")

    frame = []
    for code, belt in (("south", "C1"), ("north", "C2")):
        line, km = small_circle(POLES[code], belts[belt])
        frame.append([code, {"radius": km}, "L", _r(line)])
    coast = [p for _, pts in xyz("costa.xyz") for p in pts if COAST_LON[0] <= p[0] <= COAST_LON[1]]
    if len(coast) < 100:
        raise AntPapersError("해안선 점이 너무 적다 (costa.xyz)")
    line, km = small_circle(POLES["coast"], coast, pad=0.0)
    frame.append(["coast", {"radius": km}, "L", _r(line)])
    # 본문 — 대칭축이 대략 동경 130° 자오선이다. 극에서 해안(남위 66°)까지
    frame.append(["bisector", {}, "L", [[130.0, round(-86.4 + t * 0.1, 2)] for t in range(205)]])

    poles = [[code, {}, "P", [lon, lat]] for code, (lat, lon) in POLES.items()]
    return {"antpapers:eafbp_faults": faults, "antpapers:eafbp_basins": basins, "antpapers:eafbp_tscb": tscb,
            "antpapers:eafbp_frame": frame, "antpapers:eafbp_poles": poles}


def convert_fig4a(data: bytes) -> dict:
    """papers-fig4a 가 Fig. 4A 에서 딴 빙상 범위 GeoJSON(경위도, `age_ma`·`name`·`note`·`area_km2`, 면) → 레이어 하나 (wetherilli 440)"""
    try:
        doc = json.loads(data)
    except ValueError as exc:
        raise AntPapersError(f"Fig. 4A 파일이 JSON 이 아니다: {exc}") from exc
    rows = []
    for f in doc.get("features", []):
        geom, props = f.get("geometry") or {}, f.get("properties") or {}
        try:
            age = int(round(float(props.get("age_ma"))))
        except (TypeError, ValueError):
            raise AntPapersError(f"Fig. 4A 피처에 age_ma 가 없다 ({props})")
        polys = {"Polygon": [geom.get("coordinates")], "MultiPolygon": geom.get("coordinates")}.get(geom.get("type"))
        if not polys:
            continue
        rings = [[_r([p[:2] for p in ring]) for ring in poly if ring and len(ring) >= 4] for poly in polys if poly]
        rings = [poly for poly in rings if poly]
        if not rings:
            continue
        own = {"age": age, "name": str(props.get("name") or ""), "note": str(props.get("note") or "")}
        if props.get("area_km2") is not None:
            own["area"] = round(float(props["area_km2"]))
        rows.append(["ice", own, "A", rings])
    if not rows:
        raise AntPapersError("Fig. 4A 파일에 면이 없다")
    return {ICE: rows}


def ice_age(ages, age):
    """고른 연대 → 낼 빙상 범위의 연대. `ICE_WINDOW` 안에 없으면 None. 같은 거리면 옛것"""
    near = sorted(ages, key=lambda a: (abs(a - age), -a))
    return near[0] if near and abs(near[0] - age) <= ICE_WINDOW else None


def convert_fig2a(data: bytes) -> dict:
    """papers-fig2a 가 그림에서 딴 GeoJSON(경위도, `name`·`kind`) → 레이어 하나"""
    try:
        doc = json.loads(data)
    except ValueError as exc:
        raise AntPapersError(f"Fig. 2a 파일이 JSON 이 아니다: {exc}") from exc
    known = {code for code, *_ in CLASSES["antpapers:eafbp_fig2a"]}
    rows = []
    for f in doc.get("features", []):
        geom, props = f.get("geometry") or {}, f.get("properties") or {}
        kind = props.get("kind") if props.get("kind") in known else "other"
        lines = {"LineString": [geom.get("coordinates")], "MultiLineString": geom.get("coordinates")}.get(geom.get("type"), [])
        for line in lines or []:
            if line and len(line) >= 2:
                rows.append([kind, {"name": str(props.get("name") or "")}, "L", _r([p[:2] for p in line])])
    if not rows:
        raise AntPapersError("Fig. 2a 파일에 선이 없다")
    return {"antpapers:eafbp_fig2a": rows}


# ── 굽기 — 고지형 등고선 ─────────────────────────────────────────────

def contour(z: list, level: float) -> list:
    """마칭 스퀘어 — 칸 좌표(열, 줄)의 선 목록. NaN 이 낀 칸은 건너뛴다"""
    rows, cols = len(z), len(z[0])
    segs = []
    for r in range(rows - 1):
        top, bot = z[r], z[r + 1]
        for c in range(cols - 1):
            v = (top[c], top[c + 1], bot[c + 1], bot[c])
            if None in v:
                continue
            idx = (v[0] >= level) | (v[1] >= level) << 1 | (v[2] >= level) << 2 | (v[3] >= level) << 3
            if idx in (0, 15):
                continue
            corners = ((c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1))
            pts = {}
            for k in range(4):
                a1, a2 = v[k], v[(k + 1) % 4]
                if (a1 >= level) != (a2 >= level):
                    s = (level - a1) / (a2 - a1)
                    (c1, r1), (c2, r2) = corners[k], corners[(k + 1) % 4]
                    pts[k] = (c1 + s * (c2 - c1), r1 + s * (r2 - r1))
            edges = sorted(pts)
            if len(edges) == 2:
                segs.append((pts[edges[0]], pts[edges[1]]))
            else:                                       # 안장 — 가운데 값으로 가른다
                if (sum(v) / 4 >= level) == (v[0] >= level):
                    segs += [(pts[0], pts[3]), (pts[1], pts[2])]
                else:
                    segs += [(pts[0], pts[1]), (pts[2], pts[3])]
    key = lambda p: (round(p[0], 6), round(p[1], 6))
    adj = {}
    for i, (p, q) in enumerate(segs):
        adj.setdefault(key(p), []).append(i)
        adj.setdefault(key(q), []).append(i)
    used, lines = [False] * len(segs), []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        line = [segs[i][0], segs[i][1]]
        for forward in (True, False):
            while True:
                tip = line[-1] if forward else line[0]
                nxt = next((j for j in adj[key(tip)] if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                p, q = segs[nxt]
                other = q if key(p) == key(tip) else p
                if forward:
                    line.append(other)
                else:
                    line.insert(0, other)
        lines.append(line)
    return lines


def simplify(line: list, tol: float) -> list:
    """더글러스–포이커 (돌이 아니라 칸 좌표에서)"""
    if len(line) < 3:
        return line
    keep = [False] * len(line)
    keep[0] = keep[-1] = True
    stack = [(0, len(line) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = line[a], line[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, at = 0.0, None
        for k in range(a + 1, b):
            x, y = line[k]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > best:
                best, at = d, k
        if at is not None and best > tol:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(line, keep) if k]


def _cell_lonlat(c, r, x0=GRID_X0 + GRID_STEP / 2, ytop=GRID_Y0 - GRID_STEP / 2, step=GRID_STEP):
    """칸 좌표(열, 줄) → 경위도. `x0`·`ytop` 은 왼쪽 위 칸의 가운데"""
    return geomap.xy3031_to_lonlat(x0 + step * c, ytop - step * r)


def contours_of(z: list, x0=GRID_X0 + GRID_STEP / 2, ytop=GRID_Y0 - GRID_STEP / 2, step=GRID_STEP) -> list:
    """한 연대의 격자 → [갈래, 속성, 꼴, 좌표]. 6 칸(30 km)보다 짧은 조각은 버린다"""
    out = []
    for code, *_ in LEVELS:
        for line in contour(z, float(code)):
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(line, line[1:]))
            if length < 6:
                continue
            out.append([code, {}, "L", _r([_cell_lonlat(c, r, x0, ytop, step) for c, r in simplify(line, SIMPLIFY)])])
    return out


def _grid_rows(data: bytes):
    """GeoTIFF → (줄 목록, 왼쪽 위 칸 가운데 x, y, 칸). 래스터와 같은 `gernontopo.read_tif` 로 읽는다 — 원점·칸은 꼬리표에서"""
    from . import polargrid
    try:
        g = gernontopo.read_tif(data)
    except polargrid.PolarGridError as exc:
        raise AntPapersError(str(exc)) from exc
    except Exception as exc:                          # Pillow 가 못 읽는다 — 이 문의 말로
        raise AntPapersError(f"TIFF 를 못 읽는다: {exc}") from exc
    v = g.values
    rows = [[None if x != x else x for x in v[r * g.ne:(r + 1) * g.ne]] for r in range(g.nv)]
    return rows, g.x0, g.ytop, g.res


def convert_gernon(read, ages=AGES) -> dict:
    """연대 → 등고선 줄. `read(연대)` 가 그 연대의 GeoTIFF 바이트를 준다"""
    out = {}
    for age in ages:
        rows = contours_of(*_grid_rows(read(age)))
        if not rows:
            raise AntPapersError(f"{age} Ma 에 등고선이 없다")
        out[str(age)] = rows
    return out


def _write(doc: dict, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    part.replace(out)


def build_contours(read, ages=AGES, out=None) -> dict:
    """34 연대의 등고선을 `contours.json` 에 — `build_gernon_paleotopo` 가 래스터를 구우며 부른다 (wetherilli 439)"""
    by_age = convert_gernon(read, ages)
    _write({"built": time.strftime("%Y-%m-%d"), "source": GERNON_DATA, "ages": by_age}, out or contours_path())
    return {int(age): len(rows) for age, rows in by_age.items()}


def build(eafbp: bytes, fig2a: bytes = None, fig4a: bytes = None, out=None) -> dict:
    layers = {**convert_eafbp(eafbp), **(convert_fig2a(fig2a) if fig2a else {}), **(convert_fig4a(fig4a) if fig4a else {})}
    _write({"built": time.strftime("%Y-%m-%d"), "source": [ARMADILLO_DATA, GERNON_DATA], "layers": layers}, out or path())
    return {name: len(rows) for name, rows in layers.items()}


# ── 내주기 ───────────────────────────────────────────────────────────

#: 그리는 법(색·굵기)의 판 — 고치면 올린다. 내준 덩이는 브라우저에 1 년 두므로 파일이 그대로여도 주소가 바뀌어야 한다 (wetherilli 438)
RENDERER = 2


def version(name: str = "") -> str:
    file = _file(name)
    try:
        st = file.stat()
    except FileNotFoundError:
        return ""
    return f"r{RENDERER}-{st.st_mtime_ns}-{st.st_size}"


@functools.lru_cache(maxsize=4)
def _read(file: str, _stamp: str) -> dict:
    from pathlib import Path
    return json.loads(Path(file).read_text(encoding="utf-8"))


def _data(_stamp: str) -> dict:
    return _read(str(path()), _stamp)


def data():
    return _data(version()) if path().exists() else None


def _rows(name: str, age, stamp: str) -> list:
    """레이어의 줄 — 연대를 따르는 둘은 고른 연대의 것만. 빙상 범위는 3 Myr 안의 가장 가까운 장, 없으면 빈 것"""
    if name == CONTOURS:
        return _read(str(contours_path()), stamp)["ages"].get(str(age), [])
    rows = _data(stamp)["layers"][name]
    if name == ICE:
        pick = ice_age({own["age"] for _, own, _, _ in rows}, age)
        return [r for r in rows if r[1]["age"] == pick]
    return rows


def _props(name: str, code: str, own: dict, label: str, lang: str) -> dict:
    gernon = name.startswith("antpapers:gernon_")
    props = {"code": code, "kind": label}
    if name == ICE:
        props = {"code": code, "kind": label, "age": f"{own['age']} Ma"}
        if own.get("area"):
            props["area"] = f"{own['area']:,} km²"
        if own.get("name"):
            props["name"] = own["name"]
        props["note"] = own.get("note") or i18n.t(msg("논문 Fig. 4A 에서 딴 PISM 빙상 범위 — 모형이지 관측이 아니다"), lang)
        props["link"], props["data"] = GERNON_DOI, GERNON_DATA
        return props
    if "name" in own and name != "antpapers:eafbp_faults":
        props["name"] = own["name"]
    elif name == "antpapers:eafbp_faults":
        props["name"] = f"#{own.get('name', '')}"
    if own.get("basin"):
        props["basin"] = own["basin"]
    if own.get("side"):
        props["side"] = i18n.t(msg("동") if own["side"] == "E" else msg("서"), lang)
    if own.get("radius"):
        props["radius"] = f"{own['radius']:,} km"
    if name == "antpapers:eafbp_frame":
        props["note"] = i18n.t(msg("본문의 극 자리와 선 자료로 우리가 다시 그렸다 — 논문 그림과 조금 다를 수 있다")
                               if code != "bisector" else msg("본문 — 대칭축이 대략 동경 130° 자오선"), lang)
    if name == "antpapers:eafbp_poles":
        lat, lon = POLES[code]
        props["where"] = i18n.t(msg("본문 {lat}°S {lon}°E — 오차 타원은 넣지 않았다", lat=-lat, lon=lon), lang)
    if name == "antpapers:eafbp_fig2a":
        props["note"] = i18n.t(msg("논문 Fig. 2a 에서 딴 해석선 — 맞춤 잔차 ±3 km"), lang)
    if gernon:
        props["level"] = label
        props["age"] = f"{own.get('age', '')} Ma"
        props.pop("kind")
    props["link"] = GERNON_DOI if gernon else ARMADILLO_DOI
    props["data"] = GERNON_DATA if gernon else ARMADILLO_DATA
    return props


def body(name: str, lang: str = "ko", age=None) -> bytes:
    """레이어 하나의 GeoJSON — 갈래(`code`)마다 색. 파일이나 그 레이어가 없으면 FileNotFoundError.
    연대를 따르는 레이어(`TIMED`)는 `age` 의 것 — 모르는 연대면 ValueError"""
    if not available(name):
        raise FileNotFoundError(_file(name))
    if name in TIMED:
        try:
            age = int(age)
        except (TypeError, ValueError):
            raise ValueError(age)
        if age not in TIMED[name]:
            raise ValueError(age)
    else:
        age = None
    return _body(name, lang, age, version(name))


@functools.lru_cache(maxsize=96)
def _body(name: str, lang: str, age, _stamp: str) -> bytes:
    rows = _rows(name, age, _stamp)
    table = {code: (i18n.t(label, lang), color, look) for code, label, color, look in CLASSES[name]}
    features, counts = [], {}
    for code, own, kind, coords in rows:
        if code not in table:
            continue
        counts[code] = counts.get(code, 0) + 1
        if name == CONTOURS:
            own = {"age": age}
        geom = {"type": "Point" if kind == "P" else "MultiPolygon" if kind == "A" else "LineString", "coordinates": coords}
        features.append({"type": "Feature", "geometry": geom, "properties": _props(name, code, own, table[code][0], lang)})
    legend = [{"code": code, "label": table[code][0], "color": table[code][1], "count": counts[code], **table[code][2]}
              for code, *_ in CLASSES[name] if counts.get(code)]
    doc = {"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link", "data"],
           "legend": legend, "features": features}
    if name in LABEL_BY:
        doc["labelBy"] = LABEL_BY[name]
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 저장소의 파일이다 — 원본은 figshare·Zenodo 에서 한 번 받아 `build_antarctic_papers` 로 굽는다 (wetherilli 435)
REGISTRY = [
    {"upstream": "antpapers", "tag": "Papers", "title": "남극 논문 자료 (Armadillo 2026 · Gernon 2026)", "local": True},
]
