"""스미스소니언 열대연구소(STRI) GIS 실의 파나마 지질도로 나가는 문 — 파나마 1:25만(MICI 1990) (wetherilli 253).

- 주소: `services2.arcgis.com/HRY6x8qt5qjGnAA9/arcgis/rest/services/Geologia_Panama/FeatureServer` (ArcGIS Online 피처 서비스). 열쇠가 없다.
  원본은 상공산업부(MICI) 1990 년 1:25만 파나마 지질도를 STRI 가 디지털로 옮긴 것이다
- **피처 서비스라 그림이 없다** — 카리브(`usgscarib.py`, wetherilli 248)와 같은 꼴로 한 덩이를 받아 화면이 구워 그린다. 상류에는 처음 한 번만
  묻고 캐시에 30 일 둔다(`HELD_SECONDS`)
  - 지질 면(레이어 13 "Símbolo", 1 608 개) — 1 000 개씩 둘, 0.001°(100 m)·소수 다섯째 자리로 1.2 MB 남짓
  - 단층(레이어 3 정단층·4 추정 단층·5 충상단층) — 선 한 덩이로 모아, 갈래마다 색·끊음을 범례에 적는다
- 속성(스페인어) — `SIMBOLO`(기호)·`GRUPO`·`FORMACION`·`FORMAS`(암석 갈래)·`LEYENDA`(설명). **시대 열이 없다** — 기호의 앞머리가 시대다
  (`K` 백악기·`TPA` 팔레오세·`TE`·`TEO`·`TO`·`TOM`·`TM`·`TMPL`·`TPL`·`PI/PS`·`QPS`·`QR` — `AGES`)
- 색은 서비스의 칠하기 규칙(SIMBOLO 78 칸)
- 조건: **CC BY-SA 4.0** ("STRI GIS Office 2018"), 원도 MICI 1990. CORS `*`
"""
import json
import logging

import requests
from django.conf import settings

from . import i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "stri:"
GEOLOGY, FAULTS = "stri:geology", "stri:faults"
ATTRIBUTION = ('<a href="https://stridata-si.opendata.arcgis.com/" target="_blank" rel="noopener">STRI GIS Office</a> — '
               "Mapa Geológico de Panamá 1:250 000 (MICI 1990), CC BY-SA 4.0")
SOURCE_URL = "https://stridata-si.opendata.arcgis.com/"
HELD_SECONDS = 30 * 86400
PAGE = 1000
LABELS = {"code": "기호", "name": "이름", "rock": "암석 갈래", "desc": "설명", "age": "지질시대"}
#: 기호의 앞머리(첫 `-` 앞) → ICS 영어
AGES = {
    "K": "Cretaceous", "TPA": "Paleocene", "TE": "Eocene", "TEO": "Eocene – Oligocene", "TO": "Oligocene",
    "TOM": "Oligocene – Miocene", "TM": "Miocene", "TMPL": "Miocene – Pliocene", "TPL": "Pliocene",
    "PI/PS": "Pliocene – Pleistocene", "QPS": "Pleistocene", "QR": "Holocene",
}
#: 단층 레이어 → (칸 이름, 색, 굵기, 끊음). 추정 단층이 1 839 개로 거의 전부라 가늘고 어둡게 — 굵으면 지질도를 덮는다
FAULT_LAYERS = {3: ("Fallas Normales", "#d7191c", 1.4, None),
                4: ("Fallas Interpretadas", "#8c2d24", 0.8, [4, 3]),
                5: ("Fallas Corrimiento", "#1a1a1a", 1.6, None)}


class StriError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in (GEOLOGY, FAULTS)


def _get(path: str, params: dict):
    left = usage.paused()
    if left:
        raise StriError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.STRI_URL.rstrip('/')}/{path}"
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("stri", ok=False)
        raise StriError(f"STRI 파나마 지질도에 닿지 못했다: {exc}") from exc
    log.info("STRI %s -> %s", r.url, r.status_code)
    usage.record("stri", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise StriError(f"받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise StriError("JSON 이 아니다") from exc
    if isinstance(data, dict) and data.get("error"):
        raise StriError(f"상류 오류: {data['error'].get('message', '')}")
    return data


def _held(name: str, fetch):
    key = tilecache.key_text("stri", name)
    held = tilecache.get(key, ".json", max_age=HELD_SECONDS)
    if held is not None:
        return json.loads(held)
    data = fetch()
    tilecache.put(key, json.dumps(data, separators=(",", ":")).encode("utf-8"), ".json")
    return data


def _all(layer: int, fields: str, simplify: str) -> list:
    out, offset = [], 0
    while True:
        page = _get(f"{layer}/query", {"where": "1=1", "outFields": fields, "outSR": "4326", "f": "geojson",
                                       "resultOffset": str(offset), "resultRecordCount": str(PAGE),
                                       "maxAllowableOffset": simplify, "geometryPrecision": "5", "orderByFields": "OBJECTID"})
        got = page.get("features") or []
        out.extend(got)
        if len(got) < PAGE and not (page.get("properties") or {}).get("exceededTransferLimit"):
            break
        offset += len(got)
        if not got or offset > 20000:
            break
    return out


def units() -> list:
    return _held("units", lambda: _all(13, "SIMBOLO,GRUPO,FORMACION,FORMAS,LEYENDA", "0.001"))


def faults() -> list:
    def fetch():
        out = []
        for layer in FAULT_LAYERS:
            for f in _all(layer, "OBJECTID", "0.0005"):
                out.append({"type": "Feature", "geometry": f.get("geometry"), "properties": {"code": str(layer)}})
        return out
    return _held("faults", fetch)


def colors() -> dict:
    """SIMBOLO → 색. 서비스의 칠하기 규칙에서 — 한 번 받아 둔다"""
    def fetch():
        info = (_get("13", {"f": "json"}).get("drawingInfo") or {}).get("renderer") or {}
        return {str(u.get("value") or "").strip(): "#%02x%02x%02x" % tuple((u.get("symbol") or {}).get("color", [136, 136, 136])[:3])
                for u in info.get("uniqueValueInfos") or [] if (u.get("symbol") or {}).get("color")}
    return _held("colors", fetch)


def age_of(symbol: str) -> str:
    """기호(`TM-CATu`·`K-AR`·`PI/PS-Cv`) → ICS 영어. 모르면 빈 글"""
    return AGES.get(str(symbol or "").split("-")[0].strip(), "")


def _value(v) -> str:
    text = str(v or "").strip()
    return "" if text.lower() in ("null", "none") else text


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `usgscarib.body`·`geo3al.body` 와 같다"""
    if name == GEOLOGY:
        table, items, counts = colors(), [], {}
        for f in units():
            p = f.get("properties") or {}
            code = _value(p.get("SIMBOLO")) or "No data"
            age = age_of(code)
            props = {"code": code, "color": table.get(code, "#cccccc"),
                     "name": " · ".join(x for x in (_value(p.get("FORMACION")), _value(p.get("GRUPO"))) if x),
                     "rock": _value(p.get("FORMAS")), "desc": _value(p.get("LEYENDA")),
                     "age": (i18n.age_ko(age) if lang == "ko" else age) if age else ""}
            items.append({"type": "Feature", "geometry": f.get("geometry"), "properties": {k: v for k, v in props.items() if v}})
            counts[code] = counts.get(code, 0) + 1
        legend = [{"code": c, "label": f"{c} — {i18n.age_ko(age_of(c)) if lang == 'ko' and age_of(c) else age_of(c)}".rstrip(" —"),
                   "color": table.get(c, "#cccccc"), "count": n}
                  for c, n in sorted(counts.items(), key=lambda kv: -kv[1])]
        style = "unit"
    elif name == FAULTS:
        items, counts = faults(), {}
        for f in items:
            counts[f["properties"]["code"]] = counts.get(f["properties"]["code"], 0) + 1
        legend = [{"code": str(k), "label": label, "color": color, "width": width, **({"dash": dash} if dash else {}),
                   "count": counts.get(str(k), 0)}
                  for k, (label, color, width, dash) in FAULT_LAYERS.items() if counts.get(str(k))]
        style = "line"
    else:
        raise StriError(f"모르는 레이어다: {name}")
    out = {"type": "FeatureCollection", "labels": LABELS, "style": style, "legend": legend, "features": items}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
