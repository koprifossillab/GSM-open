"""PetroChron Antarctica 로 나가는 문 — 남극 암석 시료 1 만 1 천 분석의 암석·화학·연대 (wetherilli 419).

PetroChron 은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 상류는 Zenodo 의 레코드 5032026(판 0_1, 2021-06-25, Sanchez 외, **CC BY 4.0**). **2021 년에 멈춘 판**이라 웹서비스를 부르지
  않고 파일을 받아 우리가 굽는다. 열쇠가 없다
- 받는 것은 엮어 둔 표 `PetroChron_Antarctica_db_0_1.csv`(메타·암석·화학·연대·암석 물성을 한 줄에, 9 MB)와 참고문헌 `.bib`
  둘이다. 따로 든 `_metadata_`·`_petro_`·`_geochem_`·`_geochron_`·`_rock_prop_` 는 이 표를 가른 것이라 받지 않는다
- **화면이 부를 때 상류를 타지 않는다.** `manage.py fetch_petrochron` 이 받아 원본을 날짜 폴더(`<PETROCHRON_DIR>/raw/`, `rawstore`)에
  두고 점 한 덩이(`<PETROCHRON_DIR>/petrochron.json`)로 굽는다. 화면은 그 덩이만 읽는다
- 한 줄은 **분석 하나**다(시료 하나에 전암·광물·연대가 여러 줄일 수 있다). 점도 줄마다 하나다 — 같은 자리에 겹쳐 서고 팝업이 함께 보인다
- 색은 암석 갈래 다섯이다 — 극지연구소 암석 시료(`kopri.ROCK_CLASSES`)와 같은 색에 모양만 마름모로 갈라 둘을 함께 켜도 구별한다.
  성분·연대로 칠하는 것(연속값 색)은 다음 일이다 (TODOs)
"""
import csv
import io
import json
import logging
import re
import time
from functools import lru_cache
from pathlib import Path

import requests
from django.conf import settings

from . import kopri, usage

log = logging.getLogger(__name__)

RECORD = "https://zenodo.org/api/records/5032026"
#: 받는 파일 — (우리 이름, Zenodo 의 파일 이름)
FILES = (("db", "PetroChron_Antarctica_db_0_1.csv"), ("refs", "PetroChron_Antarctica_refs_0_1.bib"))
PAUSE = 1.0
DIGITS = 5
VERSION = "0_1"
LICENSE = "CC BY 4.0"
SOURCE_URL = "https://doi.org/10.5281/zenodo.5032026"
ATTRIBUTION = "PetroChron Antarctica (Sanchez et al. 2021, CC BY 4.0)"
#: 카탈로그의 점 레이어
LAYER = "petrochron:samples"

#: 암석 갈래 — (코드, 한국어, 색). 색은 극지연구소 암석 시료와 같다
CLASSES = tuple((code, label, color) for code, _, label, color in kopri.ROCK_CLASSES)
SHAPE = "diamond"
#: 팝업 열 — 차례가 팝업의 차례다
LABELS = {"sample": "시료 번호", "rock": "암석", "strat": "층서 이름", "place": "지점", "sampling": "채취",
          "coord": "좌표 출처", "age": "연대 (Ma)", "method": "연대 방법", "target": "분석 대상",
          "major": "주성분 (wt%)", "ref": "참고문헌", "doi": "DOI"}
LINKS = ("doi",)
#: 팝업의 주성분 한 줄 — (열, 적는 이름)
MAJORS = (("sio2", "SiO₂"), ("tio2", "TiO₂"), ("al2o3", "Al₂O₃"), ("fe2o3_tot", "Fe₂O₃t"), ("fe2o3", "Fe₂O₃"),
          ("feo", "FeO"), ("mgo", "MgO"), ("cao", "CaO"), ("na2o", "Na₂O"), ("k2o", "K₂O"))


class PetroChronError(RuntimeError):
    pass


def data_dir() -> Path:
    return Path(settings.PETROCHRON_DIR)


def path() -> Path:
    return data_dir() / "petrochron.json"


def available() -> bool:
    return path().exists()


def knows(name: str) -> bool:
    return name == LAYER


# ── 받기 ─────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 300) -> bytes:
    left = usage.paused()
    if left:
        raise PetroChronError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, timeout=(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("petrochron", ok=False)
        raise PetroChronError(f"Zenodo 에 닿지 못했다: {exc}") from exc
    log.info("petrochron %s -> %s", r.url, r.status_code)
    if r.status_code != 200:
        usage.record("petrochron", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise PetroChronError(f"Zenodo 가 {r.status_code} 로 답했다")
    usage.record("petrochron", ok=True)
    return r.content


def download(pause: float = PAUSE) -> dict:
    """Zenodo 에서 파일 둘을 받는다. {우리 이름: 본문}"""
    out = {}
    for i, (key, name) in enumerate(FILES):
        if i:
            time.sleep(pause)
        out[key] = _get(f"{RECORD}/files/{name}/content")
    return out


# ── 굽기 ─────────────────────────────────────────────────────────────

_BIB_ENTRY = re.compile(r"^@\w+\{", re.M)
_BIB_FIELD = re.compile(r"^\s*(title|doi)\s*=\s*\{(.*)\},?\s*$", re.M | re.I)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\\.|[{}$]", "", text.lower()))


def bib_dois(bib: str) -> dict:
    """참고문헌 `.bib` → {제목(글자·숫자만, 소문자): DOI}. 표의 참고문헌은 "저자, 해, 제목" 이라 제목으로 잇는다"""
    out = {}
    for entry in _BIB_ENTRY.split(bib)[1:]:
        fields = {k.lower(): v.strip() for k, v in _BIB_FIELD.findall(entry)}
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", fields.get("doi", ""), flags=re.I)
        if fields.get("title") and doi.startswith("10."):
            out[_norm(fields["title"])] = doi
    return out


def _doi_of(reference: str, dois: dict) -> str:
    """"Adachi et al., 2010, Titanium behavior …" → 제목으로 찾은 DOI. 없으면 빈 글"""
    m = re.match(r"^.*?,\s*\d{4}[a-z]?,\s*(.+)$", reference)
    return dois.get(_norm(m.group(1)), "") if m else ""


def _num(text: str):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def rock_class(group: str, kind: str) -> str:
    group, kind = group.lower(), kind.lower()
    if group == "sedimentary":
        return "sedimentary"
    if group == "metamorphic":
        return "metamorphic"
    if group == "igneous":
        return "volcanic" if "volcanic" in kind else "plutonic"
    return "other"


def _join(*parts) -> str:
    seen = []
    for p in parts:
        p = (p or "").strip()
        if p and p.lower() != "not defined" and p not in seen:
            seen.append(p)
    return " · ".join(seen)


def feature(row: dict, dois: dict):
    """표의 한 줄 → 점 하나. 좌표가 없으면 None"""
    lat, lon = _num(row.get("latitude")), _num(row.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    props = {"code": rock_class(row.get("rock_group", ""), row.get("rock_type", "")),
             "sample": row.get("sample_name", "").strip(),
             "rock": _join(row.get("rock_group"), row.get("rock_type"), row.get("rock_name"), row.get("rock_description")),
             "strat": _join(row.get("lithostrat_name"), row.get("basement_terrane")),
             "place": (row.get("geolocation") or "").strip(),
             "sampling": (row.get("sampling") or "").strip(),
             "coord": (row.get("geographic_coordinate_information") or "").strip()}
    age = _num(row.get("age_ma"))
    if age is not None:
        err = _num(row.get("age_2sd_ma"))
        props["age"] = f"{age:g} ± {err:g} (2σ)" if err and err > 0 else f"{age:g}"
        props["method"] = _join(row.get("age_type"), row.get("mineral_isotope"), row.get("technique_isotopes_analyses"),
                                row.get("age_approach"), row.get("age_significance"))
    target = (row.get("mineral_geochemistry") or "").strip()
    majors = [(name, _num(row.get(col))) for col, name in MAJORS]
    majors = [f"{name} {v:.4g}" for name, v in majors if v is not None]
    if majors:
        props["major"] = " · ".join(majors)
        if target and target != "whole rock":
            props["target"] = target           # 광물 분석이면 주성분은 그 광물의 것이다
    reference = (row.get("reference") or "").strip()
    props["ref"] = reference
    doi = _doi_of(reference, dois)
    if doi:
        props["doi"] = "https://doi.org/" + doi
    return {"type": "Feature", "id": row.get("spldata_id") or None,
            "geometry": {"type": "Point", "coordinates": [round(lon, DIGITS), round(lat, DIGITS)]},
            "properties": {k: v for k, v in props.items() if v not in (None, "")}}


def build(db_csv: bytes, bib: bytes) -> dict:
    """받은 두 파일 → 점 한 덩이({version, license, features})"""
    dois = bib_dois(bib.decode("utf-8", errors="replace"))
    rows = csv.DictReader(io.StringIO(db_csv.decode("utf-8-sig")))
    features = [f for f in (feature(row, dois) for row in rows) if f]
    if not features:
        raise PetroChronError("PetroChron 표에 점이 없다")
    return {"version": VERSION, "license": LICENSE, "source": SOURCE_URL, "features": features}


def save(data: dict) -> Path:
    dest = path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(dest)
    _body.cache_clear()
    return dest


# ── 화면에 내는 것 ────────────────────────────────────────────────────

def legend(features: list) -> list:
    counts = {}
    for f in features:
        counts[f["properties"]["code"]] = counts.get(f["properties"]["code"], 0) + 1
    return [{"code": code, "label": label, "color": color, "shape": SHAPE, "count": counts[code]}
            for code, label, color in CLASSES if counts.get(code)]


@lru_cache(maxsize=2)
def _body(mtime: float) -> bytes:
    data = json.loads(path().read_text(encoding="utf-8"))
    features = data["features"]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": list(LINKS),
                       "legend": legend(features), "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def body() -> bytes:
    """화면에 보내는 한 덩이. 굽지 않았으면 FileNotFoundError"""
    return _body(path().stat().st_mtime)


REGISTRY = [
    {"upstream": "petrochron", "tag": "PetroChron", "title": "PetroChron 남극 암석 자료", "local": True},
]
