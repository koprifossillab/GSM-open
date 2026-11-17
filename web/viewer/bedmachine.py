"""그린란드 BedMachine v7 — 빙저·해저 지형·얼음 두께·얼음 윗면을 **우리가 칠해 3413 타일로 잘라 둔다** (wetherilli 459).

BedMachine Greenland(Morlighem 외, NSIDC `IDBMG4` v7, 2025)는 얼음 두께를 질량 보존으로 메워 빙저 지형을 이은 150 m 격자다 — 빠른
출구 빙하의 골이 레이더 선 사이에서 끊기지 않는다. 남극 탭의 Bedmap3(`bas.py`, wetherilli 261)의 짝으로 그린란드 탭에 둔다.
**NASA Earthdata 로그인 뒤에 있다** — 받기는 사람이 받아 온 토큰(`<DB 옆>/earthdata_token`)으로 한 번, 원본(NetCDF-4, 2.8 GB)은
NAS `N:\\GSM\\sources\\greenland\\bedmachine\\`, 구운 것은 `GSM_BEDMACHINE_DIR`(기본 `<DB 옆>/bedmachine`). 조건은 NASA 지구과학
자료 정책(열린 자료) — 인용을 바란다.

- **세 판을 낸다** — 바닥(`bed`, 바다는 해저), 얼음 두께(`thickness`, 얼음이 앉은 곳만 — `mask` 2·3), 얼음 윗면(`surface`, 바다 빼고).
  누르면 셋을 함께 낸다(`Set.along`). 오차(`errbed`)·자료 출처(`source`)는 지질을 읽는 화면에 둘 까닭이 아직 없다
- 고도는 **지오이드(EIGEN-6C4) 기준**이다 — 원본이 그렇게 적는다. 마스크는 0 바다·1 얼음 없는 땅·2 땅에 앉은 얼음·3 빙붕
- 원본은 3413(WGS84·표준위도 70°N·중앙 경선 45°W), 10 218×18 346 칸, y 는 북에서 남으로. **두 칸에 하나를 골라 300 m 로 굽는다** — 150 m 원판을 다
  담으면 판마다 1 억 8 천만 칸이라 순수 파이썬 칠하기(`polargrid.bake`)가 몇 분·몇 GB 를 쓴다. 타일은 줌 5(256 m)까지
- 격자는 ITS_LIVE 그린란드 판(wetherilli 433)과 같은 GIBS 극지 격자다(`polargrid.TILINGS["3413"]`) — 유속과 켜서 칸이 맞는다
- 칠하기 — 바닥·윗면은 같은 고도 색(바다는 파랑, 뭍은 초록에서 갈색·흰빛), 두께는 흰빛에서 짙은 남색
- **바닥 열 상태**(MacGregor 외 2022, GBaTS v2 — NSIDC `RDBTS4` v2, 5 km)도 같은 레이어군에 둔다 — 빙상 바닥이 언 곳·녹은 곳·모르는 곳.
  레이더 층·시추공·모형·유속을 견준 **종합 판단**이지 측정이 아니다. 누르면 바닥 고도·두께가 함께 나온다
- **굽기만 호스트에서** h5py·numpy 로 읽는다(`/srv/GSM/scripts/run.sh build_bedmachine …`, AntGG 와 같다) — 제품은 구운 것만 읽는다
"""
from array import array

from . import polargrid
from .i18n import msg

UPSTREAM = "bedmachine"
WHERE = "BEDMACHINE_DIR"
FILE = "BedMachineGreenland-v7.nc"
VERSION = "v7"
MAX_ZOOM = 5                     # 256 m — 300 m 로 고른 격자보다 곱게 자르지 않는다
STRIDE = 2                       # 150 m 원판에서 두 칸에 하나
ATTRIBUTION = ('BedMachine Greenland v7 (Morlighem et al., <a href="https://doi.org/10.5067/7U2049INNRMP" target="_blank" '
               'rel="noopener">NSIDC IDBMG4</a>)')
#: 고도 색 — (m, RGB). 바다·해수면 밑의 바닥은 파랑, 뭍은 초록에서 갈색, 높은 곳은 흰빛
ELEVATION = (
    (-3000, (18, 46, 90)), (-1000, (58, 111, 158)), (-200, (110, 166, 207)), (0, (184, 219, 232)),
    (1, (112, 150, 96)), (500, (196, 184, 124)), (1000, (176, 122, 74)), (2000, (122, 58, 46)), (3000, (242, 236, 230)),
)
THICKNESS = ((0, (240, 246, 250)), (1000, (150, 196, 226)), (2000, (60, 110, 180)), (3400, (30, 30, 100)))
#: 판 → (변수, 색 고리, 아래 끝, 위 끝, 범례 이름, 누른 자리 속성, 범례 칸의 경계)
KINDS = {
    "bed": ("bed", ELEVATION, -3000, 3000, msg("빙저·해저 지형"), "바닥 고도 (m)",
            (-3000, -1000, -500, -200, 0, 500, 1000, 1500, 2000, 3000)),
    "thickness": ("thickness", THICKNESS, 0, 3400, msg("얼음 두께"), "얼음 두께 (m)",
                  (0, 500, 1000, 1500, 2000, 2500, 3000, 3400)),
    "surface": ("surface", ELEVATION, -3000, 3000, msg("얼음·땅 윗면"), "윗면 고도 (m)",
                (0, 500, 1000, 1500, 2000, 2500, 3000)),
}


def name(kind: str) -> str:
    return f"{UPSTREAM}:{kind}"


def _set(kind: str) -> polargrid.Set:
    _, ramp, lo, hi, _, prop, _ = KINDS[kind]
    return polargrid.Set(
        name=name(kind), where=WHERE, sub=kind, unit="m", scale=1, max_zoom=MAX_ZOOM,
        index_of=polargrid.ramp_index(lambda v: v, lo, hi), palette=polargrid.ramp_palette(ramp, lo, hi),
        prop=prop, attribution=ATTRIBUTION, epsg="3413",
        along=tuple(name(k) for k in KINDS if k != kind))


SETS = {name(kind): _set(kind) for kind in KINDS}

#: 바닥 열 상태 GBaTS v2 (RDBTS4) — 값 −1·0·1 의 갈래 (wetherilli 461)
THERMAL = name("thermal")
THERMAL_FILE = "RDBTS4_Greenland_1993_2017_02_basal_thermal_state.nc"
THERMAL_ATTRIBUTION = ('Basal thermal state GBaTS v2 (MacGregor et al. 2022, <a href="https://doi.org/10.5067/RQO5Q6F6E6LY" '
                       'target="_blank" rel="noopener">NSIDC RDBTS4</a>)')
#: (윗 경계, 색, 범례 글) — `polargrid.class_index` 의 꼴
THERMAL_CLASSES = ((-0.5, "#4575b4", msg("언 바닥일 가능성이 크다")),
                   (0.5, "#cfcfcf", msg("판단이 갈린다")),
                   (1e9, "#d73027", msg("녹은 바닥일 가능성이 크다")))
SETS[THERMAL] = polargrid.Set(
    name=THERMAL, where=WHERE, sub="thermal", unit="", scale=1, max_zoom=1,
    index_of=polargrid.class_index(THERMAL_CLASSES), palette=polargrid.class_palette(THERMAL_CLASSES),
    prop="바닥 열 상태", attribution=THERMAL_ATTRIBUTION, epsg="3413", along=(name("bed"), name("thickness")),
    words=tuple((v, text) for v, (_, _, text) in zip((-1, 0, 1), THERMAL_CLASSES)))


def legend(layer: str, lang: str = "ko") -> dict:
    from . import i18n
    if layer == THERMAL:
        rows = [{"code": i, "label": i18n.t(text, lang), "color": color} for i, (_, color, text) in enumerate(THERMAL_CLASSES)]
        return {"groups": [{"name": i18n.t(msg("바닥 열 상태"), lang), "rows": rows}], "attribution": THERMAL_ATTRIBUTION}
    kind = layer.split(":", 1)[1]
    _, ramp, lo, hi, label, _, edges = KINDS[kind]
    rows = []
    for i, (a, z) in enumerate(zip(edges, edges[1:])):
        r, g, b = polargrid.ramp_color((a + z) / 2, ramp)
        rows.append({"code": i, "label": f"{a:,} – {z:,} m".replace("-", "−"),
                     "color": f"#{r:02x}{g:02x}{b:02x}"})
    return {"groups": [{"name": i18n.t(label, lang), "rows": rows}], "attribution": ATTRIBUTION}


# ── 굽기 — 호스트에서만 (h5py·numpy) ──────────────────────────────────

def read_nc(path, kind: str, stride: int = STRIDE) -> polargrid.Grid:
    """BedMachine NetCDF-4 → 판 하나의 `Grid`(위에서 아래로, 빈 곳 NaN). 두께는 얼음 위만, 윗면은 바다 빼고"""
    import h5py
    import numpy as np
    variable = KINDS[kind][0]
    with h5py.File(path, "r") as h:
        for need in ("x", "y", "mask", variable):
            if need not in h:
                raise polargrid.PolarGridError(f"{path} 에 {need} 가 없다")
        xs, ys = h["x"][::stride].astype("float64"), h["y"][::stride].astype("float64")
        data = h[variable][::stride, ::stride].astype("float32")
        mask = h["mask"][::stride, ::stride]
        fill = h[variable].attrs.get("_FillValue")
    if data.shape != (len(ys), len(xs)):
        raise polargrid.PolarGridError(f"{variable} 의 꼴 {data.shape} 이 (y, x) 가 아니다")
    if fill is not None:
        data[data == np.float32(np.asarray(fill).ravel()[0])] = np.nan
    if kind == "thickness":
        data[(mask != 2) & (mask != 3)] = np.nan          # 2 얼음(땅에 앉은), 3 빙붕
    elif kind == "surface":
        data[mask == 0] = np.nan                            # 0 바다
    return _grid(xs, ys, data)


def read_thermal(path) -> polargrid.Grid:
    """GBaTS v2 → `Grid` — `likely_basal_thermal_state`(−1 언 바닥, 0 갈린다, 1 녹은 바닥), 5 km"""
    import h5py
    with h5py.File(path, "r") as h:
        for need in ("x", "y", "likely_basal_thermal_state"):
            if need not in h:
                raise polargrid.PolarGridError(f"{path} 에 {need} 가 없다")
        xs, ys = h["x"][:].astype("float64"), h["y"][:].astype("float64")
        data = h["likely_basal_thermal_state"][:].astype("float32")
    if data.shape != (len(ys), len(xs)):
        raise polargrid.PolarGridError(f"바닥 열 상태의 꼴 {data.shape} 이 (y, x) 가 아니다")
    return _grid(xs, ys, data)


def _grid(xs, ys, data) -> polargrid.Grid:
    """(y, x) 배열 → 위에서 아래로, 왼쪽에서 오른쪽으로 놓인 `Grid`"""
    import numpy as np
    if ys[0] < ys[-1]:
        data, ys = data[::-1], ys[::-1]
    if xs[0] > xs[-1]:
        data, xs = data[:, ::-1], xs[::-1]
    res = float(xs[1] - xs[0])
    if abs(float(ys[0] - ys[1]) - res) > 1e-6 * res:
        raise polargrid.PolarGridError("가로와 세로의 칸 간격이 다르다")
    values = array("f")
    values.frombytes(np.ascontiguousarray(data, dtype="<f4").tobytes())
    return polargrid.Grid(len(xs), len(ys), res, float(xs[0]), float(ys[0]), values)


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": UPSTREAM, "tag": "BedMachine", "title": "BedMachine Greenland"},
]
