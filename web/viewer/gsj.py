"""산업기술종합연구소 지질조사종합센터(GSJ, AIST)로 나가는 문 — 일본 지질도.

20만분의 1 일본 심리스 지질도 V2 의 Web API 를 부른다 (devlog 024). 일본
레이어는 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나").

- 주소: `gbank.gsj.jp/seamless/v2/api/1.3` — 타일(`tiles/{z}/{y}/{x}.png`)과
  범례(`legend.json`). **열쇠가 없다.** 정부표준이용규약 2.0 이라 출처만 밝히면 된다
- **WMS(`gbank.gsj.jp/ows/seamlessgeology200k_*`)는 쓰지 않는다.** 2026-09-28 에
  같은 자리를 대조하니 WMS 는 옛 판(V1 — 기호 `N1vb`, 일본어 속성뿐)이고 타일
  API 가 V2(2026-05 판, 범례 2 416, 영어 속성)였다. 새 것이 이긴다
- 타일 경로의 자리 차례가 **z/y/x** 다. 빈 자리는 `blank.png` 로 301 을 보내는데,
  따라가지 않고 우리가 빈 타일을 낸다 — 한 번 덜 묻는다
- 속성은 WMS 꼴이 아니라 `point=위도,경도` 로 묻는다. 그래서 `/featureinfo/` 가
  아니라 `gsj/info/` 가 받는다
- 범례는 그림이 아니라 JSON 이다. 화면이 HTML 로 그린다 — 서버의 Pillow 에는
  한글·일본어 글꼴이 없다(`tiles.py` 머리글)
"""
import functools
import io
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('20万分の1日本シームレス地質図V2 © <a href="https://gbank.gsj.jp/seamless/" '
               'target="_blank" rel="noopener">Geological Survey of Japan, AIST</a>')
#: 선·기호 레이어의 범례는 API 가 주지 않는다. 원본 뷰어로 잇는다
VIEWER_URL = "https://gbank.gsj.jp/seamless/v2/viewer/"

#: 우리 레이어명 → API 의 `layer`·`type`, 그려 주는 줌, 속성·범례를 읽는 법.
#:   legend  "extent" 면 보는 범위의 범례(`box`), "all" 이면 통째로(14 칸), None 이면 없다
#: 경계·단층은 줌 10, 기호는 줌 11 부터다. 그보다 멀면 API 가 빈 타일을 준다
LAYERS = {
    "gsj:geology": {"layer": "g", "min": 0, "max": 13, "info": True, "legend": "extent"},
    "gsj:geology_level2": {"layer": "g", "type": "level2", "min": 0, "max": 13,
                           "info": True, "legend": "all"},
    "gsj:boundaries": {"layer": "l", "min": 10, "max": 13, "info": False, "legend": None},
    "gsj:faults": {"layer": "f", "min": 10, "max": 13, "info": False, "legend": None},
    "gsj:symbols": {"layer": "s", "min": 11, "max": 13, "info": False, "legend": None},
}

#: 범위 범례의 칸 수 한도. 넓게 보면 수백 칸이 온다 — 패널이 끝없이 길어지지 않게
MAX_LEGEND = 200


class GsjError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def valid_tile(name: str, z: int, x: int, y: int) -> bool:
    spec = LAYERS.get(name)
    return bool(spec) and 0 <= z <= spec["max"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z


@functools.lru_cache(maxsize=None)
def blank_tile() -> bytes:
    """투명한 256 타일. 상류의 `blank.png` 대신 낸다."""
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(out, "PNG", optimize=True)
    return out.getvalue()


def _get(path: str, params: dict):
    # 차단 조짐이 이어지면 잠시 묻지 않는다 (usage.py). 캐시가 대신 내준다
    left = usage.paused()
    if left:
        raise GsjError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.GSJ_URL.rstrip('/')}/{path}"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, allow_redirects=False,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsj", ok=False)
        raise GsjError(f"GSJ 에 닿지 못했다: {exc}") from exc
    log.info("GSJ %s -> %s", r.url, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("gsj", ok=r.status_code in (200, 301, 302), blocked=blocked, elapsed=r.elapsed)
    return r


def get_tile(name: str, z: int, x: int, y: int) -> bytes:
    """타일 한 장(PNG). 그 줌에서 그리지 않는 레이어·빈 자리는 빈 타일이다."""
    spec = LAYERS[name]
    if z < spec["min"]:
        return blank_tile()                 # 상류도 빈 타일을 준다 — 묻지 않는다
    params = {"layer": spec["layer"]}
    if spec.get("type"):
        params["type"] = spec["type"]
    r = _get(f"tiles/{z}/{y}/{x}.png", params)
    if r.status_code in (301, 302) and "blank" in r.headers.get("location", ""):
        return blank_tile()
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsjError(f"타일이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def _json(r):
    if r.status_code != 200:
        raise GsjError(f"범례를 읽지 못했다 (status={r.status_code}, {r.text[:200]!r})")
    try:
        return r.json()
    except ValueError as exc:
        raise GsjError("범례가 JSON 이 아니다") from exc


def point_legend(name: str, lat: float, lon: float):
    """누른 자리의 범례 한 칸(상류가 준 dict). 칠해지지 않은 자리(바다·매립지)면 None."""
    spec = LAYERS[name]
    params = {"point": f"{lat:.6f},{lon:.6f}"}
    if spec.get("type"):
        params["type"] = spec["type"]
    row = _json(_get("legend.json", params))
    # 빈 자리도 200 이다 — `symbol` 이 null 인 칸이 온다
    if not isinstance(row, dict) or not row.get("symbol"):
        return None
    return row


def extent_legend(name: str, bbox, z: int) -> list:
    """보는 범위의 범례 칸들. `bbox` 는 (서, 남, 동, 북) 위경도.

    **줌을 함께 준다.** 주지 않으면 상류가 줌 13 으로 세어 넓은 범위를 400 으로
    돌려보낸다(1°×2° 에서 이미 그렇다). 화면의 줌을 주면 범위가 늘 화면 한 장이라
    상류의 한도 안에 든다.
    """
    spec = LAYERS[name]
    if spec["legend"] == "all":
        rows = _json(_get("legend.json", {"type": spec["type"]}))
    else:
        west, south, east, north = bbox
        rows = _json(_get("legend.json", {"box": f"{south:.2f},{west:.2f},{north:.2f},{east:.2f}",
                                          "z": max(0, min(spec["max"], int(z)))}))
    return [r for r in rows if isinstance(r, dict) and r.get("symbol")] if isinstance(rows, list) else []


# ── 사람이 읽을 꼴 ────────────────────────────────────────────────────

#: 상류의 대분류 → 한국어. V2 원본은 복수(`Igneous rocks`), 간략판(level2)은
#: 단수(`Igneous rock`)로 온다
GROUP_KO = {
    "sedimentary rock": "퇴적암", "igneous rock": "화성암", "metamorphic rock": "변성암",
    "accretionary complex": "부가체", "other": "기타",
}


def group_ko(value: str) -> str:
    text = str(value or "").strip()
    key = text.lower()
    if key.endswith("es") and key[:-2] in GROUP_KO:
        key = key[:-2]
    elif key.endswith("s") and key[:-1] in GROUP_KO:
        key = key[:-1]
    return GROUP_KO.get(key, text)


def age(row: dict, lang: str) -> str:
    """지질시대. 상류가 영문 ICS 명칭을 준다. 한국어판은 옮기되, 절(Age) 이름이
    섞이면 원문을 둔다 (`i18n.age_ko_stacked`, devlog 021 의 규칙)."""
    value = row.get("formationAge_en") or ""
    return i18n.age_ko_stacked(value) if lang == "ko" else value


def friendly(row: dict, lang: str = "ko") -> dict:
    """팝업에 올릴 속성. 이름은 한국어로 두고, 영어판은 `i18n.props_en` 이 옮긴다.

    암상은 **상류가 준 영어**를 올린다 — 우리가 옮긴 것이 아니라 GSJ 가 붙인
    것이고, 한국어판 사람에게 일본어보다 읽힌다. 일본어 원문은 그 밑에 둔다.
    """
    group = row.get("group_en") or ""
    props = {
        "지질시대": age(row, lang),
        "암상": lithology(row, lang),
        "구분": group_ko(group) if lang == "ko" else group,
        "기호": row.get("symbol") or "",
        "암상 (원문)": row.get("lithology_ja") or "",
    }
    return {k: v for k, v in props.items() if v}


def lithology(row: dict, lang: str) -> str:
    """간략판(level2)은 대분류가 곧 암상이고 `group_en` 이 없다 — 그때는 대분류를
    옮긴다(`Accretionary complex` → 부가체). 원본의 암상은 옮기지 않는다."""
    value = row.get("lithology_en") or ""
    if lang == "ko" and not row.get("group_en"):
        return group_ko(value)
    return value


def legend_row(row: dict, lang: str = "ko") -> dict:
    """범례 한 칸 — 색, 기호, 암상, 시대. 색은 `r·g·b` 가 그 판(간략판이면 간략판)의
    색이다. `value` 는 원본의 색이라 간략판에서 어긋난다."""
    if row.get("r") is not None:
        color = "#%02x%02x%02x" % (row["r"], row["g"], row["b"])
    else:
        color = "#" + str(row.get("value") or "cccccc")
    return {"color": color, "symbol": row.get("symbol") or "",
            "lithology": lithology(row, lang), "age": age(row, lang)}


# ── CCOP 동·동남아시아 200만 지질도 (wetherilli 108) ─────────────────────
#
# GSJ 가 2024-05 에 옮긴 새 호스트 `ows.gsj.jp` 의 MapServer WMS 다. 상류 이름은 `ccop` 로 따로 두되(심리스 V2 의 z/x/y 와
# 길이 다르다) **문은 여기 하나다** — 같은 GSJ 서버다.
#
# - 조건: "개인·교육·연구·비상업 용도로 자유롭게"(GetCapabilities 의 AccessConstraints). 밖에 열 때 geo3al(025, 재배포 금지)을
#   대신할 후보다. 출처는 CCOP 와 GSJ
# - 그림은 3857(`EPSG:900913` 도 같다)로 그대로 준다. **속성은 4326 으로만, `text/html` 로만** 준다 — 3857 로 물으면 "no results",
#   `text/plain` 도 비고 JSON 은 안 받는다(2026-09-30). 그래서 누른 픽셀을 위경도로 풀어 4326 의 작은 네모로 다시 묻고,
#   HTML 표의 한 줄(`Geology | J_Pf: Felsic Plutonic Rocks, Jurassic`)을 기호·암석·시대로 나눈다
# - CORS 가 없어 브라우저가 곧장 부르지 못한다 — 늘 `/GSM/wms/` 를 거친다
import html as _html
import math as _math
import re as _re
from types import SimpleNamespace as _NS

CCOP_LAYER = "EASIA_CCOP_2M_Combined_BLT_SLT_BA"


def _ccop_get(params: dict):
    left = usage.paused()
    if left:
        raise GsjError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.CCOP_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ccop", ok=False)
        raise GsjError(f"CCOP(GSJ) 에 닿지 못했다: {exc}") from exc
    log.info("CCOP %s -> %s", r.url, r.status_code)
    usage.record("ccop", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def ccop_get_map(params: dict):
    """`GetMap`. (바이트, content-type)."""
    params = dict(params, service="WMS", request="GetMap", version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    r = _ccop_get(params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsjError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def ccop_get_legend(layer: str):
    r = _ccop_get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                   "layer": CCOP_LAYER})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GsjError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def _clicked_lonlat(params: dict):
    """WMS `GetFeatureInfo` 의 범위·크기·픽셀 → 누른 자리의 (경도, 위도). 3857·900913·4326 을 안다."""
    srs = (params.get("srs") or params.get("crs") or "EPSG:3857").upper()
    bbox = [float(v) for v in str(params.get("bbox", "")).split(",")]
    width, height = float(params.get("width", 256)), float(params.get("height", 256))
    i = float(params.get("i", params.get("x", width / 2)))
    j = float(params.get("j", params.get("y", height / 2)))
    if srs in ("EPSG:4326", "CRS:84"):
        if srs == "EPSG:4326" and str(params.get("version", "")).startswith("1.3"):
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]      # 1.3.0 의 4326 은 위도가 먼저다
        return bbox[0] + (bbox[2] - bbox[0]) * i / width, bbox[3] - (bbox[3] - bbox[1]) * j / height
    x = bbox[0] + (bbox[2] - bbox[0]) * i / width
    y = bbox[3] - (bbox[3] - bbox[1]) * j / height
    r = 6378137.0
    return _math.degrees(x / r), _math.degrees(2 * _math.atan(_math.exp(y / r)) - _math.pi / 2)


_CELL = _re.compile(r"<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", _re.S)


def parse_ccop_html(text: str) -> list:
    """MapServer 의 HTML 표 → feature 목록. 한 줄(`Geology`)의 값을 기호·암석·시대로 나눈다."""
    features = []
    for key, value in _CELL.findall(text or ""):
        key = _html.unescape(_re.sub(r"<[^>]+>", "", key)).strip()
        value = _html.unescape(_re.sub(r"<[^>]+>", "", value)).strip()
        if not value:
            continue
        props = {"_raw": value}
        m = _re.match(r"^([^:]+):\s*(.+?)(?:,\s*([^,]+))?$", value)
        if m:
            props = {"code": m.group(1).strip(), "rock": m.group(2).strip(), "age": (m.group(3) or "").strip()}
        features.append({"id": f"ccop.{len(features)}", "properties": props, "key": key})
    return features


def ccop_get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` — 누른 자리를 가운데 둔 4326 의 1° 네모(101 픽셀, 한 칸 0.01°)로 다시 묻는다. 네모를 더 좁히면
    (0.2° 에 256 픽셀도) "no results" 다 — 이 판은 200만 축척이라 그보다 가까운 축척에서는 속성을 내주지 않는다(2026-09-30)."""
    lon, lat = _clicked_lonlat(params)
    half = 0.5
    q = {"service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo", "layers": CCOP_LAYER,
         "query_layers": CCOP_LAYER, "styles": "", "srs": "EPSG:4326",
         "bbox": f"{lon - half:.6f},{lat - half:.6f},{lon + half:.6f},{lat + half:.6f}",
         "width": 101, "height": 101, "x": 50, "y": 50, "info_format": "text/html", "feature_count": 3}
    r = _ccop_get(q)
    if r.status_code != 200:
        raise GsjError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_ccop_html(r.text)}


#: 팝업에 보일 이름 — 시대는 ICS 한글판으로 옮긴다(한국어판)
CCOP_FRIENDLY = {"code": "지질기호", "rock": "암석", "age": "지질시대", "_raw": "지질"}


def ccop_friendly(props: dict, lang: str = "ko") -> dict:
    out = {}
    for key, value in props.items():
        if key == "age" and lang == "ko":
            value = i18n.age_ko(value)
        out[CCOP_FRIENDLY.get(key, key)] = value
    return out


#: `views._Door` 가 쓰는 꼴 — 다른 문(모듈)과 같은 이름의 셋
CCOP = _NS(get_map=ccop_get_map, get_feature_info=ccop_get_feature_info, get_legend=ccop_get_legend)


# ── GSJ 의 다른 WMS — 1:200만 일본 지질도·부게 중력·지구화학도 (wetherilli 255) ──────────────
#
# 안내 쪽(`gbank.gsj.jp/owscontents/`)에서 이름을 찾았다. 상류 이름은 `gsjows` 로 따로 두되 문은 여기 하나다(CCOP 와 같다).
#
# - 조건: WMS·WMTS 의 지질도는 **정부표준이용규약 2.0**(안내 쪽 "Terms of Use") — 출처를 밝히면 된다. 중력도의 AccessConstraints 는 "저작권은
#   산총연 GSJ 에 있다" 고 적는데, 이용 조건은 위의 규약이다
# - 1:200만 지질도·중력도는 새 호스트(`ows.gsj.jp/ows/`), **지구화학도는 옛 호스트에만**(`gbank.gsj.jp/ows/geochemmap` — 새 호스트는 404)
# - 셋 다 MapServer 라 3857 로 그린다. **누르지 않는다** — CCOP 처럼 3857 로 물으면 "no results", 4326 으로 물어도 기호 번호(`GEO200 = '25'`)
#   뿐이다. 범례 그림(GetLegendGraphic)이 번호·색·이름을 다 싣는다
# - 지구화학도는 원소 53 가지(하천 퇴적물, 이마이 외 2004) — 처음엔 금속·환경 원소 열하나만 골랐고(`GEOCHEM`), 나머지 마흔둘은 셋째 판에
#   더했다(`GEOCHEM_MORE`, wetherilli 266). Capabilities 의 차례 그대로다
# - **공중 자력은 WMS 가 없다** — 지질도Navi 판으로만 있다. 일본 전체를 덮는 편집도 셋(`GSJOWS_NAVI` — 일본의 자기도 1:200만 1992, 동아시아
#   자기 이상도 1:400만 1994, 동·동남아시아 자기 이상도 3 판 2021)을 카탈로그 레이어로 올렸다(wetherilli 266). 타일은 Navi 판처럼 브라우저가
#   `tiles.gsj.jp` 를 곧장 부르고(CORS 가 열려 있다), 범례는 GSJ 가 판마다 떠 둔 범례 그림을 문이 받아 준다. 도폭마다 갈린 공중자기도(MAGN_*)는
#   지질도Navi 칸에 그대로 둔다
GSJOWS_LAYERS = {
    "gsjows:japan2m": ("ows", "geologicmap2000k", "area,line", "area"),
    "gsjows:gravity": ("ows", "gravdb", "AssumedDensity267", "GravityContour267"),
}
GEOCHEM = ("Cu", "Pb", "Zn", "As", "Hg", "Cr", "Ni", "Fe2O3", "K2O", "U", "Th")
GEOCHEM_MORE = ("Al2O3", "CaO", "MgO", "MnO", "Na2O", "P2O5", "TiO2", "Ba", "Be", "Bi", "Cd", "Ce", "Co", "Cs", "Dy", "Er", "Eu",
                "Ga", "Gd", "Hf", "Ho", "La", "Li", "Lu", "Mo", "Nb", "Nd", "Pr", "Rb", "Sb", "Sc", "Sm", "Sn", "Sr", "Ta", "Tb", "Tl",
                "Tm", "V", "Y", "Yb", "Zr")
GSJOWS_LAYERS.update({f"gsjows:geochem:{el}": ("gbank", "geochemmap", el, el) for el in GEOCHEM + GEOCHEM_MORE})
#: 지질도Navi 판을 카탈로그 레이어로 — 우리 이름 → (판 이름, 줌 끝, 범례 그림)
GSJOWS_NAVI = {
    "gsjows:magnetic_japan": ("TH_23magne", 8, "orgsize_816_legend_1088.jpg"),
    "gsjows:magnetic_eastasia_1994": ("MISC_32", 9, "orgsize_1444_legend_1408.jpg"),
    "gsjows:magnetic_eastasia_2021": ("DGM_P3_2021", 7, "orgsize_1549_legend_1521.jpg"),
}
GSJOWS_ATTRIBUTION = ('© <a href="https://gbank.gsj.jp/owscontents/" target="_blank" rel="noopener">Geological Survey of Japan, AIST</a> '
                      "(政府標準利用規約 2.0)")


def gsjows_knows(name: str) -> bool:
    return name in GSJOWS_LAYERS or name in GSJOWS_NAVI


def gsjows_tiles(name: str) -> str:
    """지질도Navi 판으로 올린 레이어의 z/x/y 주소(브라우저가 곧장 부른다). WMS 레이어면 빈 글"""
    return f"{GEONAVI_TILES}{GSJOWS_NAVI[name][0]}/{{z}}/{{x}}/{{y}}.png" if name in GSJOWS_NAVI else ""


def _gsjows(name: str):
    if name not in GSJOWS_LAYERS:
        raise GsjError(f"모르는 레이어다: {name}")
    host, service, layers, legend = GSJOWS_LAYERS[name]
    root = settings.GSJ_OWS_URL if host == "ows" else settings.GSJ_GBANK_OWS_URL
    return f"{root.rstrip('/')}/{service}", layers, legend


def _gsjows_get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise GsjError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsjows", ok=False)
        raise GsjError(f"GSJ 에 닿지 못했다: {exc}") from exc
    log.info("GSJ-OWS %s -> %s", r.url, r.status_code)
    usage.record("gsjows", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def gsjows_get_map(params: dict):
    url, layers, _ = _gsjows(str(params.get("layers") or "").strip())
    r = _gsjows_get(url, dict(params, service="WMS", request="GetMap", layers=layers, styles=""))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsjError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def gsjows_get_legend(layer: str):
    if layer in GSJOWS_NAVI:
        # Navi 판의 범례 그림(JPEG) — 원도의 범례를 스캔한 것
        r = _gsjows_get(GEONAVI_LEGEND + GSJOWS_NAVI[layer][2], {})
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise GsjError(f"범례를 받지 못했다 (status={r.status_code})")
        return r.content, ctype
    url, _, legend = _gsjows(layer)
    r = _gsjows_get(url, {"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "image/png",
                          "layer": legend, "sld_version": "1.1.0"})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GsjError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def gsjows_get_feature_info(params: dict) -> dict:
    return {"features": []}


OWS = _NS(get_map=gsjows_get_map, get_feature_info=gsjows_get_feature_info, get_legend=gsjows_get_legend)


# ── 지질도Navi 판 (wetherilli 171) ─────────────────────────────────
#
# 지질도Navi(`gbank.gsj.jp/geonavi`)가 싣는 판 1 849 장 — 5만 지질도폭 763, 해저지질도, 중력·자기도, 화산지질도 …
# **WMTS Capabilities 한 장에 다 있다** — 판마다 이름·제목·범위·범례 그림·줌 끝·타일 주소. 그래서 달 Trek 판(060)처럼
# 받은 것을 씨앗(`data/gsj_geonavi_layers.json`)으로 두되, 판마다 다시 묻지 않는다. 타일(`tiles.gsj.jp`)은 CORS 를 열어
# 두어 **브라우저가 곧장 부른다** — 우리 캐시에 담지 않는다. 사람이 손질하는 것은 숨김(`hide`)뿐이고, 한글은 시리즈 이름만
# 옮긴다 — 도폭 이름은 일본 지명이라 속성 값처럼 옮기지 않는다(사람이 정했다, 171).

GEONAVI_CAPABILITIES = "https://gbank.gsj.jp/geonavi/maptile/wmts/1.0.0/WMTSCapabilities.xml"
GEONAVI_TILES = "https://tiles.gsj.jp/tiles/geomap/"
GEONAVI_LEGEND = "https://gbank.gsj.jp/geonavi/docdata/data/pict_data/"
GEONAVI_ATTRIBUTION = ('地質図Navi © <a href="https://gbank.gsj.jp/geonavi/" target="_blank" '
                       'rel="noopener">Geological Survey of Japan, AIST</a>')

#: 시리즈(제목의 `_` 앞) → 한글·영어. 차례는 축척이 큰 지질도폭부터, 바다, 주제도, 옛 판
GEONAVI_SERIES = [
    ("5万分の1地質図幅", "5만 지질도폭", "1:50,000 geological sheets"),
    ("7万5千分の1地質図幅", "7만5천 지질도폭", "1:75,000 geological sheets"),
    ("20万分の1地質図幅", "20만 지질도폭", "1:200,000 geological sheets"),
    ("50万分の1地質図幅", "50만 지질도폭", "1:500,000 geological sheets"),
    ("200万分の1地質編集図", "200만 지질편집도", "1:2,000,000 compiled geological maps"),
    ("海陸シームレス地質情報集", "해륙 심리스 지질정보집", "Seamless land–sea geological information"),
    ("海洋・海底地質図20万", "20만 해저지질도", "1:200,000 marine geological maps"),
    ("海洋・表層堆積図20万", "20만 표층퇴적도", "1:200,000 sea-floor sediment maps"),
    ("海洋・広域図", "해양 광역도", "Regional marine maps"),
    ("火山地質図", "화산지질도", "Volcanic geological maps"),
    ("大規模火砕流分布図", "대규모 화쇄류 분포도", "Large pyroclastic flow maps"),
    ("50万分の1活構造図", "50만 활구조도", "1:500,000 active tectonic maps"),
    ("構造図", "구조도", "Tectonic maps"),
    ("重力図", "중력도", "Gravity maps"),
    ("空中磁気図", "공중자기도", "Aeromagnetic maps"),
    ("水理地質図", "수리지질도", "Hydrogeological maps"),
    ("鉱物資源図", "광물자원도", "Mineral resource maps"),
    ("地熱資源図", "지열자원도", "Geothermal resource maps"),
    ("日本炭田図", "일본 탄전도", "Coalfield maps of Japan"),
    ("日本油田・ガス田図", "일본 유전·가스전도", "Oil and gas field maps of Japan"),
    ("特殊地質図", "특수지질도", "Special geological maps"),
    ("アジア地域の地球科学図", "아시아 지구과학도", "Geoscience maps of Asia"),
    ("10万分の1土性図", "10만 토성도", "1:100,000 soil maps"),
]
_SERIES = {ja: (i, ko, en) for i, (ja, ko, en) in enumerate(GEONAVI_SERIES)}


def fetch_geonavi_capabilities() -> str:
    """Capabilities XML 한 장(2 MB 남짓). 사람이 `fetch_geonavi` 로 부를 때만 간다."""
    left = usage.paused()
    if left:
        raise GsjError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(GEONAVI_CAPABILITIES, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsj", ok=False)
        raise GsjError(f"지질도Navi 에 닿지 못했다: {exc}") from exc
    usage.record("gsj", ok=r.status_code == 200, elapsed=r.elapsed)
    if r.status_code != 200 or b"<Capabilities" not in r.content[:2000]:
        raise GsjError(f"Capabilities 가 아닌 것이 왔다 (status={r.status_code})")
    return r.content.decode("utf-8")


_MATRIX = _re.compile(r"_z(\d+)$")


def parse_geonavi(xml: str) -> list:
    """Capabilities → [{id, title, bbox, max, legend}]. 타일이 `tiles.gsj.jp` 의 z/x/y 가 아닌 판은 뺀다 —
    화면은 그 주소 꼴 하나만 안다."""
    import xml.etree.ElementTree as ET
    ns = {"w": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1",
          "xlink": "http://www.w3.org/1999/xlink"}
    out = []
    for layer in ET.fromstring(xml).iterfind("w:Contents/w:Layer", ns):
        ident = layer.findtext("ows:Identifier", "", ns)
        title = layer.findtext("ows:Title", "", ns)
        template = ""
        for res in layer.iterfind("w:ResourceURL", ns):
            if res.get("format") == "image/png":
                template = res.get("template", "")
        if template != f"{GEONAVI_TILES}{ident}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png":
            continue
        matrix = _MATRIX.search(layer.findtext("w:TileMatrixSetLink/w:TileMatrixSet", "", ns) or "")
        low = (layer.findtext("ows:WGS84BoundingBox/ows:LowerCorner", "", ns) or "").split()
        high = (layer.findtext("ows:WGS84BoundingBox/ows:UpperCorner", "", ns) or "").split()
        if not matrix or len(low) != 2 or len(high) != 2:
            continue
        legend = ""
        node = layer.find("w:Style/w:LegendURL", ns)
        if node is not None:
            href = node.get("{http://www.w3.org/1999/xlink}href", "")
            legend = href[len(GEONAVI_LEGEND):] if href.startswith(GEONAVI_LEGEND) else ""
        out.append({"id": ident, "title": title, "max": int(matrix.group(1)), "legend": legend,
                    "bbox": [round(float(v), 4) for v in (*low, *high)]})
    return out


def load_geonavi() -> list:
    """씨앗의 판들. 파일이 없으면 빈 목록 — 일본 탭은 판 목록 없이 돈다."""
    import json
    path = settings.REPO_DIR / "data" / "gsj_geonavi_layers.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["layers"]
    except (OSError, ValueError, KeyError):
        return []


def split_title(title: str) -> tuple:
    """`5万分の1地質図幅_小倉(1998)` → (시리즈, 도폭). `_` 가 없으면 시리즈가 없다."""
    series, _, sheet = title.partition("_")
    return (series, sheet) if sheet else ("", title)


def client_geonavi(lang: str = "ko") -> dict:
    """화면에 내리는 목록 — 숨기지 않은 판을 시리즈로 묶어서. 판 하나는 [이름, 도폭, bbox, 줌 끝, 범례]."""
    groups = {}
    for e in load_geonavi():
        if e.get("hide"):
            continue
        series, sheet = split_title(e["title"])
        order, ko, en = _SERIES.get(series, (len(_SERIES), series or "その他", series or "Other"))
        g = groups.setdefault(series, {"key": series, "order": order, "name": en if lang == "en" else ko,
                                       "layers": []})
        g["layers"].append([e["id"], sheet, e["bbox"], e["max"], e.get("legend") or ""])
    out = sorted(groups.values(), key=lambda g: (g["order"], g["key"]))
    for g in out:
        del g["order"]
    return {"tiles": GEONAVI_TILES, "legend": GEONAVI_LEGEND, "attribution": GEONAVI_ATTRIBUTION, "series": out}
