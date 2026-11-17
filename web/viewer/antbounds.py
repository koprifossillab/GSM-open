"""남극 접지선·빙붕·유역 — NASA MEaSUREs 의 두 자료를 남극 탭의 선·면으로 (wetherilli 460).

- **InSAR 접지선 1992–2025**(Rignot 외, NSIDC-0498 v2.1) — 위성 레이더 간섭으로 그린 접지선 1 820 개, 관측마다 한 줄. 같은 빙하에 해마다
  여러 줄이 겹쳐 접지선이 물러나는 것(파인아일랜드·스웨이츠·토튼)이 보인다. 색은 관측 시기 다섯 칸
- **남극 경계 v2**(Mouginot·Scheuchl·Rignot, NSIDC-0709) — 빙붕 181(이름), 빙하 유역 199(이름·흘러드는 빙붕), IMBIE 유역 19,
  2007–09 의 접지선 하나. 해안선은 뺐다 — ADD 해안선(KPDC 지도 서버)이 이미 있다. 마스크 래스터도 쓰지 않는다

둘 다 **NASA Earthdata 로그인 뒤에** 있어(NSIDC 클라우드) 사람이 받아 온 토큰으로 한 번 받았다. 원본은 NAS `sources/antarctica/measures/`.
`manage.py build_antarctic_boundaries <폴더>` 가 numpy 없이(셰이프는 `geo3al`·`raised`, gpkg 는 `geomap.parse_geometry`) 읽어 3031 에서
줄이고(더글러스–포이커) 위경도로 `<GSM_GLACIO_DIR>/antarctic_boundaries.json` 에 적는다. 화면이 부를 때는 이 파일만 읽는다. 문이 아니다.
조건은 NASA 지구과학 자료 정책(열린 자료, 인용).
"""
import functools
import json
import sqlite3
import time
from pathlib import Path

from django.conf import settings

from . import antpapers, geo3al, geomap, i18n
from .i18n import msg

FILE = "antarctic_boundaries.json"
INSAR = "InSAR_GL_Antarctica_v02.1.gpkg"
SHAPES = {"shelves": "IceShelf_Antarctica_v02", "basins": "Basins_Antarctica_v02", "imbie": "Basins_IMBIE_Antarctica_v02",
          "gl2008": "GroundingLine_Antarctica_v02"}
INSAR_DOI = "https://doi.org/10.5067/IKBWW4RYHF1Q"
BOUNDS_DOI = "https://doi.org/10.5067/AXE4121732AD"
CREDIT = ("MEaSUREs InSAR grounding line v2.1 (Rignot et al., NSIDC-0498) · MEaSUREs Antarctic Boundaries v2 "
          "(Mouginot, Scheuchl & Rignot, NSIDC-0709)")
#: 줄일 때의 허용(m, 3031) — 접지선은 곱게, 유역은 거칠게
TOLERANCE = {"insar_gl": 120.0, "shelves": 150.0, "basins": 300.0, "imbie": 500.0, "gl2008": 150.0}
LAYERS = {f"antbounds:{k}" for k in TOLERANCE}

_S = lambda width, dash=None: {"shape": "stroke", "width": width, **({"dash": dash} if dash else {})}
#: 관측 시기 — (code, 이름, 색, 모양, 윗 해). 옛것은 짙은 파랑, 최근은 빨강
PERIODS = [("p1990", msg("1992–1999 (ERS·RADARSAT)"), "#253494", _S(1.6), 1999),
           ("p2000", msg("2000–2009"), "#2c7fb8", _S(1.6), 2009),
           ("p2010", msg("2010–2016"), "#41b6c4", _S(1.6), 2016),
           ("p2017", msg("2017–2020 (Sentinel-1·COSMO)"), "#fd8d3c", _S(1.6), 2020),
           ("p2021", msg("2021–2025"), "#d7301f", _S(2.0), 9999)]
#: 남극의 갈래 — 유역·빙붕의 `Regions` 열
REGIONS = [("East", msg("동남극"), "#4575b4"), ("West", msg("서남극"), "#d73027"),
           ("Peninsula", msg("남극반도"), "#1a9850"), ("Islands", msg("섬"), "#7f7f7f")]
CLASSES = {
    "antbounds:insar_gl": [(c, label, color, look) for c, label, color, look, _ in PERIODS],
    "antbounds:shelves": [("shelf", msg("빙붕"), "#5ab4d6", {"shape": "area"})],
    "antbounds:basins": [(c, label, color, {}) for c, label, color in REGIONS],
    "antbounds:imbie": [(c, label, color, {}) for c, label, color in REGIONS],
    "antbounds:gl2008": [("gl", msg("접지선 (2007–2009)"), "#3a3a3a", _S(1.4))],
}
LABELS = {"name": "이름", "glacier": "빙하", "sensor": "위성", "date": "관측일", "year": "해", "region": "갈래",
          "imbie": "IMBIE 유역", "shelf": "흘러드는 빙붕", "link": "자료"}
LABEL_BY = {"antbounds:shelves": "name", "antbounds:basins": "name", "antbounds:imbie": "imbie"}


class AntBoundsError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.GLACIO_DIR) / FILE


def knows(name: str) -> bool:
    return name in LAYERS


def available() -> bool:
    return path().is_file()


# ── 굽기 — numpy 없이 ─────────────────────────────────────────────────

def _lonlat(ring) -> list:
    return [[round(v, 4) for v in geomap.xy3031_to_lonlat(x, y)] for x, y in ring]


def _period(year: int) -> str:
    return next(c for c, *_, top in PERIODS if year <= top)


def read_insar(file) -> list:
    """InSAR 접지선 gpkg → 줄 `[code, own, "M", 선들]` 목록 — 관측 하나가 한 줄(조각이 여럿이면 MultiLineString)"""
    db = sqlite3.connect(f"file:{file}?mode=ro", uri=True)
    try:
        table = db.execute("select table_name from gpkg_contents where data_type='features'").fetchone()
        if table is None:
            raise AntBoundsError(f"{file} 에 피처 표가 없다")
        rows = db.execute(f'select geom, Glac_Name, Sensor, Year, Date_1 from "{table[0]}"').fetchall()
    finally:
        db.close()
    out = []
    for blob, glacier, sensor, year, date in rows:
        kind, parts = geomap.parse_geometry(blob)
        if kind != "line" or not year:
            continue
        own = {"glacier": (glacier or "").strip(), "sensor": (sensor or "").strip(), "year": int(year), "date": (date or "").strip()}
        lines = []
        for flat in parts:
            line = antpapers.simplify(list(zip(flat[0::2], flat[1::2])), TOLERANCE["insar_gl"])
            if len(line) >= 2:
                lines.append(_lonlat(line))
        if lines:
            out.append([_period(int(year)), own, "M", lines])
    return out


def _shape(folder: Path, stem: str):
    try:
        shp, dbf = (folder / f"{stem}.shp").read_bytes(), (folder / f"{stem}.dbf").read_bytes()
        prj = (folder / f"{stem}.prj").read_bytes()
    except FileNotFoundError as exc:
        raise AntBoundsError(f"원본이 없다 — {exc.filename}") from exc
    if b"Stereographic_South_Pole" not in prj and b"Polar_Stereographic" not in prj:
        raise AntBoundsError(f"{stem} 의 투영이 남극 평사도법(3031)이 아니다")
    shapes, rows = geo3al.read_polygons(shp), geo3al.read_dbf(dbf)
    if len(shapes) != len(rows):
        raise AntBoundsError(f"{stem} 의 셰이프와 속성 표의 행 수가 다르다")
    return shapes, rows


def read_areas(folder: Path, key: str) -> list:
    """빙붕·유역 셰이프 → 줄 `[code, own, "A", 다각형들]`. 2008 접지선은 고리를 선으로 `[…, "L", 좌표]`"""
    shapes, rows = _shape(folder, SHAPES[key])
    tol = TOLERANCE[key]
    known = {c for c, *_ in REGIONS}
    out = []
    for rings, row in zip(shapes, rows):
        if row is None:
            continue
        if key == "gl2008":
            for ring in rings:
                line = antpapers.simplify(ring, tol)
                if len(line) >= 2:
                    out.append(["gl", {}, "L", _lonlat(line)])
            continue
        polygons = []
        for polygon in geo3al.group_rings(rings):
            kept = [antpapers.simplify(r, tol) for r in polygon]
            kept = [r for r in kept if len(r) >= 4]
            if kept and len(kept[0]) >= 4:
                polygons.append([_lonlat(r) for r in kept])
        if not polygons:
            continue
        name = row.get("NAME", "").replace("_", " ").strip()
        own = {"name": name, "region": row.get("Regions", "")}
        if key == "shelves":
            out.append(["shelf", own, "A", polygons])
            continue
        own["imbie"] = row.get("Subregions", "")
        if row.get("Asso_Shelf"):
            own["shelf"] = row["Asso_Shelf"].replace("_", " ")
        region = own["region"] if own["region"] in known else "Islands"
        out.append([region, own, "A", polygons])
    return out


def convert(folder) -> dict:
    folder = Path(folder)
    layers = {"antbounds:insar_gl": read_insar(folder / INSAR)}
    for key in SHAPES:
        layers[f"antbounds:{key}"] = read_areas(folder, key)
    for name, rows in layers.items():
        if not rows:
            raise AntBoundsError(f"{name}: 그릴 것이 없다")
    return {"layers": layers}


def build(folder, out: Path = None) -> dict:
    out = Path(out) if out else path()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"built": time.strftime("%Y-%m-%d"), "source": "NSIDC-0498 v2.1 · NSIDC-0709 v2", **convert(folder)}
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    part.replace(out)
    return {name: len(rows) for name, rows in doc["layers"].items()} | {"mb": round(out.stat().st_size / 1e6, 1)}


# ── 내주기 ───────────────────────────────────────────────────────────

RENDERER = 1


def version() -> str:
    try:
        st = path().stat()
    except FileNotFoundError:
        return ""
    return f"r{RENDERER}-{st.st_mtime_ns}-{st.st_size}"


@functools.lru_cache(maxsize=2)
def _data(_stamp: str) -> dict:
    return json.loads(path().read_text(encoding="utf-8"))


def _props(name: str, own: dict, label: str, lang: str) -> dict:
    props = {"code": "", "kind": label}
    for key in ("name", "glacier", "sensor", "date", "imbie", "shelf"):
        if own.get(key):
            props[key] = own[key]
    if own.get("region"):
        props["region"] = i18n.t(dict((c, l) for c, l, _ in REGIONS).get(own["region"], own["region"]), lang)
    props["link"] = INSAR_DOI if name == "antbounds:insar_gl" else BOUNDS_DOI
    return props


def body(name: str, lang: str = "ko") -> bytes:
    """레이어 하나의 GeoJSON — 갈래(`code`)마다 색. 파일이 없으면 FileNotFoundError"""
    if not available():
        raise FileNotFoundError(path())
    return _body(name, lang, version())


@functools.lru_cache(maxsize=24)
def _body(name: str, lang: str, _stamp: str) -> bytes:
    table = {code: (i18n.t(label, lang), color, look) for code, label, color, look in CLASSES[name]}
    features, counts = [], {}
    for code, own, kind, coords in _data(_stamp)["layers"].get(name, []):
        if code not in table:
            continue
        counts[code] = counts.get(code, 0) + 1
        geom = {"type": {"A": "MultiPolygon", "M": "MultiLineString"}.get(kind, "LineString"), "coordinates": coords}
        props = _props(name, own, table[code][0], lang)
        props["code"] = code
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    legend = [{"code": code, "label": table[code][0], "color": table[code][1], "count": counts[code], **table[code][2]}
              for code, *_ in CLASSES[name] if counts.get(code)]
    doc = {"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link"], "legend": legend, "features": features}
    if name in LABEL_BY:
        doc["labelBy"] = LABEL_BY[name]
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 우리 디스크의 파일이다 — 원본은 NSIDC 에서 한 번 받아 `build_antarctic_boundaries` 로 굽는다 (wetherilli 460)
REGISTRY = [
    {"upstream": "antbounds", "tag": "MEaSUREs", "title": "남극 접지선·경계 (MEaSUREs)", "local": True},
]
