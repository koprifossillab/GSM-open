"""NOAA GFS 로 나가는 문 — 지금의 바람 (koprifossillab P02).

GFS 는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소 `nomads.ncep.noaa.gov` 의 grib filter(`filter_gfs_0p25.pl`). **열쇠가 없다.** 미국 정부 자료라 쓰는 데 제한이 없다
- 하루 네 번(00·06·12·18 UTC) 판이 서고, 판은 그 시각에서 네 시간 남짓 뒤에 올라온다. 받는 것은 분석(f000)과 예보
  +3·+6·+9·+12 시간(`FORECAST_HOURS`)의 u·v 를 두 높이(10 m·250 hPa)에서 — 한 장에 한 번, 판마다 다섯 번 부른다(장마다 3 MB
  남짓). 다음 판이 올라오기까지 판 시각에서 10 시간 남짓이 걸려 +12 시간까지 받는다 — 화면이 "지금" 을 앞뒤 두 장 사이로
  섞어 보이려면 지금보다 뒤의 장이 늘 있어야 한다 (koprifossillab 008)
- NOMADS 는 **분당 120 번**을 넘으면 막는다. 우리는 한 시간에 한두 번이다
- **화면이 부를 때 상류를 타지 않는다.** 호스트의 cron 이 `manage.py fetch_gfs_wind` 로 받아 `wind.py` 가 PNG 로 굽는다
- GRIB2 는 ecCodes 로 푼다 — **cron 의 전용 venv(`/srv/GSM/scripts/venv`, `run.sh`) 에만 있다**(`requirements-wind.txt`, koprifossillab 005). 그래서 `decode` 안에서만 부른다
"""
import datetime as dt
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

FILTER = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
#: 받는 높이 — grib filter 의 이름과 우리 이름(`wind.LEVELS`)
LEVELS = {"10m": "lev_10_m_above_ground", "250hPa": "lev_250_mb"}
#: 구름량 — 같은 요청에 더한다 (koprifossillab 011). 우리 종류 -> (변수, 층, ecCodes 의 shortName·typeOfLevel).
#: 예보 장에는 순간값과 0–3 시간 평균이 함께 온다 — 바람과 짝짓도록 순간값(`instant`)만 쓴다. `TCDC` 는 기압면마다도 있어
#: 250 mb 의 것이 딸려 오지만 층(`atmosphere`)으로 거른다
CLOUDS = {
    "total": ("var_TCDC", "lev_entire_atmosphere", "tcc", "atmosphere"),
    "low": ("var_LCDC", "lev_low_cloud_layer", "lcc", "lowCloudLayer"),
    "mid": ("var_MCDC", "lev_middle_cloud_layer", "mcc", "middleCloudLayer"),
    "high": ("var_HCDC", "lev_high_cloud_layer", "hcc", "highCloudLayer"),
}
CYCLE_HOURS = 6
#: 받는 예보 시간 — 0 이 분석이다
FORECAST_HOURS = (0, 3, 6, 9, 12)


class GfsError(RuntimeError):
    pass


def recent_cycles(now: dt.datetime, count: int = 3) -> list:
    """`now`(UTC) 에서 가장 가까운 지난 판부터 `count` 개 — `YYYYMMDDHH`. 아직 안 올라온 판도 있으니 차례로 묻는다."""
    start = now.replace(minute=0, second=0, microsecond=0, hour=now.hour - now.hour % CYCLE_HOURS)
    return [(start - dt.timedelta(hours=CYCLE_HOURS * i)).strftime("%Y%m%d%H") for i in range(count)]


def valid_time(cycle: str, fh: int) -> str:
    """판 `cycle` 의 예보 `fh` 시간이 가리키는 시각 — `YYYYMMDDHH`."""
    return (dt.datetime.strptime(cycle, "%Y%m%d%H") + dt.timedelta(hours=fh)).strftime("%Y%m%d%H")


def params(cycle: str, fh: int = 0) -> dict:
    day, hour = cycle[:8], cycle[8:]
    query = {"dir": f"/gfs.{day}/{hour}/atmos", "file": f"gfs.t{hour}z.pgrb2.0p25.f{fh:03d}",
             "var_UGRD": "on", "var_VGRD": "on"}
    query.update({name: "on" for name in LEVELS.values()})
    for var, lev, _, _ in CLOUDS.values():
        query[var] = query[lev] = "on"
    return query


def download(cycle: str, fh: int = 0) -> bytes | None:
    """그 판·그 예보 시간의 u·v 를 GRIB2 로. 아직 올라오지 않았으면 None."""
    left = usage.paused()
    if left:
        raise GfsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(FILTER, params=params(cycle, fh), timeout=(settings.UPSTREAM_TIMEOUT, 120),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gfs", ok=False)
        raise GfsError(f"NOMADS 에 닿지 못했다: {exc}") from exc
    log.info("GFS %s f%03d -> %s (%d B)", cycle, fh, r.status_code, len(r.content))
    if r.status_code == 200 and r.content[:4] == b"GRIB":
        usage.record("gfs", ok=True)
        return r.content
    if r.status_code == 404:
        usage.record("gfs", ok=True)     # 판이 아직 없다 — 정상인 답이다. 매시 묻는 것이 실패로 쌓이지 않게
        return None
    blocked = usage.looks_blocked(r.status_code, r.content)
    usage.record("gfs", ok=False, blocked=blocked)
    if blocked:
        raise GfsError(f"NOMADS 가 {r.status_code} 로 막았다")
    raise GfsError(f"NOMADS 가 {r.status_code} 로 답했다")


def decode(grib: bytes) -> dict:
    """GRIB2 -> `{높이: (u, v)}`, 격자는 721×1440(경도 0 부터, 위도 90 부터). **호스트에서만** — ecCodes·numpy."""
    return decode_all(grib)[0]


def decode_all(grib: bytes) -> tuple:
    """GRIB2 -> (`{높이: (u, v)}`, `{구름 종류: 구름량 0–1}`). 구름이 오지 않았으면 둘째는 빈 사전."""
    import eccodes
    import numpy as np

    by_level = {"10": "10m", "25000": "250hPa", "250": "250hPa"}
    cloud_of = {(short, tol): kind for kind, (_, _, short, tol) in CLOUDS.items()}
    found, clouds = {}, {}
    for msg in _messages(grib):
        handle = eccodes.codes_new_from_message(msg)
        try:
            name = eccodes.codes_get(handle, "shortName")
            level = by_level.get(str(eccodes.codes_get(handle, "level")))
            ni, nj = eccodes.codes_get(handle, "Ni"), eccodes.codes_get(handle, "Nj")
            first_lat = eccodes.codes_get(handle, "latitudeOfFirstGridPointInDegrees")
            first_lon = eccodes.codes_get(handle, "longitudeOfFirstGridPointInDegrees")
            if (ni, nj) != (1440, 721) or first_lat != 90 or first_lon != 0:
                raise GfsError(f"격자가 다르다: {ni}×{nj}, 첫 점 {first_lat},{first_lon}")
            values = np.asarray(eccodes.codes_get_values(handle), dtype=np.float32).reshape(721, 1440)
            kind = cloud_of.get((name, eccodes.codes_get(handle, "typeOfLevel")))
            instant = eccodes.codes_get(handle, "stepType") == "instant"
        finally:
            eccodes.codes_release(handle)
        if kind:
            if instant:
                clouds[kind] = values / 100.0          # GFS 는 퍼센트다
            continue
        comp = {"u": "u", "10u": "u", "v": "v", "10v": "v"}.get(name)
        if level and comp:
            found.setdefault(level, {})[comp] = values
    out = {}
    for level in LEVELS:
        pair = found.get(level, {})
        if "u" not in pair or "v" not in pair:
            raise GfsError(f"{level} 의 u·v 가 다 오지 않았다")
        out[level] = (pair["u"], pair["v"])
    return out, clouds


def _messages(grib: bytes):
    """GRIB2 묶음을 메시지마다 자른다 — 머리의 길이(8 바이트, 큰 끝)를 따라간다."""
    pos = 0
    while pos + 16 <= len(grib):
        if grib[pos:pos + 4] != b"GRIB":
            raise GfsError(f"{pos} 바이트에 GRIB 머리가 없다")
        total = int.from_bytes(grib[pos + 8:pos + 16], "big")
        yield grib[pos:pos + total]
        pos += total
