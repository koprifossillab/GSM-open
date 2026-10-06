"""KIGAM 5만 지질도의 자세 기호 — 층리·엽리·편리·절리의 자리와 값.

**문이 아니다.** 상류를 부르지 않고, 받아 둔 파일(`settings.KIGAM50K_DIR`)을 읽는다.
파일은 KIGAM GeoServer WFS 에서 한 번 받아 둔 것이다 — `raw/<YYYYMMDD>/<이름>.geojson.gz`
와 `manifest.json`(docs/KIGAM_5만_구조요소.md §5). 날짜 폴더가 여럿이면 **가장 새 것**을 읽는다.

5만 지질도 타일에는 이 기호가 그림으로 박혀 있어 누를 수 없다. 여기서 자리와 값을
주면 화면이 커서를 바꾸고 팝업을 띄운다 (jikhanjung 004). 층리 뺀 판에서는 그 자리를
찾는 길이 된다.

값을 읽는 법 (§4):
- `roangle` 은 **경사 방향**이다. 주향은 `roangle − 90°`(오른손 법칙)
- `strike`·`dip` 은 사분면(`NW`·`SW`)뿐이다. 팝업에 원문으로 곁들인다
- `dipangle = -99` 는 경사 미상. 0–90 밖의 값은 적지 않는다
"""
import gzip
import json
import math
import threading
from pathlib import Path

from django.conf import settings

from .i18n import msg

#: 받아 둔 레이어 가운데 자세 기호. 차례가 화면에서 겹칠 때의 차례다
KINDS = ("bedding", "foliation", "schistosity", "joint")

#: `fetch_kigam50k` 가 받는 레이어 — 2026-09-30 에 손으로 받은 19 개와 같다(docs/KIGAM_5만_구조요소.md §3). 지질 경계(17 만)·
#: 암상 면(7 만)은 받지 않는다 — 크고 WMS 그림으로 이미 보인다 (jikhanjung P01 §4·§8)
FETCH = ("bedding", "foliation", "schistosity", "joint", "flowstructure", "cleavage", "lineation", "mineralarray",
         "foldaxis", "fold", "fault", "fossil", "sample", "mine", "oretype", "mineralspring", "alterationzone",
         "metamorphismzone", "frame")

#: 한 번에 내주는 점의 수. 줌 11 의 한 화면(≈ 40 km)에 많아야 천 남짓이다
LIMIT = 5000

_lock = threading.Lock()
_cache = {"folder": None, "rows": None}


def root() -> Path:
    return Path(settings.KIGAM50K_DIR)


def latest() -> Path | None:
    """가장 새 날짜 폴더. 없으면 None."""
    raw = root() / "raw"
    if not raw.is_dir():
        return None
    days = sorted(p for p in raw.iterdir() if p.is_dir() and p.name.isdigit())
    return days[-1] if days else None


def available() -> bool:
    folder = latest()
    return bool(folder) and any((folder / f"{k}.geojson.gz").exists() for k in KINDS)


def _row(kind, feature):
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "MultiPoint":
        coords = coords[0] if coords else None
    if not coords or len(coords) < 2:
        return None
    p = feature.get("properties") or {}
    ro = p.get("roangle")
    dip = p.get("dipangle")
    return {
        "lon": round(float(coords[0]), 6),
        "lat": round(float(coords[1]), 6),
        "kind": kind,
        "type": p.get("type") or "",
        "dipdir": (round(float(ro)) % 360) if isinstance(ro, (int, float)) else None,
        "dip": dip if isinstance(dip, (int, float)) and 0 <= dip <= 90 else None,
        "quad": "/".join(q for q in (p.get("strike"), p.get("dip")) if q),
        "sheet": p.get("mapname") or "",
        "sheet_no": p.get("mapidx") or "",
    }


def load() -> list:
    """네 레이어를 한 줄로. 폴더가 바뀌면 다시 읽는다 — 새 판을 받으면 재기동 없이 따라간다."""
    folder = latest()
    with _lock:
        if folder is not None and _cache["folder"] == folder and _cache["rows"] is not None:
            return _cache["rows"]
        rows = []
        if folder is not None:
            for kind in KINDS:
                path = folder / f"{kind}.geojson.gz"
                if not path.exists():
                    continue
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    for feature in json.load(fh).get("features") or []:
                        row = _row(kind, feature)
                        if row:
                            rows.append(row)
        _cache.update(folder=folder, rows=rows)
        return rows


def within(west: float, south: float, east: float, north: float, limit: int = LIMIT) -> tuple[list, bool]:
    """범위(위경도) 안의 점. (점들, 잘렸나)."""
    out = []
    for row in load():
        if west <= row["lon"] <= east and south <= row["lat"] <= north:
            out.append(row)
            if len(out) >= limit:
                return out, True
    return out, False


def strike_of(dipdir):
    """경사 방향 → 주향(오른손 법칙). 없으면 None."""
    return None if dipdir is None else (dipdir - 90) % 360


def fetched_on() -> str:
    """받은 날 — 폴더 이름(YYYYMMDD)을 YYYY-MM-DD 로."""
    folder = latest()
    if folder is None:
        return ""
    n = folder.name
    return f"{n[:4]}-{n[4:6]}-{n[6:8]}" if len(n) == 8 else n


# ── 장미도 (wetherilli 197, jikhanjung P01 §5 의 5 단계) ─────────────
#
# 도폭 하나(또는 고른 범위)의 층리·엽리·편리·절리 방향 분포. 서버가 각도를 칸으로 세어 주고 화면이 SVG 로 그린다 —
# 점을 다 보내지 않아 가볍다. 주향은 축(180° 대칭)이라 10° 칸 열여덟, 경사 방향은 10° 칸 서른여섯, 경사는 10° 칸 아홉이다.

#: 도폭을 찾을 때 누른 자리에서 가장 가까운 기호까지 볼 거리(°) — 5만 도폭 한 장이 15′(0.25°)다
SHEET_REACH = 0.25


def sheet_at(lon: float, lat: float):
    """누른 자리의 도폭 `(번호, 이름)` — 그 자리를 덮는 **도폭 틀**(wetherilli 199)이다. 틀 파일이 없으면 가장 가까운 자세
    기호에 적힌 도폭으로 정한다(197). 둘 다 없으면 None."""
    framed = frame_at(lon, lat)
    if framed:
        return framed
    best, best_d = None, SHEET_REACH ** 2
    cos = max(0.2, math.cos(math.radians(lat)))
    for row in load():
        d = ((row["lon"] - lon) * cos) ** 2 + (row["lat"] - lat) ** 2
        if d < best_d and row["sheet_no"]:
            best, best_d = row, d
    return (best["sheet_no"], best["sheet"]) if best else None


def in_sheet(sheet_no: str) -> list:
    return [row for row in load() if row["sheet_no"] == sheet_no]


def rose(rows: list) -> dict:
    """`{"n": {갈래: 수}, "strike": {갈래: [18]}, "dipdir": {갈래: [36]}, "dip": {갈래: [9]}, "nodip": {갈래: 수}}`.
    경사 방향이 없는 기호는 장미에서, 경사가 없는 기호(`-99`)는 경사 분포에서 빠진다(`nodip` 으로 센다)."""
    out = {"n": {}, "strike": {}, "dipdir": {}, "dip": {}, "nodip": {}}
    for kind in KINDS:
        mine = [r for r in rows if r["kind"] == kind]
        if not mine:
            continue
        strike, dipdir, dip = [0] * 18, [0] * 36, [0] * 9
        nodip = 0
        for r in mine:
            if r["dipdir"] is not None:
                dipdir[int(r["dipdir"]) % 360 // 10] += 1
                strike[int(strike_of(r["dipdir"])) % 180 // 10] += 1
            if r["dip"] is None:
                nodip += 1
            else:
                dip[min(8, int(r["dip"]) // 10)] += 1
        out["n"][kind] = len(mine)
        out["strike"][kind], out["dipdir"][kind], out["dip"][kind] = strike, dipdir, dip
        out["nodip"][kind] = nodip
    return out


# ── 레이어 — 화석산지·시료·광산·도폭 틀 (jikhanjung P01 §5 의 3·4 단계, wetherilli 199) ─────────
#
# 받아 둔 파일에서 점·면을 극지연구소 파일 레이어와 같은 꼴(`style: class` · `legend` · `labels` · `links`)로 낸다. 레이어군은
# 한국 탭의 "지질 구조 (5만)"(P01 §2·§8 의 기본안 — 사람이 고친다). 단층·습곡·변질대는 다음이다

#: 선구조·신장광물·습곡축의 팝업 열 (wetherilli 223) — `roangle` 이 침강 방향, `tangle` 이 침강각, `trend` 는 사분면 원문
LINEAR_COLS = (("type", "갈래"), ("roangle", "침강 방향"), ("tangle", "침강각"), ("trend", "방향 (사분면)"), ("comt", "설명"),
               ("mapname", "도폭"), ("mapidx", "도폭 번호"))
#: 방향 기호의 모양 — 이 모양의 갈래는 `roangle` 을 `azimuth` 로 싣는다
ROTATED = ("arrow", "strike")
#: `roangle` 에 더할 각 (wetherilli 223). 신장광물의 `roangle` 은 침강 방향이 아니라 엽리의 주향이다 — `roangle + 90` 이 `plunge` 사분면에
#: 드는 것이 443 점 가운데 89 %, `roangle` 그대로는 4 % 다. 유동구조는 층리처럼 `roangle` 이 경사 방향이다(97 %). 선구조·습곡축은 사분면이
#: 드물어(49 점) 층리의 읽기를 따른다
ROTATE_OFFSET = {"kigam50k:mineralarray": 90}

#: 레이어 → (파일, 팝업 열, 갈래 표). 갈래 표는 (코드, `type` 값들, 범례 글, 색, 모양). 값이 어디에도 없으면 마지막 갈래
LAYERS = {
    "kigam50k:fossil": ("fossil", (("type", "갈래"), ("comt", "설명"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("foram", ("유공충",), msg("유공충"), "#2c7fb8", "diamond"),
        ("plant", ("식물화석",), msg("식물화석"), "#31a354", "diamond"),
        ("fossil", (), msg("화석산지"), "#8c510a", "diamond"),
    )),
    "kigam50k:sample": ("sample", (("type", "갈래"), ("comt", "시료"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("shrimp", ("SHRIMP",), msg("SHRIMP 연대"), "#d7301f", "square"),
        ("kar", ("K-Ar",), msg("K-Ar 연대"), "#fc8d59", "square"),
        ("age", ("연대측정", "연대측정시료", "암석연대측정시료위치", "지질연대"), msg("연대측정"), "#7a0177", "square"),
        ("geochem", ("지구화학분",), msg("지구화학 분석"), "#1d91c0", "square"),
        ("other", (), msg("그 밖의 시료"), "#969696", "square"),
    )),
    "kigam50k:mine": ("mine", (("type", "갈래"), ("comt", "설명"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("mine", ("광산", "채굴지"), msg("광산·채굴지"), "#636363", "dot"),
        ("adit", ("갱도", "갱구"), msg("갱도·갱구"), "#252525", "dot"),
        ("closed", (), msg("폐광·휴광"), "#bdbdbd", "dot"),
    )),
    # 선·면 (wetherilli 202) — 단층·습곡은 선(`stroke`: 굵기·끊김은 표의 마지막 칸), 변질대·변성대는 면. 광종은 점
    "kigam50k:fault": ("fault", (("type", "갈래"), ("fault_kr", "단층 이름"), ("dipangle", "경사"), ("dipazi", "경사 방향"),
                                 ("comt", "설명"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("thrust", ("드러스트",), msg("드러스트"), "#c0392b", "stroke", {"width": 1.8}),
        ("thrust_q", ("추정드러스트", "추정드러스"), msg("추정 드러스트"), "#c0392b", "stroke", {"width": 1.4, "dash": [5, 4]}),
        ("normal", ("정단층",), msg("정단층"), "#2166ac", "stroke", {"width": 1.6}),
        ("normal_q", ("추정정단층",), msg("추정 정단층"), "#2166ac", "stroke", {"width": 1.3, "dash": [5, 4]}),
        ("strike", ("주향이동단층",), msg("주향이동단층"), "#762a83", "stroke", {"width": 1.6}),
        ("strike_q", ("추정주향이동단층",), msg("추정 주향이동단층"), "#762a83", "stroke", {"width": 1.3, "dash": [5, 4]}),
        ("fault_q", ("추정단층",), msg("추정 단층"), "#3a3a3a", "stroke", {"width": 1.1, "dash": [5, 4]}),
        ("fault", (), msg("단층"), "#1a1a1a", "stroke", {"width": 1.4}),
    )),
    "kigam50k:fold": ("fold", (("type", "갈래"), ("comt", "설명"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("anticline", ("배사",), msg("배사"), "#d6604d", "stroke", {"width": 1.8}),
        ("syncline", ("향사",), msg("향사"), "#4393c3", "stroke", {"width": 1.8}),
        ("o_anticline", ("역전등사배사",), msg("역전 등사 배사"), "#b2182b", "stroke", {"width": 1.8, "dash": [8, 3]}),
        ("o_syncline", ("역전등사향사",), msg("역전 등사 향사"), "#2166ac", "stroke", {"width": 1.8, "dash": [8, 3]}),
        ("p_anticline", ("침강배사",), msg("침강 배사"), "#f4a582", "stroke", {"width": 1.6}),
        ("p_syncline", ("침강향사",), msg("침강 향사"), "#92c5de", "stroke", {"width": 1.6}),
        ("other", (), msg("그 밖의 습곡"), "#7b3294", "stroke", {"width": 1.6}),
    )),
    "kigam50k:oretype": ("oretype", (("type", "광종"), ("광종", "광종 기호"), ("comt", "설명"), ("mapname", "도폭"),
                                     ("mapidx", "도폭 번호")), (
        ("precious", ("금", "은"), msg("금·은"), "#e6ab02", "diamond"),
        ("coal", ("석탄", "무연탄", "갈탄"), msg("석탄"), "#252525", "square"),
        ("iron", ("철", "티탄철", "자철"), msg("철"), "#a6611a", "dot"),
        ("base", ("동", "연(납)", "아연", "연", "연·아연", "중석", "몰리브덴", "니켈", "코발트", "망간", "혼합광"),
         msg("동·연·아연 따위"), "#1b9e77", "dot"),
        ("other", (), msg("비금속·그 밖"), "#7570b3", "dot"),
    )),
    "kigam50k:zones": (("alterationzone", "metamorphismzone"),
                       (("type", "갈래"), ("lithoname", "지층"), ("lithoidx", "지층 기호"), ("age", "시대"),
                        ("refrock", "대표 암상"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("thermal", ("열변성대",), msg("열변성대"), "#e08214", "square"),
        ("contact_alt", ("접촉변질대",), msg("접촉변질대"), "#b35806", "square"),
        ("alteration", ("변질대",), msg("변질대"), "#8073ac", "square"),
        ("hydrothermal", ("열수광화대",), msg("열수광화대"), "#d01c8b", "square"),
        ("contact_meta", ("접촉변성대",), msg("접촉변성대"), "#542788", "square"),
        ("other", (), msg("그 밖의 변질·변성대"), "#999999", "square"),
    )),
    # 방향 기호가 드는 점 (wetherilli 223) — 선구조 셋은 침강 방향의 화살(`arrow`), 유동구조는 주향선과 경사 방향의 눈금(`strike`).
    # 돌리는 각은 `roangle`(선구조는 침강 방향, 유동구조는 경사 방향)이고 `azimuth` 로 싣는다
    "kigam50k:lineation": ("lineation", LINEAR_COLS, (
        ("l1", ("1차선구조",), msg("1차 선구조"), "#08519c", "arrow"),
        ("l2", ("2차선구조",), msg("2차 선구조"), "#3182bd", "arrow"),
        ("l3", ("3차선구조",), msg("3차 선구조"), "#6baed6", "arrow"),
        ("lineation", ("선구조",), msg("선구조"), "#08306b", "arrow"),
        ("other", (), msg("그 밖의 선구조"), "#737373", "arrow"),
    )),
    "kigam50k:mineralarray": ("mineralarray", (("type", "갈래"), ("roangle", "침강 방향"), ("tangle", "침강각"),
                                               ("plunge", "침강 방향 (사분면)"), ("comt", "설명"), ("mapname", "도폭"),
                                               ("mapidx", "도폭 번호")), (
        ("stretch", ("신장광물",), msg("신장광물"), "#a63603", "arrow"),
        ("stretch_q", ("경사미상 신장광물",), msg("침강각 미상 신장광물"), "#fd8d3c", "arrow"),
        ("other", (), msg("그 밖의 신장광물"), "#737373", "arrow"),
    )),
    "kigam50k:foldaxis": ("foldaxis", LINEAR_COLS, (
        ("axis", ("습곡축",), msg("습곡축"), "#54278f", "arrow"),
        ("minor", ("소습곡축",), msg("소습곡축"), "#807dba", "arrow"),
        ("other", (), msg("2·3차 습곡축"), "#bcbddc", "arrow"),
    )),
    "kigam50k:flowstructure": ("flowstructure", (("type", "갈래"), ("roangle", "경사 방향"), ("dipangle", "경사"),
                                                 ("comt", "설명"), ("mapname", "도폭"), ("mapidx", "도폭 번호")), (
        ("flow", ("유동구조",), msg("유동구조"), "#006d2c", "strike"),
        ("flowband", ("유상구조",), msg("유상구조"), "#41ab5d", "strike"),
        ("other", (), msg("수직 유동구조"), "#00441b", "strike"),
    )),
    "kigam50k:frame": ("frame", (("mapname", "도폭"), ("mapidx", "도폭 번호"), ("surveyor", "조사자"),
                                 ("suryear", "조사연도"), ("comt", "비고"), ("doi", "DOI")), (
        ("frame", (), msg("5만 도폭"), "#8a6d3b", "square"),
    )),
}
LINKS = ("doi",)
ATTRIBUTION = "KIGAM 1:50,000 digital geological map (CC BY-NC) · data.kigam.re.kr"
#: 소수 다섯 자리 — 1 m 남짓. 단층 덩이가 여섯 자리면 4 MB, 다섯 자리면 3.4 MB(줄이면 0.6 MB)다 (wetherilli 202)
DIGITS = 5


def knows_file(name: str) -> bool:
    return name in LAYERS


def _files(name: str) -> tuple:
    files = LAYERS[name][0]
    return files if isinstance(files, tuple) else (files,)


def file_available(name: str) -> bool:
    folder = latest()
    return bool(folder) and all((folder / f"{f}.geojson.gz").exists() for f in _files(name))


#: 선이 많아 화면이 한 장으로 굽는 것 (`render: image`, 중국 geo3al 과 같다) — 끌 때 다시 칠하지 않는다
IMAGE = {"kigam50k:fault", "kigam50k:fold"}


def _features(kind: str) -> list:
    folder = latest()
    with gzip.open(folder / f"{kind}.geojson.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh).get("features") or []


def _round(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), DIGITS), round(float(coords[1]), DIGITS)]
    return [_round(c) for c in coords]


def _code(table, value) -> str:
    for code, values, *_ in table:
        if value in values:
            return code
    return table[-1][0]


_body_cache = {}


def layer_body(name: str) -> bytes:
    """레이어 하나의 GeoJSON. 파일이 없으면 FileNotFoundError. 단층(8 263 선)은 짓는 데 1 초 남짓이라 받아 둔 판(폴더)마다 한 번만
    짓는다 (wetherilli 202)."""
    if not file_available(name):
        raise FileNotFoundError(name)
    key = (name, str(latest()))
    with _lock:
        hit = _body_cache.get(key)
    if hit is None:
        hit = _build(name)
        with _lock:
            _body_cache[key] = hit
    return hit


def _build(name: str) -> bytes:
    _, cols, table = LAYERS[name]
    out, counts = [], {}
    for i, f in enumerate(f for kind in _files(name) for f in _features(kind)):
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        if geom.get("type") == "MultiPoint":
            geom = {"type": "Point", "coordinates": _round(coords[0])}
        else:
            geom = {"type": geom.get("type"), "coordinates": _round(coords)}
        p = f.get("properties") or {}
        props = {key: str(p[key]).strip() for key, _ in cols if p.get(key) not in (None, "")}
        # 단층의 경사 0 은 "적지 않음" 이다 — 경사·경사 방향이 0 이거나 없으면 뺀다
        for key in ("dipangle", "dipazi"):
            if props.get(key) in ("0", "0.0"):
                del props[key]
        if "doi" in props and not props["doi"].lower().startswith(("http://", "https://")):
            del props["doi"]
        # 각은 0–90 만 적는다(-99 는 미상). "경사미상" 갈래의 0 도 미상이다 (wetherilli 223)
        for key in ("tangle", "dipangle"):
            if key in props:
                value = p.get(key)
                if not isinstance(value, (int, float)) or not 0 <= value <= 90 or (value == 0 and "미상" in str(p.get("type"))):
                    del props[key]
        props["code"] = _code(table, p.get("type"))
        shape = next((row[4] for row in table if row[0] == props["code"]), None)
        if shape in ROTATED and isinstance(p.get("roangle"), (int, float)):
            props["azimuth"] = (round(p["roangle"]) + ROTATE_OFFSET.get(name, 0)) % 360
            props["roangle"] = str(props["azimuth"])
        counts[props["code"]] = counts.get(props["code"], 0) + 1
        out.append({"type": "Feature", "id": i, "geometry": geom, "properties": props})
    legend = [dict({"code": code, "label": str(label), "color": color, "shape": shape, "count": counts[code]},
                   **(rest[0] if rest else {}))
              for code, _, label, color, shape, *rest in table if counts.get(code)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": dict(cols), "links": list(LINKS),
                       "legend": legend, "features": out}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def frame_at(lon: float, lat: float):
    """누른 자리를 덮는 도폭 틀 `(번호, 이름)` — 틀 파일이 없거나 틀 밖이면 None (wetherilli 199)."""
    from .geomap import polygon_contains
    folder = latest()
    if folder is None or not (folder / "frame.geojson.gz").exists():
        return None
    for f in _frames(folder):
        geom = f.get("geometry") or {}
        polys = geom.get("coordinates") or []
        if geom.get("type") == "Polygon":
            polys = [polys]
        for poly in polys:
            rings = [[v for pt in ring for v in pt[:2]] for ring in poly]
            if polygon_contains(rings, lon, lat):
                p = f.get("properties") or {}
                if p.get("mapidx"):
                    return p["mapidx"], p.get("mapname") or ""
    return None


_frame_cache = {"folder": None, "rows": None}


def _frames(folder) -> list:
    with _lock:
        if _frame_cache["folder"] != folder:
            _frame_cache.update(folder=folder, rows=_features("frame"))
        return _frame_cache["rows"]


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "kigam50k", "tag": "KIGAM", "title": "한국지질자원연구원 5만 수치지질도"},
]
