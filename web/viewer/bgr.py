"""BGR(독일 연방 지구과학·자원청)로 나가는 문 — 독일 지질도 (wetherilli 147), 유럽 1:500만 IGME5000 (wetherilli 217).

- 주소: `services.bgr.de/wms/geologie/<판>/` (ArcGIS WMS). 판은 셋 — `gk1000`(1:100만)·`guek250`(1:25만)·`igme5000`(유럽과 이웃 1:500만,
  2005–2007). 열쇠가 없다
- IGME5000 은 아이슬란드에서 우랄·노바야젬랴·카자흐스탄 서북, 튀르키예·북아프리카 가장자리까지 덮는다. 상류가 축척마다 다른 레이어로
  가른 단층·변성암·연대 기호는 `+` 로 이어 한 레이어로 부른다(`bgr:igme5000:46+47+48` → WMS `46,47,48`). 1:23만보다 가까우면 그리지
  않아 줌 11 까지다. 속성은 판 셋이 다 같은 꼴(`application/geo+json`)이고 IGME5000 은 영어 열(`name older rock age` …)이다
- 조건: BGR 일반 약관(AGB). INSPIRE·WMS 자료는 출처를 밝히면 무료로 쓴다 — 인용 꼴은 GetCapabilities 의 것
  ("Datenquelle: GÜK250 (WMS), (c) BGR, Hannover, 2019"). `ATTRIBUTION`
- 3857 을 그대로 받는다. 판마다 그리는 줌이 좁다 — GK1000 은 9–10, GÜK250 은 10–14(2026-10-02 에 카셀에서 잰 것, `ZOOMS`)
- ArcGIS 의 레이어 이름이 번호(`7`)라 카탈로그에는 `bgr:<판>:<번호>` 로 둔다. 문이 판과 번호로 나눈다
- 속성은 `application/geo+json`. 열 이름이 독일어 표제(`Legendentext`)로 온다. 값은 독일어 그대로 둔다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "bgr:"
ATTRIBUTION = ('Datenquelle: GÜK250 · GK1000 (WMS), <a href="https://www.bgr.bund.de/" target="_blank" rel="noopener">'
               '© BGR</a>, Hannover')
#: 판마다 다른 인용 — Capabilities 가 적은 꼴 그대로
ATTRIBUTIONS = {"igme5000": ('Datenquelle: IGME5000, <a href="https://www.bgr.bund.de/" target="_blank" rel="noopener">'
                             '© BGR</a> Hannover, 2007')}
#: 판마다 그리는 화면 줌(3857, 처음·끝)
ZOOMS = {"gk1000": (9, 10), "guek250": (10, 14), "igme5000": (None, 11)}
#: 누를 것이 없는 레이어 — 단층(선의 갈래 하나뿐)·연대 기호(글자)
NOT_QUERYABLE = ("igme5000:46+47+48", "igme5000:51+53+55+57")


class BgrError(RuntimeError):
    pass


def split(name: str):
    """`bgr:guek250:7` → ("guek250", "7"). 판이 다른 이름이 섞이면 BgrError — 한 요청은 한 판으로만 간다."""
    sheets, layers = set(), []
    for one in str(name or "").split(","):
        one = one.strip()
        if one.startswith(PREFIX):
            one = one[len(PREFIX):]
        sheet, _, layer = one.partition(":")
        if sheet not in ZOOMS or not layer:
            raise BgrError(f"모르는 레이어다: {one}")
        sheets.add(sheet)
        layers.append(layer.replace("+", ","))
    if len(sheets) != 1:
        raise BgrError("판이 다른 레이어를 한 번에 물을 수 없다")
    return sheets.pop(), ",".join(layers)


def attribution(name: str) -> str:
    try:
        return ATTRIBUTIONS.get(split(name)[0], ATTRIBUTION)
    except BgrError:
        return ATTRIBUTION


def queryable(name: str) -> bool:
    return str(name).removeprefix(PREFIX) not in NOT_QUERYABLE


def _get(sheet: str, params: dict):
    left = usage.paused()
    if left:
        raise BgrError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{settings.BGR_WMS_URL.rstrip('/')}/{sheet}/", params=params,
                         timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bgr", ok=False)
        raise BgrError(f"BGR 에 닿지 못했다: {exc}") from exc
    log.info("BGR %s -> %s", r.url, r.status_code)
    usage.record("bgr", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str):
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    sheet, params["layers"] = split(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = split(params["query_layers"])[1]
    return sheet, params


def get_map(params: dict):
    sheet, params = _wms(params, "GetMap")
    r = _get(sheet, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgrError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    sheet, name = split(layer)
    r = _get(sheet, {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                     "layer": name.split(",")[0]})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgrError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    sheet, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(sheet, params)
    if r.status_code != 200:
        raise BgrError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BgrError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로.** GÜK250 은 독일어 표제, GK1000 은 대문자 열이다
FRIENDLY = (
    ("Legendentext", "지질 단위"),
    ("Petrographie - komplett", "암석"),
    ("Petrographie - kurz", "암석"),
    ("PETROGRAPHIE", "암석"),
    ("Stratigraphie - gesamt", "지질시대"),
    ("STRATIGRAPHIE", "지질시대"),
    ("Genese", "성인"),
    ("GENESE", "성인"),
    ("Legendenkürzel", "기호"),
    ("Bemerkungen", "비고"),
)


def _v(props: dict, key: str) -> str:
    value = str(props.get(key) if props.get(key) is not None else "").strip()
    return "" if value.lower() in ("null", "none") else value


def igme5000_friendly(props: dict, lang: str = "ko") -> dict:
    """IGME5000 의 영어 열 → 한국어. 시대 이름만 옮긴다(`Devonian - Permian` → 데본기~페름기). `Alpine`·`Proterozoic III` 처럼
    ICS 에 없는 이름은 그대로 둔다. 연대(Ma)는 소수점이 쉼표로 온다"""
    v = lambda k: _v(props, k)          # noqa: E731
    age = v("name older rock age")
    ma = " – ".join(x.replace(",", ".") for x in (v("younger rock age"), v("older rock age")) if x)
    rock = ", ".join(x for x in (v(f"petrography{n}") for n in range(1, 5)) if x and x != "undifferentiated")
    rows = (("기호", v("symbol older rock age")), ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
            ("연대 (Ma)", ma), ("암석", rock), ("변성암", v("metamorphic rock")), ("화성암", v("igneous rock")),
            ("해양 지질", v("marin geology")), ("성인", v("genetic element")), ("지역", v("regional name")),
            ("경계·구조선", v("boundary or structure line")))
    return {k: x for k, x in rows if x}


def friendly(props: dict, lang: str = "ko") -> dict:
    if "name older rock age" in props or "boundary or structure line" in props:
        return igme5000_friendly(props, lang)
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:
            out[label] = value
    return out
