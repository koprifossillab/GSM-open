"""말레이시아 광물지구과학국(JMG)의 MyGEMS 로 나가는 문 — 주(州)별 암상·암석 연대 (wetherilli 228).

- 주소: `mygems.jmg.gov.my/server/rest/services/Demarcation/Litology_by_Negeri/MapServer` (ArcGIS REST). 열쇠가 없다. 포털 검색으로
  찾았다(public). **WMSServer 가 꺼져 있다** — 멕시코(`sgm.py`)처럼 화면이 보내는 WMS 변수(3857 범위·크기)를 REST `export`·`identify` 로 옮긴다
- 레이어가 **주마다 따로**다 — 13 주와 연방 직할구 둘(사바·사라왁 포함)마다 `Lithology of …`(짝수 번호)와 `Rock age of …`(홀수)가 짝이다.
  우리 레이어 둘(`jmg:lithology`·`jmg:age`)이 각각 열다섯을 한 번에 부른다. 주 경계에서 끊긴다
- 원본이 3857 이다(쿠알라룸푸르 둘레 256² 0.9 초). 축척은 적혀 있지 않다(1:50만–1:100만 편집으로 보인다)
- 속성은 identify JSON — 반도는 `AGE`(오탈자 `Caroboniferous` 가 원자료에 있다)·`GLS`·`GFD`·`STATE`, 보르네오는 `GLN`(이름)·`GAM`/`GAX`
  (젊은/오랜 시대)·`NAM` 처럼 열이 조금 다르다
- 범례: 암상은 REST `legend` 의 칸을 이름으로 묶어 목록으로 낸다(46 칸). 연대는 반도와 보르네오의 칸이 달라(`CRETACEOUS, JURASSIC` 과
  `JKSer`) 범례를 두지 않는다 — 누르면 뜬다
- 조건: 찾지 못했다 — **밖에 열기 전에 사람이 읽는다**. CORS 는 Origin 을 되비춘다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "jmg:"
ATTRIBUTION = ('<a href="https://mygems.jmg.gov.my/" target="_blank" rel="noopener">JMG Malaysia (MyGEMS)</a> — '
               "Lithology and rock age by state")
#: 우리 이름 → REST 번호들 — 암상은 짝수, 연대는 홀수(주 열다섯)
LAYERS = {"jmg:lithology": tuple(range(0, 30, 2)), "jmg:age": tuple(range(1, 30, 2))}
LEGEND_LAYERS = ("jmg:lithology",)
LEGEND_MAX_AGE = 30 * 86400


class JmgError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _one(params: dict) -> str:
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise JmgError(f"모르는 레이어다: {names}")
    return names[0]


def _base() -> str:
    return f"{settings.JMG_URL.rstrip('/')}/rest/services/Demarcation/Litology_by_Negeri/MapServer"


def _get(path: str, params: dict):
    left = usage.paused()
    if left:
        raise JmgError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{_base()}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 45),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("jmg", ok=False)
        raise JmgError(f"JMG 에 닿지 못했다: {exc}") from exc
    log.info("JMG %s -> %s", r.url, r.status_code)
    usage.record("jmg", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _view(params: dict):
    """WMS 변수 → (3857 범위 네 수, 너비, 높이). 화면은 늘 3857 로 묻는다"""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in ("EPSG:3857", "EPSG:900913"):
        raise JmgError(f"3857 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise JmgError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise JmgError("범위·크기가 맞지 않다")
    return bbox, width, height


def get_map(params: dict):
    """WMS GetMap → REST export. 주 열다섯을 한 장에"""
    ids = LAYERS[_one(params)]
    bbox, width, height = _view(params)
    r = _get("export", {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": "3857", "imageSR": "3857",
                        "size": f"{width},{height}", "format": "png32", "transparent": "true", "dpi": "96",
                        "layers": "show:" + ",".join(str(i) for i in ids), "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise JmgError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """WMS GetFeatureInfo → REST identify. 누른 화소 가운데를 3857 점으로"""
    ids = LAYERS[_one(params)]
    bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise JmgError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get("identify", {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": "3857",
                          "layers": "all:" + ",".join(str(i) for i in ids), "tolerance": "1",
                          "mapExtent": ",".join(repr(v) for v in bbox), "imageDisplay": f"{width},{height},96",
                          "returnGeometry": "false", "f": "json"})
    try:
        data = r.json()
    except ValueError as exc:
        raise JmgError("속성이 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise JmgError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": [{"id": f"{x.get('layerName', '')}.{n}", "properties": x.get("attributes") or {}}
                         for n, x in enumerate(data.get("results") or [])][:1]}


def get_legend(layer: str):
    raise JmgError("그림 범례 대신 목록 범례(`legend_rows`)를 쓴다")


def legend_rows(layer: str) -> list:
    """REST `legend` 의 암상 칸(짝수 레이어)을 이름으로 묶어 — 주마다 같은 칸이 되풀이된다. 한 번 받아 담아 둔다"""
    if layer not in LEGEND_LAYERS:
        raise JmgError(f"범례가 없는 레이어다: {layer}")
    key = tilecache.key_text("jmg-legend", layer)
    held = tilecache.get(key, ".json", max_age=LEGEND_MAX_AGE)
    if held is None:
        r = _get("legend", {"f": "json"})
        try:
            data = r.json()
        except ValueError as exc:
            raise JmgError("범례가 JSON 이 아니다") from exc
        if r.status_code != 200 or data.get("error"):
            raise JmgError(f"범례를 읽지 못했다 (status={r.status_code})")
        held = json.dumps(arcwms.legend_list(data, layer_ids=LAYERS[layer])).encode("utf-8")
        tilecache.put(key, held, ".json")
    rows = [{"symbol": "", "lithology": label.rstrip("."), "age": "", "color": "transparent", "swatch": swatch}
            for label, swatch in json.loads(held)]
    return sorted(rows, key=lambda r: r["lithology"].lower())


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) or "").strip()
    return "" if value.lower() in ("null", "none") else value


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(영어)은 그대로, 시대만 옮긴다. 반도의 주는 `AGE` 가, 보르네오(사바·사라왁)는 `GAM`(젊은)·`GAX`(오랜)만
    온다 — 둘 다 있으면 둘에서 짓는다(`AGE` 에는 오탈자가 있다)"""
    young, old = _value(props, "GAM"), _value(props, "GAX")
    age = i18n.age_tidy(f"{young}, {old}" if young and old else _value(props, "AGE"))
    rows = (("기호", _value(props, "GLL")), ("이름", _value(props, "GLN")), ("암석 갈래", _value(props, "GLS")),
            ("암석", _value(props, "HOR")), ("설명", _value(props, "GFD")),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age),
            ("주", _value(props, "STATE") or _value(props, "NAM")))
    return {k: v for k, v in rows if v}
