"""BRGM(프랑스 지질광물조사소)으로 나가는 문 — 프랑스 지질도 (wetherilli 143).

- 주소: `geoservices.brgm.fr/geologie` (MapServer). 열쇠가 없다
- 조건: **Licence Ouverte / Etalab 2.0** (InfoTerre 이용 조건) — 출처(BRGM)와 마지막으로 고친 날을 밝히고, 뜻을 바꾸지 않는다.
  `ATTRIBUTION`
- 3857 을 그대로 받는다. 판마다 **그리는 축척이 정해져 있다** — 1:100만 스캔은 1:20만보다 멀 때, 1:25만 스캔은 1:8만–50만,
  1:5만 스캔은 1:25만보다 가까울 때. 카탈로그가 판마다 `minZoom`·`maxZoom` 을 알려 화면이 그 밖에서는 묻지 않는다
- 지질도는 **스캔(그림)** 이라 누를 것이 없다. 속성은 1:100만 단순 암상도만 준다(`text/plain`)
- 레이어명에 `brgm:` 를 붙여 카탈로그에 둔다. 상류로 나갈 때 뗀다
"""
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "brgm:"
ATTRIBUTION = ('<a href="https://infoterre.brgm.fr/page/conditions-dutilisation-donnees" target="_blank" rel="noopener">'
               '© BRGM</a> (Licence Ouverte Etalab 2.0)')
#: 그림(스캔)이라 누를 것이 없는 판
SCANS = {"SCAN_F_GEOL1M", "SCAN_F_GEOL250", "SCAN_H_GEOL50"}
#: 판마다 그리는 화면 줌(3857, 처음·끝) — 2026-10-02 에 파리에서 한 장씩 받아 잰 것. 화면은 그 밖에서 묻지 않는다
ZOOMS = {"SCAN_F_GEOL1M": (6, 11), "SCAN_F_GEOL250": (11, 12), "SCAN_H_GEOL50": (12, None),
         "LITHO_1M_SIMPLIFIEE": (6, 14)}


class BrgmError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise BrgmError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.BRGM_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("brgm", ok=False)
        raise BrgmError(f"BRGM 에 닿지 못했다: {exc}") from exc
    log.info("BRGM %s -> %s", r.url, r.status_code)
    usage.record("brgm", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    """`GetMap`. MapServer 는 오류도 200 으로 주므로 그림인지 본다."""
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BrgmError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BrgmError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise BrgmError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


_LAYER = re.compile(r"^Layer '([^']+)'")
_FEATURE = re.compile(r"^\s*Feature\s+(\S+):\s*$")
_ATTR = re.compile(r"^\s{2,}(\w+)\s*=\s*'(.*)'\s*$")


def parse_plain(text: str) -> list:
    """MapServer 의 text/plain 속성 → feature 목록. 문은 서로를 타지 않아 NGU·GEUS 와 따로 둔다."""
    features, layer, current = [], "", None
    for line in (text or "").splitlines():
        m = _LAYER.match(line)
        if m:
            layer = m.group(1)
            continue
        m = _FEATURE.match(line)
        if m:
            current = {"id": f"{layer}.{m.group(1)}", "properties": {}}
            features.append(current)
            continue
        m = _ATTR.match(line)
        if m and current is not None:
            current["properties"][m.group(1)] = m.group(2)
    return features


#: 상류의 열 → 팝업에 보일 이름. 값은 프랑스어 그대로 둔다
FRIENDLY = (("DESCR", "암상"), ("TYPE", "갈래"))


def friendly(props: dict) -> dict:
    return {label: str(props[key]).strip() for key, label in FRIENDLY if str(props.get(key) or "").strip()}
