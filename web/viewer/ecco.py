"""ECCO2 로 나가는 문 — 바다 표층의 해류 (koprifossillab 014).

ECCO2 는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 NASA NAS 데이터 포털(`data.nas.nasa.gov/ecco/cs_510/`). **로그인이 없다** — PO.DAAC·ECCO Drive 는 Earthdata
  로그인을 묻지만 NAS 포털은 NASA 의 공식 내려받기 쪽이라 그대로 받는다(docs/ECCO_V4_해류.md §3). NASA 자료라 쓰는 데 제한이
  없고 인용을 바란다
- 파일은 변수·날짜마다 하나(`UVEL.nc/UVEL.1440x720x50.20060617.nc`), 3 일 평균, 1/4° 위경도, 깊이 50 층. **압축 없는 netCDF
  classic** 이라 머리만 읽으면 표층(첫 층)이 몇 번째 바이트부터인지 셈으로 나온다 — 207 MB 파일에서 Range 로 4 MB 만 받는다.
  시작 자리는 변수마다 다르다(`UVEL` 9 800, `VVEL` 9 804 — 이름 길이가 다르다)
- **화면이 부를 때 상류를 타지 않는다.** 사람이 `manage.py build_ecco2` 로 받아 `ocean.py` 가 PNG 로 굽는다
- 받기는 천천히 — 파일 사이 1 초. 재려고 두드리지 않는다(devlog 010)
"""
import logging
import re
import struct

import requests
import urllib3
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

BASE = "https://data.nas.nasa.gov/ecco/cs_510/"
VARS = ("UVEL", "VVEL")
WIDTH, HEIGHT, DEPTHS = 1440, 720, 50
HEAD_BYTES = 32768
CREDIT = "ECCO2 cube92 (NASA JPL·MIT) · Menemenlis et al. 2008"
_DATE = re.compile(r"^\d{8}$")


class EccoError(RuntimeError):
    pass


def file_url(var: str, date: str) -> str:
    return f"{BASE}{var}.nc/{var}.{WIDTH}x{HEIGHT}x{DEPTHS}.{date}.nc"


def _get(url: str, *, byte_range: tuple = None, timeout: int = 120) -> bytes:
    left = usage.paused()
    if left:
        raise EccoError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    headers = {"User-Agent": "GSM/0.1"}
    if byte_range:
        # 끝을 한 바이트 더 묻는다 — 포털이 끝 바이트를 빼고 보낸다(`_read`)
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1] + 1}"
    try:
        r = requests.get(url, headers=headers, timeout=(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, stream=True)
        body = _read(r, byte_range)
    except requests.RequestException as exc:
        usage.record("ecco", ok=False)
        raise EccoError(f"NAS 포털에 닿지 못했다: {exc}") from exc
    log.info("ECCO2 %s %s -> %s (%d B)", url.rsplit("/", 1)[-1], byte_range or "", r.status_code, len(body))
    if r.status_code in (200, 206):
        usage.record("ecco", ok=True)
        return body
    blocked = usage.looks_blocked(r.status_code, body[:1000])
    usage.record("ecco", ok=False, blocked=blocked)
    raise EccoError(f"NAS 포털이 {r.status_code} 로 답했다")


def _read(r, byte_range) -> bytes:
    """몸을 읽는다. **NAS 포털은 큰 Range 에 끝 바이트를 빼고 보내면서 Content-Length 는 다 보낼 것처럼 적는다**(2026-10-01,
    `bytes=0-32767` 에 32 767 바이트. 16 바이트쯤은 온전하다. 끝을 열어 둔 `bytes=0-` 에는 한 바이트만 준다) — 끝까지 읽으면
    한 바이트를 더 기다리다 끊기고, 끊긴 읽기에 든 몸까지 버려진다. 그래서 `_get` 이 끝을 한 바이트 더 묻고, 여기서는 쓸
    만큼만 읽고 닫는다 — 빠지는 바이트는 쓰지 않는 바이트가 된다."""
    want = byte_range[1] - byte_range[0] + 1 if byte_range else None
    try:
        if r.status_code == 206 and want:
            body = r.raw.read(want, decode_content=True)
            if len(body) < want:
                raise requests.ConnectionError(f"{len(body)} B 만 왔다 ({want} B 를 물었다)")
            return body
        return r.raw.read(decode_content=True)
    except (urllib3.exceptions.ProtocolError, urllib3.exceptions.HTTPError) as exc:
        raise requests.ConnectionError(exc) from exc
    finally:
        r.close()


def dates(var: str = "UVEL") -> list:
    """그 변수의 파일이 있는 날짜들(`YYYYMMDD`) — 포털의 목록 쪽에서."""
    page = _get(f"{BASE}{var}.nc/", timeout=60).decode("utf-8", "replace")
    return sorted(set(re.findall(rf"{var}\.{WIDTH}x{HEIGHT}x{DEPTHS}\.(\d{{8}})\.nc", page)))


# ── netCDF classic 머리 ──────────────────────────────────────────────

_TYPES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 8}


def parse_header(buf: bytes) -> dict:
    """netCDF classic(CDF-1·2) 머리 -> `{변수: {"dims": [(이름, 길이)…], "type": 자료형 번호, "begin": 시작 바이트}}`.
    속성은 건너뛴다. 표준 라이브러리만 쓴다 — 굽는 쪽에 netCDF 라이브러리를 들이지 않으려고."""
    if buf[:3] != b"CDF" or buf[3] not in (1, 2):
        raise EccoError("netCDF classic 이 아니다")
    wide = buf[3] == 2
    pos = 8                                    # 마법 수 4 + 레코드 수 4

    def u32():
        nonlocal pos
        value = struct.unpack_from(">I", buf, pos)[0]
        pos += 4
        return value

    def name():
        nonlocal pos
        n = u32()
        text = buf[pos:pos + n].decode("utf-8", "replace")
        pos += (n + 3) // 4 * 4
        return text

    def skip_attrs():
        nonlocal pos
        u32()
        for _ in range(u32()):
            name()
            kind, count = u32(), u32()
            pos += (count * _TYPES[kind] + 3) // 4 * 4

    try:
        u32()
        dims = [(name(), u32()) for _ in range(u32())]
        skip_attrs()
        u32()
        out = {}
        for _ in range(u32()):
            var = name()
            ids = [u32() for _ in range(u32())]
            skip_attrs()
            kind, _size = u32(), u32()
            begin = struct.unpack_from(">Q", buf, pos)[0] if wide else u32()
            if wide:
                pos += 8
            out[var] = {"dims": [dims[i] for i in ids], "type": kind, "begin": begin}
    except (struct.error, IndexError, KeyError) as exc:
        raise EccoError("netCDF 머리가 잘렸거나 깨졌다") from exc
    return out


def surface(var: str, date: str) -> bytes:
    """그 날 그 변수의 맨 위 층(5 m) — 큰 끝 float32 1440×720, 남쪽 줄부터. 머리를 읽고 그 층만 Range 로 받는다."""
    if var not in VARS or not _DATE.match(date):
        raise EccoError("그런 변수·날짜는 받지 않는다")
    url = file_url(var, date)
    head = parse_header(_get(url, byte_range=(0, HEAD_BYTES - 1), timeout=60))
    spec = head.get(var)
    if not spec or spec["type"] != 5:
        raise EccoError(f"{var} 가 float32 로 없다")
    shape = [n for _, n in spec["dims"]]
    if shape[-2:] != [HEIGHT, WIDTH]:
        raise EccoError(f"격자가 다르다: {shape}")
    size = WIDTH * HEIGHT * 4
    body = _get(url, byte_range=(spec["begin"], spec["begin"] + size - 1))
    if len(body) != size:
        raise EccoError(f"표층이 덜 왔다 ({len(body)} B)")
    return body
