"""SGM(멕시코 지질조사소)로 나가는 문 — 멕시코 지질·광업도 1:25만·1:5만 연속판 (wetherilli 206).

- 주소: `portal.sgm.gob.mx/arcgis/rest/services/SGM/SUNGeologiaContinuoMineDatosEs/MapServer` (ArcGIS REST). GeoInfoMex 가 쓰는
  서비스다. 열쇠가 없다. **WMSServer 는 400** 이라 WMS 로 받지 못한다 — 화면이 보내는 WMS 변수(3857 범위·크기)를 이 문이 REST `export`
  로 옮겨 묻는다(PGC 경사와 같은 길). 그래서 화면에서는 다른 WMS 상류와 다르지 않다
- 레이어명은 `sgm:<REST 번호>` — `8` 암상 1:25만(전국)·`7` 암상 1:5만(광업 지구)·`6` 구조 1:25만·`5` 구조 1:5만
- 2026-10-04 에 쟀다 — 나라 전체(줌 5) 512² 가 5.9 초, 사카테카스 둘레(줌 9) 1.3 초. 타일 캐시는 없다
- 속성은 REST `identify` — 열 별칭(Clave·Litología·Roca·Formación·Era·Periodo·Edad inicial·Edad final)으로 온다
- 범례는 보는 범위의 것 — REST 범례는 1:5만 2 571 칸·1:25만 888 칸(1.3 MB)이다. 페루(`ingemmet.py`)처럼 범위 안의 단위는 통계 질의,
  색은 칠하기 규칙(`CLAVE_SGM`)에서 찾는다
- 시대는 에스파냐어다 — `i18n.age_es` 로 ICS 영문을 거쳐 한국어판이면 `i18n.age_ko`
- 조건: datos.gob.mx 의 "Cartografía Geológica de la República Mexicana 1:250,000" 이 **CC BY 4.0**. 서비스 저작권 "© SGM"
- **같은 서버의 다른 서비스도 이 문으로 간다** (wetherilli 219) — 지질 연대 측정 점(`SunEdadesGeocronologicas`, 7 740 점, 시대 색),
  고생물 산지(`Paleontologia`, 105 곳 — 서버 목록에는 감춰져 있고 주소로만 열린다), 광상 1:25만(`SUNYacimientosMinerales250` — 광산 9 465 점·
  광화 지역·광산 지구). 이름은 `sgm:<서비스>:<REST 번호>`(`SERVICES`). 그림·누른 자리·범례의 길은 지질도와 같다. 광산은 나라 전체로 보면
  기호가 땅을 덮어 줌 8 부터다
- **지화학**(wetherilli 233) — 하천 퇴적물 시료 21 만 5 천 점(`SUNGeoquimica`, 원소 34 가지, 줌 9 부터), 원소 여섯(은·코발트·구리·망간·납·아연)의
  이상 지점 1:25만(`SUNAnomalias250`, 줌 8)·1:5만(`SUNAnomalias50`, 줌 10). 이상 지점은 함량 구간으로 칠해져 범례를 그 구간(`BREAKS`)으로 낸다.
  광상의 변질대·비금속 광화 지역, 광산 1:5만(`SUNYacimientosMinerales`, 4 만 6 천 점, 줌 10)도. 같은 서버의 지자기(`DatosAbiertos` 7)는
  나라 한 장이 16 초에 면이 조각나 있어 싣지 않았다
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, i18n, metatile, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "sgm:"
ATTRIBUTION = ('<a href="https://www.sgm.gob.mx/GeoInfoMexGobMx/" target="_blank" rel="noopener">© SGM</a> '
               "(Servicio Geológico Mexicano, CC BY 4.0)")
#: 이름 가운데 마디 → REST 서비스(`SGM_URL` 의 `services/` 뒤). 마디가 없는 `sgm:8` 은 지질도(`SGM_URL`) 그대로
SERVICES = {"edades": "SGM/SunEdadesGeocronologicas", "paleo": "SGM/Paleontologia", "yac": "SGM/SUNYacimientosMinerales250",
            "yac50": "SGM/SUNYacimientosMinerales", "geoq": "SGM/SUNGeoquimica",
            "anom250": "SGM/SUNAnomalias250", "anom50": "SGM/SUNAnomalias50",
            # 지자기(wetherilli 282) — 요청마다 10 초 넘게 걸려 244 에서 미뤘다. 메타타일(`metatile.py`)로 받는다
            "datos": "DatosAbiertos/DatosAbiertos"}
#: 이상 지점 레이어의 원소 — REST 번호 차례(은·코발트·구리·망간·납·아연)
ANOMALY_ELEMENTS = ("Ag", "Co", "Cu", "Mn", "Pb", "Zn")
#: 레이어 → (REST 번호, 처음 그리는 화면 줌, 누르기가 되나)
LAYERS = {
    "sgm:8": (8, None, True),
    "sgm:7": (7, 10, True),         # 상류 minScale 75만 — 화면 줌 10 남짓부터 그린다
    "sgm:6": (6, None, False),
    "sgm:5": (5, 9, False),         # 상류 minScale 200만 — 화면 줌 8 은 1:218만이라 빈다(wetherilli 308)
    "sgm:edades:0": (0, None, True),
    "sgm:paleo:0": (0, None, True),
    "sgm:yac:0": (0, 8, True),      # 광산 9 465 점 — 넓게 보면 기호가 땅을 덮는다
    "sgm:yac:3": (3, None, True),   # 광화 지역
    "sgm:yac:2": (2, None, True),   # 광산 지구
    "sgm:yac:1": (1, None, True),   # 변질대 (wetherilli 233)
    "sgm:yac:4": (4, None, True),   # 비금속 광화 지역
    "sgm:yac50:0": (0, 10, True),   # 광산 1:5만 4 만 6 천 점
    "sgm:geoq:0": (0, 9, True),     # 하천 퇴적물 지화학 21 만 5 천 점 — 넓게 보면 땅이 점으로 덮인다
    **{f"sgm:anom250:{n}": (n, 9, True) for n in range(6)},     # 상류 minScale 200만 — 화면 줌 9 부터(wetherilli 308)
    **{f"sgm:anom50:{n}": (n, 10, True) for n in range(6)},     # 상류 minScale 75만
    # 지자기 1:25만 — 칠하기 칸뿐이라(nT 가 없다) 누르지 않는다. 줌 6 밑은 칸 하나가 25–54 초라 8 부터 (wetherilli 244·282)
    "sgm:datos:7": (7, 8, False),
}
#: 메타타일로 받는 레이어(wetherilli 282) — 요청 하나가 줌과 상관없이 10 초 넘게 드는 것. 화면의 주소는 그대로다.
#: 이름 → 메타타일로 받는 가장 깊은 격자 줌(None 은 모든 줌) — `metatile.limit` 의 표 (wetherilli 284)
METATILE = {"sgm:datos:7": None}
#: 칠하기 구간(classBreaks)을 범례로 내는 레이어 — 보는 범위와 무관하다
BREAKS = tuple(n for n in LAYERS if n.startswith(("sgm:anom250:", "sgm:anom50:", "sgm:datos:")))
#: 범례에 실을 열 — 기호, 암상, 지층, 시대
LABEL = ("CLAVE_SGM", "LITOLOGIA", "FORMACION", "PERIODO")
#: 보는 범위의 범례 — 레이어 → (칠하기 열, 묶을 열, 범례를 뜨는 가장 넓은 범위(°))
LEGENDS = {"sgm:8": ("CLAVE_SGM", LABEL, 8), "sgm:7": ("CLAVE_SGM", LABEL, 3),
           "sgm:edades:0": ("DES_CLAV", ("DES_CLAV",), 40)}
MAX_LEGEND = 60
COLORS_MAX_AGE = 30 * 86400


class SgmError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def zooms(name: str) -> tuple:
    return (LAYERS[name][1], None) if name in LAYERS else (None, None)


def legend_layers() -> list:
    return list(LEGENDS) + list(BREAKS)


def queryable(name: str) -> bool:
    return name in LAYERS and LAYERS[name][2]


def _one(params_or_name):
    name = params_or_name if isinstance(params_or_name, str) else \
        (params_or_name.get("layers") or params_or_name.get("query_layers") or "")
    names = [n.strip() for n in str(name).split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SgmError(f"모르는 레이어다: {names}")
    return names[0], LAYERS[names[0]][0]


def _base(name: str = "") -> str:
    parts = str(name).split(":")
    if len(parts) == 3 and parts[1] in SERVICES:
        root = settings.SGM_URL.split("/rest/services/", 1)[0]
        return f"{root}/rest/services/{SERVICES[parts[1]]}/MapServer"
    return settings.SGM_URL.rstrip("/")


def _get(path: str, params: dict, name: str = ""):
    left = usage.paused()
    if left:
        raise SgmError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        # 메타타일(1024 px)은 한 장이 20 초 남짓이다 — 넉넉히 기다리되 문 한계까지만 (wetherilli 282·300)
        wait = settings.UPSTREAM_TIMEOUT_MAX if metatile.limit(METATILE, name) is not False else 45
        r = requests.get(f"{_base(name)}/{path}", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, wait),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgm", ok=False)
        raise SgmError(f"SGM 에 닿지 못했다: {exc}") from exc
    log.info("SGM %s -> %s", r.url, r.status_code)
    usage.record("sgm", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _view(params: dict):
    """WMS 변수 → (3857 범위 네 수, 너비, 높이). 화면은 늘 3857 로 묻는다."""
    crs = str(params.get("crs") or params.get("srs") or "").upper()
    if crs not in ("EPSG:3857", "EPSG:900913"):
        raise SgmError(f"3857 로만 묻는다: {crs}")
    try:
        bbox = tuple(float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
    except (KeyError, ValueError) as exc:
        raise SgmError("범위·크기를 읽지 못했다") from exc
    if len(bbox) != 4 or not (0 < width <= 4096 and 0 < height <= 4096):
        raise SgmError("범위·크기가 맞지 않다")
    return bbox, width, height


def get_map(params: dict):
    """WMS GetMap → REST export. 받은 그림은 투명 PNG 다."""
    name, layer = _one(params)
    bbox, width, height = _view(params)
    r = _get("export", {"bbox": ",".join(repr(v) for v in bbox), "bboxSR": "3857", "imageSR": "3857",
                        "size": f"{width},{height}", "format": "png32", "transparent": "true", "dpi": "96",
                        "layers": f"show:{layer}", "f": "image"}, name)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SgmError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise SgmError("멕시코 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    """WMS GetFeatureInfo → REST identify. 누른 자리(I·J)를 3857 의 한 점으로 셈해 그 레이어만 묻는다."""
    name, layer = _one(params)
    if not queryable(name):
        return {"features": []}
    bbox, width, height = _view(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise SgmError("누른 자리를 읽지 못했다") from exc
    x = bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width
    y = bbox[3] - (bbox[3] - bbox[1]) * (j + 0.5) / height
    r = _get("identify", {"geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": "3857",
                          "layers": f"all:{layer}", "tolerance": "2", "mapExtent": ",".join(repr(v) for v in bbox),
                          "imageDisplay": f"{width},{height},96", "returnGeometry": "false", "f": "json"}, name)
    if r.status_code != 200:
        raise SgmError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise SgmError("속성이 JSON 이 아니다") from exc
    if data.get("error"):
        raise SgmError(f"identify 오류: {data['error'].get('message', '')}")
    return {"features": [{"id": f"{res.get('layerId')}.{(res.get('attributes') or {}).get('ObjectId', n)}",
                          "properties": res.get("attributes") or {}}
                         for n, res in enumerate(data.get("results") or [])]}


def _clean(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("null", "<null>", "none", "indeterminado", "no aplicable") else text


def _span(old: str, young: str, lang: str) -> str:
    a, b = (i18n.age_es(old) if old else ""), (i18n.age_es(young) if young else "")
    age = a if a == b or not b else (b if not a else f"{a} - {b}")
    return i18n.age_ko(age) if lang == "ko" and age else age


def edad(value: str, lang: str = "ko") -> str:
    """지질 연대 점의 시대(`Cretácico Superior-Maastrichtiano`) → 가장 자세한 마디 하나(마스트리히트절). `Triásico Superior` 는 통째로"""
    text = _clean(value)
    if not text:
        return ""
    return _span(text.split("-")[-1].strip(), "", lang)


def _link(url: str):
    url = _clean(url)
    return {"text": "", "links": [{"url": url, "label": "열기"}]} if url.startswith(("http://", "https://")) else None


def other_friendly(props: dict, lang: str = "ko"):
    """지질도 밖의 서비스(wetherilli 219) — identify 별칭 열로 가른다. 지질도면 None"""
    v = lambda k: _clean(props.get(k))          # noqa: E731
    import re
    element = [m for m in (re.fullmatch(r"([A-Za-z]{1,2})_ppm", k) for k in props) if m]
    if "NMuestra" in props and "Carta" in props:  # 하천 퇴적물 지화학 시료 — 원소마다 한 줄
        rows = [("시료", v("NMuestra")), ("도폭", v("Carta"))]
        for key in props:
            m = re.fullmatch(r"([A-Z][a-z]?) (%|ppm|ppb)", key)
            if m and v(key) and v(key).lower() != "null":
                rows.append((f"{m.group(1)} ({m.group(2)})", v(key)))
        return {k: x for k, x in rows if x}
    if element and len(props) <= 4:             # 원소 이상 지점
        key = element[0].group(0)
        return {k: x for k, x in (("원소", element[0].group(1).capitalize()), ("함량 (ppm)", v(key))) if x}
    if "Método" in props:                       # 지질 연대 측정 점
        ma = " ± ".join(x for x in (v("Edad (millones de años)"), v("Error")) if x)
        rows = (("지질시대", edad(v("Edad"), lang)), ("연대 (Ma)", ma), ("측정법", " · ".join(x for x in (v("Método"), v("Mineral")) if x)),
                ("연대 갈래", v("Tipo de edad")), ("암석", v("Roca") or v("Tipo de roca")), ("단위", v("Unidad")),
                ("시료", v("Muestra")), ("산지", v("Localidad")), ("참고 문헌", v("Referencia")), ("보고서", _link(v("Informe"))))
    elif "No de fósiles" in props:              # 고생물 산지
        rows = (("산지", v("Localidad")), ("지층", v("Formación")), ("화석 수", v("No de fósiles")),
                ("주", " · ".join(x for x in (v("Municipio"), v("Estado")) if x)), ("사진", _link(v("Ver fotos"))))
    elif "Sustancia" in props:                  # 광산
        rows = (("이름", v("Nombre")), ("광종", v("Sustancia")), ("운영", v("Tipo de operación")),
                ("광화 유형", v("Tipo de mineralización")), ("구조", v("Estructura")), ("변질", v("Alteración")))
    elif "Alteración" in props:                 # 변질대
        rows = (("변질", v("Alteración")),)
    elif "Mineralización" in props:             # 광화 지역·비금속 광화 지역
        rows = (("지역", v("Región")), ("광종", v("Mineralización")), ("광상 형태", v("Yacimiento")), ("광산 지구", v("Distrito minero")))
    elif "DIST_MINER" in props:                 # 광산 지구
        rows = (("광산 지구", v("DIST_MINER")), ("지역", v("REGION")))
    else:
        return None
    return {k: x for k, x in rows if x and str(x).upper() != "SE DESCONOCE"}


def friendly(props: dict, lang: str = "ko") -> dict:
    """identify 의 별칭 열 → 한국어. 암상·지층은 에스파냐어 그대로, 시대만 옮긴다."""
    other = other_friendly(props, lang)
    if other is not None:
        return other
    v = lambda k: _clean(props.get(k))          # noqa: E731
    period = _span(v("Periodo"), "", lang)
    stage = _span(v("Edad inicial"), v("Edad final"), lang)
    rows = (("기호", v("Clave")), ("암석", v("Litología")), ("갈래", v("Roca")), ("지층", v("Formación")),
            ("지질시대", " · ".join(x for x in (period, stage) if x)), ("위계", v("Tipo de unidad")))
    return {k: x for k, x in rows if x}


# ── 보는 범위의 범례 — 페루(`ingemmet.py`)와 같은 꼴 ───────────────

def colors(name: str) -> dict:
    _, layer = _one(name)
    # 지질도의 열쇠는 앞 판 그대로(번호만) — 다른 서비스는 이름째
    key = tilecache.key_text("sgm-colors", str(layer) if name.count(":") == 1 else name)
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _get(str(layer), {"f": "json"}, name)
    try:
        table = arcpoints.renderer_colors(r.json()["drawingInfo"]["renderer"])
    except (ValueError, KeyError, TypeError) as exc:
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise SgmError("칠하기 규칙을 읽지 못했다") from exc
    tilecache.put(key, json.dumps(table).encode("utf-8"), ".json")
    return table


def extent_legend(name: str, bbox: tuple) -> list:
    """범위 `(서, 남, 동, 북)`(위경도)에 든 단위 — `[{"value", "fields", "count"}, …]`, 면이 많은 것부터."""
    _, layer = _one(name)
    field, label, _ = LEGENDS[name]
    r = _get(f"{layer}/query", {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "groupByFieldsForStatistics": ",".join(label),
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "returnGeometry": "false", "f": "json"}, name)
    try:
        data = r.json()
    except ValueError as exc:
        raise SgmError("질의가 JSON 이 아니다") from exc
    if r.status_code != 200 or data.get("error"):
        raise SgmError(f"질의 오류 (status={r.status_code})")
    rows = {}
    for f in data.get("features") or []:
        a = f.get("attributes") or {}
        value = _clean(a.get(field))
        if not value:
            continue
        count = int(a.get("n") or a.get("N") or 0)
        if value in rows:
            rows[value]["count"] += count
        else:
            rows[value] = {"value": value, "fields": {k: _clean(a.get(k)) for k in label}, "count": count}
    return sorted(rows.values(), key=lambda r: -r["count"])


def legend_row(row: dict, table: dict, lang: str = "ko") -> dict:
    f = row["fields"]
    if "DES_CLAV" in f:                         # 지질 연대 점 — 시대 하나가 한 칸
        return {"color": table.get(row["value"], "#cccccc"), "symbol": "", "swatch": "",
                "lithology": edad(row["value"], lang) or row["value"], "age": ""}
    name = " · ".join(x for x in (f.get("LITOLOGIA"), f.get("FORMACION")) if x)
    return {"color": table.get(row["value"], "#cccccc"), "symbol": row["value"], "swatch": "",
            "lithology": f"{row['value']} {name}".strip(), "age": _span(f.get("PERIODO", ""), "", lang)}


def breaks(name: str) -> list:
    """이상 지점의 칠하기 구간 → 범례 줄 `[{"swatch": data URI, "lithology": "15 – 110.9 ppm", …}]` (wetherilli 233).

    1:25만은 한 색에 원의 **크기**로, 1:5만은 그림 기호로 구간을 가른다 — 색 한 칸으로는 안 보여 서비스의 REST 범례(`legend?f=json`)가 주는
    칸마다의 그림을 견본으로 쓴다. 그림 크기가 칸마다 달라(20–26 px) 가장 큰 칸에 맞춰 가운데 놓는다 — 화면이 견본 칸을 채워 늘려도
    크기 차이가 남게. 범례는 30 일 담아 둔다"""
    _, layer = _one(name)
    key = tilecache.key_text("sgm-breaks", name)
    held = tilecache.get(key, ".json", max_age=COLORS_MAX_AGE)
    if held is not None:
        return json.loads(held)
    r = _get("legend", {"f": "json"}, name)
    try:
        entries = next(l["legend"] for l in r.json()["layers"] if l.get("layerId") == layer)
    except (ValueError, KeyError, TypeError, StopIteration) as exc:
        stale = tilecache.get(key, ".json", stale=True)
        if stale is not None:
            return json.loads(stale)
        raise SgmError("범례를 읽지 못했다") from exc
    rows = []
    for entry, swatch in zip(entries, _padded([e.get("imageData") or "" for e in entries])):
        parts = [p.strip() for p in str(entry.get("label") or "").split(" - ")]
        try:
            text = " – ".join(f"{float(p):g}" for p in parts) + " ppm"
        except ValueError:
            text = str(entry.get("label") or "")
        rows.append({"color": "transparent", "symbol": "", "swatch": swatch, "lithology": text, "age": ""})
    tilecache.put(key, json.dumps(rows).encode("utf-8"), ".json")
    return rows


def _padded(images: list) -> list:
    """base64 PNG 여럿 → 가장 큰 것의 크기로 가운데 맞춘 data URI 여럿. 읽지 못한 것은 빈 글"""
    import base64
    import io

    from PIL import Image
    opened = []
    for data in images:
        try:
            opened.append(Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA"))
        except Exception:          # noqa: BLE001
            opened.append(None)
    size = max([max(i.size) for i in opened if i] or [1])
    out = []
    for img in opened:
        if img is None:
            out.append("")
            continue
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
        buf = io.BytesIO()
        canvas.save(buf, "PNG")
        out.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
    return out


def legend_span(name: str) -> float:
    return LEGENDS[name][2]


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "sgm", "tag": "SGM", "title": "멕시코 지질조사소", "relay": True, "projected": True, "globe": True},
]
