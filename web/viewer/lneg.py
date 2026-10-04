"""LNEG(포르투갈 국립 에너지·지질연구소)로 나가는 문 — 포르투갈 지질도 1:50만 (wetherilli 211).

- 주소: `sig.lneg.pt/server/services/CGP500k/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다. 레이어는 번호다 — `2` 대륙 지질·`1` 대륙 구조선·
  `4` 대륙붕 지질·`3` 대륙붕 구조선. **`0` 은 대륙붕(바다) 판이 아니라 기호(Sinais Convencionais)다** — REST 와 번호가 같다. 이름은 `lneg:500k:<번호>`
- 3857 이 Capabilities 에 있다. 구조선은 상류가 1:100만보다 가까울 때만 그린다
- 속성: GeoJSON 은 `InvalidFormat` 이라 **ESRI XML**(`application/vnd.esri.wms_featureinfo_xml`)로 받는다 — 기호·설명·층군·지구조 구역(포르투갈어)
- CORS 는 Origin 을 되비춘다. 조건: Capabilities 에 적힌 것이 없다(2026-10-04). 저작권 "LNEG – Laboratório Nacional de Energia e Geologia, I.P."
  — 밖에 열기 전에 사람이 읽는다
"""
import logging
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "lneg:500k:"
LAYERS = ("2", "1", "4", "3")
ZOOMS = {"lneg:500k:1": (9, None), "lneg:500k:3": (9, None)}
ATTRIBUTION = ('Carta Geológica de Portugal 1:500 000 — <a href="https://geoportal.lneg.pt/" target="_blank" rel="noopener">'
               'LNEG – Laboratório Nacional de Energia e Geologia</a>')
TIMEOUT = 45
_ESRI = "{http://www.esri.com/wms}"


class LnegError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "").startswith(PREFIX) and str(name)[len(PREFIX):] in LAYERS


def _numbers(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if not knows(one):
            raise LnegError(f"모르는 레이어다: {one}")
        out.append(one[len(PREFIX):])
    return ",".join(out)


def _url() -> str:
    return f"{settings.LNEG_URL.rstrip('/')}/services/CGP500k/MapServer/WMSServer"


def _get(params: dict):
    left = usage.paused()
    if left:
        raise LnegError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(_url(), params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("lneg", ok=False)
        raise LnegError(f"LNEG 에 닿지 못했다: {exc}") from exc
    log.info("LNEG %s -> %s", r.url, r.status_code)
    usage.record("lneg", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.3.0")
    params["layers"] = _numbers(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _numbers(params["query_layers"])
    if "srs" in params and "crs" not in params:
        params["crs"] = params.pop("srs")
    params.setdefault("styles", "")
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise LnegError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "request": "GetLegendGraphic", "version": "1.3.0", "format": "image/png",
              "layer": _numbers(layer), "sld_version": "1.1.0"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise LnegError(f"범례를 받지 못했다 (status={r.status_code})")
    return r.content, ctype


def parse_esri_xml(text) -> list:
    """ArcGIS `featureinfo_xml` → feature 목록. `<FeatureInfo><Field><FieldName/><FieldValue/></Field>…`"""
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    out = []
    for info in root.iter(f"{_ESRI}FeatureInfo"):
        props = {}
        for field in info.iter(f"{_ESRI}Field"):
            name = (field.findtext(f"{_ESRI}FieldName") or "").strip()
            if name:
                props[name] = (field.findtext(f"{_ESRI}FieldValue") or "").strip()
        out.append({"id": f"lneg.{props.get('OBJECTID', len(out))}", "properties": props})
    return out


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/vnd.esri.wms_featureinfo_xml"
    if "x" in params and "i" not in params:
        params["i"], params["j"] = params.pop("x"), params.pop("y", "0")
    r = _get(params)
    if r.status_code != 200:
        raise LnegError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_esri_xml(r.content)}


FRIENDLY = (
    ("Código", "기호"),
    ("Descrição", "설명"),
    ("Descrição1", "층군"),
    ("Zona", "지구조 구역"),
    ("IntrusõesPlutónicas", "심성암"),
    ("IntrusõesPlutónicas1", "심성암"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(포르투갈어)은 그대로 둔다."""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and value.lower() != "null" and label not in out:
            out[label] = value
    return out
