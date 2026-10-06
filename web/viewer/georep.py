"""누벨칼레도니 정부(Géorep — DIMENC 의 지질도)로 나가는 문 — 1:100만·1:20만·1:5만 지질도 (wetherilli 260).

- 주소: `carto.gouv.nc/arcgis/services/geologie_nc/MapServer/WMSServer` (ArcGIS WMS, 정부 Géorep 서버). 열쇠가 없다.
  원본은 3163(RGNC91-93 람베르트)이고 Capabilities 에 3857 이 없지만 3857 로 다시 그려 준다(2026-10-05)
- **WMS 번호와 REST 번호가 다르다**(거꾸로) — WMS `22`·`23` 1:100만 면·경계 = REST 2·1, `15`·`17`·`18` 1:20만 면·구조선·경계 = REST 9·7·6,
  `2`·`3`·`4` 1:5만 면·경계·구조점 = REST 23·22·21. **축척마다 상류가 판을 바꿔 그린다** — 1:30만보다 멀면 1:100만, 1:30만–1:10만은
  1:20만, 1:10만보다 가까우면 1:5만(REST 의 축척 한계). 그래서 레이어는 셋을 한데 묶은 하나다(`LAYERS`)
- **속성은 REST `identify`** — WMS GetFeatureInfo 는 "request not allowed" 다. 화면이 보낸 WMS 꼴(범위·크기·누른 화소)을 그 투영의 좌표 그대로
  넘기고 `visible:` 로 물어 그 축척에서 보이는 판의 면만 받는다. 열은 프랑스어 — 기호·단위·암상·지구·주기, 1:5만은 기·절도
- 범례는 **목록**이다 — WMS GetLegendGraphic 은 XML 오류를 준다. REST `legend` 의 1:20만 면(76 칸)과 1:100만 면(27 칸)을 견본째 잇는다
  (`legend_rows`, `list/legend/`). 1:5만(253 칸)은 재정비 중이라 싣지 않는다
- 조건: **Licence Ouverte (Etalab)** — Géorep 내려받기 목록이 세 축척의 지질도에 그렇게 적는다. 출처 "Gouvernement de la Nouvelle-Calédonie".
  CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

import json

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "georep:"
NAME = "georep:geology"
#: 우리 이름 → 상류 WMS 번호(넓은 축척부터 — 위에 그린 것이 이긴다)
LAYERS = {NAME: "22,23,15,17,18,2,3,4"}
#: 누를 때 묻는 REST 번호 — 축척마다 보이는 면 레이어
REST_QUERY = "visible:2,9,23"
#: 목록 범례를 내는 레이어, 견본을 뜨는 REST 번호(1:20만·1:100만 면), 범례를 담아 두는 날수
LEGEND_LAYERS = (NAME,)
LEGEND_REST = (9, 2)
LEGEND_MAX_AGE = 30 * 86400
ATTRIBUTION = ('<a href="https://georep.nc/" target="_blank" rel="noopener">Gouvernement de la Nouvelle-Calédonie — DIMENC</a> '
               "(Licence Ouverte)")
TIMEOUT = 45


class GeorepError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return bool(name) and all(n.strip() in LAYERS for n in str(name).split(","))


def _base() -> str:
    return settings.GEOREP_URL.rstrip("/")


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GeorepError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("georep", ok=False)
        raise GeorepError(f"Géorep 에 닿지 못했다: {exc}") from exc
    log.info("Géorep %s -> %s", r.url, r.status_code)
    usage.record("georep", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms_url() -> str:
    return f"{_base()}/services/geologie_nc/MapServer/WMSServer"


def _rest_url() -> str:
    return f"{_base()}/rest/services/geologie_nc/MapServer"


def _names(names: str) -> str:
    if not knows(names):
        raise GeorepError(f"모르는 레이어다: {names}")
    return ",".join(LAYERS[n.strip()] for n in str(names).split(","))


def get_map(params: dict):
    params = dict(params, service="WMS", request="GetMap", version="1.3.0")
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params["layers"] = _names(params.get("layers"))
    params.setdefault("styles", "")
    r = _get(_wms_url(), params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GeorepError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise GeorepError("그림 범례 대신 목록 범례(`legend_rows`)를 쓴다")


def legend_rows(layer: str) -> list:
    """1:20만·1:100만 면의 칸 — REST 범례의 이름표(프랑스어 암상)와 견본. 한 번 받아 30 일 담아 둔다"""
    if layer not in LEGEND_LAYERS:
        raise GeorepError(f"범례가 없는 레이어다: {layer}")
    key = tilecache.key_text("georep-legend", "rows")
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _get(f"{_rest_url()}/legend", {"f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise GeorepError("범례가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise GeorepError(f"범례를 받지 못했다 (status={r.status_code})")
    rows = []
    for rest in LEGEND_REST:                                        # 1:20만 먼저, 같은 이름은 처음 것 하나만
        rows += [{"symbol": "", "lithology": label, "age": "", "color": "transparent", "swatch": uri}
                 for label, uri in arcwms.legend_list(data, layer_ids=(rest,)) if label not in {r["lithology"] for r in rows}]
    tilecache.put(key, json.dumps(rows, ensure_ascii=False).encode("utf-8"), ".json")
    return rows


def identify_params(params: dict) -> dict:
    """WMS GetFeatureInfo 꼴 → REST identify 꼴(`ogs.identify_params` 와 같은 셈)"""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if not crs.startswith("EPSG:") or crs == "EPSG:4326":
        raise GeorepError(f"이 좌표계로는 속성을 묻지 않는다: {crs}")
    _names(params.get("query_layers") or params.get("layers"))
    try:
        a0, b0, a1, b1 = (float(v) for v in str(params.get("bbox", "")).split(",")[:4])
        width, height = float(params["width"]), float(params["height"])
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError):
        raise GeorepError("속성을 물을 자리가 없다 (BBOX·WIDTH·HEIGHT·I·J)") from None
    x = a0 + (i + 0.5) * (a1 - a0) / width
    y = b1 - (j + 0.5) * (b1 - b0) / height
    return {"geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "sr": crs.split(":")[1],
            "layers": REST_QUERY, "tolerance": 1, "mapExtent": f"{a0},{b0},{a1},{b1}",
            "imageDisplay": f"{int(width)},{int(height)},96", "returnGeometry": "false", "f": "json"}


def get_feature_info(params: dict) -> dict:
    r = _get(f"{_rest_url()}/identify", identify_params(params))
    if r.status_code != 200:
        raise GeorepError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise GeorepError("속성이 JSON 이 아니다") from exc
    if isinstance(data, dict) and "error" in data:
        raise GeorepError(f"Géorep 의 오류: {(data['error'] or {}).get('message', '')}")
    hits = data.get("results") or []
    return {"features": [{"id": f"georep.{hit.get('layerId')}.{(hit.get('attributes') or {}).get('OBJECTID', n)}",
                          "properties": hit.get("attributes") or {}}
                         for n, hit in enumerate(hits[:1])]}


def _age(text: str) -> str:
    """`Paléocène - Eocène`·`Bartonien - Priabonien` → ICS 영어. 못 옮기면 빈 글"""
    text = str(text or "").strip()
    if not text:
        return ""
    sides = [x.strip() for x in text.split(" - ")]
    moved = [i18n.age_fr(x) for x in sides]
    return " – ".join(moved) if all(m and m != x for m, x in zip(moved, sides)) else ""


#: 상류의 열(별칭) → 팝업 이름. 적은 차례로. 1:20만은 Notation·Lithologie·Groupe·Description(그 판의 Code 는 일련번호라 Notation 이 앞선다),
#: 1:100만·1:5만은 Code·Unité·Lithologie·…
FRIENDLY = (("Notation", "기호"), ("Code", "기호"), ("Unité", "단위"), ("Lithologie", "암석"), ("Groupe lithologie", "암석 갈래"),
            ("Description", "설명"), ("Province", "지질구"), ("Cycle", "주기"))


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(프랑스어)은 그대로 — 1:5만의 기·절만 ICS 로 옮긴다(절이 옮겨지면 절, 아니면 기)"""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and value.lower() not in ("null", "<null>") and label not in out:
            out[label] = value
    ics = _age(props.get("Etage")) or _age(props.get("Période"))
    if ics:
        out["지질시대"] = i18n.age_ko(ics) if lang == "ko" else ics
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "georep", "tag": "NC", "title": "누벨칼레도니 정부 (Géorep)", "relay": True, "projected": True, "globe": True},
]
