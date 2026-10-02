"""ERA5 로 나가는 문 — 지난 바람 (koprifossillab P02).

ERA5 는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 Google Cloud 의 공개 버킷 **ARCO-ERA5**(`gcp-public-data-arco-era5`) — ECMWF ERA5 를 Zarr 로 옮겨 둔 것이다. **열쇠가 없다.**
  자료는 CC BY 4.0 이다 — 화면에 Copernicus 문구를 적는다(`wind.CREDIT`)
- 판은 `full_37-1h-0p25deg-chunk-1.zarr-v3` 하나 — 한 시간마다, 0.25°, 1940 년부터. **시간 번호의 기준은 1900-01-01 이다**
  (`time/.zattrs`). 덩이 하나가 한 변수·한 시각의 온 지구다
- 지상 10 m 는 덩이가 성분마다 3.3 MB 라 통째로 받는다. 기압면은 **37 층이 한 덩이**(117 MB)라, 덩이 앞의 블록 표를 읽고
  **그 층이 든 블록만 HTTP Range 로** 받아(3.4 MB 남짓) 작은 덩이로 다시 엮어 푼다. 2026-10-01 에 통째로 푼 것과 한 비트도
  다르지 않음을 보았다
- **화면이 부를 때 상류를 타지 않는다.** 사람이 `manage.py build_era5_wind` 를 한 번 부른다
- 덩이는 blosc-lz4 다 — numcodecs 로 푼다. **cron 의 전용 venv(`/srv/GSM/scripts/venv`, `run.sh`) 에만 있다**(`requirements-wind.txt`, koprifossillab 005)
"""
import datetime as dt
import logging
import struct

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

STORE = "https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
EPOCH = dt.datetime(1900, 1, 1)
#: 37 층의 차례 (`level/0` — hPa). 250 hPa 는 열여섯째(0 부터)다
PRESSURE_LEVELS = (1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500,
                   550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000)
#: 우리 높이 -> (u 변수, v 변수, 기압면이면 그 층)
LEVELS = {
    "10m": ("10m_u_component_of_wind", "10m_v_component_of_wind", None),
    "250hPa": ("u_component_of_wind", "v_component_of_wind", 250),
}
#: 구름량 — 우리 종류 -> 변수(지상 한 장, 0–1) (koprifossillab 011)
CLOUDS = {"total": "total_cloud_cover", "low": "low_cloud_cover", "mid": "medium_cloud_cover", "high": "high_cloud_cover"}
NY, NX = 721, 1440
PLANE = NY * NX * 4          # float32 한 장의 바이트


class Era5Error(RuntimeError):
    pass


def time_index(when: dt.datetime) -> int:
    return int((when - EPOCH).total_seconds() // 3600)


def _get(url: str, byte_range: tuple | None = None) -> bytes:
    left = usage.paused()
    if left:
        raise Era5Error(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    headers = {"User-Agent": "GSM/0.1"}
    if byte_range:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    try:
        r = requests.get(url, headers=headers, timeout=(settings.UPSTREAM_TIMEOUT, 300), verify=settings.CA_BUNDLE or True)
    except requests.RequestException as exc:
        usage.record("era5", ok=False)
        raise Era5Error(f"ARCO-ERA5 에 닿지 못했다: {exc}") from exc
    if r.status_code not in (200, 206):
        usage.record("era5", ok=False, blocked=usage.looks_blocked(r.status_code, r.content))
        raise Era5Error(f"ARCO-ERA5 가 {r.status_code} 로 답했다 — {url.rsplit('/', 2)[-2]}")
    usage.record("era5", ok=True)
    return r.content


def field(variable: str, when: dt.datetime, level_hpa: int | None = None):
    """한 변수·한 시각(·한 층)의 721×1440 격자(경도 0 부터, 위도 90 부터). **호스트에서만** — numcodecs·numpy."""
    import numpy as np
    from numcodecs import blosc

    t = time_index(when)
    if level_hpa is None:
        raw = blosc.decompress(_get(f"{STORE}/{variable}/{t}.0.0"))
        if len(raw) != PLANE:
            raise Era5Error(f"{variable} 덩이가 {len(raw)} 바이트다")
        return np.frombuffer(raw, dtype="<f4").reshape(NY, NX)
    return np.frombuffer(_level_plane(f"{STORE}/{variable}/{t}.0.0.0", PRESSURE_LEVELS.index(level_hpa)),
                         dtype="<f4").reshape(NY, NX)


def _level_plane(url: str, k: int) -> bytes:
    """37 층 덩이에서 `k` 번째 층만. 머리(16 B)·블록 표·그 층의 블록을 Range 로 받아 작은 blosc 덩이로 엮어 푼다.

    blosc 의 블록은 저마다 따로 눌려 있어(블록 안에 갈래마다 길이가 붙는다) 시작 자리만 고쳐 적으면 앞뒤 블록 없이 풀린다.
    """
    from numcodecs import blosc

    head = _get(url, (0, 15))
    if len(head) != 16 or head[0] != 2:
        raise Era5Error("blosc 머리가 아니다")
    nbytes, blocksize, cbytes = struct.unpack("<III", head[4:16])
    if nbytes != PLANE * len(PRESSURE_LEVELS):
        raise Era5Error(f"덩이가 {nbytes} 바이트다 — 층 수가 바뀌었나")
    if head[2] & 0x02:
        # 눌리지 않은 덩이(blosc 의 memcpy) — 블록 표가 없고 머리 뒤가 그대로 값이다
        return _get(url, (16 + k * PLANE, 16 + (k + 1) * PLANE - 1))
    nblocks = -(-nbytes // blocksize)
    starts = struct.unpack(f"<{nblocks}i", _get(url, (16, 16 + 4 * nblocks - 1)))
    first, last = k * PLANE // blocksize, ((k + 1) * PLANE - 1) // blocksize
    end = starts[last + 1] if last + 1 < nblocks else cbytes
    body = _get(url, (starts[first], end - 1))
    count = last - first + 1
    sub_bytes = min(nbytes, (last + 1) * blocksize) - first * blocksize
    base = 16 + 4 * count
    shift = base - starts[first]
    mini = bytearray(head)
    mini[4:16] = struct.pack("<III", sub_bytes, blocksize, base + len(body))
    mini += struct.pack(f"<{count}i", *(starts[first + i] + shift for i in range(count)))
    mini += body
    raw = blosc.decompress(bytes(mini))
    offset = k * PLANE - first * blocksize
    return raw[offset:offset + PLANE]


def winds(when: dt.datetime) -> dict:
    """그 시각의 `{높이: (u, v)}`."""
    out = {}
    for level, (u_name, v_name, hpa) in LEVELS.items():
        out[level] = (field(u_name, when, hpa), field(v_name, when, hpa))
    return out


def clouds(when: dt.datetime) -> dict:
    """그 시각의 `{구름 종류: 구름량 0–1}`. 덩이가 하나에 2 MB 남짓이다."""
    return {kind: field(name, when) for kind, name in CLOUDS.items()}
