"""3857 타일 격자 — 칸 수(2^z)로 센다. 타일 크기(256·512 px)와 상관없이 맞는다. `viewer/tilegrid.py` 의 같은 셈을 옮겼다(viewer 를 타지 않게)."""
import math

HALF = 20037508.342789244            # EPSG:3857 의 반 폭


def lonlat_to_3857(lon: float, lat: float) -> tuple:
    x = lon * HALF / 180
    lat = max(min(lat, 85.0511287798), -85.0511287798)
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * HALF / math.pi
    return x, y


def tiles_for(bbox_lonlat, z: int) -> list:
    """위경도 범위 `(서, 남, 동, 북)` 를 덮는 줌 `z` 의 칸 `(x, y)` 들 — 위에서 아래로 y(OpenLayers 의 tileCoord)."""
    west, south, east, north = bbox_lonlat
    min_x, min_y = lonlat_to_3857(west, south)
    max_x, max_y = lonlat_to_3857(east, north)
    span = 2 * HALF / 2 ** z
    last = 2 ** z - 1
    x0 = max(0, int((min_x + HALF) // span))
    x1 = min(last, int((max_x + HALF) // span))
    y0 = max(0, int((HALF - max_y) // span))
    y1 = min(last, int((HALF - min_y) // span))
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
