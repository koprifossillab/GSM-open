"""USGS mrdata(광물자원 자료 서버)로 나가는 문 — 미국 본토 주 지질도 합본 SGMC 와 알래스카 지질도 SIM 3340 (wetherilli 205).

- 주소: `mrdata.usgs.gov/services/<서비스>` (MapServer WMS). 서비스는 둘 — `sgmc2`(SGMC, 본토 48 주, Horton 외 2017, USGS DS 1052,
  주마다 1:5만–1:100만을 합친 것)·`sim3340`(알래스카, Wilson 외 2015, SIM 3340, 1:158만). 열쇠가 없다. CORS `*`
- 레이어명은 `mrdata:<서비스>:<레이어>` 다. 지진 목록의 `usgs.py` 와 같은 기관이지만 서버도 하는 일도 달라 문을 따로 두었다
- **SGMC 의 WMS 는 MapCache 앞단이라 GetFeatureInfo 가 막혀 있다**("unqueryable layer"). 그래서 누른 자리는 **WFS 1.0**(`services/wfs/sgmc2`,
  `typeName=Lithology`)에 아주 작은 경위도 네모로 묻는다. `PROPERTYNAME` 을 붙이면 기하가 빠져 1 KB 남짓이다(안 붙이면 66 KB).
  WFS 1.1 은 축 순서를 맞추지 않으면 빈 답이라 1.0 을 쓴다. 이름·시대 열은 없고 단위 설명 쪽 주소(`url`)가 온다
- **알래스카는 WMS GetFeatureInfo 가 된다.** GML 은 기하가 붙어 226 KB 라 `text/plain`(400 B)으로 받아 읽는다. 알래스카에는 WFS 가 없다
- 범례 — SGMC 는 단위가 주마다 수천이고 GetLegendGraphic·GetStyles 가 501 이다(MapCache 앞단). 그런데 **색은 단위가 아니라 일반화한 암상
  (`generalize`, 스물셋 남짓)으로만 칠한다**(wetherilli 334 — 열넷 자리에서 같은 갈래는 늘 같은 색). 그래서 보는 범위의 갈래를 WFS 로 세고(기하 없이
  `propertyName=generalize`) 색은 한 번 떠 둔 표(`SGMC_COLORS`)에서 찾는다. 팝업의 단위 쪽 링크는 그대로
- **알래스카·하와이·푸에르토리코의 범례**(wetherilli 353) — 이쪽 MapServer 는 GetLegendGraphic 을 주지만 단위 이백여 칸이 세로 3 400–4 300 px 한 장이다.
  WFS 가 없어(알래스카) 보는 범위를 세지도 못한다. 그래서 칠하기 규칙(`GetStyles` 의 SLD — 규칙 이름과 채움색)을 한 번 받아 두고, 보는 범위의
  그림 한 장(512 px)에 칠해진 색을 세어 규칙과 맞댄다(`unit_legend`). 알래스카는 단위 기호, 하와이는 기호, 푸에르토리코는 암상 이름이 칸의 이름이다
- **알래스카의 "Water" 면은 문이 지운다**(wetherilli 224) — SIM 3340 은 도폭마다 바다를 네모난 물 면(`#ccffff`)으로 칠해 두어 알류샨
  남쪽에 북위 51.5° 를 따라 하늘색 띠가 선다. 물은 지질이 아니고 그 색을 쓰는 단위가 물뿐이라(빙하는 투명) 받은 그림의 그 색을 투명으로
  바꾼다. 고침의 판(`REDRAWN`)이 캐시 열쇠에 든다 — 띠가 든 옛 타일을 내지 않게
- **하와이·푸에르토리코**(wetherilli 238) — 같은 서버의 `hi`(Sherrod 외 2007, 1:10만·25만, 섬마다 화산·성장 단계)·`pr`(Bawiec 1998,
  1:10만 남짓). 3857·4326 만 받는다(3978 은 InvalidSRS) — 본토처럼 3857 로 받아 화면이 옮겨 그린다. 속성은 알래스카처럼 WMS `text/plain`
- **같은 서버의 다른 자료**(wetherilli 247) — 광물 자원 MRDS(`mrds`)·지형도의 광산 기호 USMIN(`usmin` 점·면)·지질 연대 측정 기록(`geochron`)은
  `text/plain` 으로 누른다. 북미 자력 이상 NAMAG(`aeromag`)·중력 이상(`gravity` — 아이소스타시·부게)은 그림뿐이라 누르지 않는다(QUERY_LAYERS 가
  LayerNotDefined). 서비스 목록 쪽이 맵 파일 오류를 내 이름은 검색과 Capabilities 로 찾았다
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
    "mrdata:hi:units": ("hi", "units"),
    "mrdata:hi:faults": ("hi", "faults"),
    "mrdata:hi:dikes": ("hi", "dikes"),
    "mrdata:pr:geol": ("pr", "geol"),
    "mrdata:pr:fault": ("pr", "fault"),
    "mrdata:pr:faultn": ("pr", "faultn"),
    "mrdata:mrds:mrds": ("mrds", "mrds"),
    "mrdata:usmin:points": ("usmin", "points"),
    "mrdata:usmin:polygons": ("usmin", "polygons"),
    "mrdata:geochron:geochron": ("geochron", "geochron"),
    "mrdata:aeromag:namag": ("aeromag", "namag"),
    "mrdata:gravity:isostatic": ("gravity", "isostatic"),
    "mrdata:gravity:bouguer": ("gravity", "bouguer"),
}
#: 넓게 보면 점이 땅을 덮는 레이어 — 처음 그리는 화면 줌 (wetherilli 247)
MIN_ZOOM = {"mrdata:mrds:mrds": 7, "mrdata:usmin:points": 9, "mrdata:usmin:polygons": 9,
            "mrdata:sgmc2:sgmc2structure": 9}      # SGMC 구조선 — MapCache 가 격자 줌 8 밑에서 404 (wetherilli 310)
QUERYABLE = ("mrdata:sgmc2:sgmc2", "mrdata:sim3340:units", "mrdata:hi:units", "mrdata:pr:geol",
             "mrdata:mrds:mrds", "mrdata:usmin:points", "mrdata:usmin:polygons", "mrdata:geochron:geochron")
#: 섬 — 미국 탭(3978)에서 제 범위 밖 타일을 묻지 않는다 (wetherilli 238)
ISLANDS = tuple(n for n in LAYERS if n.startswith(("mrdata:hi:", "mrdata:pr:")))
#: 받은 그림을 문이 고쳐 내는 레이어 → 고침의 판. 고치는 법을 바꾸면 올린다 — 캐시 열쇠에 든다(`views.map_cache_key`)
REDRAWN = {"mrdata:sim3340:units": "1"}
#: 알래스카의 "Water" 단위 색
WATER = (204, 255, 255)
#: 가장자리의 섞인 색까지 지울 너비 — 2026-10-04 에 알류샨 그림에서 191,239,239 까지 보였다
WATER_TOLERANCE = 16
#: SGMC 의 일반화 암상(`generalize`) → 그림의 색. 2026-10-05 에 열 지역(콜로라도·애팔래치아·미네소타·캐스케이드·플로리다·애디론댁·애리조나·
#: 미시간·네바다·와이오밍)에서 면 1 500 의 안쪽 점을 골라 WMS 그림의 색을 떠 가장 잦은 것을 적었다(wetherilli 334). 백립암(granulite)·텍토나이트처럼
#: 드문 갈래는 한두 점에서 떴다. 표에 없는 갈래는 회색으로 범례에 선다
SGMC_COLORS = {
    "Igneous and Metamorphic, undifferentiated": "#c73872",
    "Igneous and Sedimentary, undifferentiated": "#724c00",
    "Igneous, intrusive": "#ffbfbf",
    "Igneous, undifferentiated": "#a90000",
    "Igneous, volcanic": "#ff0000",
    "Metamorphic and Sedimentary, undifferentiated": "#a8a800",
    "Metamorphic, amphibolite": "#267200",
    "Metamorphic, carbonate": "#00a985",
    "Metamorphic, gneiss": "#81cd4c",
    "Metamorphic, granulite": "#55ff00",
    "Metamorphic, intrusive": "#a92885",
    "Metamorphic, schist": "#b2b2b2",
    "Metamorphic, sedimentary clastic": "#ebce9a",
    "Metamorphic, undifferentiated": "#91c340",
    "Metamorphic, volcanic": "#d7d79e",
    "Sedimentary, carbonate": "#004daa",
    "Sedimentary, clastic": "#b39b4c",
    "Sedimentary, iron formation, undifferentiated": "#000000",
    "Sedimentary, undifferentiated": "#e79900",
    "Tectonite, undifferentiated": "#c600ff",
    "Unconsolidated and Sedimentary, undifferentiated": "#ffd37f",
    "Unconsolidated, undifferentiated": "#ffffbf",
    "Water": "#97dbf3",
}
#: SGMC 범례를 세는 가장 넓은 범위(°)와 한 번에 세는 면의 수 — 6° 네모가 2 초 남짓(면 3 000)
SGMC_SPAN = 8.0
SGMC_SAMPLE = 3000
#: 보는 범위의 그림으로 범례를 세는 단위 면 — 알래스카·하와이·푸에르토리코 (wetherilli 353)
UNIT_LEGENDS = ("mrdata:sim3340:units", "mrdata:hi:units", "mrdata:pr:geol")
UNIT_SAMPLE_PX = 512
#: 이보다 작은 몫의 색은 버린다 — 가장자리의 섞인 색
UNIT_MIN_SHARE = 0.0005
#: 범례에 세울 칸의 수 — 넘는 것은 "외 n" 으로
UNIT_MAX_LEGEND = 60
#: 이보다 넓으면 그림 한 장에 단위가 뭉개져 범례를 세지 않는다(°) — 알래스카 전체가 든다
UNIT_SPAN = 45.0

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
    usage.record("mrdata", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]), elapsed=r.elapsed)
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


def sgmc_legend(bbox) -> list:
    """보는 범위의 일반화 암상 — [(갈래, 면의 수)], 많은 것부터. WFS 에 기하 없이 `generalize` 만 묻는다 (wetherilli 334)"""
    west, south, east, north = bbox
    r = _get(f"{_base()}/wfs/sgmc2", {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "Lithology",
                                      "maxFeatures": str(SGMC_SAMPLE), "bbox": f"{west},{south},{east},{north}",
                                      "propertyName": "generalize"})
    if r.status_code != 200:
        raise MrdataError(f"범례를 세지 못했다 (status={r.status_code})")
    counts = {}
    for value in re.findall(r"<ms:generalize>([^<]*)</ms:generalize>", r.text):
        value = _unescape(value.strip())
        if value:
            counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


def sgmc_legend_row(name: str) -> dict:
    return {"symbol": "", "lithology": name, "swatch": "", "color": SGMC_COLORS.get(name, "#cccccc"), "age": ""}


def parse_sld(text: str) -> list:
    """MapServer `GetStyles` 의 SLD → [(규칙 이름, "#rrggbb")]. 면을 칠하는 규칙만, 적힌 차례대로"""
    out = []
    for rule in re.findall(r"<Rule>(.*?)</Rule>", text, re.S):
        name = re.search(r"<Name>([^<]*)</Name>", rule)
        fill = re.search(r'<PolygonSymbolizer>.*?<CssParameter name="fill">\s*(#[0-9A-Fa-f]{6})\s*<', rule, re.S)
        if name and fill:
            out.append((_unescape(name.group(1).strip()), fill.group(1).lower()))
    return out


def unit_styles(name: str) -> list:
    """단위 면 레이어의 칠하기 규칙 — 서비스의 SLD 를 한 번 받는다(부르는 쪽이 캐시에 담는다)"""
    service, layer = LAYERS[name]
    r = _get(f"{_base()}/{service}", {"service": "WMS", "version": "1.1.1", "request": "GetStyles", "layers": layer})
    if r.status_code != 200 or "<Rule>" not in r.text:
        raise MrdataError(f"칠하기 규칙을 받지 못했다 (status={r.status_code})")
    return parse_sld(r.text)


def unit_legend(name: str, bbox, rules: list) -> list:
    """보는 범위에 칠해진 단위 — [(이름, 색, 몫)], 넓은 것부터 (wetherilli 353).

    알래스카에는 WFS 가 없고 하와이·푸에르토리코의 WMS 도 단위를 세어 주지 않는다. 그래서 **보는 범위의 그림 한 장**을 받아 칸마다 색을 세고
    SLD 의 규칙 색과 맞댄다. 같은 색을 쓰는 규칙은 한 칸으로 묶는다(상류의 범례 그림도 그렇게 묶는다). 가장자리의 섞인 색이 우연히 다른 규칙과
    같을 수 있어 `UNIT_MIN_SHARE` 밑은 버린다. 넓게 보면 작은 단위는 그림에서 사라져 범례에서도 빠진다"""
    import io

    from PIL import Image

    service, layer = LAYERS[name]
    west, south, east, north = bbox
    merc = lambda lon, lat: (math.radians(lon) * 6378137.0,                       # noqa: E731
                             math.log(math.tan(math.pi / 4 + math.radians(max(-85.0, min(85.0, lat))) / 2)) * 6378137.0)
    (x0, y0), (x1, y1) = merc(west, south), merc(east, north)
    r = _get(f"{_base()}/{service}", {"service": "WMS", "version": "1.1.1", "request": "GetMap", "layers": layer, "styles": "",
                                      "srs": "EPSG:3857", "bbox": f"{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}",
                                      "width": str(UNIT_SAMPLE_PX), "height": str(UNIT_SAMPLE_PX),
                                      "format": "image/png", "transparent": "true"})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise MrdataError(f"범례를 셀 그림을 받지 못했다 (status={r.status_code})")
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    counts = {}
    for n, (red, green, blue, alpha) in img.getcolors(UNIT_SAMPLE_PX * UNIT_SAMPLE_PX) or []:
        if alpha >= 250:
            hexed = f"#{red:02x}{green:02x}{blue:02x}"
            counts[hexed] = counts.get(hexed, 0) + n
    total = sum(counts.values()) or 1
    names = {}
    for rule, color in rules:
        names.setdefault(color, [])
        if rule not in names[color]:
            names[color].append(rule)
    water = f"#{WATER[0]:02x}{WATER[1]:02x}{WATER[2]:02x}"     # 알래스카의 물 면 — 타일에서도 지운다(`REDRAWN`)
    rows = [(", ".join(x for x in names[c] if x), c, n / total) for c, n in counts.items()
            if c in names and c != water and any(names[c]) and n / total >= UNIT_MIN_SHARE]
    return sorted(rows, key=lambda row: -row[2])


def unit_legend_row(label: str, color: str) -> dict:
    return {"symbol": "", "lithology": label, "swatch": "", "color": color, "age": ""}


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


def _island_age(age: str, lang: str) -> str:
    """`upper ? Cretaceous`·`Holocene` 따위 → 한국어. upper·lower 는 ICS 의 late·early 로, `?` 는 뒤에 단다. 못 옮기면 원문
    (`A.D. 1935`·`0-200 yr` 처럼 해·햇수로 적은 것은 그대로)"""
    if lang != "ko" or not age:
        return age
    doubt = "?" in age
    words = [{"upper": "Late", "lower": "Early", "middle": "Middle"}.get(w.lower(), w) for w in age.replace("?", " ").split()]
    ics = " ".join(words) + (" (?)" if doubt else "")
    ko = i18n.age_ko(ics)
    return ko if ko != ics else age


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 값은 영어 그대로 — 알래스카의 시대(`age_range`)만 ICS 영문이라 한국어판이면 옮긴다."""
    v = lambda k: str(props.get(k) or "").strip()          # noqa: E731
    if "dep_id" in props:                                  # 광물 자원 MRDS (wetherilli 247)
        rows = (("이름", v("site_name")), ("광종", v("code_list")), ("개발 단계", v("dev_stat")), ("보고서", _link(v("url"))))
        return {k: x for k, x in rows if x}
    if "ftr_type" in props:                                # 지형도의 광산 기호 USMIN
        scale = v("topo_scale")
        topo = " ".join(x for x in (v("topo_name"), f"({v('topo_date')}, 1:{int(scale):,})" if scale.isdigit() else "") if x)
        rows = (("갈래", v("ftr_type")), ("이름", v("ftr_name")), ("주", " · ".join(x for x in (v("county"), v("state")) if x)),
                ("지형도", topo), ("비고", v("remarks")))
        return {k: x for k, x in rows if x}
    if "recno" in props:                                   # 지질 연대 측정 기록 — 값은 상세 쪽에만 있다
        return {k: x for k, x in (("기록 번호", v("recno")), ("상세", _link(v("url")))) if x}
    if "volcano" in props:                                 # 하와이 (wetherilli 238)
        age = v("age_range")
        rows = (("이름", v("name") or v("unit")), ("기호", v("symbol")), ("지질시대", _island_age(age, lang)),
                ("암석", " · ".join(x for x in (v("rock_type"), v("lithology")) if x)), ("조성", v("compositio")),
                ("섬", v("island")), ("화산 성장 단계", v("volc_stage")), ("원도", v("source")), ("단위 설명", _link(v("url"))))
        return {k: x for k, x in rows if x}
    if "fmatn" in props:                                   # 푸에르토리코 (wetherilli 238)
        rows = (("이름", v("name")), ("기호", v("fmatn")), ("지질시대", _island_age(v("age"), lang)), ("암상", v("lith62name")),
                ("설명", v("descript")), ("참고 문헌", v("refs")), ("단위 설명", _link(v("url"))))
        return {k: x for k, x in rows if x}
    if "state_unit" in props or "age_range" in props:     # 알래스카
        age = v("age_range")
        rows = (("이름", v("state_unit")), ("기호", v("label")),
                ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age), ("단위 설명", _link(v("url"))))
    else:                                                  # 본토 SGMC
        rows = (("주", v("state")), ("기호", v("orig_label")), ("암상", v("generalize")),
                ("단위 설명", _link(v("url"))), ("원도", _link(v("src_url"))))
    return {k: x for k, x in rows if x}


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "mrdata", "tag": "USGS", "title": "미국 지질조사국", "relay": True, "projected": True, "globe": True},
]
