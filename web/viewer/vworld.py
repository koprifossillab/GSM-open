"""VWorld 로 나가는 문 — 주소·장소 검색, 좌표→주소, "지질 참고" 레이어.

`kigam.py` 와 나란한 **두 번째 문**이다. 상류마다 문을 하나씩 둔다 — 주소가
바뀌거나 창구가 닫힐 때 고칠 자리를 하나로 묶으려는 것이다. KIGAM 은 전혀
타지 않는다.

배경지도(WMTS)는 여기를 거치지 않는다. 그것은 브라우저가 곧장 부른다
(`settings.VWORLD_KEY` 의 설명). 곧장 닿지 못할 때만 — 사내 VPN — 거친다 (아래 WMTS, 033).
여기로 오는 것은 사람이 검색 칸에 넣고
누른 한 번, 팝업을 연 한 번, 그리고 "지질 참고" 레이어의 타일·속성·단층
모양이다 (아래 WMS·WFS, devlog 020).

**KIGAM 의 지도 화면(TerriaMap)은 Bing 지오코더를 쓴다.** 한국 주소에
약해서 검색이 자주 빗나간다. VWorld 는 국토지리정보원 자료라 도로명·지번
·행정구역이 정확하다 (devlog 009).
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.vworld.kr/req/search"
ADDRESS_URL = "https://api.vworld.kr/req/address"
TIMEOUT = 8

#: 검색 한 번에 묻는 갈래. 넷을 한꺼번에 묻는다 — 사람이 넣은 글자가
#: 주소인지 장소인지 행정구역인지 우리가 가르지 않는다. 가르려 들면 틀린다.
KINDS = (
    ("district", {"type": "district", "category": "L4"}, 3),   # 읍면동
    ("district", {"type": "district", "category": "L2"}, 2),   # 시군구
    ("road", {"type": "address", "category": "road"}, 4),
    ("parcel", {"type": "address", "category": "parcel"}, 4),
    ("place", {"type": "place"}, 6),
)

_KEY_RE = re.compile(r"(key=)[^&\s]*", re.I)


class VWorldError(RuntimeError):
    """VWorld 가 답하지 않거나 알아볼 수 없는 것을 줬을 때."""


def enabled() -> bool:
    return bool(settings.VWORLD_KEY)


def _get(url: str, params: dict) -> dict:
    sent = dict(params, key=settings.VWORLD_KEY, format="json", crs="EPSG:4326")
    try:
        # KOPRI 망이 TLS 를 가로챈다 — kigam.py 와 같은 CA 꾸러미를 쓴다
        r = requests.get(url, params=sent, timeout=TIMEOUT,
                         verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        reason = _KEY_RE.sub(r"\1…", str(exc))        # 예외 문구에 URL 이 실려 온다
        raise VWorldError(f"VWorld 에 닿지 못했다: {reason}") from exc
    log.info("VWorld %s -> %s", _KEY_RE.sub(r"\1…", r.url), r.status_code)
    try:
        body = r.json()["response"]
    except (ValueError, KeyError) as exc:
        raise VWorldError(f"VWorld 가 알아볼 수 없는 것을 줬다 (status={r.status_code})") from exc
    status = body.get("status")
    if status == "NOT_FOUND":
        return {}
    if status != "OK":
        error = (body.get("error") or {}).get("text", status)
        raise VWorldError(f"VWorld 가 거절했다: {error}")
    return body.get("result") or {}


def _point(item) -> tuple:
    p = item.get("point") or {}
    return float(p["y"]), float(p["x"])


def _one_kind(kind, extra, size, query):
    result = _get(SEARCH_URL, dict(extra, service="search", request="search",
                                   version="2.0", size=size, page=1, query=query))
    out = []
    for item in result.get("items") or []:
        try:
            lat, lon = _point(item)
        except (KeyError, TypeError, ValueError):
            continue
        addr = item.get("address") or {}
        if kind == "place":
            title = item.get("title") or ""
            sub = addr.get("road") or addr.get("parcel") or ""
        elif kind == "district":
            title, sub = item.get("title") or "", ""
        else:
            title = addr.get(kind) or item.get("title") or ""
            # 도로명이면 지번을, 지번이면 도로명을 곁에 적는다
            sub = addr.get("parcel" if kind == "road" else "road") or ""
        if title:
            out.append({"kind": kind, "title": title, "sub": sub, "lat": lat, "lon": lon})
    return out


def search(query: str) -> list:
    """주소·장소·행정구역을 한꺼번에 찾는다. 행정구역 → 주소 → 장소 차례.

    한 갈래가 실패해도 나머지는 돌려준다. 다 실패하면 `VWorldError`.
    """
    query = (query or "").strip()
    if not query:
        return []
    with ThreadPoolExecutor(max_workers=len(KINDS)) as pool:
        futures = [pool.submit(_one_kind, kind, extra, size, query)
                   for kind, extra, size in KINDS]
    results, errors = [], []
    for f in futures:
        try:
            results.extend(f.result())
        except VWorldError as exc:
            errors.append(exc)
    # 스레드 안에서 세지 않는다 — DB 연결이 스레드마다 생긴다
    usage.record("vworld", ok=True, count=len(futures) - len(errors))
    if errors:
        usage.record("vworld", ok=False, count=len(errors))
    if errors and len(errors) == len(futures):
        raise errors[0]
    # 이름이 같으면 하나로 친다. 한 번지에 건물이 여럿이면(연구원 캠퍼스처럼)
    # 같은 도로명이 건물마다 따로 온다 — 사람에게는 한 곳이다.
    seen, out = set(), []
    for row in results:
        if row["title"] not in seen:
            seen.add(row["title"])
            out.append(row)
    # 넣은 말로 **끝나는** 행정구역을 맨 앞에 둔다. "유성구" 를 찾았는데
    # 유성구의 동들이 유성구보다 먼저 뜨면 안 된다.
    out.sort(key=lambda r: 0 if r["kind"] == "district" and r["title"].endswith(query) else 1)
    return out


def reverse(lat: float, lon: float) -> dict:
    """좌표 → `{"road": "...", "parcel": "..."}`. 없으면 빈 칸이다.

    바다 한가운데처럼 주소가 없는 자리는 VWorld 가 `NOT_FOUND` 를 준다.
    """
    try:
        out = _reverse(lat, lon)
    except VWorldError:
        usage.record("vworld", ok=False)
        raise
    usage.record("vworld", ok=True)
    return out


def _reverse(lat: float, lon: float) -> dict:
    """`reverse` 의 속 — 세지 않는다. 스레드 안에서 부르는 `point_facts` 가 쓴다."""
    result = _get(ADDRESS_URL, {"service": "address", "request": "getAddress",
                                "type": "both", "point": f"{lon},{lat}"})
    out = {"road": "", "parcel": ""}
    rows = result if isinstance(result, list) else []
    for row in rows:
        kind = (row.get("type") or "").lower()
        if kind in out and not out[kind]:
            out[kind] = row.get("text") or ""
    return out


# ── 점 하나로 묻는 것 — 시료 지점에 붙인다 (074) ────────────────────────
#
# 데이터 API 가 `geomFilter=POINT(경도 위도)` + `buffer=미터` 를 받는다(004). 한 점에 넷을 묻는다 —
# 좌표→주소(위 `reverse`), 읍면동, 가장 가까운 단층, 둘레 국가지명. 단층·지명은 이름 대신 거리가 쓸모라
# 기하를 받아 우리가 잰다(평면 근사 — 20 km 안이라 1% 안쪽이다).
#
# **함정**: 데이터 API 의 자료 이름이 WMS 레이어명과 다르다 — `LT_C_ADEMD` 는 `INVALID_RANGE` 로 멈추고
# `LT_C_ADEMD_INFO` 라야 돈다(004).

DATA_URL = "https://api.vworld.kr/req/data"
#: 이 안에서 단층을 찾는다. 넘으면 "없다" 가 아니라 "20 km 안에 없다" 다
FAULT_BUFFER = 20000
#: 이 안에서 국가지명을 찾는다. 1 km 로는 도심에서 빈 곳이 많았다(2026-09-30)
PLACE_BUFFER = 2000
#: VWorld 가 아는 땅 — 대한민국 둘레. 밖이면 묻지 않는다(바다·북한·해외는 NOT_FOUND 뿐이다)
KOREA_BOX = (124.0, 33.0, 132.0, 38.7)


def in_korea(lat: float, lon: float) -> bool:
    w, s, e, n = KOREA_BOX
    return w <= lon <= e and s <= lat <= n


def _features(data: str, lat: float, lon: float, *, buffer=None, geometry=False, size=10) -> list:
    params = {"service": "data", "request": "GetFeature", "data": data, "size": size, "page": 1,
              "geometry": "true" if geometry else "false", "attribute": "true",
              "geomFilter": f"POINT({lon} {lat})"}
    if buffer:
        params["buffer"] = buffer
    result = _get(DATA_URL, params)
    return ((result or {}).get("featureCollection") or {}).get("features") or []


def _meters(lat0: float, lon0: float, lat: float, lon: float) -> tuple:
    """(lat0, lon0) 를 원점으로 한 평면 근사 (동, 북) 미터."""
    import math
    k = 111320.0
    return (lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * 110540.0


def _to_segment(p, a, b) -> float:
    import math
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _lines(geometry) -> list:
    kind, coords = (geometry or {}).get("type"), (geometry or {}).get("coordinates") or []
    if kind == "LineString":
        return [coords]
    if kind == "MultiLineString":
        return coords
    return []


def nearest_fault_m(lat: float, lon: float, features: list):
    """단층 선들 가운데 가장 가까운 것까지의 거리(m). 없으면 None."""
    best = None
    for f in features:
        for line in _lines(f.get("geometry")):
            pts = [_meters(lat, lon, y, x) for x, y in line]
            for a, b in zip(pts, pts[1:] or pts):
                d = _to_segment((0.0, 0.0), a, b)
                best = d if best is None or d < best else best
    return best


def nearest_place(lat: float, lon: float, features: list):
    """국가지명 점들 가운데 가장 가까운 것 (이름, 거리 m). 없으면 None."""
    import math
    best = None
    for f in features:
        name = ((f.get("properties") or {}).get("land_kpyo") or "").strip()
        coords = ((f.get("geometry") or {}).get("coordinates")) or []
        if coords and isinstance(coords[0], list):          # MultiPoint
            coords = coords[0]
        if not name or len(coords) < 2:
            continue
        d = math.hypot(*_meters(lat, lon, coords[1], coords[0]))
        if best is None or d < best[1]:
            best = (name, d)
    return best


def point_facts(lat: float, lon: float) -> dict:
    """한 점의 둘레 — `{"road", "parcel", "emd", "fault_m", "place", "place_m"}`. 모르는 것은 빠진다.

    넷을 한꺼번에 묻는다(`search` 와 같다). 하나가 실패해도 나머지는 돌려주고, 다 실패하면 `VWorldError`."""
    jobs = {
        "address": lambda: _reverse(lat, lon),
        "emd": lambda: _features("LT_C_ADEMD_INFO", lat, lon, size=1),
        "fault": lambda: _features("LT_L_GIMSFAULT", lat, lon, buffer=FAULT_BUFFER, geometry=True, size=100),
        "place": lambda: _features("LT_P_NSNMSSITENM", lat, lon, buffer=PLACE_BUFFER, geometry=True, size=50),
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
    out, errors = {}, []
    for name, future in futures.items():
        try:
            got = future.result()
        except VWorldError as exc:
            errors.append(exc)
            continue
        if name == "address":
            out.update({k: v for k, v in got.items() if v})
        elif name == "emd" and got:
            full = (got[0].get("properties") or {}).get("full_nm")
            if full:
                out["emd"] = full
        elif name == "fault":
            d = nearest_fault_m(lat, lon, got)
            if d is not None:
                out["fault_m"] = round(d)
        elif name == "place":
            hit = nearest_place(lat, lon, got)
            if hit:
                out["place"], out["place_m"] = hit[0], round(hit[1])
    # 스레드 안에서 세지 않는다 — DB 연결이 스레드마다 생긴다(`search` 와 같다)
    if len(errors) < len(jobs):
        usage.record("vworld", ok=True, count=len(jobs) - len(errors))
    if errors:
        usage.record("vworld", ok=False, count=len(errors))
    if errors and len(errors) == len(jobs):
        raise errors[0]
    return out


# ── WMS·WFS — "지질 참고" 레이어군 (devlog 020) ─────────────────────────
#
# 주소 검색과 달리 여기로는 **타일이** 온다. 그래서 KIGAM 타일과 같은 캐시를
# 타고(`views.wms`), 열쇠는 여기서만 붙는다 — 브라우저는 `/GSM/wms/` 만 안다.
#
# 배경지도(WMTS)는 브라우저가 곧장 부르지만 WMS 는 중계한다. `GetFeatureInfo`
# 와 WFS 가 CORS 로 막혀 어차피 중계가 필요하고(004), 중계하면 열쇠가 안
# 나가고 캐시도 탄다.
#
# **도메인(`domain=`)을 붙이지 않는다.** 2026-09-27 에 쏴 보니 서버에서 부르는
# WMS·WFS 는 도메인이 있든 없든 같은 것을 줬다 — 주소 검색(`_get`)도 붙이지
# 않고 돈다. 도메인 검사는 브라우저가 부르는 JS API 쪽 일이다.

WMS_URL = "https://api.vworld.kr/req/wms"
WFS_URL = "https://api.vworld.kr/req/wfs"
IMAGE_URL = "https://api.vworld.kr/req/image"

#: WFS 한 번에 받는 모양 수의 상한. 1° 칸 하나에 단층이 많아야 수백 개다
#: (대전 둘레 1° 칸이 167 개). 이만큼 차면 잘린 것이라 로그를 남긴다.
MAX_FEATURES = 1000


def _redact(text: str) -> str:
    return _KEY_RE.sub(r"\1…", text or "")


def _raw(url: str, params: dict, timeout=None):
    """열쇠를 붙여 부르고 응답을 그대로 돌려준다. 세는 것도 여기서 한다."""
    if not enabled():
        raise VWorldError("VWorld 열쇠가 없다")
    left = usage.paused()
    if left:
        raise VWorldError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    sent = dict(params, key=settings.VWORLD_KEY)
    try:
        r = requests.get(url, params=sent, timeout=timeout or settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("vworld", ok=False)
        raise VWorldError(f"VWorld 에 닿지 못했다: {_redact(str(exc))}") from exc
    log.info("VWorld %s -> %s", _redact(r.url), r.status_code)
    usage.record("vworld", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms_params(params: dict) -> dict:
    """VWorld WMS 는 레이어명이 **소문자라야** 돈다 (대문자면 예외 XML)."""
    out = dict(params, service="WMS", version="1.3.0")
    for key in ("layers", "query_layers"):
        if out.get(key):
            out[key] = str(out[key]).lower()
    out.setdefault("styles", "")
    # WMS 1.1.1 로 온 것(`srs`)을 1.3.0 의 `crs` 로 옮겨 적는다
    if "srs" in out and "crs" not in out:
        out["crs"] = out.pop("srs")
    return out


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 `VWorldError`.

    **빈 타일도 그림이다.** VWorld 는 축척 밖이거나 자료가 없는 자리에 투명한
    PNG 를 준다 — 그것도 그대로 캐시에 둔다. 다시 물어도 같은 것이 온다.
    """
    r = _raw(WMS_URL, _wms_params(dict(params, request="GetMap")))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise VWorldError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` → GeoJSON FeatureCollection (KIGAM 과 같은 꼴).

    **시간 제한을 찾기와 같게 짧게 둔다(`TIMEOUT`).** 팝업은 켠 레이어의 속성이
    다 와야 한 번에 뜬다 — VWorld 하나가 늦으면 지질도 속성까지 20 초를 기다린다
    (020 에서 한 번 보았다). 이틀 동안 82 번에 실패 0 이라 잦지는 않지만, 늦을 때
    지질 참고 한 칸을 버리는 편이 팝업 전체를 붙잡는 것보다 낫다."""
    r = _raw(WMS_URL, _wms_params(dict(params, request="GetFeatureInfo",
                                       info_format="application/json")), timeout=TIMEOUT)
    if r.status_code != 200:
        raise VWorldError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return r.json()
    except ValueError as exc:
        raise VWorldError("속성이 JSON 이 아니다") from exc


def get_legend(layer: str):
    """범례. WMS 의 `GetLegendGraphic` 이 아니라 VWorld 의 이미지 API 로 받는다."""
    layer = layer.lower()
    r = _raw(IMAGE_URL, {"service": "image", "request": "GetLegendGraphic",
                         "format": "png", "type": "ALL", "layer": layer, "style": layer})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise VWorldError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, ctype


def get_features(typename: str, west: float, south: float, east: float, north: float) -> dict:
    """WFS `GetFeature` — 위경도 범위 안의 모양을 GeoJSON(EPSG:4326)으로.

    **WFS 1.1.0 의 bbox 는 위도가 먼저다** (`남,서,북,동,EPSG:4326`). 돌아오는
    좌표는 경도가 먼저다 — GeoJSON 의 차례다. 2026-09-27 에 대전 둘레로 확인했다.

    기하를 **남긴다** — 이것을 그리려고 받는 것이다. 브라우저가 쓰지 않는
    곁가지(`bbox`·`geometry_name`)만 뗀다.
    """
    r = _raw(WFS_URL, {
        "service": "WFS", "version": "1.1.0", "request": "GetFeature",
        "typename": typename.lower(), "srsname": "EPSG:4326",
        "bbox": f"{south},{west},{north},{east},EPSG:4326",
        "output": "application/json", "maxfeatures": str(MAX_FEATURES),
    })
    if r.status_code != 200:
        raise VWorldError(f"모양을 받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise VWorldError("모양이 JSON 이 아니다") from exc
    features = []
    for f in data.get("features") or []:
        if not f.get("geometry"):
            continue
        features.append({"type": "Feature", "id": f.get("id"),
                         "geometry": f["geometry"], "properties": f.get("properties") or {}})
    if len(features) >= MAX_FEATURES:
        log.warning("VWorld WFS %s 가 %d 개에서 잘렸다 (%s,%s,%s,%s)",
                    typename, MAX_FEATURES, west, south, east, north)
    return {"type": "FeatureCollection", "features": features}


def thin(data: dict, step: float) -> dict:
    """선의 점을 솎는다 — 앞에 남긴 점에서 `step`(도) 안의 점은 버리고 끝점은 둔다. 좌표는 소수 여섯째 자리
    (10 cm 남짓)까지. 지하수 등수심선은 5 m 마다 점이 있어 화면이 그릴 수 있는 것보다 촘촘하다 (077).
    모양을 줄이는 도구(shapely)는 들이지 않는다 — 이것으로 넉넉하다."""
    def line(pts):
        if len(pts) < 3:
            return [[round(x, 6), round(y, 6)] for x, y, *_ in pts]
        kept = [pts[0]]
        for p in pts[1:-1]:
            if abs(p[0] - kept[-1][0]) >= step or abs(p[1] - kept[-1][1]) >= step:
                kept.append(p)
        kept.append(pts[-1])
        return [[round(x, 6), round(y, 6)] for x, y, *_ in kept]

    out = []
    for f in data.get("features") or []:
        geom = f.get("geometry") or {}
        if geom.get("type") == "LineString":
            geom = {"type": "LineString", "coordinates": line(geom["coordinates"])}
        elif geom.get("type") == "MultiLineString":
            geom = {"type": "MultiLineString", "coordinates": [line(part) for part in geom["coordinates"]]}
        out.append(dict(f, geometry=geom))
    return dict(data, features=out)


# ── 팝업에 보일 이름 ────────────────────────────────────────────────
#
# VWorld 의 열 이름은 영문 약어다(`riv_nm`·`sig_kor_nm`). 사람이 읽을 것에만
# 한국어 이름을 붙여 **그것만** 보인다 — 나머지는 코드(`*_cd`·`mnum`·`cat_cde`)
# 라 팝업을 길게 할 뿐이다. 표에 든 열이 하나도 없으면 받은 것을 그대로 둔다.
# 영어는 `i18n.PROP_EN` 에 있다. 2026-09-27 에 레이어마다 한 자리씩 눌러
# 모았다 (devlog 020).

FRIENDLY = {
    # 단층 — 벡터(WFS)로 받는다. `legend` 의 뜻은 VWorld 가 밝히지 않았다
    "legend": "구분",
    "leng": "길이 (m)",
    # 수문지질단위 · 지질구조선
    "info": "수문지질단위",
    "sig_nam": "시군구",
    # 온천지구
    "uname": "지구",
    "sido_name": "시도",
    "sigg_name": "시군구",
    # 등산로 — 길이·걸리는 시간 열도 있지만 단위를 밝히지 않아 싣지 않는다
    "mntn_nm": "산",
    "pmntn_nm": "구간",
    "sec_grad": "난이도",
    # 국가지명
    "land_kpyo": "지명",
    # 하천망
    "riv_nm": "하천명",
    "riv_level": "하천 등급",
    # 행정경계
    "full_nm": "행정구역",
    "ctp_kor_nm": "시도",
    "sig_kor_nm": "시군구",
    "emd_kor_nm": "읍면동",
    "li_kor_nm": "리",
    # 보호구역·재해 지구 — 용도지역 꼴(`ucode`·`uname`)이 같다. 2026-09-30 에 모았다
    # (wetherilli 084). `uname` 은 위의 "지구" 가 받는다
    "remark": "비고",
    "alias": "세부",
    "dyear": "지정 연도",
    "park_name": "공원",
    "name": "이름",
    # 해양보호구역
    "mpa_nam": "보호구역",
    "gos_num": "고시",
    "gos_dat": "고시일",
    "law": "근거 법",
    "mng_org": "관리 기관",
    "loc": "위치",
    "ara_siz": "면적 (km²)",
    # 공역 — `*_lbl_1` 이 이름, `_2`·`_3` 이 윗·아랫 고도다. 글꼴이 섞인 열(`prohibited`)은 뺀다
    "prh_lbl_1": "공역",
    "res_lbl_1": "공역",
    "dng_lbl_1": "공역",
    "uac_lbl_1": "공역",
    "ctr_lbl_1": "공역",
    "prh_lbl_2": "상한 고도",
    "res_lbl_2": "상한 고도",
    "dng_lbl_2": "상한 고도",
    "uac_lbl_2": "상한 고도",
    "prh_lbl_3": "하한 고도",
    "res_lbl_3": "하한 고도",
    "dng_lbl_3": "하한 고도",
    "uac_lbl_3": "하한 고도",
    # 유역
    "bbsnnm": "대권역",
    "mbsnnm": "중권역",
    "sbsnnm": "표준유역",
}


#: 레이어마다 뜻이 다른 열. 지하수 등치선은 `legend` 에 **선의 값**을 싣는다
#: (단층의 `legend` 는 구분 1·2 다). `info` 는 모든 선이 1 이라 싣지 않는다.
#: 2026-09-28 에 WFS 로 확인했다 — 등수위 10~430, 전기전도도 50~1400 (대전·청주 둘레).
LAYER_FRIENDLY = {
    "lt_l_gimspoten": {"legend": "지하수위 표고 (m)", "info": None},
    "lt_l_gimsec": {"legend": "전기전도도 (µS/cm)"},
    "lt_l_gimsdepth": {"legend": "지하수 등수심 (m)", "info": None},
    # 정밀토양도 넷은 모두 `label` 에 값을 싣는다 — 레이어마다 뜻이 다르다
    "lt_c_asitsoildep": {"label": "유효토심 (cm)"},
    "lt_c_asitsurston": {"label": "자갈 함량 (%)"},
    "lt_c_asitdeepsoil": {"label": "심토 토성"},
    "lt_c_asitsoildra": {"label": "배수 등급"},
    # 산림입지도의 `name` 은 산림토양형이다
    "lt_c_fsdifrsts": {"name": "산림토양", "toyanghyun": "토양형 기호"},
}


def friendly(props: dict, layer: str = "") -> dict:
    """VWorld 의 열 → 팝업에 보일 `{한국어 이름: 값}`. 받은 차례를 지킨다."""
    table = dict(FRIENDLY, **LAYER_FRIENDLY.get(layer.lower(), {}))
    out = {}
    for key, value in props.items():
        name = table.get(str(key).lower())
        if not name or value in (None, "", "null"):
            continue
        if name == "지정 연도" and str(value) == "0000":    # 모르는 해를 0000 으로 적는다
            continue
        if name == "길이 (m)":
            try:
                value = f"{float(value):,.0f}"
            except (TypeError, ValueError):
                pass
        out.setdefault(name, value)
    return out or dict(props)


# ── WMTS 배경지도 — 브라우저가 곧장 못 받을 때만 (devlog 033) ──────────
#
# 배경지도는 브라우저가 `api.vworld.kr` 에서 곧장 받는다(003). 그런데 **사내
# VPN 이 그 연결을 끊는다**(`ERR_CONNECTION_RESET`, 2026-09-29) — VPN 은 사내
# 주소만 통과시키고, 이 서버는 VWorld 에 닿는다. 그래서 브라우저가 곧장 받아
# 보다가 끊기면 **그때만** 여기를 거친다. 사내에서는 여전히 여기를 타지 않는다.
#
# 열쇠가 URL 의 **경로에** 든다(`…/1.0.0/<열쇠>/Base/…`). 로그에는 레이어·자리만
# 적는다. 받은 것을 디스크 캐시에 담지 않는다 — 곧장 받을 때도 우리 것이 아니고,
# 브라우저가 들고 있으면(`Cache-Control`) 된다.

WMTS_URL = "https://api.vworld.kr/req/wmts/1.0.0/{key}/{layer}/{z}/{y}/{x}.{ext}"

#: 중계하는 레이어와 그 확장자. 브라우저가 쓰는 것뿐이다 (`map.js`·`map3d.js`)
WMTS_LAYERS = {"Base": "png", "white": "png", "midnight": "png", "Hybrid": "png", "Satellite": "jpeg"}

#: 테마 위성영상 — 남극 세종·장보고기지 둘레(2013). 캐퍼빌리티의 `ResourceURL` 이 이 경로다.
#: **자리 차례가 z/x/y 로 배경지도(z/y/x)와 반대다**(004). 중계 주소는 배경지도와 같은
#: `vworld/<레이어>/<z>/<y>/<x>` 로 받고 여기서 바꿔 부른다 (wetherilli 093)
WMTS_THEMES = {
    "AntarcticaSejong": "Satellite/themes/cities/2013/AntarcticaSejong",
    "AntarcticaJangbogo": "Satellite/themes/cities/2013/AntarcticaJangbogo",
}
WMTS_THEME_URL = "https://api.vworld.kr/req/wmts/1.0.0/{key}/{path}/{z}/{x}/{y}.png"


def knows_wmts(layer: str) -> bool:
    return layer in WMTS_LAYERS or layer in WMTS_THEMES


def get_wmts_tile(layer: str, z: int, y: int, x: int):
    """배경지도 타일 한 장. (바이트, content-type). 자료가 없는 자리는 `None`.

    **자료 밖은 200 에 XML 이 온다**(`Base/15/1000/1000` 이 436 바이트의 XML).
    그것은 빈 자리라 `None` 을 돌려주고, 부르는 쪽이 투명 타일을 낸다."""
    if not enabled():
        raise VWorldError("VWorld 열쇠가 없다")
    left = usage.paused()
    if left:
        raise VWorldError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    if layer in WMTS_THEMES:
        url = WMTS_THEME_URL.format(key=settings.VWORLD_KEY, path=WMTS_THEMES[layer], z=z, x=x, y=y)
    else:
        url = WMTS_URL.format(key=settings.VWORLD_KEY, layer=layer, z=z, y=y, x=x,
                              ext=WMTS_LAYERS[layer])
    where = f"{layer}/{z}/{y}/{x}"
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("vworld", ok=False)
        # 예외 문구에 URL 이 실려 온다 — 경로의 열쇠를 지운다
        raise VWorldError(f"VWorld 에 닿지 못했다 ({where}): "
                          f"{str(exc).replace(settings.VWORLD_KEY, '…')}") from exc
    log.info("VWorld WMTS %s -> %s", where, r.status_code)
    ctype = r.headers.get("content-type", "")
    usage.record("vworld", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    if r.status_code == 200 and ctype.startswith("image/"):
        return r.content, ctype
    if r.status_code == 200:
        return None
    raise VWorldError(f"배경지도 타일을 받지 못했다 ({where}, status={r.status_code})")
