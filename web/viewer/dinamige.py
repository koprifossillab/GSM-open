"""DINAMIGE(우루과이 광업지질국, 산업에너지광업부 MIEM)로 나가는 문 — 우루과이 지질도 1:50만 (wetherilli 196).

- 주소: `geoportal.miem.gub.uy/arcgis1091/services/Dinamige_GeoS/MapaBaseUnidadesGeologicasGeoS/MapServer/WMSServer`
  (ArcGIS WMS). 열쇠가 없다. 레이어는 번호뿐이다 — WMS `0` 지질 단위(색·무늬)·`1` 단층·접촉·선구조·`2` 암맥(Filones).
  **REST 의 번호와 거꾸로다**(REST 는 0 이 암맥, 2026-10-04 에 하나씩 그려 보았다). 이름은 SGC 처럼 WMS 번호로 `dinamige:<번호>`
- Capabilities 는 32721·4326 만 적지만 **3857 GetMap 이 실제 지질도를 그린다**(2026-10-04, 몬테비데오 둘레 256² 2.9 초·53 KB)
- 속성은 `application/geo+json` — 단위 코드(`PP_cb`)·이름·누대/대/계/통·암석·성인. 값은 에스파냐어 그대로 둔다
- 범례: WMS `GetLegendGraphic` 은 18×18 빈 그림을 준다. 대신 ArcGIS REST 의 `legend?f=json`(칸마다 이름과 견본 그림)을 받아
  화면이 목록으로 그린다(`dinamige/legend/`, 일본·대만과 같은 꼴)
- **CORS 가 없다**(Capabilities 는 Origin 을 되돌려 주지만 GetMap·속성은 머리가 없다, 2026-10-04) — 서버 문으로만 가고 정적 판에는 싣지 않는다
- 조건: Capabilities·서비스 설명·MIEM 의 지도 안내에 적힌 것이 없다(2026-10-04). 출처 "DINAMIGE (MIEM)" 를 밝히고, 밖에 열기 전에 사람이 읽는다
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "dinamige:"
LAYERS = ("0", "1", "2")
ATTRIBUTION = ('Carta Geológica del Uruguay 1:500.000 — <a href="https://www.gub.uy/ministerio-industria-energia-mineria/" '
               'target="_blank" rel="noopener">DINAMIGE (MIEM)</a>')
ZOOMS = {}
#: 범례를 목록으로 내는 레이어 — 지질 단위(61 칸)와 선(단층·접촉·선구조 7 칸). 암맥은 한 칸이고 이름이 비어 범례를 두지 않는다
LEGEND_LAYERS = ("dinamige:0", "dinamige:1")
#: WMS 번호 → REST 번호 (범례는 REST 로 묻는다)
REST_ID = {"0": "2", "1": "1", "2": "0"}
TIMEOUT = 45


class DinamigeError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "").startswith(PREFIX) and str(name)[len(PREFIX):] in LAYERS


def _numbers(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if not knows(one):
            raise DinamigeError(f"모르는 레이어다: {one}")
        out.append(one[len(PREFIX):])
    return ",".join(out)


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise DinamigeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("dinamige", ok=False)
        raise DinamigeError(f"DINAMIGE 에 닿지 못했다: {exc}") from exc
    log.info("DINAMIGE %s -> %s", r.url, r.status_code)
    usage.record("dinamige", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms_url() -> str:
    return f"{settings.DINAMIGE_URL.rstrip('/')}/services/Dinamige_GeoS/MapaBaseUnidadesGeologicasGeoS/MapServer/WMSServer"


def _rest_url() -> str:
    return f"{settings.DINAMIGE_URL.rstrip('/')}/rest/services/Dinamige_GeoS/MapaBaseUnidadesGeologicasGeoS/MapServer"


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _numbers(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _numbers(params["query_layers"])
    return params


def get_map(params: dict):
    r = _get(_wms_url(), _wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise DinamigeError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise DinamigeError("그림 범례는 비어 있다 — 목록 범례(`legend_rows`)를 쓴다")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(_wms_url(), params)
    if r.status_code != 200:
        raise DinamigeError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise DinamigeError("속성이 JSON 이 아니다") from exc


def legend_rows(layer: str) -> list:
    """REST `legend?f=json` → 화면이 그리는 줄 `[{"lithology", "age", "swatch", "color"}]`. 견본은 상류의 PNG(base64)다.
    지질 단위의 칸 이름은 `FORMACION DOLORES - Cuaternario Pleistoceno` 꼴이라 마지막 ` - ` 에서 이름과 시대로 가른다"""
    number = REST_ID[_numbers(layer)]
    r = _get(f"{_rest_url()}/legend", {"f": "json"})
    if r.status_code != 200:
        raise DinamigeError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise DinamigeError("범례가 JSON 이 아니다") from exc
    rows = []
    for part in data.get("layers") or []:
        if str(part.get("layerId")) != number:
            continue
        for item in part.get("legend") or []:
            label = str(item.get("label") or "").strip()
            if not label or not item.get("imageData"):
                continue
            name, _, age = label.rpartition(" - ") if " - " in label else (label, "", "")
            rows.append({"symbol": "", "lithology": name, "age": age, "color": "transparent",
                         "swatch": f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"})
    return rows


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() == "null" else value


FRIENDLY = (
    ("CODIGO", "기호"),
    ("NOMBRE DE UNIDAD", "이름"),
    ("NOMBRE DEL GRUPO", "층군"),
    ("LITOLOGIA", "암석"),
    ("ORIGEN", "성인"),
    ("COMENTARIOS", "설명"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(에스파냐어)은 그대로 둔다. 지질시대는 적힌 것 가운데 가장 잘게 가른 것(통 > 계 > 대 > 누대)이다."""
    out = {}
    for key, label in FRIENDLY:
        value = _value(props, key)
        if value and label not in out:
            out[label] = value
    for key in ("SERIE", "SISTEMA", "ERA", "EON"):
        value = _value(props, key)
        if value:
            out["지질시대"] = value
            break
    return out
