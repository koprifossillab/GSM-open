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


REGISTRY = [
    {"upstream": UPSTREAM, "tag": "FAKE", "title": "Fake addon", "local": True},
]
