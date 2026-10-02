"""대만 경제부 지질조사·광업관리중심(GSMMA)으로 나가는 문 — 대만 지질도 (wetherilli 136).

대만 레이어는 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나"). 같은 기관의 호스트 둘을 이 문 하나가 맡는다.

- **그림** — `geomap.gsmma.gov.tw` 의 MapGuide WMS. 열쇠가 없다. **EPSG:4326 만 받는다** — 3857·3826(대만 TM2)로
  물으면 `InvalidCRS` 다(2026-10-02). 그래서 화면은 4326 격자로 받아 옮겨 그린다(`map.js` 의 `taiwanSource`).
  레이어가 지층·경계·단층처럼 잘게 나뉘어 있어, 카탈로그의 레이어 하나가 상류 레이어 여럿을 엮는다(`LAYERS`).
  `GetFeatureInfo`(모두 `queryable=0`)와 `GetLegendGraphic`(559)은 주지 않는다
- **속성** — `www.geologycloud.tw` 의 지질운 API(GeoJSON). 1/5만 지층(`Stratum`)과 1/25만 지층(`Stratum25`)을 `bbox` 로
  묻는다. 누른 자리를 가운데 둔 작은 네모(약 20 m)로 묻고, 돌아온 면 가운데 그 점을 품은 것을 고른다
- 조건: 기관의 "정부 웹사이트 자료 개방 선언" — 무상·비독점으로 복제·가공·공중 전송, 상품·서비스 개발까지 허락하고
  **출처를 밝힌다**. 확인한 선언은 같은 기관의 활동단층 사이트(`fault.gsmma.gov.tw/Webservice/Opendata`)의 것이고
  지도 서버에는 따로 붙은 문구가 없다. GetCapabilities 는 `Fees=none`, `AccessConstraints=none`
- 값(지층명·암상)은 중국어 그대로 둔다. 지질시대만 옮긴다(`i18n.age_zh`)
"""
import base64
import io
import logging
import math
from types import SimpleNamespace

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('臺灣地質圖 © <a href="https://www.gsmma.gov.tw/" target="_blank" rel="noopener">'
               '經濟部地質調查及礦業管理中心</a>')


class GsmmaError(RuntimeError):
    pass


#: 카탈로그의 레이어 → 상류 레이어(아래부터 위로 겹친다)와 속성을 물을 지질운 API. `info` 가 없으면 누르지 않는다
LAYERS = {
    "gsmma:geology_50k": {"wms": ["50K_Geomap_strata", "50K_Geomap_strata_boundary", "50K_Geomap_fault",
                                  "50K_Geomap_fold"],
                          "info": "Stratum"},
    "gsmma:geology_250k": {"wms": ["250K_Geomap_strata_1974", "250K_Geomap_strata_boundary_1974",
                                   "250K_Geomap_fault_1974"],
                           "info": "Stratum25"},
    "gsmma:geology_500k": {"wms": ["500K_Geomap_strata_2000", "500K_Geomap_boundary_2000", "500K_Geomap_fault_2000",
                                   "500K_Geomap_earthquake_fault_2000"]},
    "gsmma:geology_1m": {"wms": ["1M_Geomap_strata_1986", "1M_Geomap_strata_boundary_1986"]},
    "gsmma:labels_50k": {"wms": ["50K_Geomap_lable", "50K_Geomap_fault_name", "50K_Geomap_fold_name"]},
    "gsmma:attitude_50k": {"wms": ["50K_Geomap_attitude", "50K_Geomap_dip_angle"]},
    "gsmma:active_faults": {"wms": ["25K_Geomap_fault_2021"]},
    "gsmma:tectonic_500k": {"wms": ["500K_Tectonic_map_tectonic_element_1978", "500K_Tectonic_map_fault_1978",
                                    "500K_Tectonic_map_fold_1978",
                                    "500K_Tectonic_map_extinct_or_dormant_volcano_1978"]},
    "gsmma:sheets_50k": {"wms": ["50K_Geomap_index_frame", "50K_Geomap_index_name"]},
    # ── 둘째 판 (wetherilli 141) ──
    "gsmma:fossils_50k": {"wms": ["50K_Geomap_fossil"]},
    # 5만 붕괴·붕적지(`50K_Geomap_landslide`)는 어느 축척·자리에서도 빈 그림이라 두지 않는다(2026-10-02)
    # 환경지질 — 산사태 목록·순향사면·잠재 붕괴, 토양 액상화
    "gsmma:landslide_inventory": {"wms": ["Geomap_Envi_Landslide_list_2006-2013"]},
    "gsmma:dip_slope": {"wms": ["Geomap_Envi_DipSlope_2013"], "info": "DipSlope"},
    "gsmma:dip_slope_class": {"wms": ["Geomap_Envi_DipSlopeClass_2013"]},
    "gsmma:rock_slide": {"wms": ["Geomap_Envi_RockSlide_2013"]},
    "gsmma:debris_slide": {"wms": ["Geomap_Envi_DebrisSlide_2013"]},
    "gsmma:liquefaction": {"wms": ["Geomap_Envi_Soil_liquefatcion_2021"]},
    # 지질 민감구역 — "조사·연구·분석·계획에만, 법령 업무에는 쓰지 않는다"(기관의 단서)
    "gsmma:sensitive_fault": {"wms": ["Sensitive_area_fault"]},
    "gsmma:sensitive_landslide": {"wms": ["Sensitive_area_landslide"]},
    "gsmma:sensitive_groundwater": {"wms": ["Sensitive_area_groundwater"]},
    "gsmma:sensitive_landscape": {"wms": ["Sensitive_area_landscape"]},
    # 점 — 지질운이 점을 속성째 준다
    "gsmma:hot_springs": {"wms": ["Spring_2014"], "info": "HotSpring", "point": True},
    "gsmma:boreholes": {"wms": ["Engineering_drilling"], "info": "Drill", "point": True},
    "gsmma:hydro_wells": {"wms": ["Hydrogeological_well"]},
}


def knows(name: str) -> bool:
    return name in LAYERS


def queryable(name: str) -> bool:
    return bool(LAYERS.get(name, {}).get("info"))


def _upstream_layers(value: str) -> str:
    """카탈로그 이름(쉼표로 여럿일 수 있다) → MapGuide 레이어 이름들."""
    out = []
    for name in str(value or "").split(","):
        name = name.strip()
        if name not in LAYERS:
            raise GsmmaError(f"모르는 대만 레이어: {name}")
        out.extend("WMS/" + layer for layer in LAYERS[name]["wms"])
    return ",".join(out)


def _get(url: str, params: dict, label: str):
    left = usage.paused()
    if left:
        raise GsmmaError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsmma", ok=False)
        raise GsmmaError(f"대만 {label} 에 닿지 못했다: {exc}") from exc
    log.info("GSMMA %s -> %s", r.url, r.status_code)
    usage.record("gsmma", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


MERCATOR = ("EPSG:3857", "EPSG:900913", "EPSG:102100")
R = 6378137.0


def _fetch(q: dict):
    r = _get(settings.GSMMA_WMS_URL, q, "지질도 서버")
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsmmaError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 화면(2D)은 4326 으로 묻는다 — 그대로 넘기고 레이어 이름만 바꾼다.
    3D 는 3857 로 묻는다 — 상류가 3857 을 받지 않아 `mercator_map` 이 4326 으로 받아 편다."""
    q = dict(params, service="WMS", request="GetMap", styles="")
    q["layers"] = _upstream_layers(q.get("layers"))
    srs = (q.get("crs") or q.get("srs") or "").upper()
    if srs in MERCATOR:
        return mercator_map(q)
    return _fetch(q)


def _lat(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


def mercator_map(q: dict):
    """3857 의 범위를 4326 으로 받아 3857 로 편다. 3857 의 가로는 경도에 비례하므로 **줄(위도)만 다시 고르면
    된다** — 한 줄씩 그 위도의 줄을 옮겨 붙인다. 받는 그림은 세로를 두 배로 받아 고르는 칸을 촘촘히 한다."""
    from PIL import Image

    x0, y0, x1, y1 = [float(v) for v in str(q.get("bbox", "")).split(",")]
    width, height = int(float(q.get("width", 256))), int(float(q.get("height", 256)))
    west, east = math.degrees(x0 / R), math.degrees(x1 / R)
    south, north = _lat(y0), _lat(y1)
    rows = height * 2
    src = dict(q, crs="EPSG:4326", version="1.3.0", width=width, height=rows, format="image/png",
               transparent="true", bbox=f"{south:.9f},{west:.9f},{north:.9f},{east:.9f}")
    src.pop("srs", None)
    content, _ = _fetch(src)
    image = Image.open(io.BytesIO(content)).convert("RGBA")
    out = Image.new("RGBA", (width, height))
    for j in range(height):
        lat = _lat(y1 - (j + 0.5) * (y1 - y0) / height)
        row = min(rows - 1, max(0, int((north - lat) / (north - south) * rows)))
        out.paste(image.crop((0, row, width, row + 1)), (0, j))
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=False)
    return buf.getvalue(), "image/png"


def get_legend(layer: str):
    raise GsmmaError("대만 지질도 서버는 범례를 주지 않는다")


def clicked_lonlat(params: dict):
    """WMS `GetFeatureInfo` 의 범위·크기·픽셀 → 누른 자리의 (경도, 위도). 화면은 4326 으로 묻는다 —
    1.3.0 이면 범위가 위도부터다. 3857 로 온 것도 받는다."""
    srs = (params.get("srs") or params.get("crs") or "EPSG:4326").upper()
    bbox = [float(v) for v in str(params.get("bbox", "")).split(",")]
    width, height = float(params.get("width", 256)), float(params.get("height", 256))
    i = float(params.get("i", params.get("x", width / 2)))
    j = float(params.get("j", params.get("y", height / 2)))
    if srs in ("EPSG:4326", "CRS:84"):
        if srs == "EPSG:4326" and str(params.get("version", "1.3.0")).startswith("1.3"):
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]
        return bbox[0] + (bbox[2] - bbox[0]) * i / width, bbox[3] - (bbox[3] - bbox[1]) * j / height
    x = bbox[0] + (bbox[2] - bbox[0]) * i / width
    y = bbox[3] - (bbox[3] - bbox[1]) * j / height
    r = 6378137.0
    return math.degrees(x / r), math.degrees(2 * math.atan(math.exp(y / r)) - math.pi / 2)


def _inside(lon: float, lat: float, ring) -> bool:
    """점이 고리(경위도 쌍의 목록) 안에 드나 — 반직선을 세는 셈."""
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def contains(geometry: dict, lon: float, lat: float) -> bool:
    """GeoJSON 의 면(Polygon·MultiPolygon)이 점을 품나. 구멍은 뺀다."""
    kind = (geometry or {}).get("type")
    coords = (geometry or {}).get("coordinates") or []
    polygons = [coords] if kind == "Polygon" else coords if kind == "MultiPolygon" else []
    for rings in polygons:
        rings = [[tuple(p[:2]) for p in ring] for ring in rings if ring]
        if rings and _inside(lon, lat, rings[0]) and not any(_inside(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


#: 지질운의 속성 → 팝업에 보일 이름. 여기 없는 열(지층의 도식 번호 `Code`, 순향사면을 판독한 사람)은 버린다
FRIENDLY = {"Name": "지층명", "Abbrev": "기호", "Time": "지질시대", "Note": "암상",
            # 온천(HotSpring)
            "SpaName": "온천명", "Type": "수질", "Temperature": "수온 (°C)", "SpaPH": "pH",
            # 공학 지질 시추(Drill)
            "Project_Name": "조사 사업", "Hole_Point_No": "공번", "Depth": "심도 (m)",
            # 순향사면(DipSlope)
            "MAP_NAME": "도폭", "SLOPE_DIR": "사면 방향", "COUN_NAME": "시·현"}


def pixel_degrees(params: dict) -> float:
    """`GetFeatureInfo` 범위에서 한 픽셀이 몇 도인가(가로). 3857 이면 미터를 도로."""
    try:
        bbox = [float(v) for v in str(params.get("bbox", "")).split(",")]
        width = float(params.get("width", 256))
    except ValueError:
        return 0.0
    srs = (params.get("srs") or params.get("crs") or "EPSG:4326").upper()
    if srs == "EPSG:4326" and str(params.get("version", "1.3.0")).startswith("1.3"):
        span = bbox[3] - bbox[1]
    elif srs in ("EPSG:4326", "CRS:84"):
        span = bbox[2] - bbox[0]
    else:
        span = math.degrees((bbox[2] - bbox[0]) / 6378137.0)
    return abs(span) / width


def get_feature_info(params: dict) -> dict:
    """누른 자리의 지층 — 지질운 API 에 약 20 m 네모로 묻고, 그 점을 품은 면만 남긴다(없으면 네모에 걸린 것)."""
    layer = (params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
    api = LAYERS.get(layer, {}).get("info")
    if not api:
        return {"features": []}
    lon, lat = clicked_lonlat(params)
    point = LAYERS[layer].get("point")
    # 면은 누른 자리 둘레 약 20 m, 점은 화면의 8 픽셀(점 기호가 그만하다)
    half = max(pixel_degrees(params) * 8, 0.0001) if point else 0.0001
    r = _get(f"{settings.GSMMA_API_URL}/{api}",
             {"bbox": f"{lon - half:.6f},{lat - half:.6f},{lon + half:.6f},{lat + half:.6f}"}, "지질운")
    if r.status_code != 200:
        raise GsmmaError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        found = r.json().get("features") or []
    except ValueError as exc:
        raise GsmmaError("지질운이 JSON 이 아닌 것을 주었다") from exc
    if point:
        # 가까운 점부터 셋 — 시추공은 한 자리에 여럿이 겹친다
        def far(f):
            x, y = ((f.get("geometry") or {}).get("coordinates") or [lon, lat])[:2]
            return (x - lon) ** 2 + (y - lat) ** 2
        chosen = sorted(found, key=far)[:3]
    else:
        inside = [f for f in found if contains(f.get("geometry"), lon, lat)]
        chosen = inside or found
    features = []
    for n, feature in enumerate(chosen):
        props = {key: str(value).strip() for key, value in (feature.get("properties") or {}).items()
                 if key in FRIENDLY and value not in (None, "")}
        if "SLOPE_DIR" in props:
            props["SLOPE_DIR"] = props["SLOPE_DIR"].lstrip("ABCDEFGH")     # `B東南` — 앞의 글자는 칸 번호다
        features.append({"id": f"gsmma.{api}.{n}", "properties": props})
    return {"features": features}


def friendly(props: dict, lang: str = "ko") -> dict:
    """지질운의 열 이름 → 팝업 이름. 지질시대는 중국어에서 옮긴다(영어판은 영어로)."""
    out = {}
    for key, value in props.items():
        if key == "Time":
            value = i18n.age_zh(value, lang)
        out[FRIENDLY.get(key, key)] = value
    return out


#: `views._Door` 가 쓰는 꼴
DOOR = SimpleNamespace(get_map=get_map, get_feature_info=get_feature_info, get_legend=get_legend)


# ── 범례 — 보는 범위의 지층을 그림에서 떠 온다 (wetherilli 142) ─────────────
#
# WMS 의 `GetLegendGraphic` 은 559, MapGuide 의 `GETLEGENDIMAGE` 는 401 이다. 지질운의 지층 자료에는 색이 없다.
# 그래서 **보는 범위의 지층 면(지질운)과 같은 범위의 지층 그림(WMS)을 맞대어** 면마다 안쪽 한 점의 그림 조각을 뜬다.
# 무늬(빗금·점)가 있는 지층이 많아 색 한 칸이 아니라 조각(16 픽셀)을 견본으로 준다. 일본(GSJ)처럼 화면이 HTML 로 그린다.

#: 범례를 주는 레이어 → 지질운 자료, 칠한 면만 그린 상류 레이어, 범례를 물을 수 있는 가장 넓은 범위(도)
LEGENDS = {
    "gsmma:geology_50k": {"api": "Stratum", "wms": "50K_Geomap_strata", "span": 0.6},
    "gsmma:geology_250k": {"api": "Stratum25", "wms": "250K_Geomap_strata_1974", "span": 4.0},
}
LEGEND_PIXELS = 1024          # 범위 그림의 긴 변
SWATCH = 16                   # 견본 조각의 한 변
MAX_LEGEND = 60


def inner_points(geometry: dict, lines: int = 7):
    """면 안의 점들 — 가장 큰 고리를 세로로 고르게 가로지르는 줄마다, 가장 긴 안쪽 구간의 가운데. 면이 오목해도 안에 든다."""
    kind = (geometry or {}).get("type")
    coords = (geometry or {}).get("coordinates") or []
    polygons = [coords] if kind == "Polygon" else coords if kind == "MultiPolygon" else []
    best, best_area = None, -1.0
    for rings in polygons:
        if not rings or len(rings[0]) < 3:
            continue
        xs, ys = [p[0] for p in rings[0]], [p[1] for p in rings[0]]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best, best_area = rings, area
    if best is None:
        return []
    ring = [tuple(p[:2]) for p in best[0]]
    low, high = min(p[1] for p in ring), max(p[1] for p in ring)
    points = []
    # 가운데 줄부터 바깥으로 — 가운데가 가장 넉넉할 때가 많다
    order = sorted(range(1, lines + 1), key=lambda k: abs(k - (lines + 1) / 2))
    for k in order:
        y = low + (high - low) * k / (lines + 1)
        cuts = sorted(x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                      for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]) if (y1 > y) != (y2 > y))
        spans = [(cuts[i], cuts[i + 1]) for i in range(0, len(cuts) - 1, 2)]
        if spans:
            a, b = max(spans, key=lambda s: s[1] - s[0])
            points.append(((a + b) / 2, y))
    return points


def extent_legend(name: str, bbox) -> list:
    """보는 범위(서, 남, 동, 북)에 든 지층 — [{swatch, color, symbol, name, time, note}], 많이 나온 차례."""
    from PIL import Image

    spec = LEGENDS[name]
    west, south, east, north = bbox
    if east - west > spec["span"] or north - south > spec["span"]:
        raise LegendTooWide(spec["span"])
    r = _get(f"{settings.GSMMA_API_URL}/{spec['api']}",
             {"bbox": f"{west:.4f},{south:.4f},{east:.4f},{north:.4f}", "all": "true"}, "지질운")
    if r.status_code != 200:
        raise GsmmaError(f"지층을 받지 못했다 (status={r.status_code})")
    try:
        polygons = r.json().get("features") or []
    except ValueError as exc:
        raise GsmmaError("지질운이 JSON 이 아닌 것을 주었다") from exc
    # 그림 — 가로·세로를 범위의 비에 맞춘다(4326 그대로, 위도에 따른 늘임은 견본에 상관없다)
    ratio = (north - south) / (east - west)
    width = LEGEND_PIXELS if ratio <= 1 else max(64, int(LEGEND_PIXELS / ratio))
    height = max(64, int(width * ratio))
    content, _ = _fetch({"service": "WMS", "request": "GetMap", "version": "1.3.0", "layers": "WMS/" + spec["wms"],
                         "styles": "", "crs": "EPSG:4326", "bbox": f"{south},{west},{north},{east}",
                         "width": width, "height": height, "format": "image/png", "transparent": "true"})
    image = Image.open(io.BytesIO(content)).convert("RGBA")
    units = {}
    half = SWATCH // 2
    dx, dy = (east - west) / width * half, (north - south) / height * half

    def cut(point, h=half):
        px = int((point[0] - west) / (east - west) * width)
        py = int((north - point[1]) / (north - south) * height)
        if not (h <= px < width - h and h <= py < height - h):
            return None
        crop = image.crop((px - h, py - h, px + h, py + h))
        colors = [c for c in crop.getdata() if c[3] > 0]
        if len(colors) < (2 * h) ** 2 // 2:         # 반 넘게 비었다 — 경계·구멍에 걸렸다
            return None
        if h != half:
            crop = crop.resize((SWATCH, SWATCH), Image.NEAREST)
        return crop, max(set(colors), key=colors.count)

    for feature in polygons:
        props = feature.get("properties") or {}
        label = (str(props.get("Abbrev") or "").strip(), str(props.get("Name") or "").strip(),
                 str(props.get("Time") or "").strip())
        if not label[1]:
            continue
        unit = units.setdefault(label, {"count": 0, "swatch": None, "fits": False,
                                        "note": str(props.get("Note") or "").strip()})
        unit["count"] += 1
        if unit["fits"]:
            continue
        geometry = feature.get("geometry")
        for point in inner_points(geometry):
            # 조각의 네 귀퉁이가 모두 이 면 안이면 옆 지층이 섞이지 않는다. 안 들어맞으면 작은 조각(6 픽셀)을
            # 떠서 키운다 — 무늬는 굵어지지만 옆 지층이 덜 섞인다. 들어맞는 면이 뒤에 오면 그것으로 바꾼다
            corners = [(point[0] + sx * dx, point[1] + sy * dy) for sx in (-1, 1) for sy in (-1, 1)]
            fits = all(contains(geometry, x, y) for x, y in corners)
            if not fits and unit["swatch"]:
                continue                              # 섞인 견본은 이미 있다 — 들어맞는 자리만 찾는다
            got = cut(point) if fits else cut(point, 3)
            if not got:
                continue
            crop, common = got
            buf = io.BytesIO()
            crop.save(buf, "PNG")
            unit["swatch"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            unit["color"] = "#%02x%02x%02x" % common[:3]
            unit["fits"] = fits
            if fits:
                break
    rows = [{"symbol": k[0], "name": k[1], "time": k[2], "note": v["note"], "swatch": v["swatch"],
             "color": v.get("color", "#cccccc"), "count": v["count"]}
            for k, v in units.items() if v["swatch"]]
    rows.sort(key=lambda row: -row["count"])
    return rows


class LegendTooWide(GsmmaError):
    def __init__(self, span):
        super().__init__(f"범위가 넓다 — {span}° 안으로 들어오면 범례가 뜬다")
        self.span = span


def legend_row(row: dict, lang: str = "ko") -> dict:
    """화면이 그리는 한 칸 — 일본(GSJ)의 칸과 같은 이름에 견본 조각을 더했다."""
    return {"color": row["color"], "swatch": row["swatch"], "symbol": row["symbol"],
            "lithology": row["name"] + (f" ({row['note']})" if row.get("note") else ""),
            "age": i18n.age_zh(row["time"], lang) if row.get("time") else ""}
