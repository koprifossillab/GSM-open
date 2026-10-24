"""SCAR KGIS 킹조지섬 지형 DB로 나가는 문 — 셰이프 zip 열여섯을 받아 두고, 남극 탭에 일곱 레이어로 한 덩이씩 낸다 (wetherilli 424).

SCAR KGIS(King George Island GIS Project)는 프라이부르크대가 2007 년까지 돌린 킹조지섬의 통합 지형 DB 다. 서비스는 닫혔고 남은 셰이프를
AWI 가 PANGAEA 에 묶어 두었다 — **PANGAEA.837976, CC BY 3.0**(데이터셋 머리의 `License`, 2026-10-24 확인). 파일 하나하나는 AWI 저장소
ePIC 의 핸들(`hdl:10013/epic.44322.d001`…`d016`)이고 `epic.awi.de/id/eprint/36527/<n>/<이름>.zip` 으로 풀린다.

- **받는 길은 여기 하나다** — `manage.py fetch_kgis` 가 핸들을 1 초 간격으로 풀어 zip 을 `GSM_KGIS_DIR`(기본 `<DB 옆>/kgis`)에 둔다.
  한 번 받으면 끝이다(2007 년에 멈췄다). 원본은 NAS `N:\\GSM\\sources\\kgis\\`. 화면이 부를 때 상류를 타지 않는다
- 좌표는 **WGS84 경위도**(.prj 가 EPSG:4326) — 옮기지 않는다. 셰이프는 GDAL 없이 `geo3al`·`moonmap` 의 읽기로 읽는다
- **바턴반도(세종기지)가 든다** — 건물 43(한국 23)·등고선 159·길 19·세종기지·연료 탱크·물길 133·호수 86(2026-10-24 받아 세었다)
- 섬 전체의 꼭짓점이 많다(등고선 27 만). 0.00002°(남북 2 m·동서 1 m)로 줄인다 — 현장 축척에서도 꺾임이 남는다
- 레이어는 일곱 — 등고선·해안선·얼음 없는 땅·물길과 호수·기지와 시설·길·보호구역. **지명(Placename)은 싣지 않는다** — 같은 SCAR
  지명사전의 새 판이 이미 남극 탭의 이름표다(`scar.py`, KGIS 의 `SCAR_GAZ_I` 가 그 번호다)
- **낡았다(2007)** — 빙하 끝·해안선은 그 뒤로 물러났고, 보호구역은 그 해의 경계다. 설명과 출처 줄에 적는다
- 속성의 글자는 UTF-8 인데 `geo3al.read_dbf` 가 latin-1 로 읽는다 — 되돌려 읽는다(`_text`)

꼴은 극지연구소의 점 레이어(`kopri.py`)와 같다 — `style: class`, 갈래마다 `code`, 덩이에 `legend`([{code, label, color, shape}]).
"""
import json
import logging
import struct
import threading
import time
import zipfile
from pathlib import Path

import requests
from django.conf import settings

from . import geo3al, moonmap, tectonics, usage
from .i18n import msg

log = logging.getLogger(__name__)

#: PANGAEA 의 차례 그대로 — 핸들 `hdl:10013/epic.44322.d<번호>` 의 번호가 이 차례다
FILES = ("Building", "Coastline", "Contour_010", "Historic", "Icefree", "Landing_area", "Path", "Pipe", "Placename",
         "Protected", "Refuge_poly", "Road", "Station", "Tank", "Watercourse", "Waterstorage")
HANDLE = "https://hdl.handle.net/10013/epic.44322.d{n:03d}"
DOI = "https://doi.org/10.1594/PANGAEA.837976"
SOURCE_URL = DOI
ATTRIBUTION = ('<a href="' + DOI + '" target="_blank" rel="noopener">SCAR KGIS</a> '
               "(AWI &amp; SCAR 2007, King George Island topographic database, PANGAEA, CC BY 3.0)")
PAUSE = 1.0
TOLERANCE = 0.00002
DIGITS = 6

#: 레이어 → 담는 셰이프. 셰이프마다 갈래를 고르는 손(`_code_of`)이 따로다
LAYERS = {
    "kgis:contours": ("Contour_010",),
    "kgis:coastline": ("Coastline",),
    "kgis:icefree": ("Icefree",),
    "kgis:water": ("Waterstorage", "Watercourse"),
    "kgis:facilities": ("Landing_area", "Refuge_poly", "Tank", "Building", "Pipe", "Station"),
    "kgis:routes": ("Road", "Path"),
    "kgis:protected": ("Protected", "Historic"),
}
#: 갈래 → (범례 이름, 색, 모양[, 굵기, 끊김]). `stroke` 는 선, `area` 는 면, `dot`·`star`·`diamond` 는 점 (`map.js` 의 `classStyle`)
CLASSES = {
    "index": (msg("주곡선 50 m"), "#8a5a2b", "stroke", 1.3),
    "contour": (msg("등고선 10 m"), "#b98a5a", "stroke", 0.6),
    "rock": (msg("암석 해안"), "#3d3d3d", "stroke", 1.4),
    "ice": (msg("얼음 해안 (빙벽)"), "#4a9fd0", "stroke", 1.6),
    "coast": (msg("해안 (갈래 모름)"), "#8a8a8a", "stroke", 1.2),
    "icefree": (msg("얼음 없는 땅"), "#a0743c", "area"),
    "lake": (msg("호수"), "#2a7fbf", "area"),
    "creek": (msg("물길"), "#3b8fd0", "stroke", 1.0),
    "landing": (msg("착륙장·헬기장"), "#7b3294", "area"),
    "refuge": (msg("피난처·야외 기지"), "#d95f02", "area"),
    "tank": (msg("탱크"), "#b2182b", "area"),
    "building": (msg("건물"), "#333333", "area"),
    "pipe": (msg("관"), "#636363", "stroke", 1.0, [3, 3]),
    "station": (msg("기지"), "#d7301f", "star"),
    "road": (msg("길"), "#7f2704", "stroke", 2.0),
    "path": (msg("오솔길"), "#a63603", "stroke", 1.2, [5, 4]),
    "aspa": (msg("남극특별보호구역 (ASPA, 2007)"), "#c51b7d", "area"),
    "asma": (msg("남극특별관리구역 (ASMA, 2007)"), "#e6a100", "area"),
    "hsm": (msg("역사 유적 (HSM)"), "#6a3d9a", "diamond"),
}
#: 팝업의 이름 — 한국어, 영어판은 `i18n.PROP_EN`
LABELS = {"kind": "갈래", "name": "이름", "elevation": "고도", "jurisdiction": "관할", "use": "쓰임", "status": "상태",
          "surface": "표면", "service": "담는 것", "description": "설명", "number": "번호", "staff": "인원", "aircraft": "항공기",
          "established": "지정일", "values": "보호 가치", "link": "링크"}


class KgisError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def root() -> Path:
    return Path(settings.KGIS_DIR)


def zip_path(stem: str) -> Path:
    return root() / f"{stem}.zip"


def available(name: str) -> bool:
    return knows(name) and all(zip_path(stem).is_file() for stem in LAYERS[name])


# ── 받기 ─────────────────────────────────────────────────────────────

def _download(n: int, stem: str, target: Path) -> int:
    url = HANDLE.format(n=n)
    try:
        r = requests.get(url, timeout=(settings.UPSTREAM_TIMEOUT, 300), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"}, allow_redirects=True)
    except requests.RequestException as exc:
        usage.record("kgis", ok=False)
        raise KgisError(f"{stem}: AWI ePIC 에 닿지 못했다: {exc}") from exc
    log.info("kgis %s -> %s %s", url, r.url, r.status_code)
    usage.record("kgis", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
    if r.status_code != 200 or r.content[:2] != b"PK":
        raise KgisError(f"{stem}: zip 이 아닌 것이 왔다 (status={r.status_code}, type={r.headers.get('content-type')})")
    part = target.with_suffix(".zip.part")
    part.write_bytes(r.content)
    part.replace(target)
    return len(r.content)


def download(force: bool = False, log_line=print) -> dict:
    """zip 열여섯을 받는다. 있는 것은 건너뛴다(`force` 면 다시)."""
    root().mkdir(parents=True, exist_ok=True)
    got = skipped = size = 0
    for n, stem in enumerate(FILES, start=1):
        target = zip_path(stem)
        if target.is_file() and not force:
            skipped += 1
            continue
        if got:
            time.sleep(PAUSE)
        size += _download(n, stem, target)
        got += 1
        log_line(f"{stem}.zip")
    return {"got": got, "skipped": skipped, "bytes": size}


# ── 읽기 ─────────────────────────────────────────────────────────────

def _text(value) -> str:
    """latin-1 로 읽힌 UTF-8 을 되돌린다 — `Estação` 가 `EstaÃ§Ã£o` 로 읽힌다. 별표(dBASE 의 빈 수)는 빈 것으로"""
    if not value or set(value) <= {"*"}:
        return ""
    try:
        return value.encode("latin-1").decode("utf-8").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value.strip()


def _members(stem: str):
    try:
        with zipfile.ZipFile(zip_path(stem)) as zf:
            return zf.read(f"{stem}/{stem}.shp"), zf.read(f"{stem}/{stem}.dbf")
    except KeyError as exc:
        raise KgisError(f"{stem}.zip 에 {stem}.shp·.dbf 가 없다") from exc


def _read_points(data: bytes) -> list:
    """점 셰이프파일(1) → 행마다 (x, y). 빈 모양(0)은 None"""
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        kind = struct.unpack("<i", data[at + 8:at + 12])[0]
        out.append(struct.unpack("<2d", data[at + 12:at + 28]) if kind == 1 else None)
        at += 8 + words * 2
    return out


def _round(points) -> list:
    return [[round(x, DIGITS), round(y, DIGITS)] for x, y in points]


def _geometry(kind: int, shape):
    if kind == 1:
        return {"type": "Point", "coordinates": _round([shape])[0]} if shape else None
    if kind == 3:
        lines = [_round(tectonics.simplify(p, TOLERANCE)) for p in shape if len(p) >= 2]
        return {"type": "MultiLineString", "coordinates": lines} if lines else None
    polys = []
    for poly in geo3al.group_rings(shape):
        # 작은 건물은 줄이면 고리가 무너진다 — 그때는 원래 고리를 둔다
        kept = [_round(s if len(s := tectonics.simplify(r, TOLERANCE)) >= 4 else r) for r in poly]
        kept = [r for r in kept if len(r) >= 4]
        if kept:
            polys.append(kept)
    return {"type": "MultiPolygon", "coordinates": polys} if polys else None


def _code_of(stem: str, row: dict) -> str:
    if stem == "Contour_010":
        try:
            return "index" if round(float(row.get("ELEVATION") or 0)) % 50 == 0 else "contour"
        except ValueError:
            return "contour"
    if stem == "Coastline":
        return {"Rock": "rock", "Ice": "ice"}.get(row.get("SURFACE"), "coast")
    if stem == "Protected":
        return "asma" if row.get("PA_TYPE") == "ASMA" else "aspa"
    return {"Icefree": "icefree", "Waterstorage": "lake", "Watercourse": "creek", "Landing_area": "landing",
            "Refuge_poly": "refuge", "Tank": "tank", "Building": "building", "Pipe": "pipe", "Station": "station",
            "Road": "road", "Path": "path", "Historic": "hsm"}[stem]


def _props(stem: str, row: dict) -> dict:
    t = {k: _text(v) for k, v in row.items()}
    use = t.get("PURPOSE_DE") or t.get("BUILDING_P") or t.get("USE")
    out = {
        "name": t.get("NAME") or (t.get("DESCRIPTIO") if stem in ("Protected", "Historic") else ""),
        "elevation": f"{t['ELEVATION']} m" if stem == "Contour_010" and t.get("ELEVATION") else "",
        "jurisdiction": t.get("JURISDICTI"),
        "use": "" if use == "Unknown" else use,
        "status": t.get("STATUS") if t.get("STATUS") not in ("Unknown", "") else "",
        "surface": t.get("SURFACE") if t.get("SURFACE") not in ("Unknown", "") else "",
        "service": t.get("SERVICE") if t.get("SERVICE") not in ("Unknown", "") else "",
        "kind": t.get("WATERCOURS") or t.get("FACILITIES") or (t.get("DESCRIPTIO") if stem == "Refuge_poly" else ""),
        "description": t.get("DESCRIPTIO") if stem in ("Historic", "Landing_area") else "",
        "number": f"{t.get('PA_TYPE')} {t.get('ATN')}" if stem in ("Protected", "Historic") and t.get("ATN") else t.get("LO_CODE"),
        "staff": t.get("STAFF"),
        "aircraft": t.get("AIRCRAFT"),
        "established": f"{t['DATE_ESTAB'][:4]}-{t['DATE_ESTAB'][4:6]}-{t['DATE_ESTAB'][6:]}" if len(t.get("DATE_ESTAB") or "") == 8 else "",
        "values": t.get("VALUES_PRO"),
        "link": t.get("CEP_ARCHIV"),
    }
    if out["name"] == out["description"]:
        out["description"] = ""
    return {k: v for k, v in out.items() if v}


def _layer(name: str) -> dict:
    features, counts = [], {}
    for stem in LAYERS[name]:
        shp, dbf = _members(stem)
        if struct.unpack(">i", shp[:4])[0] != 9994:
            raise KgisError(f"{stem}.shp 가 셰이프파일이 아니다")
        kind = struct.unpack("<i", shp[32:36])[0]
        if kind == 1:
            shapes = _read_points(shp)
        elif kind == 3:
            shapes = moonmap._read_lines(shp)
        elif kind == 5:
            shapes = geo3al.read_polygons(shp)
        else:
            raise KgisError(f"{stem}.shp 의 모양 갈래({kind})를 모른다")
        rows = geo3al.read_dbf(dbf)
        if len(shapes) != len(rows):
            raise KgisError(f"{stem}: 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
        for shape, row in zip(shapes, rows):
            if not row or not shape:
                continue
            geometry = _geometry(kind, shape)
            if geometry is None:
                continue
            code = _code_of(stem, row)
            counts[code] = counts.get(code, 0) + 1
            features.append({"type": "Feature", "properties": {**_props(stem, row), "code": code}, "geometry": geometry})
    legend = []
    for code, spec in CLASSES.items():
        if counts.get(code):
            row = {"code": code, "label": str(spec[0]), "color": spec[1], "shape": spec[2], "count": counts[code]}
            if len(spec) > 3:
                row["width"] = spec[3]
            if len(spec) > 4:
                row["dash"] = spec[4]
            legend.append(row)
    return {"features": features, "legend": legend}


_cache, _lock = {}, threading.Lock()


def _load(name: str) -> dict:
    """옮긴 것을 프로세스가 든다 — zip 의 크기·고친 때가 같으면 다시 읽지 않는다(`ntgeo` 와 같다)"""
    mark = tuple((st.st_size, st.st_mtime_ns) for st in (zip_path(s).stat() for s in LAYERS[name]))
    with _lock:
        held = _cache.get(name)
        if held and held[0] == mark:
            return held[1]
    try:
        loaded = _layer(name)
    except (zipfile.BadZipFile, struct.error, IndexError, geo3al.Geo3alError, moonmap.MoonMapError) as exc:
        raise KgisError(str(exc)) from exc
    with _lock:
        _cache[name] = (mark, loaded)
    return loaded


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `kopri._pack` 과 같다. 팝업·범례 이름은 한국어이고 영어판이면 화면이 `T()` 로 옮긴다"""
    if not knows(name):
        raise KgisError(f"모르는 레이어다: {name}")
    loaded = _load(name)
    out = {"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link"], "legend": loaded["legend"],
           "features": loaded["features"]}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "kgis", "tag": "SCAR", "title": "SCAR 킹조지섬 GIS", "local": True},
]
