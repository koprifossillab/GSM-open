"""미국 지질조사국(USGS) 지진 목록으로 나가는 문 — 온 지구의 M5 이상 지진 (wetherilli 138).

지진 목록(ComCat)은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 FDSN 이벤트 API(`earthquake.usgs.gov/fdsnws/event/1/`). **열쇠가 없다.** USGS 가 만든 자료는 미국 공공 도메인이고,
  출처로 "U.S. Geological Survey" 를 적어 달라고 한다(`CREDIT`)
- **화면이 부를 때 상류를 타지 않는다.** 1900 년부터 M5 이상은 10 만 곳 남짓이라 `manage.py fetch_quakes` 가 받아
  `quakes.py` 가 `<EARTH_DIR>/quakes.sqlite` 로 굽는다 — PBDB(098)·GVP(134)와 같은 틀이다
- 한 번에 2 만 건까지만 준다. **5 년씩 끊어 1 초 간격으로** 묻는다(26 번 남짓). 차단 조짐이면 멈춘다
"""
import datetime
import logging
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
CREDIT = "U.S. Geological Survey · ANSS Comprehensive Earthquake Catalog (ComCat) · public domain"
MIN_MAG = 5.0
START_YEAR = 1900
STEP_YEARS = 5
PAUSE = 1.0


class UsgsError(RuntimeError):
    pass


def event_url(event_id: str) -> str:
    """사람이 읽는 지진 쪽."""
    return f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}"


def windows(start_year: int = START_YEAR, today: datetime.date | None = None) -> list:
    """`(시작, 끝)` 날짜 문자열의 목록 — 5 년씩. 끝은 내일까지(오늘 것도 든다)."""
    end = (today or datetime.date.today()) + datetime.timedelta(days=1)
    out, year = [], start_year
    while datetime.date(year, 1, 1) < end:
        stop = min(datetime.date(year + STEP_YEARS, 1, 1), end)
        out.append((f"{year}-01-01", stop.isoformat()))
        year += STEP_YEARS
    return out


def download(dest: Path, log_line=print, pause: float = PAUSE) -> int:
    """M5 이상을 모두 CSV 로 `dest` 에 적는다. 머리줄은 한 번만. 적은 지진 수."""
    tmp = Path(str(dest) + ".part")
    count = 0
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        for i, (start, end) in enumerate(windows()):
            left = usage.paused()
            if left:
                raise UsgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
            if i:
                time.sleep(pause)
            params = {"format": "csv", "starttime": start, "endtime": end, "minmagnitude": MIN_MAG,
                      "eventtype": "earthquake", "orderby": "time-asc", "limit": 20000}
            try:
                r = requests.get(API, params=params, timeout=(settings.UPSTREAM_TIMEOUT, 300),
                                 verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
            except requests.RequestException as exc:
                usage.record("usgs", ok=False)
                raise UsgsError(f"USGS 에 닿지 못했다: {exc}") from exc
            log.info("USGS %s -> %s", r.url, r.status_code)
            if r.status_code == 204:          # 그 5 년에 지진이 없다
                usage.record("usgs", ok=True)
                continue
            if r.status_code != 200:
                usage.record("usgs", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
                raise UsgsError(f"USGS 가 {r.status_code} 로 답했다 ({start}–{end})")
            usage.record("usgs", ok=True)
            lines = r.text.splitlines()
            if not lines:
                continue
            if count == 0 and fh.tell() == 0:
                fh.write(lines[0] + "\n")
            body = [line for line in lines[1:] if line.strip()]
            if len(body) >= 20000:
                raise UsgsError(f"{start}–{end} 이 2 만 건을 넘는다 — 창을 줄여야 한다")
            fh.write("\n".join(body) + ("\n" if body else ""))
            count += len(body)
            log_line(f"  {start[:4]}–{end[:4]}  {len(body):,} 건")
    if not count:
        tmp.unlink(missing_ok=True)
        raise UsgsError("USGS 가 빈 목록을 주었다")
    tmp.replace(dest)
    return count
