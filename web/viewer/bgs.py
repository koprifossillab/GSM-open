"""BGS(영국 지질조사소)로 나가는 문 — 영국(그레이트브리튼) 1:5만 지질도 (wetherilli 143).

- 주소: `map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다
- 조건: **Open Government Licence** — 출처 문구 "Contains British Geological Survey materials © UKRI [해]" 를 달아야 한다
  (GetCapabilities 의 AccessConstraints). `ATTRIBUTION`
- 3857 을 그대로 받는다. **1:94 495 보다 가까울 때만 그린다**(3857 줌 13 쯤부터) — 넓게 볼 때는 EGDI 1:100만이 밑을 채운다
- 레이어명에 `bgs:` 를 붙여 카탈로그에 둔다 — 상류 이름(`BGS.50k.Bedrock`)에 점이 들어 있다. 상류로 나갈 때 뗀다
- 속성은 `application/geo+json`. 열이 쉰 남짓이라 `FRIENDLY` 에 적은 것만 보인다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "bgs:"
ATTRIBUTION = ('Contains <a href="https://www.bgs.ac.uk/" target="_blank" rel="noopener">British Geological Survey</a>'
               ' materials © UKRI 2026 (<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/"'
               ' target="_blank" rel="noopener">OGL</a>)')
#: 가장 넓게 그리는 축척 — 이보다 멀면 상류가 빈 그림을 준다. 3857 로 줌 13 부터다(2026-10-02 에 쟀다) — 화면은 그보다 멀면 묻지 않는다
MAX_SCALE = 94494.99256
MIN_ZOOM = 13


class BgsError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.BGS_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bgs", ok=False)
        raise BgsError(f"BGS 에 닿지 못했다: {exc}") from exc
    log.info("BGS %s -> %s", r.url, r.status_code)
    usage.record("bgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BgsError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로.** `_D` 가 붙은 열이 글로 풀린 값이다
FRIENDLY = (
    ("LEX_D", "지층명"),
    ("RCS_D", "암석"),
    ("TYPE_D", "갈래"),
    ("MAX_PERIOD", "지질시대"),
    ("MAX_EPOCH", "세"),
    ("MAX_TIME_D", "가장 오랜 시기"),
    ("MIN_TIME_D", "가장 젊은 시기"),
    ("GP_EQ_D", "층군"),
    ("SETTING_D", "생성 환경"),
    ("FEATURE_D", "선 구조"),
    ("FLTNAME_D", "단층 이름"),
    ("CATEGORY", "갈래"),
    ("MAP_SRC", "도폭"),
    ("LEX_WEB", "어휘집"),
)
_EMPTY = {"null", "not applicable", "no parent", "none"}
_AGES = ("MAX_PERIOD", "MAX_EPOCH")


def friendly(props: dict, lang: str = "ko") -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or value.lower() in _EMPTY or label in out:
            continue
        if key in _AGES and lang == "ko":
            value = i18n.age_ko(value)
        out[label] = value
    return out


# ── GSNI(북아일랜드 지질조사소) 1:25만 (wetherilli 147) ─────────────────
#
# BGS 가 같은 서버(`map.bgs.ac.uk`)에서 대신 내준다 — 그래서 문은 여기 하나다(CCOP 가 gsj.py 에 든 것과 같다). 상류 이름은
# `gsni` 로 따로 둔다 — 출처 문구가 GSNI 의 것이다. 3857 그대로, 줌 제한 없음. 속성은 GeoJSON 을 청해도 ArcGIS XML 을 주어
# `featureinfo_xml`(Field·FieldName·FieldValue)로 읽는다. 열은 BGS 1:5만과 같은 꼴(`LEX_D`·`RCS_D`)이라 `friendly` 를 같이 쓴다
import xml.etree.ElementTree as _ET
from types import SimpleNamespace as _NS

GSNI_PREFIX = "gsni:"
GSNI_ATTRIBUTION = ('Contains <a href="https://www.economy-ni.gov.uk/topics/geological-survey-northern-ireland" target="_blank"'
                    ' rel="noopener">Geological Survey of Northern Ireland</a> materials © Crown Copyright (OGL)')
_ESRI = "{http://www.esri.com/wms}"


def _gsni_get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.GSNI_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsni", ok=False)
        raise BgsError(f"GSNI(BGS) 에 닿지 못했다: {exc}") from exc
    log.info("GSNI %s -> %s", r.url, r.status_code)
    usage.record("gsni", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _gsni_wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = ",".join(n.strip()[len(GSNI_PREFIX):] if n.strip().startswith(GSNI_PREFIX) else n.strip()
                                   for n in str(params[key]).split(","))
    return params


def gsni_get_map(params: dict):
    r = _gsni_get(_gsni_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def gsni_get_legend(layer: str):
    name = layer[len(GSNI_PREFIX):] if layer.startswith(GSNI_PREFIX) else layer
    r = _gsni_get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                   "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def gsni_get_feature_info(params: dict) -> dict:
    params = _gsni_wms(params, "GetFeatureInfo")
    params["info_format"] = "application/vnd.esri.wms_featureinfo_xml"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _gsni_get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_esri_xml(r.text)}


def parse_esri_xml(text: str) -> list:
    """ArcGIS `featureinfo_xml` → feature 목록. 문은 서로를 타지 않아 igme.py 의 것과 따로 둔다."""
    try:
        root = _ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except _ET.ParseError:
        return []
    features = []
    for info in root.iter(f"{_ESRI}FeatureInfo"):
        props = {}
        for field in info.iter(f"{_ESRI}Field"):
            name = (field.findtext(f"{_ESRI}FieldName") or "").strip()
            if name:
                props[name] = (field.findtext(f"{_ESRI}FieldValue") or "").strip()
        features.append({"id": f"gsni.{props.get('OBJECTID', len(features))}", "properties": props})
    return features


#: `views._Door` 가 쓰는 꼴 — 다른 문(모듈)과 같은 이름의 셋
GSNI = _NS(get_map=gsni_get_map, get_feature_info=gsni_get_feature_info, get_legend=gsni_get_legend)


# ── 아프리카 지하수 지도책(AGA)의 나라별 1:500만 지질 (wetherilli 207) ──────────
#
# 같은 BGS 서버(`map.bgs.ac.uk/arcgis/services/AGA/BGS_Groundwater`)의 것이라 문은 여기다(GSNI 와 같다). 상류 이름은 `aga` 로 따로 —
# 조건이 **CC BY-SA 4.0** 으로 다르다(Capabilities 의 AccessConstraints). 나라마다 레이어가 하나라(38 나라, 수단·모리타니·보츠와나는
# 기반암·표층으로 갈린다 — 기반암을 쓴다) 카탈로그에는 **레이어 하나**(`aga:geology`)로 두고 문이 나라 레이어를 쉼표로 이어 묻는다.
# 3857 그대로(동아프리카 넷을 묶어 256² 1.7 초, 2026-10-04). 속성은 `text/xml` 의 `<FIELDS KenGLG="Igneous Volcanic" …/>` —
# 열 이름이 나라마다 달라 `…GLG` 로 끝나는 것을 암상으로 읽는다. 지질시대 열은 없다

AGA_PREFIX = "aga:"
AGA_ATTRIBUTION = ('Africa Groundwater Atlas — <a href="https://www2.bgs.ac.uk/africagroundwateratlas/" target="_blank" rel="noopener">'
                   'British Geological Survey</a> (CC BY-SA 4.0)')
#: 나라 레이어 — 2026-10-04 의 Capabilities. 기반암·표층으로 갈린 셋은 기반암
AGA_COUNTRIES = ("AGO", "BEN", "BFA", "BWA", "CAF", "CIV", "CMR", "COD", "COG", "DJI", "DZA", "ESH", "ETH", "GAB", "GHA", "GMB",
                 "KEN", "LSO", "MAR", "MDG", "MLI", "MOZ", "MRT", "MWI", "NER", "NGA", "SDN", "SEN", "SLE", "SOM", "SSD", "TCD",
                 "TGO", "TUN", "TZA", "UGA", "ZMB", "ZWE")
AGA_SPLIT = ("BWA", "MRT", "SDN")
AGA_LAYERS = {"aga:geology": tuple(f"{c}_BGS_5M_{'Bedrock' if c in AGA_SPLIT else ''}Geology" for c in AGA_COUNTRIES)}
#: 범례는 나라마다 같은 갈래(암상 열 남짓)라 한 나라의 것을 쓴다
AGA_LEGEND_LAYER = "KEN_BGS_5M_Geology"


def _aga_names(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if one not in AGA_LAYERS:
            raise BgsError(f"모르는 레이어다: {one}")
        out.extend(AGA_LAYERS[one])
    return ",".join(out)


def _aga_get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.AGA_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("aga", ok=False)
        raise BgsError(f"BGS 지하수 지도책에 닿지 못했다: {exc}") from exc
    log.info("AGA %s -> %s", r.url, r.status_code)
    usage.record("aga", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _aga_wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _aga_names(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _aga_names(params["query_layers"])
    return params


def aga_get_map(params: dict):
    r = _aga_get(_aga_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def aga_get_legend(layer: str):
    _aga_names(layer)
    r = _aga_get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                  "layer": AGA_LEGEND_LAYER})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def aga_get_feature_info(params: dict) -> dict:
    params = _aga_wms(params, "GetFeatureInfo")
    params["info_format"] = "text/xml"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _aga_get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_fields_xml(r.text)}


def parse_fields_xml(text: str) -> list:
    """ArcGIS `text/xml` 의 `<FIELDS 열="값" …/>` → feature 목록."""
    try:
        root = _ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except _ET.ParseError:
        return []
    return [{"id": f"aga.{f.attrib.get('OBJECTID', i)}", "properties": dict(f.attrib)}
            for i, f in enumerate(root.iter(f"{_ESRI}FIELDS"))]


def aga_friendly(props: dict, lang: str = "ko") -> dict:
    """나라마다 열 이름이 다르다(`KenGLG`·`EthGLG` …) — `GLG` 로 끝나는 열이 암상이다. 값(영어)은 그대로 둔다."""
    for key, value in props.items():
        if key.endswith("GLG") and str(value or "").strip():
            return {"암상": str(value).strip()}
    return {}


AGA = _NS(get_map=aga_get_map, get_feature_info=aga_get_feature_info, get_legend=aga_get_legend)


# ── 나미비아 지질조사소(GSN) 1:100만 — BGS 가 대신 내준다 (wetherilli 209) ─────────
#
# BGS 의 다른 서버(`ogc.bgs.ac.uk/cgi-bin/BGS_GSN_Bedrock_Geology/wms`, MapServer·OneGeology)라 문은 여기다(GSNI·AGA 와 같다). 상류 이름은
# `gsn` — 자료의 주인이 나미비아 지질조사소이고 조건이 다르다: AccessConstraints "This data set is available from the Geological Survey of
# Namibia, contact: sales@mme.gov.na", Fees "N$283" — **자료는 파는 것**이다. 보기(WMS)는 열려 있지만 **서버 캐시에 담지 않는다**
# (`views.NO_STORE`). 3857 그대로(빈트후크 둘레 256² 1.6 초, 2026-10-04). 속성은 `text/plain` — 연대·층군·층·암석이 넉넉하다
import re as _re

GSN_PREFIX = "gsn:"
GSN_ATTRIBUTION = ('Geological Map of Namibia 1:1 000 000 — <a href="https://www.mme.gov.na/gsn/" target="_blank" rel="noopener">'
                   'Geological Survey of Namibia</a> (served by BGS)')
GSN_LAYERS = ("NAM_GSN_1M_BLS", "NAM_GSN_1M_BA")


def _gsn_names(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        name = one[len(GSN_PREFIX):] if one.startswith(GSN_PREFIX) else ""
        if name not in GSN_LAYERS:
            raise BgsError(f"모르는 레이어다: {one}")
        out.append(name)
    return ",".join(out)


def _gsn_get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.GSN_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsn", ok=False)
        raise BgsError(f"GSN(BGS) 에 닿지 못했다: {exc}") from exc
    log.info("GSN %s -> %s", r.url, r.status_code)
    usage.record("gsn", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _gsn_wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _gsn_names(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _gsn_names(params["query_layers"])
    # MapServer 는 GetFeatureInfo 에도 STYLES·FORMAT 을 요구한다(없으면 MissingParameterValue, 2026-10-04)
    params.setdefault("styles", "")
    params.setdefault("format", "image/png")
    return params


def gsn_get_map(params: dict):
    r = _gsn_get(_gsn_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def gsn_get_legend(layer: str):
    r = _gsn_get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                  "layer": _gsn_names(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def gsn_get_feature_info(params: dict) -> dict:
    params = _gsn_wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _gsn_get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_mapserver_plain(r.text)}


_PLAIN_FEATURE = _re.compile(r"^\s*Feature\s+(\S+):\s*$")
_PLAIN_ATTR = _re.compile(r"^\s{2,}(\w+)\s*=\s*'(.*)'\s*$")


def parse_mapserver_plain(text: str) -> list:
    """MapServer 의 `text/plain` 속성 → feature 목록. 문은 서로를 타지 않아 brgm.py 의 것과 따로 둔다."""
    features, current = [], None
    for line in (text or "").splitlines():
        m = _PLAIN_FEATURE.match(line)
        if m:
            current = {"id": f"gsn.{m.group(1)}", "properties": {}}
            features.append(current)
            continue
        m = _PLAIN_ATTR.match(line)
        if m and current is not None:
            current["properties"][m.group(1)] = m.group(2)
    return features


GSN_FRIENDLY = (("MAPCODE", "기호"), ("AGE", "지질시대"), ("SEQUENCE", "누층군"), ("GROUP", "층군"), ("SUBGROUP", "아층군"),
                ("FORMATION", "층"), ("ROCKTYPES", "암석"))


def gsn_friendly(props: dict, lang: str = "ko") -> dict:
    """연대(`Namibian` 같은 그 나라의 시대 이름)·층서·암석. 값은 영어 그대로 둔다."""
    return {label: str(props[key]).strip() for key, label in GSN_FRIENDLY if str(props.get(key) or "").strip()}


GSN = _NS(get_map=gsn_get_map, get_feature_info=gsn_get_feature_info, get_legend=gsn_get_legend)


# ── 부르키나파소 지질광업국(BUMIGEB) 1:100만 — BGS 가 대신 내준다 (wetherilli 246) ─────────
#
# 나미비아 GSN 과 같은 BGS 의 MapServer(`ogc.bgs.ac.uk/cgi-bin/BGS_BUMIGEB_FR_Bedrock_Geology/wms`, OneGeology)라 문은 여기다. 상류 이름은
# `bumigeb`. 조건: AccessConstraints "personal, teaching, research or non-commercial use" — **비상업**(페루·브라질과 같다), 파는 자료는 아니라
# 캐시에 담는다. 3857 그대로(나라 전체 512² 2.4 초, 2026-10-05). 속성은 `text/plain` 인데 **latin-1** 로 온다(`Granite à biotite`)

BUMIGEB_PREFIX = "bumigeb:"
BUMIGEB_ATTRIBUTION = ('Carte géologique du Burkina Faso 1:1 000 000 — <a href="https://www.bumigeb.bf/" target="_blank" '
                       'rel="noopener">BUMIGEB</a> (served by BGS, non-commercial use)')
#: 레이어 — 암상(면)과 주요 구조(선). 구조는 누를 것이 없다
BUMIGEB_LAYERS = ("BFA_BUMIGEB_FR_1M_BLS", "BFA_BUMIGEB_FR_1M_MSF")


def _bumigeb_names(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        name = one[len(BUMIGEB_PREFIX):] if one.startswith(BUMIGEB_PREFIX) else ""
        if name not in BUMIGEB_LAYERS:
            raise BgsError(f"모르는 레이어다: {one}")
        out.append(name)
    return ",".join(out)


def _bumigeb_get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.BUMIGEB_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bumigeb", ok=False)
        raise BgsError(f"BUMIGEB(BGS) 에 닿지 못했다: {exc}") from exc
    log.info("BUMIGEB %s -> %s", r.url, r.status_code)
    usage.record("bumigeb", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _bumigeb_wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _bumigeb_names(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _bumigeb_names(params["query_layers"])
    params.setdefault("styles", "")
    params.setdefault("format", "image/png")
    return params


def bumigeb_get_map(params: dict):
    r = _bumigeb_get(_bumigeb_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def bumigeb_get_legend(layer: str):
    r = _bumigeb_get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                      "layer": _bumigeb_names(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def bumigeb_get_feature_info(params: dict) -> dict:
    params = _bumigeb_wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _bumigeb_get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        text = r.content.decode("utf-8")
    except UnicodeDecodeError:          # latin-1 로 온다(2026-10-05)
        text = r.content.decode("latin-1")
    return {"features": parse_mapserver_plain(text)}


BUMIGEB_FRIENDLY = (("NOTATION", "기호"), ("DESCR", "설명"), ("LITHOLOGIE", "암석"), ("GROUPE3", "암석 분류"))


def _greek(value: str) -> str:
    """기호 열은 그리스 글자(γ 화강암 따위)를 cp1253 바이트로 적었다 — latin-1 로 읽힌 것을 되돌린다(`ã3` → `γ3`)."""
    try:
        return value.encode("latin-1").decode("cp1253")
    except UnicodeError:
        return value


def bumigeb_friendly(props: dict, lang: str = "ko") -> dict:
    """기호·설명·암석. 값은 프랑스어 그대로 둔다. 연대 열이 없다."""
    out = {label: str(props[key]).strip() for key, label in BUMIGEB_FRIENDLY if str(props.get(key) or "").strip()}
    if "기호" in out:
        out["기호"] = _greek(out["기호"])
    return out


BUMIGEB = _NS(get_map=bumigeb_get_map, get_feature_info=bumigeb_get_feature_info, get_legend=bumigeb_get_legend)


# ── 영국 GeoIndex — 자력·중력 이상, 광산·채석장, 광물 산지 (wetherilli 258) ───────────────
#
# BGS 의 GeoIndex 지도(`map.bgs.ac.uk/arcgis/services/GeoIndex_Onshore/<서비스>/MapServer/WMSServer`). 상류 이름은 `bgsgi` 로 따로 두되 문은 여기다.
#
# - 조건: BGS WMS 의 "Terms of use" — **Open Government Licence**, "Contains British Geological Survey materials © UKRI [해]" 를 붙인다.
#   광물 서비스의 copyrightText 는 "Geological Materials Copyright NERC. All rights reserved." 지만 WMS 로 내준 것의 조건은 위의 것이다
# - 자력·중력 이상(1:62만 5천 지도의 색 음영)은 상류 maxScale 이 62만 5천이라 **화면 줌 9 까지** 그린다(그 위는 빈 그림 — 화면이 늘린다)
# - 광산·채석장(BritPits)은 minScale 60만이라 **줌 10 부터**. 광물 산지(MINGOL)는 넓게도 그린다
# - 속성은 `application/geo+json`. 지구물리는 그림이라 누르지 않는다
# - **수리지질·G-BASE**(wetherilli 324) — 같은 GeoIndex 의 `hydrogeology`(1:62만 5천 대수층 생산성 — 갈래·흐름·요약)와 `geochemistry` 의
#   하천 퇴적물 시료 지점(G-BASE, 시료 번호·분석 원소, 상류 minScale 25만이라 줌 12 부터). 원소마다 칠한 지도는 GeoIndex 가 아니라 **핵심 광물
#   정보센터(CMIC) 의 `CMIC/Stream_Sediment_Geochemistry`**(하천 퇴적물 31 원소 — G-BASE·북아일랜드 Tellus 시료를 보간한 래스터)에 있다.
#   WMS 를 켜지 않아 REST `export`·`identify` 로 옮긴다(`arcwms.rest_*`). 누르면 화소 값(주원소 산화물 %, 미량 원소 mg/kg — 범례 칸의 값이
#   그 꼴이다). 이 서비스는 조건 글이 없다 — WMS 의 OGL 이 REST 에도 걸리는지 사람이 읽는다
GEOINDEX_PREFIX = "bgsgi:"
GEOINDEX_ATTRIBUTION = ('Contains <a href="https://www.bgs.ac.uk/technologies/web-map-services-wms/" target="_blank" rel="noopener">'
                        "British Geological Survey</a> materials © UKRI 2026 (OGL)")
#: 레이어 → (GeoIndex 서비스, WMS 레이어, 누르기가 되나)
GEOINDEX_LAYERS = {
    "bgsgi:magnetic": ("geophysics", "Magnetic.anomalies.colour.shaded", False),
    "bgsgi:gravity": ("geophysics", "Gravity.anomalies.colour.shaded", False),
    "bgsgi:mines": ("minerals_wms", "Mines.and.quarries", True),
    "bgsgi:occurrences": ("minerals_wms", "Mineral.Occurrences", True),
    # 수리지질·G-BASE 시료 지점 (wetherilli 324)
    "bgsgi:hydrogeology": ("hydrogeology", "Hydrogeology", True),
    "bgsgi:gbase_streamsed": ("geochemistry", "Stream.sediment", True),
}
#: CMIC 하천 퇴적물 지화학(wetherilli 324) — 원소 기호 → (REST 번호, 영어 이름, 주원소 산화물인가). REST 만이다
GEOCHEM_SERVICE = "CMIC/Stream_Sediment_Geochemistry"
GEOCHEM = {sym: (n, name, n <= 6) for n, name, sym in (
    (1, "Calcium", "CaO"), (2, "Iron", "Fe2O3"), (3, "Potassium", "K2O"), (4, "Magnesium", "MgO"), (5, "Manganese", "MnO"),
    (6, "Titanium", "TiO2"), (8, "Antimony", "Sb"), (9, "Arsenic", "As"), (10, "Barium", "Ba"), (11, "Beryllium", "Be"),
    (12, "Bismuth", "Bi"), (13, "Cadmium", "Cd"), (14, "Cerium", "Ce"), (15, "Chromium", "Cr"), (16, "Cobalt", "Co"),
    (17, "Copper", "Cu"), (18, "Gallium", "Ga"), (19, "Lanthanum", "La"), (20, "Lead", "Pb"), (21, "Lithium", "Li"),
    (22, "Molybdenum", "Mo"), (23, "Nickel", "Ni"), (24, "Rubidium", "Rb"), (25, "Strontium", "Sr"), (26, "Tin", "Sn"),
    (27, "Tungsten", "W"), (28, "Uranium", "U"), (29, "Vanadium", "V"), (30, "Yttrium", "Y"), (31, "Zinc", "Zn"),
    (32, "Zirconium", "Zr"))}
GEOCHEM_PREFIX = "bgsgi:gq:"
#: 목록 범례를 내는 레이어(`views.LIST_LEGENDS`) — CMIC 원소 지도. 칸은 함량 구간이다
LEGEND_LAYERS = tuple(GEOCHEM_PREFIX + s for s in GEOCHEM)
#: 그리는 화면 줌 — (처음, 끝)
GEOINDEX_ZOOMS = {"bgsgi:magnetic": (None, 9), "bgsgi:gravity": (None, 9), "bgsgi:mines": (10, None),
                  "bgsgi:gbase_streamsed": (12, None)}
#: BritPits 의 운영 상태 약호
PIT_STATUS = {"A": "Active", "C": "Ceased", "I": "Inactive", "P": "Proposed"}


def geoindex_knows(name: str) -> bool:
    return name in GEOINDEX_LAYERS or _geochem(name) is not None


def geoindex_queryable(name: str) -> bool:
    return _geochem(name) is not None or (name in GEOINDEX_LAYERS and GEOINDEX_LAYERS[name][2])


def _geochem(name: str):
    """`bgsgi:gq:Cu` → ("Cu", REST 번호, 영어 이름, 산화물인가). 아니면 None"""
    name = str(name or "").strip()
    if not name.startswith(GEOCHEM_PREFIX) or name[len(GEOCHEM_PREFIX):] not in GEOCHEM:
        return None
    sym = name[len(GEOCHEM_PREFIX):]
    return (sym, *GEOCHEM[sym])


def _geochem_url(path: str) -> str:
    root = settings.BGS_WMS_URL.split("/arcgis/services/", 1)[0]
    return f"{root}/arcgis/rest/services/{GEOCHEM_SERVICE}/MapServer/{path}"


def _geoindex(name: str):
    if name not in GEOINDEX_LAYERS:
        raise BgsError(f"모르는 레이어다: {name}")
    service, layer, queryable = GEOINDEX_LAYERS[name]
    root = settings.BGS_WMS_URL.split("/arcgis/services/", 1)[0]
    return f"{root}/arcgis/services/GeoIndex_Onshore/{service}/MapServer/WMSServer", layer, queryable


def _geoindex_get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bgsgi", ok=False)
        raise BgsError(f"BGS GeoIndex 에 닿지 못했다: {exc}") from exc
    log.info("BGS-GeoIndex %s -> %s", r.url, r.status_code)
    usage.record("bgsgi", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def geoindex_get_map(params: dict):
    gq = _geochem(params.get("layers"))
    if gq:
        try:
            query = arcwms.rest_export_params(params, str(gq[1]))
        except ValueError as exc:
            raise BgsError(str(exc)) from exc
        r = _geoindex_get(_geochem_url("export"), query)
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
        return r.content, ctype
    url, layer, _ = _geoindex(str(params.get("layers") or "").strip())
    r = _geoindex_get(url, dict(params, service="WMS", request="GetMap", layers=layer, styles=""))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def legend_rows(name: str) -> list:
    """CMIC 원소 지도의 범례 — REST `legend` 의 함량 구간 칸(`list/legend/`)"""
    gq = _geochem(name)
    if not gq:
        raise BgsError(f"범례가 없는 레이어다: {name}")
    r = _geoindex_get(_geochem_url("legend"), {"f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise BgsError("범례가 JSON 이 아니다") from exc
    unit = "%" if gq[3] else "mg/kg"
    return [{"symbol": "", "lithology": f"{label} {unit}", "age": "", "color": "transparent", "swatch": uri}
            for label, uri in arcwms.legend_list(data, layer_ids=(gq[1],))]


def geoindex_get_legend(layer: str):
    if _geochem(layer):
        raise BgsError("원소 지도는 목록 범례(`legend_rows`)를 쓴다")
    url, name, _ = _geoindex(layer)
    r = _geoindex_get(url, {"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "image/png", "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def geoindex_get_feature_info(params: dict) -> dict:
    gq = _geochem(params.get("query_layers") or params.get("layers"))
    if gq:
        try:
            query = arcwms.rest_identify_params(params, str(gq[1]), tolerance=1)
        except ValueError as exc:
            raise BgsError(str(exc)) from exc
        r = _geoindex_get(_geochem_url("identify"), query)
        try:
            data = r.json()
        except ValueError as exc:
            raise BgsError("속성이 JSON 이 아니다") from exc
        out = []
        for f in arcwms.identify_features(data, f"bgsgi.gq.{gq[0]}", limit=1):
            value = f["properties"].get("Classify.Pixel Value")
            if value not in (None, "", "NoData"):
                f["properties"] = {"_gq": gq[0], "_oxide": gq[3], "value": value}
                out.append(f)
        return {"features": out}
    url, layer, queryable = _geoindex(str(params.get("query_layers") or params.get("layers") or "").strip())
    if not queryable:
        return {"features": []}
    q = dict(params, service="WMS", request="GetFeatureInfo", layers=layer, query_layers=layer, styles="",
             info_format="application/geo+json")
    r = _geoindex_get(url, q)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BgsError("속성이 JSON 이 아니다") from exc


def geoindex_friendly(props: dict, lang: str = "ko") -> dict:
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    if "_gq" in props:                          # CMIC 원소 지도의 화소 값 (wetherilli 324)
        try:
            value = float(props["value"])
        except (TypeError, ValueError):
            return {}
        unit = "%" if props.get("_oxide") else "mg/kg"
        return {"원소": props["_gq"], f"함량 ({unit})": f"{value:.2f}" if props.get("_oxide") else f"{value:.1f}"}
    if "CHARACTER" in props or "FLOW_MECHA" in props:   # 수리지질
        rows = (("암석 단위", v("ROCK_UNIT")), ("갈래", v("CLASS")), ("대수층", v("CHARACTER")), ("흐름", v("FLOW_MECHA")),
                ("요약", v("SUMMARY")))
        return {k: x for k, x in rows if x}
    if "SAMPLE_NUMBER" in props and "ANALYTES" in props:  # G-BASE 시료 지점
        rows = (("시료 번호", v("SAMPLE_NUMBER")), ("분석 원소", " ".join(v("ANALYTES").replace(",", " ").split())), ("사업", v("PROJECT")),
                ("영국 격자", f"E {v('EASTING')} · N {v('NORTHING')}"))
        return {k: x for k, x in rows if x and x != "E  · N "}
    if "PIT_NAME" in props:                     # 광산·채석장 (BritPits)
        status = v("PIT_STATUS")
        rows = (("이름", v("PIT_NAME")), ("운영", PIT_STATUS.get(status, status)), ("영국 격자", f"E {v('EASTING')} · N {v('NORTHING')}"))
    else:                                       # 광물 산지 (MINGOL)
        rows = (("이름", v("OCCURRENCE")), ("광종", v("COMMODITY")), ("영국 격자", f"E {v('EASTING')} · N {v('NORTHING')}"))
    return {k: x for k, x in rows if x and x != "E  · N "}


GEOINDEX = _NS(get_map=geoindex_get_map, get_feature_info=geoindex_get_feature_info, get_legend=geoindex_get_legend)
