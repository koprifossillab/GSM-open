"""남극–에이트켄(SPA) 분지 지질도의 속성 — 원본 GeoTIFF 에서 누른 자리의 단위를 읽는다 (wetherilli 081).

Iqbal 외 2026(Icarus, "Geological Mapping of the South Pole-Aitken (SPA) Basin and South Pole Region of the Moon",
1:50만)의 지도를 Trek 이 타일(`SPA_GeoMap_lqbal_et_al`)로 준다. 타일은 그림뿐이고 속성이 없다. 저자들이 Zenodo 에
CC BY 4.0 으로 둔 원본(doi:10.5281/zenodo.19728952 의 `GeoMap.tif.zip`)은 **팔레트 GeoTIFF** 라 칸의 번호가 곧 색이고,
색은 지도판 범례의 단위 색이다. 그래서 **화면은 Trek 의 타일을 그대로 쓰고, 누른 자리만 원본에서 읽는다** — 30 점을
견줘 Trek 의 타일과 단위가 다 같았다(2026-09-30).

상류가 아니라 우리 디스크의 파일이라 문이 아니다 — `requests` 가 없다. 파일은 `GSM_MOON_DIR`(달 원도와 같은 자리)에
`SOURCE_NAME` 으로 둔다. 원본은 NAS `sources/moon/`.

    원본          85 564 × 66 601 칸, 한 칸 49.4 m, 8 줄마다 LZW 로 묶은 띠(strip) 8 326 개, 112 MB
    투영          람베르트 정적 방위도법(구, R = 1 737 400 m), 가운데 남위 53°·서경 157.5°

통째로 풀면 5.7 GB 라 Pillow 로 열지 않는다. **누른 자리가 든 띠 하나(8 줄, 68 만 바이트)만 풀어** 읽는다 — TIFF 의
LZW 를 여기서 푼다(한 띠에 몇 ms).

**색 → 단위.** 원본의 256 색 가운데 단위는 28 가지다. 몇 단위는 범례 색 그대로, 몇 단위는 범례 색을 70% 남짓으로
흰 바탕에 얹은 색이다(선넥타리스기 지각·크레이터처럼 넓은 것). 그래서 팔레트의 색마다 "범례 색을 불투명도 a 로 얹은
것" 가운데 가장 가까운 단위를 고르고(`_fit`), 어긋남이 `FIT_LIMIT` 를 넘으면 단위가 아니다(경계선·글자·무늬의 번짐).
눈으로 가른 둘(`OVERRIDES`)은 따로 적었다. 누른 칸이 단위가 아니면 둘레 7×7 칸에서 가장 많은 단위를 낸다.
"""
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

from django.conf import settings

SOURCE_NAME = "spa_geomap_iqbal2026.tif"

#: 화면이 카드 밑에 적는 출처. CC BY 라 반드시 보여야 한다
ATTRIBUTION = ("Iqbal et al. 2026, Icarus (doi:10.5281/zenodo.19728952, CC BY 4.0)")

#: 람베르트 정적 방위도법의 가운데와 달 반지름 — 원본의 GeoKey(3088·3089·2057)
R = 1737400.0
LAT0 = -53.0
LON0 = -157.5

#: 지도판(Mapplate)의 범례 차례 그대로 — 젊은 것이 위다. (기호, 이름, 시대, 범례 색). 이름은 원본의 것이라 옮기지
#: 않는다. 시대는 `trek.AGES_KO` 가 옮긴다 — 두 시대에 걸친 단위는 "A–B" 로 적는다
UNITS = [
    ("Cc", "Copernican crater", "Copernican", (253, 231, 84)),
    ("Elp", "Eratosthenian light plain", "Eratosthenian", (238, 131, 159)),
    ("Edp", "Eratosthenian dark plain", "Eratosthenian", (246, 86, 86)),
    ("Ec", "Eratosthenian crater", "Eratosthenian", (147, 241, 100)),
    ("EIc", "Eratosthenian-Imbrian crater", "Eratosthenian–Imbrian", (131, 201, 166)),
    ("UIc", "Upper Imbrian crater", "Imbrian", (217, 245, 255)),
    ("UIlp", "Upper Imbrian light plain", "Imbrian", (240, 200, 245)),
    ("UIdm", "Upper Imbrian dark mantle", "Imbrian", (254, 78, 185)),
    ("UIdp", "Upper Imbrian dark plain", "Imbrian", (198, 150, 238)),
    ("Ilp", "Imbrian light plain", "Imbrian", (56, 221, 200)),
    ("IOmr", "Imbrian Orientale Montes Rook formation", "Imbrian", (134, 207, 253)),
    ("IOma", "Imbrian Orientale Maunder formation", "Imbrian", (159, 181, 230)),
    ("IOm", "Imbrian Orientale massif", "Imbrian", (126, 143, 205)),
    ("IOe", "Imbrian Orientale ejecta", "Imbrian", (212, 228, 243)),
    ("LISCHrf", "Lower Imbrian Schrödinger rough plain", "Imbrian", (0, 38, 115)),
    ("LISCHsf", "Lower Imbrian Schrödinger smooth floor", "Imbrian", (56, 110, 173)),
    ("LIrp", "Lower Imbrian rough plain", "Imbrian", (157, 201, 212)),
    ("LIc", "Lower Imbrian crater", "Imbrian", (40, 69, 181)),
    ("NIp", "Nectarian light plain", "Nectarian", (245, 208, 198)),
    ("NpNc", "Nectarian - Pre-Nectarian crater", "Nectarian–Pre-Nectarian", (176, 99, 48)),
    ("pNAPLrp", "Pre-Nectarian Apollo basin rough plains", "Pre-Nectarian", (239, 176, 134)),
    ("pNAPLrm", "Pre-Nectarian Apollo basin rim massif", "Pre-Nectarian", (127, 50, 11)),
    ("pNIG", "Pre-Nectarian Ingenii basin material", "Pre-Nectarian", (112, 82, 55)),
    ("pNSPAf", "Pre-Nectarian South Pole - Aitken basin floor", "Pre-Nectarian", (212, 197, 150)),
    ("pNSPAm", "Pre-Nectarian South Pole - Aitken basin material", "Pre-Nectarian", (183, 167, 159)),
    ("pNSPAr", "Pre-Nectarian South Pole - Aitken basin rim", "Pre-Nectarian", (123, 118, 111)),
    ("pNt", "Pre-Nectarian terra", "Pre-Nectarian", (199, 184, 170)),
]

#: 단위 위에 무늬로 얹은 지표 특징 가운데 색이 한 가지인 것 — 누르면 단위와 함께 적는다
FEATURES = {(215, 255, 210): "Slumped material", (255, 201, 131): "Floor-fractured crater"}

#: 맞춤만으로는 잘못 가는 둘 — 자리로 가렸다(2026-09-30, 원본을 성기게 훑어 중간값).
#: (193,226,255) 는 맞춤으로 IOmr 이지만 오리엔탈레 가운데에서 750 km(몬테스 루크 고리 밖)라 분출물이다 — 진짜
#: IOmr (134,207,253) 는 430 km 다. (204,188,180) 은 맞춤으로 pNt 이지만 SPA 가운데에서 1 030 km 로 분지 바닥
#: (700 km)과 테두리(1 016 km) 곁이라 SPA 물질이다 — 진짜 pNt (220,205,191) 는 1 385 km, 분지 밖이다
OVERRIDES = {(193, 226, 255): "IOe", (204, 188, 180): "pNSPAm"}

#: 팔레트 색과 "범례 색을 불투명도 a 로 흰 바탕에 얹은 색" 의 가장 큰 띠 차이가 이 밑이어야 단위다
FIT_LIMIT = 9
#: 누른 칸이 단위가 아닐 때 둘레를 볼 반폭 — 7×7 칸, 350 m 남짓
NEAR = 3


class SpaMapError(RuntimeError):
    pass


def source() -> Path:
    return Path(settings.MOON_DIR) / SOURCE_NAME


def available() -> bool:
    return source().is_file()


def _fit(rgb) -> tuple:
    """(어긋남, 기호) — 범례 색을 불투명도 0.5–1 로 흰 바탕에 얹은 것 가운데 가장 가까운 단위."""
    best = (999.0, "")
    for code, _name, _age, color in UNITS:
        for step in range(50, 101):
            a = step / 100
            err = max(abs(v - (255 - a * (255 - c))) for v, c in zip(rgb, color))
            if err < best[0]:
                best = (err, code)
    return best


@lru_cache(maxsize=2)
def _open(path: str, mtime: float) -> dict:
    """원본의 머리 — 크기·띠 자리·지오 변환·팔레트를 한 번 읽는다. 칸은 읽지 않는다."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as image:
        if image.mode != "P" or image.tag_v2.get(259) != 5:
            raise SpaMapError(f"팔레트·LZW GeoTIFF 가 아니다 ({image.mode}, 압축 {image.tag_v2.get(259)})")
        tags = image.tag_v2
        palette = image.getpalette()
        head = {
            "width": image.size[0], "height": image.size[1],
            "rows": int(tags.get(278, image.size[1])),
            "offsets": tuple(tags[273]), "counts": tuple(tags[279]),
            "origin": (float(tags[33922][3]), float(tags[33922][4])), "res": float(tags[33550][0]),
        }
    units, features = {}, {}
    for i in range(len(palette) // 3):
        rgb = tuple(palette[3 * i:3 * i + 3])
        if rgb in FEATURES:
            features[i] = FEATURES[rgb]
        elif rgb in OVERRIDES:
            units[i] = OVERRIDES[rgb]
        else:
            err, code = _fit(rgb)
            if err <= FIT_LIMIT:
                units[i] = code
    head.update(units=units, features=features)
    return head


def _head() -> dict:
    path = source()
    return _open(str(path), path.stat().st_mtime)


def lzw(data: bytes) -> bytes:
    """TIFF 의 LZW(앞 비트부터, 표가 511·1023·2047 에 닿으면 한 비트 넓힌다 — "early change")."""
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bits, pos, prev, end = 9, 0, None, len(data) * 8
    while pos + bits <= end:
        at = pos >> 3
        chunk = int.from_bytes(data[at:at + 3].ljust(3, b"\0"), "big")
        code = (chunk >> (24 - (pos & 7) - bits)) & ((1 << bits) - 1)
        pos += bits
        if code == 256:                 # 표를 비운다
            del table[258:]
            bits, prev = 9, None
            continue
        if code == 257:                 # 끝
            break
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)
        out += entry
        prev = entry
        size = len(table)
        bits = 12 if size >= 2047 else 11 if size >= 1023 else 10 if size >= 511 else 9
    return bytes(out)


def to_pixel(lon: float, lat: float, head: dict) -> tuple:
    """달 경위도 → 원본의 (열, 줄). 람베르트 정적 방위도법(구)."""
    p, p0 = math.radians(lat), math.radians(LAT0)
    dl = math.radians((lon - LON0 + 540) % 360 - 180)
    cos_c = math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(dl)
    if cos_c <= -1 + 1e-12:             # 맞은편 한 점 — 지도에 없다
        return -1, -1
    k = math.sqrt(2 / (1 + cos_c))
    x = R * k * math.cos(p) * math.sin(dl)
    y = R * k * (math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(dl))
    x0, y0 = head["origin"]
    return int((x - x0) // head["res"]), int((y0 - y) // head["res"])


def _window(head: dict, col: int, row: int, half: int) -> list:
    """(열, 줄) 둘레 (2·half+1)² 칸의 팔레트 번호 — 가운데가 맨 앞이다. 걸친 띠만 푼다."""
    width, height, rows = head["width"], head["height"], head["rows"]
    strips = {}
    with open(source(), "rb") as f:
        for r in range(max(0, row - half), min(height, row + half + 1)):
            s = r // rows
            if s not in strips:
                f.seek(head["offsets"][s])
                strips[s] = lzw(f.read(head["counts"][s]))
    out = []
    for dr, dc in [(0, 0)] + [(dr, dc) for dr in range(-half, half + 1) for dc in range(-half, half + 1) if dr or dc]:
        r, c = row + dr, col + dc
        if 0 <= r < height and 0 <= c < width:
            data = strips[r // rows]
            at = (r % rows) * width + c
            if at < len(data):
                out.append(data[at])
    return out


def identify(lon: float, lat: float) -> dict | None:
    """누른 자리의 단위 — `{"unit", "rows": [[이름, 값], …], "color"}`. 지도 밖이면 None."""
    head = _head()
    col, row = to_pixel(lon, lat, head)
    if not (0 <= col < head["width"] and 0 <= row < head["height"]):
        return None
    cells = _window(head, col, row, NEAR)
    if not cells:
        return None
    units, features = head["units"], head["features"]
    code = units.get(cells[0])
    if code is None:
        near = Counter(units[i] for i in cells if i in units).most_common(1)
        if not near:
            return None                 # 지도 밖(흰 바탕)이거나 선 한가운데
        code = near[0][0]
    unit = next(u for u in UNITS if u[0] == code)
    rows = [["단위", code], ["이름", unit[1]], ["시대", unit[2]]]
    feature = next((features[i] for i in cells[:1] + cells if i in features), None)
    if feature:
        rows.append(["지표 특징", feature])
    return {"unit": code, "rows": rows, "color": "#%02x%02x%02x" % unit[3]}


def legend() -> list:
    """범례 — 지도판의 차례(젊은 것이 위). `[{"unit", "label", "age", "color"}]`. 시대는 부르는 쪽이 옮긴다."""
    return [{"unit": code, "label": f"{name} ({code})", "age": age, "color": "#%02x%02x%02x" % color}
            for code, name, age, color in UNITS]
