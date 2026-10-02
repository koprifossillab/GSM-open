"""스미스소니언 Global Volcanism Program 으로 나가는 문 — 온 지구의 홀로세 화산 (wetherilli 134).

화산 목록(Volcanoes of the World)은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 GVP 의 GeoServer WFS(`webservices.volcano.si.edu/geoserver/GVP-VOTW/ows`). **열쇠가 없다.** 이용 조건은
  스미스소니언의 것 — 개인·교육·비상업 이용은 되고 출처를 밝혀 링크를 건다. 인용 꼴은 `CREDIT` 이다
- **화면이 부를 때 상류를 타지 않는다.** 홀로세 화산은 1 200 여 개(2.4 MB)라 `manage.py fetch_gvp` 가 한 번에 받아
  `<EARTH_DIR>/gvp_volcanoes.json` 에 줄여 적는다 — PBDB 와 같은 틀이다(098). 판이 오르면(1 년에 한두 번) 다시 받는다
- 사진(`Primary_Photo_*`)은 찍은 사람마다 저작권이 따로라 담지 않는다. 화산 쪽으로 가는 링크만 건다
"""
import json
import logging
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

WFS = "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows"
LAYER = "GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes"
CREDIT = "Global Volcanism Program, Smithsonian Institution · Volcanoes of the World · volcano.si.edu"
#: 담는 속성 — WFS 의 이름 그대로. 줄인 파일의 열쇠는 오른쪽
FIELDS = {
    "Volcano_Number": "no", "Volcano_Name": "name", "Primary_Volcano_Type": "type", "Volcanic_Landform": "landform",
    "Last_Eruption_Year": "last", "Country": "country", "Region": "region", "Subregion": "subregion",
    "Elevation": "elev", "Tectonic_Setting": "tectonic", "Evidence_Category": "evidence", "Major_Rock_Type": "rock",
    "Geological_Summary": "summary",
}


class GvpError(RuntimeError):
    pass


def volcano_url(no: int) -> str:
    """사람이 읽는 화산 쪽."""
    return f"https://volcano.si.edu/volcano.cfm?vn={int(no)}"


def shrink(collection: dict) -> list:
    """WFS 의 GeoJSON → 화산마다 `FIELDS` 와 `lon`·`lat` 만 남긴 목록."""
    out = []
    for feature in collection.get("features") or []:
        geom, props = feature.get("geometry") or {}, feature.get("properties") or {}
        coords = geom.get("coordinates") if geom.get("type") == "Point" else None
        if not coords or props.get("Volcano_Number") is None:
            continue
        row = {short: props.get(long) for long, short in FIELDS.items()}
        row["lon"], row["lat"] = round(float(coords[0]), 5), round(float(coords[1]), 5)
        out.append(row)
    return out


def download(dest: Path) -> int:
    """홀로세 화산을 모두 받아 줄여 `dest` 에 적는다. 화산 수."""
    left = usage.paused()
    if left:
        raise GvpError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeName": LAYER,
              "outputFormat": "application/json"}
    try:
        r = requests.get(WFS, params=params, timeout=(settings.UPSTREAM_TIMEOUT, 300),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gvp", ok=False)
        raise GvpError(f"GVP 에 닿지 못했다: {exc}") from exc
    log.info("GVP %s -> %s", r.url, r.status_code)
    if r.status_code != 200:
        usage.record("gvp", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise GvpError(f"GVP 가 {r.status_code} 로 답했다")
    try:
        rows = shrink(r.json())
    except ValueError as exc:
        usage.record("gvp", ok=False)
        raise GvpError("GVP 가 GeoJSON 이 아닌 것을 주었다") from exc
    usage.record("gvp", ok=True)
    if not rows:
        raise GvpError("GVP 가 빈 목록을 주었다")
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps({"source": LAYER, "fetched": time.strftime("%Y-%m-%d"), "volcanoes": rows}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(dest)
    return len(rows)
