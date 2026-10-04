"""태국 광물자원국(DMR)으로 나가는 문 — 태국 암석 단위 1:25만 (wetherilli 228).

- 주소: `gisportal.dmr.go.th/arcgis/services/GEOL/ROCK_UNIT_250K/MapServer/WMSServer` (ArcGIS WMS), REST `…/rest/services/GEOL/ROCK_UNIT_250K/
  MapServer`. 열쇠가 없다. 원본은 UTM 47N(32647)인데 3857 GetMap 이 그린다(2026-10-04, 치앙마이 둘레 256² 0.7 초)
- 속성은 geojson 이지만 **기호와 편집 연도뿐**이다 — 열 이름도 태국어(`อักษรสัญลักษณ์…`). 단위 이름은 REST `legend`(94 칸, `Qa ตะกอน…`)에
  있어 한 번 받아 두고 기호로 찾아 붙인다. 이름은 태국어 그대로다
- 시대는 기호의 앞 대문자(태국 지질도의 관례 — `Q`·`T`·`K`·`J`·`Tr`·`P`·`C`·`D`·`S`·`O`·`E`(캄브리아)·`PE`(선캄브리아))에서 푼다
- 범례는 REST `legend` 를 목록으로 낸다(`list/legend/`) — 기호·태국어 이름·풀린 시대
- 조건: copyright 비어 있음 — **밖에 열기 전에 사람이 읽는다**. CORS 는 Origin 을 되비춘다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "dmr:"
ATTRIBUTION = ('<a href="https://www.dmr.go.th/" target="_blank" rel="noopener">Department of Mineral Resources, Thailand</a> — '
               "Rock units 1:250,000")
LAYERS = {"dmr:rock_units": "0"}
LEGEND_LAYERS = ("dmr:rock_units",)
SYMBOL = "อักษรสัญลักษณ์ของหน่วยหินที่ปรากฏบนแผนที่"
YEAR = "ปี ค.ศ. ที่ประมวลผล"
LEGEND_MAX_AGE = 30 * 86400
#: 기호의 시대 글자 — 긴 것부터 맞춘다
_CODES = (("PE", "Precambrian"), ("Tr", "Triassic"), ("Q", "Quaternary"), ("T", "Tertiary"), ("K", "Cretaceous"),
          ("J", "Jurassic"), ("P", "Permian"), ("C", "Carboniferous"), ("D", "Devonian"), ("S", "Silurian"),
          ("O", "Ordovician"), ("E", "Cambrian"))


class DmrError(RuntimeError):
    pass


def _base() -> str:
    return settings.DMR_URL.rstrip("/")


def _url() -> str:
    return f"{_base()}/services/GEOL/ROCK_UNIT_250K/MapServer/WMSServer"


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise DmrError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("dmr", ok=False)
        raise DmrError(f"DMR 에 닿지 못했다: {exc}") from exc
    log.info("DMR %s -> %s", r.url, r.status_code)
    usage.record("dmr", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


DOOR = arcwms.Door(url=_url, layers=LAYERS, queryable=("dmr:rock_units",), get=_get, error=DmrError)
knows, get_map = DOOR.knows, DOOR.get_map


def get_legend(layer: str):
    raise DmrError("그림 범례 대신 목록 범례(`legend_rows`)를 쓴다")


def age_of(symbol: str) -> str:
    """기호(`Trm`·`KTpk`·`SDCtn`·`PE`) → ICS 이름(영어). 앞의 시대 글자를 이어 읽고 처음과 끝을 잇는다. 못 읽으면 빈 글"""
    text, found = str(symbol or "").strip(), []
    while text:
        for code, name in _CODES:
            if text.startswith(code):
                found.append(name)
                text = text[len(code):]
                break
        else:
            break
    if not found:
        return ""
    return found[0] if len(found) == 1 or found[0] == found[-1] else f"{found[0]} – {found[-1]}"


def _legend() -> list:
    """REST `legend` 의 칸 — `[(기호, 태국어 이름, 견본)]`. 한 번 받아 담아 둔다"""
    key = tilecache.key_text("dmr-legend", "ROCK_UNIT_250K")
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is None:
        r = _get(f"{_base()}/rest/services/GEOL/ROCK_UNIT_250K/MapServer/legend", {"f": "json"})
        try:
            data = r.json()
        except ValueError as exc:
            raise DmrError("범례가 JSON 이 아니다") from exc
        if r.status_code != 200 or data.get("error"):
            raise DmrError(f"범례를 읽지 못했다 (status={r.status_code})")
        held = json.dumps(arcwms.legend_list(data, layer_ids=(0,))).encode("utf-8")
        tilecache.put(key, held, ".json")
    rows = []
    for label, swatch in json.loads(held):
        symbol, _, name = label.partition(" ")
        rows.append((symbol, name.strip(), swatch))
    return rows


def legend_rows(layer: str) -> list:
    if layer not in LEGEND_LAYERS:
        raise DmrError(f"범례가 없는 레이어다: {layer}")
    return [{"symbol": s, "lithology": n, "age": age_of(s), "color": "transparent", "swatch": w}
            for s, n, w in _legend() if s and not s.lower().startswith("water")]


def get_feature_info(params: dict) -> dict:
    """속성에 단위 이름(`_name`)을 범례에서 찾아 붙인다 — 상류는 기호만 준다. 범례를 못 받아도 속성은 낸다"""
    data = DOOR.get_feature_info(params)
    try:
        names = {s: n for s, n, _ in _legend()}
    except DmrError as exc:
        log.info("태국 범례를 받지 못했다: %s", exc)
        names = {}
    for f in data["features"]:
        props = f.get("properties") or {}
        name = names.get(str(props.get(SYMBOL) or "").strip())
        if name:
            props["_name"] = name
    return data


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름은 태국어 그대로, 시대는 기호에서 풀어 옮긴다"""
    symbol = str(props.get(SYMBOL) or "").strip()
    age = age_of(symbol)
    rows = (("기호", symbol), ("이름", props.get("_name", "")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("편집 연도", props.get(YEAR, "")))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip()}

