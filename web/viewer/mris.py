"""몽골 국가지질조사소(NGS)의 MonGeoCat 으로 나가는 문 — 국가지질도첩의 지질도·단층 (wetherilli 221).

- 주소: `gismap.mris.mn/arcgis/services/Atlas/1_Geology/MapServer/WMSServer`(지질), `…/Atlas/2_Faults/…`(단층 1:50만). ArcGIS WMS,
  열쇠가 없다. **문서에 없는 주소다** — MonGeoCat 화면(`webgis.mris.mn`)의 JS 묶음에서 찾았다(docs/아시아_오세아니아_지질도.md).
  예고 없이 바뀔 수 있다
- Capabilities 는 4326·CRS:84 만 적지만 **3857 GetMap 이 그린다**(2026-10-04, 울란바토르 둘레 256² 1.2 초)
- **WMS 번호와 REST 번호가 거꾸로다** — WMS `1` 이 지질, `0` 이 국경(REST 는 0 이 지질). 이름은 WMS 번호로 `mris:<서비스>:<번호>`
- 속성은 `application/geojson`(모양 없이 1 KB) — 몽골어·영어 두 벌(`Formation_Complex_EN` 따위). 지질시대 열은 따로 없고
  **기호(`Label`, `aQ₂`·`J₂₋₃`)가 러시아식 층서 지수**라 거기서 ICS 시대를 푼다(`age_of`)
- 범례: ArcGIS REST `legend?f=json` 의 칸(255)을 목록으로 낸다 — 칸 이름이 `10100_Q2` 꼴이라 지수만 보이고 시대를 풀어 붙인다
- 조건: Capabilities·서비스 설명에 적힌 것이 없다(copyright 비어 있음, 2026-10-04). MonGeoCat 은 호주 원조 사업(AMEP)으로 지질 정보를
  공개하는 체계다. **밖에 열기 전에 사람이 읽는다.** CORS 는 Origin 을 되비춘다
"""
import logging
import re

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "mris:"
#: 메타타일로 받는다 (wetherilli 287) — 512 px 4.3–6.9 초, 1 024 px 7.0 초. 큰 장 하나가 칸 넷보다 싸다. `metatile.limit` 의 표
METATILE = {"mris:": None}
ATTRIBUTION = ('<a href="https://webgis.mris.mn/" target="_blank" rel="noopener">MonGeoCat</a> — '
               "National Geological Survey of Mongolia")
#: 우리 이름 → (서비스, WMS 번호, REST 번호). 국경(WMS 0)은 부르지 않는다
LAYERS = {
    "mris:geology:1": ("1_Geology", "1", "0"),
    "mris:faults:0": ("2_Faults", "0", "0"),
}
QUERYABLE = ("mris:geology:1", "mris:ree")
LEGEND_LAYERS = ("mris:geology:1",)
TIMEOUT = 45


class MrisError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "") in LAYERS or str(name or "") in RESOURCES


#: 희토류(wetherilli 280) → (Atlas 서비스, REST 번호들). `12_REE` 는 WMS 를 켜지 않아 REST `export`·`identify` 로 옮긴다 —
#: 광상 6·광화 지점 280·산지 85. 같은 폴더의 `AtlasPoints` 는 광상 레이어(6–9)가 모두 우물 자료를 돌려줘 쓰지 않는다(2026-10-05)
RESOURCES = {"mris:ree": ("12_REE", "2,3,4")}


def _resource(names) -> str:
    first = str(names or "").split(",")[0].strip()
    return first if first in RESOURCES else ""


def _resource_get(name: str, path: str, query: dict):
    service, _ = RESOURCES[name]
    return _get(f"{_rest_url(service)}/{path}", query)


def _service(names: str) -> tuple:
    """`mris:a:1,mris:a:2` → (서비스, WMS 번호들). 서비스가 다른 것을 한 번에 부르지 않는다"""
    services, numbers = set(), []
    for one in str(names or "").split(","):
        one = one.strip()
        if not knows(one):
            raise MrisError(f"모르는 레이어다: {one}")
        service, number, _ = LAYERS[one]
        services.add(service)
        numbers.append(number)
    if len(services) != 1:
        raise MrisError(f"서비스가 다른 레이어를 한 번에 부를 수 없다: {names}")
    return services.pop(), ",".join(numbers)


def _wms_url(service: str) -> str:
    return f"{settings.MRIS_URL.rstrip('/')}/services/Atlas/{service}/MapServer/WMSServer"


def _rest_url(service: str) -> str:
    return f"{settings.MRIS_URL.rstrip('/')}/rest/services/Atlas/{service}/MapServer"


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise MrisError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("mris", ok=False)
        raise MrisError(f"MonGeoCat 에 닿지 못했다: {exc}") from exc
    log.info("MonGeoCat %s -> %s", r.url, r.status_code)
    usage.record("mris", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> tuple:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    service, numbers = _service(params.get("layers") or params.get("query_layers"))
    params["layers"] = numbers
    if "query_layers" in params:
        params["query_layers"] = _service(params["query_layers"])[1]
    return service, params


def get_map(params: dict):
    name = _resource(params.get("layers"))
    if name:
        try:
            r = _resource_get(name, "export", arcwms.rest_export_params(params, RESOURCES[name][1]))
        except ValueError as exc:
            raise MrisError(str(exc)) from exc
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise MrisError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
        return r.content, ctype
    service, params = _wms(params, "GetMap")
    r = _get(_wms_url(service), params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise MrisError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise MrisError("그림 범례는 칸이 255 라 두지 않는다 — 목록 범례(`legend_rows`)를 쓴다")


def get_feature_info(params: dict) -> dict:
    name = _resource(params.get("query_layers") or params.get("layers"))
    if name:
        try:
            r = _resource_get(name, "identify", arcwms.rest_identify_params(params, RESOURCES[name][1]))
            data = r.json()
        except ValueError as exc:
            raise MrisError(str(exc)) from exc
        if r.status_code != 200 or data.get("error"):
            raise MrisError(f"속성을 읽지 못했다 (status={r.status_code})")
        return {"features": arcwms.identify_features(data, name)}
    service, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(_wms_url(service), params)
    if r.status_code != 200:
        raise MrisError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise MrisError("속성이 JSON 이 아니다") from exc


# ── 층서 지수 → ICS ──────────────────────────────────────────────
# 러시아식 지수다. 글자가 계(Period)이고 붙은 숫자가 통(세)이다. 몽골 지질도첩의 제4기는 둘로만 가른다 — 범례가 Q2 를 홀로세,
# Q1 을 플라이스토세로 쓴다(속성의 `aQ₂` 가 "Holocene sediment"). 속성의 기호는 `Є`·`₽` 를 제 글자로 쓰지만, 범례 칸 이름은
# 둘 다 `E` 로 적는다 — 다섯 자리 코드(3xxxx)에서는 고진기(₽), 여섯 자리(310xxx·관입암 따위)에서는 캄브리아기(Є)다

_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉₋", "0123456789-")
_INDEX = re.compile(r"(NP|MP|PP|PZ|NA|AR|Q|N|E|Є|₽|K|J|T|P|C|D|S|O)(\d)?(?:-(NP|MP|PP|PZ|Q|N|E|Є|₽|K|J|T|P|C|D|S|O)?(\d)?)?")
_THREE = ("Early", "Middle", "Late")
#: 글자 → (계 이름, 통 번호 → 이름)
_PERIODS = {
    "Q": ("Quaternary", {1: "Pleistocene", 2: "Holocene"}),
    "N": ("Neogene", {1: "Miocene", 2: "Pliocene", 3: "Pliocene"}),
    "₽": ("Paleogene", {1: "Paleocene", 2: "Eocene", 3: "Oligocene"}),
    "K": ("Cretaceous", {1: "Early Cretaceous", 2: "Late Cretaceous"}),
    "J": ("Jurassic", {i + 1: f"{w} Jurassic" for i, w in enumerate(_THREE)}),
    "T": ("Triassic", {i + 1: f"{w} Triassic" for i, w in enumerate(_THREE)}),
    "P": ("Permian", {i + 1: f"{w} Permian" for i, w in enumerate(_THREE)}),
    "C": ("Carboniferous", {1: "Mississippian", 2: "Pennsylvanian", 3: "Pennsylvanian"}),
    "D": ("Devonian", {i + 1: f"{w} Devonian" for i, w in enumerate(_THREE)}),
    "S": ("Silurian", {1: "Llandovery", 2: "Wenlock", 3: "Ludlow", 4: "Pridoli"}),
    "O": ("Ordovician", {i + 1: f"{w} Ordovician" for i, w in enumerate(_THREE)}),
    "Є": ("Cambrian", {i + 1: f"{w} Cambrian" for i, w in enumerate(_THREE)}),
    "PZ": ("Paleozoic", {1: "Early Paleozoic", 2: "Late Paleozoic"}),
    "NP": ("Neoproterozoic", {1: "Tonian", 2: "Cryogenian", 3: "Ediacaran"}),
    "MP": ("Mesoproterozoic", {1: "Calymmian", 2: "Ectasian", 3: "Stenian"}),
    "PP": ("Paleoproterozoic", {}),
    "NA": ("Neoarchean", {}),
    "AR": ("Archean", {}),
}


def _one(letter: str, digit, cambrian: bool) -> str:
    if letter == "E":
        letter = "Є" if cambrian else "₽"
    name, series = _PERIODS[letter]
    return series.get(int(digit), name) if digit else name


def age_of(label: str, code: str = "") -> str:
    """층서 지수(`aQ₂`·`J₂₋₃`·`grT₃-J₁`) → ICS 이름(영어). 앞의 소문자(성인·암석 기호)는 건너뛴다. 못 읽으면 빈 글.
    `code` 는 단위 코드(`L_Code`) — `E` 가 고진기인지 캄브리아기인지 가른다"""
    text = str(label or "").translate(_SUB)
    m = _INDEX.search(text)
    if not m:
        return ""
    code = str(code or "")
    cambrian = not (len(code) == 5 and code.startswith("3"))
    first, d1, second, d2 = m.groups()
    a = _one(first, d1, cambrian)
    if not (second or d2):
        return a
    b = _one(second or first, d2, cambrian)
    if a == b:
        return a
    # 같은 계 안의 세 갈래(`Middle Jurassic`·`Late Jurassic`)는 `Middle – Late Jurassic` 으로 줄인다
    wa, wb = a.split(" ", 1), b.split(" ", 1)
    if len(wa) == 2 and len(wb) == 2 and wa[1] == wb[1] and wa[0] in _THREE and wb[0] in _THREE:
        return f"{wa[0]} – {b}"
    return f"{a} – {b}"


def legend_rows(layer: str) -> list:
    """REST `legend?f=json` → 화면이 그리는 줄. 칸 이름이 `10100_Q2` 꼴이라 코드는 떼고 지수를 기호로, 풀린 시대를 함께 적는다"""
    if layer not in LEGEND_LAYERS:
        raise MrisError(f"범례가 없는 레이어다: {layer}")
    service, _, rest_id = LAYERS[layer]
    r = _get(f"{_rest_url(service)}/legend", {"f": "json"})
    if r.status_code != 200:
        raise MrisError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise MrisError("범례가 JSON 이 아니다") from exc
    rows = []
    for part in data.get("layers") or []:
        if str(part.get("layerId")) != rest_id:
            continue
        for item in part.get("legend") or []:
            label = str(item.get("label") or "").strip()
            if not label or not item.get("imageData"):
                continue
            code, _, symbol = label.partition("_")
            age = age_of(symbol, code)
            rows.append({"symbol": symbol or code, "lithology": "", "age": age, "color": "transparent",
                         "swatch": f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"})
    return rows


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "none") else value


def ree_friendly(props: dict) -> dict:
    """희토류 산지 (wetherilli 280) — 영어 이름·성인이 있으면 그것, 없으면 몽골어"""
    v = lambda *keys: next((_value(props, k) for k in keys if _value(props, k)), "")   # noqa: E731
    rows = (("이름", v("Name", "Ord_ilreli")), ("성인", v("Ore_genesis", "garal_uuse")), ("도폭", v("SHEET_REF")))
    return {k: x for k, x in rows if x}


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 영어 열을 쓰고(몽골어는 "원 이름"), 지질시대만 기호에서 풀어 옮긴다"""
    if "Ore_genesis" in props or "garal_uuse" in props or "Ord_ilreli" in props:
        return ree_friendly(props)
    rows = (("기호", _value(props, "Label")), ("이름", _value(props, "Formation_Complex_EN")),
            ("원 이름", _value(props, "Formation_Complex_MN")), ("설명", _value(props, "RockDescription_EN")),
            ("지구조 구역", _value(props, "TecZone_EN")), ("지구조 대구역", _value(props, "MegaZone_EN")))
    out = {k: v for k, v in rows if v}
    if out.get("지구조 대구역") and out.get("지구조 대구역") == out.get("지구조 구역"):
        del out["지구조 대구역"]
    age = age_of(_value(props, "Label"), _value(props, "L_Code"))
    if age:
        out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
    return out
