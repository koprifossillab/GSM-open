"""SIGÉOM(퀘벡 지질 광업 정보 체계)으로 나가는 문 — 퀘벡 지질도 (wetherilli 210).

- 주소: `servicesvectoriels.atlas.gouv.qc.ca/IDS_SGM_WMS/service.svc/get` — 퀘벡 정부 앞단 뒤의 GeoServer(`geoserver-prd`). 열쇠가 없다
- **WMS 1.1.1 만 받는다**(1.3.0 은 InvalidParameterValue). 화면의 1.3.0 변수를 1.1.1(`srs`·`x`·`y`)로 옮긴다
- **Origin 헤더가 붙으면 403** 이다(`Access-Control-Allow-Origin: *` 를 달고도) — 정적 판에서는 못 쓰고 이 문으로만 간다. 문은 Origin 을 보내지 않는다
- Capabilities 에 3978 이 없지만 **3978 로 물어도 그린다**(2026-10-04) — 캐나다 탭처럼 3978 로 곧장 받는다
- 축척에 따라 그린다 — `SGM:Geologie_generale` 은 512 격자 줌 4(화면 줌 5)부터, `SGM:Geologie_regionale` 은 격자 줌 7(화면 줌 8)부터.
  그보다 멀면 빈 그림이다
- 속성은 `text/plain` 으로 받는다 — `application/json` 은 기하가 붙어 415 KB, `text/plain` 은 2 KB. GeoServer 의 `propertyName` 은
  앞단을 지나며 깨진다(ClassCastException). 값은 프랑스어 그대로다(지층·시대·암석). `REF_EXA` 의 `<a>` 는 뷰가 링크로 가른다
- 범례는 없다 — GetLegendGraphic 이 28×18 한 칸이고, `hideEmptyRules` 같은 벤더 인자도 앞단을 지나지 못한다
- 조건: Capabilities 의 AccessConstraints "Licence du gouvernement ouvert – Québec" = **CC BY 4.0**
"""
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "sigeom:"
ATTRIBUTION = ('<a href="https://sigeom.mines.gouv.qc.ca/" target="_blank" rel="noopener">SIGÉOM</a> '
               "(Gouvernement du Québec, CC BY 4.0)")
#: 레이어 → (상류 이름, 처음 그리는 화면 줌, 누르기가 되나)
LAYERS = {
    "sigeom:generale": ("SGM:Geologie_generale", 5, True),
    "sigeom:regionale": ("SGM:Geologie_regionale", 8, True),
    "sigeom:failles": ("SGM:Failles_regionales", 8, False),
}


class SigeomError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def queryable(name: str) -> bool:
    return name in LAYERS and LAYERS[name][2]


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SigeomError(f"모르는 레이어다: {names}")
    return names[0]


def _get(params: dict):
    left = usage.paused()
    if left:
        raise SigeomError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        # Origin 을 붙이지 않는다 — 붙이면 403 이다
        r = requests.get(settings.SIGEOM_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sigeom", ok=False)
        raise SigeomError(f"SIGÉOM 에 닿지 못했다: {exc}") from exc
    log.info("SIGÉOM %s -> %s", r.url, r.status_code)
    usage.record("sigeom", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    """화면의 WMS 1.3.0 변수 → 1.1.1. 투영 좌표라 BBOX 의 축 차례는 그대로다."""
    name = _one(params)
    out = dict(params, service="WMS", request=request, version="1.1.1", layers=LAYERS[name][0])
    if "crs" in out:
        out["srs"] = out.pop("crs")
    if "query_layers" in out:
        out["query_layers"] = LAYERS[name][0]
    for new, old in (("x", "i"), ("y", "j")):
        if old in out:
            out[new] = out.pop(old)
    out.setdefault("styles", "")
    return out


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SigeomError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise SigeomError("퀘벡 지질도는 범례를 주지 않는다")


def get_feature_info(params: dict) -> dict:
    if not queryable(_one(params)):
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    r = _get(params)
    if r.status_code != 200:
        raise SigeomError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


def parse_plain(text: str) -> list:
    """GeoServer GetFeatureInfo `text/plain` → feature 목록. 덩이는 줄표 줄로 갈린다. 기하 줄(`GEOMETRIE = [GEOMETRY …]`)은 뺀다."""
    out, props = [], {}
    for line in text.splitlines():
        if line.startswith("-----"):
            if props:
                out.append({"id": f"sigeom.{len(out)}", "properties": props})
            props = {}
            continue
        m = re.match(r"([A-Z_0-9]+) = (.*)$", line)
        if m and not m.group(2).startswith("[GEOMETRY"):
            props[m.group(1)] = m.group(2).strip()
    if props:
        out.append({"id": f"sigeom.{len(out)}", "properties": props})
    return out


FRIENDLY = (("NOM_ABRG_ETQT_LITH", "기호"), ("STRATIGRAPHIE", "지층"), ("DESC_ZONE_GEOLG", "암석"), ("AGE", "지질시대"),
            ("REF_EXA", "원도"))


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 프랑스어 그대로다 — 시대(`Néoarchéen` 따위)도 옮기지 않는다(옮기는 표가 없다)."""
    out = {}
    for key, label in FRIENDLY:
        value = props.get(key)
        if value not in (None, "", "null") and label not in out:
            out[label] = value
    return out
