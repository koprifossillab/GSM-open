"""그린란드 정부의 광물자원 포털(ArcGIS)로 나가는 문 — 시료·연대·광물 산출지.

`kigam.py`·`vworld.py`·`geus.py` 와 나란한 **네 번째 문**이다 (CLAUDE.md
"상류마다 문이 하나"). 이 상류의 레이어는 여기로만 나간다.

- 주소: `services5.arcgis.com/wbN76kmEQ2ue8VQm/arcgis/rest/services/<서비스>/FeatureServer/0`
  그린란드 정부(광물자원청, 계정 `emni_nanoq`)가 올린 공개 FeatureServer 다.
  Asiaq 가 차린 웹지도 "Online Map Geological data from Greenland" 가 이것들을
  얹어 보인다. 값의 뿌리는 GEUS 자료다(`data.geus.dk` 링크가 딸려 온다)
- **타일이 아니라 점을 받는다.** 레이어 하나가 수백~2 만 점이라 통째로 받아
  한 덩이의 GeoJSON 으로 브라우저에 준다. 브라우저가 그리고, 누르면 그
  자리에서 속성을 읽는다 — 상류에 한 번 더 묻지 않는다
- 한 번에 2 000 점까지 준다(`maxRecordCount`). `resultOffset` 으로 넘기며 받고,
  한 장과 한 장 사이에 **쉰다** — 2 만 점이 열 번이다
- 이용 조건은 항목에 적혀 있지 않다(`licenseInfo` 가 비어 있다). 웹지도의
  한 줄 소개가 "Free Geological Data for Greenland" 다. devlog 019
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, usage

log = logging.getLogger(__name__)

#: 한 번에 받는 점의 수. 상류의 `maxRecordCount` 와 같다.
PAGE = 2000
#: 한 레이어에서 넘기는 장의 한계. 상류가 끝을 알려주지 않고 돌기만 할 때를 막는다.
MAX_PAGES = 40
#: 장과 장 사이에 쉬는 초. 한 레이어를 받는 동안 브라우저가 기다리므로
#: 너무 길게는 못 둔다 — 2 만 점이면 열 장, 쉬는 것만 5 초다.
PAUSE = 0.5
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS`).
DIGITS = arcpoints.DIGITS


class PortalError(RuntimeError):
    pass


_field = arcpoints.field


#: 레이어명 → 상류 서비스와 받는 열. **열쇠가 짧은 까닭** — 2 만 점마다 되풀이되는
#: 이름이라 짧을수록 덜 싣는다. 팝업의 이름(`label`)은 한 번만 따로 보낸다.
#: `label` 이 없는 열(색 따위)은 그리는 데만 쓰고 팝업에 올리지 않는다.
#: 팝업 이름의 영어는 `i18n.PROP_EN` 에 적는다.
LAYERS = {
    "grportal:geochron": {
        "service": "geochron",
        "item": "6ddb07fed184429cab4c8a3f1326d644",
        "style": "age",
        "fields": {
            "sample": _field("sample_no", "시료 번호"),
            "age": _field("age_num", "연대 (Ma)", "number"),
            "err": _field("uncertaint", "오차 (Ma)"),
            "interp": _field("interpreta", "해석"),
            "mineral": _field("mineral", "광물"),
            "tech": _field("technique", "측정법"),
            "appr": _field("approach", "계산법"),
            "lith": _field("lithology", "암상"),
            "rock": _field("rock_type", "암석 갈래"),
            "terrane": _field("terrane", "지괴"),
            "fm": _field("formation", "지층"),
            "unit": _field("unit", "단위"),
            "ref": _field("reference", "문헌"),
            "link": _field("details", "GEUS 상세", "link"),
        },
    },
    "grportal:mineral_occurrences": {
        "service": "mineral_occurrences",
        "item": "bf6ac25c4cd6453eb5400d464aff8fab",
        "style": "mineral",
        "fields": {
            "name": _field("name", "이름"),
            "comm": _field("commodity", "광종"),
            "group": _field("commodity_", "광종 무리"),
            "status": _field("economic_s", "경제성"),
            "link": _field("report", "보고서", "link"),
        },
    },
    "grportal:intrusions": {
        "service": "intrusions",
        "item": "0936c8ef763c46e7b9c06b92180b0d09",
        "style": "intrusion",
        "fields": {
            "name": _field("name", "이름"),
            "desc": _field("descriptio", "설명"),
            "link": _field("link", "보고서", "link"),
        },
    },
    "grportal:samples": {
        "service": "samples_grportal",
        "item": "bb962bb1fc6a420b99349f7e59992bab",
        "style": "sample",
        "fields": {
            "no": _field("sampleno", "시료 번호"),
            "type": _field("sample_typ", "시료 갈래"),
            "lith": _field("lithology_", "암상"),
            "mat": _field("material_s", "시료 기재"),
            "loc": _field("localityna", "채취 지점"),
            "by": _field("collector", "채취자"),
            "date": _field("collected_", "채취일"),
            # 포털이 시료 갈래마다 매겨 둔 색("220 220 0"). 그 색으로 그린다
            "color": _field("rgb", "", "rgb"),
        },
    },
    # 그린란드 공식 지명(Nunat Aqqi) 33 025 — 레이어로 켜지 않고 찾기 칸이 뒤진다 (wetherilli 096). 포털에 판이 다섯
    # 있다(`Nunat_Aqqi`·`…_pisortatigut_aug2018`·`Stednavne_03_08_2018_official` 따위). 열이 같고 가장 나중에
    # 고친(2019-06) `Nunat_Aqqi` 를 쓴다. 이름은 새 철자·옛 철자(`ĸ`)·덴마크어·다른 이름 넷을 다 뒤진다
    "grportal:place_names": {
        "service": "Nunat_Aqqi", "oid": "OBJECTID",
        "item": "",
        "style": "name",
        "fields": {
            "name": _field("Aqqa_stednavn", "지명"),
            "old": _field("Allattaasitoqqamik_gml_stave", "옛 철자"),
            "da": _field("Qallunaatut_Dansk", "덴마크어 이름"),
            "alt": _field("Allatut_Alternativ", "다른 이름"),
            "kind": _field("Sammisaq_Genstand", "갈래"),
            "mun": _field("Kommune", "지자체"),
        },
    },
    # ── 면과 갈래 색 (wetherilli 089) ─────────────────────────────────
    # 아래는 `style: class` 로 간다 — 극지연구소(053)와 같은 틀. 갈래(`classes`)를 받은 값에서
    # 가르고 덩이에 `legend` 를 싣는다. 면(`areal`)은 `generalize` 도(°)로 줄여 받는다.
    # `layer` 는 FeatureServer 안의 번호(적지 않으면 0), `fresh` 는 캐시를 믿는 초(적지 않으면 3 년)
    #
    # 광물 잠재 구역 — GEUS·그린란드 정부가 2009–2014 에 광종마다 연 평가 워크숍(USGS 3 단계 평가)의 구역.
    # `n90`…`n01` 은 "이 확률로 적어도 몇 개" 의 미발견 광상 수다. 색은 포털이 광종마다 매긴 것(`rgb`)
    "grportal:mineral_tracts": {
        "service": "gmom_tracts",
        "item": "91249221eda646ffa8c303936d169394",
        "style": "class", "areal": True, "generalize": 0.005,
        "classes": {"by": "work", "table": (
            ("cu", "구리", "#008c28", "square", ("Copper",)),
            ("au", "금", "#149bf0", "square", ("Gold",)),
            ("ni", "니켈", "#8c28f0", "square", ("Nickel",)),
            ("ree", "희토류", "#f0288c", "square", ("Rare Earth",)),
            ("w", "텅스텐", "#288cf0", "square", ("Tungsten",)),
            ("zn", "아연", "#8cf028", "square", ("Zinc",)),
        ), "else": ("other", "그 밖·미상", "#757575", "square")},
        "fields": {
            "tract": _field("tract_name", "구역"),
            "work": _field("workshop", "평가 광종"),
            "year": _field("year", "평가 연도"),
            "model": _field("mineralisa", "광상 모델"),
            "known": _field("number_kno", "알려진 광상 수", "number"),
            "unk": _field("number_unk", "미발견 광상 수 (추정)", "number"),
            "n90": _field("n90", "미발견 광상 수 (90%)", "number"),
            "n50": _field("n50", "미발견 광상 수 (50%)", "number"),
            "n10": _field("n10", "미발견 광상 수 (10%)", "number"),
            "n05": _field("n05", "미발견 광상 수 (5%)", "number"),
            "n01": _field("n01", "미발견 광상 수 (1%)", "number"),
            "link": _field("report", "보고서", "link"),
            "geo": _field("geology_an", "지질 해설", "link"),
        },
    },
    # 불안정 사면·매스무브먼트 — 그린란드 정부 지질과가 "작업 중, 정기적으로 고친다(마지막 2026-02)"
    # 라고 적은 지도다. 한 서비스에 그린란드어·영어 이름의 같은 레이어가 둘씩 있어(5=2, 8=7) 영어 쪽을 받는다.
    # 그래서 캐시를 30 일만 믿는다
    "grportal:unstable_slopes": {
        "service": "Map_of_unstable_slopes_and_registered_mass_movements_WFL1", "layer": 2, "oid": "OBJECTID",
        "item": "43ac21a7a6dc4d389b42637004e2cad1",
        "style": "class", "areal": True, "generalize": 0.0001, "fresh": 30 * 86400,
        "classes": {"by": "", "table": (), "else": ("slope", "불안정 사면", "#f2c200", "square")},
        "fields": {
            "place": _field("Placename", "지명"),
            "near": _field("closest_si", "가까운 마을"),
            "dist": _field("distance_s", "마을까지 (km)", "number"),
            "vol": _field("Min_volume", "최소 부피 (m³)", "number"),
            "area": _field("area", "면적 (m²)", "number"),
            "h": _field("heights", "높이 (m)", "number"),
            "run": _field("Runout_3d_", "도달 거리 (m)", "number"),
            "geol": _field("Geology", "지질"),
            "src": _field("source_dat", "원자료"),
        },
    },
    "grportal:mass_movements": {
        "service": "Map_of_unstable_slopes_and_registered_mass_movements_WFL1", "layer": 7, "oid": "OBJECTID",
        "item": "43ac21a7a6dc4d389b42637004e2cad1",
        "style": "class", "areal": True, "generalize": 0.0001, "fresh": 30 * 86400,
        "classes": {"by": "tsu", "table": (
            ("tsunami", "매스무브먼트 — 쓰나미를 일으켰다", "#b71c1c", "square", ("1",)),
        ), "else": ("event", "매스무브먼트", "#6d4c41", "square")},
        "fields": {
            "name": _field("Stednavn", "이름"),
            "when": _field("Skred_periode", "일어난 때"),
            "tsu": _field("Tsunamigeneration", "쓰나미 (1 = 일으켰다)"),
            "vol": _field("Volumen", "부피 (m³)", "number"),
            "area": _field("skredareal", "면적 (m²)", "number"),
            "h": _field("H", "낙차 (m)", "number"),
            "run": _field("Runout", "도달 거리 (m)", "number"),
            "src": _field("Kildedata", "원자료"),
            "note": _field("Remarks", "비고"),
        },
    },
    # 다이아몬드 탐사 자료(DED)의 산출지 3 029 — 킴벌라이트·램프로파이어·카보나타이트 따위의 암맥·관입체.
    # 모르는 값을 -999 로 적어 `measure` 로 받는다. 시추공·지시광물 화학은 받지 않았다
    "grportal:diamond_occurrences": {
        "service": "DED_GL_OCCURRENCES",
        "item": "2f2965291cb84ba996a5754cfeddc111",
        "style": "class",
        "classes": {"by": "rock", "table": (
            ("kimb", "킴벌라이트질", "#6a1b9a", "diamond", ("Kimberlit",)),
            ("carb", "카보나타이트", "#00897b", "dot", ("Carbonatite", "Soevite", "Fenite")),
            ("lampo", "램프로아이트", "#c2185b", "dot", ("Lamproit",)),
            ("lampr", "램프로파이어", "#ef6c00", "dot", ("Lamprophyre", "Alnoite", "Shonkinite")),
        ), "else": ("other", "그 밖·미상", "#757575", "dot")},
        "fields": {
            "loc": _field("LOCNAME", "지점"),
            "other": _field("OTHER_NAME", "다른 이름"),
            "rock": _field("ROCK_GROUP", "암석군"),
            "morph": _field("MORPHOLOGY", "산상"),
            "strike": _field("STRIKE", "주향 (°)", "measure"),
            "dip": _field("DIP", "경사 (°)", "measure"),
            "dipdir": _field("DIPDIR", "경사 방향"),
            "len": _field("DIMENSION1", "길이 (m)", "measure"),
            "wid": _field("DIMENSION2", "너비 (m)", "measure"),
            "grade": _field("DIAM_GRADE", "다이아몬드 품위"),
            "desc": _field("COMMENTS1", "기재"),
            "note": _field("COMMENTS2", "비고"),
            "srct": _field("SOURCETYPE", "출처 갈래"),
            "owner": _field("OWNERNAME", "보고한 곳"),
            "year": _field("DATE", "연도"),
        },
    },
}

#: 지도 귀퉁이에 적는 출처. 항목 주소가 있으면 그리로, 없으면 웹지도로 잇는다.
WEBMAP = "https://asiaq.maps.arcgis.com/apps/webappviewer/index.html?id=4f800688403c4cfea40175950dd94875"


def knows(name: str) -> bool:
    return name in LAYERS


def source_url(name: str) -> str:
    item = LAYERS.get(name, {}).get("item")
    return f"https://www.arcgis.com/home/item.html?id={item}" if item else WEBMAP


def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 (`arcpoints.signature`). 019 의 열쇠 그대로다 —
    틀을 떼어 냈다고 받아 둔 점을 다시 받지 않는다."""
    spec = LAYERS[name]
    head = f"{spec['service']}|FID"
    if spec.get("layer") or spec.get("generalize"):
        head = f"{spec['service']}/{spec.get('layer', 0)}|{spec.get('oid', 'FID')}|g={spec.get('generalize', 0)}"
    return arcpoints.signature(spec, head)


def fresh_seconds(name: str):
    """캐시를 믿는 초. None 이면 다른 받아온 것처럼 3 년이다 (`views.point_features`)."""
    return LAYERS[name].get("fresh")


def labels(name: str) -> dict:
    return arcpoints.labels(LAYERS[name])


def _query_url(service: str, layer: int = 0) -> str:
    return f"{settings.GRPORTAL_URL.rstrip('/')}/{service}/FeatureServer/{layer}/query"


def _get_page(service: str, fields: list, offset: int, *, layer: int = 0, oid: str = "FID",
              generalize: float = 0) -> dict:
    params = {
        "where": "1=1", "outFields": ",".join(fields), "returnGeometry": "true",
        "outSR": "4326", "f": "geojson", "orderByFields": f"{oid} ASC",
        "resultOffset": offset, "resultRecordCount": PAGE,
    }
    if generalize:
        params["maxAllowableOffset"] = generalize
    try:
        r = requests.get(_query_url(service, layer), params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털에 닿지 못했다: {exc}") from exc
    log.info("grportal %s offset=%d -> %s", service, offset, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    if r.status_code != 200:
        usage.record("grportal", ok=False, blocked=blocked)
        raise PortalError(f"그린란드 포털이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        usage.record("grportal", ok=False)
        raise PortalError("그린란드 포털이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if "error" in data:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털의 오류: {data['error'].get('message', '')}")
    usage.record("grportal", ok=True)
    return data


def fetch(name: str, pause: float = None) -> list:
    """레이어 하나의 점을 **모두** 받아 짧은 열쇠의 GeoJSON feature 목록으로.

    상류가 준 값은 고치지 않는다 — 앞뒤 빈칸만 떼고, 빈 값은 뺀다. 이 목록이
    그대로 캐시에 담긴다.
    """
    spec = LAYERS[name]
    fields = spec["fields"]
    oid = spec.get("oid", "FID")
    # FID 를 늘 함께 받는다 — 열을 골라 받으면 상류가 feature 의 `id` 를 비워 보낸다
    wanted = sorted({f["from"] for f in fields.values()} | {oid})
    return arcpoints.collect(
        lambda offset: _get_page(spec["service"], wanted, offset, layer=spec.get("layer", 0), oid=oid,
                                 generalize=spec.get("generalize", 0)),
        fields, page=PAGE, max_pages=MAX_PAGES, pause=PAUSE if pause is None else pause,
        name=name, oid=oid, areal=spec.get("areal", False))


#: 받은 feature 를 우리 꼴로 줄이는 틀은 `arcpoints` 에 있다 (NPI 와 함께 쓴다, 021)
compact = arcpoints.compact
_clean = arcpoints.clean


def class_of(spec: dict, props: dict) -> tuple:
    """feature 하나의 갈래 (code, label, color, shape). 받은 값이 표의 머리말로 시작하면 그 갈래다 —
    위에서부터 먼저 맞는 것. 캐시에는 넣지 않고 내보낼 때 가른다 — 색을 고쳐도 다시 받지 않는다."""
    classes = spec["classes"]
    value = str(props.get(classes["by"], "")) if classes["by"] else ""
    for code, label, color, shape, heads in classes["table"]:
        if value.startswith(heads):
            return code, label, color, shape
    return classes["else"]


def body(name: str, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이 (`arcpoints.body`). 갈래가 있는 레이어는 feature 마다 `code`,
    덩이에 `legend`([{code, label, color, shape, count}])를 싣는다 — 극지연구소와 같은 꼴이다."""
    spec = LAYERS[name]
    if "classes" not in spec:
        return arcpoints.body(spec, features_json)
    features = json.loads(features_json)
    counts, table = {}, {}
    for feature in features:
        code, label, color, shape = class_of(spec, feature["properties"])
        feature["properties"]["code"] = code
        counts[code] = counts.get(code, 0) + 1
        table[code] = (label, color, shape)
    order = [row[0] for row in spec["classes"]["table"]] + [spec["classes"]["else"][0]]
    legend = [{"code": c, "label": table[c][0], "color": table[c][1], "shape": table[c][2], "count": counts[c]}
              for c in order if c in counts]
    return json.dumps({"type": "FeatureCollection", "labels": arcpoints.labels(spec),
                       "links": arcpoints.links(spec), "style": "class", "legend": legend,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
