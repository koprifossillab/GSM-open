"""OGS(온타리오 지질조사소)로 나가는 문 — 온타리오 기반암 1:25만·제4기 지질 (wetherilli 204).

- 주소: `ws.lioservices.lrc.gov.on.ca/arcgis1071a/services/GeologyOntario/GeologyOntario_Map/MapServer/WMSServer` (ArcGIS WMS, LIO 가 낸다).
  열쇠가 없다. **WMS 번호와 REST 번호가 다르다** — WMS `3` 기반암 = REST 57, `1` 제4기 = 52, `6` 단층 = 54, `4` 암맥 = 56,
  `5` 철층 = 55 (2026-10-04). 이름은 WMS 번호로 `ogs:<번호>`
- 원본은 4269 이고 3857·3978 로 다시 그려 준다(Capabilities 에 없어도 된다, 2026-10-04)
- **속성은 REST `identify`** — WMS GetFeatureInfo 가 GeoJSON 을 XML 오류로 돌려준다. 화면이 보낸 WMS 꼴(범위·크기·누른 화소)을 그 투영의
  좌표 그대로 identify 에 넘긴다(`sr` = 그 EPSG 번호). 암상·층서·누대/대·지질구가 온다(영어)
- 단층·철층·암맥 선은 상류가 1:150만보다 가까울 때만 그린다(REST `minScale`)
- CORS 는 Origin 을 되비춘다. 조건: Open Government Licence – Ontario. 출처 "Ontario Geological Survey"
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "ogs:"
#: WMS 번호 → REST 번호
REST_ID = {"3": "57", "1": "52", "6": "54", "4": "56", "5": "55",
           # 광물 산지 목록 MDI(OMEIS Mineral Inventory, 1 만 8 천 곳, wetherilli 288)
           "11": "46"}
ATTRIBUTION = ('Bedrock & Quaternary Geology of Ontario — <a href="https://www.ontario.ca/page/open-government-licence-ontario" '
               'target="_blank" rel="noopener">Ontario Geological Survey, OGL–Ontario</a>')
TIMEOUT = 45


class OgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "").startswith(PREFIX) and str(name)[len(PREFIX):] in REST_ID


def _numbers(names: str) -> list:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if not knows(one):
            raise OgsError(f"모르는 레이어다: {one}")
        out.append(one[len(PREFIX):])
    return out


def _base() -> str:
    return settings.OGS_URL.rstrip("/")


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise OgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ogs", ok=False)
        raise OgsError(f"OGS 에 닿지 못했다: {exc}") from exc
    log.info("OGS %s -> %s", r.url, r.status_code)
    usage.record("ogs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms_url() -> str:
    return f"{_base()}/services/GeologyOntario/GeologyOntario_Map/MapServer/WMSServer"


def _rest_url() -> str:
    return f"{_base()}/rest/services/GeologyOntario/GeologyOntario_Map/MapServer"


def get_map(params: dict):
    params = dict(params, service="WMS", request="GetMap", version="1.3.0")
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params["layers"] = ",".join(_numbers(params.get("layers")))
    params.setdefault("styles", "")
    r = _get(_wms_url(), params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise OgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get(_wms_url(), {"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0", "format": "image/png",
                          "layer": _numbers(layer)[0], "sld_version": "1.1.0"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise OgsError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


def identify_params(params: dict) -> dict:
    """WMS GetFeatureInfo 꼴 → REST identify 꼴. 누른 화소의 가운데를 그 투영의 좌표로 셈한다(4326 은 받지 않는다)."""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if not crs.startswith("EPSG:") or crs == "EPSG:4326":
        raise OgsError(f"이 좌표계로는 속성을 묻지 않는다: {crs}")
    try:
        a0, b0, a1, b1 = (float(v) for v in str(params.get("bbox", "")).split(",")[:4])
        width, height = float(params["width"]), float(params["height"])
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError):
        raise OgsError("속성을 물을 자리가 없다 (BBOX·WIDTH·HEIGHT·I·J)") from None
    x = a0 + (i + 0.5) * (a1 - a0) / width
    y = b1 - (j + 0.5) * (b1 - b0) / height
    layers = ",".join(REST_ID[n] for n in _numbers(params.get("query_layers") or params.get("layers")))
    return {"geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "sr": crs.split(":")[1],
            "layers": f"all:{layers}", "tolerance": 2, "mapExtent": f"{a0},{b0},{a1},{b1}",
            "imageDisplay": f"{int(width)},{int(height)},96", "returnGeometry": "false", "f": "json"}


def get_feature_info(params: dict) -> dict:
    r = _get(f"{_rest_url()}/identify", identify_params(params))
    if r.status_code != 200:
        raise OgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise OgsError("속성이 JSON 이 아니다") from exc
    if isinstance(data, dict) and "error" in data:
        raise OgsError(f"OGS 의 오류: {(data['error'] or {}).get('message', '')}")
    return {"features": [{"id": f"ogs.{hit.get('layerId')}.{(hit.get('attributes') or {}).get('OBJECTID', n)}",
                          "properties": hit.get("attributes") or {}}
                         for n, hit in enumerate(data.get("results") or [])]}


#: 상류의 열 → 팝업 이름. 적은 것만, 적은 차례로. 기반암(…_P)과 제4기의 열이 다르다
FRIENDLY = (
    ("UNITNAME_P", "이름"),
    ("TYPE_P", "기호"),
    ("ROCKTYPE_P", "암석"),
    ("STRAT_P", "층서"),
    ("EPOCH_P", "지질시대"),
    ("PERIOD_P", "지질시대"),
    ("ERA_P", "지질시대"),
    ("EON_P", "지질시대"),
    ("PROVINCE_P", "지질구"),
    # 제4기 — 단위·물질·시대 (2026-10-04 에 토론토 북쪽을 눌러 받은 열)
    ("UNIT_NAME", "이름"),
    ("MATERIAL", "물질"),
    ("AGE", "지질시대"),
)
AGE_KEYS = ("EPOCH_P", "PERIOD_P", "ERA_P", "EON_P", "AGE")


def _age_name(value: str) -> str:
    """`PALEOPROTEROZOIC (1.6 Ga to 2.5 Ga)` → `Paleoproterozoic (1.6 Ga to 2.5 Ga)` — ICS 이름만 첫 글자를 살린다."""
    name, sep, rest = value.partition(" (")
    return name.strip().capitalize() + (f" ({rest}" if sep else "")


#: MDI 의 열 — identify 는 별칭(`MDI Identifier`)을, WMS 는 필드 이름(`MDI_IDENT`)을 준다. 둘 다 읽는다 (wetherilli 288)
MDI_COLS = (("이름", ("NAME", "Name")), ("번호", ("MDI_IDENT", "MDI Identifier")), ("개발 단계", ("STATUS", "Status")),
            ("광종", ("PRIMARY_COMMODITIES", "Primary Commodities")), ("딸린 광종", ("SECONDARY_COMMODITIES", "Secondary Commodities")),
            ("곳", ("TOWNSHIP", "Township or Area")), ("지구", ("RGP_DISTRICT", "RGP District")))


def mdi_friendly(props: dict) -> dict:
    out = {}
    for label, keys in MDI_COLS:
        value = next((str(props[k]).strip() for k in keys if str(props.get(k) or "").strip().lower() not in ("", "null", "<null>")), "")
        if value:
            out[label] = value
    link = next((str(props[k]) for k in ("INFO_LINK", "Info Link", "Information Link") if str(props.get(k) or "").startswith("http")), "")
    if link:
        out["상세"] = {"text": "", "links": [{"url": link, "label": "MDI"}]}
    return out


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 지질시대는 가장 잘게 가른 것 하나이고 한국어판이면 ICS 이름을 옮긴다. 값(암상·층서)은 영어 그대로."""
    if any(k in props for k in ("MDI_IDENT", "MDI Identifier")):
        return mdi_friendly(props)
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or value.lower() in ("null", "<null>") or label in out:
            continue
        if key in AGE_KEYS:
            value = _age_name(value)
            if lang == "ko":
                name, sep, rest = value.partition(" (")
                value = i18n.age_ko(name) + (f" ({rest}" if sep else "")
        out[label] = value
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "ogs", "tag": "OGS", "title": "온타리오 지질조사소", "relay": True, "projected": True, "globe": True},
]
