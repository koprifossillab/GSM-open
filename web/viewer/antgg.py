"""남극 중력 AntGG2021 — 5 km 격자를 **우리가 칠해 3031 타일로 잘라 둔다** (wetherilli 431).

AntGG2021(Scheinert·Zingerle·Schaller·Pail 2024, PANGAEA 971238, **CC BY 4.0**)은 IAG AntGG 가 모은 지상·항공 중력을 최소제곱
배치법(PE-LSC)으로 이은 5 km 격자다. ADMAP-2 자력(`admap.py`, wetherilli 262)의 짝으로 남극 탭의 지구물리에 둔다. 서비스가 없고
파일 여덟(각 27 MB)뿐이라 받아 굽는다. 원본은 NAS `N:\\GSM\\sources\\antgg2021\\`, 구운 것은 `GSM_ANTGG_DIR`(기본 `<DB 옆>/antgg`).

- **두 판만 낸다** — 지표의 중력 이상(자유공기, `grav_anom`)과 부게 이상(`Boug_anom`). 나머지 여섯(중력 교란 둘·높이 이상 둘·
  2 차 미분·표준편차)은 측지 쪽 쓰임이라 지질을 읽는 화면에 둘 까닭이 없었다
- 원본은 NetCDF-4(HDF5) — 1 333×1 333 칸, 3031(WGS84·표준위도 −71°), y 는 남에서 북으로, 빈 곳은 NaN. **머리는 변수를 (x, y) 라
  적었지만 값은 (y, x) 차례다** — 딸린 표면 고도(`h_ell`)로 대어 보니 (y, x) 로 읽어야 돔 A 가 4 090 m, 보스토크가 3 478 m 다
  **굽기만 호스트에서** h5py 로 읽는다(`/srv/GSM/scripts/run.sh build_antgg …`, PaleoDEM 과 같다) — 제품은 구운 것만 읽는다
- 칠하기는 온 세계 부게(`gravmag.py`, wetherilli 391)와 같은 파랑–흰–빨강. 끝은 부게 ±500 mGal, 프리에어 ±150 — 그쪽의 ±300 이면
  동남극이 −300 아래(남극점 −426, 보스토크 −438)라 대륙이 한 색으로 묻힌다. 프리에어는
  99 % 가 ±90 안이다
- 타일은 줌 3(3.3 km)까지 — 원본 한 칸이 5 km 다. 누른 자리는 0.1 mGal 단위의 int16
"""
from . import gravmag, polargrid
from .i18n import msg

UPSTREAM = "antgg"
ATTRIBUTION = ('AntGG2021 (Scheinert et al., 2024, <a href="https://doi.org/10.1594/PANGAEA.971238" target="_blank" '
               'rel="noopener">PANGAEA</a>, CC BY 4.0)')
MAX_ZOOM = 3
SCALE = 10                       # 0.1 mGal
#: 판 → (원본 파일, 변수, 색의 끝 mGal, 범례 이름)
KINDS = {
    "free_air": ("AntGG2021_Gravity-anomaly.nc", "grav_anom", 150, msg("프리에어 중력 이상")),
    "bouguer": ("AntGG2021_Bouguer-anomaly.nc", "Boug_anom", 500, msg("부게 중력 이상")),
}
#: 누른 자리 속성의 이름 — 영어는 `i18n.PROP_EN`
PROPS = {"free_air": "프리에어 이상 (mGal)", "bouguer": "부게 이상 (mGal)"}
#: gravmag 의 색 고리를 −1…1 의 RGB 로
RAMP = tuple((s, gravmag._rgb(h)) for s, h in gravmag.STOPS)


def _set(kind: str) -> polargrid.Set:
    span = KINDS[kind][2]
    return polargrid.Set(
        name=f"{UPSTREAM}:{kind}", where="ANTGG_DIR", sub=kind, unit="mGal", scale=SCALE, max_zoom=MAX_ZOOM,
        index_of=polargrid.ramp_index(lambda v, span=span: v / span, -1.0, 1.0),
        palette=polargrid.ramp_palette(RAMP, -1.0, 1.0), prop=PROPS[kind], attribution=ATTRIBUTION)


SETS = {f"{UPSTREAM}:{kind}": _set(kind) for kind in KINDS}


def legend(name: str, lang: str = "ko") -> dict:
    """범례 — gravmag 과 같은 칸(끝에 대한 비 `EDGES`)에 이 판의 끝을 곱한다"""
    from . import i18n
    kind = name.split(":", 1)[1]
    span, label = KINDS[kind][2], KINDS[kind][3]
    edges = gravmag.EDGES
    rows = []
    for i, (lo, hi) in enumerate(zip(edges, edges[1:])):
        r, g, b = polargrid.ramp_color((lo + hi) / 2, RAMP)
        a, z = round(lo * span), round(hi * span)
        text = (f"≤ {z:,} mGal" if i == 0 else f"≥ {a:,} mGal" if i == len(edges) - 2 else f"{a:,} – {z:,} mGal")
        rows.append({"code": i, "label": text.replace("-", "−"), "color": f"#{r:02x}{g:02x}{b:02x}"})
    return {"groups": [{"name": i18n.t(label, lang), "rows": rows}], "attribution": ATTRIBUTION}


# ── 굽기 — 호스트에서만 (h5py) ─────────────────────────────────────────

def read_nc(path, variable: str) -> polargrid.Grid:
    """AntGG2021 NetCDF-4 한 장 → `Grid`. h5py 가 있어야 한다"""
    import h5py
    with h5py.File(path, "r") as h:
        if variable not in h:
            raise polargrid.PolarGridError(f"{path} 에 {variable} 가 없다")
        xs, ys = [float(v) for v in h["x"][:]], [float(v) for v in h["y"][:]]
        data = h[variable][:]
        if data.shape != (len(ys), len(xs)):
            raise polargrid.PolarGridError(f"{variable} 의 꼴 {data.shape} 이 (y, x) 가 아니다")
        return polargrid.from_rows(data.tolist(), xs, ys)          # 머리의 (x, y) 를 믿지 않는다 — 위 머리말


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": UPSTREAM, "tag": "AntGG", "title": "AntGG2021"},
]
