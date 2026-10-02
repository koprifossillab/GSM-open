"""최근 빙기의 빙상 가장자리 — NADI-1(북미)·DATED-1(유라시아) (wetherilli P07 §3·104).

저장소의 `data/ice_margins.json`(`manage.py build_ice_margins`)을 읽는다. 문이 아니다.

- 연대 25–1 ka 에 뜬다. 1 Ma 안쪽이라 **오늘의 지구 위에** 그린다 — 대륙은 그대로다(시간 축의 갈림, 091)
- 북미는 500 년마다(NADI-1 최적), 유라시아는 천 년마다(DATED-1 가장 믿을 만한 것, 25–10 ka). 둘 다 **가장 가까운 조각을 반 조각
  간격 안에서만** 쓴다 — 사이를 메우지 않는다. 유라시아는 10 ka 보다 젊은 조각이 없다
- 연대 측정을 모아 그린 복원이다. 두 묶음은 최소·최대 가장자리도 주지만 한 선만 그린다 — 그 폭은 devlog 104 에 적었다
"""
import functools
import io
import json

from django.conf import settings

from . import paleo

RENDERER = "1"
STEP = {"nadi": 0.5, "dated": 1.0}      # ka — 조각 간격. 그 반 안에서만 쓴다
FILL = (235, 245, 255, 190)
EDGE = (120, 200, 255, 255)
CREDIT = "NADI-1 (Dalton et al. 2023, CC BY 4.0) · DATED-1 (Hughes et al. 2016, CC BY 3.0)"


@functools.lru_cache(maxsize=1)
def data():
    try:
        with open(settings.ICE_MARGINS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def stops() -> dict:
    """묶음마다 조각의 연대(ka) — 화면의 띠·캡션이 쓴다."""
    d = data() or {}
    return {k: sorted(float(a) for a in d.get(k, {})) for k in ("nadi", "dated")}


def pick(ka: float) -> dict:
    """그 연대에 쓸 조각 — `{"nadi": 20.0, "dated": 20.0}`, 없는 묶음은 빠진다."""
    out = {}
    for key, ages in stops().items():
        best = min(ages, key=lambda a: abs(a - ka), default=None)
        if best is not None and abs(best - ka) <= STEP[key] / 2 + 1e-9:
            out[key] = best
    return out


def render_tile(ka: float, z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장 — 얼음을 옅게 칠하고 가장자리를 밝게 긋는다."""
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = paleo.TILE * k
    scale = size / span
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    d = data() or {}
    lines = []
    for key, at in pick(ka).items():
        piece = d[key][f"{at:g}"]
        for fill, rings in ((FILL, piece["ice"]), ((0, 0, 0, 0), piece["holes"])):
            for flat in rings:
                xs, ys = flat[0::2], flat[1::2]
                if max(xs) < west or min(xs) > west + span or max(ys) < north - span or min(ys) > north:
                    continue
                pts = [((flat[i] - west) * scale, (north - flat[i + 1]) * scale) for i in range(0, len(flat), 2)]
                draw.polygon(pts, fill=fill)
                lines.append(pts + pts[:1])
    for pts in lines:
        draw.line(pts, fill=EDGE, width=2 * k)
    buf = io.BytesIO()
    image.resize((paleo.TILE, paleo.TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()
