"""IGME(스페인 지질광물연구소)로 나가는 문 — 스페인 지질도 (wetherilli 147).

- 주소: `mapas.igme.es/gis/services/Cartografia_Geologica/<판>/MapServer/WMSServer` (ArcGIS WMS). 판은 둘 —
  `IGME_Geologico_1M`(이베리아 반도·발레아레스·카나리아 1:100만)·`IGME_MAGNA_50`(MAGNA 1:5만). 열쇠가 없다
- 조건: GetCapabilities 의 AccessConstraints — "IGME 와 연락하지 않고 **유료** 부가가치 서비스를 만들지 못한다". 무료 뷰어는 걸리지
  않는다. 출처는 IGME. `ATTRIBUTION`
- **1:100만은 3857 을 그려 주지 않는다** — 4326 으로 받아 화면이 옮겨 그린다. MAGNA 는 3857 그대로이고 줌 11 부터 그린다
- ArcGIS 의 레이어 이름이 번호(`0`)라 카탈로그에는 `igme:<판>:<번호>` 로 둔다
- 속성 — MAGNA 는 `application/geo+json`, 1:100만은 GeoJSON 을 주지 않고 `text/plain` 은 값에 쌍반점이 섞여 깨진다. 그래서
  ArcGIS 의 `featureinfo_xml`(Field·FieldName·FieldValue)로 읽는다. 열 이름의 띄어쓰기가 빠져 온다(`Litologíagenérica`)
"""
import logging
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "igme:"
ATTRIBUTION = '<a href="https://info.igme.es/" target="_blank" rel="noopener">© IGME</a> (CN IGME-CSIC)'
SHEETS = {"geologico1m": "IGME_Geologico_1M", "magna50": "IGME_MAGNA_50"}
#: 판마다 받는 투영과 그리는 화면 줌
PROJECTION = {"geologico1m": "EPSG:4326", "magna50": "EPSG:3857"}
ZOOMS = {"geologico1m": (None, None), "magna50": (11, None)}
_ESRI = "{http://www.esri.com/wms}"


class IgmeError(RuntimeError):
    pass


def split(name: str):
    """`igme:magna50:0` → ("magna50", "0")."""
    sheets, layers = set(), []
    for one in str(name or "").split(","):
        one = one.strip()
        if one.startswith(PREFIX):
            one = one[len(PREFIX):]
        sheet, _, layer = one.partition(":")
        if sheet not in SHEETS or not layer:
            raise IgmeError(f"모르는 레이어다: {one}")
        sheets.add(sheet)
        layers.append(layer)
    if len(sheets) != 1:
        raise IgmeError("판이 다른 레이어를 한 번에 물을 수 없다")
    return sheets.pop(), ",".join(layers)


def _get(sheet: str, params: dict):
    left = usage.paused()
    if left:
        raise IgmeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.IGME_WMS_URL.rstrip('/')}/{SHEETS[sheet]}/MapServer/WMSServer"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("igme", ok=False)
        raise IgmeError(f"IGME 에 닿지 못했다: {exc}") from exc
    log.info("IGME %s -> %s", r.url, r.status_code)
    usage.record("igme", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str):
    asked = str(params.get("version", ""))
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    # 1.3.0 의 4326 은 위도가 먼저다 — 1.1.1 로 옮겨 적으니 범위도 경도 먼저로 뒤집는다(1:100만이 4326 으로 받는다)
    if asked.startswith("1.3") and str(params.get("srs", "")).upper() == "EPSG:4326" and params.get("bbox"):
        s, w, n, e = str(params["bbox"]).split(",")
        params["bbox"] = ",".join((w, s, e, n))
    sheet, params["layers"] = split(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = split(params["query_layers"])[1]
    return sheet, params


def get_map(params: dict):
    sheet, params = _wms(params, "GetMap")
    r = _get(sheet, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise IgmeError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    sheet, name = split(layer)
    r = _get(sheet, {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                     "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise IgmeError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    sheet, params = _wms(params, "GetFeatureInfo")
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    params["info_format"] = "application/geo+json" if sheet == "magna50" else "application/vnd.esri.wms_featureinfo_xml"
    r = _get(sheet, params)
    if r.status_code != 200:
        raise IgmeError(f"속성을 읽지 못했다 (status={r.status_code})")
    if sheet == "magna50":
        try:
            return {"features": r.json().get("features") or []}
        except ValueError as exc:
            raise IgmeError("속성이 JSON 이 아니다") from exc
    return {"features": parse_esri_xml(r.text)}


def parse_esri_xml(text: str) -> list:
    """ArcGIS `featureinfo_xml` → feature 목록. `<FeatureInfo><Field><FieldName/><FieldValue/></Field>…`"""
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    features = []
    for info in root.iter(f"{_ESRI}FeatureInfo"):
        props = {}
        for field in info.iter(f"{_ESRI}Field"):
            name = (field.findtext(f"{_ESRI}FieldName") or "").strip()
            if name:
                props[name] = (field.findtext(f"{_ESRI}FieldValue") or "").strip()
        features.append({"id": f"igme.{props.get('OBJECTID', len(features))}", "properties": props})
    return features


#: 상류의 열 → 팝업에 보일 이름. 값은 스페인어 그대로 둔다
FRIENDLY = (
    ("descripción litológica", "암상"),
    ("Litologíaespecífica", "암상"),
    ("Litologíagenérica", "암석 갈래"),
    ("Sistema", "지질시대"),
    ("Serie", "세"),
    ("Eon-Era", "대"),
    ("unidad cartográfica", "지질 단위"),
    ("Unidadcartográfica", "지질 단위"),
    ("nº de hoja", "도폭"),
)


def friendly(props: dict) -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:
            out[label] = value
    return out
