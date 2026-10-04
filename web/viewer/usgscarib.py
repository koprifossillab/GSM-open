"""USGS World Energy Project 지질도로 나가는 문 — 카리브(French & Schenk 2004, OFR 97-470-K, wetherilli 248)와
남미(Schenk 외 1999, OFR 97-470-D, wetherilli 256). 같은 USGS 계정의 같은 꼴 피처 서비스라 문 하나가 둘을 맡는다.

- 주소: `services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Caribbean_Geology/FeatureServer/2` (USGS 공식 계정의 ArcGIS Online 피처 서비스).
  열쇠가 없다. 옛 주소(`certmapper.cr.usgs.gov/…/geology/caribbean/MapServer`)는 301 다음 403 으로 죽었다
- **피처 서비스라 그림이 없다** — 면(6 343)을 한 덩이로 받아 화면이 구워 그린다(중국 geo3al·얀마옌과 같은 꼴, `kind: points`·`render: image`).
  상류에는 처음 한 번만 묻는다 — 2 000 개씩 네 번, `maxAllowableOffset` 0.005°(1:250만 지도라 500 m 로 줄여도 그림이 같다)·소수 넷째 자리로
  받아 2 MB 남짓을 캐시에 30 일 둔다(`HELD_SECONDS`)
- 덮는 곳: 카리브와 중미 전부(서경 93°–58°, 북위 7°–28°) — 쿠바·아이티·자메이카·바하마·소앤틸리스·과테말라·온두라스·엘살바도르·벨리즈까지.
  나라 기관의 지질도가 없거나 닫힌 곳을 메운다(docs/다른_대륙_지질도.md 끝 절)
- 속성은 `AGE`(기호 — Q·uK·lT·Tpm…)와 `DESCRPTN`(영어 설명 — "Pliocene and Miocene strata")뿐이다. 색은 서비스의 칠하기 규칙(AGE 73 칸)을 쓴다 —
  무늬 채움이라 색이 비어 있는 칸은 기호의 시대 글자로 갈음색을 고른다(`_FALLBACK`)
- 조건: **공공 도메인**(USGS), 인용 doi 10.3133/ofr97470K. CORS `*`
- **남미**(`South_America_Geology/FeatureServer/2`, 면 4 960) — 칠레·볼리비아·가이아나·수리남·프랑스령 기아나처럼 나라 서비스가 닫힌 곳을
  공공 도메인으로 덮는다. 열은 `GLG`(기호) 하나 — 설명은 칠하기 규칙의 이름표("Cv Cretaceous-Tertiary volcanics")에서 기호를 떼어 쓴다.
  화산암·관입암은 무늬 채움이라 색이 없고 변성암은 검정이라 우리 색으로 갈음한다(`_SA_COLORS`). `U`(미조사)는 싣지 않는다.
  1:500만 급이라 0.02° 로 줄인다
"""
import json
import logging

import requests
from django.conf import settings

from . import tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "usgscarib:"
NAME = "usgscarib:geology"
SA_NAME = "usgscarib:sa:geology"
ATTRIBUTION = ('<a href="https://doi.org/10.3133/ofr97470K" target="_blank" rel="noopener">USGS — Geologic map of the Caribbean region</a> '
               "(French & Schenk 2004, public domain)")
SOURCE_URL = "https://doi.org/10.3133/ofr97470K"
SA_ATTRIBUTION = ('<a href="https://doi.org/10.3133/ofr97470D" target="_blank" rel="noopener">USGS — Geologic map of South America</a> '
                  "(Schenk et al. 1999, public domain)")
SA_SOURCE_URL = "https://doi.org/10.3133/ofr97470D"
SA_SIMPLIFY = 0.02
#: 남미의 색 없는 칸(무늬 채움)·검정 칸·투명 칸의 갈음색
_SA_COLORS = {"Cv": "#f08a4b", "Qv": "#f6b26b", "Mv": "#a3d977", "Pv": "#e07a5f", "PZv": "#9b8cc4",
              "MCi": "#e0457b", "PMi": "#c2508a", "Mm": "#6fa36a", "PZm": "#8478b0", "ICE": "#eef4f8"}
PAGE = 2000
SIMPLIFY = 0.005
HELD_SECONDS = 30 * 86400
LABELS = {"code": "기호", "desc": "설명"}
#: 색이 비어 있는 칸의 갈음색 — 기호의 첫 시대 글자(소문자 꾸밈 lT·uK 은 건너뛴다)
_FALLBACK = (("Q", "#f9f97f"), ("T", "#fdb46c"), ("K", "#7fc64e"), ("J", "#34b2c9"), ("Tr", "#812b92"),
             ("P", "#f04028"), ("M", "#67a599"), ("D", "#cb8c37"), ("pC", "#f74370"), ("Pz", "#99c08d"))


class UsgsCaribError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in (NAME, SA_NAME)


def _get(params: dict, path: str = "query", base: str = ""):
    left = usage.paused()
    if left:
        raise UsgsCaribError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{(base or settings.USGSCARIB_URL).rstrip('/')}/{path}".rstrip("/")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("usgscarib", ok=False)
        raise UsgsCaribError(f"USGS 카리브 지질도에 닿지 못했다: {exc}") from exc
    log.info("USGS 카리브 %s -> %s", r.url, r.status_code)
    usage.record("usgscarib", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise UsgsCaribError(f"받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise UsgsCaribError("JSON 이 아니다") from exc
    if isinstance(data, dict) and data.get("error"):
        raise UsgsCaribError(f"상류 오류: {data['error'].get('message', '')}")
    return data


def _held(name: str, fetch) -> dict:
    key = tilecache.key_text("usgscarib", name)
    held = tilecache.get(key, ".json", max_age=HELD_SECONDS)
    if held is not None:
        return json.loads(held)
    data = fetch()
    tilecache.put(key, json.dumps(data, separators=(",", ":")).encode("utf-8"), ".json")
    return data


def _pages(base: str, fields: str, simplify: float, order: str) -> list:
    """면 전부(위경도 GeoJSON, 줄인 모양). 2 000 개씩 받아 잇는다"""
    out, offset = [], 0
    while True:
        page = _get({"where": "1=1", "outFields": fields, "outSR": "4326", "f": "geojson",
                     "resultOffset": str(offset), "resultRecordCount": str(PAGE),
                     "maxAllowableOffset": str(simplify), "geometryPrecision": "4", "orderByFields": order}, base=base)
        got = page.get("features") or []
        out.extend(got)
        if len(got) < PAGE and not (page.get("properties") or {}).get("exceededTransferLimit"):
            break
        offset += len(got)
        if not got or offset > 50000:
            break
    return out


def features() -> list:
    """카리브 면 전부"""
    def fetch():
        return {"features": _pages(settings.USGSCARIB_URL, "AGE,DESCRPTN", SIMPLIFY, "OBJECTID_1")}
    return _held("features", fetch)["features"]


def sa_features() -> list:
    """남미 면 전부"""
    return _held("sa_features", lambda: {"features": _pages(settings.USGSCARIB_SA_URL, "GLG", SA_SIMPLIFY, "OBJECTID")})["features"]


def colors(name: str = NAME) -> dict:
    """기호 → (영어 이름표, 색). 서비스의 칠하기 규칙에서 — 한 번 받아 둔다. 색이 없거나 투명하면 빈 글"""
    sa = name == SA_NAME
    def fetch():
        base = settings.USGSCARIB_SA_URL if sa else ""
        info = (_get({"f": "json"}, path="", base=base).get("drawingInfo") or {}).get("renderer") or {}
        table = {}
        for u in info.get("uniqueValueInfos") or []:
            c = (u.get("symbol") or {}).get("color")
            table[str(u.get("value") or "").strip()] = [str(u.get("label") or "").strip(),
                                                         "#%02x%02x%02x" % tuple(c[:3]) if c and (len(c) < 4 or c[3]) else ""]
        return table
    return _held("sa_colors" if sa else "colors", fetch)


def _fallback(code: str) -> str:
    bare = code.lstrip("lmu")
    for prefix, color in _FALLBACK:
        if bare.startswith(prefix):
            return color
    return "#bbbbbb"


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `geo3al.body` 와 같다(`style: unit`, 칸마다 code·color, 범례)"""
    if not knows(name):
        raise UsgsCaribError(f"모르는 레이어다: {name}")
    sa = name == SA_NAME
    items, table, counts = [], colors(name), {}

    def color_of(code):
        if sa:
            return _SA_COLORS.get(code) or (table.get(code) or ["", ""])[1] or "#bbbbbb"
        return (table.get(code) or ["", ""])[1] or _fallback(code)

    for f in sa_features() if sa else features():
        p = f.get("properties") or {}
        code = str(p.get("GLG" if sa else "AGE") or "").strip() or ("U" if sa else "Und")
        if sa and code == "U":                                 # 미조사 — 싣지 않는다
            continue
        if sa:
            label = (table.get(code) or [""])[0]
            desc = label[len(code):].strip() if label.startswith(code) else label
        else:
            desc = str(p.get("DESCRPTN") or "").strip()
        items.append({"type": "Feature", "geometry": f.get("geometry"),
                      "properties": {k: v for k, v in {"code": code, "color": color_of(code), "desc": desc}.items() if v}})
        counts[code] = counts.get(code, 0) + 1
    legend = []
    for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = (table.get(code) or [""])[0] or code
        legend.append({"code": code, "label": label, "color": color_of(code), "count": n})
    out = {"type": "FeatureCollection", "labels": LABELS, "style": "unit", "legend": legend, "features": items}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
