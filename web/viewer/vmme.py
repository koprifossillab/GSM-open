"""파라과이 광업·에너지 차관실(VMME, MOPC)로 나가는 문 — 파라과이 지질도 (wetherilli 256).

- 주소: `services5.arcgis.com/LSvRaxOMGSmUKhcq/arcgis/rest/services/Mapa_WFL1/FeatureServer/5` ("Geología"). 차관실이 광업권 대시보드
  (`vmme.maps.arcgis.com`)에 얹어 둔 피처 서비스다. 열쇠가 없고 CORS `*`
- **피처 서비스라 그림이 없다** — 카리브(`usgscarib.py`)·파나마(`stri.py`)와 같은 꼴로 한 덩이(면 61, 0.16 MB)를 받아 화면이 그린다.
  상류에는 처음 한 번만 묻고 캐시에 30 일 둔다
- 속성은 `Cod_`(기호)·`Descrip_`(층군·층 이름, 스페인어)뿐이다. 단위가 열셋인 개략도다 — 차관실이 PDF·SIG 파일로 내는 1:100만(2023·2024
  개정)보다 거칠다. **칠하기 규칙이 단색이라 색은 우리가 붙인다**(`UNITS`, ICS 색에 가깝게). 시대는 기호의 시대 글자가 뜻이 분명한 것만 적는다
  — `M`(중생대)·`Q`·`T`·`P`·`C` 따위. `E`(Itapucumí 층군)는 비워 둔다
- 조건: 적힌 것이 없다(사람이 읽는다, TODOs)
"""
import json
import logging

import requests
from django.conf import settings

from . import i18n, tilecache, usage

log = logging.getLogger(__name__)

PREFIX = "vmme:"
NAME = "vmme:geology"
ATTRIBUTION = ('<a href="https://www.ssme.gov.py/vmme/" target="_blank" rel="noopener">VMME (MOPC)</a> — Mapa Geológico del Paraguay')
SOURCE_URL = "https://vmme.maps.arcgis.com/apps/dashboards/48a65a969c734098a065bbec48463a13"
HELD_SECONDS = 30 * 86400
LABELS = {"code": "기호", "name": "이름", "age": "지질시대"}
#: 기호 → (색, ICS 영어 시대 — 모르면 빈 글)
UNITS = {
    "Q1": ("#fff7b2", "Quaternary"), "Q2": ("#fdeb8a", "Quaternary"), "T": ("#fdc07a", "Cenozoic"),
    "Mb": ("#7fc64e", "Mesozoic"), "Mi": ("#b6d96a", "Mesozoic"), "Ms": ("#4fb8c8", "Mesozoic"),
    "P/T": ("#e8705a", "Permian – Triassic"), "P": ("#f04028", "Permian"), "C": ("#67a599", "Carboniferous"),
    "O/S/D": ("#b3d8b0", "Ordovician – Devonian"), "E": ("#fdb46c", ""),
    "pE": ("#f04370", "Precambrian"), "Pm": ("#c2185b", "Precambrian"),
}


class VmmeError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name == NAME


def _get(params: dict):
    left = usage.paused()
    if left:
        raise VmmeError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(f"{settings.VMME_URL.rstrip('/')}/query", params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("vmme", ok=False)
        raise VmmeError(f"파라과이 지질도에 닿지 못했다: {exc}") from exc
    log.info("VMME %s -> %s", r.url, r.status_code)
    usage.record("vmme", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    if r.status_code != 200:
        raise VmmeError(f"받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise VmmeError("JSON 이 아니다") from exc
    if isinstance(data, dict) and data.get("error"):
        raise VmmeError(f"상류 오류: {data['error'].get('message', '')}")
    return data


def units() -> list:
    """면 전부 — 61 개라 한 번에 받는다"""
    key = tilecache.key_text("vmme", "units")
    held = tilecache.get(key, ".json", max_age=HELD_SECONDS)
    if held is not None:
        return json.loads(held)
    data = (_get({"where": "1=1", "outFields": "Cod_,Descrip_", "outSR": "4326", "f": "geojson",
                  "maxAllowableOffset": "0.002", "geometryPrecision": "5"}).get("features") or [])
    tilecache.put(key, json.dumps(data, separators=(",", ":")).encode("utf-8"), ".json")
    return data


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `usgscarib.body` 와 같다"""
    if not knows(name):
        raise VmmeError(f"모르는 레이어다: {name}")
    items, counts, names = [], {}, {}
    for f in units():
        p = f.get("properties") or {}
        code = str(p.get("Cod_") or "").strip() or "?"
        color, age = UNITS.get(code, ("#cccccc", ""))
        shown = (i18n.age_ko(age) if lang == "ko" else age) if age else ""
        desc = str(p.get("Descrip_") or "").strip()
        items.append({"type": "Feature", "geometry": f.get("geometry"),
                      "properties": {k: v for k, v in {"code": code, "color": color, "name": desc, "age": shown}.items() if v}})
        counts[code] = counts.get(code, 0) + 1
        names.setdefault(code, desc)
    order = list(UNITS)
    legend = [{"code": c, "label": f"{c} {names[c]}".strip(), "color": UNITS.get(c, ("#cccccc", ""))[0], "count": counts[c]}
              for c in sorted(counts, key=lambda c: order.index(c) if c in order else len(order))]
    out = {"type": "FeatureCollection", "labels": LABELS, "style": "unit", "legend": legend, "features": items}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "vmme", "tag": "VMME", "title": "파라과이 광업·에너지 차관실 (VMME)"},
]
