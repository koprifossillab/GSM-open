"""앨버타 지질조사소(Alberta Geological Survey, AER)로 나가는 문 — 앨버타 기반암 1:100만 (Map 600)의 누른 자리 (wetherilli 235).

- **그림은 문을 거치지 않는다.** AGS 가 ArcGIS Online 에 올린 타일(`Bedrock_Geology_1M_Map_600_No_Labels_NEW`, 3857 z/x/y, 줌 0–12)뿐이고
  `export` 가 없다(TilesOnly). 일본 지리원 주제 타일(wetherilli 172)처럼 카탈로그 행의 `tiles` 를 화면이 곧장 받는다 — 열쇠가 없고
  CORS 가 열렸다. 캐나다 탭(3978)에서는 OpenLayers 가 옮겨 그린다
- **누른 자리만 이 문이 묻는다** — 같은 자료의 피처 서비스(`Bedrock_Geology_of_Alberta_POLY_DIG_2013_0018/FeatureServer/0`)에 누른 점
  하나로 `query`(`inSR` 은 화면의 투영)
- 조건: Open Government Licence – Alberta. "AER/AGS 를 출처로 밝힌다" — 타일 서비스의 저작권 칸이 그렇게 적는다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "ags:"
ATTRIBUTION = ('<a href="https://ags.aer.ca/publications/all-publications/map-600" target="_blank" rel="noopener">'
               "Alberta Energy Regulator / Alberta Geological Survey</a> (Map 600, OGL–Alberta)")
TILE_URL = ("https://tiles.arcgis.com/tiles/jQV6VMr2Loovu7GU/arcgis/rest/services/Bedrock_Geology_1M_Map_600_No_Labels_NEW/"
            "MapServer/tile/{z}/{y}/{x}")
#: 레이어 → (타일 주소, 타일의 마지막 줌)
LAYERS = {"ags:bedrock": (TILE_URL, 12)}
FIELDS = ("Unit_Name", "Lithology", "Environ", "Age", "GeolRegion")


class AgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise AgsError(f"모르는 레이어다: {names}")
    return names[0]


def get_map(params: dict):
    raise AgsError("앨버타 타일은 화면이 곧장 받는다")


def get_legend(layer: str):
    raise AgsError("앨버타 범례는 따로 받지 않는다")


def get_feature_info(params: dict) -> dict:
    """WMS GetFeatureInfo 변수(화면이 누른 자리 둘레로 지은 작은 네모) → 그 가운데 점 하나로 피처 서비스 `query`."""
    _one(params)
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    try:
        west, south, east, north = (float(v) for v in str(params["bbox"]).split(","))
    except (KeyError, ValueError) as exc:
        raise AgsError("범위를 읽지 못했다") from exc
    if not crs.startswith("EPSG:"):
        raise AgsError(f"EPSG 로만 묻는다: {crs}")
    left = usage.paused()
    if left:
        raise AgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.AGS_FEATURE_URL.rstrip("/") + "/query",
                         params={"geometry": f"{(west + east) / 2!r},{(south + north) / 2!r}", "geometryType": "esriGeometryPoint",
                                 "inSR": crs[5:], "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(FIELDS),
                                 "returnGeometry": "false", "f": "json"},
                         timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ags", ok=False)
        raise AgsError(f"앨버타에 닿지 못했다: {exc}") from exc
    log.info("AGS %s -> %s", r.url, r.status_code)
    usage.record("ags", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    if r.status_code != 200:
        raise AgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise AgsError("속성이 JSON 이 아니다") from exc
    if data.get("error"):
        raise AgsError(f"query 오류: {data['error'].get('message', '')}")
    return {"features": [{"id": f"ags.{n}", "properties": f.get("attributes") or {}}
                         for n, f in enumerate(data.get("features") or [])]}


def friendly(props: dict, lang: str = "ko") -> dict:
    """지층·암상·퇴적 환경은 영어 그대로, 시대(`Upper Cretaceous` 따위)만 옮긴다."""
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    age = v("Age")
    # Map 600 은 `Upper`·`Lower` 를 쓴다 — ICS 의 Late·Early 로 바꿔 옮긴다
    ics = " ".join({"Upper": "Late", "Lower": "Early"}.get(w, w) for w in age.split())
    rows = (("지층", v("Unit_Name")), ("암석", v("Lithology")), ("퇴적 환경", v("Environ")),
            ("지질시대", (i18n.age_ko(ics) if i18n.age_ko(ics) != ics else age) if lang == "ko" and age else age), ("지역", v("GeolRegion")))
    return {k: x for k, x in rows if x}
