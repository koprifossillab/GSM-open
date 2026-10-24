"""셰필드대 연구자료 저장소(ORDA, figshare)로 나가는 문 — 빙저호 목록 (wetherilli 420).

빙저호는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 자료는 Livingstone 외 2022 의 전 지구 빙저호 목록(Nat Rev Earth Environ 3, 106–124)이다. ORDA 의 figshare 항목
  18094037 이 셰이프 zip 과 엑셀 한 벌을 주고 **CC BY 4.0** 이다. 2025-02 에 고쳤다
- **엑셀을 받는다.** 셰이프의 `Lake_Type` 은 773 개 가운데 181 개만 차 있고 찾은 법·문헌이 없다. 엑셀은 지역마다 시트가
  따로이고(남극·그린란드·만년설·곡빙하) 종류·찾은 법·문헌이 다 있다. 남극 시트와 그린란드 시트만 쓴다
- 엑셀은 openpyxl 없이 읽는다 — xlsx 는 zip 안의 XML 이다(`read_xlsx`). 제품은 openpyxl 을 쓰지 않는다
- **화면이 부를 때 상류를 타지 않는다.** `manage.py fetch_subglacial_lakes` 가 figshare API 로 파일 목록을 보고 엑셀 한 장을
  받아 `<GLACIO_DIR>/subglacial_lakes.json` 에 줄여 적는다(두 번 부른다, 1 초 간격). 목록은 몇 해에 한 번 고쳐진다
"""
import functools
import json
import logging
import re
import time
import zipfile
import io
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from django.conf import settings

from . import i18n, usage
from .i18n import msg

log = logging.getLogger(__name__)

ARTICLE = 18094037
API = f"https://api.figshare.com/v2/articles/{ARTICLE}"
DOI = "https://doi.org/10.15131/shef.data.18094037.v1"
PAPER = "https://doi.org/10.1038/s43017-021-00246-9"
SOURCE_URL = DOI
CREDIT = "Livingstone et al. 2022, Compiled global database of subglacial lakes (Univ. Sheffield ORDA, CC BY 4.0)"
PAUSE = 1.0
#: 카탈로그의 레이어 — 시트 하나에 하나
LAYERS = {"orda:lakes_antarctica": "Antarctica", "orda:lakes_greenland": "Greenland"}
#: 종류 — 얼음 윗면이 오르내려 채웠다 비웠다 하는 것(활성)과 얼음 레이더로 본 그대로인 것(안정)
KINDS = [("active", msg("활성 빙저호 (채웠다 비웠다)"), "#e4572e"),
         ("stable", msg("안정 빙저호"), "#2e86de"),
         ("unknown", msg("종류를 적지 않음"), "#9aa5b1")]
LABELS = {"name": "이름", "kind": "종류", "method": "찾은 법", "area": "넓이 (km²)", "ice": "얼음 두께 (m)",
          "refs": "문헌", "link": "자료 (ORDA)"}


class OrdaError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.GLACIO_DIR) / "subglacial_lakes.json"


def knows(name: str) -> bool:
    return name in LAYERS


def available() -> bool:
    return path().exists()


# ── 받기 ─────────────────────────────────────────────────────────────

def _get(url: str, **kw):
    try:
        r = requests.get(url, timeout=(settings.UPSTREAM_TIMEOUT, 120), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"}, **kw)
    except requests.RequestException as exc:
        usage.record("orda", ok=False)
        raise OrdaError(f"figshare 에 닿지 못했다: {exc}") from exc
    log.info("orda %s -> %s", r.url, r.status_code)
    usage.record("orda", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:200]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise OrdaError(f"figshare 가 {r.status_code} 로 답했다")
    return r


def download(out: Path) -> dict:
    """항목의 파일 목록에서 엑셀을 찾아 받고, 줄여 `out` 에 적는다. 적은 수를 돌려준다."""
    meta = _get(API).json()
    files = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(".xlsx")]
    if not files:
        raise OrdaError("항목에 엑셀이 없다 — 파일 이름이 바뀌었나")
    time.sleep(PAUSE)
    data = _get(files[0]["download_url"]).content
    lakes = parse(data)
    doc = {"fetched": time.strftime("%Y-%m-%d"), "source": DOI, "version": meta.get("modified_date", "")[:10],
           "license": (meta.get("license") or {}).get("name", ""), "file": files[0]["name"], "lakes": lakes}
    # 다 적은 뒤 바꿔 넣는다 — 적다 멈춰도 화면이 반쪽 파일을 읽지 않게
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    part.replace(out)
    return {region: sum(1 for l in lakes if l["region"] == region) for region in LAYERS.values()}


# ── 엑셀 ─────────────────────────────────────────────────────────────

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(data: bytes) -> dict:
    """xlsx → {시트 이름: 행 목록(칸 목록)}. 공유 문자열과 글 칸만 푼다 — 수식·서식은 보지 않는다."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        rels = {}
        for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
            target = rel.get("Target", "").lstrip("/")
            rels[rel.get("Id")] = target if target.startswith("xl/") else "xl/" + target
        out = {}
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{_NS}sheet"):
            part = rels.get(sheet.get(_REL))
            if part not in names:
                continue
            rows = []
            for row in ET.fromstring(z.read(part)).iter(f"{_NS}row"):
                cells = {}
                for c in row.iter(f"{_NS}c"):
                    kind, v = c.get("t"), c.find(f"{_NS}v")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
                    elif v is None:
                        continue
                    else:
                        value = shared[int(v.text)] if kind == "s" else v.text
                    cells[_col(c.get("r"))] = value
                rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
            out[sheet.get("name")] = rows
        return out


#: 머리줄의 글 → 우리 열. 시트마다 열 차례가 달라 머리줄로 찾는다(그린란드는 `Name / Location`)
_HEADS = (("name", r"^name"), ("lat", r"^lat"), ("lon", r"^lon"), ("kind", r"^lake type"),
          ("method", r"^method"), ("refs", r"^references"), ("area", r"^area"), ("ice", r"^ice thickness"))


def _number(text):
    try:
        return round(float(text), 4)
    except (TypeError, ValueError):
        return None


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse(data: bytes) -> list:
    """엑셀에서 남극·그린란드 빙저호 — `{region, name, lat, lon, kind, method, refs, area, ice}` 목록."""
    sheets = read_xlsx(data)
    lakes = []
    for region in LAYERS.values():
        rows = sheets.get(region)
        if not rows:
            raise OrdaError(f"엑셀에 {region} 시트가 없다")
        head = [_clean(h).lower() for h in rows[0]]
        cols = {}
        for key, pattern in _HEADS:
            for i, h in enumerate(head):
                if re.search(pattern, h):
                    cols[key] = i
                    break
        if not {"lat", "lon"} <= set(cols):
            raise OrdaError(f"{region} 시트에 위경도 열이 없다")

        def cell(row, key):
            i = cols.get(key)
            return row[i] if i is not None and i < len(row) else None

        for row in rows[1:]:
            lat, lon = _number(cell(row, "lat")), _number(cell(row, "lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 360):
                continue
            kind = _clean(cell(row, "kind")).lower()
            lakes.append({"region": region, "name": _clean(cell(row, "name")), "lat": lat,
                          "lon": lon - 360 if lon > 180 else lon,
                          "kind": kind if kind in ("active", "stable") else "unknown",
                          "method": _clean(cell(row, "method")), "refs": _clean(cell(row, "refs")),
                          "area": _clean(cell(row, "area")), "ice": _clean(cell(row, "ice"))})
    return lakes


# ── 내주기 ───────────────────────────────────────────────────────────

def _stamp() -> str:
    try:
        st = path().stat()
    except FileNotFoundError:
        return ""
    return f"{st.st_mtime_ns}-{st.st_size}"


def version() -> str:
    return _stamp()


def body(name: str, lang: str = "ko") -> bytes:
    """레이어 하나의 GeoJSON — 종류의 색(`style: class`). 파일이 없으면 FileNotFoundError."""
    if not available():
        raise FileNotFoundError(path())
    return _body(name, lang, _stamp())


@functools.lru_cache(maxsize=8)
def _body(name: str, lang: str, _stamp: str) -> bytes:
    doc = json.loads(path().read_text(encoding="utf-8"))
    region = LAYERS[name]
    kinds = {code: i18n.t(label, lang) for code, label, _ in KINDS}
    features, counts = [], {}
    for lake in doc["lakes"]:
        if lake["region"] != region:
            continue
        counts[lake["kind"]] = counts.get(lake["kind"], 0) + 1
        props = {"code": lake["kind"], "name": lake["name"], "kind": kinds[lake["kind"]], "method": lake["method"],
                 "area": lake["area"], "ice": lake["ice"], "refs": lake["refs"], "link": DOI}
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lake["lon"], lake["lat"]]},
                         "properties": {k: v for k, v in props.items() if v not in ("", None)}})
    legend = [{"code": code, "label": str(label), "color": color, "shape": "dot", "count": counts[code]}
              for code, label, color in KINDS if counts.get(code)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link"],
                       "legend": legend, "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "orda", "tag": "ORDA", "title": "셰필드대 연구자료 저장소"},
]
