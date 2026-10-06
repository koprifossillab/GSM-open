"""노던테리토리 지질도 — NTGS 1:250만 해석 지질도와 단층을 우리 디스크에서 읽는다 (wetherilli 361).

노던테리토리 지질조사소(NTGS)는 지도 서비스를 열어 두지 않았다 — `geoscience.nt.gov.au/geoserver`·`/arcgis` 는 404 이고 STRIKE 화면은
주소를 감춘다. 대신 주 열린자료(`data.nt.gov.au`)에 **"Northern Territory Geological Map (Interp) 2500K"·"… Geological Faults 2500K"** 가
셰이프 ZIP 으로 있다(**CC BY** — 목록이 판 번호 없이 "Creative Commons Attribution" 이라 적는다, 4.4 MB·0.2 MB). 얀마옌(`janmayen.py`)처럼 받아 두고 한 덩이로 화면에 준다. 상류가 아니라 파일이라 문이 아니다.
원본은 NAS `N:\\GSM\\sources\\australia\\nt_geology\\`, 서버는 `GSM_NTGEO_DIR`(기본 `<DB 옆>/nt_geology`)에 ZIP 둘을 그대로 둔다.
파일이 없어도 뷰어는 돌고 레이어 패널에 안내가 뜬다.

- 좌표는 GDA94 경위도(EPSG:4283) — WGS84 와 1 m 남짓이라 옮기지 않는다
- 면 1 975 개(바다 넷은 뺀다)·꼭짓점 38 만 — 1:250만에서 0.5 mm 는 1.2 km 라 **0.002°(200 m 남짓)로 줄여**(Douglas–Peucker, `tectonics.simplify`) 화면이 한 장으로 굽는다
- **색은 우리가 붙인다** — 자료에 색 열이 없다. 대부분이 원생누대라 ICS 의 기(period) 색만으로는 70 % 가 한 분홍이 된다. 원생누대의 기
  (스타테로스기·오로세이라기 …)까지 ICS 색을 쓰고, 기가 없으면 대·누대의 색. 범례는 그 색의 칸이다
- 속성: 기호·단위 이름·암석·암석 갈래·지질구·시대(ICS 영어 → 한국어판에서 옮긴다)·연대 범위(Ma)
- 단층 849 개 — 해석(지구물리)은 끊은 선, 나머지(지도에서 옮긴 것)는 실선
"""
import json
import logging
import threading
import zipfile
from pathlib import Path

from django.conf import settings

from . import geo3al, i18n, moonmap, tectonics
from .i18n import msg

log = logging.getLogger(__name__)

UNITS = "ntgs:geology"
FAULTS = "ntgs:faults"
FILES = {UNITS: "GEO_INTERP_2500K_shp.zip", FAULTS: "GEO_FAULTS_2500K_shp.zip"}
SOURCE_URL = "https://data.nt.gov.au/dataset/strike---northern-territory-geological-map-interp-2500k"
ATTRIBUTION = ('<a href="' + SOURCE_URL + '" target="_blank" rel="noopener">© Northern Territory Government</a> '
               "(Northern Territory Geological Survey, 1:2.5M, CC BY)")
TOLERANCE = 0.002
DIGITS = 4

#: ICS 국제층서표 v2024/12 의 색 — 기·대·누대. 원생누대는 기까지
ICS = {
    "Quaternary": "#F9F97F", "Neogene": "#FFE619", "Paleogene": "#FD9A52", "Cenozoic": "#F2F91D",
    "Cretaceous": "#7FC64E", "Jurassic": "#34B2C9", "Triassic": "#812B92", "Mesozoic": "#67C5CA",
    "Permian": "#F04028", "Carboniferous": "#67A599", "Devonian": "#CB8C37", "Silurian": "#B3E1B6",
    "Ordovician": "#009270", "Cambrian": "#7FA056", "Palaeozoic": "#99C08D", "Phanerozoic": "#9AD9DD",
    "Ediacaran": "#FED96A", "Cryogenian": "#FECC5C", "Tonian": "#FEBF4E", "Neoproterozoic": "#FEB342",
    "Stenian": "#FED99A", "Ectasian": "#FDCC8A", "Calymmian": "#FDC07A", "Mesoproterozoic": "#FDB462",
    "Statherian": "#F875A7", "Orosirian": "#F76898", "Rhyacian": "#F75B89", "Siderian": "#F74F7C",
    "Palaeoproterozoic": "#F74370", "Proterozoic": "#F73563", "Archaean": "#F0047F",
}
#: 범례의 차례 — 젊은 것부터
ORDER = list(ICS)
LABELS = {"symbol": "기호", "name": "단위", "rock": "암석", "class": "암석 갈래", "region": "지질구", "age": "지질시대", "range": "연대",
          "zone": "변형대", "derivation": "근거", "data": "자료"}
FAULT_STYLES = {"interp": {"color": "#3b1f5e", "width": 1.2, "dash": [5, 4]}, "mapped": {"color": "#3b1f5e", "width": 1.6}}


class NtGeoError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in FILES


def root() -> Path:
    return Path(settings.NTGEO_DIR)


def available(name: str) -> bool:
    return knows(name) and (root() / FILES[name]).is_file()


def age_of(row: dict) -> str:
    """가장 자세한 ICS 이름 — 기, 없으면 대, 없으면 누대. "Ectasian-Stenian" 같은 걸침은 그대로 둔다(색은 앞의 것)"""
    return row.get("PERIOD") or row.get("ERA") or row.get("EON") or ""


def color_of(age: str) -> str:
    return ICS.get(age.split("-")[0].strip(), "#cccccc")


def _round(points):
    return [[round(x, DIGITS), round(y, DIGITS)] for x, y in points]


def _members(name: str):
    with zipfile.ZipFile(root() / FILES[name]) as zf:
        stem = Path(FILES[name]).stem.removesuffix("_shp")
        try:
            return zf.read(stem + ".shp"), zf.read(stem + ".dbf")
        except KeyError as exc:
            raise NtGeoError(f"{FILES[name]} 에 {stem}.shp·.dbf 가 없다") from exc


def _units() -> dict:
    shp, dbf = _members(UNITS)
    shapes, rows = geo3al.read_polygons(shp), geo3al.read_dbf(dbf)
    if len(shapes) != len(rows):
        raise NtGeoError(f"셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
    features, counts = [], {}
    for rings, row in zip(shapes, rows):
        if not row or not rings or row.get("SYMBOL") == "sea":      # 아라푸라해의 바다 면 넷 — 지질이 아니다
            continue
        polys = []
        for poly in geo3al.group_rings(rings):
            # 작은 단위는 줄이면 고리가 무너진다 — 그때는 원래 고리를 둔다(작아서 꼭짓점도 적다)
            kept = [_round(simple if len(simple := tectonics.simplify(r, TOLERANCE)) >= 4 else r) for r in poly]
            kept = [r for r in kept if len(r) >= 4]
            if kept:
                polys.append(kept)
        if not polys:
            continue
        age = age_of(row)
        key = age.split("-")[0].strip() if age.split("-")[0].strip() in ICS else "?"
        counts[key] = counts.get(key, 0) + 1
        props = {"code": key, "color": color_of(age), "symbol": row.get("SYMBOL"), "name": row.get("STRAT_UNIT"),
                 "rock": row.get("LITHDESCN1"), "class": row.get("LITHCLASS"), "region": row.get("GEOLREGION"),
                 "age": age, "range": row.get("AGERANGE")}
        features.append({"type": "Feature", "properties": {k: v for k, v in props.items() if v},
                         "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    legend = [{"code": k, "age": k, "color": ICS.get(k, "#cccccc"), "count": counts[k]}
              for k in sorted(counts, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER))]
    return {"features": features, "legend": legend}


def _faults() -> dict:
    shp, dbf = _members(FAULTS)
    lines, rows = moonmap._read_lines(shp), geo3al.read_dbf(dbf)
    if len(lines) != len(rows):
        raise NtGeoError(f"셰이프({len(lines)})와 속성({len(rows)})의 수가 다르다")
    features, counts = [], {}
    for parts, row in zip(lines, rows):
        if not row or not parts:
            continue
        kind = "interp" if row.get("DERIVATION") == "Interpreted" or row.get("DATA") == "Geophysics" else "mapped"
        counts[kind] = counts.get(kind, 0) + 1
        props = {"code": kind, "name": row.get("NAME"), "zone": row.get("DEFZONE"), "derivation": row.get("DERIVATION"),
                 "data": row.get("DATA")}
        features.append({"type": "Feature", "properties": {k: v for k, v in props.items() if v},
                         "geometry": {"type": "MultiLineString", "coordinates": [_round(tectonics.simplify(p, TOLERANCE)) for p in parts]}})
    legend = [dict(FAULT_STYLES[k], code=k, count=counts[k], label=k) for k in ("mapped", "interp") if k in counts]
    return {"features": features, "legend": legend}


_cache, _lock = {}, threading.Lock()


def _load(name: str) -> dict:
    """옮긴 것을 프로세스가 든다 — ZIP 의 크기·고친 때가 같으면 다시 읽지 않는다(얀마옌과 같은 까닭)"""
    path = root() / FILES[name]
    st = path.stat()
    mark = (st.st_size, st.st_mtime_ns)
    with _lock:
        held = _cache.get(name)
        if held and held[0] == mark:
            return held[1]
    try:
        loaded = _units() if name == UNITS else _faults()
    except (zipfile.BadZipFile, geo3al.Geo3alError, moonmap.MoonMapError) as exc:
        raise NtGeoError(str(exc)) from exc
    with _lock:
        _cache[name] = (mark, loaded)
    return loaded


LEGEND_TEXT = {"interp": msg("해석 단층 (지구물리)"), "mapped": msg("지도의 단층")}


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `janmayen.body` 와 같다. 시대만 옮긴다(한국어판은 ICS 한글판, 영어판은 그대로)"""
    if not knows(name):
        raise NtGeoError(f"모르는 레이어다: {name}")
    loaded = _load(name)
    features = loaded["features"]
    if name == UNITS:
        if lang == "ko":
            features = [dict(f, properties=dict(f["properties"], age=i18n.age_ko(f["properties"]["age"])))
                        if "age" in f["properties"] else f for f in features]
        legend = [dict(r, label=(i18n.age_ko(r["age"]) if lang == "ko" else r["age"]) if r["age"] != "?" else "?") for r in loaded["legend"]]
        style = "unit"
    else:
        legend = [dict(r, label=i18n.t(LEGEND_TEXT[r["code"]], lang)) for r in loaded["legend"]]
        style = "line"
    out = {"type": "FeatureCollection", "labels": LABELS, "style": style, "legend": legend, "features": features}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
