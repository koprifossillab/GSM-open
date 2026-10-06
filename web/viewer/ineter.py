"""니카라과 국토연구원(INETER)으로 나가는 문 — 니카라과 지질도와 단층 (wetherilli 242).

- 주소: `mapserveride.ineter.gob.ni/geoserver/ows` (GeoServer WMS). 열쇠가 없다. 레이어 `wsINETER-DGGG:Geologia_Nicaragua`(온 나라 지질 면)·
  `wsINETER-DGGG:Fallas_Nacionales`(단층). 축척 한계가 없다
- 3857 로 곧장 — 나라 전체 512×450 2.5 초, 마나과 둘레(줌 12 남짓) 1.4 초(2026-10-05)
- 속성은 `application/json` — 모양까지 오지 않게 `propertyName` 으로 열을 고른다(418 B). `nomencla`·`sistema`(계)·`serie`(통)·`formacion`·
  `litologia`, 스페인어다. 시대는 `i18n.age_es` 로 옮긴다 — `Mioceno Medio-Superior` 처럼 꾸밈말 둘을 붙여 쓴 것은 갈라 옮긴다
- **단층은 누르지 않는다** — 값에 Latin-1 이 JSON 에 섞여 글자가 깨진다(`tipo`·`clase`)
- 범례는 GeoServer 그림(863×620)
- 조건: Capabilities 의 AccessConstraints `NONE`. 그 밖의 조건 문서는 찾지 못했다(사람이 읽는다). CORS 는 `*`
"""
import logging

import requests
from django.conf import settings

from . import arcwms, i18n, usage

log = logging.getLogger(__name__)

PREFIX = "ineter:"
ATTRIBUTION = ('<a href="https://www.ineter.gob.ni/" target="_blank" rel="noopener">INETER</a> — Mapa Geológico de Nicaragua')
FIELDS = "nomencla,sistema,serie,formacion,litologia"


class IneterError(RuntimeError):
    pass


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise IneterError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ineter", ok=False)
        raise IneterError(f"INETER 에 닿지 못했다: {exc}") from exc
    log.info("INETER %s -> %s", r.url, r.status_code)
    usage.record("ineter", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


DOOR = arcwms.Door(url=lambda: settings.INETER_WMS_URL,
                   layers={"ineter:geology": "wsINETER-DGGG:Geologia_Nicaragua", "ineter:faults": "wsINETER-DGGG:Fallas_Nacionales"},
                   queryable=("ineter:geology",), get=_get, error=IneterError, info_format="application/json",
                   info_params={"ineter:geology": {"propertyName": FIELDS, "feature_count": "1"}})
knows, get_map, get_legend, get_feature_info = DOOR.knows, DOOR.get_map, DOOR.get_legend, DOOR.get_feature_info


def age(serie: str, sistema: str = "") -> str:
    """스페인어 통·계 → ICS 영어. `Mioceno Medio-Superior` 는 `Middle Miocene – Late Miocene` 로 갈라 옮긴다. 못 옮기면 빈 글"""
    text = str(serie or "").strip() or str(sistema or "").strip()
    if not text:
        return ""
    whole = i18n.age_es(text)
    if whole != text:
        return whole
    if "-" in text:                                       # `Plioceno-Pleistoceno` — 시대 둘을 이었다
        sides = [x.strip() for x in text.split("-")]
        moved = [i18n.age_es(x) for x in sides]
        if all(m != x for m, x in zip(moved, sides)):
            return " – ".join(moved)
    noun, _, mods = text.partition(" ")
    if "-" in mods:
        parts = [i18n.age_es(f"{noun} {m.strip()}") for m in mods.split("-")]
        if all(p != f"{noun} {m.strip()}" for p, m in zip(parts, mods.split("-"))):
            return " – ".join(parts)
    return ""


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값(스페인어)은 그대로, 시대만 옮긴다(못 옮기면 원문)"""
    v = lambda k: "" if str(props.get(k) or "").strip().lower() in ("", "null", "ningun nombre") else str(props.get(k)).strip()  # noqa: E731
    ics = age(v("serie"), v("sistema"))
    shown = (i18n.age_ko(ics) if lang == "ko" else ics) if ics else (v("serie") or v("sistema"))
    rows = (("기호", v("nomencla")), ("이름", v("formacion")), ("암석", v("litologia")), ("지질시대", shown))
    return {k: x for k, x in rows if x}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "ineter", "tag": "INETER", "title": "니카라과 국토연구원 (INETER)", "relay": True, "projected": True, "globe": True},
]
