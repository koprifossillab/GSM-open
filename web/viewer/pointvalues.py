"""점묶음의 점마다 우리 디스크의 파일에서 읽는 값 — CSV 로 내려받을 때 열로 붙인다 (wetherilli 190).

지구 점에는 남극 GeoMAP 지질 단위(60°S 남쪽)·지각 두께(CRUST 2.0)·가장 가까운 PBDB 화석 산지를, 달·화성·수성 점에는
그 몸의 원도·지질도 단위를 붙인다. 모두 우리 파일이라 상류를 타지 않는다. 열 이름은 한국어이고 영어판은 `PROP_EN` 으로 옮긴다.
문이 아니다.
"""
import logging
import math
import sqlite3

from . import crust, fossils, geomap, i18n, marsmap, mercurymap, moonmap

#: 몸마다 붙일 수 있는 값의 갈래. 차례가 열의 차례다
EXTRAS = {"earth": ("geomap", "crust", "fossil"), "moon": ("unit",), "mars": ("unit",), "mercury": ("unit",)}
#: 붙일 값을 읽는 점의 상한 — 넘으면 값 없이 내려받는다. 운영 파일로 3 000 점을 재니 지구 3 초·수성 4 초·화성 11 초·달 19 초였다
#: (2026-10-04). gunicorn 은 60 초에 워커가 셋이라 달이 한 워커를 오래 붙잡지 않게 2 000 으로 둔다
LIMIT = 2000
#: 가장 가까운 화석 산지를 찾는 둘레(°). 이보다 멀면 비운다
FOSSIL_RADIUS = 1.0
#: GeoMAP 단위를 읽는 위도 — 남극 대륙과 둘레 섬
GEOMAP_NORTH = -60.0
EARTH_RADIUS_KM = 6371.0
#: 파일이 깨졌거나 읽다 막힌 갈래 — 그 점의 그 값만 비우고 나머지는 붙인다
ERRORS = (OSError, ValueError, sqlite3.Error, geomap.GeomapError, moonmap.MoonMapError, marsmap.MarsMapError,
          mercurymap.MercuryMapError)

log = logging.getLogger(__name__)

#: 갈래 → 열 이름들
COLUMNS = {
    "geomap": ("지질 단위(GeoMAP)", "지질기호(GeoMAP)", "연대 Ma(GeoMAP)"),
    "crust": ("지각 두께 km(CRUST 2.0)",),
    "fossil": ("가까운 화석 산지(PBDB)", "산지 번호(PBDB)", "산지의 시대(PBDB)", "산지까지 km(PBDB)"),
    "moon": ("지질 단위(원도)", "단위 이름(원도)", "시대(원도)", "원도"),
    "mars": ("지질 단위(화성 지질도)", "단위 이름(화성 지질도)", "시대(화성 지질도)", "화성 지질도"),
    "mercury": ("지질 단위(수성 지질도)", "단위 무리(수성 지질도)", "도폭(수성 지질도)"),
}


def kinds(body: str, wanted=None) -> list:
    """몸에 붙일 갈래 — `wanted`(갈래 이름들)가 있으면 그 가운데 몸에 맞는 것만. 파일이 없는 갈래는 뺀다."""
    out = [k for k in EXTRAS.get(body, ()) if wanted is None or k in wanted]
    return [k for k in out if _available(body, k)]


def _available(body: str, kind: str) -> bool:
    if kind == "geomap":
        return geomap.available()
    if kind == "crust":
        return crust.grid() is not None
    if kind == "fossil":
        return fossils.available()
    return {"moon": moonmap, "mars": marsmap, "mercury": mercurymap}[body].available()


def columns(body: str, kinds_: list) -> list:
    return [c for k in kinds_ for c in COLUMNS[body if k == "unit" else k]]


def km_between(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def values(body: str, kinds_: list, lat: float, lon: float, lang: str = "ko") -> dict:
    """한 점의 값 — `{열 이름: 값}`. 읽지 못한 것은 빠진다."""
    out = {}
    for kind in kinds_:
        try:
            out.update(_read(body, kind, lat, lon, lang))
        except ERRORS as exc:
            log.warning("점의 값을 읽지 못했다 (%s %s, %.4f %.4f): %s", body, kind, lat, lon, exc)
    return out


def _read(body, kind, lat, lon, lang) -> dict:
    if kind == "geomap":
        return _geomap(lat, lon)
    if kind == "crust":
        km = crust.at(lon, lat)
        return {} if km is None else {COLUMNS["crust"][0]: km}
    if kind == "fossil":
        return _fossil(lat, lon, lang)
    return _unit(body, lat, lon, lang)


def _geomap(lat, lon) -> dict:
    if lat > GEOMAP_NORTH:
        return {}
    x, y = geomap.lonlat_to_3031(lon, lat)
    hits = geomap.query("units", x, y, 1.0, limit=1)
    if not hits:
        return {}
    props = hits[0]["properties"]
    names = COLUMNS["geomap"]
    return {k: v for k, v in ((names[0], props.get("지질 단위")), (names[1], props.get("지질기호")),
                              (names[2], props.get("연대 (Ma)"))) if v not in (None, "")}


def _fossil(lat, lon, lang) -> dict:
    hits = fossils.near(0.0, lon, lat, FOSSIL_RADIUS, limit=1)
    if not hits:
        return {}
    row, _ = hits[0]
    span = row["early"] + (f" – {row['late']}" if row["late"] and row["late"] != row["early"] else "")
    names = COLUMNS["fossil"]
    return {names[0]: row["name"], names[1]: row["no"], names[2]: i18n.age_ko(span) if lang == "ko" else span,
            names[3]: round(km_between(lon, lat, row["lon"], row["lat"]), 1)}


def _unit(body, lat, lon, lang) -> dict:
    names = COLUMNS[body]
    if body == "moon":
        hit = moonmap.identify(lon, lat)
        if not hit:
            return {}
        epoch = hit["epoch"] if lang == "en" else moonmap.epoch_ko(hit["epoch"])
        got = (hit["unit"], hit["name"], epoch, hit["citation"])
    elif body == "mars":
        hit = marsmap.identify(lon, lat)
        if not hit:
            return {}
        got = (hit["unit"], hit["name"], hit["age"], f"{hit['map']} · {hit['citation']}")
    else:
        hit = mercurymap.identify(lon, lat)
        if not hit:
            return {}
        got = (hit["unit"], hit["group"], hit["quad"])
    return {k: v for k, v in zip(names, got) if v not in (None, "")}
