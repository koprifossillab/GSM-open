"""호주 남극자료센터(AADC) 자료 저장소(EDS)로 나가는 문 — 남극 특별보호구역 ASPA 2024 (wetherilli 423).

ASPA 의 면·점은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나"). 같은 AADC 의 GeoServer WFS 로 받는 SCAR 지명사전은
`scar.py` 다 — 저 문은 SCAR 의 지명사전을, 이 문은 AADC 의 자료 저장소에 든 파일을 받는다.

- 자료는 Terauds 외(2024) "Antarctic Specially Protected Areas (Points and Polygons) 2024 Update" — 관리 계획의 좌표와 지도에
  다시 맞춘 판이다. 조건은 **CC BY 4.0** — 자료 안의 `LICENSE`·`README` 가 그렇게 적는다. 인용 꼴은 `CREDIT`
- **묶음 내려받기(`/eds/api/dataset/<번호>/download`)는 이메일 주소를 물어 넘겨 준다.** 이메일을 적지 않으려고 파일마다 받는다 —
  자료 화면이 파일 목록에 거는 주소(`/eds/api/dataset/<uuid>/object/download?prefix=…`)가 열쇠 없이 하루짜리 서명된 주소로 넘겨 준다
- **화면이 부를 때 상류를 타지 않는다.** `manage.py fetch_aspa` 가 셰이프 파일 열(면·점 각 다섯)을 1 초 간격으로 받아 원본은
  `<AADC_DIR>/aspa_raw/<날짜>/` 에(`rawstore`), 위경도로 옮겨 줄인 것은 `<AADC_DIR>/aspa_2024.json` 에 적는다. 레이어는 이 파일만 읽는다
- 셰이프는 EPSG:3031 미터 좌표이고 글자는 UTF-8 이다(`.cpg`). 면은 꼭짓점 13 만이라 **2 m 로 줄인다**(Douglas–Peucker) — 가장 작은
  ASPA 가 100 m² 라 그보다 거칠게 줄이면 모양이 무너진다
- 속성 가운데 `PrimProtDe`(A–I)·`EnvDomain` 은 싣지 않는다 — 자료가 그 부호의 뜻을 적지 않았다. 지어 붙이지 않는다
"""
import json
import logging
import struct
import time
from pathlib import Path
from urllib.parse import quote

import requests
from django.conf import settings

from . import geo3al, geomap, tectonics, usage

log = logging.getLogger(__name__)

EDS = "https://data.aad.gov.au/eds/api/dataset"
#: ASPA 2024 의 자료 번호와 uuid. 파일은 uuid 로만 받는다
ASPA_ID = "5998"
ASPA_UUID = "b4c92f68-64c3-476d-97eb-d439360415b9"
ASPA_PREFIX = "AAS_4296_Updated_ASPAs_2024"
#: 받는 파일 — 면·점의 셰이프 다섯씩과 조건·설명
SHAPES = {"polygons": "ASPAs_polygons_v5_2024", "points": "ASPAs_points_v5_2024"}
PARTS = (".shp", ".shx", ".dbf", ".prj", ".cpg")
EXTRA = ("LICENSE", "README")
PAUSE = 1.0
SOURCE_URL = "https://data.aad.gov.au/metadata/AAS_4296_Updated_ASPAs_2024"
CREDIT = ('<a href="' + SOURCE_URL + '" target="_blank" rel="noopener">Terauds et al. (2024) Antarctic Specially Protected Areas '
          "2024 Update</a>, Australian Antarctic Data Centre (CC BY 4.0)")
#: 면을 줄이는 너비 (m, 3031)
TOLERANCE = 2.0
DIGITS = 6

#: 카탈로그의 레이어 — 면과, 멀리서도 보이게 찍은 점
POLYGONS = "aadc:aspa"
POINTS = "aadc:aspa_points"
LAYERS = {POLYGONS: "polygons", POINTS: "points"}
#: 팝업 이름(한국어 원문 — 영어는 `i18n.PROP_EN`). 차례가 팝업의 차례다
LABELS = {"no": "ASPA 번호", "name": "이름", "by": "제안국", "measure": "지정 문서", "area": "넓이 (km²)",
          "marine": "바다를 품는다", "acbr": "보전 생물지리구 (ACBR)"}
#: 갈래 — 바다를 품은 것과 땅뿐인 것. 범례 이름은 한국어 원문(화면이 옮긴다)
CLASSES = (("land", "ASPA", "#c62828", "square"), ("marine", "ASPA — 바다를 품는다", "#1565c0", "square"))


class AadcError(RuntimeError):
    pass


def root() -> Path:
    return Path(settings.AADC_DIR)


def path() -> Path:
    return root() / "aspa_2024.json"


def raw_dir() -> Path:
    return root() / "aspa_raw"


def knows(name: str) -> bool:
    return name in LAYERS


def available() -> bool:
    return path().is_file()


# ── 받기 ─────────────────────────────────────────────────────────────

def _file_url(prefix: str) -> str:
    return f"{EDS}/{ASPA_UUID}/object/download?prefix={quote(prefix, safe='')}"


def _get(prefix: str) -> bytes:
    """파일 하나. EDS 가 서명된 주소(transfer.data.aad.gov.au)로 넘기는 것을 따라간다"""
    try:
        r = requests.get(_file_url(prefix), timeout=(settings.UPSTREAM_TIMEOUT, 120), allow_redirects=True,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("aadc", ok=False)
        raise AadcError(f"AADC 에 닿지 못했다: {exc}") from exc
    # 넘겨받은 주소에는 하루짜리 서명이 붙는다 — 로그에는 묻은 자리만 적는다
    log.info("aadc %s -> %s", prefix, r.status_code)
    if r.status_code != 200:
        usage.record("aadc", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise AadcError(f"AADC 가 {r.status_code} 로 답했다 ({prefix})")
    if r.content[:15].lower().startswith((b"<!doctype", b"<html")):
        usage.record("aadc", ok=False)
        raise AadcError(f"AADC 가 파일 대신 화면을 주었다 ({prefix})")
    usage.record("aadc", ok=True, elapsed=r.elapsed)
    return r.content


def download(pause: float = PAUSE) -> dict:
    """받을 파일 모두 → {파일 이름: 바이트}. 파일 사이에 `pause` 초 쉰다"""
    wanted = [f"{ASPA_PREFIX}/{stem}/{stem}{ext}" for stem in SHAPES.values() for ext in PARTS] + list(EXTRA)
    out = {}
    for index, prefix in enumerate(wanted):
        if index:
            time.sleep(pause)
        out[prefix.rsplit("/", 1)[-1]] = _get(prefix)
    return out


# ── 읽기 ─────────────────────────────────────────────────────────────

def read_points(data: bytes) -> list:
    """점 셰이프파일(1) → 행마다 (x, y). 빈 점(0)은 None"""
    if struct.unpack(">i", data[:4])[0] != 9994:
        raise AadcError("셰이프파일이 아니다")
    if struct.unpack("<i", data[32:36])[0] != 1:
        raise AadcError("점 셰이프파일이 아니다")
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        kind = struct.unpack("<i", data[body:body + 4])[0]
        out.append(struct.unpack("<2d", data[body + 4:body + 20]) if kind == 1 else None)
        at = body + words * 2
    return out


def _utf8(row: dict) -> dict:
    """`geo3al.read_dbf` 는 latin-1 로 읽는다 — ASPA 의 글자는 UTF-8 이라(`.cpg`) 다시 푼다(Sør Rondane)"""
    out = {}
    for key, value in row.items():
        try:
            out[key] = value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            out[key] = value
    return out


def _props(row: dict) -> dict:
    marine = row.get("Marine") == "1"
    try:
        area = round(float(row.get("Area_km") or ""), 4)
    except ValueError:
        area = None
    props = {"code": "marine" if marine else "land", "no": row.get("ASPA_No"), "name": row.get("NAME"),
             "by": row.get("Propon"), "measure": row.get("DesigInstr"), "area": area,
             "marine": "예" if marine else None, "acbr": row.get("ACBR") if row.get("ACBR") not in ("", "NA") else None}
    return {k: v for k, v in props.items() if v not in (None, "")}


def _lonlat(x: float, y: float) -> list:
    lon, lat = geomap.xy3031_to_lonlat(x, y)
    return [round(lon, DIGITS), round(lat, DIGITS)]


def _simplified(ring: list) -> list:
    simple = tectonics.simplify(ring, TOLERANCE)
    return simple if len(simple) >= 4 else ring


def convert(files: dict) -> dict:
    """받은 파일들 → {"polygons": [feature…], "points": [feature…]}. 속성은 `_props`, 좌표는 위경도"""
    for stem in SHAPES.values():
        cpg = files.get(stem + ".cpg", b"UTF-8").strip().upper()
        if cpg not in (b"UTF-8", b"UTF8"):
            raise AadcError(f"{stem}.cpg 가 UTF-8 이 아니다: {cpg!r}")
        prj = files.get(stem + ".prj", b"").decode("latin-1")
        if "Stereographic_South_Pole" not in prj or "-71" not in prj:
            raise AadcError(f"{stem}.prj 가 남극 평사도법(3031)이 아니다")
    stem = SHAPES["polygons"]
    shapes = geo3al.read_polygons(files[stem + ".shp"])
    rows = geo3al.read_dbf(files[stem + ".dbf"])
    if len(shapes) != len(rows):
        raise AadcError(f"면 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
    polygons = []
    for index, (rings, row) in enumerate(zip(shapes, rows)):
        if not row or not rings:
            continue
        polys = []
        for poly in geo3al.group_rings(rings):
            # 작은 고리는 줄이면 무너진다 — 그때는 원래 고리를 둔다 (`ntgeo` 와 같다)
            kept = [[_lonlat(x, y) for x, y in _simplified(r)] for r in poly]
            kept = [r for r in kept if len(r) >= 4]
            if kept:
                polys.append(kept)
        if polys:
            polygons.append({"type": "Feature", "id": index, "properties": _props(_utf8(row)),
                             "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    stem = SHAPES["points"]
    spots = read_points(files[stem + ".shp"])
    rows = geo3al.read_dbf(files[stem + ".dbf"])
    if len(spots) != len(rows):
        raise AadcError(f"점 셰이프({len(spots)})와 속성({len(rows)})의 수가 다르다")
    points = [{"type": "Feature", "id": index, "properties": _props(_utf8(row)),
               "geometry": {"type": "Point", "coordinates": _lonlat(*spot)}}
              for index, (spot, row) in enumerate(zip(spots, rows)) if row and spot]
    return {"polygons": polygons, "points": points}


def write(baked: dict, out: Path = None) -> Path:
    out = out or path()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.with_suffix(".part")
    work.write_text(json.dumps({"source": SOURCE_URL, "dataset": ASPA_ID, **baked}, ensure_ascii=False,
                               separators=(",", ":")), encoding="utf-8")
    work.replace(out)
    return out


# ── 내주기 ───────────────────────────────────────────────────────────

_memo = {}


def _load() -> dict:
    """구운 파일을 프로세스가 든다 — 크기·고친 때가 같으면 다시 읽지 않는다"""
    st = path().stat()
    mark = (st.st_size, st.st_mtime_ns)
    if _memo.get("mark") != mark:
        _memo.update(mark=mark, data=json.loads(path().read_text(encoding="utf-8")))
    return _memo["data"]


def body(name: str, lang: str = "ko") -> bytes:
    """`/points/` 의 한 덩이 — 갈래 색은 `style: class` 의 `legend` 로(극지연구소와 같은 꼴). 팝업 이름·범례 이름은 화면이 옮긴다.
    `바다를 품는다` 의 값 `예` 만은 여기서 옮긴다"""
    if not knows(name):
        raise AadcError(f"모르는 레이어다: {name}")
    features = _load()[LAYERS[name]]
    if lang == "en":
        features = [dict(f, properties=dict(f["properties"], marine="yes")) if "marine" in f["properties"] else f
                    for f in features]
    counts = {}
    for f in features:
        counts[f["properties"]["code"]] = counts.get(f["properties"]["code"], 0) + 1
    legend = [{"code": code, "label": label, "color": color, "shape": shape, "count": counts[code]}
              for code, label, color, shape in CLASSES if code in counts]
    return json.dumps({"type": "FeatureCollection", "labels": LABELS, "links": [], "style": "class", "legend": legend,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "aadc", "tag": "AADC", "title": "호주 남극자료센터"},
]
