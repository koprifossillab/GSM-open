"""NGU(노르웨이 지질조사소)로 나가는 문 — 노르웨이 본토 기반암 지질도 (wetherilli 140).

- 주소: `geo.ngu.no/mapserver/BerggrunnWMS3` (MapServer). 열쇠가 없다. 국가(1:135만)·지역(1:25만)·지방(1:5만)
  세 축척의 기반암 데이터베이스를 레이어로 나눠 준다
- 조건: 노르웨이 공공데이터 라이선스(**NLOD 2.0**) — NGU 자료 정책. 출처를 밝히되 NGU 가 승인한 것처럼 보이게 쓰지
  않는다. `ATTRIBUTION`
- **3413 을 그려 주지 않는다**(`InvalidSRS`). 대신 북극 람베르트 등적 유럽판(**EPSG:3575**, 경도 10° 가 아래)을 받아
  OpenLayers 가 3413 화면에 옮겨 그린다. 3857 로 물으면 북위 70° 에서 축척이 세 배 부풀어 축척 따라 켜고 끄는 레이어가
  어긋난다(NPI 021 의 함정)
- 레이어명에 `ngu:` 를 붙여 카탈로그에 둔다 — 상류로 나갈 때 뗀다
- 속성은 `text/plain` 이다(JSON 을 주지 않는다). GEUS 와 같은 MapServer 꼴이지만 문은 서로를 타지 않아 읽는 함수를 따로 둔다
"""
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "ngu:"
ATTRIBUTION = ('<a href="https://www.ngu.no/" target="_blank" rel="noopener">© NGU</a>'
               ' (<a href="https://data.norge.no/nlod/no/2.0" target="_blank" rel="noopener">NLOD 2.0</a>)')


class NguError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    """카탈로그의 이름(여럿이면 쉼표) → 상류의 이름."""
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise NguError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.NGU_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("ngu", ok=False)
        raise NguError(f"NGU 에 닿지 못했다: {exc}") from exc
    log.info("NGU %s -> %s", r.url, r.status_code)
    usage.record("ngu", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
    return r


def _wms(params: dict, request: str) -> dict:
    """브라우저가 보낸 것을 1.1.1 로 옮겨 적는다."""
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 NguError — MapServer 는 오류도 200 으로 준다."""
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise NguError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise NguError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "text/plain"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise NguError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


_LAYER = re.compile(r"^Layer '([^']+)'")
_FEATURE = re.compile(r"^\s*Feature\s+(\S+):\s*$")
_ATTR = re.compile(r"^\s{2,}(\w+)\s*=\s*'(.*)'\s*$")


def parse_plain(text: str) -> list:
    """MapServer 의 text/plain 속성 → feature 목록.

        Layer 'Berggrunn_regional_hovedbergarter'
          Feature 39881:
            hovedbergart_tekst = 'Grønnstein'
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


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로** 보인다 — 나머지는 번호·날짜·색 값이다.
#: 값은 노르웨이어 그대로 둔다(속성 값은 옮기지 않는다). 영문이 따로 오는 것만 함께 싣는다
FRIENDLY = (
    ("bergartsenhet_tekst", "암석 단위"),
    ("bergartsenhet_tekst_engelsk", "암석 단위 (영문)"),
    ("hovedbergart_tekst", "주 암석"),
    ("tilleggsbergart1_tekst", "딸린 암석"),
    ("tilleggsbergart2_tekst", "딸린 암석 2"),
    ("dannelsesalder_tekst", "형성 연대"),
    ("dannelsesalder_visning_tekst", "형성 연대"),
    ("metamorffacies_tekst", "변성상"),
    ("metamorfalder_tekst", "변성 연대"),
    ("tektoniskhovedinndeling_tekst", "지구조 구분"),
    ("tektoniskenhet_tekst", "지구조 단위"),
    ("berggrunn_datatype_tekst", "자료"),
)
#: 지도를 그리지 않은 자리 — 속성이 아니라 빈칸의 표시다
_UNMAPPED = {"IKKE KARTLAGT"}


def friendly(props: dict) -> dict:
    if str(props.get("bergartsenhet_tekst", "")).strip().upper() in _UNMAPPED:
        return {}
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:                   # 형성 연대는 단일 값이 있으면 그것을, 없으면 "Fra … til …"
            out[label] = value
    return out
