"""타일·지층 면을 박스로 잘라 낸다(wetherilli 385), 빈 타일 가리기. Pillow 만 쓴다."""
import io
import math

from PIL import Image, ImageDraw

from . import grid

UNITS_DIGITS = 5               # 지층 면 좌표의 소수 자리 — 1 m 남짓. 5만 지질도(1 mm = 50 m)에 넉넉하다


def is_blank(data: bytes) -> bool:
    """투명 한 장인가. 읽지 못하면 빈 것이 아니다 — 넣어 둔다."""
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            alpha = image.convert("RGBA").getchannel("A")
            return alpha.getextrema()[1] == 0
    except (OSError, ValueError):
        pass
    return False


def round_coords(coords, digits=UNITS_DIGITS):
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], digits), round(coords[1], digits)]
    return [round_coords(c, digits) for c in coords]


def clip_tile(data: bytes, z: int, x: int, y: int, bbox, on=None) -> bytes:
    """타일(격자 줌 z)에서 박스(경위도) 밖을 투명하게 비운다. 다 안이면 그대로, 다 밖이면 b"".
    `on` 은 격자(`grid.Grid`) — 없거나 3857 이면 지금까지의 셈(경위도 네모가 3857 의 네모다)이고, 다른 격자는 테두리를 투영해 다각형으로 자른다"""
    if on is not None and on.name != grid.MERCATOR.name:
        return _clip_projected(data, z, x, y, bbox, on)
    span = 2 * grid.HALF / 2 ** z
    left, top = -grid.HALF + x * span, grid.HALF - y * span
    west, south = grid.lonlat_to_3857(bbox[0], bbox[1])
    east, north = grid.lonlat_to_3857(bbox[2], bbox[3])
    if east <= left or west >= left + span or north <= top - span or south >= top:
        return b""
    if west <= left and east >= left + span and south <= top - span and north >= top:
        return data
    try:
        image = Image.open(io.BytesIO(data)).convert("RGBA")
    except (OSError, ValueError):
        return data
    size = image.size[0]
    box = (max(0, math.floor((west - left) / span * size)), max(0, math.floor((top - north) / span * size)),
           min(size, math.ceil((east - left) / span * size)), min(size, math.ceil((top - south) / span * size)))
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.paste(image.crop(box), box[:2])
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _inside(point, ring):
    """점이 고리 안에 드나 — 짝홀 규칙."""
    px, py = point
    hit = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
        if (ay > py) != (by > py) and px < ax + (bx - ax) * (py - ay) / (by - ay):
            hit = not hit
    return hit


def _clip_projected(data, z, x, y, bbox, on):
    """3857 밖의 격자(극 평사도법 따위, wetherilli 410) — 경위도 네모는 부채꼴이라 투영의 네모로 자르면 둘레가 샌다.
    테두리를 투영한 다각형으로 칸 밖을 비운다. 네 귀가 다 안이고 테두리가 칸을 지나지 않으면 그대로 둔다"""
    left, bottom, right, top = on.cell_extent(z, x, y)
    ring = on.edge(bbox)
    b = _bounds_of(ring)
    if b[2] <= left or b[0] >= right or b[3] <= bottom or b[1] >= top:
        return b""
    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    crossing = any(left < px < right and bottom < py < top for px, py in ring)
    if not crossing and all(_inside(c, ring) for c in corners):
        return data
    try:
        image = Image.open(io.BytesIO(data)).convert("RGBA")
    except (OSError, ValueError):
        return data
    w, h = image.size
    pixels = [((px - left) / (right - left) * w, (top - py) / (top - bottom) * h) for px, py in ring]
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).polygon(pixels, fill=255)
    if mask.getbbox() is None:
        return b""
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.paste(image, (0, 0), mask)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _bounds_of(points):
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def _clip_ring(ring, bbox):
    """닫힌 고리 하나를 네모로 자른다(서덜랜드–호지먼). 남는 것이 없으면 빈 목록."""
    west, south, east, north = bbox
    edges = [(lambda p: p[0] >= west, lambda a, b: (west, a[1] + (b[1] - a[1]) * (west - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= east, lambda a, b: (east, a[1] + (b[1] - a[1]) * (east - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= south, lambda a, b: (a[0] + (b[0] - a[0]) * (south - a[1]) / (b[1] - a[1]), south)),
             (lambda p: p[1] <= north, lambda a, b: (a[0] + (b[0] - a[0]) * (north - a[1]) / (b[1] - a[1]), north))]
    points = [tuple(p[:2]) for p in ring[:-1]] if ring and ring[0] == ring[-1] else [tuple(p[:2]) for p in ring]
    for inside, cross in edges:
        if not points:
            break
        kept = []
        for k, cur in enumerate(points):
            prev = points[k - 1]
            if inside(cur):
                if not inside(prev):
                    kept.append(cross(prev, cur))
                kept.append(cur)
            elif inside(prev):
                kept.append(cross(prev, cur))
        points = kept
    if len(points) < 3:
        return []
    return [list(p) for p in points] + [list(points[0])]


def clip_polygons(geometry: dict, bbox):
    """면(Polygon·MultiPolygon)을 네모로 자른다 — 바깥 고리가 사라지면 그 면을 버린다. 남는 것이 없으면 None."""
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    out = []
    for poly in polys:
        rings = [_clip_ring(r, bbox) for r in poly]
        if rings and rings[0]:
            out.append([rings[0]] + [r for r in rings[1:] if r])
    if not out:
        return None
    return {"type": "MultiPolygon", "coordinates": out} if len(out) > 1 else {"type": "Polygon", "coordinates": out[0]}
