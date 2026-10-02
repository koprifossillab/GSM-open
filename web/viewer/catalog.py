"""`GetCapabilities` XML 을 카탈로그 씨앗으로 바꾼다.

**사람이 문서를 보고 옮겨 적지 않는다.** 상류 안내 페이지의 레이어 목록에는
틀린 것이 있다 — 지화학도 12 종이 전부 바나듐으로 적혀 있고, 변성암·광상
동위원소는 심성암과 같은 이름이 붙어 있으며, 좋은물지도 15 종은 아예 빠져
있다. devlog 001 을 볼 것.
"""
import re
import xml.etree.ElementTree as ET

WMS_NS = "{http://www.opengis.net/wms}"

#: 오픈API 로 열린 묶음. 상류 GeoServer 는 399 개를 들고 있지만 `geoOpen` 밖은
#: 인증키로도 열리지 않는다고 보고 씨앗에 넣지 않는다.
OPEN_WORKSPACE = "geoOpen"

#: 레이어명에서 레이어군을 고른다. 위에서부터 먼저 맞는 것을 쓴다.
GROUP_RULES = [
    (r"^L_(50K|250K|1M)_Geology_Map$|^l_50k_geology_frame_latest$", "지질도"),
    (r"coalfield", "탄전지질도"),
    (r"Gravity_Raster|Magnetic_Raster", "지구물리이상도"),
    (r"^L_geochemMP_", "지화학도"),
    (r"^good_water_rgb_|^gw_loct_att$", "좋은물지도"),
    (r"^M_geology_|^Marine_geology_", "해저지질도"),
    (r"^L_1M_isotope_", "동위원소 연대지도"),
]

GROUP_ORDER = ["지질도", "탄전지질도", "지구물리이상도", "지화학도",
               "좋은물지도", "해저지질도", "동위원소 연대지도", "그 밖"]


def group_for(name: str) -> str:
    for pattern, group in GROUP_RULES:
        if re.search(pattern, name):
            return group
    return "그 밖"


def parse(xml_text: str) -> dict:
    """씨앗 하나를 만든다. `data/kigam_layers.json` 과 같은 꼴이다."""
    root = ET.fromstring(xml_text)
    layers = []
    for node in root.iter(f"{WMS_NS}Layer"):
        name_node = node.find(f"{WMS_NS}Name")
        if name_node is None or not name_node.text:
            continue                      # 이름 없는 마디는 묶음일 뿐이다
        full = name_node.text
        if not full.startswith(f"{OPEN_WORKSPACE}:"):
            continue
        short = full.split(":", 1)[1]

        title_node = node.find(f"{WMS_NS}Title")
        title = (title_node.text or "").strip() if title_node is not None else ""
        if title == short:
            title = ""                    # 제목이 없어 이름이 그대로 든 것

        abstract_node = node.find(f"{WMS_NS}Abstract")
        abstract = (abstract_node.text or "").strip() if abstract_node is not None else ""

        layers.append({
            "name": short,
            "title": title,
            "group": group_for(short),
            "abstract": abstract,
            "bbox": _bbox(node),
            "crs": [c.text for c in node.findall(f"{WMS_NS}CRS")][:6],
        })

    layers.sort(key=lambda d: (GROUP_ORDER.index(d["group"]), d["title"] or d["name"]))
    return {"레이어군순서": GROUP_ORDER, "레이어": layers}


def _bbox(node):
    box = node.find(f"{WMS_NS}EX_GeographicBoundingBox")
    if box is None:
        return None
    keys = ("westBoundLongitude", "southBoundLatitude",
            "eastBoundLongitude", "northBoundLatitude")
    values = [box.findtext(f"{WMS_NS}{k}") for k in keys]
    if not all(values):
        return None
    try:
        return [float(v) for v in values]
    except ValueError:
        return None
