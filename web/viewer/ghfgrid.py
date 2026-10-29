"""남극 지열류 모형 셋 — 격자를 **IHFC 측정 점과 같은 색 눈금으로** 칠해 3031 타일로 잘라 둔다 (wetherilli 432).

측정 점(`heatflow.py`, IHFC 2024)은 남극에 드물다 — 얼음 밑을 잰 곳이 손에 꼽힌다. 그 사이를 메우는 모형 셋을 따로 레이어로 낸다.
**모형이지 측정이 아니다** — 셋이 서로 수십 mW/m² 씩 어긋나는 것 자체가 읽을거리라 하나로 섞지 않았다.

| 판 | 원본 | 격자 | 조건 |
|---|---|---|---|
| `stal` Aq1 | Stål·Reading·Halpin·Whittaker 2021, PANGAEA 924857 `aq1_01_20.csv` | 20 km, 3031 X·Y | CC BY 4.0 |
| `losing` 기계 학습 | Lösing & Ebbing 2021, PANGAEA 930237 `HF_Min_Max_MaxAbs-1.csv` | 위도 0.5° 고리의 경위도 점(약 55 km) | CC BY 4.0 |
| `martos` 퀴리 깊이 | Martos 외 2017, PANGAEA 882503 `Antarctic_GHF.xyz` | 15 km, 극 평사도법 X·Y | CC BY 3.0 |

- 셋 다 글 파일이라 **numpy 없이** 컨테이너에서 굽는다(`manage.py build_antarctic_ghf <폴더>`). 원본은 NAS `N:\\GSM\\sources\\antarctic_ghf\\`,
  구운 것은 `GSM_ANTARCTIC_GHF_DIR`(기본 `<DB 옆>/antarctic_ghf`)의 판마다 하위 폴더
- 색은 `heatflow.CLASSES` 의 갈래 여섯 그대로 — 점과 격자를 겹쳐 같은 색이면 같은 갈래다
- Lösing 은 점이 경위도 고리라 3031 의 20 km 칸에 **가장 가까운 점**으로 채운다(반지름 45 km — 고리 간격의 거의 다). 모양이 모자이크로 보인다
- 타일은 줌 2(6.5 km)까지 — 원본이 그보다 거칠다
"""
import csv
import io

from . import geomap, heatflow, polargrid
from .i18n import msg

UPSTREAM = "ghfgrid"
MAX_ZOOM = 2
SCALE = 10                       # 0.1 mW/m²
LINK = '<a href="https://doi.org/10.1594/PANGAEA.{id}" target="_blank" rel="noopener">PANGAEA</a>'
#: 판 → (원본 파일, 범례 이름, 출처)
KINDS = {
    "stal": ("aq1_01_20.csv", msg("지열류 모형 Aq1 (Stål 2021)"),
             f"Aq1 (Stål et al., 2021, {LINK.format(id=924857)}, CC BY 4.0)"),
    "losing": ("HF_Min_Max_MaxAbs-1.csv", msg("지열류 모형 (Lösing & Ebbing 2021)"),
               f"Lösing &amp; Ebbing (2021, {LINK.format(id=930237)}, CC BY 4.0)"),
    "martos": ("Antarctic_GHF.xyz", msg("지열류 모형 (Martos 2017)"),
               f"Martos et al. (2017, {LINK.format(id=882503)}, CC BY 3.0)"),
}
PROP = "지열류 모형 (mW/m²)"


def _set(kind: str) -> polargrid.Set:
    return polargrid.Set(
        name=f"{UPSTREAM}:{kind}", where="ANTARCTIC_GHF_DIR", sub=kind, unit="mW/m²", scale=SCALE, max_zoom=MAX_ZOOM,
        index_of=polargrid.class_index(heatflow.CLASSES), palette=polargrid.class_palette(heatflow.CLASSES),
        prop=PROP, attribution=KINDS[kind][2])


SETS = {f"{UPSTREAM}:{kind}": _set(kind) for kind in KINDS}


def legend(name: str, lang: str = "ko") -> dict:
    from . import i18n
    kind = name.split(":", 1)[1]
    rows = [{"code": i, "label": row["name"], "color": row["color"]} for i, row in enumerate(heatflow.legend(lang))]
    return {"groups": [{"name": i18n.t(KINDS[kind][1], lang), "rows": rows}], "attribution": KINDS[kind][2]}


# ── 원본 읽기 ─────────────────────────────────────────────────────────

def _spacing(values) -> float:
    """고른 격자의 칸 간격 — 다른 값끼리의 가장 흔한 차"""
    xs = sorted(set(round(v, 1) for v in values))
    gaps = {}
    for a, b in zip(xs, xs[1:]):
        gaps[round(b - a)] = gaps.get(round(b - a), 0) + 1
    return float(max(gaps, key=gaps.get))


def read(kind: str, text: str) -> polargrid.Grid:
    """원본 글 → `Grid`"""
    if kind == "stal":
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "Q (mW/m2)" not in rows[0]:
            raise polargrid.PolarGridError("Aq1 의 머리(Q (mW/m2),…,X,Y)가 아니다")
        pts = [(float(r["X"]), float(r["Y"]), float(r["Q (mW/m2)"])) for r in rows if r["Q (mW/m2)"].strip()]
        return polargrid.rasterize(pts, _spacing(p[0] for p in pts))
    if kind == "losing":
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "HF [mW/m2]" not in rows[0]:
            raise polargrid.PolarGridError("Lösing 의 머리(Lon,Lat,HF [mW/m2],…)가 아니다")
        pts = [(*geomap.lonlat_to_3031(float(r["Lon"]), float(r["Lat"])), float(r["HF [mW/m2]"])) for r in rows
               if r["HF [mW/m2]"].strip()]
        return polargrid.rasterize(pts, 20000.0, radius=45000.0)
    if kind == "martos":
        pts = []
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 3:
                pts.append(tuple(float(v) for v in parts))
        if not pts:
            raise polargrid.PolarGridError("Martos 의 x y z 줄이 없다")
        return polargrid.rasterize(pts, _spacing(p[0] for p in pts))
    raise polargrid.PolarGridError(f"모르는 판 {kind}")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": UPSTREAM, "tag": "GHF", "title": "남극 지열류 모형"},
]
