"""인도네시아 에너지광물자원부(ESDM) 지질청(Badan Geologi)으로 나가는 문 — 인도네시아 지질도 1:10만 편집 2018 (wetherilli 228).

- 주소: `geoportal.esdm.go.id/gis4/services/BGS_PM/Geologi_Litologi/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다. 섬 전체(95–141°E)
- Capabilities 는 4326·CRS:84 만 적지만 **3857 GetMap 이 그린다**(2026-10-04, 반둥 둘레 256² 2.0 초). Capabilities 는 17 초 걸렸다
- **1:57만 7 790 보다 크게 확대하면 그리지 않는다**(서비스의 maxScale) — 화면 줌 10 까지만 받고 그 위는 화면이 늘려 그린다(`LAST_ZOOM` →
  카탈로그의 `maxZoom`, `map.js` 의 `npolarSource` 가 격자를 거기서 멈춘다)
- 속성은 **ESRI XML 만** 준다(geojson 을 물어도 XML) — `<FIELDS NotasiFormasi="Qyt" NamaFormasi="Pumiceous Tuff" UmurFormasi="Kuarter" …/>`.
  지층명은 영어, 시대·설명은 인도네시아어다. 시대는 값 28 가지(2026-10-04 에 모았다)를 ICS 로 옮긴다(`AGES`)
- 범례는 두지 않는다 — 1 403 칸이다. 누르면 단위가 뜬다
- 조건: copyright "Pusat Survei Geologi" 뿐, 이용 조건 문서를 찾지 못했다 — **밖에 열기 전에 사람이 읽는다**. CORS 는 Origin 을 되비춘다
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "esdm:"
ATTRIBUTION = ('<a href="https://geoportal.esdm.go.id/" target="_blank" rel="noopener">Badan Geologi (ESDM)</a> — '
               "Peta Geologi Indonesia 1:100.000")
LAYERS = {"esdm:geology": "0"}
#: 이 줌까지만 받는다 — 상류가 1:57만 7 790 보다 크게는 그리지 않는다
LAST_ZOOM = 10
#: 인도네시아어 시대 → ICS(영어). 상류의 값 28 가지 그대로다. 옮기지 못하는 것(`Pra Tersier` 따위)은 원문을 보인다
AGES = {
    "Kuarter": "Quaternary", "Holosen": "Holocene", "Tersier": "Tertiary", "Neogen": "Neogene", "Paleogen": "Paleogene",
    "Miosen": "Miocene", "Miocene": "Miocene", "Oligocene": "Oligocene", "Kapur": "Cretaceous", "Jura": "Jurassic",
    "Trias": "Triassic", "Triassic": "Triassic", "Perm": "Permian", "Permian": "Permian", "Permo Karbon": "Carboniferous – Permian",
    "Karbon": "Carboniferous", "Carbonifer": "Carboniferous", "Devonian": "Devonian", "Silurian": "Silurian",
    "Ordovician": "Ordovician", "Mesozoikum": "Mesozoic", "Paleozoikum": "Paleozoic", "Paleo - Meso": "Paleozoic – Mesozoic",
    "Meso - Paleo": "Paleozoic – Mesozoic", "Proteroz": "Proterozoic", "Prakambrium": "Precambrian",
}


class EsdmError(RuntimeError):
    pass


def _url() -> str:
    return f"{settings.ESDM_URL.rstrip('/')}/services/BGS_PM/Geologi_Litologi/MapServer/WMSServer"


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise EsdmError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 45),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("esdm", ok=False)
        raise EsdmError(f"ESDM 에 닿지 못했다: {exc}") from exc
    log.info("ESDM %s -> %s", r.url, r.status_code)
    usage.record("esdm", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


DOOR = arcwms.Door(url=_url, layers=LAYERS, queryable=("esdm:geology",), info_format="text/xml", get=_get, error=EsdmError)
knows, get_map, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_feature_info


def get_legend(layer: str):
    raise EsdmError("범례를 두지 않는다 — 1 403 칸이다")


def age(value: str, lang: str = "ko") -> str:
    text = str(value or "").strip()
    ics = AGES.get(text)
    if not ics:
        return text
    return i18n.age_ko(ics) if lang == "ko" else ics


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 지층명(영어)·설명(인도네시아어)은 그대로, 시대만 옮긴다"""
    rows = (("기호", props.get("NotasiFormasi", "")), ("이름", props.get("NamaFormasi", "")),
            ("설명", props.get("Keterangan", "")), ("지질시대", age(props.get("UmurFormasi", ""), lang)))
    return {k: str(v).strip() for k, v in rows if str(v or "").strip()}
