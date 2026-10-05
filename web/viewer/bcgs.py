"""브리티시컬럼비아 지질조사소(BCGS)로 나가는 문 — BC Digital Geology 기반암 (wetherilli 231).

- 주소: `openmaps.gov.bc.ca/geo/pub/WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW/ows` (GeoServer WMS). 레이어
  `pub:WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW`. 열쇠가 없다. 1:5만–1:25만 합본
- **상류의 스타일은 1:50만보다 넓게 보면 칠하지 않는다** — 색 스타일(`1903`)의 519 칸이 모두 `MaxScaleDenominator 500000`, 테두리 칸은 1:70만.
  이름 붙은 스타일 셋이 다 그렇다. 처음엔 줌 11 부터 얹었다(wetherilli 231). **넓게 볼 때는 우리 스타일을 보낸다**(wetherilli 317) — 상류 스타일
  (640 KB)을 한 번 받아 같은 색을 `AGE_GROUP` 값(173)에서 색(161)으로 묶고 축척 끝을 뺀 47 KB 로 줄여(`wide_sld`, 캐시에 30 일), 주소에 실을
  수 없어 **POST 의 `SLD_BODY`** 로 보낸다(GeoServer 가 KVP 를 POST 몸으로 받는다). 섬 전체 512² 가 4 초 남짓. 1:50만 안쪽은 상류의 스타일 그대로다
  (테두리까지). 그래서 줌 5 부터 얹는다
- Capabilities 는 3005·CRS:84 만 적지만 **3978 GetMap 이 그린다** — 캐나다 탭의 투영으로 곧장 받는다(캄루프스 둘레 512² 2.6 초).
  처음 한 장은 9.5 초 걸렸다(wetherilli 210)
- 속성은 `application/json` 인데 **모양까지 딸려 와 80 KB** 다 — `propertyName` 으로 열을 골라 묻는다(뉴질랜드 `gns.py` 와 같다).
  열이 넉넉하다 — 층서명·암상·시대(Ma)·지구조 구역(terrane)·지은이
- 범례는 GeoServer 그림(326×3480) 그대로
- 조건: **Open Government Licence – British Columbia**(AccessConstraints NONE). CORS 머리가 없어 정적 판은 곧장 못 부른다 — 서버 문으로만
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "bcgs:"
ATTRIBUTION = ('<a href="https://www2.gov.bc.ca/gov/content/industry/mineral-exploration-mining/british-columbia-geological-survey" '
               'target="_blank" rel="noopener">BC Geological Survey</a> (Open Government Licence – British Columbia)')
LAYERS = {"bcgs:bedrock": "pub:WHSE_MINERAL_TENURE.GEOL_BEDROCK_UNIT_POLY_SVW",
          # MINFILE 광물 산지 1 만 6 천 곳(wetherilli 288) — 같은 openmaps 의 다른 레이어. 레이어마다 주소가 따로다(`…/pub/<레이어>/ows`)
          "bcgs:minfile": "pub:WHSE_MINERAL_TENURE.MINFIL_MINERAL_FILE"}
#: 이 줌부터 얹는다 — 캐나다 탭에서 BC 가 한 화면에 드는 줌. 그보다 넓으면 캐나다 Wheeler 1:500만이 맡는다 (wetherilli 317)
MIN_ZOOM = 5
#: 상류의 색 스타일이 칠하는 가장 넓은 축척 — 이보다 넓으면 우리 스타일(`wide_sld`)을 보낸다
WIDE_SCALE = 500000
#: 줄인 스타일을 담아 두는 날 — 상류가 색을 고치면 따라간다
WIDE_SLD_SECONDS = 30 * 86400
FIELDS = ("STRATIGRAPHIC_UNIT_CODE,STRATIGRAPHIC_NAME,ROCK_TYPE_DESCRIPTION,ROCK_CLASS,ORIGINAL_DESCRIPTION,"
          "MAXIMUM_AGE_NAME,MINIMUM_AGE_NAME,MAXIMUM_AGE_VALUE,MINIMUM_AGE_VALUE,GEOLOGICAL_PERIOD,TERRANE_NAME,"
          "MORPHOTECTONIC_BELT,AUTHOR_NAMES")


#: MINFILE 에서 받을 열 — 모양이 딸려 오지 않게 고른다
MINFILE_FIELDS = ("MINFILE_NUMBER,MINFILE_NAME1,STATUS_DESCRIPTION,COMMODITY_DESCRIPTION1,COMMODITY_DESCRIPTION2,COMMODITY_DESCRIPTION3,"
                  "COMMODITY_DESCRIPTION4,DEPOSIT_TYPE_DESCRIPTION1,DEPOSIT_CLASS_DESCRIPTION1,TECTONIC_BELT_DESCRIPTION,"
                  "TERRANE_DESCRIPTION,PRODUCTION_IND,RESERVES_IND,MINFILE_SUMMARY_URL")


class BcgsError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return str(name or "") in LAYERS


def _names(names: str) -> str:
    if not all(knows(n.strip()) for n in str(names or "").split(",")):
        raise BcgsError(f"모르는 레이어다: {names}")
    return ",".join(LAYERS[n.strip()] for n in names.split(","))


def _url(names) -> str:
    """openmaps 는 레이어마다 제 주소가 있다 — 설정의 주소(기반암)에서 레이어 마디만 바꾼다"""
    first = str(names or "").split(",")[0].strip()
    layer = LAYERS.get(first, LAYERS["bcgs:bedrock"]).split(":", 1)[1]
    return settings.BCGS_WMS_URL.replace(LAYERS["bcgs:bedrock"].split(":", 1)[1], layer)


def _get(params: dict, url: str = ""):
    left = usage.paused()
    if left:
        raise BcgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url or settings.BCGS_WMS_URL, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bcgs", ok=False)
        raise BcgsError(f"BC openmaps 에 닿지 못했다: {exc}") from exc
    log.info("BCGS %s -> %s", r.url, r.status_code)
    usage.record("bcgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = _names(params[key])
    return params


def _scale(params: dict) -> float:
    """요청의 축척 분모 — 범위 너비 ÷ 픽셀 ÷ 0.28 mm. 경위도면 1° = 111 km 로 어림한다"""
    try:
        west, _, east, _ = (float(v) for v in str(params.get("bbox") or "").split(","))
        width = float(params.get("width") or 256)
    except ValueError:
        return 0.0
    metres = (east - west) * (111320.0 if str(params.get("srs") or params.get("crs") or "").upper() in ("EPSG:4326", "CRS:84") else 1.0)
    return abs(metres) / max(width, 1.0) / 0.00028


def compact_sld(style_xml: str) -> str:
    """상류 스타일(SLD) → 같은 색의 `AGE_GROUP` 값을 한 칸으로 묶고 축척 끝·테두리를 뺀 SLD. 640 KB → 47 KB"""
    import re
    colours = {}
    for rule in re.findall(r"<sld:Rule>(.*?)</sld:Rule>", style_xml, re.S):
        value = re.search(r"PropertyName>AGE_GROUP</ogc:PropertyName>\s*<ogc:Literal>([^<]*)</ogc:Literal>", rule)
        fill = re.search(r'name="fill">\s*([^<]+?)\s*<', rule)
        if value and fill:
            colours.setdefault(fill.group(1), set()).add(value.group(1))
    if not colours:
        raise BcgsError("상류 스타일에서 색을 찾지 못했다")
    rules = []                                     # 값·색은 상류 XML 에서 뜬 글 그대로라 이미 이스케이프돼 있다 — 다시 하지 않는다
    for colour, values in colours.items():
        cond = "".join(f"<ogc:PropertyIsEqualTo><ogc:PropertyName>AGE_GROUP</ogc:PropertyName><ogc:Literal>{v}</ogc:Literal>"
                       "</ogc:PropertyIsEqualTo>" for v in sorted(values))
        if len(values) > 1:
            cond = f"<ogc:Or>{cond}</ogc:Or>"
        rules.append(f'<Rule><ogc:Filter>{cond}</ogc:Filter><PolygonSymbolizer><Fill><CssParameter name="fill">{colour}'
                     "</CssParameter></Fill></PolygonSymbolizer></Rule>")
    return ('<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">'
            f'<NamedLayer><Name>{LAYERS["bcgs:bedrock"]}</Name><UserStyle><FeatureTypeStyle>{"".join(rules)}'
            "</FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>")


def wide_sld() -> str:
    """넓게 볼 때 보낼 스타일 — 상류의 색 스타일을 한 번 받아 줄인 것. 캐시에 30 일"""
    from . import tilecache
    key = tilecache.key_text("bcgs-wide-sld", LAYERS["bcgs:bedrock"])
    held = tilecache.get(key, ".xml", max_age=WIDE_SLD_SECONDS)
    if held is not None:
        return held.decode("utf-8")
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetStyles", "layers": LAYERS["bcgs:bedrock"]}, _url("bcgs:bedrock"))
    if r.status_code != 200 or "Rule>" not in r.text:
        raise BcgsError(f"상류 스타일을 받지 못했다 (status={r.status_code})")
    sld = compact_sld(r.text)
    tilecache.put(key, sld.encode("utf-8"), ".xml")
    return sld


def _post(params: dict, url: str):
    left = usage.paused()
    if left:
        raise BcgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.post(url, data=params, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                          verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bcgs", ok=False)
        raise BcgsError(f"BC openmaps 에 닿지 못했다: {exc}") from exc
    log.info("BCGS POST %s %s -> %s", url, params.get("bbox"), r.status_code)       # 스타일(47 KB)은 적지 않는다
    usage.record("bcgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def get_map(params: dict):
    wms = _wms(params, "GetMap")
    if str(params.get("layers") or "").strip() == "bcgs:bedrock" and _scale(wms) > WIDE_SCALE:
        # 넓게 볼 때 — 상류 스타일이 칠하지 않는 축척이라 우리 스타일을 POST 로 (wetherilli 317)
        r = _post(dict(wms, styles="", SLD_BODY=wide_sld()), _url("bcgs:bedrock"))
    else:
        r = _get(wms, _url(params.get("layers")))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BcgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png", "layer": _names(layer)},
             _url(layer))
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BcgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    url = _url(params.get("query_layers") or params.get("layers"))
    minfile = "MINFIL" in url
    params = _wms(params, "GetFeatureInfo")
    params.update(info_format="application/json", feature_count="3" if minfile else "1",
                  propertyName=MINFILE_FIELDS if minfile else FIELDS)
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params, url)
    if r.status_code != 200:
        raise BcgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BcgsError("속성이 JSON 이 아니다") from exc


def _value(props: dict, key: str) -> str:
    value = props.get(key)
    return "" if value is None else str(value).strip()


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·암석·설명은 영어 그대로, 시대만 옮긴다(`Upper Triassic` → 트라이아스기 후기)"""
    if "MINFILE_NUMBER" in props:                 # MINFILE (wetherilli 288)
        v = lambda k: _value(props, k)            # noqa: E731
        url = v("MINFILE_SUMMARY_URL")
        rows = (("이름", v("MINFILE_NAME1")), ("번호", v("MINFILE_NUMBER")), ("개발 단계", v("STATUS_DESCRIPTION")),
                ("광종", ", ".join(x for x in (v(f"COMMODITY_DESCRIPTION{n}") for n in range(1, 5)) if x)),
                ("광상 유형", v("DEPOSIT_TYPE_DESCRIPTION1")), ("갈래", v("DEPOSIT_CLASS_DESCRIPTION1")),
                ("지구조 구역", " · ".join(x for x in (v("TERRANE_DESCRIPTION"), v("TECTONIC_BELT_DESCRIPTION")) if x)),
                ("생산", "Y" if v("PRODUCTION_IND") == "Y" else ""),
                ("상세", {"text": "", "links": [{"url": url, "label": "MINFILE"}]} if url.startswith(("http://", "https://")) else ""))
        return {k: x for k, x in rows if x}
    old, young = _value(props, "MAXIMUM_AGE_NAME"), _value(props, "MINIMUM_AGE_NAME")
    age = i18n.age_tidy(old if old == young or not young else f"{old} - {young}") or _value(props, "GEOLOGICAL_PERIOD")
    hi, lo = _value(props, "MAXIMUM_AGE_VALUE"), _value(props, "MINIMUM_AGE_VALUE")
    rows = (("기호", _value(props, "STRATIGRAPHIC_UNIT_CODE")), ("이름", _value(props, "STRATIGRAPHIC_NAME")),
            ("암석", _value(props, "ROCK_TYPE_DESCRIPTION")), ("원 설명", _value(props, "ORIGINAL_DESCRIPTION")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
            ("연대", f"{hi}–{lo} Ma" if hi and lo else ""),
            ("지구조 구역", " · ".join(x for x in (_value(props, "TERRANE_NAME"), _value(props, "MORPHOTECTONIC_BELT")) if x)),
            ("편집", _value(props, "AUTHOR_NAMES")))
    return {k: v for k, v in rows if v}
