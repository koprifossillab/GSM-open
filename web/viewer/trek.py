"""NASA Trek 으로 나가는 문 — 달·화성·수성의 지질도·표고·지명.

`kigam.py`·`npolar.py` 와 나란한 문이다 (CLAUDE.md "상류마다 문이 하나"). 달의 자료는
여기로만 나간다. 계획은 devlog P05, 고른 까닭은 devlog 036.

주소는 셋이고 모두 `settings.TREK_URL`(`trek.nasa.gov/moon`) 밑이다.

- `trekarcgis3/rest/services/<지질도>/MapServer` — USGS 달 통합 지질도 1:500만(2020)을
  Trek 이 올려 둔 것. 타일(`export`)·속성(`identify`)·범례(`legend`)
- `trekarcgis/rest/services/LRO_LOLA_DEM_Global_256ppd_v06/ImageServer` — LOLA 표고.
  값(F32)을 TIFF 로 받아 Terrarium PNG 로 옮긴다 — 둥근 달의 지형이다
- `TrekServices/ws/index/…` — 색인. 지명(IAU 행성 지명 사전을 옮긴 것)을 받는다.
  사람이 `manage.py fetch_moon_places` 를 부를 때만 간다

**경위도 격자로 받는다.** Trek 의 달 경위도는 ESRI 코드 `104903`(GCS_Moon_2000)이고, 격자는
Cesium 의 `GeographicTilingScheme` 과 같다 — 줌 0 이 가로 2 장·세로 1 장, 한 장이
`180 / 2^z` 도. 우리 이름은 PSDI 표준의 `IAU_2015:30100` 이고(P05 §3), 상류에 물을 때만
`104903` 이라 적는다. 그 바꿈은 이 파일에만 있다.

**표고는 `elevation.py` 가 아니라 여기다.** 그쪽은 지구의 표고로 나가는 문이고, 이것은 Trek 이
주는 것이다 — 상류 하나에 문 하나다. Terrarium 부호화만 같다.

영상 배경(LRO WAC·LOLA 음영 WMTS)은 이 문을 타지 않는다 — 브라우저가 곧장 부른다(EOX 와 같다).

**수성도 이 문이다**(wetherilli P10) — `settings.TREK_MERCURY_URL`, 아래 "수성" 마디의 `mercury_*`.

**화성도 이 문이다**(058). Mars Trek 은 같은 NASA Trek 의 다른 몸이라(`settings.TREK_MARS_URL`,
`trek.nasa.gov/mars`) 문을 새로 내지 않았다 — 아래 "화성" 마디가 `mars_*` 로 같은 일을 한다.
화성 경위도는 ESRI `104905`(GCS_Mars_2000)이고 격자는 달과 같다.
"""
import io
import json
import logging
import math
import re
import time
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

ATTRIBUTION = ("Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) · "
               "LRO LOLA (NASA/GSFC) · via NASA Moon Trek")
#: 상류에 적는 달 경위도의 코드 (ESRI GCS_Moon_2000)
SR = 104903
#: 달 반지름 (IAU 2015, 구)
RADIUS = 1737400.0

TILE = 256
#: 표고 격자 한 장의 한 변 — Cesium 의 높이 격자 기본값(65×65)
DEM_SIZE = 65
#: 지질도는 1:500만이라 줌 9(한 픽셀 약 130 m) 너머는 같은 선을 크게 그릴 뿐이다.
#: 그래도 가까이 가면 선이 흐려지지 않게 12 까지 받는다
MAX_ZOOM = 12
#: LOLA 256 ppd — 한 픽셀 0.0039°(약 118 m). 줌 9 에서 한 칸(0.35° ÷ 64)이 0.0055° 로 그쯤이다 (wetherilli 083)
DEM_MAX_ZOOM = 9

#: 우리 이름 → Trek 의 MapServer. `units` 만 속성·범례가 있다
LAYERS = {
    "units": "Unified_Global_Geologic_Map_of_the_Moon_Geologic_Units",
    "contacts": "Unified_Global_Geologic_Map_of_the_Moon_Geologic_Contacts",
    "linear": "Unified_Global_Geologic_Map_of_the_Moon_Linear_Features",
}
#: 표고 판. 바꾸면 캐시 열쇠(`views.moon_dem`)가 따라 바뀐다 — 옛 판의 격자가 섞이지 않는다.
#: 128 ppd(`…_128ppd_v04`)에서 올렸다 — 높이 기준(1 737.4 km 구)이 같고 같은 자리 값이 수 m 안에서 맞다 (wetherilli 083)
DEM_SERVICE = "LRO_LOLA_DEM_Global_256ppd_v06"

#: `identify` 가 주는 열 → 팝업의 이름 (한국어 원문. 영어는 `i18n.PROP_EN`)
FIELDS = (("FIRST_Unit", "단위"), ("FIRST_Un_1", "시대"), ("FIRST_Un_2", "이름"),
          ("UnitDescri", "설명"), ("Interpreta", "해석"))

#: 달의 지질시대 — 값은 다섯 가지다(2026-09-29 `returnDistinctValues` 로 셌다). ICS 밖이라
#: 한글판 표가 없다. 한국어판만 옮긴다 — 영어판은 받은 그대로 (P05 §8, 사람이 다시 본다)
AGES_KO = {
    "Copernican": "코페르니쿠스기",
    "Eratosthenian": "에라토스테네스기",
    "Imbrian": "임브리움기",
    "Nectarian": "넥타리스기",
    "Pre-Nectarian": "선넥타리스기",
}


class TrekError(RuntimeError):
    pass


# ── 격자 ────────────────────────────────────────────────────────────

def valid_tile(z: int, x: int, y: int, max_zoom: int = MAX_ZOOM) -> bool:
    return 0 <= z <= max_zoom and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def tile_bbox(z: int, x: int, y: int) -> tuple:
    """경위도 격자 한 장의 (서, 남, 동, 북). y 는 북쪽부터 센다."""
    step = 180.0 / 2 ** z
    west = -180.0 + x * step
    north = 90.0 - y * step
    return west, north - step, west + step, north


# ── 극 격자 (052) ───────────────────────────────────────────────────
#
# 극은 달 극 평사도법이다 — 구(반지름 1737.4 km), 극에서 축척 1, 가짜 동거 0. 우리 이름은 PSDI 의
# `IAU_2015:30130`(북)·`30135`(남)이고, Trek 은 제 극지 서비스(`…_NP`·`…_SP`)가 이 투영을 WKT 로 적는다
# (wkid 가 없다 — `bboxSR` 을 적지 않으면 서비스의 것으로 읽는다). 격자는 Trek 극 WMTS 의 것 그대로다 —
# 왼쪽 위가 (−1 095 930, 1 095 930) m, 줌 0 이 한 장, 한 장이 줌마다 반씩. 영상 배경(브라우저가 곧장
# 부른다)과 한 칸도 어긋나지 않게 같은 격자를 쓴다.

POLAR_HALF = 1095930.0
POLAR_MAX_ZOOM = 12
POLES = {"n": "_NP", "s": "_SP"}


def polar_valid(z: int, x: int, y: int) -> bool:
    return 0 <= z <= POLAR_MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def polar_tile_bbox(z: int, x: int, y: int) -> tuple:
    """극 격자 한 장의 (서, 남, 동, 북) — 극 평사도법 미터."""
    span = 2 * POLAR_HALF / 2 ** z
    west = -POLAR_HALF + x * span
    north = POLAR_HALF - y * span
    return west, north - span, west + span, north


def polar_to_lonlat(x: float, y: float, pole: str) -> tuple:
    """극 평사도법 → 경위도 (`moonmap.stereo_to_lonlat` 과 같은 식)."""
    rho = math.hypot(x, y)
    c = 2 * math.atan2(rho, 2 * RADIUS)
    lat = 90.0 - math.degrees(c)
    if pole == "n":
        return math.degrees(math.atan2(x, -y)), lat
    return math.degrees(math.atan2(x, y)), -lat


def lonlat_to_polar(lon: float, lat: float, pole: str) -> tuple:
    phi, lam = math.radians(lat), math.radians(lon)
    if pole == "n":
        rho = 2 * RADIUS * math.tan(math.pi / 4 - phi / 2)
        return rho * math.sin(lam), -rho * math.cos(lam)
    rho = 2 * RADIUS * math.tan(math.pi / 4 + phi / 2)
    return rho * math.sin(lam), rho * math.cos(lam)


# ── 부르기 ──────────────────────────────────────────────────────────

def _get(path: str, params: dict, base: str = ""):
    url = f"{(base or settings.TREK_URL).rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("trek", ok=False)
        raise TrekError(f"NASA Trek 에 닿지 못했다: {exc}") from exc
    log.info("trek %s -> %s", r.url, r.status_code)
    usage.record("trek", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _json(r) -> dict:
    if r.status_code != 200:
        raise TrekError(f"NASA Trek 이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise TrekError("NASA Trek 이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if isinstance(data, dict) and "error" in data:
        raise TrekError(f"NASA Trek 의 오류: {data['error'].get('message', '')}")
    return data


def _map(layer: str, op: str) -> str:
    if layer not in LAYERS:
        raise TrekError("달 지질 레이어가 아니다")
    return f"trekarcgis3/rest/services/{LAYERS[layer]}/MapServer/{op}"


def _image(r) -> bytes:
    kind = r.headers.get("Content-Type") or r.headers.get("content-type") or ""
    if r.status_code != 200 or not kind.startswith("image/"):
        raise TrekError(f"NASA Trek 이 그림을 주지 않았다 (status={r.status_code}, {kind})")
    return r.content


# ── 지질도 ──────────────────────────────────────────────────────────

def get_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """지질도 타일 한 장 (256 px PNG). Trek 이 공식 색으로 칠한다."""
    w, s, e, n = tile_bbox(z, x, y)
    return _image(_get(_map(layer, "export"), {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": SR, "imageSR": SR, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


def get_polar_tile(layer: str, pole: str, z: int, x: int, y: int) -> bytes:
    """극 격자의 지질도 타일 (052). Trek 의 극지 판(`…_NP`·`…_SP`)이 제 투영으로 그린다."""
    if pole not in POLES:
        raise TrekError("극이 아니다")
    w, s, e, n = polar_tile_bbox(z, x, y)
    return _image(_get(_map(layer, "export").replace("/MapServer/", f"{POLES[pole]}/MapServer/"), {
        "bbox": f"{w},{s},{e},{n}", "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 지질 단위. 없으면 None.

    돌려주는 것은 `{"unit": "Im2", "age": "Imbrian", "rows": [(한국어 이름, 값), …]}` —
    값은 옮기지 않는다(CLAUDE.md "영어판"). 시대만 부르는 쪽이 옮긴다."""
    d = 0.5
    data = _json(_get(_map("units", "identify"), {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": SR,
        "layers": "all", "tolerance": 1, "returnGeometry": "false", "f": "json",
        "mapExtent": f"{lon - d},{lat - d},{lon + d},{lat + d}", "imageDisplay": "200,200,96",
    }))
    hits = data.get("results") or []
    if not hits:
        return None
    attrs = hits[0].get("attributes") or {}
    rows = [(label, str(attrs[key]).strip()) for key, label in FIELDS
            if str(attrs.get(key) or "").strip()]
    return {"unit": attrs.get("FIRST_Unit") or "", "age": attrs.get("FIRST_Un_1") or "", "rows": rows}


def legend() -> list:
    """단위 49 가지의 범례 — `[{"label": "Copernican Crater (Cc)", "image": "data:image/png;base64,…"}]`."""
    data = _json(_get(_map("units", "legend"), {"f": "json"}))
    out = []
    for layer in data.get("layers") or []:
        for item in layer.get("legend") or []:
            image = item.get("imageData")
            if not image:
                continue
            label = item.get("label") or ""
            unit = _unit_of(label)
            out.append({"label": label, "unit": unit, "age": age_of_unit(unit),
                        "image": f"data:{item.get('contentType') or 'image/png'};base64,{image}"})
    return out


_UNIT = re.compile(r"\(([^()]+)\)\s*$")
#: 단위 기호의 머리글자 → 시대. `EIp`·`INt` 처럼 둘에 걸친 것은 앞 글자(더 젊은 쪽)로 묶는다
_AGE_HEAD = {"C": "Copernican", "E": "Eratosthenian", "I": "Imbrian", "N": "Nectarian"}


def _unit_of(label: str) -> str:
    """범례 이름 끝의 기호 — "Copernican Crater (Cc)" → "Cc"."""
    m = _UNIT.search(label)
    return m.group(1).strip() if m else ""


def age_of_unit(unit: str) -> str:
    if unit.startswith("pN"):
        return "Pre-Nectarian"
    return _AGE_HEAD.get(unit[:1], "")


# ── 표고 ────────────────────────────────────────────────────────────

def _terrarium_rgb(value: float) -> tuple:
    v = value + 32768
    r, rem = divmod(v, 256)
    g = int(rem)
    b = int(round((rem - g) * 256))
    if b == 256:
        g, b = g + 1, 0
    return (max(0, min(255, int(r))), g, b)


#: 가까이서 쓰는 고운 표고 판 (wetherilli 107) — (서비스, 범위(서, 남, 동, 북), 줌 끝, 배율). 줌 `DEM_MAX_ZOOM` 너머에서만
#: 쓴다. 판의 한 칸이 격자 한 칸(장 ÷ 64)에 맞는 줌까지다. 모두 경위도 판이다 — 극 평사도법 판(`…_NP`·`86S356E_3mp`)과
#: 투영 좌표 NAC 둘(02N085E·07N022E)은 뺐다.
#: 극 5 m 는 **0.5 m 단위 정수를 그대로** 준다(2026-09-30, 18 점이 모두 256 ppd 의 두 배) — 배율 0.5. 자료는 87.5° 너머뿐이라
#: 범위를 거기로 잡았다. 북극 30 m 판은 한 칸(0.004°)이 256 ppd 와 같아 뺐다.
DEM_PARTS = (
    ("LRO_LOLA_DEM_SPole875_5mp_v04_EQ", (-180.0, -90.0, 180.0, -87.55), 11, 0.5),
    ("LRO_LOLA_DEM_NPole875_5mp_v04_EQ", (-180.0, 87.55, 180.0, 90.0), 11, 0.5),
    ("LRO_LOLA_DEM_SPole75_30mp_v04_EQ", (-180.0, -90.0, 180.0, -75.05), 10, 1.0),
    # NAC DTM — 범위는 판의 네모다. 네모 안에서도 띠 밖은 비어 있어 256 ppd 로 메운다
    ("LRO_NAC_DEM_00N234E_150cmp", (-125.9745, -0.5607, -125.1072, 0.7690), 15, 1.0),
    ("LRO_NAC_DEM_02S167E_150cmp", (166.5794, -2.9192, 166.9710, -1.7502), 15, 1.0),
    ("LRO_NAC_DEM_02S317E_150cmp", (-43.3346, -2.9501, -42.9085, -1.8250), 15, 1.0),
    ("LRO_NAC_DEM_03S286E_150cmp", (-74.5352, -3.6993, -73.7101, -2.5608), 15, 1.0),
    ("LRO_NAC_DEM_05N000E_150cmp", (-0.5939, 4.1055, -0.1652, 5.3704), 15, 1.0),
    ("LRO_NAC_DEM_06N120E_200cmp", (119.5579, 5.9841, 120.1013, 7.1090), 15, 1.0),
    ("LRO_NAC_DEM_07N301E_2mp", (-58.8657, 6.8589, -58.4104, 7.8233), 15, 1.0),
    ("LRO_NAC_DEM_08N332E_2mp", (-28.0737, 7.0615, -27.1066, 8.7463), 15, 1.0),
    ("LRO_NAC_DEM_09S015E_150cmp", (15.1403, -9.6470, 15.6962, -8.6196), 15, 1.0),
    ("LRO_NAC_DEM_10N058E_150cmp", (58.6398, 10.6602, 58.9404, 11.1357), 15, 1.0),
    ("LRO_NAC_DEM_13N356E_150cmp", (-3.9301, 12.5163, -3.6453, 13.4699), 15, 1.0),
    ("LRO_NAC_DEM_13S358E_200cmp", (-2.6084, -13.1203, -2.0041, -12.0866), 15, 1.0),
    ("LRO_NAC_DEM_14N304E_2mp", (-56.1364, 13.2130, -55.6417, 14.1965), 15, 1.0),
    ("LRO_NAC_DEM_16S041E_150cmp", (40.4706, -16.5958, 41.2195, -15.2778), 15, 1.0),
    ("LRO_NAC_DEM_17S173E_150cmp", (173.1571, -17.4360, 173.7186, -15.9753), 15, 1.0),
    ("LRO_NAC_DEM_19N005E_2mp", (5.2291, 18.1295, 5.5045, 19.0863), 15, 1.0),
    ("LRO_NAC_DEM_19S070E_150cmp", (69.5021, -19.3338, 70.2348, -17.6288), 15, 1.0),
    ("LRO_NAC_DEM_19S129E_150cmp", (128.2948, -20.1831, 128.8312, -18.7234), 15, 1.0),
    ("LRO_NAC_DEM_20N010E_2mp", (10.1997, 19.5487, 10.5707, 20.5179), 15, 1.0),
    ("LRO_NAC_DEM_20S337E_400cmp", (-22.7927, -21.0659, -22.2073, -20.4841), 14, 1.0),
    ("LRO_NAC_DEM_25N311E_2mp", (-49.0412, 24.0893, -48.4353, 25.2897), 15, 1.0),
    ("LRO_NAC_DEM_26N004E_150cmp", (3.0272, 25.4546, 3.8496, 26.7641), 15, 1.0),
    ("LRO_NAC_DEM_26N150E_200cmp", (150.1462, 25.6232, 150.6846, 26.8169), 15, 1.0),
    ("LRO_NAC_DEM_26N178E_150cmp", (177.5399, 25.6718, 178.0041, 26.4303), 15, 1.0),
    ("LRO_NAC_DEM_26S265E_200cmp", (-95.7877, -26.7175, -95.0620, -25.4910), 15, 1.0),
    ("LRO_NAC_DEM_27N318E_150cmp", (-42.0125, 26.7587, -41.5623, 27.7138), 15, 1.0),
    ("LRO_NAC_DEM_28N307E_150cmp", (-52.7440, 27.2168, -52.1656, 28.4802), 15, 1.0),
    ("LRO_NAC_DEM_32N292E_2mp", (-68.2808, 31.0044, -66.8543, 32.3601), 15, 1.0),
    ("LRO_NAC_DEM_36N320E_2mp", (-40.3344, 35.6677, -39.6430, 36.7432), 15, 1.0),
    ("LRO_NAC_DEM_36S164E_2mp", (164.0231, -36.1359, 164.8637, -34.8575), 15, 1.0),
    ("LRO_NAC_DEM_37S206E_150cmp", (-153.9540, -37.2488, -153.4460, -36.8352), 15, 1.0),
    ("LRO_NAC_DEM_43S349E_150cmp", (-11.6454, -43.6577, -10.9236, -42.3481), 15, 1.0),
    ("LRO_NAC_DEM_51S171E_2mp", (170.5026, -51.6683, 171.4013, -50.3714), 15, 1.0),
    ("LRO_NAC_DEM_53N354E_150cmp", (-5.4833, 53.0779, -4.8128, 53.5177), 15, 1.0),
    ("LRO_NAC_DEM_55N077E_200cmp", (76.9027, 53.7778, 77.3971, 54.9353), 15, 1.0),
    ("LRO_NAC_DEM_60S200E_150cmp", (-160.6817, -60.6431, -159.4890, -59.3179), 15, 1.0),
    ("LRO_NAC_DEM_61N099E_150cmp", (98.7326, 60.4580, 100.1981, 61.7296), 15, 1.0),
    ("LRO_NAC_DEM_73N350E_150cmp", (-9.4369, 73.3188, -8.2911, 73.7132), 15, 1.0),
    # 경위도 판이 아닌 셋(wetherilli 150) — ImageServer 가 우리 경위도로 옮겨 준다(`bboxSR`·`imageSR`). 256 ppd 와 맞대니
    # 평균 −1.2·−2.9·−1.2 m 였다. 극 평사도법 판의 범위는 네 귀를 경위도로 옮긴 네모라 빈 곳이 넓다 — 256 ppd 로 메운다
    ("LRO_NAC_DEM_86S356E_3mp", (-15.38, -87.2, 0.44, -84.59), 15, 1.0),
    ("LRO_NAC_DEM_02N085E_150cmp", (84.812, 1.3778, 85.702, 2.8148), 15, 1.0),
    ("LRO_NAC_DEM_07N022E_150cmp", (21.4617, 6.2719, 22.0539, 7.2299), 15, 1.0),
)
#: 넣지 않은 판 (wetherilli 150) — 아폴로 15 PanCam DEM 셋은 256 ppd 와의 차이가 평균 ±15 m·흩어짐 23–52 m 로 NAC(10–14 m)보다
#: 커 자리가 어긋난 판으로 보인다. 메트릭 카메라 1024 ppd 둘(`Apollo17_…`·`ApolloZone_…`)은 256 ppd 보다 120 m 남짓 낮다 —
#: 기준면이 다른 까닭을 모른 채 맞추지 않았다
DEM_FINE_MAX = max(part[2] for part in DEM_PARTS)


#: 줌 0(반구 한 장)은 256 ppd 판이 "Unable to complete operation" 으로 받지 않는다(2026-09-30, 0.21.0 부터 운영의 줌 0 이
#: 502 였다). 65×65 로 줄이면 두 판이 같으니 128 ppd 판으로 받는다
DEM_Z0_SERVICE = "LRO_LOLA_DEM_Global_128ppd_v04"


def dem_source(z: int, x: int, y: int) -> tuple:
    """그 장을 받을 판 — `(서비스, 배율)`. 캐시 열쇠도 이것을 쓴다."""
    part = dem_part(z, x, y)
    if part:
        return part[0], part[3]
    return (DEM_Z0_SERVICE if z == 0 else DEM_SERVICE), 1.0


def dem_part(z: int, x: int, y: int):
    """줌 `DEM_MAX_ZOOM` 너머의 한 장에 쓸 고운 판 — 그 장에 걸치고 줌 끝이 넉넉한 것 가운데 가장 고운 것. 없으면 None."""
    if z <= DEM_MAX_ZOOM:
        return None
    w, s, e, n = tile_bbox(z, x, y)
    got = [part for part in DEM_PARTS
           if part[2] >= z and part[1][0] < e and part[1][2] > w and part[1][1] < n and part[1][3] > s]
    return max(got, key=lambda part: part[2]) if got else None


def _dem_values(service: str, box: tuple, scale: float = 1.0) -> list:
    """`exportImage` 로 65×65 표고 — 못 읽은 칸은 None."""
    from PIL import Image

    w, s, e, n = box
    half = (e - w) / (DEM_SIZE - 1) / 2
    r = _get(f"trekarcgis/rest/services/{service}/ImageServer/exportImage", {
        "bbox": f"{w - half},{s - half},{e + half},{n + half}", "bboxSR": SR, "imageSR": SR,
        "size": f"{DEM_SIZE},{DEM_SIZE}", "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    })
    try:
        image = Image.open(io.BytesIO(_image(r)))
        image.load()
    except (OSError, ValueError) as exc:
        raise TrekError(f"표고 TIFF 를 읽지 못했다: {exc}") from exc
    if image.mode != "F" or image.size != (DEM_SIZE, DEM_SIZE):
        raise TrekError(f"표고의 꼴이 다르다 ({image.mode}, {image.size})")
    # 자료 밖은 아주 큰 음수이거나, 정수 판이면 −32768 이다
    return [v * scale if -20000 < v < 20000 and v != -32768 and not math.isnan(v) else None for v in image.getdata()]


def dem_tile(z: int, x: int, y: int) -> bytes:
    """표고 격자 한 장 — 65×65 Terrarium PNG. 가장자리 점이 이웃 장과 겹치게 받는다.

    ImageServer 의 `exportImage` 는 픽셀의 **가운데**를 잰다. 격자의 첫 점과 끝 점이 장의
    가장자리에 오도록 네모를 반 칸씩 넓혀 묻는다 — 안 그러면 장과 장 사이에 금이 간다.

    줌 `DEM_MAX_ZOOM` 까지는 온 달 판(256 ppd), 그 너머는 고운 판(`dem_part`)이고 그 판의 빈 칸은 온 달 판으로
    메운다 (wetherilli 107). 고운 판이 없는 자리는 부르는 쪽이 묻지 않는다(`views.moon_dem` 이 404)."""
    from PIL import Image

    box = tile_bbox(z, x, y)
    part = dem_part(z, x, y)
    service, scale = dem_source(z, x, y)
    values = _dem_values(service, box, scale)
    if part and any(v is None for v in values):
        base = _dem_values(DEM_SERVICE, box)
        values = [v if v is not None else b for v, b in zip(values, base)]
    out = Image.new("RGB", (DEM_SIZE, DEM_SIZE))
    # 그래도 빈 칸은 0 m 로 둔다 — 구멍보다 평평한 것이 낫다
    out.putdata([_terrarium_rgb(v if v is not None else 0.0) for v in values])
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


# ── 점의 표고 (037) ──────────────────────────────────────────────────
#
# 달 점묶음의 ⛰. 지구의 `elevation.elevations` 와 같은 자리다. `getSamples` 가 여러 점을 한 번에
# 받는다. **POST 는 403 이다**(2026-09-29 — Trek 앞의 방화벽) — GET 으로, 주소가 길어지지 않게
# 한 번에 `SAMPLE_CHUNK` 점씩(100 점이 3 KB 남짓).

#: 출처 이름과 높이 기준. `pointsets.ELEV_DATUMS` 에도 적는다
ELEV_SOURCE = "lola-256ppd"
ELEV_DATUM = "moon-sphere"
SAMPLE_CHUNK = 100


def lola_values(points: dict) -> dict:
    """`{id: (lat, lon)}` → `{id: 표고 m}`. 반지름 1 737.4 km 구에서 잰 높이다. 못 읽은 점은 빠진다."""
    ids = list(points)
    out = {}
    for start in range(0, len(ids), SAMPLE_CHUNK):
        chunk = ids[start:start + SAMPLE_CHUNK]
        geometry = {"points": [[round(points[i][1], 6), round(points[i][0], 6)] for i in chunk],
                    "spatialReference": {"wkid": SR}}
        data = _json(_get(f"trekarcgis/rest/services/{DEM_SERVICE}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "interpolation": "RSP_BilinearInterpolation", "f": "json",
        }))
        for sample in data.get("samples") or []:
            try:
                value = float(sample.get("value"))
                index = int(sample.get("locationId"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(chunk) and -20000 < value < 20000:
                out[chunk[index]] = value
    return out


# ── 높이 그래프 (wetherilli 100) ──────────────────────────────────────
#
# 잰 선을 따라 고르게 찍은 점의 표고. 선은 꼭짓점만 받아 **대원**을 따라 점을 찍는다 — 화면이 길이를 대원으로
# 재므로(`moon.js` 의 `arc`) 그래프의 가로도 같은 길이가 된다. 높이는 점묶음의 ⛰ 와 같은 `lola_values` 다.

#: 한 선에 찍는 점의 수 끝. 256 ppd 한 칸이 118 m 라 수십 km 선이면 이만큼이 칸마다 한 점쯤이다.
#: `getSamples` 한 번에 100 점이라 512 점이면 여섯 번 묻는다
PROFILE_MAX_POINTS = 512
PROFILE_MAX_VERTICES = 100


def _unit(lon: float, lat: float) -> tuple:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _slerp(a: tuple, b: tuple, t: float) -> tuple:
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    omega = math.acos(dot)
    if omega < 1e-12:
        return a
    s = math.sin(omega)
    wa, wb = math.sin((1 - t) * omega) / s, math.sin(t * omega) / s
    return tuple(wa * x + wb * y for x, y in zip(a, b))


def profile_points(vertices: list, n: int, radius: float = RADIUS) -> list:
    """꼭짓점 `[(경도, 위도), …]` → 대원을 따라 고르게 `n` 점 `[(경도, 위도, 처음부터의 거리 m), …]`.
    꼭짓점 자리에는 꼭 한 점을 둔다 — 꺾인 곳의 높이가 빠지지 않게. 거리는 `radius` 의 구에서 잰다."""
    units = [_unit(lon, lat) for lon, lat in vertices]
    seg = [radius * math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)))))
           for a, b in zip(units, units[1:])]
    total = sum(seg)
    if total <= 0:
        return [(vertices[0][0], vertices[0][1], 0.0)]
    # 구간마다 길이에 비례해 나누되 적어도 한 칸
    counts = [max(1, round((n - 1) * s / total)) for s in seg]
    out, start = [], 0.0
    for i, (a, b) in enumerate(zip(units, units[1:])):
        for k in range(counts[i]):
            x, y, z = _slerp(a, b, k / counts[i])
            out.append((math.degrees(math.atan2(y, x)), math.degrees(math.asin(max(-1.0, min(1.0, z)))),
                        start + seg[i] * k / counts[i]))
        start += seg[i]
    x, y, z = units[-1]
    out.append((math.degrees(math.atan2(y, x)), math.degrees(math.asin(max(-1.0, min(1.0, z)))), total))
    return out


#: 몸 → (반지름, 표고 읽기, 출처, 높이 기준). 화성·수성은 화면의 구와 같은 반지름으로 거리를 잰다 (wetherilli 148)
def _profile_body(body: str) -> tuple:
    if body == "mars":
        return MARS_RADIUS, mars_values, MARS_ELEV_SOURCE, MARS_ELEV_DATUM
    if body == "mercury":
        return MERCURY_RADIUS, mercury_values, MERCURY_ELEV_SOURCE, MERCURY_ELEV_DATUM
    return RADIUS, lola_values, ELEV_SOURCE, ELEV_DATUM


def profile(vertices: list, n: int = 256, body: str = "moon") -> dict:
    """`{"dist": [m…], "elev": [m 또는 None…], "lon": […], "lat": […], "source", "datum"}`. 못 읽은 점은 None.
    화성·수성도 같은 틀이다 — 지질 띠는 상류를 많이 불러 넣지 않았다 (wetherilli 148)."""
    radius, read, source, datum = _profile_body(body)
    n = max(2, min(int(n), PROFILE_MAX_POINTS))
    pts = profile_points(vertices, n, radius)
    values = read({i: (lat, lon) for i, (lon, lat, _) in enumerate(pts)})
    return {"dist": [round(d, 1) for _, _, d in pts],
            "elev": [round(values[i], 1) if i in values else None for i in range(len(pts))],
            "lon": [round(lon, 6) for lon, _, _ in pts], "lat": [round(lat, 6) for _, lat, _ in pts],
            "source": source, "datum": datum}


# ── 누른 자리의 값 (wetherilli 103) ──────────────────────────────────
#
# 광물·원소·지각 두께 판은 Trek 이 색을 칠해 준다(060) — 그림만으로는 값을 모른다. 같은 자료의 ImageServer 가
# 값(F32·F64)을 주므로 누른 자리 한 점을 `getSamples` 로 읽는다. **켠 판의 것만** 묻는다 — 한 번 누르는 데 판마다 한
# 요청이다. 판마다 단위·배율·그럴 법한 범위를 손으로 적었다(2026-09-30 에 한 점씩 받아 보았다). 범위 밖(빈 값)은 버린다.

#: 갈래 → (서비스 뿌리, 서비스, 이름(한국어 원문), 단위, 배율, 아래, 위, 자릿수, 출처)
VALUES = {
    "feo": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_FeOWeightPercent_50N50S", "FeO", "wt%", 1, 0, 40, 1,
            "Kaguya MI"),
    "olivine": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_OlivinePercent_50N50S", "감람석", "wt%", 100, 0, 100, 1,
                "Kaguya MI"),
    "cpx": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_ClinopyroxenePercent_50N50S", "단사휘석", "wt%", 100, 0, 100, 1,
            "Kaguya MI"),
    "opx": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_OrthopyroxenePercent_50N50S", "사방휘석", "wt%", 100, 0, 100, 1,
            "Kaguya MI"),
    "plag": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_PlagioclasePercent_50N50S", "사장석", "wt%", 100, 0, 100, 1,
             "Kaguya MI"),
    "th": ("trekarcgis", "LP_GRS_Th_Global_2ppd", "토륨", "ppm", 1, 0, 30, 2, "Lunar Prospector GRS"),
    "ti": ("trekarcgis2", "LP_GRS_TitaniumAbundance_2ppd", "티타늄", "wt%", 1, 0, 15, 2, "Lunar Prospector GRS"),
    **{f"thick{n}": ("trekarcgis", f"Model{n}_thick_eq", "지각 두께", "km", 1, 0, 200, 1, f"GRAIL · Wieczorek et al. 2013, model {n}")
       for n in range(1, 5)},
    # 다누리 KGRS (wetherilli 150) — **단위를 모른다.** Trek 색인에 없고 서비스 설명도 비었다. 값이 함량이 아니라 계수율로
    # 보인다(칼륨 1.6–3.3, 토륨이 LP 의 1/10 남짓, 2026-10-02). 사람이 "상대값(단위 미확인)" 으로 내자고 했다
    "kgrs_k": ("trekarcgis3", "KPLO_KGRS_Potassium_2ppd", "칼륨 상대값 (단위 미확인)", "", 1, 0, 1000, 2, "KPLO(다누리) KGRS"),
    "kgrs_u": ("trekarcgis3", "KPLO_KGRS_Uranium_2ppd", "우라늄 상대값 (단위 미확인)", "", 1, 0, 1000, 2, "KPLO(다누리) KGRS"),
    "kgrs_th": ("trekarcgis3", "KGRS_Th_LG_smooth", "토륨 상대값 (단위 미확인)", "", 1, 0, 1000, 3, "KPLO(다누리) KGRS"),
    "kgrs_tn": ("trekarcgis3", "KPLO_KGRS_Thermal_Neutron_2ppd", "열중성자 상대값 (단위 미확인)", "", 1, 0, 1000, 2,
                "KPLO(다누리) KGRS"),
    "kgrs_tn_lg": ("trekarcgis3", "KGRS_Thermal_Neutron_LG", "열중성자 상대값 (단위 미확인)", "", 1, 0, 1000, 4,
                   "KPLO(다누리) KGRS"),
    # 북극 (wetherilli 150) — 극 평사도법 ImageServer 도 경위도 점으로 묻는다. 남극 짝(`sp_*`)은 2026-09-30·10-02 둘 다 답이 없다
    "np_feo": ("trekarcgis", "np_feo_mlemelin_031417", "FeO (북극)", "wt%", 1, 0, 40, 1, "NASA Moon Trek (M. Lemelin)"),
    "ice_today": ("trekarcgis", "np_ice_depth_new_240m_mat_today_27_Oct_2016", "얼음이 버틸 깊이 — 오늘의 자전축", "m", 1, 0, 2.5, 2,
                  "NASA Moon Trek"),
    "ice_paleo": ("trekarcgis", "np_ice_depth_new_240m_mat_paleo_27_Oct_2016", "얼음이 버틸 깊이 — 옛 자전축", "m", 1, 0, 2.5, 2,
                  "NASA Moon Trek"),
    # 남은 판 (wetherilli 236) — 2026-10-04 에 한 점씩 받아 보았다. 단위는 서비스 이름·자료의 꼴에서 왔다. SMFe 는 이름에 단위가 없다
    "omat": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_OpticalMaturityIndex_50N50S", "광학 성숙도 지수 (OMAT)", "", 1, 0, 1, 3,
             "Kaguya MI"),
    "plag_grain": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_PlagioclaseGrainSizeMicrons_50N50S", "사장석 알갱이 크기", "µm", 1,
                   0, 200, 1, "Kaguya MI"),
    "smfe": ("trekarcgis", "Lunar_Kaguya_MIMap_MineralDeconv_AbundanceSMFe_50N50S", "미세 금속철(SMFe) 상대값 (단위 미확인)", "", 1,
             0, 7, 2, "Kaguya MI"),
    **{f"cmi{n}": ("trekarcgis", f"Model{n}_cmi_eq", "지각–맨틀 경계 (기준 반지름 대비 높이)", "km", 1, -200, 100, 1,
                   f"GRAIL · Wieczorek et al. 2013, model {n}") for n in range(1, 5)},
    "grain_density": ("trekarcgis2", "grain_density_310_eq", "지각 알갱이 밀도", "kg/m³", 1, 2000, 4000, 0,
                      "GRAIL · Wieczorek et al. 2013"),
    "relief": ("trekarcgis", "LOLA_PA_310_eq", "표면 기복 (기준 반지름 대비)", "km", 1, -20, 20, 2, "GRAIL · LOLA"),
    **{f"cf_{kind}_{ppd}": ("trekarcgis2", f"dgdr_{kind}_cf_clc_cyl_{ppd}_jp2", "크리스티안센 특성 파장", "µm", 1, 6, 10, 2,
                            "LRO Diviner") for kind in ("std", "nen") for ppd in ("032", "128")},
    **{f"tbol_{name}": ("trekarcgis2", f"diviner_tbol_{name}", label, "K", 1, 0, 450, 1, "LRO Diviner")
       for name, label in (("max", "가장 높은 온도"), ("min", "가장 낮은 온도"), ("hour00", "자정의 온도"), ("hour12", "정오의 온도"))},
    **{f"tbol_{name}": ("trekarcgis2", f"diviner_tbol_{name}", label, "K", 1, -300, 300, 1, "LRO Diviner")
       for name, label in (("max_anom", "가장 높은 온도의 이상"), ("min_anom", "가장 낮은 온도의 이상"),
                           ("max_sub_min_anom", "온도 이상의 차"))},
    "tbol_max_div_min_anom": ("trekarcgis2", "diviner_tbol_max_div_min_anom", "온도 이상의 비", "", 1, -20, 20, 3, "LRO Diviner"),
    "minirf_cpr": ("trekarcgis2", "minirf_s1_49dnorm_EQ", "원편광 비 (CPR)", "", 1, 0, 15, 2, "LRO Mini-RF"),
    # 표고를 그린 판(색 음영·음영)은 화성·수성처럼 LOLA 높이를 낸다. 점묶음의 표고(`lola_values`)와 같은 서비스다
    "moon_elev": ("trekarcgis", DEM_SERVICE, "높이 — 달 기준구 1737.4 km", "m", 1, -10000, 11000, 0, "LRO LOLA 256 ppd"),
}

#: 한 자리만 덮는 판 — 판 밖은 상류가 오류를 주어 빈 값으로 돌린다 (wetherilli 236)
LOCAL_VALUES = ("minirf_cpr",)

#: 판이 여럿인 갈래 (wetherilli 236) — 열쇠가 서비스 이름을 품는다. GRAIL 중력은 차수(L50–1200)마다, NAC 경사는 착륙 후보지마다 판이 있다
#: 갈래 → (열쇠의 꼴, 서비스 뿌리, 이름, 단위, 아래, 위, 자릿수, 출처)
_GRAV = {"boug": ("부게 중력 교란", "mGal", -3000, 3000, 1), "anom": ("프리에어 중력 이상", "mGal", -3000, 3000, 1),
         "dist": ("중력 교란", "mGal", -3000, 3000, 1), "geoid": ("지오이드 높이", "m", -2000, 2000, 1),
         "anomerr": ("중력 이상 오차", "mGal", 0, 1000, 2)}
_GRAV_KEY = re.compile(r"^grav:(boug|anom|dist|geoid|anomerr):(\d{2,4})$")
_SLOPE_KEY = re.compile(r"^slope:(LRO_NAC_(?:Slope_\d+m_\w+|CraterSlopes(?:Masked)?_\d+mpp_Site\w|Slope_2_5mpp_Shioli))$")


def value_spec(key: str):
    """갈래 → `VALUES` 꼴의 명세. 고정된 갈래는 `VALUES`, 판이 여럿인 갈래(`grav:…`·`slope:…`)는 열쇠에서 짓는다. 모르면 None."""
    if key in VALUES:
        return VALUES[key]
    m = _GRAV_KEY.match(key)
    if m:
        label, unit, lo, hi, digits = _GRAV[m.group(1)]
        return ("trekarcgis2", f"gggrx_1200a_{m.group(1)}_l{m.group(2)}_eq", label, unit, 1, lo, hi, digits,
                f"GRAIL GRGM1200A · L{m.group(2)}")
    if key == "grav:degstr":
        return ("trekarcgis2", "gggrx_1200a_degstr_eq", "중력 차수 강도", "", 1, 0, 1500, 0, "GRAIL GRGM1200A")
    m = _SLOPE_KEY.match(key)
    if m:
        root = "trekarcgis2" if m.group(1).startswith("LRO_NAC_Slope_") and "mpp" not in m.group(1) else "trekarcgis3"
        return (root, m.group(1), "경사도", "°", 1, 0, 90, 1, "LRO NAC DEM")     # "경사" 는 팝업에서 지층의 경사(dip)다
    return None

#: 판이 덮는 위도 끝 — 없으면 온 달
VALUE_LAT = {key: 50 for key in ("feo", "olivine", "cpx", "opx", "plag", "omat", "plag_grain", "smfe")}
#: 북극 판이 덮는 위도 밑 — 그 밑은 묻지 않는다. 극 평사도법 네모의 가장 먼 귀(FeO ±1 266 km, 얼음 ±300 km)보다 조금 안쪽
VALUE_NORTH = {"np_feo": 50, "ice_today": 80, "ice_paleo": 80}

#: 씨앗의 판 이름 → 갈래. 색 판과 회색 판이 같은 값을 가리킨다. 극지 짝(`_NP`·`_SP`)은 씨앗에 없다
_VALUE_IDS = (
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_FeOWeightPercent_50N50S"), "feo"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_OlivinePercent_50N50S"), "olivine"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_ClinopyroxenePercent_50N50S"), "cpx"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_OrthopyroxenePercent_50N50S"), "opx"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_PlagioclasePercent_50N50S"), "plag"),
    (re.compile(r"^LP_GRS_Th_(Clr_)?Global_2ppd$"), "th"),
    (re.compile(r"^LP_GRS_(Clr)?TitaniumAbundance_2ppd$"), "ti"),
    (re.compile(r"^Model([1-4])_thick\.eq$"), "thick"),
    (re.compile(r"^KPLO_KGRS_Potassium_2ppd$"), "kgrs_k"),
    (re.compile(r"^KPLO_KGRS_Uranium_2ppd$"), "kgrs_u"),
    (re.compile(r"^KGRS_Th_LG_smooth$"), "kgrs_th"),
    (re.compile(r"^KPLO_KGRS_Thermal_Neutron_2ppd$"), "kgrs_tn"),
    (re.compile(r"^KGRS_Thermal_Neutron_LG$"), "kgrs_tn_lg"),
    (re.compile(r"^np_feo_mlemelin_031417$"), "np_feo"),
    (re.compile(r"^np_ice_depth_new_240m_mat_today_27_Oct_2016$"), "ice_today"),
    (re.compile(r"^np_ice_depth_new_240m_mat_paleo_27_Oct_2016$"), "ice_paleo"),
    # 남은 판 (wetherilli 236)
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_OpticalMaturityIndex_50N50S"), "omat"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_PlagioclaseGrainSizeMicrons_50N50S"), "plag_grain"),
    (re.compile(r"^Lunar_Kaguya_MIMap_MineralDeconv_AbundanceSMFe_50N50S"), "smfe"),
    (re.compile(r"^Model([1-4])_cmi\.eq$"), "cmi"),
    (re.compile(r"^grain_density_310\.eq$"), "grain_density"),
    (re.compile(r"^LOLA_PA_310\.eq$"), "relief"),
    (re.compile(r"^dgdr_(?:Clr)?(std|nen)_cf_clc_cyl_(032|128)_jp2$"), "cf"),
    (re.compile(r"^diviner_(?:Clr)?tbol_(max|min|hour00|hour12|max_anom|min_anom|max_sub_min_anom|max_div_min_anom)$"), "tbol"),
    (re.compile(r"^minirf_s1_(?:Clr)?49dnorm_EQ$"), "minirf_cpr"),
    (re.compile(r"^LRO_LOLA_(?:Clr)?Shade_Global_(?:128ppd_v04|256ppd_v06)$"), "moon_elev"),
    (re.compile(r"^gggrx_1200a_(boug|anom|dist|geoid|anomerr)_l(\d{2,4})\.eq$"), "grav"),
    (re.compile(r"^gggrx_1200a_degstr\.eq$"), "grav:degstr"),
    (re.compile(r"^LRO_NAC_(?:Clr)?(Slope_\d+m_\w+|CraterSlopes(?:Masked)?_\d+mpp_Site\w|Slope_2_5mpp_Shioli)$"), "slope"),
)


#: 화성 (wetherilli 192) — 값을 주는 ImageServer 는 표고뿐이다. TES 광물·열관성·알베도는 WMTS 그림만 있고(`getLayerServices`
#: 가 WMTS 하나만 준다, 2026-10-04) ImageServer 목록(`trekarcgis`, 화성은 이 뿌리 하나)에도 없다 — 값을 읽지 못해 뺐다.
#: 그래서 표고를 그린 판(색 음영·음영·MOLA 합본)을 켜면 MOLA–HRSC 200 m 의 높이를, 1 m DEM 판은 그 DEM 의 높이를 낸다.
#: 판 밖은 상류가 400 오류(JSON)를 주어 빈 값이 된다. 갈래 → `VALUES` 와 같은 꼴
MARS_VALUES = {
    "mars_elev": ("trekarcgis", "Mars_MOLA_blend200ppx_HRSC_DEM_clon0dd_200mpp_lzw", "높이 — 화성 기준면(아레오이드)", "m", 1,
                  -9000, 22000, 0, "MOLA–HRSC 200 m"),
    "mars_gale": ("trekarcgis", "Gale_DEM_SMG_1m", "높이 — 화성 기준면(아레오이드)", "m", 1, -9000, 22000, 1, "Gale HiRISE DEM 1 m"),
    "mars_victoria": ("trekarcgis", "DEM_1m_VictoriaCrater", "높이 — 화성 기준면(아레오이드)", "m", 1, -9000, 22000, 1,
                      "Victoria Crater HiRISE DEM 1 m"),
}
_MARS_VALUE_IDS = (
    (re.compile(r"^Mars_MOLA_blend200ppx_HRSC_(Clr)?Shade_clon0dd_200mpp_lzw$"), "mars_elev"),
    (re.compile(r"^Mars_MGS_MOLA_ClrShade_merge_global_463m$"), "mars_elev"),
    (re.compile(r"^mola128_mola64_merge_90Nto90S_SimpleC_clon0$"), "mars_elev"),
    (re.compile(r"^Gale_DEM_SMG_1m$"), "mars_gale"),
    (re.compile(r"^DEM_1m_VictoriaCrater$"), "mars_victoria"),
)


#: 수성 (wetherilli 194) — 화성처럼 표고를 그린 판(색 음영·음영)을 켜면 MESSENGER 665 m DEM 의 높이를 낸다. 점묶음의 표고
#: (`mercury_values`)와 같은 서비스다. 지역 DEM(`MSGR_*_DEM_*`)은 씨앗에 타일이 없어 화면에 서지 않는다 — 넣지 않았다
MERCURY_VALUES = {
    "mercury_elev": ("arcgis", "mercury/Mercury_Messenger_USGS_DEM_Global_665m_v2", "높이 — 수성 기준구 2439.4 km", "m", 1,
                     -12000, 12000, 0, "MESSENGER · USGS 665 m"),
}
_MERCURY_VALUE_IDS = (
    (re.compile(r"^Mercury_Messenger_USGS_DEM_665m_v2_Hillshade(Color)?$"), "mercury_elev"),
    (re.compile(r"^Mercury_Messenger_USGS_ClrShade_Global_2km$"), "mercury_elev"),
)


def value_key(body: str, label: str) -> str:
    """씨앗의 판 → 누른 자리의 값 갈래. 없으면 빈 칸. 달·화성(wetherilli 192)·수성(194)."""
    if body == "mars":
        return next((key for pattern, key in _MARS_VALUE_IDS if pattern.match(label)), "")
    if body == "mercury":
        return next((key for pattern, key in _MERCURY_VALUE_IDS if pattern.match(label)), "")
    if body != "moon":
        return ""
    for pattern, key in _VALUE_IDS:
        m = pattern.match(label)
        if not m:
            continue
        if key in ("thick", "cmi"):
            return key + m.group(1)
        if key == "cf":
            return f"cf_{m.group(1)}_{m.group(2)}"
        if key == "tbol":
            return f"tbol_{m.group(1)}"
        if key == "grav":
            return f"grav:{m.group(1)}:{m.group(2)}"
        if key == "slope":
            return f"slope:LRO_NAC_{m.group(1)}"
        return key
    return ""


def value_at(key: str, lon: float, lat: float) -> dict:
    """`{"rows": [[이름, "16.7 wt%"], ["출처", …]]}` — 자료 밖이면 rows 가 빈다. 이름은 한국어 원문이다."""
    if key in MARS_VALUES:
        return _value_rows(MARS_VALUES[key], lon, lat, MARS_SR, _body_base("mars"))
    if key in MERCURY_VALUES:
        return _value_rows(MERCURY_VALUES[key], lon, lat, MERCURY_SR, _body_base("mercury"))
    root, service, label, unit, scale, lo, hi, digits, source = value_spec(key)
    # Kaguya MI 는 남북위 50° 안뿐이다. 밖을 물으면 빈 값이 아니라 "Invalid … parameters" 오류가 온다(2026-09-30)
    if abs(lat) > VALUE_LAT.get(key, 90) or lat < VALUE_NORTH.get(key, -90):
        return {"rows": []}
    geometry = {"points": [[round(lon, 6), round(lat, 6)]], "spatialReference": {"wkid": SR}}
    try:
        data = _json(_get(f"{root}/rest/services/{service}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "f": "json",
        }))
    except TrekError as exc:
        # 한 자리만 덮는 판(NAC 경사·Mini-RF, wetherilli 236)은 판 밖을 물으면 빈 값이 아니라 "Invalid … parameters" 가 온다
        if key in LOCAL_VALUES or key.startswith("slope:"):
            if "Invalid" in str(exc):
                return {"rows": []}
        raise
    for sample in data.get("samples") or []:
        try:
            value = float(sample.get("value")) * scale
        except (TypeError, ValueError):
            continue
        if lo <= value <= hi and not math.isnan(value):
            return {"rows": [[label, f"{value:.{digits}f} {unit}".strip()], ["출처", source]]}
    return {"rows": []}


def _value_rows(spec, lon: float, lat: float, sr: int, base: str) -> dict:
    """화성의 한 점 — 달의 `value_at` 과 같은 꼴. 판 밖이면 상류가 오류 JSON 을 주어 rows 가 빈다."""
    root, service, label, unit, scale, lo, hi, digits, source = spec
    geometry = {"points": [[round(lon, 6), round(lat, 6)]], "spatialReference": {"wkid": sr}}
    r = _get(f"{root}/rest/services/{service}/ImageServer/getSamples", {
        "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
        "returnFirstValueOnly": "true", "f": "json",
    }, base=base)
    try:
        data = _json(r)
    except TrekError:
        # 판 밖 — 1 m DEM 은 "Invalid or missing input parameters" 를 200 에 싣는다(2026-10-04). 다른 실패는 그대로 올린다
        if r.status_code == 200 and "Invalid or missing input" in r.text:
            return {"rows": []}
        raise
    for sample in data.get("samples") or []:
        try:
            value = float(sample.get("value")) * scale
        except (TypeError, ValueError):
            continue
        if lo <= value <= hi and not math.isnan(value):
            return {"rows": [[label, f"{value:,.{digits}f} {unit}".strip()], ["출처", source]]}
    return {"rows": []}


# ── 착륙·충돌 지점 (046) ─────────────────────────────────────────────
#
# Trek 의 `Lunar_Landing_Impact_Sites` MapServer — 갈래마다 레이어 하나다(충돌·연착륙·유인 착륙·로버).
# 모두 합쳐 백 곳이 안 된다. 한 번에 통째로 받는다 — 이 서버는 쪽 나누기(`resultRecordCount`)를 받지 않는다.
# 좌표는 달 경위도(GCS_Moon)이고, 속성에 우주선 이름·날짜·NSSDC 링크가 있다

LANDING_SERVICE = "trekarcgis2/rest/services/Lunar_Landing_Impact_Sites/MapServer"
#: 레이어 번호 → 갈래 (화면이 모양·색을 고르고 이름을 옮긴다)
LANDING_KINDS = {0: "impact", 1: "soft", 2: "crewed", 3: "rover"}


def landing_sites() -> list:
    """`[{"name", "kind", "date", "lon", "lat", "link"}]`."""
    out = []
    for layer, kind in LANDING_KINDS.items():
        data = _json(_get(f"{LANDING_SERVICE}/{layer}/query", {
            "where": "1=1", "outFields": "Spacecraft,Date,Link", "returnGeometry": "true", "f": "json"}))
        for feat in data.get("features") or []:
            geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
            try:
                lon, lat = float(geom["x"]), float(geom["y"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({"name": str(attrs.get("Spacecraft") or "").strip(), "kind": kind,
                        "date": " ".join(str(attrs.get("Date") or "").split()),
                        "lon": round(lon, 5), "lat": round(lat, 5),
                        "link": str(attrs.get("Link") or "").strip()})
    return out


# ── 지명 ────────────────────────────────────────────────────────────

def fetch_places(body: str = "moon") -> list:
    """색인의 지명과 착륙지 — `[[이름, 갈래, 경도, 위도], …]`. 사람이 부를 때만 간다.

    지명은 `itemType: nomenclature`(IAU 행성 지명 사전을 옮긴 것), 착륙지는 `bookmark`
    (아폴로·루나·창어 …, 화성은 바이킹·큐리오시티 …)다. 경도는 −180–180 으로 맞춘다."""
    mars = body == "mars"
    r = _get("TrekServices/ws/index/eq/searchItems", {
        "proj": f"urn:ogc:def:crs:EPSG::{BODIES[body][1]}", "start": 0, "rows": 100000,
    }, base=_body_base(body))
    docs = (_json(r).get("response") or {}).get("docs") or []
    out, seen = [], set()
    for doc in docs:
        kind = doc.get("itemType")
        if kind not in ("nomenclature", "bookmark"):
            continue
        name = str(doc.get("title") or "").strip()
        point = _center(doc)
        if not name or point is None:
            continue
        # 화성의 북마크에는 착륙지 말고도 둘러보기("Major Features")·영화("The Martian Path")가 섞여 있다
        if mars and kind == "bookmark" and not _MARS_LANDING.search(name):
            continue
        # 갈래는 "Lacus, lacūs" 처럼 단수·복수를 적는데, 복수 쪽이 상류에서 글자가 깨져 온다
        # ("lac?à?½s", 2026-09-29). 쉼표 앞의 단수만 쓴다
        # 달은 갈래를 `productType` 에, 화성은 `productCat2` 에 적는다 (2026-09-29). 수성은 `productType` 이
        # "nomenclature" 뿐이고 갈래는 `keyword` 에 있다 — "Crater, craters" (wetherilli P10)
        keyword = doc.get("keyword") or []
        group = ("Landing site" if kind == "bookmark"
                 else str((keyword[0] if body == "mercury" and keyword else "")
                          or (doc.get("productType") if doc.get("productType") != "nomenclature" else "")
                          or doc.get("productCat2") or "Feature").split(",")[0].strip())
        key = (name.lower(), group)
        if key in seen:
            continue
        seen.add(key)
        lon, lat = point
        out.append([name, group, round(lon, 4), round(lat, 4)])
    out.sort(key=lambda row: row[0].lower())
    return out


_MARS_LANDING = re.compile(r"Landing Site|^Viking \d")


def _center(doc: dict):
    bbox = str(doc.get("bbox") or "")
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
    except ValueError:
        return None
    lon, lat = (w + e) / 2, (s + n) / 2
    if lon > 180:
        lon -= 360
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lon, lat


def search_places(places: list, query: str, limit: int = 12) -> list:
    """이름으로 찾는다. 앞이 맞는 것이 먼저, 그다음 들어 있는 것. 대소문자를 가리지 않는다."""
    q = query.strip().lower()
    if not q:
        return []
    head = [p for p in places if p[0].lower().startswith(q)]
    rest = [p for p in places if q in p[0].lower() and not p[0].lower().startswith(q)]
    # 착륙지는 앞에 — "Apollo" 를 치면 크레이터 Apollo 보다 착륙지가 먼저다
    head.sort(key=lambda p: (p[1] != "Landing site", len(p[0])))
    return [{"name": p[0], "kind": p[1], "lon": p[2], "lat": p[3]} for p in (head + rest)[:limit]]


def load_places(path) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return data.get("places") or []


# ── 화성 (058) ───────────────────────────────────────────────────────
#
# 달과 같은 틀이다 — 지질도는 MapServer `export`·`identify`·`legend`, 표고는 ImageServer, 착륙지는
# MapServer `query`. 주소만 `settings.TREK_MARS_URL` 밑이고 서비스가 모두 `trekarcgis/` 에 있다.
# 영상 배경(Viking·THEMIS·MOLA 음영·HiRISE)은 달처럼 브라우저가 곧장 부른다.

MARS_ATTRIBUTION = ("Geologic Map of Mars 1:20M (Tanaka et al., 2014, USGS SIM 3292) · "
                    "MOLA–HRSC blended DEM (NASA/GSFC, ESA/DLR/FU Berlin) · via NASA Mars Trek")
#: 상류에 적는 화성 경위도의 코드 (ESRI GCS_Mars_2000). 우리 이름은 `IAU_2015:49900`
MARS_SR = 104905
#: 화성 반지름 (IAU 2015 의 평균 적도 반지름, 구로 다룬다 — 화면의 Cesium 도 구다)
MARS_RADIUS = 3396190.0
MARS_GEOLOGY = "SIM3292_Global_Geology"
#: MOLA 와 HRSC 를 섞은 200 m 표고(S16, 화성 기준면 — 아레오이드 — 에서 잰 높이). **줄인 판(피라미드)이 없어**
#: 넓게 물으면 9 초 걸리거나(90° 네모) 400 을 준다(반구, 2026-09-29). 그래서 멀리서는 MOLA 128 ppd(463 m, 같은
#: 기준면)를 쓴다 — 이쪽은 줄인 판이 있어 어느 넓이든 0.8 초다. 점의 표고(`mars_values`)는 한 점씩이라 늘 200 m
MARS_DEM = "Mars_MOLA_blend200ppx_HRSC_DEM_clon0dd_200mpp_lzw"
MARS_DEM_COARSE = "mola128_mola64_merge_90Nto90S_SimpleC_clon0"
#: 이 줌부터 200 m 판 — 줌 8 의 한 장이 0.7° 네모라 곧 온다
MARS_DEM_FINE_ZOOM = 8
#: 지질도는 1:2000만이라 줌 7(한 픽셀 약 460 m)이면 선이 다 보인다. 가까이 가도 흐리지 않게 11 까지
MARS_MAX_ZOOM = 11
#: 200 m 표고 — 줌 9 의 한 칸(0.35° ÷ 64)이 0.0055°(330 m)로 그쯤이다
MARS_DEM_MAX_ZOOM = 9
#: 화성의 표고는 −8.2 km(헬라스)에서 +21.2 km(올림푸스 몬스)다. 자료 밖은 S16 의 −32768
MARS_ELEV_RANGE = (-9000.0, 22000.0)
MARS_ELEV_SOURCE = "mola-hrsc-200m"
MARS_ELEV_DATUM = "mars-areoid"

MARS_FIELDS = (("Unit", "단위"), ("UnitDesc", "이름"))

#: 화성의 지질시대 — 셋이고 앞에 전기·중기·후기가 붙는다. ICS 밖이라 한글판 표가 없다. 이름은 시대를 딴
#: 땅(노아키스 대지·헤스페리아 평원·아마조니스 평원)을 따라 적었다 — 한국어판만 옮긴다(P05 처럼 사람이 다시 본다)
MARS_PERIODS_KO = {"Amazonian": "아마조니스기", "Hesperian": "헤스페리아기", "Noachian": "노아키스기"}
MARS_EPOCHS_KO = {"Early": "전기", "Middle": "중기", "Late": "후기"}


def mars_age(desc: str) -> str:
    """단위 이름 앞머리의 시대 — "Early Hesperian basin unit" → "Early Hesperian",
    "Amazonian and Hesperian impact unit" → "Amazonian and Hesperian"."""
    words = []
    for word in str(desc or "").split():
        if word in MARS_PERIODS_KO or word in MARS_EPOCHS_KO or (word == "and" and words):
            words.append(word)
        else:
            break
    while words and words[-1] == "and":
        words.pop()
    return " ".join(words)


def mars_period(age: str) -> str:
    """범례를 묶는 머리 — 둘에 걸친 것은 앞의 것(더 젊은 쪽)이다. 달의 `age_of_unit` 과 같은 규칙."""
    for word in age.split():
        if word in MARS_PERIODS_KO:
            return word
    return ""


def mars_age_ko(age: str) -> str:
    """"Early Hesperian" → "헤스페리아기 전기", "Amazonian and Hesperian" → "아마조니스기–헤스페리아기"."""
    parts, epoch = [], ""
    for word in age.split():
        if word in MARS_EPOCHS_KO:
            epoch = MARS_EPOCHS_KO[word]
        elif word in MARS_PERIODS_KO:
            parts.append(f"{MARS_PERIODS_KO[word]} {epoch}".strip())
            epoch = ""
    return "–".join(parts) or age


def _mars(path: str, params: dict):
    return _get(f"trekarcgis/rest/services/{path}", params, base=settings.TREK_MARS_URL)


def mars_tile(z: int, x: int, y: int) -> bytes:
    """화성 지질도 타일 한 장 (256 px PNG). Trek 이 USGS 의 색으로 칠한다."""
    w, s, e, n = tile_bbox(z, x, y)
    return _image(_mars(f"{MARS_GEOLOGY}/MapServer/export", {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": MARS_SR, "imageSR": MARS_SR, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


# ── 화성 극 격자 (065) ──
#
# 달의 극 격자(052)와 같은 꼴이다 — 극 평사도법, 극에서 축척 1, 줌 0 이 한 장, 한 장이 줌마다 반씩. 다른 것 둘.
#
# - **구의 반지름이 극 반지름(3 376.2 km)이다.** Trek 의 화성 극지 판(`…_np`·`…_sp`)이 WKT 에 그렇게 적는다
#   (`Mars_2000_Sphere_Polar`). 경위도·등거리 원통의 3 396.19 km 와 20 km 다르다 — 이것으로 옮겨야 극 영상과
#   점이 맞는다. 그래서 PSDI 의 `IAU_2015:49930`·`49935`(평균 적도 반지름의 구)라 부르지 않고 Trek 색인의
#   이름(`IAU2000:49918` 북·`49920` 남)을 쓴다
# - **격자의 반폭은 1 809 300.127 m 다.** WMTSCapabilities 는 왼쪽 위를 (−1 821 000, 1 821 000)으로 적지만 같은
#   문서의 축척(1:50 482 700.9)은 1 809 300 에서 나오고, 극 WMTS 한 장과 같은 판의 ArcGIS `export` 를 맞대 보면
#   1 809 300 에서 한 픽셀도 어긋나지 않는다(2026-09-30, 남·북 둘). 극 반지름의 구에서 꼭 위도 60° 다
#
# 지질도(SIM 3292)는 극지 판이 없다. MapServer `export` 에 극 평사도법 WKT 를 `bboxSR`·`imageSR` 로 주면
# Trek 이 옮겨 그려 준다(한 장 0.8 초) — 달처럼 극지 판을 부르는 대신 이 길이다.

MARS_POLAR_RADIUS = 3376200.0
MARS_POLAR_HALF = 1809300.127
_MARS_POLAR_WKT = (
    'PROJCS["Mars_{p}polar_Sphere_Polar",GEOGCS["GCS_Mars_2000_Sphere_Polar",'
    'DATUM["D_Mars_2000_Sphere_Polar",SPHEROID["Mars_2000_Sphere_Polar",3376200.0,0.0]],'
    'PRIMEM["Reference_Meridian",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Stereographic_{pole}_Pole"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],'
    'PARAMETER["central_meridian",0.0],PARAMETER["standard_parallel_1",{lat}],UNIT["Meter",1.0]]')
MARS_POLAR_WKT = {
    "n": _MARS_POLAR_WKT.format(p="N", pole="North", lat="90.0"),
    "s": _MARS_POLAR_WKT.format(p="S", pole="South", lat="-90.0"),
}


def mars_polar_tile_bbox(z: int, x: int, y: int) -> tuple:
    """화성 극 격자 한 장의 (서, 남, 동, 북) — 극 평사도법 미터."""
    span = 2 * MARS_POLAR_HALF / 2 ** z
    west = -MARS_POLAR_HALF + x * span
    north = MARS_POLAR_HALF - y * span
    return west, north - span, west + span, north


def mars_polar_to_lonlat(x: float, y: float, pole: str) -> tuple:
    rho = math.hypot(x, y)
    lat = 90.0 - math.degrees(2 * math.atan2(rho, 2 * MARS_POLAR_RADIUS))
    if pole == "n":
        return math.degrees(math.atan2(x, -y)), lat
    return math.degrees(math.atan2(x, y)), -lat


def mars_lonlat_to_polar(lon: float, lat: float, pole: str) -> tuple:
    phi, lam = math.radians(lat), math.radians(lon)
    if pole == "n":
        rho = 2 * MARS_POLAR_RADIUS * math.tan(math.pi / 4 - phi / 2)
        return rho * math.sin(lam), -rho * math.cos(lam)
    rho = 2 * MARS_POLAR_RADIUS * math.tan(math.pi / 4 + phi / 2)
    return rho * math.sin(lam), rho * math.cos(lam)


def mars_polar_tile(pole: str, z: int, x: int, y: int) -> bytes:
    """극 격자의 화성 지질도 타일 (065). Trek 이 SIM 3292 를 극 평사도법으로 옮겨 그린다."""
    if pole not in MARS_POLAR_WKT:
        raise TrekError("극이 아니다")
    w, s, e, n = mars_polar_tile_bbox(z, x, y)
    sr = json.dumps({"wkt": MARS_POLAR_WKT[pole]}, separators=(",", ":"))
    return _image(_mars(f"{MARS_GEOLOGY}/MapServer/export", {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": sr, "imageSR": sr, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


def mars_identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 지질 단위 — `{"unit": "eHv", "age": "Early Hesperian", "rows": […]}`. 없으면 None."""
    d = 0.5
    data = _json(_mars(f"{MARS_GEOLOGY}/MapServer/identify", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": MARS_SR,
        "layers": "all", "tolerance": 1, "returnGeometry": "false", "f": "json",
        "mapExtent": f"{lon - d},{lat - d},{lon + d},{lat + d}", "imageDisplay": "200,200,96",
    }))
    hits = data.get("results") or []
    if not hits:
        return None
    attrs = hits[0].get("attributes") or {}
    rows = [(label, str(attrs[key]).strip()) for key, label in MARS_FIELDS
            if str(attrs.get(key) or "").strip()]
    return {"unit": str(attrs.get("Unit") or ""), "age": mars_age(attrs.get("UnitDesc") or ""), "rows": rows}


def mars_legend() -> list:
    """단위의 범례 — 이름에 기호가 없어(렌더러가 `UnitDesc` 로 칠한다) 기호는 `query` 로 따로 받아 붙인다."""
    data = _json(_mars(f"{MARS_GEOLOGY}/MapServer/legend", {"f": "json"}))
    codes = {}
    try:
        got = _json(_mars(f"{MARS_GEOLOGY}/MapServer/0/query", {
            "where": "1=1", "outFields": "Unit,UnitDesc", "returnDistinctValues": "true",
            "returnGeometry": "false", "f": "json"}))
        for feat in got.get("features") or []:
            a = feat.get("attributes") or {}
            codes[str(a.get("UnitDesc") or "")] = str(a.get("Unit") or "")
    except TrekError:
        pass                        # 기호가 없어도 범례는 선다
    out = []
    for layer in data.get("layers") or []:
        for item in layer.get("legend") or []:
            image = item.get("imageData")
            if not image:
                continue
            label = item.get("label") or ""
            age = mars_age(label)
            out.append({"label": label, "unit": codes.get(label, ""), "age": mars_period(age),
                        "image": f"data:{item.get('contentType') or 'image/png'};base64,{image}"})
    return out


def mars_dem_tile(z: int, x: int, y: int) -> bytes:
    """화성 표고 격자 한 장 — 65×65 Terrarium PNG. 달의 `dem_tile` 과 같은 수(반 칸 넓혀 묻기)다.
    줌 `MARS_DEM_FINE_ZOOM` 밑은 MOLA 128 ppd, 그 위는 MOLA–HRSC 200 m 다."""
    from PIL import Image

    w, s, e, n = tile_bbox(z, x, y)
    half = (e - w) / (DEM_SIZE - 1) / 2
    service = MARS_DEM if z >= MARS_DEM_FINE_ZOOM else MARS_DEM_COARSE
    r = _mars(f"{service}/ImageServer/exportImage", {
        "bbox": f"{w - half},{s - half},{e + half},{n + half}", "bboxSR": MARS_SR, "imageSR": MARS_SR,
        "size": f"{DEM_SIZE},{DEM_SIZE}", "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    })
    try:
        image = Image.open(io.BytesIO(_image(r)))
        image.load()
    except (OSError, ValueError) as exc:
        raise TrekError(f"표고 TIFF 를 읽지 못했다: {exc}") from exc
    if image.mode != "F" or image.size != (DEM_SIZE, DEM_SIZE):
        raise TrekError(f"표고의 꼴이 다르다 ({image.mode}, {image.size})")
    lo, hi = MARS_ELEV_RANGE
    out = Image.new("RGB", (DEM_SIZE, DEM_SIZE))
    out.putdata([_terrarium_rgb(v if lo < v < hi and not math.isnan(v) else 0.0) for v in image.getdata()])
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def mars_values(points: dict) -> dict:
    """`{id: (lat, lon)}` → `{id: 표고 m}` — 화성 기준면(아레오이드)에서 잰 높이. 달의 `lola_values` 와 같은 길(GET)."""
    ids = list(points)
    out = {}
    lo, hi = MARS_ELEV_RANGE
    for start in range(0, len(ids), SAMPLE_CHUNK):
        chunk = ids[start:start + SAMPLE_CHUNK]
        geometry = {"points": [[round(points[i][1], 6), round(points[i][0], 6)] for i in chunk],
                    "spatialReference": {"wkid": MARS_SR}}
        data = _json(_mars(f"{MARS_DEM}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "interpolation": "RSP_BilinearInterpolation", "f": "json",
        }))
        for sample in data.get("samples") or []:
            try:
                value = float(sample.get("value"))
                index = int(sample.get("locationId"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(chunk) and lo < value < hi:
                out[chunk[index]] = value
    return out


#: 착륙선·로버마다 Trek 이 이야기 지점(착륙 자리·열 차폐막·낙하산·들른 곳)을 레이어 하나로 둔다.
#: (서비스, 임무, 갈래) — 갈래는 화면이 색을 고른다
MARS_WAYPOINTS = (
    ("viking_waypoints", "Viking 1", "lander"), ("viking2_waypoints", "Viking 2", "lander"),
    ("sojourner_waypoints", "Mars Pathfinder", "rover"), ("spirit_waypoints", "Spirit", "rover"),
    ("opportunity_waypoints", "Opportunity", "rover"), ("phoenix_waypoints", "Phoenix", "lander"),
    ("curiosity_waypoints", "Curiosity", "rover"), ("InSight_waypoints", "InSight", "lander"),
    ("mars2020_waypoints", "Perseverance", "rover"),
)
#: 로버가 달린 길 — (서비스, 임무). 퍼서비어런스는 솔(sol)마다 선이 갈려 있다
MARS_TRAVERSES = (("spirit_path", "Spirit"), ("opportunity_path", "Opportunity"),
                  ("curiosity_path", "Curiosity"), ("Perseverance_Traverse_Path", "Perseverance"))


def mars_landings() -> list:
    """`[{"name", "mission", "kind", "lon", "lat"}]` — 착륙선·로버의 이야기 지점. 모두 백 곳이 안 된다."""
    out = []
    for service, mission, kind in MARS_WAYPOINTS:
        data = _json(_mars(f"{service}/MapServer/0/query", {
            "where": "1=1", "outFields": "name", "returnGeometry": "true", "f": "json"}))
        for feat in data.get("features") or []:
            geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
            try:
                lon, lat = float(geom["x"]), float(geom["y"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({"name": str(attrs.get("name") or "").strip(), "mission": mission, "kind": kind,
                        "lon": round(lon, 6), "lat": round(lat, 6)})
    return out


def mars_traverses() -> list:
    """`[{"mission", "paths": [[[lon, lat], …], …]}]` — 로버가 달린 길. 좌표는 여섯째 자리(수 cm)까지."""
    out = []
    for service, mission in MARS_TRAVERSES:
        data = _json(_mars(f"{service}/MapServer/0/query", {
            "where": "1=1", "outFields": "FID", "returnGeometry": "true", "f": "json"}))
        paths = []
        for feat in data.get("features") or []:
            for path in (feat.get("geometry") or {}).get("paths") or []:
                line = [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in path if len(p) >= 2]
                if len(line) >= 2:
                    paths.append(line)
        out.append({"mission": mission, "paths": paths})
    return out


# ── 수성 (wetherilli P10) ────────────────────────────────────────────
#
# 화성과 같은 틀이다 — 주소만 `settings.TREK_MERCURY_URL` 밑이다. **ArcGIS 의 뿌리가 다르다** — 달·화성의
# `trekarcgis/` 가 아니라 `arcgis/rest/services/mercury/` 다(2026-10-02, `trekarcgis` 는 404).
# 지질도는 Trek 에서 받지 않는다 — Trek 의 5M 도폭 일곱은 색인·Capabilities 만 있고 타일이 404 다(2026-10-02). USGS 1:500만
# 도폭 합본을 우리가 굽는다(`mercurymap.py`, wetherilli 144). 영상 배경(MESSENGER MDIS)은 브라우저가 곧장 부른다.

MERCURY_ATTRIBUTION = ("MESSENGER MDIS (NASA/JHUAPL/Carnegie Institution of Washington) · "
                       "MESSENGER DEM v2 (USGS, Becker et al., 2016) · via NASA Mercury Trek")
#: 상류에 적는 수성 경위도의 코드 (ESRI GCS_Mercury_2000). 우리 이름은 `IAU_2015:19900`
MERCURY_SR = 104974
#: 수성 반지름 — Trek 의 경위도(`GCS_Mercury_2000`)가 적는 것. 구로 다룬다
MERCURY_RADIUS = 2439700.0
#: USGS 의 MESSENGER 표고 665 m(64 ppd). 정수(S16)이고 반지름 2 439.4 km 구에서 잰 높이다(서비스의 WKT)
MERCURY_DEM = "Mercury_Messenger_USGS_DEM_Global_665m_v2"
#: 64 ppd — 줌 7 의 한 칸(1.41° ÷ 64)이 0.022° 로 판의 한 칸(0.0156°)쯤이다
MERCURY_DEM_MAX_ZOOM = 7
#: 수성의 높이는 ±10 km 안이다. 자료 밖은 S16 의 −32768
MERCURY_ELEV_RANGE = (-12000.0, 12000.0)
MERCURY_ELEV_SOURCE = "messenger-usgs-665m"
MERCURY_ELEV_DATUM = "mercury-sphere"


def _mercury(path: str, params: dict):
    return _get(f"arcgis/rest/services/mercury/{path}", params, base=settings.TREK_MERCURY_URL)


def mercury_dem_tile(z: int, x: int, y: int) -> bytes:
    """수성 표고 격자 한 장 — 65×65 Terrarium PNG. 달의 `dem_tile` 과 같은 수(반 칸 넓혀 묻기)다."""
    from PIL import Image

    w, s, e, n = tile_bbox(z, x, y)
    half = (e - w) / (DEM_SIZE - 1) / 2
    r = _mercury(f"{MERCURY_DEM}/ImageServer/exportImage", {
        "bbox": f"{w - half},{s - half},{e + half},{n + half}", "bboxSR": MERCURY_SR, "imageSR": MERCURY_SR,
        "size": f"{DEM_SIZE},{DEM_SIZE}", "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    })
    try:
        image = Image.open(io.BytesIO(_image(r)))
        image.load()
    except (OSError, ValueError) as exc:
        raise TrekError(f"표고 TIFF 를 읽지 못했다: {exc}") from exc
    if image.mode != "F" or image.size != (DEM_SIZE, DEM_SIZE):
        raise TrekError(f"표고의 꼴이 다르다 ({image.mode}, {image.size})")
    lo, hi = MERCURY_ELEV_RANGE
    out = Image.new("RGB", (DEM_SIZE, DEM_SIZE))
    out.putdata([_terrarium_rgb(v if lo < v < hi and not math.isnan(v) else 0.0) for v in image.getdata()])
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def mercury_values(points: dict) -> dict:
    """`{id: (lat, lon)}` → `{id: 표고 m}` — 반지름 2 439.4 km 구에서 잰 높이. 화성의 `mars_values` 와 같은 길(GET)."""
    ids = list(points)
    out = {}
    lo, hi = MERCURY_ELEV_RANGE
    for start in range(0, len(ids), SAMPLE_CHUNK):
        chunk = ids[start:start + SAMPLE_CHUNK]
        geometry = {"points": [[round(points[i][1], 6), round(points[i][0], 6)] for i in chunk],
                    "spatialReference": {"wkid": MERCURY_SR}}
        data = _json(_mercury(f"{MERCURY_DEM}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "interpolation": "RSP_BilinearInterpolation", "f": "json",
        }))
        for sample in data.get("samples") or []:
            try:
                value = float(sample.get("value"))
                index = int(sample.get("locationId"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(chunk) and lo < value < hi:
                out[chunk[index]] = value
    return out


# ── Trek 판 목록 (060) — 달·화성이 함께 쓴다 ────────────────────────
#
# Trek 색인(`searchItems`)에는 지명 말고도 판(product·dataset)이 달 1 200 남짓, 화성 240 남짓 있다
# (2026-09-30). 거의 다 영상 배경과 같은 WMTS(`tiles/<몸>/EQ/<판>/1.0.0/…`)라 브라우저가 곧장 부르면
# 되고, 판을 하나씩 손으로 넣지 않고 **목록을 씨앗으로 받아 둔다**(`manage.py fetch_trek_catalog`).
# 씨앗은 KIGAM 카탈로그처럼 사람이 한글 제목·숨김만 손질한다.
#
# 색인이 `serviceTypes: Mosaic` 이라 적어도 WMTS 가 없는 판이 있다 — 화성의 지형 형태 조사(선상지·골짜기망 …)는
# MapServer 만 있다(2026-09-30, 화성 세션이 찔러 봤다). 그래서 판마다 `WMTSCapabilities.xml` 을 한 번 물어 포맷과
# 줌 끝을 적고, 404 면 타일이 아닌 판(`kind: null`)으로 둔다. 줌 끝은 손으로 한 장씩 재 둔 값(Kaguya 10·LOLA 음영 6
# ·NAC 아폴로 12 16)과 같았다.

#: 몸 → (Trek 타일 경로의 이름, 상류에 적는 경위도 코드)
BODIES = {"moon": ("Moon", SR), "mars": ("Mars", 104905), "mercury": ("Mercury", 104974)}

#: 색인의 갈래(`productCat1`) → 레이어군 이름 (한국어, 영어). 목록에 이 차례로 선다. 없는 갈래는 맨 끝 "기타"
CATEGORIES = (
    ("Geology", "지질도", "Geology"),
    ("Mineralogy", "광물·원소", "Mineralogy"),
    ("Mineral", "광물·원소", "Mineralogy"),
    ("Spectrometer", "광물·원소", "Mineralogy"),
    ("Algebraic", "광물·원소", "Mineralogy"),
    ("Gravity", "중력", "Gravity"),
    ("Crust", "지각", "Crust"),
    ("Radiometer", "열·복사", "Thermal"),
    ("Temperature", "열·복사", "Thermal"),
    ("ThermalInertia", "열·복사", "Thermal"),
    ("Imagery", "영상", "Imagery"),
    ("Topography", "지형", "Topography"),
    ("Terrain", "경사·거칠기", "Slope & roughness"),
    ("Illumination", "빛·그늘", "Illumination"),
    ("Landforms", "지형 형태", "Landforms"),
    ("Surface Feature", "표면 암괴", "Surface features"),
    ("Hazard", "착륙 위험", "Landing hazards"),
    ("Feature", "지점·경로", "Sites & paths"),
    ("Landing Site", "지점·경로", "Sites & paths"),
    ("Exploration Zones", "지점·경로", "Sites & paths"),
    ("Index", "색인", "Index"),
)
OTHER_CATEGORY = ("기타", "Other")
#: 값을 색으로 칠한 갈래 — Trek 의 범례 그림(`TrekWS/rest/cat/legend/stream`)을 붙인다. 영상·음영에는 범례가 없다.
#: 지형은 색 음영(`ColorHillshade`)만 높이 범례가 있다
_LEGEND_CATS = {"Mineralogy", "Mineral", "Spectrometer", "Algebraic", "Gravity", "Crust", "Radiometer",
                "Temperature", "ThermalInertia", "Terrain", "Illumination", "Hazard", "Surface Feature"}

#: 이미 화면이 따로 쓰는 판 — 영상 배경·극지 판·착륙지 사진(`moon.js`·`mars.js`). 목록에 두 번 세우지 않는다
IN_USE = {
    "moon": {"Kaguya_TCortho_Mosaic_Global_4096ppd", "LRO_WAC_Mosaic_Global_303ppd_v02",
             "LRO_LOLA_Shade_Global_256ppd_v06", "LRO_NAC_Apollo12_Mosaic_p", "LRO_NAC_Apollo15_Mosaic_p",
             "LRO_NAC_Apollo16_Mosaic_p", "NAC_DTM_APOLLO17_MOSAIC_120CM",
             "LRO_NAC_Post_Landing_OrthoMosaic_1mpp_IM_1_LandingSite",
             "apollo11_26cm_mosaic_byte_geo_1_2_highContrast", "apollo14_28cm_mosaic_byte_geo_1_2_highContrast",
             *LAYERS.values(), "Lunar_Anthropogenic_Impacts_and_Spacecraft"},
    "mars": {"Mars_Viking_MDIM21_ClrMosaic_global_232m", "THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018",
             "Mars_MGS_MOLA_ClrShade_merge_global_463m", "Mars_MOLA_blend200ppx_HRSC_Shade_clon0dd_200mpp_lzw"},
    "mercury": {"Mercury_MESSENGER_mosaic_global_250m_2013", "Mercury_MESSENGER_MDIS_Basemap_BDR_Mosaic_Global_166m",
                "Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m",
                "Mercury_Messenger_USGS_DEM_665m_v2_HillshadeColor", "Mercury_Messenger_USGS_DEM_665m_v2_Hillshade"},
}

#: 처음 들어올 때 숨겨 두는 갈래 — 착륙 공학용(위험·암괴·색인)이거나, 값을 회색으로 칠한 판(같은 것을 칠한 짝이
#: 있다)이거나, 표고 값 그대로라 그림으로는 읽히지 않는 판. 숨김은 씨앗의 `hide` 이고 사람이 뒤집을 수 있다
_HIDE_CATS = {"Hazard", "Surface Feature", "Index"}
_HIDE_CAT2 = {"Confidence", "Confidence Colorized", "Precision", "Grayscale", "DEM", "Slope", "Roughness"}
_GRAY = re.compile(r"\b(Gray|Grey)(scale)?\b", re.I)


def category(cat1: str) -> tuple:
    """색인의 갈래 → (레이어군 한국어, 영어, 차례)."""
    for i, (key, ko, en) in enumerate(CATEGORIES):
        if key == cat1:
            return ko, en, i
    return OTHER_CATEGORY[0], OTHER_CATEGORY[1], len(CATEGORIES)


def hidden_by_default(body: str, item: dict) -> bool:
    if item["id"] in IN_USE.get(body, ()):
        return True
    if item.get("cat") in _HIDE_CATS or item.get("cat2") in _HIDE_CAT2:
        return True
    return bool(_GRAY.search(item.get("title") or ""))


def _bbox(text) -> list | None:
    try:
        w, s, e, n = (float(v) for v in str(text).split(","))
    except (TypeError, ValueError):
        return None
    return [round(w, 5), round(s, 5), round(e, 5), round(n, 5)]


def catalog_items(body: str) -> list:
    """색인의 판 — `[{id, title, cat, cat2, mission, instrument, coverage, bbox}]`. 지명·북마크는 뺀다."""
    name, sr = BODIES[body]
    r = _get("TrekServices/ws/index/eq/searchItems", {
        "proj": f"urn:ogc:def:crs:EPSG::{sr}", "start": 0, "rows": 100000,
    }, base=_body_base(body))
    docs = (_json(r).get("response") or {}).get("docs") or []
    out, seen = [], set()
    for doc in docs:
        if doc.get("itemType") not in ("product", "dataset"):
            continue
        label = str(doc.get("productLabel") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        out.append({"id": label, "uuid": doc.get("item_UUID") or "",
                    "title": " ".join(str(doc.get("title") or label).split()),
                    "cat": doc.get("productCat1") or "", "cat2": doc.get("productCat2") or "",
                    "mission": doc.get("mission") or "", "instrument": doc.get("instrument") or "",
                    "coverage": doc.get("coverage") or "", "bbox": _bbox(doc.get("bbox"))})
    for item in EXTRA_ITEMS.get(body, ()):
        if item["id"] not in seen:
            out.append({k: v for k, v in item.items() if k != "image"})
    return out


#: 색인(`searchItems`)에 없는 판 (wetherilli 150) — 서비스 목록에서 찾았다. 씨앗 뽑기가 색인의 판처럼 WMTS 를 묻는다.
#: `image` 는 WMTS 가 없는 판의 ImageServer — 우리 문이 `exportImage` 로 굽는다(`map_tile`). `pole` 은 그 ImageServer 가 제
#: 투영으로 극 평사도법인 판 — 극 평면에서는 극 격자로 곧장 받는다(`map_polar_tile`). 경위도 타일을 극으로 다시 옮기면 극
#: 둘레가 바퀴살처럼 찢어진다(2026-10-02)
EXTRA_ITEMS = {"moon": [
    *({"id": label, "uuid": "", "title": title, "cat": "Spectrometer", "cat2": "Abundance", "mission": "KPLO",
       "instrument": "KGRS", "coverage": "Global", "bbox": [-180.0, -90.0, 180.0, 90.0]}
      for label, title in (("KPLO_KGRS_Potassium_2ppd", "KPLO KGRS Potassium"),
                           ("KPLO_KGRS_Uranium_2ppd", "KPLO KGRS Uranium"),
                           ("KGRS_Th_LG_smooth", "KPLO KGRS Thorium (LG, smoothed)"),
                           ("KPLO_KGRS_Thermal_Neutron_2ppd", "KPLO KGRS Thermal Neutron"),
                           ("KGRS_Thermal_Neutron_LG", "KPLO KGRS Thermal Neutron (LG)"))),
    {"id": "np_feo_mlemelin_031417", "uuid": "", "title": "North Pole FeO (Lemelin)", "cat": "Mineralogy",
     "cat2": "Abundance", "mission": "LRO", "instrument": "", "coverage": "Regional", "bbox": [-180.0, 50.0, 180.0, 90.0],
     "image": "trekarcgis/rest/services/np_feo_mlemelin_031417/ImageServer", "pole": "n"},
    *({"id": label, "uuid": "", "title": title, "cat": "Temperature", "cat2": "Ice stability depth", "mission": "LRO",
       "instrument": "Diviner", "coverage": "Regional", "bbox": [-180.0, 80.0, 180.0, 90.0],
       "image": f"trekarcgis/rest/services/{label}/ImageServer", "pole": "n"}
      for label, title in (("np_ice_depth_new_240m_mat_today_27_Oct_2016", "North Pole Ice Stability Depth (today)"),
                           ("np_ice_depth_new_240m_mat_paleo_27_Oct_2016", "North Pole Ice Stability Depth (paleo spin axis)"))),
]}


def tiles_root(body: str) -> str:
    """판 타일의 뿌리 — `https://trek.nasa.gov/tiles/Moon/EQ`. 색인 주소의 호스트를 따른다."""
    base = _body_base(body)
    host = base.split("://", 1)[-1].split("/", 1)[0]
    return f"{base.split('://', 1)[0]}://{host}/tiles/{BODIES[body][0]}/EQ"


_WMTS = "{http://www.opengis.net/wmts/1.0}"
_OWS = "{http://www.opengis.net/ows/1.1}"


def parse_wmts(xml: bytes) -> dict | None:
    """`WMTSCapabilities.xml` → `{"ext": "png", "max": 10, "z0": 0}`. 경위도 격자(가로 2·세로 1)가 없으면 None."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    fmt = root.findtext(f".//{_WMTS}Layer/{_WMTS}Format") or ""
    levels = {}
    for tm in root.iter(f"{_WMTS}TileMatrix"):
        try:
            levels[int(tm.findtext(f"{_OWS}Identifier"))] = (
                float(tm.findtext(f"{_WMTS}MatrixWidth")), float(tm.findtext(f"{_WMTS}MatrixHeight")))
        except (TypeError, ValueError):
            continue
    # 줌 0(가로 2·세로 1)을 `1` 로 적는 판이 있다 — 타일 주소도 그 번호다(Apollo 15 메트릭 카메라 신뢰도,
    # 2026-09-30). 우리 줌 0 이 상류의 몇 번인지를 `z0` 에 적는다
    z0 = [k for k, v in levels.items() if v == (2.0, 1.0)]
    if not fmt.startswith("image/") or not z0:
        return None
    return {"ext": "jpg" if fmt.endswith(("jpeg", "jpg")) else fmt.split("/", 1)[1],
            "max": max(levels) - z0[0], "z0": z0[0]}


def wmts_info(body: str, label: str) -> dict | None:
    """판 하나의 WMTS — 포맷·줌 끝. 404 면 None(타일이 없는 판). 다른 실패는 `TrekError`."""
    r = _get(f"{label}/1.0.0/WMTSCapabilities.xml", {}, base=tiles_root(body))
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise TrekError(f"NASA Trek 이 받지 않았다 (status={r.status_code})")
    return parse_wmts(r.content)


def tile_exists(body: str, label: str, info: dict, bbox, delay: float = 0.0) -> bool:
    """WMTS 판의 타일이 실제로 있나 — 판 범위의 가운데를 덮는 줌 0 타일 한 장을 받아 본다 (wetherilli 090).

    Capabilities 가 200 인데 타일이 모두 404 인 판이 있다(화성 사구 지대·Hynek 골짜기망 — MapServer 만 둔다,
    wetherilli 080). 좁은 판도 줌 0 타일은 준다(2026-09-30, 달·화성 판 열둘을 줌 0·2·끝에서 받아 보았다 — 있는 판은
    다 200, 없는 판은 다 404). 두 장 다 404 면 False, 다른 실패는 `TrekError`. 두 번 물을 때 사이에 `delay` 초 쉰다."""
    w, s, e, n = bbox or (-180.0, -90.0, 180.0, 90.0)
    first = 0 if (w + e) / 2 < 0 else 1
    # 줌 0 은 두 장이다. 가운데 쪽이 404 면 다른 쪽도 본다 — 범위가 망가진 판이 있다(화성 CTX 11S289E 는 동경
    # 219° 까지라 적어 가운데가 동반구로 가지만 자료는 서경 71° 에 있다)
    for i, x in enumerate((first, 1 - first)):
        if i and delay:
            time.sleep(delay)
        r = _get(f"{label}/1.0.0/default/default028mm/{info.get('z0') or 0}/0/{x}.{info.get('ext') or 'png'}", {},
                 base=tiles_root(body))
        if r.status_code == 404:
            continue
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            raise TrekError(f"NASA Trek 이 타일을 주지 않았다 (status={r.status_code})")
        return True
    return False


# ── 극지 짝 (wetherilli 085) ────────────────────────────────────────
#
# 색인(`index/eq`)은 적도 판만 준다. 몇 판은 Trek 이 극 평사도법으로 따로 구운 짝(`<판>_SP`·`_NP`)을 둔다 —
# 극 평면에서 적도 판을 옮겨 그리면 극 가까이가 성기니, 짝이 있으면 그것을 받는다. 짝을 알려 주는 색인이
# 없어(`index/sp`·`rasters/sp/list.json` 은 404, 2026-09-30) ArcGIS 서비스 목록에서 이름으로 찾는다.


def polar_twins(body: str, delay: float = 0.0) -> dict:
    """`{판: {"s": (경로 뿌리, 서비스 이름, 갈래), …}}` — 서비스 목록에서 `_SP`·`_NP` 로 끝나는 것.
    목록을 셋 받는다 — 사이에 `delay` 초 쉰다. 수성은 극지 판 타일이 없어(`tiles/Mercury/NP` 404, P10) 묻지 않는다."""
    out = {}
    if body == "mercury":
        return out
    for i, root in enumerate(_SERVICE_ROOTS):
        if i and delay:
            time.sleep(delay)
        r = _get(f"{root}/rest/services", {"f": "json"}, base=_body_base(body))
        if r.status_code == 404:
            continue                # 화성은 `trekarcgis` 하나뿐이다 — 2·3 은 404 (2026-10-04, wetherilli 192)
        data = _json(r)
        for s in data.get("services") or []:
            name = str(s.get("name") or "")
            for pole, suffix in POLES.items():
                if name.endswith(suffix):
                    out.setdefault(name[:-len(suffix)], {})[pole] = (root, name, s.get("type") or "")
    if body == "mars":
        _mars_twins(out)
    return out


#: 화성 극 평면이 시작하는 위도 — 판이 이 너머까지 닿아야 극지 길을 둔다(화면의 문턱 65° 보다 넉넉히)
MARS_POLAR_REACH = 60.0


def _mars_twins(out: dict) -> None:
    """화성의 극지 길 (wetherilli 192). 서비스 목록의 `_NP`·`_SP` 는 MOLA 합본 하나뿐이다(2026-10-04). 대신 둘이 있다.

    - **WMTS 판은 `tiles/Mars/NP/<판>_np`** — 영상 배경(065)이 받는 꼴이다. 소문자 꼬리라 서비스 목록으로는 찾지 못한다.
      극까지 닿는 판만 짝 후보로 둔다 — 있는지는 `probe_polar` 가 Capabilities 로 묻는다
    - **MapServer 판은 짝이 없어도 된다.** 우리 문이 화성 극 투영(WKT, 065)으로 `export` 를 물으면 Trek 이 옮겨 그린다 —
      SIM 3292 극 타일과 같은 길이다. 묻지 않고 그 판 자신의 서비스를 적는다(`Self`)"""
    for e in load_catalog("mars"):
        bbox = e.get("bbox") or [-180, -90, 180, 90]
        poles = [p for p, reach in (("n", bbox[3] >= MARS_POLAR_REACH), ("s", bbox[1] <= -MARS_POLAR_REACH)) if reach]
        for pole in poles:
            if pole in out.get(e["id"], {}):
                continue
            if e.get("kind") == "tile":
                out.setdefault(e["id"], {})[pole] = ("", f"{e['id']}_{pole}p", "WMTS")
            elif e.get("kind") == "map" and e.get("ms"):
                out.setdefault(e["id"], {})[pole] = ("", e["ms"], "Self")


def parse_polar_wmts(xml: bytes, body: str = "moon") -> dict | None:
    """극지 판의 `WMTSCapabilities.xml` → `{"ext", "max", "box": [서, 남, 동, 북] m}`. 격자는 우리 극 격자와 같다
    (왼쪽 위 ±1 095 930 m) — 다르면 None. 상류는 줌 0 을 가로 2·세로 1 로 적지만 실제로는 한 장이다.
    화성은 Capabilities 가 왼쪽 위를 ±1 821 000 으로 잘못 적는다 — 참은 ±1 809 300 이다(065). 그래서 모서리를 보지 않고
    범위를 우리 격자 안으로 자른다 (wetherilli 192)"""
    half = MARS_POLAR_HALF if body == "mars" else POLAR_HALF
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    fmt = root.findtext(f".//{_WMTS}Layer/{_WMTS}Format") or ""
    levels = []
    for tm in root.iter(f"{_WMTS}TileMatrix"):
        try:
            corner = [float(v) for v in tm.findtext(f"{_WMTS}TopLeftCorner").split()]
            levels.append(int(tm.findtext(f"{_OWS}Identifier")))
        except (AttributeError, TypeError, ValueError):
            continue
        if body != "mars" and (abs(corner[0] + half) > 1 or abs(corner[1] - half) > 1):
            return None
    try:
        lo = [float(v) for v in root.findtext(f".//{_OWS}BoundingBox/{_OWS}LowerCorner").split()]
        hi = [float(v) for v in root.findtext(f".//{_OWS}BoundingBox/{_OWS}UpperCorner").split()]
    except (AttributeError, ValueError):
        lo, hi = [-half, -half], [half, half]
    if not fmt.startswith("image/") or 0 not in levels:
        return None
    lo, hi = [max(-half, v) for v in lo], [min(half, v) for v in hi]
    return {"ext": "jpg" if fmt.endswith(("jpeg", "jpg")) else fmt.split("/", 1)[1], "max": max(levels),
            "box": [round(lo[0]), round(lo[1]), round(hi[0]), round(hi[1])]}


def polar_wmts_info(body: str, name: str, pole: str) -> dict | None:
    """극지 짝 하나의 WMTS — 없으면 None."""
    root = tiles_root(body).rsplit("/", 1)[0] + ("/NP" if pole == "n" else "/SP")
    r = _get(f"{name}/1.0.0/WMTSCapabilities.xml", {}, base=root)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise TrekError(f"NASA Trek 이 받지 않았다 (status={r.status_code})")
    return parse_polar_wmts(r.content, body)


def probe_polar(body: str, twins: dict, delay: float = 0.0) -> dict:
    """판 하나의 극지 짝(`polar_twins` 의 값)을 물어 씨앗에 적을 꼴로 — `{"s": {"kind": "tile", "ext", "max",
    "box", "name"}}` 나 `{"s": {"kind": "map", "ms"}}`. WMTS 가 먼저다. 둘 다 없는 극은 빠진다. 극 사이에
    `delay` 초 쉰다."""
    out = {}
    for i, (pole, (root, name, kind)) in enumerate(sorted(twins.items())):
        if kind == "Self":                       # 화성 MapServer 판 자신 — 묻지 않는다 (wetherilli 192)
            out[pole] = {"kind": "map", "ms": name}
            continue
        if i and delay:
            time.sleep(delay)
        info = polar_wmts_info(body, name, pole)
        if info:
            out[pole] = {"kind": "tile", "name": name, **info}
        elif kind == "MapServer" or (kind == "ImageServer" and body == "mars"):
            out[pole] = {"kind": "map", "ms": f"{root}/rest/services/{name}/{kind}"}
    return out


def catalog_file(body: str):
    """씨앗 자리 — `data/moon_trek_layers.json`·`data/mars_trek_layers.json`. 저장소에 담는다."""
    return settings.REPO_DIR / "data" / f"{body}_trek_layers.json"


def load_catalog(body: str) -> list:
    """씨앗의 판 — 없거나 깨졌으면 빈 목록(화면은 목록 없이 돈다)."""
    try:
        return json.loads(catalog_file(body).read_text(encoding="utf-8")).get("layers") or []
    except (OSError, ValueError):
        return []


#: 우리 레이어와 같은 자료를 다르게 그린 판 — 누르면 그 레이어의 속성을, 범례 칸에는 그 레이어의 범례를 낸다.
#: Kaguya TC 지질도는 통합 지질도(`units`)의 단위를 Kaguya 지형 카메라 영상 위에 칠한 래스터다 — 단위 기호·색이 같다.
#: SPA 지질도(`spa`)는 Trek 이 속성 없이 주는 그림이고, 속성은 저자들이 낸 원본에서 우리가 읽는다(`spamap.py`)
SAME_AS = {"moon": {"Unified_Geologic_Map_of_the_Moon_RASTER": "units", "SPA_GeoMap_lqbal_et_al": "spa"}}


def _client_polar(polar, pole: str = "") -> dict:
    """씨앗의 극지 짝 → 화면이 쓰는 것. 타일이면 이름·포맷·줌 끝·범위(m), MapServer 면 갈래만(우리 문이 굽는다).
    `pole` 은 판 자신이 그 극의 극 평사도법 ImageServer 인 것 (wetherilli 150)."""
    out = {pole: {"kind": "map"}} if pole else {}
    for pole, p in (polar or {}).items():
        if p.get("kind") == "tile":
            out[pole] = {"kind": "tile", "name": p["name"], "ext": p.get("ext") or "png", "max": p.get("max") or 0,
                         "box": p.get("box")}
        elif p.get("kind") == "map":
            out[pole] = {"kind": "map"}
    return out


def client_catalog(body: str) -> dict:
    """화면에 내리는 목록 — 타일(WMTS·MapServer)이 있고 숨기지 않은 판만, 레이어군으로 묶어서. 페이지에 싣는다.

    `kind` 가 `tile` 이면 브라우저가 Trek 을 곧장, `map` 이면 우리 문(`trek/<몸>/map/…`)을 부른다.

    `bbox` 는 판이 몸 전체를 덮으면 null — 화면이 범위 밖 타일을 거르지 않는다. 제목은 영어(`title`)와
    사람이 붙인 한글(`ko`, 없으면 빈 칸 — 화면이 영어로 낸다) 둘을 다 싣는다."""
    groups = {}
    for e in load_catalog(body):
        if e.get("kind") not in ("tile", "map") or e.get("hide"):
            continue
        ko, en, order = category(e.get("cat") or "")
        bbox = e.get("bbox")
        if bbox and bbox[0] <= -179.9 and bbox[1] <= -89.9 and bbox[2] >= 179.9 and bbox[3] >= 89.9:
            bbox = None
        src = " · ".join(v for v in (e.get("mission"), e.get("instrument")) if v and v != "None")
        g = groups.setdefault(ko, {"ko": ko, "en": en, "order": order, "layers": []})
        legend = (e.get("kind") == "map" or e.get("cat") in _LEGEND_CATS
                  or (e.get("cat") == "Topography" and "Color" in (e.get("cat2") or "")))
        g["layers"].append({"id": e["id"], "kind": e["kind"], "title": e["title"], "ko": e.get("ko") or "",
                            "ext": e.get("ext") or "png",
                            "max": e.get("max") or 0, "z0": e.get("z0") or 0, "bbox": bbox, "src": src,
                            "legend": legend, "same": SAME_AS.get(body, {}).get(e["id"], ""),
                            "polar": _client_polar(e.get("polar"), e.get("pole") or ""), "value": value_key(body, e["id"])})
    out = sorted(groups.values(), key=lambda g: g["order"])
    for g in out:
        del g["order"]
    base = _body_base(body)
    return {"root": tiles_root(body), "legend": f"{base.rstrip('/')}/TrekWS/rest/cat/legend/stream?label=",
            "groups": out}


# ── MapServer 판 (060) — WMTS 가 없는 판 ────────────────────────────
#
# 점·선·면 조사(화성의 골짜기망·선상지 …, 달의 아르테미스 후보·인공물 지점)는 WMTS 가 없고 ArcGIS MapServer 만
# 있다. 지질도처럼 **우리 문이 `export` 로 타일을 굽고 `identify` 로 속성을 읽는다** — 한 틀로 달·화성의 것을 다
# 받는다. 서비스 주소는 `getLayerServices` 가 알려 주는데, 색인이 WMTS 라 적고 MapServer 만 둔 판도 있어
# (화성 Hynek 골짜기망, 2026-09-30) 그때는 같은 이름을 `trekarcgis*` 밑에서 찾아본다.

_SERVICE_ROOTS = ("trekarcgis", "trekarcgis2", "trekarcgis3")


def _service_roots(body: str) -> tuple:
    """ArcGIS 서비스 목록의 자리 — 달·화성은 `trekarcgis*/rest/services`, 수성은 `arcgis/rest/services/mercury` 하나다
    (`trekarcgis` 는 404, P10 · wetherilli 185)."""
    if body == "mercury":
        return ("arcgis/rest/services/mercury",)
    return tuple(f"{root}/rest/services" for root in _SERVICE_ROOTS)


def _body_base(body: str) -> str:
    """몸의 Trek 뿌리 — `trek.nasa.gov/moon`·`/mars`·`/mercury`."""
    return {"mars": settings.TREK_MARS_URL, "mercury": settings.TREK_MERCURY_URL}.get(
        body, settings.TREK_URL).rstrip("/")


def find_mapserver(body: str, uuid: str, label: str) -> str:
    """판의 MapServer 경로(`trekarcgis2/rest/services/X/MapServer`) — 없으면 빈 칸. 색인 밖의 판이 ImageServer 를 적었으면
    그것이다 (wetherilli 150)."""
    for item in EXTRA_ITEMS.get(body, ()):
        if item["id"] == label and item.get("image"):
            return item["image"]
    base = _body_base(body)
    if uuid:
        docs = (_json(_get("TrekServices/ws/index/getLayerServices", {"uuid": uuid}, base=base))
                .get("response") or {}).get("docs") or []
        for doc in docs:
            end = str(doc.get("endPoint") or "")
            if doc.get("protocol") == "ArcGISDynamic" and end.startswith(base + "/") and end.endswith("/MapServer"):
                return end[len(base) + 1:]
    for root in _service_roots(body):
        path = f"{root}/{label}/MapServer"
        r = _get(path, {"f": "json"}, base=base)
        if r.status_code == 200:
            try:
                data = r.json()
            except ValueError:
                continue
            if isinstance(data, dict) and "error" not in data:
                return path
    return ""


def polar_map(body: str, label: str, pole: str) -> str:
    """씨앗에 적힌 극지 MapServer 짝의 경로 — 없으면 빈 칸. 씨앗에 없는 것은 부르지 않는다."""
    for e in _catalog_index(body):
        if e["id"] == label:
            if e.get("pole") == pole and e.get("kind") == "map":
                return e.get("ms") or ""                       # 판 자신이 극 평사도법 (wetherilli 150)
            p = (e.get("polar") or {}).get(pole) or {}
            return p.get("ms", "") if p.get("kind") == "map" else ""
    return ""


def map_polar_tile(body: str, ms: str, pole: str, z: int, x: int, y: int) -> bytes:
    """극지 MapServer 짝의 타일 한 장 — 극 격자(`polar_tile_bbox`). 서비스가 제 투영(WKT)으로 읽는다(052).
    화성은 화성 극 격자(`mars_polar_tile_bbox`)이고 투영을 WKT 로 밝힌다 — 적도 판도 Trek 이 옮겨 그린다 (wetherilli 192)"""
    op = "exportImage" if ms.endswith("/ImageServer") else "export"
    if body == "mars":
        w, s, e, n = mars_polar_tile_bbox(z, x, y)
        sr = json.dumps({"wkt": MARS_POLAR_WKT[pole]}, separators=(",", ":"))
        extra = {"bboxSR": sr, "imageSR": sr}
    else:
        w, s, e, n = polar_tile_bbox(z, x, y)
        extra = {}
    return _image(_get(f"{ms}/{op}", {
        "bbox": f"{w},{s},{e},{n}", "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image", **extra,
    }, base=_body_base(body)))


def map_entry(body: str, label: str) -> dict | None:
    """씨앗에서 MapServer 판 하나 — 씨앗에 없는 이름은 부르지 않는다(아무 서비스나 중계하지 않게)."""
    for e in _catalog_index(body):
        if e["id"] == label and e.get("kind") == "map" and e.get("ms"):
            return e
    return None


_INDEX = {}


def _catalog_index(body: str) -> list:
    path = catalog_file(body)
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return []
    if _INDEX.get(body, (None,))[0] != stamp:
        _INDEX[body] = (stamp, load_catalog(body))
    return _INDEX[body][1]


def map_tile(body: str, ms: str, z: int, x: int, y: int) -> bytes:
    """MapServer 판의 타일 한 장 (256 px PNG). 경위도 격자는 지질도와 같다. ImageServer 판(색인 밖의 북극 판, wetherilli 150)은
    `exportImage` 로 — 서비스가 늘인 회색으로 칠하고 극 평사도법을 우리 경위도로 옮겨 준다."""
    w, s, e, n = tile_bbox(z, x, y)
    sr = BODIES[body][1]
    op = "exportImage" if ms.endswith("/ImageServer") else "export"
    return _image(_get(f"{ms}/{op}", {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": sr, "imageSR": sr, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }, base=_body_base(body)))


#: 속성에서 빼는 열 — ArcGIS 가 붙이는 것
_SKIP_FIELDS = re.compile(r"^(FID|OBJECTID|OID|Shape|Shape_Length|Shape_Area|Shape\.STLength\(\)|Shape\.STArea\(\))$", re.I)


def map_identify(body: str, ms: str, lon: float, lat: float, z: int) -> list:
    """누른 자리의 것 — `[[열, 값], …]` 을 찾은 것마다. 점·선이 잡히게 화면의 줌(`z`)으로 너그러움을 잰다.

    열 이름·값은 옮기지 않는다(상류의 조사 자료다)."""
    step = 180.0 / 2 ** max(0, min(z, 20))
    sr = BODIES[body][1]
    data = _json(_get(f"{ms}/identify", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": sr,
        "layers": "all", "tolerance": 4, "returnGeometry": "false", "f": "json",
        "mapExtent": f"{lon - step / 2},{lat - step / 2},{lon + step / 2},{lat + step / 2}",
        "imageDisplay": f"{TILE},{TILE},96",
    }, base=_body_base(body)))
    out = []
    for hit in (data.get("results") or [])[:5]:
        attrs = hit.get("attributes") or {}
        rows = [[k, str(v).strip()] for k, v in attrs.items()
                if not _SKIP_FIELDS.match(k) and str(v).strip() not in ("", "Null", "None", " ")]
        if rows:
            out.append({"layer": hit.get("layerName") or "", "rows": rows})
    return out


def map_legend(body: str, ms: str) -> list:
    """`[{"label", "image"}]` — MapServer 의 범례. 그림은 data URL 이다."""
    data = _json(_get(f"{ms}/legend", {"f": "json"}, base=_body_base(body)))
    out = []
    for layer in data.get("layers") or []:
        for item in layer.get("legend") or []:
            label = str(item.get("label") or layer.get("layerName") or "").strip()
            if item.get("imageData"):
                out.append({"label": label, "image": f"data:{item.get('contentType') or 'image/png'};base64,"
                                                    f"{item['imageData']}"})
    return out
