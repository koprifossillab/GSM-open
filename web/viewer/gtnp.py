"""GTN-P 영구동토 시추공으로 나가는 문 — 북극해·남극 탭의 지온 관측공 점 (wetherilli 422).

시추공 목록은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 Arctic Portal 이 GTN-P(Global Terrestrial Network for Permafrost) 데이터베이스를 내는 GeoServer WFS
  (`flatey.arcticportal.org/geoserver/page21/ows`). **열쇠가 없다.** 문서에 적힌 주소가 아니라, 옛 GTN-P 포털
  (gtnp.arcticportal.org)의 지도가 쓰던 것이다 — 예고 없이 닫힐 수 있어 화면이 부를 때 타지 않는다
- 받는 레이어는 `page21:magt` 하나다. `page21:tsp`(시추공 메타데이터)와 행이 같고(1 389, 번호가 `borehole_id` 로 맞다)
  깊이·고도·영구동토대에 더해 **1978–2016 년의 해마다 연평균 지온(MAGT)** 과 그 깊이가 붙어 있다. CSV 한 장(430 KB)
- 조건은 CC BY 3.0 — PANGAEA 사본 둘(시추공 메타데이터 842820, 2007–2016 지온 884711)이 그렇게 적고 "Always quote
  citation above when using data!" 라 한다. 인용 꼴은 `CREDIT`
- `manage.py fetch_gtnp` 가 한 번 받아 `<GTNP_DIR>/gtnp_boreholes.json` 에 줄여 적는다. 화면은 이 파일만 읽는다.
  같은 GeoServer 의 `magt_composite` 는 자료 제공자의 전자우편이 든다 — 받지 않는다
- 북극해 탭은 북위 50° 너머, 남극 탭은 남위 60° 너머만 싣는다. 몽골·중국·알프스의 공(북위 27–50°)은 실을 탭이 없다
"""
import csv
import io
import json
import logging
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

WFS = "https://flatey.arcticportal.org/geoserver/page21/ows"
LAYER = "page21:magt"
CREDIT = "GTN-P (2015, 2018), PANGAEA (CC BY 3.0)"
SOURCE_URL = "https://doi.pangaea.de/10.1594/PANGAEA.842820"
#: 카탈로그의 레이어 → 싣는 위도 (남, 북)
LAYERS = {
    "gtnp:boreholes_arctic": (50.0, 90.0),
    "gtnp:boreholes_antarctica": (-90.0, -60.0),
}
#: 해마다의 지온 열 — 상류의 열 이름이 해다
YEARS = tuple(str(y) for y in range(1978, 2017))
#: 가장 최근 지온의 구간 → (번호, 이름, 색). 0 °C 가까이가 녹는 쪽이라 따뜻한 색으로 끝난다
CLASSES = (
    ("cold", "−5 °C 밑", "#2c5aa0"),
    ("cool", "−5 ~ −2 °C", "#5fa8d3"),
    ("near", "−2 ~ 0 °C", "#f2b134"),
    ("warm", "0 °C 넘음", "#d1495b"),
    ("none", "지온 자료 없음", "#8c8c8c"),
)
#: 팝업의 열 — 차례가 팝업의 차례다. 이름은 한국어 원문, 영어는 `i18n.PROP_EN`
LABELS = {"name": "시추공", "site": "지점", "country": "나라", "gtnp": "GTN-P 번호", "zone": "영구동토대",
          "depth": "시추 깊이 (m)", "elev": "고도 (m)", "magt": "연평균 지온 (°C)", "magt_year": "지온의 해",
          "magt_depth": "지온 깊이 (m)", "years": "지온 관측 해", "trend": "지온 추세 (°C/년)", "pi": "자료 책임자"}
#: 상류의 영구동토대 표기가 대소문자로 갈린다 — 하나로
ZONES = {"no permafrost": "No permafrost", "isolated patches": "Isolated patches"}


class GtnpError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.GTNP_DIR) / "gtnp_boreholes.json"


def available() -> bool:
    return path().exists()


def knows(name: str) -> bool:
    return name in LAYERS


# ── 받기 ─────────────────────────────────────────────────────────────

def _get() -> str:
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": LAYER, "outputFormat": "CSV"}
    try:
        r = requests.get(WFS, params=params, timeout=(settings.UPSTREAM_TIMEOUT, 120),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gtnp", ok=False)
        raise GtnpError(f"Arctic Portal 에 닿지 못했다: {exc}") from exc
    log.info("gtnp %s -> %s", r.url, r.status_code)
    if r.status_code != 200:
        usage.record("gtnp", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise GtnpError(f"Arctic Portal 이 {r.status_code} 로 답했다")
    r.encoding = "utf-8"
    if not r.text.startswith("FID,"):
        usage.record("gtnp", ok=False)
        raise GtnpError("Arctic Portal 이 CSV 가 아닌 것을 주었다")
    usage.record("gtnp", ok=True, elapsed=r.elapsed)
    return r.text


def _num(text, digits: int = 2):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return round(value, digits) if digits else int(round(value))


def _depths(lo, hi) -> str:
    lo, hi = _num(lo, 1), _num(hi, 1)
    if lo is None:
        return ""
    lo, hi = f"{lo:g}", f"{hi:g}" if hi is not None else ""
    return lo if not hi or hi == lo else f"{lo}–{hi}"


def row_of(p: dict):
    """CSV 한 줄 → 담을 dict. 자리가 없으면 None. 지온은 값이 있는 마지막 해의 것"""
    lon, lat = _num(p.get("longitude"), 5), _num(p.get("latitude"), 5)
    if lon is None or lat is None:
        return None
    last = next(((y, v) for y in reversed(YEARS) if (v := _num(p.get(y))) is not None), None)
    zone = (p.get("permafrost_zone") or "").strip()
    first, final = (p.get("first_year") or "").strip(), (p.get("last_year") or "").strip()
    out = {"id": _num(p.get("borehole_id"), 0), "lon": lon, "lat": lat,
           "name": (p.get("borehole_name") or "").strip(), "site": (p.get("site_name") or "").strip(),
           "country": (p.get("country_name") or "").strip(), "gtnp": (p.get("gtnp_code") or "").strip(),
           "zone": ZONES.get(zone.lower(), zone), "depth": _num(p.get("borehole_drilled_depth"), 1),
           "elev": _num(p.get("elevation"), 0), "pi": " ".join((p.get("responsible_person_name") or "").split())}
    if last:
        out.update(magt=last[1], magt_year=int(last[0]),
                   magt_depth=_depths(p.get("min_magt_depth"), p.get("max_magt_depth")),
                   years=first if not final or final == first else f"{first}–{final}")
        if (_num(p.get("year_count"), 0) or 0) >= 3:
            out["trend"] = _num(p.get("timeseries_slope"), 3)
    return {k: v for k, v in out.items() if v not in (None, "")}


def parse(text: str) -> list:
    return [r for r in (row_of(p) for p in csv.DictReader(io.StringIO(text))) if r]


def download(dest: Path) -> dict:
    """시추공 목록을 받아 줄여 `dest` 에 적는다. {시추공 수, 지온이 있는 수}."""
    left = usage.paused()
    if left:
        raise GtnpError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    rows = parse(_get())
    if not rows:
        raise GtnpError("Arctic Portal 이 빈 목록을 주었다")
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps({"source": LAYER, "fetched": time.strftime("%Y-%m-%d"), "license": "CC BY 3.0",
                               "rows": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(dest)
    return {"boreholes": len(rows), "magt": sum("magt" in r for r in rows)}


# ── 읽기 ─────────────────────────────────────────────────────────────

def class_of(magt) -> str:
    if magt is None:
        return "none"
    return "cold" if magt <= -5 else "cool" if magt <= -2 else "near" if magt <= 0 else "warm"


_memo = {}


def _load() -> dict:
    stamp = path().stat().st_mtime        # 없으면 FileNotFoundError — 부르는 쪽이 "아직 받지 않았다" 로 옮긴다
    if _memo.get("stamp") != stamp:
        _memo.clear()
        _memo.update(stamp=stamp, data=json.loads(path().read_text(encoding="utf-8")))
    return _memo["data"]


def features(name: str) -> list:
    south, north = LAYERS[name]
    out = []
    for r in _load()["rows"]:
        if not south <= r["lat"] <= north:
            continue
        props = {k: v for k, v in r.items() if k not in ("id", "lon", "lat")}
        props["code"] = class_of(r.get("magt"))          # 칠하기 칸 — 범례(`legend`)의 번호
        out.append({"type": "Feature", "id": r.get("id"), "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                    "properties": props})
    return out


def body(name: str) -> bytes:
    """레이어 하나의 덩이 — 극지연구소 파일 레이어와 같은 꼴(`style: class`·`labels`·`legend`). 파일이 없으면 FileNotFoundError"""
    feats = features(name)
    counts = {}
    for f in feats:
        counts[f["properties"]["code"]] = counts.get(f["properties"]["code"], 0) + 1
    legend = [{"code": c, "label": label, "color": color, "shape": "dot", "count": counts[c]}
              for c, label, color in CLASSES if counts.get(c)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": [], "legend": legend,
                       "harvested": _load().get("fetched"), "features": feats},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "gtnp", "tag": "GTN-P", "title": "영구동토 관측망"},
]
