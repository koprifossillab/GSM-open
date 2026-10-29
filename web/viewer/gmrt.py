"""GMRT(Global Multi-Resolution Topography)로 나가는 문 — 극지 수심 (wetherilli 428).

- 주소: `www.gmrt.org/services/mapserver/wms_SP`(남극, 3031·4326)·`wms_NP`(북극, **3995 뿐**), 그리고 같은 꼴의
  `wms_SP_mask`·`wms_NP_mask` — 다중빔으로 잰 곳만 색이고 나머지(GEBCO 로 메운 곳)는 회색으로 죽인 판이다.
  레이어 이름은 넷 다 `South_Polar_Bathymetry`·`North_Polar_Bathymetry` 이고 서비스(주소)가 판을 가른다.
  열쇠가 없고 CORS `*` 지만 늘 `/GSM/wms/` 를 거친다 — 한 장에 2–3 초라(2026-10-29) 담아 두는 덕이 크다
- 조건: **CC BY 4.0**(Ryan et al. 2009 을 인용), 그리고 "not to be used for navigation" — 범례 자리(`ATTRIBUTION`)와 캡션에 적는다
- 남극은 화면(3031)이 곧장 받는다. 북극은 3413 을 그려 주지 않아 3995 로 받고 화면이 옮겨 그린다 — NGU 의 3575 와 같다(wetherilli 140)
- 그림은 불투명이다(바다·땅을 다 칠한다). 범례 그림(`GetLegendGraphic`)은 빈 그림이라 범례를 싣지 않는다
- **누른 자리의 표고는 PointServer** — `services/PointServer?latitude=…&longitude=…&format=json` 이 `{"elevation": "-261"}` 을 준다.
  WMS 는 `queryable="0"` 이다. 화면이 보낸 `GetFeatureInfo`(평면 좌표의 범위와 픽셀)를 위경도로 풀어 그 한 점을 묻는다
- 레이어명에 `gmrt:` 를 붙여 카탈로그에 둔다 — `gmrt:sp`·`gmrt:sp_mask`·`gmrt:np`·`gmrt:np_mask`
"""
import logging
import math

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('<a href="https://www.gmrt.org/" target="_blank" rel="noopener">GMRT</a> '
               "(Ryan et al. 2009, CC BY 4.0) — not for navigation")
#: 카탈로그 이름 → (서비스, 상류 레이어, 투영)
LAYERS = {
    "gmrt:sp": ("wms_SP", "South_Polar_Bathymetry", "EPSG:3031"),
    "gmrt:sp_mask": ("wms_SP_mask", "South_Polar_Bathymetry", "EPSG:3031"),
    "gmrt:np": ("wms_NP", "North_Polar_Bathymetry", "EPSG:3995"),
    "gmrt:np_mask": ("wms_NP_mask", "North_Polar_Bathymetry", "EPSG:3995"),
}
#: 평사도법 둘 — (기준 위도, 북극인가). 경도 0° 가 가운데 아래(북극)·위(남극)다. WGS84
STEREO = {"EPSG:3031": (-71.0, False), "EPSG:3995": (71.0, True)}
_A, _F = 6378137.0, 1 / 298.257223563
_E = math.sqrt(_F * (2 - _F))


class GmrtError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def projection(name: str) -> str:
    return LAYERS[name][2]


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GmrtError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gmrt", ok=False)
        raise GmrtError(f"GMRT 에 닿지 못했다: {exc}") from exc
    log.info("GMRT %s -> %s", r.url, r.status_code)
    usage.record("gmrt", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _service(name: str) -> str:
    if name not in LAYERS:
        raise GmrtError(f"모르는 GMRT 레이어다: {name}")
    return f"{settings.GMRT_URL.rstrip('/')}/services/mapserver/{LAYERS[name][0]}"


def get_map(params: dict):
    """`GetMap` — 1.1.1 로 옮겨 적는다. (바이트, content-type). 그림이 아니면 GmrtError."""
    name = str(params.get("layers", ""))
    out = dict(params, service="WMS", request="GetMap", version="1.1.1", layers=LAYERS.get(name, ("", ""))[1], styles="")
    if "crs" in out and "srs" not in out:
        out["srs"] = out.pop("crs")
    r = _get(_service(name), out)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GmrtError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise GmrtError("GMRT 는 범례 그림을 주지 않는다")


def stereo_to_latlon(code: str, x: float, y: float):
    """극 평사도법(3031·3995)의 평면 좌표 → (위도, 경도). Snyder(1987) 21-39 꼴, 기준 위도에서 축척 1"""
    lat_c, north = STEREO[code]
    if not north:                       # 남극은 뒤집어 북극의 식을 쓴다
        x, y, lat_c = -x, -y, -lat_c
    phi_c = math.radians(lat_c)
    m_c = math.cos(phi_c) / math.sqrt(1 - (_E * math.sin(phi_c)) ** 2)
    t_c = math.tan(math.pi / 4 - phi_c / 2) / ((1 - _E * math.sin(phi_c)) / (1 + _E * math.sin(phi_c))) ** (_E / 2)
    rho = math.hypot(x, y)
    t = rho * t_c / (_A * m_c)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(10):
        es = _E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - es) / (1 + es)) ** (_E / 2))
    lon = math.degrees(math.atan2(x, -y))
    lat = math.degrees(phi)
    return (lat, lon) if north else (-lat, -lon)


def _clicked(params: dict):
    """`GetFeatureInfo` 의 범위·픽셀 → 누른 자리의 (위도, 경도)"""
    code = str(params.get("crs") or params.get("srs") or "").upper()
    if code not in STEREO:
        raise GmrtError(f"모르는 투영이다: {code}")
    try:
        x0, y0, x1, y1 = (float(v) for v in str(params["bbox"]).split(","))
        width, height = float(params["width"]), float(params["height"])
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError) as exc:
        raise GmrtError("누른 자리를 읽지 못했다") from exc
    return stereo_to_latlon(code, x0 + (i + 0.5) / width * (x1 - x0), y1 - (j + 0.5) / height * (y1 - y0))


def get_feature_info(params: dict) -> dict:
    """누른 자리의 표고 — PointServer 한 번. 음수는 수심이다"""
    lat, lon = _clicked(params)
    r = _get(f"{settings.GMRT_URL.rstrip('/')}/services/PointServer",
             {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "format": "json"})
    if r.status_code != 200:
        raise GmrtError(f"표고를 읽지 못했다 (status={r.status_code})")
    try:
        value = float(r.json()["elevation"])
    except (ValueError, KeyError, TypeError) as exc:
        raise GmrtError("표고가 숫자가 아니다") from exc
    props = {"표고 (m)": f"{value:,.0f}", "위도": f"{lat:.4f}", "경도": f"{lon:.4f}"}
    if value < 0:
        props = {"수심 (m)": f"{-value:,.0f}", **props}
    return {"features": [{"id": "gmrt", "properties": props}]}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "gmrt", "tag": "GMRT", "title": "GMRT 다중 해상도 지형", "relay": True, "projected": True},
]
