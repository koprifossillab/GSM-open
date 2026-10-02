"""GEUS(덴마크·그린란드 지질조사소)로 나가는 문 — 그린란드 지질도.

`kigam.py`·`vworld.py` 와 나란한 **세 번째 문**이다 (CLAUDE.md "상류마다 문이
하나"). 그린란드 레이어는 여기로만 나간다.

- 주소: `data.geus.dk/geusmap/ows/3857.jsp?mapname=greenland_portal` (MapServer)
  2026-09-27 에 찾았다. GEUS 안내 페이지는 `mapname=greenland` 를 적었지만
  그 이름은 404 이고, GEUS 지도 화면의 코드에 있던 `greenland_portal` 이 돈다
- **부르는 이를 밝힌다** (`whoami`). GEUS 는 서버가 작아 이름 없는 호출을
  바쁜 시간에 거절할 수 있다고 적었다. 로그에는 적지 않는다 — 이메일이다
- 그림은 3000 × 3000 까지, 한 번에 레이어 5 개까지 (GEUS 의 제한)
- 속성은 `text/plain` 으로 받는다. `application/json` 을 광고하지만 비어 온다
"""
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

_WHOAMI_RE = re.compile(r"(whoami=)[^&\s]*", re.I)


class GeusError(RuntimeError):
    pass


def _get(params: dict):
    sent = dict(params, nocache="nocache", mapname=settings.GEUS_MAPNAME,
                whoami=settings.GEUS_WHOAMI)
    try:
        r = requests.get(settings.GEUS_WMS_URL, params=sent, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("geus", ok=False)
        reason = _WHOAMI_RE.sub(r"\1…", str(exc))       # 예외 문구에 URL 이 실려 온다
        raise GeusError(f"GEUS 에 닿지 못했다: {reason}") from exc
    log.info("GEUS %s -> %s", _WHOAMI_RE.sub(r"\1…", r.url), r.status_code)
    usage.record("geus", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 GeusError."""
    params = dict(params, service="WMS", request="GetMap")
    # GEUS 는 WMS 1.1.1 의 SRS 를 쓴다. 브라우저가 1.3.0 의 CRS 로 보내면 옮겨 적는다
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params["version"] = "1.1.1"
    r = _get(params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GeusError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
              "format": "image/png", "layer": layer})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GeusError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` → KIGAM 과 같은 꼴의 GeoJSON 비슷한 dict (`features`)."""
    params = dict(params, service="WMS", request="GetFeatureInfo", info_format="text/plain")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    params["version"] = "1.1.1"
    r = _get(params)
    if r.status_code != 200:
        raise GeusError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


_FEATURE = re.compile(r"^\s*Feature\s+(\S+):\s*$")
_ATTR = re.compile(r"^\s{2,}(\w+)\s*=\s*'(.*)'\s*$")
_LAYER = re.compile(r"^Layer '([^']+)'")


def parse_plain(text: str) -> list:
    """MapServer 의 text/plain 속성을 feature 목록으로.

        Layer 'grl_g500_lithostr_search'
          Feature 733:
            gu_name = 'Rapakivi Suite'
    """
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


#: GEUS 의 열 이름 → 팝업에 보일 이름. 여기 없는 열은 그대로 보인다.
#: 안쪽에서만 쓰는 열(`id_hidden`·`rgb`)은 뺀다.
FRIENDLY = {
    "gu_mapcode": "지질기호",
    "gu_name": "지질 단위",
    "ics_min_age_num": "최소 연대 (Ma)",
    "ics_max_age_num": "최대 연대 (Ma)",
    "report_link": "설명",
}
HIDDEN = {"id_hidden", "rgb", "fid", "objectid", "gid"}


def friendly(props: dict) -> dict:
    out = {}
    for key, value in props.items():
        if key.lower() in HIDDEN:
            continue
        if isinstance(value, str) and re.fullmatch(r"-?\d+\.0+", value):
            value = value.split(".")[0]                   # 1600.000000 → 1600
        out[FRIENDLY.get(key, key)] = value
    return out
