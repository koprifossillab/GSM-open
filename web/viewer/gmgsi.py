"""NOAA GMGSI 로 나가는 문 — 위성이 찍은 지금의 구름 (koprifossillab 012).

GMGSI(Global Mosaic of Geostationary Satellite Imagery)는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 AWS 의 NOAA 공개 자료 버킷 `noaa-gmgsi-pds`. **열쇠가 없다.** 미국 정부 자료라 쓰는 데 제한이 없다
- 정지궤도 위성 다섯(GOES-East·West, Himawari, Meteosat 둘)의 장파 적외선을 NESDIS 가 이어 붙인 **온 지구 합성**이다. 한 시간마다
  한 장(HDF5, 7.5 MB 남짓)이 정시에서 30 분 남짓 뒤에 올라온다. NASA GIBS 의 정지궤도 영상에는 Meteosat 이 없어 경도 0°–70°E 가
  비므로 이것을 골랐다
- 격자는 **메르카토르**다 — 4999×3000, 경도 0.072° 고르게(날짜변경선부터), 위도는 행마다 간격이 다르고 **±72.7° 까지**뿐이다
- 값은 휘도 온도를 0–255 로 줄인 회색이다(차가울수록 밝다 — 높은 구름이 희다)
- **화면이 부를 때 상류를 타지 않는다.** 호스트의 cron 이 매시 `manage.py fetch_gmgsi` 로 받고 `wind.py` 가 PNG 로 굽는다
- HDF5 는 h5py 로 푼다 — **cron 의 전용 venv 에만 있다**(`requirements-wind.txt`). 그래서 `decode` 안에서만 부른다
"""
import datetime as dt
import logging
import re

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

BUCKET = "https://noaa-gmgsi-pds.s3.amazonaws.com"
PRODUCT = "GMGSI_LW"
#: 펴서 굽는 격자 — 0.1°, 온 지구. 위도 ±72.7° 너머는 비운다
WIDTH, HEIGHT = 3600, 1800


class GmgsiError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, timeout: int = 120) -> requests.Response:
    left = usage.paused()
    if left:
        raise GmgsiError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gmgsi", ok=False)
        raise GmgsiError(f"GMGSI 버킷에 닿지 못했다: {exc}") from exc
    if r.status_code != 200:
        usage.record("gmgsi", ok=False, blocked=usage.looks_blocked(r.status_code, r.content))
        raise GmgsiError(f"GMGSI 버킷이 {r.status_code} 로 답했다")
    usage.record("gmgsi", ok=True)
    return r


def hour_key(hour: dt.datetime) -> str | None:
    """그 시(UTC)의 장의 열쇠. 아직 없으면 None. 한 시에 한 장이다."""
    prefix = f"{PRODUCT}/{hour:%Y/%m/%d/%H}/"
    body = _get(BUCKET + "/", {"list-type": "2", "prefix": prefix, "max-keys": "20"}, timeout=30).text
    keys = sorted(k for k in re.findall(r"<Key>([^<]+)</Key>", body) if k.endswith(".nc"))
    return keys[-1] if keys else None


def recent_hours(now: dt.datetime, count: int = 3) -> list:
    """`now` 에서 가장 가까운 지난 시부터 `count` 개."""
    start = now.replace(minute=0, second=0, microsecond=0)
    return [start - dt.timedelta(hours=i) for i in range(count)]


def download(key: str) -> bytes:
    r = _get(f"{BUCKET}/{key}", timeout=300)
    log.info("GMGSI %s (%d B)", key.rsplit("/", 1)[-1], len(r.content))
    return r.content


def decode(blob: bytes):
    """HDF5 -> 0.1° 경위도 회색 격자(1800×3600, 경도 −180 부터, 위도 90 부터, uint8). 위도 ±72.7° 너머는 0.
    **호스트에서만** — h5py·numpy."""
    import io

    import h5py
    import numpy as np

    with h5py.File(io.BytesIO(blob), "r") as f:
        data = np.asarray(f["data"][0], dtype=np.float32)
        lat = np.asarray(f["lat"][:, 0], dtype=np.float64)
        lon = np.asarray(f["lon"][0], dtype=np.float64)
    if data.ndim != 2 or data.shape != (lat.size, lon.size):
        raise GmgsiError(f"격자가 다르다: {data.shape}")
    data = np.where(data < 0, 0, data)                    # 채움 값
    # 경도 — 날짜변경선(180)부터 돈다. −180→180 으로 펴고 0.1° 칸 가운데로 가장 가까운 열을 고른다
    lon = (lon + 180) % 360 - 180
    order = np.argsort(lon)
    lon, data = lon[order], data[:, order]
    want_lon = -180 + 0.05 + 0.1 * np.arange(WIDTH)
    cols = np.clip(np.searchsorted(lon, want_lon), 0, lon.size - 1)
    # 위도 — 메르카토르라 행마다 간격이 다르다. 0.1° 칸 가운데마다 위아래 두 행을 선형으로
    want_lat = 90 - 0.05 - 0.1 * np.arange(HEIGHT)
    asc = lat[::-1]                                       # 오름차순으로
    pos = np.interp(want_lat, asc, np.arange(asc.size))   # 오름차순 행 번호(소수)
    inside = (want_lat <= asc[-1]) & (want_lat >= asc[0])
    r0 = np.floor(pos).astype(int)
    r1 = np.minimum(r0 + 1, asc.size - 1)
    frac = (pos - r0)[:, None]
    rows = data[::-1]
    grid = rows[r0][:, cols] * (1 - frac) + rows[r1][:, cols] * frac
    grid[~inside] = 0
    return np.clip(np.rint(grid), 0, 255).astype(np.uint8)


def stamp_of(key: str) -> str:
    """열쇠의 시작 시각(`_s20261001100000…`) -> `YYYYMMDDHH`."""
    m = re.search(r"_s(\d{10})", key)
    if not m:
        raise GmgsiError(f"열쇠에 시각이 없다: {key}")
    return m.group(1)
