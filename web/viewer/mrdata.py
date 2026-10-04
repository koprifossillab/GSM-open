"""USGS mrdata(광물자원 자료 서버)로 나가는 문 — 미국 본토 주 지질도 합본 SGMC 와 알래스카 지질도 SIM 3340 (wetherilli 205).

- 주소: `mrdata.usgs.gov/services/<서비스>` (MapServer WMS). 서비스는 둘 — `sgmc2`(SGMC, 본토 48 주, Horton 외 2017, USGS DS 1052,
  주마다 1:5만–1:100만을 합친 것)·`sim3340`(알래스카, Wilson 외 2015, SIM 3340, 1:158만). 열쇠가 없다. CORS `*`
- 레이어명은 `mrdata:<서비스>:<레이어>` 다. 지진 목록의 `usgs.py` 와 같은 기관이지만 서버도 하는 일도 달라 문을 따로 두었다
- **SGMC 의 WMS 는 MapCache 앞단이라 GetFeatureInfo 가 막혀 있다**("unqueryable layer"). 그래서 누른 자리는 **WFS 1.0**(`services/wfs/sgmc2`,
  `typeName=Lithology`)에 아주 작은 경위도 네모로 묻는다. `PROPERTYNAME` 을 붙이면 기하가 빠져 1 KB 남짓이다(안 붙이면 66 KB).
  WFS 1.1 은 축 순서를 맞추지 않으면 빈 답이라 1.0 을 쓴다. 이름·시대 열은 없고 단위 설명 쪽 주소(`url`)가 온다
- **알래스카는 WMS GetFeatureInfo 가 된다.** GML 은 기하가 붙어 226 KB 라 `text/plain`(400 B)으로 받아 읽는다. 알래스카에는 WFS 가 없다
- 범례는 없다 — SGMC 는 단위가 주마다 수천이고 GetLegendGraphic 이 501 이다. 팝업의 단위 쪽 링크가 범례를 갈음한다
- **알래스카의 "Water" 면은 문이 지운다**(wetherilli 224) — SIM 3340 은 도폭마다 바다를 네모난 물 면(`#ccffff`)으로 칠해 두어 알류샨
  남쪽에 북위 51.5° 를 따라 하늘색 띠가 선다. 물은 지질이 아니고 그 색을 쓰는 단위가 물뿐이라(빙하는 투명) 받은 그림의 그 색을 투명으로
  바꾼다. 고침의 판(`REDRAWN`)이 캐시 열쇠에 든다 — 띠가 든 옛 타일을 내지 않게
- 조건: USGS 자료 — 공공 도메인, 출처 표기만(AccessConstraints none). 정적 판에 실을 수 있다(`static_site.py --with usa`)
"""
import logging
import math
import re

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "mrdata:"
ATTRIBUTION = ('<a href="https://mrdata.usgs.gov/geology/state/" target="_blank" rel="noopener">USGS SGMC</a> '
               "(Horton et al. 2017, DS 1052) · USGS SIM 3340 Alaska (Wilson et al. 2015) — public domain")
#: 레이어 → (서비스, WMS 레이어). 누를 수 있는 것은 단위 면뿐이다
LAYERS = {
    "mrdata:sgmc2:sgmc2": ("sgmc2", "sgmc2"),
    "mrdata:sgmc2:sgmc2structure": ("sgmc2", "sgmc2structure"),
    "mrdata:sim3340:units": ("sim3340", "units"),
    "mrdata:sim3340:faults": ("sim3340", "faults"),
}
QUERYABLE = ("mrdata:sgmc2:sgmc2", "mrdata:sim3340:units")
#: 받은 그림을 문이 고쳐 내는 레이어 → 고침의 판. 고치는 법을 바꾸면 올린다 — 캐시 열쇠에 든다(`views.map_cache_key`)
REDRAWN = {"mrdata:sim3340:units": "1"}
#: 알래스카의 "Water" 단위 색
WATER = (204, 255, 255)
#: 가장자리의 섞인 색까지 지울 너비 — 2026-10-04 에 알류샨 그림에서 191,239,239 까지 보였다
WATER_TOLERANCE = 16
#: SGMC WFS 에서 받을 열 — 기하는 받지 않는다
SGMC_FIELDS = ("state", "orig_label", "unit_link", "generalize", "src_url", "url")
#: 누른 자리 둘레의 반지름(픽셀) — 다른 WMS 의 GetFeatureInfo 둘레와 비슷하게
CLICK_PX = 2


class MrdataError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _one(params: dict):
    names = [n.strip() for n in str(params.get("layers") or params.get("query_layers") or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise MrdataError(f"모르는 레이어다: {names}")
    return names[0], LAYERS[names[0]]


def _get(url: str, params: dict):
    left = usage.paused()
    if left:
        raise MrdataError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, 30),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("mrdata", ok=False)
        raise MrdataError(f"USGS mrdata 에 닿지 못했다: {exc}") from exc
    log.info("mrdata %s -> %s", r.url, r.status_code)
    usage.record("mrdata", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _base() -> str:
    return settings.MRDATA_URL.rstrip("/")


def get_map(params: dict):
    name, (service, layer) = _one(params)
    r = _get(f"{_base()}/{service}", dict(params, service="WMS", request="GetMap", layers=layer))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise MrdataError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    if name in REDRAWN and ctype.startswith("image/png"):
        return clear_water(r.content), "image/png"
    return r.content, ctype


def redraw_tag(layers) -> str:
    """캐시 열쇠에 넣을 고침의 판 — 고치지 않는 레이어면 빈 글"""
    return REDRAWN.get(str(layers or "").split(",")[0].strip(), "")


def clear_water(png: bytes) -> bytes:
    """알래스카 그림에서 물 면(`WATER`)을 투명으로. 가장자리는 매끈하게 섞여(202,253,253 반투명 따위) 남으므로 물 색 둘레
    `WATER_TOLERANCE` 안이면서 초록·파랑이 같은(옥빛) 것까지 지운다 — 물 면과 섞인 땅의 가장자리는 땅 색이 짙어 남는다"""
    import io

    from PIL import Image, ImageChops
    try:
        img = Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:          # noqa: BLE001 — 읽지 못하는 그림은 받은 그대로 낸다
        return png
    r, g, b, a = img.split()
    near = lambda band, want: Image.eval(band, lambda v: 255 if abs(v - want) <= WATER_TOLERANCE else 0)  # noqa: E731
    mask = ImageChops.multiply(ImageChops.multiply(near(r, WATER[0]), near(g, WATER[1])), near(b, WATER[2]))
    mask = ImageChops.multiply(mask, Image.eval(ImageChops.difference(g, b), lambda v: 255 if v <= 2 else 0))
    img.putalpha(Image.composite(Image.new("L", img.size, 0), a, mask))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def get_legend(layer: str):
    raise MrdataError("USGS 지질도는 범례를 주지 않는다 — 단위가 주마다 수천이다")


def click_lonlat(params: dict):
    """WMS GetFeatureInfo 의 변수(3857 범위·크기·I·J) → 누른 자리의 (경도, 위도)와 한 픽셀의 도(°)."""
    try:
        west, south, east, north = (float(v) for v in str(params["bbox"]).split(","))
        width, height = int(params["width"]), int(params["height"])
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (KeyError, TypeError, ValueError) as exc:
        raise MrdataError("누른 자리를 읽지 못했다") from exc
    x = west + (east - west) * (i + 0.5) / width
    y = north - (north - south) * (j + 0.5) / height
    lon = math.degrees(x / 6378137.0)
    lat = math.degrees(2 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2)
    pixel = math.degrees((east - west) / width / 6378137.0)
    return lon, lat, pixel


def get_feature_info(params: dict) -> dict:
    name, (service, layer) = _one(params)
    if name not in QUERYABLE:
        return {"features": []}
    if service == "sgmc2":
        lon, lat, pixel = click_lonlat(params)
        d = max(pixel * CLICK_PX, 1e-5)
        r = _get(f"{_base()}/wfs/sgmc2", {"service": "WFS", "version": "1.0.0", "request": "GetFeature",
                                          "typeName": "Lithology", "maxFeatures": "3",
                                          "bbox": f"{lon - d:.6f},{lat - d:.6f},{lon + d:.6f},{lat + d:.6f}",
                                          "propertyName": ",".join(SGMC_FIELDS)})
        if r.status_code != 200:
            raise MrdataError(f"속성을 읽지 못했다 (status={r.status_code})")
        return {"features": parse_gml(r.text, "Lithology")}
    r = _get(f"{_base()}/{service}", dict(params, service="WMS", request="GetFeatureInfo", layers=layer,
                                          query_layers=layer, info_format="text/plain"))
    if r.status_code != 200:
        raise MrdataError(f"속성을 읽지 못했다 (status={r.status_code})")
    return {"features": parse_plain(r.text)}


def parse_gml(text: str, kind: str) -> list:
    """MapServer WFS 1.0 GML → feature 목록. `<ms:열>값</ms:열>` 만 읽는다(기하는 받지 않았다)."""
    out = []
    for n, block in enumerate(re.findall(rf"<ms:{kind}[^>]*>(.*?)</ms:{kind}>", text, re.S)):
        props = {k: _unescape(v.strip()) for k, v in re.findall(r"<ms:([A-Za-z_]+)>(.*?)</ms:\1>", block, re.S)}
        out.append({"id": f"{kind}.{n}", "properties": props})
    return out


def parse_plain(text: str) -> list:
    """MapServer GetFeatureInfo `text/plain` → feature 목록 (`Feature N:` 밑의 `열 = '값'` 줄)."""
    out, props, fid = [], None, ""
    for line in text.splitlines():
        head = re.match(r"\s*Feature (\S+):", line)
        if head:
            if props is not None:
                out.append({"id": fid, "properties": props})
            props, fid = {}, head.group(1)
            continue
        pair = re.match(r"\s+(\w+) = '(.*)'\s*$", line)
        if pair and props is not None:
            props[pair.group(1)] = pair.group(2)
    if props is not None:
        out.append({"id": fid, "properties": props})
    return out


def _unescape(text: str) -> str:
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")


def _link(url: str):
    url = str(url or "").strip()
    return {"text": "", "links": [{"url": url, "label": "열기"}]} if url.startswith(("http://", "https://")) else None


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 영어 그대로 — 알래스카의 시대(`age_range`)만 ICS 영문이라 한국어판이면 옮긴다."""
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    if "state_unit" in props or "age_range" in props:     # 알래스카
        age = v("age_range")
        rows = (("이름", v("state_unit")), ("기호", v("label")),
                ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("단위 설명", _link(v("url"))))
    else:                                                  # 본토 SGMC
        rows = (("주", v("state")), ("기호", v("orig_label")), ("암상", v("generalize")),
                ("단위 설명", _link(v("url"))), ("원도", _link(v("src_url"))))
    return {k: x for k, x in rows if x}
