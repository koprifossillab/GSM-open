"""중국(과 동아시아) 지질도 — USGS geo3al 을 우리 디스크에서 읽는다 (devlog 025).

자료는 USGS Open-File Report 97-470F 의 판 1 "The Far East" 에 딸린 **Generalized
Geology of the Far East (geo3al)** 다(1999, doi:10.5066/P9EXVH3J). 원도는 UNESCO/CGMW
의 *Geology of East and South Asia* (1:500만·1:300만). 중국·몽골·한반도·일본·대만과
인도차이나 일부를 덮는다. 면 12 330, 꼭짓점 64 만.

**이용 조건이 붙어 있다.** 메타데이터의 Use_Constraints — UNESCO·CGMW·ESRI 의
지적재산이 들어 있어 "자기 내부 용도만, 가공한 결과물을 포함해 제3자에게 재배포
금지" 다. 연구실 안에서만 쓰는 것으로 사람이 정했다(2026-09-28). **GSM 을 밖에 열
때는 이 레이어를 먼저 내린다.** 파일은 저장소·이미지 어디에도 넣지 않는다.

- **상류가 아니라 파일이다.** 얀마옌(022)처럼 서버 디스크의 셰이프파일을 읽고,
  위경도 GeoJSON 한 덩이로 브라우저에 준다(`/points/`). 받는 문(`requests`)이 없다
- 셰이프파일·dBASE 는 `struct` 로 푼다. 공간 라이브러리를 들이지 않는다(018)
- 원본 좌표는 **람베르트 정각원추**(중앙경선 120°E, 표준위선 31°N·29°S, WGS84)다.
  `.prj` 에서 변수를 읽어 `crs.lcc_to_latlon` 으로 옮긴다. pyproj 를 들이지 않는다 (013)
- 옮긴 것은 프로세스가 들고 있다. 셋 파일의 크기·고친 때가 같으면 다시 읽지 않는다.
  처음 한 번이 몇 초 걸린다
- **꼭짓점을 줄이지 않는다.** 면마다 따로 줄이면 이웃한 면 사이에 틈이 벌어진다.
  줄이지 않아도 gzip 으로 3.6 MB 다 — 연구실 망에서는 한 번이면 된다

레이어는 둘이다. 같은 면을 두 번 칠하지 않도록 뜻을 갈랐다.

- `geo3al:age` — 모든 면을 **지질시대**(`GEN_GLG`)로 칠한다. 색은 ICS 국제층서표의
  색이다 — 원도를 낸 CGMW 가 그 색을 정한다
- `geo3al:rock` — 화성암·풍성 퇴적물(`TYPE` 이 있는 면)만 **암종**으로 칠한다.
  원도의 범례가 퇴적암과 변성암을 가르지 않아(메타데이터), 그 밖의 면에는 암종이 없다

바다·호수(`H2O`)와 "지질을 그리지 않은 곳"(`oth`)은 싣지 않는다 — 칠할 지질이 없다.
"""
import json
import logging
import math
import re
import struct
import threading
from pathlib import Path

from django.conf import settings

from . import crs, i18n
from .i18n import msg

log = logging.getLogger(__name__)

DATASET = "geo3al"
#: 좌표를 이 자리까지만 둔다. 소수 넷째 자리가 10 m 남짓이다 — 원도는 수백 m 로 거칠다
DIGITS = 4
SOURCE_URL = "https://doi.org/10.5066/P9EXVH3J"
#: 지도 귀퉁이의 출처. 다른 상류처럼 영어로 적는다 — 두 판이 같은 글이다
ATTRIBUTION = ('<a href="' + SOURCE_URL + '" target="_blank" rel="noopener">USGS</a> geo3al '
               "(OFR 97-470F) · UNESCO/CGMW — internal use only, no redistribution")


class Geo3alError(RuntimeError):
    pass


#: 레이어명 → 무엇으로 칠하나. `style` 은 `map.js` 의 `legendStyle` 이 읽는다.
LAYERS = {
    "geo3al:age": {"by": "age", "style": "unit", "opacity": 0.75},
    "geo3al:rock": {"by": "rock", "style": "unit", "opacity": 0.9},
}

#: 팝업에 올리는 열과 그 이름. 차례가 팝업의 차례다. 영어는 `i18n.PROP_EN`.
LABELS = {
    "age": "지질시대",
    "rock": "암종",
    "glg": "원도 기호",
}

#: 싣지 않는 시대 기호 — 바다·호수, 지질을 그리지 않은 곳.
SKIP = {"H2O", "oth"}

# ── 지질시대 ─────────────────────────────────────────────────────────
#
# 메타데이터의 기호 풀이를 ICS 한국어 이름으로 옮겼다. 두 시대에 걸친 것은
# **옛것~새것** 으로 적는다(KIGAM 의 값이 그렇게 쓴다). USGS 는 새것을 앞에 둔다
# (`TK`) — 기호는 원도 그대로 두고 이름만 우리 차례로 쓴다. 영어판은
# `i18n.age_en` 이 낱말마다 옮긴다.
# 메타데이터에 없는 기호가 자료에 넷 있다(`Pg`·`AP`·`TrK`·`PtPZ`·`MZT`). 이름의 짜임이
# 다른 기호와 같아 그 뜻으로 읽었다.

#: 원도의 시대 기호(`GLG`, 44 가지) → 이름. 팝업의 "지질시대" 다.
GLG = {
    "Q": "제4기", "TQ": "제3기~제4기", "NQ": "신진기~제4기", "N": "신진기", "Pg": "고진기",
    "T": "제3기", "KT": "백악기~제3기", "MZT": "중생대~제3기", "CzMz": "중생대~신생대",
    "MZ": "중생대", "PZMZ": "고생대~중생대", "K": "백악기", "JK": "쥐라기~백악기",
    "J": "쥐라기", "TrJ": "트라이아스기~쥐라기", "TrK": "트라이아스기~백악기",
    "Tr": "트라이아스기", "PTr": "페름기~트라이아스기", "CTr": "석탄기~트라이아스기",
    "PZ": "고생대", "PZu": "고생대 후기", "P": "페름기", "CP": "석탄기~페름기",
    "C": "석탄기", "DC": "데본기~석탄기", "D": "데본기", "PZl": "고생대 전기",
    "SD": "실루리아기~데본기", "S": "실루리아기", "OS": "오르도비스기~실루리아기",
    "O": "오르도비스기", "CmO": "캄브리아기~오르도비스기", "CmD": "캄브리아기~데본기",
    "Cm": "캄브리아기", "PtCm": "원생누대~캄브리아기", "PtO": "원생누대~오르도비스기",
    "PtPZ": "원생누대~고생대", "pC": "선캄브리아시대", "Pt": "원생누대",
    "AP": "시생누대~원생누대", "A": "시생누대", "und": "시대 미상",
}

#: ICS 국제층서표(2023/09)의 색. 기(Period)·대(Era)·누대(Eon) 것만 쓴다.
ICS = {
    "Q": "#f9f97f", "N": "#ffe619", "Pg": "#fd9a52", "Cz": "#f2f91d",
    "K": "#7fc64e", "J": "#34b2c9", "Tr": "#812b92", "Mz": "#67c5ca",
    "P": "#f04028", "C": "#67a599", "D": "#cb8c37", "S": "#b3e1b6",
    "O": "#009270", "Cm": "#7fa056", "Pz": "#99c08d",
    "Pt": "#f73563", "A": "#f0047f", "pCm": "#f74370",
}


def _mix(*codes):
    """ICS 색 여럿을 고르게 섞는다. 두 시대에 걸친 단위의 색이다."""
    rgb = [tuple(int(ICS[c][i:i + 2], 16) for i in (1, 3, 5)) for c in codes]
    return "#%02x%02x%02x" % tuple(round(sum(v[i] for v in rgb) / len(rgb)) for i in range(3))


#: 일반화한 시대 기호(`GEN_GLG`, 36 가지) → (이름, 색). **차례가 범례의 차례다**
#: (젊은 것 → 옛 것). 제3기(`T`)는 ICS 에 없는 말이라 고진기·신진기를 섞었다.
AGE_CLASSES = [
    ("Cz", "신생대", ICS["Cz"]),
    ("CzMz", "중생대~신생대", _mix("Cz", "Mz")),
    ("Q", "제4기", ICS["Q"]),
    ("N", "신진기", ICS["N"]),
    ("T", "제3기", _mix("N", "Pg")),
    ("Pg", "고진기", ICS["Pg"]),
    ("TK", "백악기~제3기", _mix("Pg", "K")),
    ("Mz", "중생대", ICS["Mz"]),
    ("K", "백악기", ICS["K"]),
    ("KJ", "쥐라기~백악기", _mix("K", "J")),
    ("J", "쥐라기", ICS["J"]),
    ("JTr", "트라이아스기~쥐라기", _mix("J", "Tr")),
    ("Tr", "트라이아스기", ICS["Tr"]),
    ("MzPz", "고생대~중생대", _mix("Mz", "Pz")),
    ("TrP", "페름기~트라이아스기", _mix("Tr", "P")),
    ("Pz", "고생대", ICS["Pz"]),
    ("Pzu", "고생대 후기", _mix("D", "C", "P")),
    ("P", "페름기", ICS["P"]),
    ("PC", "석탄기~페름기", _mix("P", "C")),
    ("C", "석탄기", ICS["C"]),
    ("CD", "데본기~석탄기", _mix("C", "D")),
    ("D", "데본기", ICS["D"]),
    ("DS", "실루리아기~데본기", _mix("D", "S")),
    ("Pzl", "고생대 전기", _mix("Cm", "O", "S")),
    ("S", "실루리아기", ICS["S"]),
    ("SO", "오르도비스기~실루리아기", _mix("S", "O")),
    ("O", "오르도비스기", ICS["O"]),
    ("OCm", "캄브리아기~오르도비스기", _mix("O", "Cm")),
    ("Cm", "캄브리아기", ICS["Cm"]),
    ("PzpCm", "선캄브리아시대~고생대", _mix("Pz", "pCm")),
    ("pCm", "선캄브리아시대", ICS["pCm"]),
    ("Pt", "원생누대", ICS["Pt"]),
    ("A", "시생누대", ICS["A"]),
    ("und", "시대 미상", "#bdbdbd"),
]
AGE_BY_CODE = {code: (name, color) for code, name, color in AGE_CLASSES}

#: 암종(`TYPE`) → (이름, 색). 메타데이터가 풀지 않은 `x` 가 네 면 있다 — 지어내지
#: 않고 "기호 풀이 없음" 으로 둔다. 차례가 범례의 차례다.
ROCKS = {
    "i": (msg("관입 화성암"), "#e0301e"),
    "v": (msg("분출 화성암"), "#f28e2b"),
    "w": (msg("초염기성암·오피올라이트"), "#1b7837"),
    "e": (msg("풍성 퇴적물"), "#d8b365"),
    "x": (msg("기호 풀이 없음 (x)"), "#9e9e9e"),
}


def knows(name: str) -> bool:
    return name in LAYERS


def data_dir():
    root = settings.USGS_DIR
    return Path(root) / DATASET if root else None


def _files():
    root = data_dir()
    return [root / f"{DATASET}.{ext}" for ext in ("shp", "dbf", "prj")] if root else []


def available() -> bool:
    files = _files()
    return bool(files) and all(p.is_file() for p in files)


# ── 좌표계 (.prj) ──────────────────────────────────────────────────────

_PARAM = re.compile(r'PARAMETER\["([A-Za-z_0-9]+)",\s*(-?[\d.]+)\]')


def projection(wkt: str) -> dict:
    """`.prj`(ESRI WKT) → 람베르트 변수. 다른 투영이나 타원체면 멈춘다 — 모르고
    옮기면 지도가 수백 km 어긋난 채 그려진다."""
    if "Lambert_Conformal_Conic" not in wkt:
        raise Geo3alError("좌표계가 람베르트 정각원추가 아니다")
    if not re.search(r'SPHEROID\["WGS_1984",\s*6378137(\.0*)?,\s*298\.257223563', wkt):
        raise Geo3alError("타원체가 WGS84 가 아니다")
    p = {k.lower(): float(v) for k, v in _PARAM.findall(wkt)}
    try:
        return {"lon0": p["central_meridian"], "lat1": p["standard_parallel_1"],
                "lat2": p["standard_parallel_2"], "lat0": p.get("latitude_of_origin", 0.0),
                "fe": p.get("false_easting", 0.0), "fn": p.get("false_northing", 0.0)}
    except KeyError as exc:
        raise Geo3alError(f".prj 에 {exc} 가 없다") from exc


# ── dBASE ──────────────────────────────────────────────────────────────

def read_dbf(data: bytes) -> list:
    """dBASE III → 행 목록(dict). 글자는 ASCII 기호뿐이라 latin-1 로 읽는다."""
    count, header, width = struct.unpack("<4xIHH", data[:12])
    fields, at = [], 32
    while data[at] != 0x0D:
        name = data[at:at + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[at + 16]))
        at += 32
    rows = []
    for i in range(count):
        rec = data[header + i * width: header + (i + 1) * width]
        if rec[:1] == b"*":                     # 지운 행
            rows.append(None)
            continue
        row, pos = {}, 1
        for name, size in fields:
            row[name] = rec[pos:pos + size].decode("latin-1").strip()
            pos += size
        rows.append(row)
    return rows


# ── 셰이프파일 (다각형) ────────────────────────────────────────────────

def read_polygons(data: bytes):
    """셰이프파일 → 행마다 고리 목록(평면 좌표). 다각형(5)이 아니면 멈춘다."""
    if struct.unpack(">i", data[:4])[0] != 9994:
        raise Geo3alError("셰이프파일이 아니다")
    if struct.unpack("<i", data[32:36])[0] != 5:
        raise Geo3alError("다각형 셰이프파일이 아니다")
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        kind = struct.unpack("<i", data[body:body + 4])[0]
        rings = []
        if kind == 5:
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            for a, b in zip(starts, starts[1:]):
                rings.append([(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)])
        out.append(rings)
        at = body + words * 2
    return out


def _area(ring):
    """고리의 부호 있는 넓이. 셰이프파일은 바깥 고리가 시계 방향(음수)이다."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:])) / 2


def _inside(point, ring):
    x, y = point
    hit = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def group_rings(rings):
    """고리 목록 → 다각형 목록(바깥 고리 하나 + 구멍들). 구멍은 그것을 품은 바깥
    고리에 붙인다. OpenLayers 는 한 다각형의 둘째 고리부터 구멍으로 칠하므로, 바깥
    고리가 여럿인 행을 한 다각형에 몰아 담으면 섬이 구멍이 된다."""
    outers = [[r] for r in rings if _area(r) <= 0]
    holes = [r for r in rings if _area(r) > 0]
    if not outers:                               # 방향이 거꾸로 적힌 자료 — 다 바깥으로
        return [[r] for r in rings]
    for hole in holes:
        owner = next((o for o in outers if _inside(hole[0], o[0])), outers[0])
        owner.append(hole)
    return outers


def convert(shapes, rows, proj) -> list:
    """(평면 고리, dBASE 행, 투영) → 위경도 feature 목록. 속성은 기호 그대로 싣고
    이름·색은 레이어마다 붙인다(`_layer`)."""
    if len(shapes) != len(rows):
        raise Geo3alError(f"셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")

    def lonlat(point):
        lat, lon = crs.lcc_to_latlon(point[0], point[1], **proj)
        return [round(lon, DIGITS), round(lat, DIGITS)]

    features = []
    for index, (rings, row) in enumerate(zip(shapes, rows)):
        if row is None or not rings or row.get("GLG") in SKIP:
            continue
        polygons = [[[lonlat(p) for p in ring] for ring in polygon] for polygon in group_rings(rings)]
        geometry = ({"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1
                    else {"type": "MultiPolygon", "coordinates": polygons})
        features.append({"type": "Feature", "id": index, "geometry": geometry,
                         "properties": {"glg": row.get("GLG", ""), "gen": row.get("GEN_GLG", ""),
                                        "type": row.get("TYPE", "")}})
    return features


_memo = {}
_lock = threading.Lock()


def _load() -> list:
    """셋 파일을 읽어 옮긴 것. 파일이 그대로면 들고 있던 것을 준다."""
    if not available():
        raise Geo3alError(f"geo3al 파일이 없다: {data_dir()}")
    files = _files()
    stamp = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in files)
    with _lock:
        hit = _memo.get("features")
        if hit and hit[0] == stamp:
            return hit[1]
        shp, dbf, prj = files
        try:
            proj = projection(prj.read_text(encoding="latin-1"))
            features = convert(read_polygons(shp.read_bytes()), read_dbf(dbf.read_bytes()), proj)
        except (OSError, struct.error, IndexError, ValueError) as exc:
            raise Geo3alError(f"geo3al 파일을 읽지 못했다: {exc}") from exc
        _memo.clear()
        _memo["features"] = (stamp, features)
        log.info("geo3al — 면 %d 개를 위경도로 옮겼다", len(features))
        return features


def _age_name(code, lang):
    name = GLG.get(code)
    if name is None:
        return code or None                      # 모르는 기호는 기호 그대로
    return i18n.age_en(name) if lang == "en" else name


def _layer(name: str, lang: str):
    """레이어 하나의 feature 와 범례. 칠하는 열쇠가 `code` 다(`legendStyle`)."""
    by = LAYERS[name]["by"]
    features, counts = [], {}
    for f in _load():
        src = f["properties"]
        if by == "age":
            code = src["gen"]
            color = (AGE_BY_CODE.get(code) or (None, "#888888"))[1]
        else:
            code = src["type"]
            if code not in ROCKS:
                continue
            color = ROCKS[code][1]
        rock = ROCKS.get(src["type"])
        props = {"code": code, "color": color, "age": _age_name(src["glg"], lang),
                 "rock": i18n.t(rock[0], lang) if rock else None,
                 "glg": src["glg"] + (f" · {src['type']}" if src["type"] else "")}
        features.append(dict(f, properties={k: v for k, v in props.items() if v}))
        counts[code] = counts.get(code, 0) + 1
    if by == "age":
        table = [(code, i18n.age_en(label) if lang == "en" else label, color)
                 for code, label, color in AGE_CLASSES]
    else:
        table = [(code, i18n.t(label, lang), color) for code, (label, color) in ROCKS.items()]
    legend = [{"code": code, "label": label, "color": color, "count": counts[code]}
              for code, label, color in table if counts.get(code)]
    return features, legend


_bodies = {}


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이. 꼴은 `janmayen.body` 와 같다. 12 MB 남짓이라
    만든 것을 들고 있는다 — 파일이 바뀌면(`_load` 가 새로 읽으면) 버린다."""
    features = _load()
    key = (name, lang, id(features))
    hit = _bodies.get(key)
    if hit is not None:
        return hit
    items, legend = _layer(name, lang)
    out = {"type": "FeatureCollection", "labels": LABELS, "style": LAYERS[name]["style"],
           "legend": legend, "features": items}
    data = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with _lock:
        for old in [k for k in _bodies if k[2] != id(features)]:
            del _bodies[old]
        _bodies[key] = data
    return data


def bbox_of(features) -> list:
    """feature 목록의 위경도 범위 [서, 남, 동, 북]. 씨앗의 bbox 를 잴 때 쓴다."""
    west = south = math.inf
    east = north = -math.inf

    def walk(c):
        nonlocal west, south, east, north
        if c and isinstance(c[0], (int, float)):
            west, east = min(west, c[0]), max(east, c[0])
            south, north = min(south, c[1]), max(north, c[1])
        else:
            for x in c:
                walk(x)
    for f in features:
        walk(f["geometry"]["coordinates"])
    return [west, south, east, north]


# ── 높이 그래프의 지질 띠 (wetherilli 180) ────────────────────────────

_boxes = {}


def _feature_boxes(features) -> list:
    """면마다 [서, 남, 동, 북]. 파일이 바뀌면(`_load` 가 새로 읽으면) 다시 잰다."""
    key = id(features)
    hit = _boxes.get(key)
    if hit is None:
        hit = [bbox_of([f]) for f in features]
        with _lock:
            _boxes.clear()
            _boxes[key] = hit
    return hit


def units_along(name: str, points: list, lang: str = "ko") -> list:
    """위경도 점들 → 점마다 `(범례 이름, 색)` 또는 None. 칠하는 열쇠는 지도의 것(`_layer`)과 같다."""
    by = LAYERS[name]["by"]
    features = _load()
    boxes = _feature_boxes(features)
    out = []
    for lon, lat in points:
        found = None
        for f, (w, s, e, n) in zip(features, boxes):
            if not (w <= lon <= e and s <= lat <= n):
                continue
            geom = f["geometry"]
            polygons = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            if any(_inside((lon, lat), p[0]) and not any(_inside((lon, lat), h) for h in p[1:]) for p in polygons):
                found = f["properties"]
                break
        if found is None:
            out.append(None)
        elif by == "age":
            code = found["gen"]
            label, color = AGE_BY_CODE.get(code) or (code, "#888888")
            out.append((i18n.age_en(label) if lang == "en" else label, color))
        elif found["type"] in ROCKS:
            label, color = ROCKS[found["type"]]
            out.append((i18n.t(label, lang), color))
        else:
            out.append(None)
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "geo3al", "tag": "USGS", "title": "미국 지질조사국"},
]
