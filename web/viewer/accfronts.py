"""남극순환류(ACC) 전선 다섯 — Park & Durand 2019 (SEANOE, doi:10.17882/59800, CC BY 4.0) (wetherilli 429).

인공위성 고도계의 평균 역학 지형(CNES-CLS18 베타)에서 뽑은 전선의 자리다 — 북쪽 경계(NB)·아남극 전선(SAF)·극 전선(PF)·
남쪽 ACC 전선(SACCF)·남쪽 경계(SB). 시간 평균이라 한 날의 전선이 아니다.

`manage.py build_acc_fronts <nc>` 가 원본(NetCDF-3, 321 KB)을 `seafloor.read_netcdf3` 로 읽어 `data/acc_fronts.json` 에 적는다 —
전선마다 이은 고리 하나, 세 점에 하나(0.375°, 남위 55° 에서 24 km 남짓), 소수 셋째 자리. 100 KB 남짓이라 저장소에 둔다. 문이 아니다.

- 원본은 경도 0° 에서 동으로 180° 까지 가다 −180° 로 건너 0° 로 돌아온다(0.125° 간격, 끝에 NaN 하나). 구울 때 경도를 이어(0–360)
  날짜변경선에서 끊기지 않는 고리로 만든다. 남극 탭(3031)은 그대로 긋고, 경위도 타일은 −360 만큼 옮긴 벌도 함께 긋는다
- 남극 탭은 GeoJSON 선(`body`, 누르면 전선 이름), 온 지구 화면은 경위도 타일(`render_tile`)이다
"""
import functools
import io
import json
import math

from django.conf import settings

from . import geomap, paleo
from .i18n import msg

RENDERER = "1"
MAX_ZOOM = 7
NAME = "acc:fronts"
DOI = "https://doi.org/10.17882/59800"
CREDIT = "Park &amp; Durand 2019, ACC fronts (SEANOE, CC BY 4.0)"
CITE = "Park & Durand 2019, Altimetry-derived Antarctic Circumpolar Current fronts · SEANOE · CC BY 4.0"
#: 전선 — (원본 이름, 이름, 색). 북에서 남으로. 색은 따뜻한 쪽에서 찬 쪽으로
FRONTS = [
    ("NB", msg("북쪽 경계 (NB)"), "#e4572e"),
    ("SAF", msg("아남극 전선 (SAF)"), "#f3a712"),
    ("PF", msg("극 전선 (PF)"), "#29a36a"),
    ("SACCF", msg("남쪽 ACC 전선 (SACCF)"), "#2e86de"),
    ("SB", msg("남쪽 경계 (SB)"), "#7b4fd6"),
]
STEP = 3
LABELS = {"front": "전선", "lat": "위도 범위", "link": "자료"}


class AccFrontsError(RuntimeError):
    pass


def path():
    return settings.ACC_FRONTS_FILE


def knows(name: str) -> bool:
    return name == NAME


def available() -> bool:
    return path().exists()


# ── 굽기 ─────────────────────────────────────────────────────────────

def convert(data: bytes) -> dict:
    """원본 NetCDF → `{"fronts": {코드: [[경도, 위도], …]}}` — 경도를 이은 닫힌 고리"""
    from . import seafloor
    try:
        head = seafloor.read_netcdf3(data)
    except Exception as exc:                        # 머리가 깨졌다 — seafloor 의 오류를 이 문의 말로
        raise AccFrontsError(f"NetCDF-3 가 아니다: {exc}") from exc
    out = {}
    for code, _, _ in FRONTS:
        if f"Lat{code}" not in head["vars"]:
            raise AccFrontsError(f"전선 {code} 가 없다")
        lats, lons = seafloor.variable(data, head, f"Lat{code}"), seafloor.variable(data, head, f"Lon{code}")
        pts, prev = [], None
        for lon, lat in zip(lons, lats):
            if math.isnan(lon) or math.isnan(lat):
                continue
            if prev is not None:                    # 날짜변경선을 건너도 잇는다
                while lon - prev > 180:
                    lon -= 360
                while prev - lon > 180:
                    lon += 360
            pts.append((lon, lat))
            prev = lon
        if len(pts) < 100:
            raise AccFrontsError(f"전선 {code} 의 점이 너무 적다 ({len(pts)})")
        kept = pts[::STEP]
        ring = [[round(x, 3), round(y, 3)] for x, y in kept]
        ring.append([round(kept[0][0] + 360 * round((kept[-1][0] - kept[0][0]) / 360), 3), round(kept[0][1], 3)])
        out[code] = ring
    return {"fronts": out}


def build(data: bytes, out=None) -> dict:
    out = out or path()
    doc = {"source": DOI, "cite": CITE, **convert(data)}
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    part.replace(out)
    return {code: len(ring) for code, ring in doc["fronts"].items()}


# ── 내주기 ───────────────────────────────────────────────────────────

def version() -> str:
    try:
        st = path().stat()
    except FileNotFoundError:
        return ""
    return f"{st.st_mtime_ns}-{st.st_size}"


@functools.lru_cache(maxsize=2)
def _data(_stamp: str) -> dict:
    return json.loads(path().read_text(encoding="utf-8"))


def data():
    return _data(version()) if available() else None


def legend(lang: str = "ko") -> list:
    from . import i18n
    return [{"code": code, "name": i18n.t(label, lang), "color": color} for code, label, color in FRONTS]


def body(lang: str = "ko") -> bytes:
    """남극 탭의 GeoJSON — 전선이 갈래(`code`). 파일이 없으면 FileNotFoundError"""
    if not available():
        raise FileNotFoundError(path())
    return _body(lang, version())


@functools.lru_cache(maxsize=4)
def _body(lang: str, _stamp: str) -> bytes:
    from . import i18n
    fronts = _data(_stamp)["fronts"]
    features, legend_rows = [], []
    for code, label, color in FRONTS:
        ring = fronts.get(code)
        if not ring:
            continue
        lats = [p[1] for p in ring]
        props = {"code": code, "front": i18n.t(label, lang), "lat": f"{min(lats):.1f}° – {max(lats):.1f}°", "link": DOI}
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": ring}, "properties": props})
        legend_rows.append({"code": code, "label": i18n.t(label, lang), "color": color, "shape": "stroke", "count": 1, "width": 2})
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link"],
                       "legend": legend_rows, "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def render_tile(z: int, x: int, y: int) -> bytes:
    """경위도 격자(`paleo.render_tile` 과 같다) 한 장 — 전선마다 제 색으로. 이은 고리라 −360 만큼 옮긴 벌도 긋는다"""
    from PIL import Image, ImageDraw
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    ss = 2
    size = paleo.TILE * ss
    scale = size / span
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if north - span <= -30:                          # 전선은 남위 35° 남쪽뿐이다
        draw = ImageDraw.Draw(image)
        width = 1.4 if z <= 2 else 2.0 if z <= 4 else 2.6
        fronts = (data() or {"fronts": {}})["fronts"]
        for code, _, color in FRONTS:
            ring = fronts.get(code)
            if not ring:
                continue
            rgba = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (235,)
            for shift in (0.0, -360.0, 360.0):
                flat = [v for lon, lat in ring for v in (lon + shift, lat)]
                for run in geomap._clip_runs(geomap._to_px(flat, (west, north, scale, scale), 10 ** 6), size, size, 8 * ss):
                    geomap._stroke(draw, run, [{"color": rgba, "width": width, "dash": None}], ss)
    out = image.resize((paleo.TILE, paleo.TILE), Image.Resampling.BOX)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


#: 저장소의 파일이다 — 원본은 SEANOE 에서 한 번 받아 `build_acc_fronts` 로 굽는다 (wetherilli 429)
REGISTRY = [
    {"upstream": "acc", "tag": "SEANOE", "title": "남극순환류 전선 (Park & Durand 2019)", "local": True},
]
