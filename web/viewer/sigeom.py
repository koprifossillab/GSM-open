"""SIGÉOM(퀘벡 지질 광업 정보 체계)으로 나가는 문 — 퀘벡 지질도 (wetherilli 210).

- 주소: `servicesvectoriels.atlas.gouv.qc.ca/IDS_SGM_WMS/service.svc/get` — 퀘벡 정부 앞단 뒤의 GeoServer(`geoserver-prd`). 열쇠가 없다
- **WMS 1.1.1 만 받는다**(1.3.0 은 InvalidParameterValue). 화면의 1.3.0 변수를 1.1.1(`srs`·`x`·`y`)로 옮긴다
- **Origin 헤더가 붙으면 403** 이다(`Access-Control-Allow-Origin: *` 를 달고도) — 정적 판에서는 못 쓰고 이 문으로만 간다. 문은 Origin 을 보내지 않는다
- Capabilities 에 3978 이 없지만 **3978 로 물어도 그린다**(2026-10-04) — 캐나다 탭처럼 3978 로 곧장 받는다
- 축척에 따라 그린다 — `SGM:Geologie_generale` 은 512 격자 줌 4(화면 줌 5)부터, `SGM:Geologie_regionale` 은 격자 줌 7(화면 줌 8)부터.
  그보다 멀면 빈 그림이다
- 시대는 프랑스어로 온다 — `i18n.age_fr` 가 ICS 이름으로 옮긴다(wetherilli 224)
- 속성은 `text/plain` 으로 받는다 — `application/json` 은 기하가 붙어 415 KB, `text/plain` 은 2 KB. GeoServer 의 `propertyName` 은
  앞단을 지나며 깨진다(ClassCastException). 값은 프랑스어 그대로다(지층·암석). `REF_EXA` 의 `<a>` 는 뷰가 링크로 가른다
- 범례는 없다 — GetLegendGraphic 이 28×18 한 칸이고, `hideEmptyRules` 같은 벤더 인자도 앞단을 지나지 못한다
- 조건: Capabilities 의 AccessConstraints "Licence du gouvernement ouvert – Québec" = **CC BY 4.0**
"""
import logging
import re

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "sigeom:"
ATTRIBUTION = ('<a href="https://sigeom.mines.gouv.qc.ca/" target="_blank" rel="noopener">SIGÉOM</a> '
               "(Gouvernement du Québec, CC BY 4.0)")
#: 레이어 → (상류 이름, 처음 그리는 화면 줌, 누르기가 되나)
LAYERS = {
    "sigeom:generale": ("SGM:Geologie_generale", 5, True),
    "sigeom:regionale": ("SGM:Geologie_regionale", 8, True),
    "sigeom:failles": ("SGM:Failles_regionales", 9, False),     # 격자 줌 7 은 빈 그림, 8 부터 그린다 — 재어 정했다 (wetherilli 310)
    # 가동 광산·진행 사업(wetherilli 288)
    "sigeom:mines": ("SGM:Mines_projets", 5, True),
    # 광물 산지(indices, gîtes, mines et carrières, wetherilli 323) — 288 이 "WMS 에 없다" 고 적었지만 같은 WMS 의 무리 레이어
    # `Indices_gites_mines_carrieres` 아래에 있었다. 갈래마다 "모두" 레이어 하나씩 — 금속(원소)·비금속(광물)·석재(암석)
    "sigeom:gites_metal": ("SGM:Substances_metalliques", 7, True),
    "sigeom:gites_nonmetal": ("SGM:Substances_non_metalliques", 7, True),
    "sigeom:gites_stone": ("SGM:Pierre_architecturale_industrielle", 7, True),
}


class SigeomError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def queryable(name: str) -> bool:
    return name in LAYERS and LAYERS[name][2]


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SigeomError(f"모르는 레이어다: {names}")
    return names[0]


def _get(params: dict):
    left = usage.paused()
    if left:
        raise SigeomError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        # Origin 을 붙이지 않는다 — 붙이면 403 이다
        r = requests.get(settings.SIGEOM_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sigeom", ok=False)
        raise SigeomError(f"SIGÉOM 에 닿지 못했다: {exc}") from exc
    log.info("SIGÉOM %s -> %s", r.url, r.status_code)
    usage.record("sigeom", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    """화면의 WMS 1.3.0 변수 → 1.1.1. 투영 좌표라 BBOX 의 축 차례는 그대로다."""
    name = _one(params)
    out = dict(params, service="WMS", request=request, version="1.1.1", layers=LAYERS[name][0])
    if "crs" in out:
        out["srs"] = out.pop("crs")
    if "query_layers" in out:
        out["query_layers"] = LAYERS[name][0]
    for new, old in (("x", "i"), ("y", "j")):
        if old in out:
            out[new] = out.pop(old)
    out.setdefault("styles", "")
    return out


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SigeomError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise SigeomError("퀘벡 지질도는 범례를 주지 않는다")


def get_feature_info(params: dict) -> dict:
    if not queryable(_one(params)):
        return {"features": []}
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    r = _get(params)
    if r.status_code != 200:
        raise SigeomError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


def parse_plain(text: str) -> list:
    """GeoServer GetFeatureInfo `text/plain` → feature 목록. 덩이는 줄표 줄로 갈린다. 기하 줄(`GEOMETRIE = [GEOMETRY …]`)은 뺀다."""
    out, props = [], {}
    for line in text.splitlines():
        if line.startswith("-----"):
            if props:
                out.append({"id": f"sigeom.{len(out)}", "properties": props})
            props = {}
            continue
        m = re.match(r"([A-Z_0-9]+) = (.*)$", line)
        if m and not m.group(2).startswith("[GEOMETRY"):
            props[m.group(1)] = m.group(2).strip()
    if props:
        out.append({"id": f"sigeom.{len(out)}", "properties": props})
    return out


FRIENDLY = (("NOM_ABRG_ETQT_LITH", "기호"), ("STRATIGRAPHIE", "지층"), ("DESC_ZONE_GEOLG", "암석"), ("AGE", "지질시대"),
            ("REF_EXA", "원도"),
            # 가동 광산·진행 사업(wetherilli 288) — 지질 단위와 열이 겹치지 않는다
            ("NOM_MINE_PROJE", "이름"), ("SIGN_MINR", "광종"), ("SIGN_STAT_MINE_PROJE", "개발 단계"), ("NOM_SOCIE", "회사"),
            # 광물 산지(wetherilli 323) — 금속·비금속·석재의 열이 다르다. 상세 링크(`URL_NOM_CORPS_MINR`)는 `friendly` 가 따로 뽑는다
            ("NOM_CORPS_MINR", "이름"), ("NOM_GISM", "이름"), ("NOM_GISM_CARR", "이름"),
            ("SUBST_PRINC", "광종"), ("MINER", "광종"), ("PROD_EXTR", "산물"), ("SUBS_GISM_CARR", "암석"),
            ("ETAT_CORPS_MINR", "상태"), ("ETAT_GISM", "상태"), ("ETAT_GISM_CARR", "상태"),
            ("AN_DECV", "발견 연도"), ("CODE_TYPE_ROCH_LITH", "모암"), ("USAGE_PROD_EXTR", "쓰임"), ("COMN_DECV", "발견"))
_HREF = re.compile(r'href="(https://[^"]+)"')


def age(value: str, lang: str = "ko") -> str:
    """시대(`Néoarchéen`, `Silurien à Dévonien`, `A ou B`) → ICS 영문, 한국어판이면 한국어 (wetherilli 224). 모르는 말이 섞이면 원문"""
    en = i18n.age_fr(value)
    if en == value or lang != "ko":
        return en
    return " 또는 ".join(i18n.age_ko(x) for x in en.split(" or "))


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 프랑스어 그대로다 — 시대만 옮긴다(`i18n.age_fr`, wetherilli 224)."""
    out = {}
    for key, label in FRIENDLY:
        value = props.get(key)
        if value not in (None, "", "null") and label not in out:
            out[label] = age(value, lang) if key == "AGE" else value
    link = _HREF.search(str(props.get("URL_NOM_CORPS_MINR") or ""))     # 금속 광물 산지의 SIGÉOM 상세 (wetherilli 323)
    if link:
        out["상세"] = {"text": "", "links": [{"url": link.group(1).replace("&amp;", "&"), "label": "열기"}]}
    return out


# ── 보는 범위의 범례 (wetherilli 337) ─────────────────────────────────
# WMS 의 GetLegendGraphic 은 28×18 한 칸뿐이다. 면마다 칠한 색(`COUL_REMPL_HEXA`)이 속성에 들어 있어, 같은 자료의 WFS 에 보는 범위의 면을
# 기하 없이(`propertyName`) 받아 단위마다 센다 — 일반 지질 2.5° 네모에 62 KB·1.2 초(2026-10-05, 발도르)

#: 레이어 → (WFS 이름, 기호 열, 이름 열, 범례를 뜨는 가장 넓은 범위(°))
LEGEND = {
    "sigeom:generale": ("SGM:Geologie_generale", "ZGQ_CODE_IDENT_ETIQU_LEGEN", "ZGQ_DESCR", 8.0),
    "sigeom:regionale": ("SGM:Geologie_regionale", "NOM_ABRG_ETQT_LITH", "DESC_ZONE_GEOLG", 2.0),
}
LEGEND_FEATURES = 5000
MAX_LEGEND = 60


def legend_span(name: str) -> float:
    return LEGEND[name][3]


def extent_legend(name: str, bbox: tuple, lang: str = "ko") -> list:
    """보는 범위 `(서, 남, 동, 북)`(위경도)의 단위 `[{"symbol", "lithology", "color", "age", "count"}]` — 면이 많은 것부터"""
    if name not in LEGEND:
        raise SigeomError("범례가 없는 레이어다")
    typename, code_col, name_col, _ = LEGEND[name]
    left = usage.paused()
    if left:
        raise SigeomError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    w, s, e, n = bbox
    try:
        r = requests.get(settings.SIGEOM_WFS_URL, params={
            "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature", "TYPENAME": typename,
            "BBOX": f"{w!r},{s!r},{e!r},{n!r},EPSG:4326", "PROPERTYNAME": f"{code_col},{name_col},AGE,COUL_REMPL_HEXA",
            "MAXFEATURES": str(LEGEND_FEATURES), "OUTPUTFORMAT": "application/json"},
            timeout=max(settings.UPSTREAM_TIMEOUT, 30), verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sigeom", ok=False)
        raise SigeomError(f"SIGÉOM WFS 에 닿지 못했다: {exc}") from exc
    log.info("SIGÉOM-WFS %s -> %s", r.url, r.status_code)
    usage.record("sigeom", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise SigeomError(f"범례를 받지 못했다 (status={r.status_code})")
    try:
        features = r.json().get("features") or []
    except ValueError as exc:
        raise SigeomError("범례가 JSON 이 아니다") from exc
    rows = {}
    for f in features:
        p = f.get("properties") or {}
        code, label = str(p.get(code_col) or "").strip(), str(p.get(name_col) or "").strip()
        color = str(p.get("COUL_REMPL_HEXA") or "").strip()
        if not (code or label):
            continue
        row = rows.setdefault((code, label, color), {"symbol": code, "lithology": label, "swatch": "",
                                                     "color": color if color.startswith("#") else "#cccccc",
                                                     "age": age(str(p.get("AGE") or "").strip(), lang) if p.get("AGE") else "", "count": 0})
        row["count"] += 1
    return sorted(rows.values(), key=lambda r: -r["count"])


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "sigeom", "tag": "SIGÉOM", "title": "퀘벡 지질 광업 정보 체계", "relay": True, "projected": True, "globe": True},
]
