"""동남극 고지형 Gernon 외 2026 — 연대마다의 5 km 고도 격자를 **고도 단계로 칠해 3031 타일로 잘라 둔다** (wetherilli 436).

Gernon 외 2026(Science 392:eadz6758, doi:10.1126/science.adz6758)은 대륙이 갈라질 때의 융기가 동남극 빙상을 열었다고 본다.
그 Fig. 3A 의 고지형이 Zenodo 19205651(**CC BY 4.0**)의 GeoTIFF 34 장(`COB160BestFitModel<NNN>Ma.tif`, 100–34 Ma, 2 Myr)이다.
**FastScape 모형 재구성이지 관측이 아니다** — 34 Ma 바탕은 Paxman 외 2019 의 고지형이고, 거기서 거꾸로 셈해 올라갔다.
**좌표는 오늘의 자리다** — 판을 돌리지 않은 3031 격자라 오늘의 남극 지도 위에 그대로 얹는다.

- 원본은 3031, 한 칸 5 km, 601×601, float32 LZW(predictor 없음), 원점(왼쪽 위 모서리) x=−1 002 500 y=2 502 500, 빈 곳 NaN.
  Pillow 로 읽는다(**numpy 없이**, 컨테이너에서 `manage.py build_gernon_paleotopo <zip>`). 원본은 NAS `N:\\GSM\\sources\\antarctic_papers\\`,
  구운 것은 `GSM_GERNON_PALEOTOPO_DIR`(기본 `<DB 옆>/gernon_paleotopo`)의 연대마다 하위 폴더
- 연대는 34 장 모두(100–34 Ma, 2 Myr) 굽고 **카탈로그 레이어는 하나**(`gernontopo:paleotopo`)다 — 남극 탭의 연대 막대가 타일 주소의
  `{age}` 를 바꿔 끼운다(wetherilli 439). 연대마다의 판(`gernontopo:<연대>`)은 타일·누른 자리를 내는 속 이름으로만 남는다
- 칠하기는 PaleoDEM(`paleodem.py`)의 바다·뭍 빛을 **단계로** 끊었다 — 같은 남극 탭에서 어울리게. **1 500 m(본문의 빙모 문턱)부터는 녹슨
  빛으로 건너뛴다** — 그 위가 빙모가 앉을 수 있는 땅이라 Fig. 3A 를 읽는 열쇠다
- 타일은 줌 3(3.3 km)까지 — 원본 한 칸이 5 km 다. 누른 자리는 m 단위의 int16
"""
import io
import re
import zipfile
from array import array

from . import polargrid
from .i18n import msg

UPSTREAM = "gernontopo"
WHERE = "GERNON_PALEOTOPO_DIR"
MAX_ZOOM = 3
#: 원자료의 연대 34 장 — 옛것부터 (wetherilli 439)
AGES = tuple(range(100, 33, -2))
#: 카탈로그의 레이어 하나 — 연대는 화면의 연대 막대가 고른다
LAYER = f"{UPSTREAM}:paleotopo"
#: 3D 는 연대 막대를 따르지 않는다 — 이 연대 하나로 (wetherilli 439)
AGE_3D = 34
ATTRIBUTION = ('Gernon et al. (2026, <a href="https://doi.org/10.1126/science.adz6758" target="_blank" rel="noopener">Science</a>; '
               '<a href="https://doi.org/10.5281/zenodo.19205651" target="_blank" rel="noopener">Zenodo</a>, CC BY 4.0) — '
               '34 Ma base: Paxman et al. (2019)')
PROP = "고도 (m)"
AGE_PROP = "연대 (Ma)"
NAME = re.compile(r"COB160BestFitModel(\d{3})Ma\.tif$")
#: (윗 경계 m, 색, 범례 글) — PaleoDEM 의 SEA·LAND 빛을 단계로. 1 500 m 부터 녹슨 빛
CLASSES = (
    (-4000, "#122e5a", "< −4,000 m"),
    (-2000, "#245685", "−4,000 – −2,000 m"),
    (-1000, "#3a6f9e", "−2,000 – −1,000 m"),
    (-200, "#528cba", "−1,000 – −200 m"),
    (0, "#86bad6", "−200 – 0 m"),
    (250, "#709660", "0 – 250 m"),
    (500, "#96ac6a", "250 – 500 m"),
    (1000, "#c4b87c", "500 – 1,000 m"),
    (1500, "#d8c896", "1,000 – 1,500 m"),
    (2000, "#c0703c", "1,500 – 2,000 m"),
    (2500, "#9c4a2c", "2,000 – 2,500 m"),
    (3000, "#7a3a2e", "2,500 – 3,000 m"),
    (1e9, "#f2ece6", "≥ 3,000 m"),
)


def kind(age: int) -> str:
    return str(age)


def _set(age: int) -> polargrid.Set:
    return polargrid.Set(
        name=f"{UPSTREAM}:{kind(age)}", where=WHERE, sub=kind(age), unit="m", scale=1, max_zoom=MAX_ZOOM,
        index_of=polargrid.class_index(CLASSES), palette=polargrid.class_palette(CLASSES),
        prop=PROP, attribution=ATTRIBUTION, extra=((AGE_PROP, age),))


SETS = {f"{UPSTREAM}:{kind(age)}": _set(age) for age in AGES}
#: 카탈로그 이름으로 부르는 자리(3D 의 `warp/`)는 한 연대로 — 2D 는 `set_for` 로 연대를 고른다
SETS[LAYER] = SETS[f"{UPSTREAM}:{kind(AGE_3D)}"]


def set_for(age) -> "polargrid.Set | None":
    """연대(Ma) → 그 연대의 판. 없는 연대면 None"""
    try:
        return SETS.get(f"{UPSTREAM}:{kind(int(age))}")
    except (TypeError, ValueError):
        return None


def root() -> "Path":
    from pathlib import Path

    from django.conf import settings
    return Path(getattr(settings, WHERE))


def legend(name: str, lang: str = "ko") -> dict:
    from . import i18n
    age = name.split(":", 1)[1]
    rows = [{"code": i, "label": row[2].replace("-", "−"), "color": row[1]} for i, row in enumerate(CLASSES)]
    title = i18n.t(msg("고지형 (FastScape 모형)") if name == LAYER else msg("고지형 {age} Ma (FastScape 모형)", age=age), lang)
    return {"groups": [{"name": title, "rows": rows}], "attribution": ATTRIBUTION}


# ── 원본 읽기 ─────────────────────────────────────────────────────────

def read_tif(data: bytes) -> polargrid.Grid:
    """GeoTIFF 한 장(float32, 3031) → `Grid`. 원점·칸은 GeoTIFF 꼬리표(33922·33550)에서 읽는다 — 모서리 원점이라 반 칸 옮긴다"""
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    if image.mode != "F":
        raise polargrid.PolarGridError(f"float32 한 겹이 아니다 ({image.mode})")
    tags = image.tag_v2
    try:
        res_x, res_y = tags[33550][0], tags[33550][1]
        left, top = tags[33922][3], tags[33922][4]
    except (KeyError, IndexError) as exc:
        raise polargrid.PolarGridError("GeoTIFF 의 원점·칸 꼬리표가 없다") from exc
    if abs(res_x - res_y) > 1e-6 * res_x:
        raise polargrid.PolarGridError("가로와 세로의 칸 간격이 다르다")
    ne, nv = image.size
    values = array("f", image.tobytes("raw", "F"))
    return polargrid.Grid(ne, nv, float(res_x), left + res_x / 2, top - res_y / 2, values)


def members(zip_path) -> dict:
    """zip 안의 연대 → 파일 이름 (34 장)"""
    with zipfile.ZipFile(zip_path) as z:
        out = {}
        for n in z.namelist():
            m = NAME.search(n)
            if m and int(m.group(1)) in AGES:
                out[int(m.group(1))] = n
        return out


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": UPSTREAM, "tag": "Gernon", "title": "동남극 고지형 (Gernon 2026)"},
]
