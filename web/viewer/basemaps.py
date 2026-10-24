"""조건이 열린 배경으로 나가는 문 — NASA GIBS(Blue Marble WMTS·WMS)와 GEBCO 해저 지형(WMS) (wetherilli 184),
NPI 의 스발바르 지형도·위성 모자이크 타일 (wetherilli 200)·정주지 상세도 FKB (wetherilli 425), 그리고 배경이 아니라 겹쳐 그리는 GIBS 레이어 — MEaSUREs 빙하 속도 (wetherilli 413).

브라우저가 곧장 부르던 배경 가운데 **담아 두어도 되는 것**만 서버를 거쳐 캐시에 담는다(`views.gibs_tile`·`gibs_wms`·`gebco_wms`).

- **GEBCO** — GEBCO Grid 는 공공 도메인이다. 출처만 밝힌다. 한 장에 2–3 초라(2026-10-04 에 서버에서 2.8 초) 담아 두는 덕이 크다
- **NASA GIBS** — NASA 지구과학 자료는 쓰임에 제한이 없다(출처 표기를 바란다). 한 장에 1 초 남짓(같은 날 0.95 초)
- **NPI 타일** — 두 서비스의 설명이 "Lisensiert/licensed under CC BY 4.0" 이다(`copyrightText` "Norsk Polarinstitutt",
  위성은 "… Copernicus Sentinel data", 2026-10-04). 출처는 화면이 이미 단다. `Basisdata/` 의 것만 — `Basisdata_Intern/` 은 부르지 않는다(P01).
  FKB 상세도는 "Tjenesten er tilgjengelig under CC-BY-lisensen" 이고 롱위에아르뷔엔 둘레는 공동 소유자를 함께 밝히라고 한다(2026-10-24).
  같은 폴더의 정사사진(`NP_Ortofoto_*`)은 조건 칸이 비어 있어 부르지 않는다

받는 것은 브라우저가 부르던 주소 그대로다 — WMTS 는 같은 경로를, WMS 는 브라우저가 보낸 변수(`kigam.clean_params` 로 거른 것)를
그대로 넘긴다. 레이어·투영·줌은 화면이 쓰는 것만 받는다. 조건을 먼저 봐야 하는 배경(PGC 음영·NPI 타일·Trek 영상·EOX·Esri)은
여기 없다 — 조건을 읽고 나서 이 문에 더한다. VWorld 는 열쇠에 도메인 제한이 걸려 곧장 부른다(003).
PGC 음영·Trek 영상은 2026-10-04 에 읽었지만 다시 내줘도 되는지가 분명하지 않아 그대로 둔다(wetherilli 200, TODOs (사람)).

**GIBS 의 겹쳐 그리는 레이어**(`GIBS_OVERLAYS`) — 남극·그린란드 빙하 속도(NSIDC-0484·0478)는 카탈로그 레이어(`gibs:` 씨앗)지만
같은 GIBS 의 같은 격자라 문을 새로 내지 않고 여기에 얹는다. 다른 것은 셋이다 — PNG(투명)이고, 시점(`Time`)이 경로에 들고,
레이어 이름을 화면이 아니라 이 표가 고른다. 시점은 Capabilities 의 `Default` 를 적어 둔다. 범례는 GIBS 의 SVG 를 화면이 곧장 부른다.
누른 자리의 값은 없다 — WMTS 라 `GetFeatureInfo` 가 없다.

두 상류를 문 하나에 묶은 것은 하는 일이 같아서다 — 열쇠 없이 타일 한 장을 받아 그림인지만 본다. `elevation.py` 가 표고 상류
셋을 묶은 것과 같은 까닭이다. 상류가 바뀌면 고칠 자리는 `settings.GIBS_URL`·`GEBCO_WMS_URL` 과 아래 표다.
"""
import logging
import math

import requests
from django.conf import settings

from . import tiles, usage

log = logging.getLogger(__name__)

#: 화면이 쓰는 GIBS 레이어(`map.js` 의 `gibsLayer`, `earth.js` 의 `BASES`)
GIBS_LAYERS = ("BlueMarble_ShadedRelief_Bathymetry", "BlueMarble_NextGeneration", "BlueMarble_ShadedRelief")
#: GIBS WMTS 의 투영 → 500 m 판의 마지막 줌. 4326 은 줌 0 이 288° 한 장(가로 2·세로 1), 극지는 2×2 장이다
GIBS_ZOOMS = {"4326": 8, "3413": 4, "3031": 4}
#: 겹쳐 그리는 GIBS 레이어 — 카탈로그 이름 → (GIBS 레이어, 투영, 시점). 격자는 Blue Marble 과 같은 `500m`(줌 0–4, 512 px)다
GIBS_OVERLAYS = {
    "gibs:ice_velocity_antarctica": ("MEaSUREs_Ice_Velocity_Antarctica", "3031", "1996-01-01"),
    "gibs:ice_velocity_greenland": ("MEaSUREs_Ice_Velocity_Greenland", "3413", "2008-12-01"),
}
GIBS_OVERLAY_ZOOM = 4
GIBS_ATTRIBUTION = ('Ice velocity: <a href="https://doi.org/{doi}" target="_blank" rel="noopener">MEaSUREs {short}</a> '
                    '({who}, NASA NSIDC DAAC) via <a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA GIBS</a>')
GIBS_CITES = {
    "gibs:ice_velocity_antarctica": {"doi": "10.5067/D7GK8F5J8M8R", "short": "NSIDC-0484", "who": "Rignot, Mouginot &amp; Scheuchl 2017"},
    "gibs:ice_velocity_greenland": {"doi": "10.5067/OC7B04ZM9G6Q", "short": "NSIDC-0478", "who": "Joughin et al. 2015"},
}
#: 화면이 쓰는 GEBCO 레이어(`map.js` 의 `gebcoLayer`, `earth.js` 의 `BASES.gebco`)
GEBCO_LAYERS = ("GEBCO_LATEST", "GEBCO_LATEST_SUB_ICE_TOPO")
#: WMS 한 장의 가장 큰 변 — 화면은 512 를, Cesium 은 256 을 부른다
MAX_SIDE = 1024
#: NPI 의 타일 서비스(`map.js` 의 `npiTiles`) — 25833 격자, 줌 0–17
NPI_SERVICES = ("NP_Basiskart_Svalbard_WMTS_25833", "NP_Satellitt_Svalbard_WMTS_25833")
NPI_MAX_ZOOM = 17
#: NPI 의 정주지 상세도(FKB) — 3857 격자. 정주지 둘레에만 그림이 있어 서비스의 `fullExtent`(3857 미터) 밖 칸은 묻지 않는다.
#: 안에서도 빈 칸은 404 라 화면은 지형도 위에 얹는다(`map.js` 의 `npi_fkb`)
FKB_SERVICE = "FKB_Svalbard_WMTS_3857"
FKB_EXTENT = (1303496.06, 14385765.21, 1845320.93, 14899703.44)
WEB_MERCATOR_HALF = 20037508.342789244


class BasemapError(RuntimeError):
    pass


def gibs_tile_count(epsg: str, z: int) -> tuple:
    """GIBS WMTS 한 줌의 칸 수 (가로, 세로)."""
    if epsg == "4326":
        span = 288.0 / 2 ** z                           # 한 장이 덮는 도 — 0.5625°/칸 × 512 칸
        return math.ceil(360 / span), math.ceil(180 / span)
    return 2 ** (z + 1), 2 ** (z + 1)


def knows_gibs_tile(epsg: str, layer: str, z: int, x: int, y: int) -> bool:
    if layer not in GIBS_LAYERS or epsg not in GIBS_ZOOMS or not 0 <= z <= GIBS_ZOOMS[epsg]:
        return False
    cols, rows = gibs_tile_count(epsg, z)
    return 0 <= x < cols and 0 <= y < rows


def wms_ok(params: dict, layers) -> bool:
    """화면이 부르는 꼴의 GetMap 인지 — 남의 서버를 아무렇게나 부르는 길이 되지 않게."""
    if str(params.get("request", "")).lower() != "getmap" or params.get("layers") not in layers:
        return False
    try:
        width, height = int(params.get("width", 0)), int(params.get("height", 0))
    except ValueError:
        return False
    return 0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE and bool(params.get("bbox"))


def _get(upstream: str, url: str, params=None, empty_404: bool = False):
    left = usage.paused()
    if left:
        raise BasemapError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise BasemapError(f"{upstream} 에 닿지 못했다: {exc}") from exc
    log.info("%s %s -> %s", upstream, r.url, r.status_code)
    if empty_404 and r.status_code == 404:
        usage.record(upstream, ok=True, elapsed=r.elapsed)
        return tiles.blank_tile(256, 256)
    usage.record(upstream, ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BasemapError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def knows_npi_tile(service: str, z: int, x: int, y: int) -> bool:
    """화면이 부르는 NPI 타일인가. 격자의 칸 수는 서비스의 `tileInfo` 원점에서 스발바르까지라 2^z 보다 넉넉히 잡는다."""
    if service == FKB_SERVICE:
        return knows_fkb_tile(z, x, y)
    return service in NPI_SERVICES and 0 <= z <= NPI_MAX_ZOOM and 0 <= x < 2 ** (z + 3) and 0 <= y < 2 ** (z + 3)


def knows_fkb_tile(z: int, x: int, y: int) -> bool:
    """FKB 의 3857 칸이 서비스의 범위에 걸치는가."""
    if not 0 <= z <= NPI_MAX_ZOOM:
        return False
    size = 2 * WEB_MERCATOR_HALF / 2 ** z
    left, top = -WEB_MERCATOR_HALF + x * size, WEB_MERCATOR_HALF - y * size
    xmin, ymin, xmax, ymax = FKB_EXTENT
    return left < xmax and left + size > xmin and top > ymin and top - size < ymax


def npi_tile(service: str, z: int, x: int, y: int) -> bytes:
    """NPI 의 미리 구운 타일 한 장. 경로는 브라우저가 부르던 그대로다 — `…/MapServer/tile/z/y/x`."""
    if not knows_npi_tile(service, z, x, y):
        raise BasemapError("모르는 NPI 타일이다")
    # FKB 는 정주지 밖 칸이 404 다 — 그릴 것이 없다는 뜻이라 투명한 칸으로 담는다
    return _get("npi-tile", f"{settings.NPI_TILE_URL.rstrip('/')}/{service}/MapServer/tile/{z}/{y}/{x}",
                empty_404=service == FKB_SERVICE)


def gibs_tile(epsg: str, layer: str, z: int, x: int, y: int) -> bytes:
    """GIBS WMTS 한 장 (JPEG). 경로는 브라우저가 부르던 그대로다 — z/y/x."""
    if not knows_gibs_tile(epsg, layer, z, x, y):
        raise BasemapError("모르는 GIBS 타일이다")
    base = settings.GIBS_URL.rstrip("/")
    return _get("gibs", f"{base}/wmts/epsg{epsg}/best/{layer}/default/500m/{z}/{y}/{x}.jpeg")


def knows_gibs_overlay(epsg: str, layer: str, z: int, x: int, y: int) -> bool:
    """겹쳐 그리는 GIBS 타일인가 — 경로의 레이어는 GIBS 의 이름이다"""
    if not any(spec[:2] == (layer, epsg) for spec in GIBS_OVERLAYS.values()) or not 0 <= z <= GIBS_OVERLAY_ZOOM:
        return False
    cols, rows = gibs_tile_count(epsg, z)
    return 0 <= x < cols and 0 <= y < rows


def gibs_overlay_time(layer: str) -> str:
    return next(time for name, epsg, time in GIBS_OVERLAYS.values() if name == layer)


def gibs_overlay_path(name: str) -> str:
    """카탈로그 레이어 → 화면이 부를 우리 주소의 꼴 (`gibs/<투영>/<레이어>/{z}/{y}/{x}.png`)"""
    layer, epsg, _ = GIBS_OVERLAYS[name]
    return f"gibs/{epsg}/{layer}/{{z}}/{{y}}/{{x}}.png"


def gibs_overlay_direct(name: str) -> str:
    """정적 판이 곧장 부를 GIBS 주소의 꼴 — 서버가 받는 것과 같다"""
    layer, epsg, time = GIBS_OVERLAYS[name]
    return f"{settings.GIBS_URL.rstrip('/')}/wmts/epsg{epsg}/best/{layer}/default/{time}/500m/{{z}}/{{y}}/{{x}}.png"


def gibs_overlay_legend(name: str) -> str:
    """GIBS 의 가로 범례 그림(SVG) — 화면이 `<img>` 로 곧장 부른다(그 안의 스크립트는 `<img>` 에서 돌지 않는다)"""
    return f"{settings.GIBS_URL.rstrip('/')}/legends/{GIBS_OVERLAYS[name][0]}_H.svg"


def gibs_overlay_grid() -> dict:
    """화면이 받을 격자 — `map.js` 의 `gibsLayer` 와 같다(원점 (-4194304, 4194304), 줌 0 이 8192 m, 512 px)"""
    return {"origin": [-4194304, 4194304], "extent": [-4194304, -4194304, 4194304, 4194304], "tileSize": 512,
            "resolutions": [8192 / 2 ** z for z in range(GIBS_OVERLAY_ZOOM + 1)]}


def gibs_overlay_tile(epsg: str, layer: str, z: int, x: int, y: int) -> bytes:
    """겹쳐 그리는 GIBS 타일 한 장 (PNG). 경로는 정적 판이 부르는 그대로다 — 시점을 넣은 z/y/x"""
    if not knows_gibs_overlay(epsg, layer, z, x, y):
        raise BasemapError("모르는 GIBS 타일이다")
    return _get("gibs", f"{settings.GIBS_URL.rstrip('/')}/wmts/epsg{epsg}/best/{layer}/default/"
                        f"{gibs_overlay_time(layer)}/500m/{z}/{y}/{x}.png")


def gibs_wms(params: dict) -> bytes:
    """GIBS WMS(4326) 한 장 — 온 지구의 구(Cesium)가 부른다."""
    if not wms_ok(params, GIBS_LAYERS):
        raise BasemapError("화면이 부르는 꼴의 GetMap 이 아니다")
    return _get("gibs", f"{settings.GIBS_URL.rstrip('/')}/wms/epsg4326/best/wms.cgi", params)


def gebco_wms(params: dict) -> bytes:
    """GEBCO WMS 한 장 (PNG)."""
    if not wms_ok(params, GEBCO_LAYERS):
        raise BasemapError("화면이 부르는 꼴의 GetMap 이 아니다")
    return _get("gebco", settings.GEBCO_WMS_URL, params)


#: 레이어 패널의 딱지 — 겹쳐 그리는 GIBS 레이어(빙하 속도)만 카탈로그에 선다. 배경은 딱지가 없다 (`doors.py`, wetherilli 413)
REGISTRY = [
    {"upstream": "gibs", "tag": "NASA", "title": "미국 항공우주국 GIBS"},
]
