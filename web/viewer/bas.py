"""영국 남극조사소(BAS)로 나가는 문 — Bedmap3 빙저 지형·얼음 두께·얼음 윗면의 범례 (wetherilli 261).

- **그림은 문을 거치지 않는다.** BAS 가 ArcGIS Online 에 올린 타일(`tiles.arcgis.com/tiles/tPxy1hrFDhJfZ0Mf/…/Bedmap3*/MapServer`,
  TilesOnly)을 앨버타(`ags.py`)처럼 카탈로그 행의 `tiles` 로 화면이 곧장 받는다 — 열쇠가 없고 CORS 가 Origin 을 되비춘다(2026-10-05).
  타일은 3031 이지만 Esri 극 격자라 **원점·해상도가 우리 3031 격자(GeoMAP)와 다르다** — 행에 `grid`(원점·해상도)를 실어 화면이 그 격자로
  받는다(`map.js` 의 `esriGridSource`)
- 원본은 500 m 격자(Pritchard 외 2025). 캐시는 줌 4 부터(`minScale` 5 654 만 — 그 밑은 404, 화면이 줌 4 를 줄여 그린다), 빙저 지형이 줌 13,
  두께·윗면이 줌 12 까지다(`maxScale` 62 429·160 000) — 그 위는 화면이 늘린다
- 누른 자리는 없다 — 타일 서비스라 `identify` 가 없다. 값은 2D 의 표고·IBCSO 가 갈음한다
- 범례는 REST `legend?f=json` 의 견본 조각(빙저 지형 42 칸, 두께·윗면 9 칸)을 목록으로 — `-4,999.999999 - -4,000` 같은 칸 이름을 정수 m 로 다듬는다.
  한 번 받아 30 일 담는다
- 조건: **CC BY 4.0** — 타일 서비스 항목의 이용 조건. 인용 Pritchard 외 2025(Sci Data 12, 414)·자료 doi 10.5285/2d0e4791-8e20-46a3-80e4-f5f6716025d2
"""
import json
import logging
import re

import requests
from django.conf import settings

from . import tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "bas:"
ATTRIBUTION = ('<a href="https://doi.org/10.1038/s41597-025-04672-y" target="_blank" rel="noopener">Bedmap3</a> '
               "(Pritchard et al. 2025, BAS / UK Polar Data Centre, CC BY 4.0)")
#: 레이어 → (BAS 타일 서비스 이름, 타일의 마지막 줌)
LAYERS = {
    "bas:bedmap3_bed": ("Bedmap3", 13),
    "bas:bedmap3_thickness": ("Bedmap3_thickness", 12),
    "bas:bedmap3_surface": ("Bedmap3_surface", 12),
}
LEGEND_LAYERS = tuple(LAYERS)
#: Esri 극 격자(3031) — 서비스의 `tileInfo`. 줌 0 의 해상도에서 반씩 줄어든다
ORIGIN = (-30635955.4472718, 30635955.4472718)
RESOLUTION0 = 239343.40193181095
EXTENT = (-3333500.0, -3333500.0, 3333500.0, 3333500.0)
#: 캐시가 있는 가장 거친 줌 — 세 서비스 모두 `minScale` 56 537 811 (줌 0 의 1/16)
MIN_ZOOM = 4
LEGEND_MAX_AGE = 30 * 86400


class BasError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _service(name: str) -> str:
    return f"{settings.BAS_TILES_URL.rstrip('/')}/{LAYERS[name][0]}/MapServer"


def tile_url(name: str) -> str:
    return _service(name) + "/tile/{z}/{y}/{x}"


def grid(name: str) -> dict:
    """화면이 받을 격자 — 원점·줌마다의 해상도·범위"""
    return {"origin": list(ORIGIN), "extent": list(EXTENT), "minZoom": MIN_ZOOM,
            "resolutions": [RESOLUTION0 / 2 ** z for z in range(LAYERS[name][1] + 1)]}


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise BasError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bas", ok=False)
        raise BasError(f"BAS 에 닿지 못했다: {exc}") from exc
    log.info("BAS %s -> %s", r.url, r.status_code)
    usage.record("bas", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


_NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")


def tidy_label(label: str) -> str:
    """`-4,999.999999 - -4,000` → `-5,000 – -4,000 m`. 숫자 둘이 아니면 원문"""
    nums = _NUMBER.findall(str(label or ""))
    if len(nums) != 2:
        return str(label or "").strip()
    lo, hi = (round(float(n.replace(",", ""))) for n in nums)
    return f"{lo:,} – {hi:,} m"


def legend_rows(name: str) -> list:
    """REST 범례 → `[{"symbol", "lithology", "age", "color", "swatch"}]` (`views.list_legend` 의 꼴)"""
    if name not in LAYERS:
        raise BasError(f"범례가 없는 레이어다: {name}")
    key = tilecache.key_text("bas-legend", name)
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is None:
        r = _get(_service(name) + "/legend", {"f": "json"})
        try:
            data = r.json()
        except ValueError as exc:
            raise BasError("범례가 JSON 이 아니다") from exc
        if r.status_code != 200 or data.get("error"):
            raise BasError(f"범례를 받지 못했다 (status={r.status_code})")
        rows = []
        for part in data.get("layers") or []:
            for item in part.get("legend") or []:
                if item.get("imageData"):
                    rows.append([str(item.get("label") or ""),
                                 f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"])
        held = json.dumps(rows).encode("utf-8")
        tilecache.put(key, held, ".json")
    return [{"symbol": "", "lithology": tidy_label(label), "age": "", "color": "transparent", "swatch": swatch}
            for label, swatch in json.loads(held)]
