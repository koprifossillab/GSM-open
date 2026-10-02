"""GSI(아일랜드 지질조사소)로 나가는 문 — 아일랜드 기반암 지질도 (wetherilli 147).

- 주소: `gsi.geodata.gov.ie/server/services/Bedrock/<판>/MapServer/WMSServer` (ArcGIS WMS). 판은 둘 —
  `IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM`(섬 전체 1:100만, 북아일랜드 GSNI 와 함께 만든 것)·
  `IE_GSI_Bedrock_Geology_Datasets_100K_IE26_ITM`(공화국 1:10만). 열쇠가 없다
- 조건: GSI 가 만든 자료는 **CC BY 4.0**, 1:100만의 북아일랜드 몫은 영국 **OGL v3** (GetCapabilities). `ATTRIBUTION`
- 3857 을 그대로 받는다. 1:10만은 줌 6–14 에서만 그린다(2026-10-02 에 잰 것) — 1:2만 3천보다 가까우면 빈 그림이다
- 레이어명은 상류 이름이 길고 판마다 다르므로 `gsi:<판>:<레이어>` 로 둔다
- 속성은 `application/geojson` — BGS·BGR 의 `geo+json` 과 이름이 다르다(같은 ArcGIS 인데)
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "gsi:"
ATTRIBUTION = ('Contains Irish Public Sector Data (<a href="https://www.gsi.ie/" target="_blank" rel="noopener">'
               'Geological Survey Ireland</a>, CC BY 4.0) · Geological Survey of Northern Ireland (OGL)')
SHEETS = {"1m": "IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM", "100k": "IE_GSI_Bedrock_Geology_Datasets_100K_IE26_ITM"}
ZOOMS = {"1m": (None, None), "100k": (6, 14)}


class GsiError(RuntimeError):
    pass


def split(name: str):
    sheets, layers = set(), []
    for one in str(name or "").split(","):
        one = one.strip()
        if one.startswith(PREFIX):
            one = one[len(PREFIX):]
        sheet, _, layer = one.partition(":")
        if sheet not in SHEETS or not layer:
            raise GsiError(f"모르는 레이어다: {one}")
        sheets.add(sheet)
        layers.append(layer)
    if len(sheets) != 1:
        raise GsiError("판이 다른 레이어를 한 번에 물을 수 없다")
    return sheets.pop(), ",".join(layers)


def _get(sheet: str, params: dict):
    left = usage.paused()
    if left:
        raise GsiError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.GSI_WMS_URL.rstrip('/')}/{SHEETS[sheet]}/MapServer/WMSServer"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsi", ok=False)
        raise GsiError(f"GSI 에 닿지 못했다: {exc}") from exc
    log.info("GSI %s -> %s", r.url, r.status_code)
    usage.record("gsi", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str):
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    sheet, params["layers"] = split(params.get("layers") or params.get("query_layers"))
    if "query_layers" in params:
        params["query_layers"] = split(params["query_layers"])[1]
    return sheet, params


def get_map(params: dict):
    sheet, params = _wms(params, "GetMap")
    r = _get(sheet, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsiError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    sheet, name = split(layer)
    r = _get(sheet, {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                     "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise GsiError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    sheet, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geojson"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(sheet, params)
    if r.status_code != 200:
        raise GsiError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise GsiError("속성이 JSON 이 아니다") from exc


FRIENDLY = (
    ("Rock Unit Name", "지질 단위"),
    ("Description", "암석"),
    ("Geological Age", "지질시대"),
    ("Stratigraphic Code", "기호"),
    ("Bedrock Geology 100k Sheet Number", "도폭"),
    ("Document Link", "설명"),
)


def friendly(props: dict) -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if value and label not in out:
            out[label] = value
    return out
