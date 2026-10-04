"""SEGEMAR(아르헨티나 지질광업조사소)로 나가는 문 — SIGAM GeoServer 의 아르헨티나 지질도 (wetherilli 196).

- 주소: `sigam.segemar.gov.ar/geoserver217/ows` (GeoServer 2.17 WMS). 열쇠가 없다. 워크스페이스는 `sigam:`
- **3857 로 그린다**(2026-10-04, 멘도사 둘레 256² 한 장 2.4 초·53 KB). 유럽 문처럼 3857 로 받는다
- 판: 1:250만 지질 단위·구조선·화산 목록(나라 전체), 1:25만 지질 단위·단층(**간행 도폭만** 덮는다 — 가까이서만 그린다).
  이름은 `segemar:<상류 이름에서 sigam: 을 뗀 것>`
- 속성은 `application/json`. 기하가 따라와 무겁다(1:250만 122 KB) — `propertyName` 으로 열만 받는다. 값은 에스파냐어 그대로 둔다
  (콜롬비아·스페인처럼 — 시대도 `Pleistoceno inferior` 꼴이라 옮기는 표가 없다)
- 범례: `GetLegendGraphic` 그림(1:250만 554×3 280). JSON 범례·`hideEmptyRules` 는 이 판의 GeoServer 가 받지 못한다(NPE·빈 그림,
  2026-10-04) — 그림 한 장을 그대로 낸다
- **CORS 가 없다** — 브라우저가 곧장 못 부른다. 서버 문으로만 가고 정적 판에는 싣지 않는다
- 조건: AccessConstraints "SEGEMAR 의 재산. 크리에이티브 커먼즈 아르헨티나 라이선스로 쓸 때 저작자를 밝힌다", Fees "보기는 자유·무료"
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "segemar:"
WORKSPACE = "sigam:"
ATTRIBUTION = ('<a href="https://sigam.segemar.gov.ar/" target="_blank" rel="noopener">SEGEMAR</a> '
               '(Servicio Geológico Minero Argentino) · SIGAM — CC Argentina, atribución')
#: 판 → (첫 줌, 끝 줌). 1:25만은 간행 도폭만 덮어 멀리서는 빈 데가 많다 — 가까이서만
ZOOMS = {"e250K_UnidadGeologica": (9, None), "e250K.Fallas": (9, None)}
#: 속성으로 받을 열 — 기하를 떼려고 `propertyName` 에 넣는다
PROPERTIES = {
    "e2.5M.UnidadesGeologicas": "sigla,nombre,ambiente,edad_inf,edad_sup,litologia,region",
    "e250K_UnidadGeologica": "nro_hoja,nom_hoja,nombre,descrip_litologica,edad_inf,edad_sup,jerarquia",
}
TIMEOUT = 45


class SegemarError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "").startswith(PREFIX)


def upstream_name(name: str) -> str:
    return str(name or "").split(",")[0].strip()[len(PREFIX):] if knows(name) else str(name or "")


def _qualify(names: str) -> str:
    out = []
    for one in str(names or "").split(","):
        one = one.strip()
        if not knows(one):
            raise SegemarError(f"모르는 레이어다: {one}")
        out.append(WORKSPACE + one[len(PREFIX):])
    return ",".join(out)


def _get(params: dict):
    left = usage.paused()
    if left:
        raise SegemarError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.SEGEMAR_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("segemar", ok=False)
        raise SegemarError(f"SEGEMAR 에 닿지 못했다: {exc}") from exc
    log.info("SEGEMAR %s -> %s", r.url, r.status_code)
    usage.record("segemar", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["layers"] = _qualify(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = _qualify(params["query_layers"])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SegemarError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": _qualify(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise SegemarError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/json"
    columns = PROPERTIES.get(params["query_layers"].split(",")[0][len(WORKSPACE):])
    if columns:
        params["propertyName"] = columns
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise SegemarError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise SegemarError("속성이 JSON 이 아니다") from exc


FRIENDLY = (
    ("sigla", "기호"),
    ("nombre", "이름"),
    ("litologia", "암석"),
    ("descrip_litologica", "암석"),
    ("ambiente", "퇴적 환경"),
    ("region", "지역"),
    ("jerarquia", "층서 단위"),
    ("nom_hoja", "도폭"),
)


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(에스파냐어)은 그대로 둔다. 시대는 아래·위가 같으면 하나, 다르면 `아래 - 위` 로 잇는다."""
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:
            if key == "nom_hoja" and props.get("nro_hoja"):
                value = f"{props['nro_hoja']} {value}"
            out[label] = value
    low, high = str(props.get("edad_inf") or "").strip(), str(props.get("edad_sup") or "").strip()
    if low or high:
        out["지질시대"] = low if low == high or not high else (high if not low else f"{low} - {high}")
    return out
