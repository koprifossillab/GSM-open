"""세계 암상 — GLiM(Hartmann & Moosdorf 2012)의 0.5° 격자판을 오늘의 지구에 칠한다 (wetherilli 267). 지각 두께(`crust.py`)와 같은 꼴이다.

원본은 PANGAEA 788537 "GLiM v1.0 (gridded to 0.5° spatial resolution)" — **CC BY 3.0**, 38 KB zip 안의 ESRI ASCII 격자(720 × 360,
칸마다 그 칸에서 가장 넓은 암상 하나, 16 갈래)다. `manage.py build_glim <zip>` 이 `data/glim_05deg.json`(줄마다 720 글자, 갈래 하나가
글자 하나)로 굽는다. 저장소의 파일이라 문이 아니다.

- **0.5° 칸의 가장 넓은 암상이다** — 원본 GLiM 은 다각형 123 만 개(1:375 만 남짓)이지만 그 판은 갈래가 3 단계이고 수 GB 라 굽지 않았다.
  칸 안의 다른 암상은 보이지 않는다. 누르면 그렇게 적는다
- **오늘에만 뜬다**
- 빈 칸(`nd`, 바다)은 칠하지 않는다. 물(`wb`)·얼음(`ig`)은 칠한다 — GLiM 이 땅 위의 갈래로 둔 것이다
"""
import functools
import io
import json

from django.conf import settings

from . import paleo
from .i18n import msg, t

RENDERER = "1"
MAX_ZOOM = 5
NODATA = "."
CITE = "GLiM (Hartmann & Moosdorf 2012, G-cubed) · PANGAEA 788537 · CC BY 3.0"
#: 번호 → (부호, 이름, 색). 번호와 부호는 원본 `Classnames.txt` 그대로
CLASSES = {
    1: ("su", msg("미고결 퇴적물"), "#fff1a6"),
    2: ("vb", msg("염기성 화산암"), "#8c3a2a"),
    3: ("ss", msg("쇄설성 퇴적암"), "#e5bf68"),
    4: ("pb", msg("염기성 심성암"), "#3d6b2f"),
    5: ("sm", msg("혼합 퇴적암"), "#c9a777"),
    6: ("sc", msg("탄산염 퇴적암"), "#7fb3d5"),
    7: ("va", msg("산성 화산암"), "#e07a8a"),
    8: ("mt", msg("변성암"), "#9b7bb8"),
    9: ("pa", msg("산성 심성암"), "#e4473f"),
    10: ("vi", msg("중성 화산암"), "#c45c86"),
    11: ("wb", msg("물"), "#9ecae1"),
    12: ("py", msg("화산쇄설암"), "#f3a35b"),
    13: ("pi", msg("중성 심성암"), "#a63a5c"),
    14: ("ev", msg("증발암"), "#b8e0d2"),
    15: ("nd", msg("자료 없음"), None),
    16: ("ig", msg("빙하·만년설"), "#eef4f8"),
}


def char_of(code: int) -> str:
    return chr(ord("a") + code - 1)


def code_of(ch: str):
    return None if ch == NODATA else ord(ch) - ord("a") + 1


@functools.lru_cache(maxsize=1)
def grid():
    """`rows[북에서 j]` — 720 글자. 파일이 없으면 None."""
    try:
        with open(settings.GLIM_FILE, encoding="utf-8") as fh:
            return json.load(fh)["rows"]
    except FileNotFoundError:
        return None


def at(lon: float, lat: float):
    """누른 자리의 갈래 번호. 빈 칸이면 None."""
    rows = grid()
    if rows is None:
        return None
    j = min(359, max(0, int((90.0 - lat) * 2)))
    i = int((((lon + 180.0) % 360.0) + 360.0) % 360.0 * 2) % 720
    code = code_of(rows[j][i])
    return None if code is None or CLASSES[code][2] is None else code


def name(code: int, lang: str = "ko") -> str:
    return t(CLASSES[code][1], lang)


def legend(lang: str = "ko") -> list:
    return [{"name": t(label, lang), "color": color} for _, (_, label, color) in sorted(CLASSES.items()) if color]


def _rgb(hexa):
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))


@functools.lru_cache(maxsize=1)
def _image():
    from PIL import Image
    rows = grid()
    im = Image.new("RGBA", (720, 360), (0, 0, 0, 0))
    px = im.load()
    colours = {char_of(c): _rgb(v[2]) + (255,) for c, v in CLASSES.items() if v[2]}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in colours:
                px[i, j] = colours[ch]
    return im


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자(`crust.render_tile` 과 같다) — 칸을 가장 가까운 점으로 늘린다(갈래라 섞지 않는다)."""
    from PIL import Image
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    box = ((west + 180.0) * 2, (90.0 - north) * 2, (west + span + 180.0) * 2, (90.0 - north + span) * 2)
    tile = _image().transform((paleo.TILE, paleo.TILE), Image.Transform.EXTENT, box, Image.Resampling.NEAREST)
    buf = io.BytesIO()
    tile.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def read_ascii(text: str) -> list:
    """ESRI ASCII 격자(720 × 360, 0.5°, 왼쪽 아래 −180·−90) → 줄마다 720 글자(북→남)."""
    lines = text.splitlines()
    head = {}
    for line in lines[:6]:
        key, value = line.split()
        head[key.lower()] = value
    if (int(head["ncols"]), int(head["nrows"]), float(head["cellsize"])) != (720, 360, 0.5):
        raise ValueError(f"격자의 꼴이 다르다 — {head}")
    nodata = head.get("nodata_value", "-9999")
    rows = []
    for line in lines[6:]:
        cells = line.split()
        if not cells:
            continue
        if len(cells) != 720:
            raise ValueError(f"한 줄이 {len(cells)} 칸이다")
        rows.append("".join(NODATA if c == nodata or int(c) not in CLASSES else char_of(int(c)) for c in cells))
    if len(rows) != 360:
        raise ValueError(f"줄이 {len(rows)} 개다")
    return rows
