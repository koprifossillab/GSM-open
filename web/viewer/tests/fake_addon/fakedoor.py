"""가짜 덧붙이의 문 — 제 디스크의 격자 하나를 `polargrid` 틀로 낸다."""
from viewer import polargrid

UPSTREAM = "fakeaddon"
LAYER = f"{UPSTREAM}:bed"
ATTRIBUTION = "Fake addon"
RAMP = ((-1.0, (0, 0, 255)), (1.0, (255, 0, 0)))

SETS = {LAYER: polargrid.Set(
    name=LAYER, where="ADDON_DIR", sub="fake_addon/bed", unit="m", scale=1, max_zoom=2,
    index_of=polargrid.ramp_index(lambda v: v / 1000, -1.0, 1.0),
    palette=polargrid.ramp_palette(RAMP, -1.0, 1.0), prop="가짜 바닥 높이 (m)", attribution=ATTRIBUTION)}


def legend(name: str, lang: str = "ko") -> dict:
    return {"groups": [{"name": "가짜", "rows": [{"code": 0, "label": "0 m", "color": "#000000"}]}],
            "attribution": ATTRIBUTION}


#: 점 레이어 — 이름 -> 카탈로그 행에 얹을 것. 덩이는 `points()` 가 짓는다 (wetherilli 449)
POINTS_LAYER = f"{UPSTREAM}:cores"
POINTS = {POINTS_LAYER: {"attribution": ATTRIBUTION}}


def points(name: str, lang: str = "ko", request=None):
    if name != POINTS_LAYER:
        return None
    return {"type": "FeatureCollection", "style": "class", "labels": {"name": "이름"}, "links": [],
            "legend": [{"code": 0, "label": "가짜 코어", "color": "#3366cc", "shape": "dot", "count": 1}],
            "features": [{"type": "Feature", "id": "c1", "geometry": {"type": "Point", "coordinates": [10.0, -75.0]},
                          "properties": {"name": "FAKE-GC01", "code": 0}}]}


REGISTRY = [
    {"upstream": UPSTREAM, "tag": "FAKE", "title": "Fake addon", "local": True},
]
