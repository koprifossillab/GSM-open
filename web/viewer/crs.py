"""우리나라에서 쓰는 평면 좌표계 <-> 위경도. import 는 math 뿐이다.

현장 자료가 TM(중부원점 등)으로 찍혀 오는 일이 흔하다. 옛 시추·지질 자료는
Bessel 타원체의 옛 중부원점이다. 그것을 위경도로 바꿔 올리고, 좌표 칸에서도
받으려고 둔다. **pyproj 를 들이지 않는다** — 웹 이미지가 수십 MB 불어나는데
필요한 것은 횡메르카토르 하나와 옛 측지계 옮기기 하나뿐이다 (devlog 013).

- 횡메르카토르: Krüger 급수 (n 의 6 차). 원점에서 수백 km 까지 mm 안쪽이다
- Bessel → GRS80: 7 변수 헬머트 변환 (국토지리정보원이 쓰는 값, EPSG:5174
  의 towgs84 와 같다). 1 m 안팎이다 — 옛 자료 자체가 그보다 거칠다

`test_crs` 가 pyproj 로 뽑아 둔 값과 견준다.
"""
import functools
import math

GRS80 = (6378137.0, 1 / 298.257222101)
BESSEL = (6377397.155, 1 / 299.1528128)
#: Bessel(한국 옛 측지계) → WGS84/GRS80. 이동(m)·회전(초)·축척(ppm)
TOWGS84_KOREA = (-115.80, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43)

#: 고를 수 있는 좌표계. (이름, 타원체, 원점 위도, 원점 경도, 축척, 동가산, 북가산, 옛 측지계?)
SYSTEMS = {
    "4326": ("위경도 (WGS84)", None, 0, 0, 0, 0, 0, False),
    "5186": ("중부원점 (GRS80)", GRS80, 38, 127, 1.0, 200000, 600000, False),
    "5185": ("서부원점 (GRS80)", GRS80, 38, 125, 1.0, 200000, 600000, False),
    "5187": ("동부원점 (GRS80)", GRS80, 38, 129, 1.0, 200000, 600000, False),
    "5188": ("동해원점 (GRS80)", GRS80, 38, 131, 1.0, 200000, 600000, False),
    "5179": ("UTM-K (GRS80)", GRS80, 38, 127.5, 0.9996, 1000000, 2000000, False),
    "32652": ("UTM 52N (WGS84)", GRS80, 0, 129, 0.9996, 500000, 0, False),
    "5174": ("옛 중부원점 (Bessel, 보정)", BESSEL, 38, 127.0028902777778, 1.0, 200000, 500000, True),
    "2097": ("옛 중부원점 (Bessel)", BESSEL, 38, 127, 1.0, 200000, 500000, True),
}


def is_planar(code: str) -> bool:
    return code in SYSTEMS and code != "4326"


# ── 횡메르카토르 (Krüger) ────────────────────────────────────────────

@functools.lru_cache(maxsize=8)
def _series(ellipsoid):
    a, f = ellipsoid
    n = f / (2 - f)
    n2, n3, n4, n5, n6 = n ** 2, n ** 3, n ** 4, n ** 5, n ** 6
    A = a / (1 + n) * (1 + n2 / 4 + n4 / 64 + n6 / 256)
    alpha = (
        n / 2 - 2 * n2 / 3 + 5 * n3 / 16 + 41 * n4 / 180 - 127 * n5 / 288 + 7891 * n6 / 37800,
        13 * n2 / 48 - 3 * n3 / 5 + 557 * n4 / 1440 + 281 * n5 / 630 - 1983433 * n6 / 1935360,
        61 * n3 / 240 - 103 * n4 / 140 + 15061 * n5 / 26880 + 167603 * n6 / 181440,
        49561 * n4 / 161280 - 179 * n5 / 168 + 6601661 * n6 / 7257600,
        34729 * n5 / 80640 - 3418889 * n6 / 1995840,
        212378941 * n6 / 319334400,
    )
    beta = (
        n / 2 - 2 * n2 / 3 + 37 * n3 / 96 - n4 / 360 - 81 * n5 / 512 + 96199 * n6 / 604800,
        n2 / 48 + n3 / 15 - 437 * n4 / 1440 + 46 * n5 / 105 - 1118711 * n6 / 3870720,
        17 * n3 / 480 - 37 * n4 / 840 - 209 * n5 / 4480 + 5569 * n6 / 90720,
        4397 * n4 / 161280 - 11 * n5 / 504 - 830251 * n6 / 7257600,
        4583 * n5 / 161280 - 108847 * n6 / 3991680,
        20648693 * n6 / 638668800,
    )
    e = math.sqrt(f * (2 - f))
    return A, alpha, beta, e


def _tm_forward_raw(lat, lon, lon0, ellipsoid):
    """(위도, 경도) → (ξ·A, η·A) — 원점 경선 기준, 축척·가산 전."""
    A, alpha, _, e = _series(ellipsoid)
    phi = math.radians(lat)
    lam = math.radians(lon - lon0)
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi_p = math.atan2(t, math.cos(lam))
    eta_p = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    xi, eta = xi_p, eta_p
    for j, a_j in enumerate(alpha, start=1):
        xi += a_j * math.sin(2 * j * xi_p) * math.cosh(2 * j * eta_p)
        eta += a_j * math.cos(2 * j * xi_p) * math.sinh(2 * j * eta_p)
    return A * xi, A * eta


def _tm_inverse_raw(x_north, y_east, lon0, ellipsoid):
    A, _, beta, e = _series(ellipsoid)
    xi, eta = x_north / A, y_east / A
    xi_p, eta_p = xi, eta
    for j, b_j in enumerate(beta, start=1):
        xi_p -= b_j * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta_p -= b_j * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    # 등각위도 → 측지위도 (뉴턴 반복)
    tau_p = math.tan(chi)
    tau = tau_p
    for _ in range(8):
        sigma = math.sinh(e * math.atanh(e * tau / math.sqrt(1 + tau * tau)))
        tau_i = tau * math.sqrt(1 + sigma * sigma) - sigma * math.sqrt(1 + tau * tau)
        d = (tau_p - tau_i) / math.sqrt(1 + tau_i * tau_i) * (
            1 + (1 - e * e) * tau * tau) / ((1 - e * e) * math.sqrt(1 + tau * tau))
        tau += d
        if abs(d) < 1e-14:
            break
    lat = math.degrees(math.atan(tau))
    lon = lon0 + math.degrees(math.atan2(math.sinh(eta_p), math.cos(xi_p)))
    return lat, lon


def _tm_to_ll(east, north, spec):
    _, ell, lat0, lon0, k0, fe, fn, _ = spec
    x0, _ = _tm_forward_raw(lat0, lon0, lon0, ell)
    return _tm_inverse_raw((north - fn) / k0 + x0, (east - fe) / k0, lon0, ell)


def _ll_to_tm(lat, lon, spec):
    _, ell, lat0, lon0, k0, fe, fn, _ = spec
    x0, _ = _tm_forward_raw(lat0, lon0, lon0, ell)
    x, y = _tm_forward_raw(lat, lon, lon0, ell)
    return fe + k0 * y, fn + k0 * (x - x0)


def utm_to_latlon(zone: int, east: float, north: float):
    """UTM 북반구(ETRS89·WGS84 — 둘은 1 m 안쪽으로 같다) → (위도, 경도).

    고르개(`SYSTEMS`)에 올리지 않는다. 한국 밖 자료를 읽을 때만 쓴다 — 얀마옌
    지질도가 EPSG:25829(UTM 29N)로 온다 (devlog 022). 셈은 위의 TM 그대로다.
    """
    lon0 = zone * 6 - 183
    return _tm_to_ll(east, north, ("", GRS80, 0, lon0, 0.9996, 500000, 0, False))


def latlon_to_utm(zone: int, lat: float, lon: float):
    """(위도, 경도) → UTM 북반구 (동, 북). 시험과 되짚기에 쓴다."""
    lon0 = zone * 6 - 183
    return _ll_to_tm(lat, lon, ("", GRS80, 0, lon0, 0.9996, 500000, 0, False))


# ── 람베르트 정각원추 (표준위선 둘) ─────────────────────────────────────
#
# USGS 의 동아시아 지질도(geo3al)가 이것으로 온다 — 중앙경선 120°E, 표준위선
# 31°N·29°S, 원점 위도 0°, WGS84 (devlog 025). 표준위선이 적도 양쪽에 있어 원뿔이
# 거의 원통이다(n ≈ 0.018). 셈은 Snyder (1987) 의 타원체 식 15-1~15-11 그대로다.
# 이것도 고르개(`SYSTEMS`)에 올리지 않는다 — 한국 좌표계가 아니다.

WGS84 = (6378137.0, 1 / 298.257223563)


def _lcc_t(phi, e):
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - e * s) / (1 + e * s)) ** (e / 2)


def _lcc_m(phi, e2):
    return math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)


@functools.lru_cache(maxsize=8)
def _lcc_constants(lon0, lat1, lat2, lat0, ellipsoid):
    a, f = ellipsoid
    e2 = f * (2 - f)
    e = math.sqrt(e2)
    p1, p2, p0 = (math.radians(v) for v in (lat1, lat2, lat0))
    n = ((math.log(_lcc_m(p1, e2)) - math.log(_lcc_m(p2, e2)))
         / (math.log(_lcc_t(p1, e)) - math.log(_lcc_t(p2, e))))
    big_f = _lcc_m(p1, e2) / (n * _lcc_t(p1, e) ** n)
    return a, e, n, big_f, a * big_f * _lcc_t(p0, e) ** n, math.radians(lon0)


def lcc_to_latlon(east, north, lon0, lat1, lat2, lat0=0.0, fe=0.0, fn=0.0, ellipsoid=WGS84):
    """람베르트 정각원추 (동, 북) → (위도, 경도). 위도는 되풀이로 푼다 (1e-12 rad 까지)."""
    a, e, n, big_f, rho0, lam0 = _lcc_constants(lon0, lat1, lat2, lat0, ellipsoid)
    x, y = east - fe, rho0 - (north - fn)
    rho = math.copysign(math.hypot(x, y), n)
    theta = math.atan2(x, y) if n > 0 else math.atan2(-x, -y)
    t = (rho / (a * big_f)) ** (1 / n)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(15):
        es = e * math.sin(phi)
        nxt = math.pi / 2 - 2 * math.atan(t * ((1 - es) / (1 + es)) ** (e / 2))
        if abs(nxt - phi) < 1e-12:
            phi = nxt
            break
        phi = nxt
    return math.degrees(phi), math.degrees(theta / n + lam0)


def latlon_to_lcc(lat, lon, lon0, lat1, lat2, lat0=0.0, fe=0.0, fn=0.0, ellipsoid=WGS84):
    """(위도, 경도) → 람베르트 정각원추 (동, 북). 시험과 되짚기에 쓴다."""
    a, e, n, big_f, rho0, lam0 = _lcc_constants(lon0, lat1, lat2, lat0, ellipsoid)
    rho = a * big_f * _lcc_t(math.radians(lat), e) ** n
    theta = n * (math.radians(lon) - lam0)
    return fe + rho * math.sin(theta), fn + rho0 - rho * math.cos(theta)


# ── 북극 람베르트 등적 방위도법 (DATED-1 의 빙상 가장자리, wetherilli 104) ──

def _laea_q(phi, e):
    s = math.sin(phi)
    return (1 - e * e) * (s / (1 - e * e * s * s) - math.log((1 - e * s) / (1 + e * s)) / (2 * e))


def laea_north_to_latlon(x, y, lon0=0.0, ellipsoid=WGS84):
    """북극 람베르트 등적 방위도법(타원체) (x, y) → (위도, 경도). Snyder (1987) 24-15–24-19·3-18 — 위도는 수렴 급수다."""
    a, f = ellipsoid
    e2 = f * (2 - f)
    e = math.sqrt(e2)
    qp = _laea_q(math.pi / 2, e)
    beta = math.asin(max(-1.0, min(1.0, (qp - (x * x + y * y) / (a * a)) / qp)))
    phi = (beta + (e2 / 3 + 31 * e2 ** 2 / 180 + 517 * e2 ** 3 / 5040) * math.sin(2 * beta)
           + (23 * e2 ** 2 / 360 + 251 * e2 ** 3 / 3780) * math.sin(4 * beta)
           + (761 * e2 ** 3 / 45360) * math.sin(6 * beta))
    return math.degrees(phi), lon0 + math.degrees(math.atan2(x, -y))


def latlon_to_laea_north(lat, lon, lon0=0.0, ellipsoid=WGS84):
    """(위도, 경도) → 북극 람베르트 등적 방위도법 (x, y). 시험과 되짚기에 쓴다."""
    a, f = ellipsoid
    e = math.sqrt(f * (2 - f))
    rho = a * math.sqrt(max(0.0, _laea_q(math.pi / 2, e) - _laea_q(math.radians(lat), e)))
    lam = math.radians(lon - lon0)
    return rho * math.sin(lam), -rho * math.cos(lam)


# ── 대원을 따라 고르게 (wetherilli 109) ─────────────────────────────

def great_circle_points(vertices, n, radius=6371008.8):
    """꼭짓점 `[(경도, 위도), …]` → 대원을 따라 고르게 `n` 점 `[(경도, 위도, 처음부터의 거리 m), …]`. 꼭짓점 자리에는 꼭
    한 점을 둔다 — 꺾인 곳의 높이가 빠지지 않게. 구로 잰다(평균 반지름 — `ol.sphere` 의 거리와 같다). 달 화면의 것
    (`trek.profile_points`)과 같은 셈이다 — 문은 서로를 타지 않아 여기 한 벌 둔다."""
    def unit(lon, lat):
        lo, la = math.radians(lon), math.radians(lat)
        return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))

    def slerp(a, b, f):
        dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
        omega = math.acos(dot)
        if omega < 1e-12:
            return a
        s = math.sin(omega)
        p, q = math.sin((1 - f) * omega) / s, math.sin(f * omega) / s
        return tuple(p * x + q * y for x, y in zip(a, b))

    def lonlat(v):
        return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))

    units = [unit(lon, lat) for lon, lat in vertices]
    seg = [radius * math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))) for a, b in zip(units, units[1:])]
    total = sum(seg)
    if total <= 0:
        return [(vertices[0][0], vertices[0][1], 0.0)]
    counts = [max(1, round((n - 1) * s / total)) for s in seg]
    out, start = [], 0.0
    for i, (a, b) in enumerate(zip(units, units[1:])):
        for k in range(counts[i]):
            out.append(lonlat(slerp(a, b, k / counts[i])) + (start + seg[i] * k / counts[i],))
        start += seg[i]
    out.append(lonlat(units[-1]) + (total,))
    return out


# ── 옛 측지계 (Bessel ↔ GRS80) ────────────────────────────────────────

def _geodetic_to_ecef(lat, lon, ell, h=0.0):
    a, f = ell
    e2 = f * (2 - f)
    phi, lam = math.radians(lat), math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    return ((N + h) * math.cos(phi) * math.cos(lam),
            (N + h) * math.cos(phi) * math.sin(lam),
            (N * (1 - e2) + h) * math.sin(phi))


def _ecef_to_geodetic(x, y, z, ell):
    a, f = ell
    e2 = f * (2 - f)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(10):
        N = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        lat = math.atan2(z + e2 * N * math.sin(lat), p)
    return math.degrees(lat), math.degrees(lon)


def _helmert(x, y, z, params, inverse=False):
    dx, dy, dz, rx, ry, rz, s = params
    sec = math.pi / 180 / 3600
    rx, ry, rz, s = rx * sec, ry * sec, rz * sec, s * 1e-6
    if inverse:
        dx, dy, dz, rx, ry, rz, s = -dx, -dy, -dz, -rx, -ry, -rz, -s
    # position vector 식 (PROJ 의 towgs84 와 같다)
    return (dx + (1 + s) * (x - rz * y + ry * z),
            dy + (1 + s) * (rz * x + y - rx * z),
            dz + (1 + s) * (-ry * x + rx * y + z))


def _bessel_to_wgs(lat, lon):
    return _ecef_to_geodetic(*_helmert(*_geodetic_to_ecef(lat, lon, BESSEL), TOWGS84_KOREA), GRS80)


def _wgs_to_bessel(lat, lon):
    return _ecef_to_geodetic(*_helmert(*_geodetic_to_ecef(lat, lon, GRS80), TOWGS84_KOREA,
                                       inverse=True), BESSEL)


# ── 밖으로 내는 것 ──────────────────────────────────────────────────

def to_latlon(code: str, east: float, north: float):
    """평면 좌표(동, 북) → (위도, 경도). 위경도를 넘기면 (north, east) 그대로."""
    spec = SYSTEMS[code]
    if code == "4326":
        return north, east
    lat, lon = _tm_to_ll(east, north, spec)
    if spec[7]:
        lat, lon = _bessel_to_wgs(lat, lon)
    return lat, lon


def from_latlon(code: str, lat: float, lon: float):
    """(위도, 경도) → 평면 좌표 (동, 북)."""
    spec = SYSTEMS[code]
    if code == "4326":
        return lon, lat
    if spec[7]:
        lat, lon = _wgs_to_bessel(lat, lon)
    return _ll_to_tm(lat, lon, spec)


#: 바꾼 좌표가 여기 안에 있어야 받는다 — 좌표계를 잘못 고르면 바다 한가운데나
#: 딴 나라로 간다. 그때는 고른 좌표계를 의심하라고 말한다.
KOREA_BOX = (120.0, 30.0, 135.0, 44.0)


def in_korea(lat: float, lon: float) -> bool:
    w, s, e, n = KOREA_BOX
    return w <= lon <= e and s <= lat <= n


# ── 사람이 넣은 두 수 ────────────────────────────────────────────────

import re  # noqa: E402  (위의 셈은 math 만 쓴다. 이 아래는 글자를 읽는다)

_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def two_numbers(text: str):
    """"234567.1 417654.3", "234,567.1, 417,654.3" 같은 것에서 수 둘을 꺼낸다."""
    text = _THOUSANDS.sub("", text or "")
    found = _NUMBER.findall(text)
    if len(found) != 2:
        return None
    return float(found[0]), float(found[1])


_LABELLED = re.compile(r"(?i)(north|east|[NE]|북|동)\s*[:=]?\s*(-?\d[\d,]*(?:\.\d+)?)")


def labelled_pair(text: str):
    """"N 420005 E 232509", "동=232509, 북=420005" 처럼 이름을 붙인 두 수 → (동, 북).

    X·Y 는 받지 않는다 — GIS 는 x 가 동쪽이고 측량은 X 가 북쪽이라, 이름을
    붙여도 뜻이 갈린다.
    """
    east = north = None
    for label, number in _LABELLED.findall(_THOUSANDS.sub("", text or "")):
        value = float(number.replace(",", ""))
        if label.lower() in ("n", "north", "북"):
            north = value
        else:
            east = value
    return (east, north) if east is not None and north is not None else None


def candidates(code: str, a: float, b: float):
    """두 수의 두 차례 가운데 한반도 안에 떨어지는 것들. [(위도, 경도, "동북"|"북동")]."""
    out = []
    for east, north, order in ((a, b, "en"), (b, a, "ne")):
        try:
            lat, lon = to_latlon(code, east, north)
        except (ValueError, OverflowError, ZeroDivisionError):
            continue
        if in_korea(lat, lon):
            out.append((lat, lon, order))
    return out


def resolve(code: str, a: float, b: float):
    """평면 좌표 두 수 → (위도, 경도, 뒤바꿨나). 한반도 밖이면 None.

    **동·북 차례를 가리지 않는다.** GIS 는 x 가 동쪽이고, 측량은 X 가
    북쪽이다. 사람이 어느 쪽으로 적었는지 묻지 않고, 적힌 차례로 바꿔 보고
    한반도 밖이면 뒤집어 본다. 둘 다 안이면 적힌 차례가 이긴다.
    """
    try:
        lat, lon = to_latlon(code, a, b)
        if in_korea(lat, lon):
            return lat, lon, False
        lat, lon = to_latlon(code, b, a)
        if in_korea(lat, lon):
            return lat, lon, True
    except (ValueError, OverflowError, ZeroDivisionError):
        pass
    return None
