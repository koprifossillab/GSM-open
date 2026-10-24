"""PANGAEA 로 나가는 문 — 극지 현장 둘레의 자료 목록을 점으로 (wetherilli 421).

PANGAEA(AWI·MARUM 이 차린 지구·환경과학 자료 출판소)의 자료는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 PANGAEA 검색 화면이 쓰는 Elasticsearch(`ws.pangaea.de/es/pangaea/panmd/_search`). **열쇠가 없다.** CORS 머리가
  없어 브라우저가 곧장 부를 수 없다 — 그래도 서버가 그때그때 부르지 않는다. KPDC(`kopri.py`)처럼 **모아 둔다** —
  `manage.py fetch_pangaea` 가 1 초에 한 번 받아 `<PANGAEA_DIR>/pangaea.json` 에 줄여 적고, 화면은 이 파일만 읽는다
- 자료마다 **가운데 자리(`meanPosition`) 하나**를 점으로 둔다. 같은 관측소의 자료(다산 기지 옆 BSRN 복사 관측의 달마다의 자료
  따위)는 한 점에 수백 개가 겹친다 — 누르면 겹친 것이 다 나온다
- **메타데이터만 싣는다** — 제목·저자·연도·사업·주제·자료의 조건·DOI. PANGAEA 이용 약관 6.2 가 메타데이터를 CC0 로 낸다.
  자료 본문은 자료마다 조건이 다르고(대개 CC BY) DOI 로 잇기만 한다
- 자료의 조건은 검색 응답의 큰 XML(`xml`, 건당 15–40 KB)에만 있다. 받을 때 그 안에서 조건 이름만 뽑고 XML 은 버린다
- 모으는 범위는 **현장 다섯의 둘레**다(`AREAS`) — 세종(킹조지섬)·장보고(테라노바만)·다산(콩스피오르)·그린란드 둘(디스코만·
  자켄베르그). 주제는 가리지 않는다. 극지 전체의 지질(Lithosphere) 자료는 다음으로 미뤘다(TODOs)
"""
import html as htmlmod
import json
import logging
import re
import time
from pathlib import Path

import requests
from django.conf import settings

from . import i18n, usage
from .i18n import msg

log = logging.getLogger(__name__)

SEARCH = "https://ws.pangaea.de/es/pangaea/panmd/_search"
#: 쪽 하나에 받는 자료 수. XML 이 붙어 쪽마다 4–8 MB 다
PAGE = 200
PAUSE = 1.0
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS` 와 같다)
DIGITS = 5
ATTRIBUTION = "PANGAEA · metadata CC0"
HOME = "https://www.pangaea.de/"
#: 받는 열 — `xml` 은 조건을 뽑으려고만 받는다
SOURCE = ("URI", "meanPosition", "agg-author", "agg-pubYear", "agg-topic", "agg-project", "sp-lastModified",
          "sp-hidden", "xml-thumb", "xml")

#: 현장 → (탭, 이름, (서, 남, 동, 북)). 네모는 2026-10-23 에 건수를 세어 본 것이다(devlog wetherilli 421).
#: 이름은 팝업의 값이라 서버가 말마다 옮겨 낸다(`file_body` 의 `lang`)
AREAS = {
    "sejong": ("antarctica", msg("킹조지섬 (세종 기지)"), (-59.1, -62.3, -57.5, -61.9)),
    "jangbogo": ("antarctica", msg("테라노바만 (장보고 기지)"), (163.5, -75.2, 165.5, -74.4)),
    "dasan": ("svalbard", msg("콩스피오르 (다산 기지)"), (10.5, 78.7, 13.0, 79.2)),
    "disko": ("greenland", msg("디스코만"), (-55.0, 69.0, -50.0, 70.5)),
    "zackenberg": ("greenland", msg("자켄베르그"), (-21.5, 74.3, -20.0, 74.7)),
}
TABS = ("antarctica", "svalbard", "greenland")

#: 주제 → (코드, 한국어, 색, PANGAEA 주제). 자료 하나에 주제가 여럿이면 위에서부터 먼저 맞는 것 — 퇴적물의 지화학은 지질로 간다
TOPICS = (
    ("litho", "지질·퇴적물", "#8c510a", ("Lithosphere", "Paleontology")),
    ("cryo", "빙권", "#2c7fb8", ("Cryosphere",)),
    ("bio", "생물", "#66a61e", ("Biosphere", "Ecology", "Biological Classification")),
    ("ocean", "해양", "#1b9e77", ("Oceans",)),
    ("atmo", "대기", "#7570b3", ("Atmosphere",)),
    ("chem", "화학", "#c51b7d", ("Chemistry",)),
    ("other", "그 밖", "#6b6b6b", ()),
)

#: 레이어 → (탭, 주제 코드). 카탈로그 씨앗(`data/pangaea_<탭>_layers.json`)에는 자료가 있는 것만 넣었다
LAYERS = {f"pangaea:{code}_{tab}": {"tab": tab, "topic": code} for tab in TABS for code, *_ in TOPICS}

LABELS = {"title": "제목", "authors": "저자", "year": "연도", "project": "사업", "topics": "주제",
          "area": "현장", "license": "자료의 조건", "doi": "PANGAEA 자료 (DOI)"}
LINKS = ("doi",)
#: 팝업의 저자는 이만큼만 — 넘으면 "et al." (사람 이름 줄이라 옮기지 않는다)
AUTHORS = 3


class PangaeaError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.PANGAEA_DIR) / "pangaea.json"


def available() -> bool:
    return path().exists()


def knows(name: str) -> bool:
    return name in LAYERS


# ── 받기 ─────────────────────────────────────────────────────────────

def _query(box, start: int) -> dict:
    west, south, east, north = box
    return {"from": start, "size": PAGE, "sort": [{"sf-idDataSet": "asc"}], "_source": list(SOURCE),
            "query": {"bool": {"filter": [{"geo_bounding_box": {"meanPosition": {
                "top_left": {"lat": north, "lon": west}, "bottom_right": {"lat": south, "lon": east}}}}]}}}


def _post(body: dict) -> dict:
    try:
        r = requests.post(SEARCH, json=body, timeout=(settings.UPSTREAM_TIMEOUT, 300),
                          verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("pangaea", ok=False)
        raise PangaeaError(f"PANGAEA 에 닿지 못했다: {exc}") from exc
    log.info("pangaea %s from=%s -> %s", SEARCH, body.get("from"), r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:500])
    usage.record("pangaea", ok=r.status_code == 200, blocked=blocked, elapsed=r.elapsed)
    if r.status_code != 200:
        raise PangaeaError(f"PANGAEA 가 {r.status_code} 로 답했다")
    try:
        return r.json()
    except ValueError as exc:
        raise PangaeaError("PANGAEA 가 JSON 이 아닌 것을 주었다") from exc


_TITLE = re.compile(r"<md:title>(.*?)</md:title>", re.S)
_LICENSE = re.compile(r"<md:license\b[^>]*>\s*<md:label>(.*?)</md:label>", re.S)


def _text(pattern, xml: str) -> str:
    m = pattern.search(xml or "")
    return htmlmod.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


def _list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def record(hit: dict, area: str):
    """검색 응답의 한 건 → 담을 것. 자리가 없거나 숨긴 자료면 None."""
    s = hit.get("_source") or {}
    pos = s.get("meanPosition") or {}
    if s.get("sp-hidden") or pos.get("lat") is None or pos.get("lon") is None:
        return None
    rec = {"t": _text(_TITLE, s.get("xml-thumb")) or s.get("URI", ""), "a": _list(s.get("agg-author")),
           "y": s.get("agg-pubYear"), "tp": _list(s.get("agg-topic")), "p": " · ".join(_list(s.get("agg-project"))),
           "lic": _text(_LICENSE, s.get("xml")), "doi": s.get("URI") or "", "mod": s.get("sp-lastModified") or "",
           "lat": round(float(pos["lat"]), DIGITS), "lon": round(float(pos["lon"]), DIGITS), "area": area}
    return {k: v for k, v in rec.items() if v not in ("", [], None)}


def harvest(area: str, pause: float = PAUSE, say=None) -> dict:
    """현장 하나의 자료를 다 받는다 — 자료 번호 → 담을 것."""
    box = AREAS[area][2]
    out, start, total = {}, 0, None
    while total is None or start < total:
        if start:
            time.sleep(pause)
        data = _post(_query(box, start))
        hits = data.get("hits") or {}
        total = hits.get("total") or 0
        if isinstance(total, dict):      # 새 판의 Elasticsearch 는 {"value": n}
            total = total.get("value") or 0
        page = hits.get("hits") or []
        if not page:
            break
        for hit in page:
            rec = record(hit, area)
            if rec:
                out[str(hit["_id"])] = rec
        start += len(page)
        if say:
            say(f"  {area}: {start:,} / {total:,}")
    return out


def download(pause: float = PAUSE, say=None) -> dict:
    """현장 다섯을 다 받아 파일 하나에 적는다. 다 쓴 뒤 바꿔 끼운다 — 받다 멈춰도 앞의 파일이 깨지지 않는다."""
    records, counts = {}, {}
    for index, area in enumerate(AREAS):
        if index:
            time.sleep(pause)
        got = harvest(area, pause, say)
        counts[area] = len(got)
        records.update(got)
    data = {"harvested": time.strftime("%Y-%m-%d"), "areas": counts, "records": records}
    out = path()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)
    return counts


# ── 화면에 내는 것 ────────────────────────────────────────────────────
#
# KPDC 자료(`kopri.file_body`)와 같은 꼴(`style: class`)이다 — feature 마다 `code`, 덩이에 `legend`.
# 팝업 이름·범례 이름은 한국어이고 영어판이면 브라우저가 `T()` 로 옮긴다. 현장 이름만은 값이라 서버가 옮긴다.
# 주제·조건 값은 PANGAEA 의 영어 그대로다.

#: 주제 꼬리표가 없는 자료가 많다(현장 다섯에서 3 천 6 백 — 다산 기지 옆 관측소의 달마다·날마다의 자료). 그때는 사업과 제목으로
#: 가른다. 사업 → 주제 코드
PROJECT_TOPIC = {"BSRN": "atmo", "AC3": "atmo", "AWI_Meteo": "atmo", "LTO_Permafrost_Bayelva": "cryo", "AWI_Perma": "cryo"}
#: 그래도 없으면 제목의 낱말로 — 위에서부터 먼저 맞는 것. 강설 영상 측정기(VISSS)·무인기 기상 관측·CTD 따위
TITLE_TOPICS = (
    ("litho", re.compile(r"sediment|core\b|granulometr|geolog|rock|moraine", re.I)),
    ("ocean", re.compile(r"oceanograph|\bCTD\b|seawater|water column", re.I)),
    ("atmo", re.compile(r"snowfall|radiosonde|meteorolog|ozone|aerosol|lidar|radiation|photometer|wind vector|cloud", re.I)),
)


def topic_of(topics: list, project: str = "", title: str = "") -> str:
    have = set(topics or ())
    for code, _, _, names in TOPICS:
        if have.intersection(names):
            return code
    for name in (project or "").split(" · "):
        if name in PROJECT_TOPIC:
            return PROJECT_TOPIC[name]
    return next((code for code, words in TITLE_TOPICS if words.search(title or "")), "other")


def _topic(rec: dict) -> str:
    return topic_of(rec.get("tp"), rec.get("p"), rec.get("t"))


def _authors(names: list) -> str:
    shown = "; ".join(names[:AUTHORS])
    return shown + (" et al." if len(names) > AUTHORS else "")


def features(records: dict, name: str, lang: str = "ko") -> list:
    spec = LAYERS[name]
    out = []
    for key, rec in records.items():
        area = AREAS.get(rec.get("area"))
        if not area or area[0] != spec["tab"] or _topic(rec) != spec["topic"]:
            continue
        props = {"code": spec["topic"], "title": rec.get("t"), "authors": _authors(rec.get("a") or []),
                 "year": rec.get("y"), "project": rec.get("p"), "topics": " · ".join(rec.get("tp") or []),
                 "area": i18n.t(area[1], lang), "license": rec.get("lic"), "doi": rec.get("doi")}
        out.append({"type": "Feature", "id": key, "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]},
                    "properties": {k: v for k, v in props.items() if v}})
    return out


def legend_for(name: str, feats: list) -> list:
    code = LAYERS[name]["topic"]
    label, color = next((l, c) for c_, l, c, _ in TOPICS if c_ == code)
    return [{"code": code, "label": label, "color": color, "shape": "dot", "count": len(feats)}] if feats else []


def file_body(name: str, lang: str = "ko") -> bytes:
    """모아 둔 파일에서 레이어 하나. 파일이 없으면 FileNotFoundError."""
    data = json.loads(path().read_text(encoding="utf-8"))
    feats = features(data.get("records") or {}, name, lang)
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": list(LINKS),
                       "legend": legend_for(name, feats), "harvested": data.get("harvested"), "features": feats},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "pangaea", "tag": "PANGAEA", "title": "PANGAEA 지구·환경 자료 출판소"},
]
