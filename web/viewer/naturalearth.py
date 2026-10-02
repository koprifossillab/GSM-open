"""온 지구의 지명·강·호수·빙하 — Natural Earth 10 m (wetherilli P07 §3·102).

저장소의 `data/earth_places.json`·`earth_water.json`·`earth_ice.json`(`manage.py build_natural_earth <폴더>`, 퍼블릭 도메인)을
읽는다. 문이 아니다.

- **지명 찾기** — 온 지구 화면의 첫 찾기다. 도시·산맥·바다·호수·강 1 만여 이름을 영어·한국어 이름으로 찾는다
  (`arcpoints.fold`·`match_index` 를 빌린다 — 지역 탭의 지명 찾기와 같은 차례, 096)
- **이름표** — 산맥·고원·사막 따위와 바다의 이름. 화면이 순위(scalerank)로 멀리서는 큰 것만 띄운다
- **강·호수**와 **빙하·빙붕**은 서버가 경위도 타일로 그린다(판 조각과 같은 격자). 강은 줌마다 순위로 거른다
- 오늘의 것이다 — 1 Ma 부터는 뜨지 않는다
"""
import functools
import io
import json

from django.conf import settings

from . import arcpoints, paleo

RENDERER = "1"
MAX_ZOOM = 7
STYLES = ("water", "ice")
CREDIT = "Natural Earth 10 m (public domain)"
RIVER = (74, 163, 223, 235)
LAKE = (74, 163, 223, 210)
ICE = (236, 246, 255, 215)
SHELF = (205, 228, 250, 215)
#: 이름표로 띄우는 갈래 — 도시는 찾기만 한다(온 지구 화면은 지질을 보는 자리다)
LABEL_KINDS = {"Range/mtn", "Plateau", "Desert", "Basin", "Plain", "Peninsula", "Pen/cape", "Tundra", "Lowland",
               "Depression", "Valley", "Gorge", "Delta", "Wetlands", "Geoarea", "Foothills", "Isthmus",
               "ocean", "sea", "gulf", "bay", "strait", "channel", "sound", "inlet", "lagoon", "fjord", "reef"}
#: 찾기 결과의 곁말 — 갈래를 사람의 말로
KIND_KO = {"city": "도시", "river": "강", "lake": "호수", "Range/mtn": "산맥", "Plateau": "고원", "Desert": "사막",
           "Island": "섬", "Island group": "제도", "Peninsula": "반도", "Pen/cape": "곶", "Basin": "분지",
           "Plain": "평야", "ocean": "대양", "sea": "바다", "gulf": "만", "bay": "만", "strait": "해협",
           "channel": "해협", "Valley": "골짜기", "Delta": "삼각주"}


@functools.lru_cache(maxsize=4)
def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def places() -> list:
    data = _load(str(settings.EARTH_PLACES_FILE))
    return data["places"] if data else []


@functools.lru_cache(maxsize=2)
def _index(lang: str) -> list:
    """찾기 색인 — 보이는 이름은 그 말의 것(한국어판은 한국어 이름이 먼저), 다른 말의 이름으로도 찾는다.
    같은 이름이면 큰 것(순위가 작은 것)이 먼저다."""
    feats = []
    for name, ko, kind, lon, lat, rank in places():
        names = {"a": ko or name, "b": name} if lang == "ko" else {"a": name, "b": ko}
        side = KIND_KO.get(kind, kind) if lang == "ko" else kind.replace("Range/mtn", "Range").lower()
        feats.append({"properties": {**names, "side": side, "rank": "0" if rank <= 3 else "1"},
                      "geometry": {"coordinates": [lon, lat]}})
    return arcpoints.name_index(feats, names=("a", "b"), sub=("side",), prefer=("rank", {"0"}))


def search(query: str, lang: str = "ko", limit: int = 20) -> list:
    out = arcpoints.match_index(_index(lang), query, limit)
    for hit in out:
        hit["kind"] = hit.pop("sub") or ""
    return out


def labels(lang: str = "ko") -> list:
    """이름표 — `[이름, 경도, 위도, 순위]`, 큰 것부터."""
    rows = [[(ko or name) if lang == "ko" else name, lon, lat, rank]
            for name, ko, kind, lon, lat, rank in places() if kind in LABEL_KINDS]
    return sorted(rows, key=lambda r: r[3])


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def _river_rank(z: int) -> int:
    """이 줌에서 긋는 강의 순위 끝 — 멀리서는 큰 강만."""
    return {0: 2, 1: 4, 2: 6, 3: 8}.get(z, 12)


def render_tile(style: str, z: int, x: int, y: int) -> bytes:
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def pts(flat, shift):
        return [((flat[i] + shift - west) * scale, (north - flat[i + 1]) * scale) for i in range(0, len(flat), 2)]

    def shifts(flat):
        xs = flat[0::2]
        lo, hi = min(xs), max(xs)
        ys = flat[1::2]
        if max(ys) < north - span - 0.1 or min(ys) > north + 0.1:
            return []
        return [s for s in (-360.0, 0.0, 360.0) if not (hi + s < west or lo + s > west + span)]

    if style == "water":
        data = _load(str(settings.EARTH_WATER_FILE)) or {}
        top = _river_rank(z)
        for rank, flat in data.get("lakes", []):
            if rank <= top + 2:
                for s in shifts(flat):
                    draw.polygon(pts(flat, s), fill=LAKE)
        for rank, flat in data.get("islands", []):
            if rank <= top + 2:
                for s in shifts(flat):
                    draw.polygon(pts(flat, s), fill=(0, 0, 0, 0))
        for rank, flat in data.get("lines", []):
            if rank <= top:
                width = max(1, round((1.5 - 0.08 * rank + 0.2 * min(z, 6)) * k))
                for s in shifts(flat):
                    draw.line(pts(flat, s), fill=RIVER, width=width, joint="curve")
    else:
        data = _load(str(settings.EARTH_ICE_FILE)) or {}
        for kind, flat in data.get("polys", []):
            for s in shifts(flat):
                # 테두리는 긋지 않는다 — 원본이 큰 빙상을 여러 면으로 나눠, 테두리가 빙상 한가운데를 가로지른다
                draw.polygon(pts(flat, s), fill=SHELF if kind else ICE)
        for kind, flat in data.get("holes", []):
            for s in shifts(flat):
                draw.polygon(pts(flat, s), fill=(0, 0, 0, 0))
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()
