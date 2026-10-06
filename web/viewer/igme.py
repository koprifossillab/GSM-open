"""IGME(스페인 지질광물연구소)로 나가는 문 — 스페인 지질도 (wetherilli 147).

- 주소: `mapas.igme.es/gis/services/Cartografia_Geologica/<판>/MapServer/WMSServer` (ArcGIS WMS). 판은 둘 —
  `IGME_Geologico_1M`(이베리아 반도·발레아레스·카나리아 1:100만)·`IGME_MAGNA_50`(MAGNA 1:5만). 열쇠가 없다
- 조건: GetCapabilities 의 AccessConstraints — "IGME 와 연락하지 않고 **유료** 부가가치 서비스를 만들지 못한다". 무료 뷰어는 걸리지
  않는다. 출처는 IGME. `ATTRIBUTION`
- **1:100만은 3857 을 그려 주지 않는다** — 4326 으로 받아 화면이 옮겨 그린다. MAGNA 는 3857 그대로이고 줌 11 부터 그린다
- ArcGIS 의 레이어 이름이 번호(`0`)라 카탈로그에는 `igme:<판>:<번호>` 로 둔다
- 속성 — MAGNA 는 `application/geo+json`, 1:100만은 GeoJSON 을 주지 않고 `text/plain` 은 값에 쌍반점이 섞여 깨진다. 그래서
  ArcGIS 의 `featureinfo_xml`(Field·FieldName·FieldValue)로 읽는다. 열 이름의 띄어쓰기가 빠져 온다(`Litologíagenérica`)
- **도미니카공화국 1:25만**(판 `sgnrd`, wetherilli 242) — 도미니카 지질조사소(SGN)·BGR 의 SYSMIN 지질도를 IGME 가 같은 서버의 다른 폴더
  (`PSysmin/IGME_SGN_EN_Geology`)에 연다. 영어판이다. **WMS 번호와 REST 번호가 거꾸로**다 — WMS `0` 지질 단위·`1` 구조(단층·경계).
  Capabilities 는 3857 을 적지 않지만 그린다(코르디예라 센트랄 512² 2.0 초). 속성은 geojson 이 `InvalidFormat` 이라 1:100만처럼
  `featureinfo_xml` 로 — `Descriptio`·`System`·`Series`(ICS 영어). 범례 그림은 2 383×4 877 이라 두지 않는다. 조건 문구는 없다(사람이 읽는다)
"""
import logging
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

from . import i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "igme:"
ATTRIBUTION = '<a href="https://info.igme.es/" target="_blank" rel="noopener">© IGME</a> (CN IGME-CSIC)'
#: 판 → 서비스. `/` 가 든 것은 `Cartografia_Geologica` 밖의 폴더다(서비스 뿌리에서 센다)
SHEETS = {"geologico1m": "IGME_Geologico_1M", "magna50": "IGME_MAGNA_50", "sgnrd": "PSysmin/IGME_SGN_EN_Geology",
          # 광물 산지(BDMIN Indicios)·산업 광물·암석 채굴지(BDMIN Explotaciones) — `BasesDatos` 폴더 (wetherilli 296)
          "bdmin": "BasesDatos/IGME_BDMIN_Indicios", "bdminexp": "BasesDatos/IGME_BDMIN_Explotaciones"}
#: 판마다 받는 투영과 그리는 화면 줌
PROJECTION = {"geologico1m": "EPSG:4326", "magna50": "EPSG:3857", "sgnrd": "EPSG:3857", "bdmin": "EPSG:3857", "bdminexp": "EPSG:3857"}
ZOOMS = {"geologico1m": (None, None), "magna50": (11, None), "sgnrd": (None, None), "bdmin": (None, None), "bdminexp": (None, None)}
#: 범례 그림을 두지 않는 판 — 너무 크다
NO_LEGEND = ("sgnrd",)
ATTRIBUTIONS = {"sgnrd": '<a href="https://info.igme.es/" target="_blank" rel="noopener">SGN República Dominicana · BGR · IGME</a> '
                         "(SYSMIN 1:250 000)"}
_ESRI = "{http://www.esri.com/wms}"


class IgmeError(RuntimeError):
    pass


def split(name: str):
    """`igme:magna50:0` → ("magna50", "0"). 상류 레이어 여럿은 `+` 로 잇는다(`igme:bdmin:0+1`, wetherilli 296 — BGR 과 같다)."""
    sheets, layers = set(), []
    for one in str(name or "").split(","):
        one = one.strip()
        if one.startswith(PREFIX):
            one = one[len(PREFIX):]
        sheet, _, layer = one.partition(":")
        if sheet not in SHEETS or not layer:
            raise IgmeError(f"모르는 레이어다: {one}")
        sheets.add(sheet)
        layers.append(layer.replace("+", ","))
    if len(sheets) != 1:
        raise IgmeError("판이 다른 레이어를 한 번에 물을 수 없다")
    return sheets.pop(), ",".join(layers)


def _get(sheet: str, params: dict):
    left = usage.paused()
    if left:
        raise IgmeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    base = settings.IGME_WMS_URL.rstrip("/")
    if "/" in SHEETS[sheet]:
        base = base.rsplit("/", 1)[0]          # 서비스 뿌리(`…/gis/services`)
    url = f"{base}/{SHEETS[sheet]}/MapServer/WMSServer"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("igme", ok=False)
        raise IgmeError(f"IGME 에 닿지 못했다: {exc}") from exc
    log.info("IGME %s -> %s", r.url, r.status_code)
    usage.record("igme", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
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


#: 목록 범례(`views.list_legend`) — 도미니카공화국 1:25만 지질 단위 (wetherilli 357). 범례 그림은 2 383×4 877 한 장이라 두지 않았는데,
#: REST 의 칠하기 규칙은 77 칸(`Descriptio`)이다. 나라가 작아 보는 범위로 거르지 않고 전부 세운다 — 이 판의 REST 는 통계 질의도 받지 않는다
LEGEND_LAYERS = ("igme:sgnrd:0",)
#: WMS 번호 → REST 번호 (거꾸로다, 위 문서)
_SGNRD_REST = {"0": "1"}


def legend_rows(layer: str) -> list:
    """REST 칠하기 규칙 → 화면의 줄 `[{"lithology", "color", "age"}]`. 이 서버는 이따금 한 분 가까이 걸려 한 번 받아 담는다"""
    if layer not in LEGEND_LAYERS:
        raise IgmeError("범례가 없는 레이어다")
    key = tilecache.key_text("igme-renderer", layer)
    held = tilecache.get(key, ".json")
    if held:
        import json
        return json.loads(held)
    sheet, name = split(layer)
    left = usage.paused()
    if left:
        raise IgmeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    base = settings.IGME_WMS_URL.rstrip("/").rsplit("/", 1)[0].replace("/gis/services", "/gis/rest/services")
    try:
        r = requests.get(f"{base}/{SHEETS[sheet]}/MapServer/{_SGNRD_REST[name]}", params={"f": "json"},
                         timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("igme", ok=False)
        raise IgmeError(f"IGME 에 닿지 못했다: {exc}") from exc
    log.info("IGME %s -> %s", r.url, r.status_code)
    usage.record("igme", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    try:
        infos = r.json()["drawingInfo"]["renderer"]["uniqueValueInfos"]
    except (ValueError, KeyError, TypeError) as exc:
        raise IgmeError(f"칠하기 규칙을 읽지 못했다 (status={r.status_code})") from exc
    rows = []
    for info in infos:
        color = (info.get("symbol") or {}).get("color")
        label = str(info.get("label") or info.get("value") or "").strip()
        if color and label and color[3:4] != [0]:
            rows.append({"symbol": "", "lithology": label, "age": "", "swatch": "",
                         "color": "#" + "".join(f"{int(v):02x}" for v in color[:3])})
    if not rows:
        raise IgmeError("칠하기 규칙이 비었다")
    import json
    tilecache.put(key, json.dumps(rows, ensure_ascii=False).encode("utf-8"), ".json")
    return rows


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
    ("Descriptio", "암상"),                 # 도미니카공화국(영어판, wetherilli 242)
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


#: 광물 산지·채굴지(wetherilli 296) — ESRI XML 의 열 이름(별칭)
MINERAL_FRIENDLY = (("Nombre Mina", "이름"), ("NombreMina", "이름"), ("Sustancia", "광종"), ("Asociación Mineral", "광물 조합"),
                    ("AsociaciónMineral", "광물 조합"), ("Morfología", "광상 형태"), ("Tamaño indicio", "광상 규모"), ("Tamañoindicio", "광상 규모"),
                    ("Estado_Explotacion", "개발 단계"), ("Estado Explotacion", "개발 단계"), ("Forma_Explotacion", "채굴 형태"),
                    ("Forma Explotacion", "채굴 형태"), ("Usos", "쓰임"), ("Municipio", "곳"), ("Provincia", "주"))


def friendly(props: dict, lang: str = "ko") -> dict:
    if "Sustancia" in props:
        out = {}
        for key, label in MINERAL_FRIENDLY:
            value = str(props.get(key) or "").strip()
            if value and value.lower() != "null" and label not in out:
                out[label] = value
        lo = str(props.get("EdadInferior") or props.get("Edad Inferior") or props.get("Edad_inferior") or "").strip()
        hi = str(props.get("EdadSuperior") or props.get("Edad Superior") or props.get("Edad_superior") or "").strip()
        age = " - ".join(x.capitalize() for x in (lo, hi) if x and x.lower() != "null")
        if age:
            out["지질시대 (원문)"] = age
        return out
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:
            out[label] = value
    if "ID_UC250k" in props:
        # 도미니카공화국 — 시대가 ICS 영어다(`Lower Cretaceous-Upper Cretaceous`). 통이 있으면 통을, 없으면 계를 옮긴다
        age = i18n.age_tidy(str(props.get("Series") or "").strip() or str(props.get("System") or "").strip())
        if age:
            out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
        out.pop("세", None)
    return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "igme", "tag": "IGME", "title": "스페인 지질광물연구소", "relay": True, "projected": True, "globe": True},
]
