"""노르웨이 극지연구소(NPI)로 나가는 문 — 스발바르와 남극 드로닝모드랜드 지질도.

`kigam.py`·`vworld.py`·`geus.py`·`grportal.py` 와 나란한 문이다 (CLAUDE.md
"상류마다 문이 하나"). NPI 의 레이어는 여기로만 나간다. 계획은 devlog P01,
고른 까닭은 devlog 021.

주소는 셋이고 모두 NPI 의 것이다.

- `geodata.npolar.no/arcgis/rest/services` — NPI 의 ArcGIS 지도 서버. 지질도
  타일(`export`)·속성(`identify`)·범례(`legend`)·드로닝모드랜드의 점(`query`)
- `services3.arcgis.com/CflNQ7lugha7SFIt` — NPI 가 ArcGIS Online 에 올린
  FeatureServer. 스발바르 암석 시료 보관소와 지명
- `api.npolar.no` — 자료 목록. 지금은 부르지 않는다. 시료 팝업의 링크가
  `data.npolar.no` 로 잇는다

**WMS 가 아니라 REST `export` 를 중계한다.** NPI 의 WMS 는 EPSG:25833·4326 만
광고하지만 `export` 는 요청한 투영(`bboxSR`·`imageSR`)으로 그 자리에서 다시
그려 준다. 브라우저는 여느 WMS 처럼 `/wms/` 를 부르고(`LAYERS`·`BBOX`·`CRS`),
여기서 `export` 로 옮겨 적는다. 스발바르는 3413, 드로닝모드랜드는 3031 로 받는다.
3857 로 받지 않는 까닭은 devlog 021 — NPI 지도는 **축척에 따라 1:25만과 1:75만을
갈아 끼우는데**, 3857 로 물으면 북위 78° 에서 축척이 다섯 배 부풀어 1:25만이
한참 늦게 뜬다.

`Basisdata_Intern/*` 는 부르지 않는다 — "NP Svalbardkartet 안에서만 쓸 것" 이라고
적혀 있다. 여기 적은 것은 모두 CC BY 4.0 이고 출처는 `ATTRIBUTION` 이다.
"""
import base64
import io
import logging
import re

import requests
from django.conf import settings

from . import arcpoints, i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = "© Norsk Polarinstitutt (CC BY 4.0)"
#: 출처 표기가 잇는 곳 — NPI 자료 목록
DATA_URL = "https://data.npolar.no/"

#: 한 번에 받는 점의 수. 지도 서버의 `maxRecordCount` 가 1 000 인 것도 있어 거기 맞춘다.
PAGE = 1000
MAX_PAGES = 20
#: 장과 장 사이에 쉬는 초 (grportal 과 같다). 지명 8 393 점이 아홉 장이다.
PAUSE = 0.5
#: 한 장의 가장 큰 변. NPI 의 `maxImageWidth`·`maxImageHeight` 가 4096 이다.
MAX_SIZE = 4096
#: 타일을 받을 수 있는 투영. 스발바르(3413)·남극(3031), 그리고 투영 정의를 못
#: 읽은 브라우저가 떨어지는 3857.
SRS = {"EPSG:3413": 3413, "EPSG:3031": 3031, "EPSG:3857": 3857, "EPSG:900913": 3857}


class NpolarError(RuntimeError):
    pass


# ── 레이어 ──────────────────────────────────────────────────────────
#
# 타일 레이어 — 이름 → 서비스와 그 안의 레이어 번호.
#   show    그릴 레이어 번호 (`export` 의 `layers=show:`)
#   info    속성을 물을 번호 (`identify` 의 `layers=visible:`). None 이면 묻지 않는다
#   legend  범례로 그릴 번호. None 이면 범례가 없다
#   format  `export` 의 그림 꼴
#   projection  화면이 이 레이어의 타일을 받을 투영. 지역 화면의 투영과 같다
#
# **번호가 둘씩인 것은 축척이 갈라 놓은 짝이다.** NPI 는 지질 단위를 1:25만(24)과
# 1:75만(10) 두 벌로 두고, 1:25만보다 가까우면 앞의 것을, 멀면 뒤의 것을 그린다
# (상류가 레이어마다 축척 범위를 걸어 두었다 — `dynamicLayers` 로도 풀리지 않는다).
# 하나만 켜면 다른 축척에서 빈 타일이 온다. 그래서 짝을 한 레이어로 묶었다.
# 속성도 `visible:` 로 물어 **그 축척에서 보이는 것**을 읽는다.

TILES = {
    "npolar:svalbard_units": {
        "service": "Temadata/G_Geologi_Svalbard_S250_S750", "projection": "EPSG:3413", "show": [10, 24], "info": [10, 24],
        "legend": [24], "format": "png32"},
    "npolar:svalbard_faults": {
        "service": "Temadata/G_Geologi_Svalbard_S250_S750", "projection": "EPSG:3413", "show": [2, 3, 15, 16], "info": [2, 3, 15, 16],
        "legend": [16], "format": "png32"},
    # 인쇄된 1:10만·1:25만 지질도를 이어 붙이고 음영을 입힌 한 장. 그림이라 속성이 없다.
    # png32 로 받으면 한 장이 0.5 MB 라 256 색(png8)으로 받는다 — 0.09 MB, 눈으로는 같다
    "npolar:svalbard_paper": {
        "service": "Temadata/G_Geologi_Svalbard_S100_S250_Papir_Hs", "projection": "EPSG:3413", "show": [0], "info": None,
        "legend": None, "format": "png8"},
    "npolar:svalbard_type_localities": {
        "service": "Temadata/G_Lithostratigraphic_Lexicon_of_Svalbard", "projection": "EPSG:3413", "show": [0], "info": [0],
        "legend": [0], "format": "png32"},
    # 스발바르 1:10만 도폭 스캔(P01 6 단계) — 인쇄한 도폭을 지도면만 오려 붙인 래스터 38 장.
    # `1` 은 그 묶음(Kartbilder)이다. 스캔이라 png8 로 받는다. 도폭 하나만 그리는 것은
    # `npolar:svalbard_sheets@<KartNR>` 이다(`sheet_spec`)
    "npolar:svalbard_sheets": {
        "service": "Temadata/G_Geologi_Kartblad", "projection": "EPSG:3413", "show": [1], "info": None,
        "legend": None, "format": "png8"},
    # 빙하 전면 변화(wetherilli 094) — 1936–2025 년의 빙하 끝선 4 064 줄. NPI 가 연도(`Date_year`)마다
    # 색을 달리해 그려 준다(23 갈래). 줄마다 누르면 빙하 이름·관측일·영상·길이가 온다. CC BY 4.0
    "npolar:svalbard_glacier_fronts": {
        "service": "Temadata/I_Glacier_Fronts_Svalbard", "projection": "EPSG:3413", "show": [0], "info": [0],
        "legend": [0], "format": "png32"},
    # 남극 드로닝모드랜드 — 1:25만(6)과 1:500만(7)이 스발바르처럼 축척으로 갈린다
    "npolar:dml_units": {
        "service": "Temadata/G_Geologi_DML", "projection": "EPSG:3031", "show": [6, 7], "info": [6, 7],
        "legend": [6], "format": "png32"},
    "npolar:dml_structures": {
        "service": "Temadata/G_Geologi_DML", "projection": "EPSG:3031", "show": [4], "info": [4], "legend": [4], "format": "png32"},
    "npolar:dml_tectonic": {
        "service": "Temadata/G_Geologi_DML", "projection": "EPSG:3031", "show": [3], "info": [3], "legend": [3], "format": "png32"},
}

_f = arcpoints.field

#: 점 레이어 — 타일이 아니라 점을 통째로 받는다 (grportal 과 같은 틀, `arcpoints`).
#:   where   "map" 이면 지도 서버(`NPOLAR_URL`), "features" 면 ArcGIS Online(`NPOLAR_FEATURES_URL`)
#:   path    그 밑의 레이어 주소
#:   oid     차례를 매기는 열. 장을 넘길 때 이것으로 줄 세운다
#:   paged   False 면 장을 넘기지 않고 한 번에 받는다 — 드로닝모드랜드 지점은
#:           "Pagination is not supported" 로 돌려보낸다(1 131 점, 한 장에 든다)
#: 팝업 이름의 영어는 `i18n.PROP_EN` 에 적는다.
POINTS = {
    "npolar:rock_archive": {
        "where": "features", "path": "rock_archive_svalbard/FeatureServer/0", "oid": "ObjectId",
        "style": "rock", "source": "https://data.npolar.no/geology/sample",
        "fields": {
            "no": _f("sampleName", "시료 번호"),
            "lith": _f("lithology", "암상"),
            "place": _f("placename", "지명"),
            "year": _f("collectedYear", "채취 연도"),
            "by": _f("geologists", "채취자"),
            "exp": _f("expedition", "탐사"),
            "acc": _f("positionAccuracy", "위치 정확도"),
            "cab": _f("cabinetRef", "보관함"),
            "link": _f("rockArchive", "시료 보관소", "link"),
            "photo": _f("image", "사진", "link"),
        },
    },
    "npolar:dml_geochron": {
        "where": "map", "path": "Temadata/G_Geologi_DML/MapServer/2", "oid": "OBJECTID",
        "style": "age", "source": "https://data.npolar.no/dataset/7a2dbf63-9214-40ac-b296-e30a5e0459d3",
        "fields": {
            # `age` 라는 열쇠는 화면이 색을 고르는 데 쓴다 (map.js 의 ageColor)
            "age": _f("Age", "연대 (Ma)", "number"),
            "kind": _f("type", "연대 갈래"),
            "sample": _f("sample", "시료 번호"),
            "rock": _f("rock_descr", "암석"),
            "tech": _f("method", "측정법"),
            "mineral": _f("material", "광물"),
            "note": _f("comment", "비고"),
            "ref": _f("ref_full", "문헌"),
            "refno": _f("ref_short", "문헌 번호"),
            "loc": _f("loc_type", "위치 근거"),
        },
    },
    "npolar:dml_samples": {
        "where": "map", "path": "Temadata/G_Geologi_DML/MapServer/0", "oid": "OBJECTID",
        "style": "rock", "source": "https://data.npolar.no/geology/sample",
        "fields": {
            "no": _f("title", "시료 번호"),
            "lith": _f("lithology", "암상"),
            "desc": _f("sample_description", "기재"),
            "place": _f("placename", "지명"),
            "year": _f("collected_year", "채취 연도"),
            "by": _f("geologist", "채취자"),
            "exp": _f("expedition", "탐사"),
            "acc": _f("position_accuracy", "위치 정확도"),
            "link": _f("archive", "시료 보관소", "link"),
            "photo": _f("image_uri", "사진", "link"),
        },
    },
    "npolar:dml_sites": {
        "where": "map", "path": "Temadata/G_Geologi_DML/MapServer/1", "oid": "FID", "paged": False,
        "style": "site", "source": "https://data.npolar.no/dataset/7a2dbf63-9214-40ac-b296-e30a5e0459d3",
        "fields": {
            "site": _f("Locality", "지점"),
            "samples": _f("Samples", "시료"),
            "note": _f("Comment", "비고"),
            "exp": _f("Expedition", "탐사"),
        },
    },
    # 지명 — 레이어로 켜지 않고 찾기 칸이 뒤진다 (카탈로그에 없다)
    # 스발바르 도폭 경계(P01 6 단계) — 면 45 개. 점이 아니라 면이라 `areal`, 상류의 선이
    # 촘촘해(4.7 MB) 0.001° 로 줄여 받는다(10 KB). `csv.Folk` 에는 사람 이메일이 들어
    # 있어 받지 않는다. `sheets` 면 스캔이 있는 도폭에 `scan` 을 붙인다
    "npolar:svalbard_sheet_index": {
        "where": "map", "path": "Temadata/G_Geologi_Kartblad/MapServer/120",
        "oid": "S_100_Geologi_Kartblad_Indeks.FID", "paged": False, "areal": True,
        "generalize": 0.001, "sheets": True,
        "style": "sheet", "source": "https://data.npolar.no/",
        "fields": {
            "code": _f("S_100_Geologi_Kartblad_Indeks.KartNR", "도폭 번호"),
            "name": _f("S_100_Geologi_Kartblad_Indeks.Navn", "도폭명"),
            "scale": _f("S_100_Geologi_Kartblad_Indeks.csv.Skala", "축척"),
            "printed": _f("S_100_Geologi_Kartblad_Indeks.csv.aar", "발행"),
            "field": _f("S_100_Geologi_Kartblad_Indeks.csv.Feltarbeid_status", "야외 조사"),
            "digital": _f("S_100_Geologi_Kartblad_Indeks.csv.Digitaliseringsstatus", "수치화"),
            "pub": _f("S_100_Geologi_Kartblad_Indeks.csv.NP_publikasjonsdatabase", "출판물", "link"),
            "archive": _f("S_100_Geologi_Kartblad_Indeks.csv.NP_kartarkiv", "지도 보관소", "link"),
        },
    },
    "npolar:place_names": {
        "where": "features", "path": "NPI_Place_Names_Svalbard/FeatureServer/0", "oid": "ObjectId",
        "style": "name", "source": "https://placenames.npolar.no/",
        "fields": {"name": _f("name", "지명"), "area": _f("area", "지역")},
    },
    # 드로닝모드랜드 지명 4 074 — 스발바르와 같은 꼴이다 (wetherilli 096). CC BY 4.0
    "npolar:dml_place_names": {
        "where": "features", "path": "NPI_Place_Names_Dronning_Maud_Land/FeatureServer/0", "oid": "ObjectId",
        "style": "name", "source": "https://placenames.npolar.no/",
        "fields": {"name": _f("name", "지명"), "area": _f("area", "지역")},
    },
}


def knows(name: str) -> bool:
    return name in TILES


def knows_points(name: str) -> bool:
    return name in POINTS


def source_url(name: str) -> str:
    return POINTS.get(name, {}).get("source") or DATA_URL


# ── 부르기 ──────────────────────────────────────────────────────────

def _get(url: str, params: dict):
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("npolar", ok=False)
        raise NpolarError(f"NPI 에 닿지 못했다: {exc}") from exc
    log.info("npolar %s -> %s", r.url, r.status_code)
    usage.record("npolar", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _json(r) -> dict:
    if r.status_code != 200:
        raise NpolarError(f"NPI 가 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise NpolarError("NPI 가 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if isinstance(data, dict) and "error" in data:
        raise NpolarError(f"NPI 의 오류: {data['error'].get('message', '')}")
    return data


def _map_url(service: str, op: str) -> str:
    return f"{settings.NPOLAR_URL.rstrip('/')}/{service}/MapServer/{op}"


def _spec(params: dict, *keys) -> tuple:
    for key in keys:
        name = (params.get(key) or "").split(",")[0].strip()
        if name in TILES:
            return name, TILES[name]
        if name.startswith(SHEETS + "@"):
            return name, sheet_spec(name)
    raise NpolarError("NPI 레이어가 아니다")


# ── 도폭 하나 (P01 6 단계) ────────────────────────────────────────────
#
# 도폭 경계의 팝업에서 "이 도폭만 켜기" 를 누르면 `npolar:svalbard_sheets@A4G` 를 켠다.
# 도폭 번호(KartNR)로 Kartbilder 묶음(`1`) 안의 래스터를 찾는다 — 래스터 이름이
# `A4G-Vasahalvøya_100_2007.tif` 처럼 번호로 시작한다. 한 도폭에 래스터가 여럿인 것이
# 있다(FG23G 여섯, DE23G 셋). 대응표는 지도 서버의 레이어 목록에서 한 번 받아 하루 믿는다.

SHEETS = "npolar:svalbard_sheets"
_SHEET_CODE = re.compile(r"^[A-Z]{1,2}\d{1,4}G$")
#: 대응표를 믿는 초
SHEET_TABLE_SECONDS = 24 * 3600
_sheet_memo = {}


def sheet_rasters() -> dict:
    """도폭 번호 → Kartbilder 안의 래스터 번호들."""
    import time
    now = time.time()
    if _sheet_memo.get("at", 0) + SHEET_TABLE_SECONDS > now:
        return _sheet_memo["table"]
    spec = TILES[SHEETS]
    data = _json(_get(_map_url(spec["service"], ""), {"f": "json"}))
    group = set(spec["show"])
    table = {}
    for layer in data.get("layers") or []:
        if layer.get("parentLayerId") not in group:
            continue
        code = str(layer.get("name") or "").split("-", 1)[0].strip()
        if _SHEET_CODE.match(code):
            table.setdefault(code, []).append(int(layer["id"]))
    _sheet_memo.update(at=now, table=table)
    return table


def sheet_spec(name: str) -> dict:
    """`npolar:svalbard_sheets@A4G` → 그 도폭의 래스터만 그리는 스펙."""
    code = name.split("@", 1)[1] if "@" in name else ""
    if not _SHEET_CODE.match(code):
        raise NpolarError("도폭 번호가 아니다")
    ids = sheet_rasters().get(code)
    if not ids:
        raise NpolarError(f"스캔이 없는 도폭이다: {code}")
    return dict(TILES[SHEETS], show=ids)


def _srs(params: dict) -> int:
    code = (params.get("crs") or params.get("srs") or "").upper()
    if code not in SRS:
        raise NpolarError(f"받지 않는 투영이다: {code}")
    return SRS[code]


def _box(params: dict) -> list:
    try:
        box = [float(v) for v in (params.get("bbox") or "").split(",")]
    except ValueError as exc:
        raise NpolarError("BBOX 를 읽지 못했다") from exc
    if len(box) != 4 or not (box[0] < box[2] and box[1] < box[3]):
        raise NpolarError("BBOX 를 읽지 못했다")
    return box


def _size(params: dict) -> tuple:
    try:
        w, h = int(params.get("width") or 256), int(params.get("height") or 256)
    except ValueError as exc:
        raise NpolarError("크기를 읽지 못했다") from exc
    if not (0 < w <= MAX_SIZE and 0 < h <= MAX_SIZE):
        raise NpolarError("그림이 너무 크다")
    return w, h


def export_params(params: dict) -> tuple:
    """WMS `GetMap` 꼴 → (`export` 주소, 변수). 시험이 이것을 따로 본다."""
    _, spec = _spec(params, "layers")
    srs, box, (w, h) = _srs(params), _box(params), _size(params)
    return _map_url(spec["service"], "export"), {
        "bbox": ",".join(repr(v) for v in box), "bboxSR": srs, "imageSR": srs,
        "size": f"{w},{h}", "dpi": 96, "format": spec["format"], "transparent": "true",
        "layers": "show:" + ",".join(str(i) for i in spec["show"]), "f": "image",
    }


def get_map(params: dict):
    """`GetMap` → `export`. (바이트, content-type). 그림이 아니면 NpolarError."""
    url, sent = export_params(params)
    r = _get(url, sent)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NpolarError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def identify_params(params: dict) -> tuple:
    """WMS `GetFeatureInfo` 꼴 → (`identify` 주소, 변수).

    누른 픽셀(`I`·`J`, 1.1.1 이면 `X`·`Y`)을 BBOX 안의 좌표로 옮긴다. 픽셀의
    한가운데를 짚는다. 둘레(`tolerance`)는 3 픽셀 — 선(단층)을 누르기에 넉넉하고,
    면(지질 단위)에서 옆 단위까지 딸려 오지는 않는다.
    """
    _, spec = _spec(params, "query_layers", "layers")
    if not spec["info"]:
        raise NpolarError("속성이 없는 레이어다")
    srs, box, (w, h) = _srs(params), _box(params), _size(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise NpolarError("누른 자리를 읽지 못했다") from exc
    x = box[0] + (i + 0.5) * (box[2] - box[0]) / w
    y = box[3] - (j + 0.5) * (box[3] - box[1]) / h
    return _map_url(spec["service"], "identify"), {
        "geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": srs,
        "layers": "visible:" + ",".join(str(n) for n in spec["info"]), "tolerance": 3,
        "mapExtent": ",".join(repr(v) for v in box), "imageDisplay": f"{w},{h},96",
        "returnGeometry": "false", "f": "json",
    }


def get_feature_info(params: dict) -> dict:
    """`identify` → KIGAM 과 같은 꼴(`features`). 속성 이름은 상류의 것 그대로 담는다 —
    사람이 읽을 이름으로 바꾸는 것은 내보낼 때다(`friendly`)."""
    url, sent = identify_params(params)
    data = _json(_get(url, sent))
    features = []
    for res in data.get("results") or []:
        attrs = res.get("attributes") or {}
        oid = attrs.get("OBJECTID", attrs.get("FID", attrs.get("OBJECTID_1", "")))
        features.append({"id": f"{res.get('layerId')}.{oid}", "properties": attrs})
    return {"features": features}


# ── 속성 이름 ────────────────────────────────────────────────────────
#
# identify 는 열의 **별칭**을 준다(`Stratigraphic Unit`·`Type section / area`).
# 여기 없는 열은 팝업에 올리지 않는다 — 넓이·길이·색 번호·내부 번호가 대부분이다.
# 차례는 이 표의 차례다. 영어는 `i18n.PROP_EN`.

FRIENDLY = {
    # 스발바르 지질 단위·단층
    "NAME": "이름",
    "Name": "이름",
    "NAVN": "노르웨이어 이름",
    "MAIN_LITHO": "주 암상",
    "AGE_PERIOD": "지질시대",
    "AGE_BASE": "시대 하한",
    "AGE_TOP": "시대 상한",
    "SUPERIOR_U": "상위 단위",
    "TYPE": "갈래",
    "Type": "갈래",
    "DATING_MET": "연대 근거",
    "ACCURACY": "정확도",
    "GEO_CODE": "범례 번호",
    # 층서명 모식지
    "Stratigraphic Unit": "층서명",
    "Type section / area": "모식지",
    "Nature of section": "모식지 갈래",
    "UTM POSITION": "UTM 위치",
    "ID": "번호",
    # 드로닝모드랜드
    "Former_nam": "옛 이름",
    "F250_000_CO": "범례 번호",
    "REFERENCE": "문헌",
    "REFERENCES": "문헌",
    "References": "문헌",
    "Reference": "문헌",
    "REMARKS": "비고",
    "URL": "층서 사전",
    # 빙하 전면 (wetherilli 094). `Name` 은 위의 "이름", `Ident` 는 NPI 의 빙하 번호라 싣지 않는다
    "Date": "관측일",
    "Source": "원자료 (영상)",
    "Length_km": "전면 길이 (km)",
}
#: 링크로 그릴 속성 (http·https 만)
LINK_PROPS = {"URL"}
#: 값을 지질시대로 읽어 한국어판에서 옮길 속성. 값은 영문 ICS 명칭이다
AGE_PROPS = ("지질시대", "시대 하한", "시대 상한")
_EMPTY = ("", " ", "Null", "null", "<Null>")


def friendly(props: dict, lang: str = "ko") -> dict:
    """identify 의 속성 → 팝업. 이름을 바꾸고, 한국어판이면 지질시대를 옮긴다.
    노르웨이어 이름(`NAVN`)·지층명·암상은 옮기지 않는다 (CLAUDE.md "영어판")."""
    out = {}
    for key, label in FRIENDLY.items():
        value = props.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value in _EMPTY or value is None or label in out:
            continue
        if key in LINK_PROPS:
            if not str(value).lower().startswith(("http://", "https://")):
                continue
            value = {"text": "", "links": [{"url": str(value), "label": "열기"}]}
        elif label in AGE_PROPS and lang == "ko":
            value = i18n.age_ko(value)
        elif key == "Date" and re.fullmatch(r"\d{8}", str(value)):
            value = f"{str(value)[:4]}-{str(value)[4:6]}-{str(value)[6:]}"     # 빙하 전면의 20230910
        else:
            value = decimal_point(value)
            if key == "Length_km" and isinstance(value, str) and _NUMBER.fullmatch(value):
                value = f"{float(value):.2f}"
        out[label] = value
    return out


#: identify 가 노르웨이 꼴로 적는 소수 — 소수점이 쉼표다("3,595676", wetherilli 094). 노르웨이 꼴은 천 단위를 빈칸으로 띄우므로
#: 쉼표 하나는 소수점으로 읽는다. 쉼표가 둘 이상("1,234,567")이면 꼴이 달라 걸리지 않는다
_COMMA_DECIMAL = re.compile(r"-?\d+,\d+")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def decimal_point(value):
    """쉼표 소수(`"3,595676"`)를 점 소수(`"3.595676"`)로. 그 꼴이 아니면 그대로 — 어느 열이든 여기 한 곳에서 고친다 (wetherilli 193).
    쉼표가 하나뿐이고 양쪽이 숫자일 때만이라 "Hornsund, Sørkapp" 같은 글은 건드리지 않는다."""
    if isinstance(value, str) and _COMMA_DECIMAL.fullmatch(value.strip()):
        return value.strip().replace(",", ".")
    return value


# ── 범례 ────────────────────────────────────────────────────────────
#
# 지도 서버의 `legend?f=json` 은 칸마다 작은 그림(base64)과 이름을 준다. 화면은
# 범례를 그림 한 장으로 받으므로(`/legend/`) 여기서 이어 붙인다. WMS 의
# `GetLegendGraphic` 도 있지만 WMS 의 레이어 번호가 REST 의 번호와 달라
# (WMS 의 "10" 이 REST 의 단층이다) 번호표를 하나 더 들고 다녀야 한다.

ROW = 22
PAD = 6


def get_legend(layer: str):
    spec = TILES.get(layer)
    if not spec or not spec["legend"]:
        raise NpolarError("범례가 없는 레이어다")
    data = _json(_get(_map_url(spec["service"], "legend"), {"f": "json"}))
    rows = []
    for item in data.get("layers") or []:
        if item.get("layerId") in spec["legend"]:
            rows.extend(item.get("legend") or [])
    if not rows:
        raise NpolarError("범례가 비어 있다")
    return draw_legend(rows), "image/png"


def draw_legend(rows: list) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:                        # 옛 Pillow — 크기를 못 고른다
        font = ImageFont.load_default()
    labels = [(r.get("label") or "").strip() or "-" for r in rows]
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    width = min(520, max(int(probe.textlength(t, font=font)) for t in labels) + 36 + PAD * 2)
    image = Image.new("RGB", (width, ROW * len(rows) + PAD * 2), "white")
    draw = ImageDraw.Draw(image)
    for index, (row, text) in enumerate(zip(rows, labels)):
        y = PAD + index * ROW
        try:
            swatch = Image.open(io.BytesIO(base64.b64decode(row.get("imageData") or ""))).convert("RGBA")
            image.paste(swatch, (PAD, y + (ROW - swatch.height) // 2), swatch)
        except Exception:                    # 그림 한 칸이 깨져도 이름은 적는다
            pass
        draw.text((PAD + 28, y + 4), text, fill=(40, 40, 40), font=font)
    out = io.BytesIO()
    # 256 색으로 줄인다 — 스발바르 지질 단위 336 칸이 0.33 MB 에서 3 분의 1 쯤으로
    image.quantize(colors=256).save(out, "PNG", optimize=True)
    return out.getvalue()


# ── 점 ──────────────────────────────────────────────────────────────

def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 (`arcpoints.signature`)."""
    spec = POINTS[name]
    return arcpoints.signature(spec, f"{spec['where']}:{spec['path']}|{spec['oid']}")


def _point_url(spec: dict) -> str:
    root = settings.NPOLAR_FEATURES_URL if spec["where"] == "features" else settings.NPOLAR_URL
    return f"{root.rstrip('/')}/{spec['path']}/query"


def fetch(name: str, pause: float = None) -> list:
    """점 레이어 하나를 **모두** 받아 짧은 열쇠의 GeoJSON feature 목록으로."""
    spec = POINTS[name]
    fields = spec["fields"]
    wanted = sorted({f["from"] for f in fields.values()} | {spec["oid"]})
    url = _point_url(spec)
    paged = spec.get("paged", True)

    def page(offset):
        params = {"where": "1=1", "outFields": ",".join(wanted), "returnGeometry": "true",
                  "outSR": "4326", "f": "geojson"}
        if spec.get("generalize"):
            params["maxAllowableOffset"] = spec["generalize"]
        if paged:
            params.update(orderByFields=f"{spec['oid']} ASC", resultOffset=offset, resultRecordCount=PAGE)
        return _json(_get(url, params))

    if not paged:
        data = page(0)
        rows = [row for row in (arcpoints.compact(f, fields, spec["oid"], areal=spec.get("areal", False))
                                for f in data.get("features") or []) if row is not None]
        if spec.get("sheets"):
            scans = sheet_rasters()
            for row in rows:
                if row["properties"].get("code") in scans:
                    row["properties"]["scan"] = 1
        return rows
    return arcpoints.collect(page, fields, page=PAGE, max_pages=MAX_PAGES,
                             pause=PAUSE if pause is None else pause, name=name)


def body(name: str, features_json: bytes) -> bytes:
    return arcpoints.body(POINTS[name], features_json)


# ── 지명 찾기 ────────────────────────────────────────────────────────

def match_places(features: list, query: str, limit: int = 20) -> list:
    """받아 둔 지명 가운데 `query` 에 맞는 것 — 틀은 `arcpoints.match_index` 에 있다 (wetherilli 096)."""
    return arcpoints.match_index(arcpoints.name_index(features, ("name",), ("area",)), query, limit)
