"""SGC(콜롬비아 지질조사소)로 나가는 문 — 남미 지질도와 콜롬비아 지질도 (wetherilli 188).

- 주소: `srvags.sgc.gov.co/arcgis/services/<판>/MapServer/WMSServer` (ArcGIS WMS). 판은 둘 —
  `Mapa_Geologico_Sur_America/GeologicalMapSouthAmerican`(남미 1:500만, CGMW 2019 — Gómez·Schobbenhaus·Montes 편)·
  `Mapa_Geologico_Colombia/Mapa_Geologico_Colombia_V2023`(콜롬비아 1:50만, 콜롬비아 지질 아틀라스 2023). 열쇠가 없다
- Capabilities 는 4326(콜롬비아는 4686 도)만 적지만 **3857 GetMap 도 그린다**(2026-10-04 에 잰 것) — 다른 유럽 문처럼 3857 로 받는다
- 레이어 번호는 WMS 의 것이다 — ArcGIS REST 의 번호와 다르다. 이름은 `sgc:<판>:<번호>`
- 속성은 `application/geo+json` — 남미 판은 영어 열(`Unit code`·누대·대·기·암석), 콜롬비아 판은 에스파냐어 열(`Símbolo UC`·`Edad`)
- 조건: 남미 판은 **CGMW 의 지도**다 — SGC 가 WMS 를 열어 두었지만 CGMW 는 지도를 판다. 밖에 열기 전에 사람이 읽는다(TODOs).
  콜롬비아 판은 SGC 열린자료(CC BY 4.0). AccessConstraints 는 둘 다 비어 있다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "sgc:"
ATTRIBUTION = ('Geological Map of South America 2019 (Gómez, Schobbenhaus & Montes, CGMW · '
               '<a href="https://www.sgc.gov.co/" target="_blank" rel="noopener">Servicio Geológico Colombiano</a> · SGB) · '
               'Mapa Geológico de Colombia 2023 (SGC, CC BY 4.0)')
SHEETS = {"sa": "Mapa_Geologico_Sur_America/GeologicalMapSouthAmerican",
          "co": "Mapa_Geologico_Colombia/Mapa_Geologico_Colombia_V2023"}
ZOOMS = {"sa": (None, None), "co": (None, None)}
#: 정적 판(GitHub Pages)에 실을 수 있는 판 — 조건이 열린 콜롬비아 1:50만(SGC 열린자료, CC BY 4.0)만이다 (wetherilli 201).
#: 남미 1:500만은 CGMW 의 지도라 사람이 조건을 읽기 전에는 싣지 않는다. 싣는 것은 굽는 사람이 고른다(`static_site.py --with colombia`)
STATIC_SHEETS = ("co",)
#: 정적 판의 출처 표기 — 실는 판의 것만
STATIC_ATTRIBUTION = ('Mapa Geológico de Colombia 2023 (<a href="https://www.sgc.gov.co/" target="_blank" rel="noopener">'
                      'Servicio Geológico Colombiano</a>, CC BY 4.0)')
#: 넓은 줌의 512 타일은 따로 물으면 3–4 초인데, 화면이 여러 장을 한꺼번에 물으면 상류에서 밀려 20 초를 넘긴다(2026-10-04).
#: EGDI 처럼 더 기다린다 — gunicorn 의 60 초 안에서
TIMEOUT = 45


class SgcError(RuntimeError):
    pass


def static_ok(name: str) -> bool:
    """정적 판에 실어도 되는 레이어인가 — 조건이 열린 판(`STATIC_SHEETS`)의 것만."""
    try:
        return split(name)[0] in STATIC_SHEETS
    except SgcError:
        return False


def split(name: str):
    sheets, layers = set(), []
    for one in str(name or "").split(","):
        one = one.strip()
        if one.startswith(PREFIX):
            one = one[len(PREFIX):]
        sheet, _, layer = one.partition(":")
        if sheet not in SHEETS or not layer.isdigit():
            raise SgcError(f"모르는 레이어다: {one}")
        sheets.add(sheet)
        layers.append(layer)
    if len(sheets) != 1:
        raise SgcError("판이 다른 레이어를 한 번에 물을 수 없다")
    return sheets.pop(), ",".join(layers)


def _get(sheet: str, params: dict):
    left = usage.paused()
    if left:
        raise SgcError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.SGC_WMS_URL.rstrip('/')}/{SHEETS[sheet]}/MapServer/WMSServer"
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgc", ok=False)
        raise SgcError(f"SGC 에 닿지 못했다: {exc}") from exc
    log.info("SGC %s -> %s", r.url, r.status_code)
    usage.record("sgc", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
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
        raise SgcError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    sheet, name = split(layer)
    r = _get(sheet, {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                     "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise SgcError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    sheet, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(sheet, params)
    if r.status_code != 200:
        raise SgcError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise SgcError("속성이 JSON 이 아니다") from exc


#: 남미 판은 누대·대·기를 "가장 오랜"·"가장 젊은" 둘로 적는다 — 같으면 하나로, 다르면 `오랜 - 젊은` 으로 잇는다(`i18n.age_ko` 가 `~` 로 옮긴다)
AGE_PAIRS = (("The oldest period", "The youngest period"), ("The oldest era", "The youngest era"),
             ("The oldest eon", "The youngest eon"))

FRIENDLY = (
    ("Unit code", "기호"),
    ("Símbolo UC", "기호"),
    ("Descripción", "암석"),
    ("Rock type", "암석"),
    ("Rock classification", "암석 분류"),
    ("Edad", "지질시대"),
    ("Name", "이름"),
    ("Nombre", "이름"),
    ("Tipo", "갈래"),
    ("Type", "갈래"),
)


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() == "null" else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 남미 판의 지질시대(영문 ICS)는 한국어판이면 옮기고, 콜롬비아 판의 값(에스파냐어)은 그대로 둔다."""
    out = {}
    for key, label in FRIENDLY:
        value = _value(props, key)
        if value and label not in out:
            out[label] = value
        if key == "Unit code" and "지질시대" not in out:
            for old, young in AGE_PAIRS:
                a, b = _value(props, old), _value(props, young)
                if a or b:
                    age = a if a == b or not b else (b if not a else f"{a} - {b}")
                    out["지질시대"] = i18n.age_ko(age) if lang == "ko" else age
                    break
    return out
