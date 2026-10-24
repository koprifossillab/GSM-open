"""과학 해양 시추(DSDP·ODP·IODP)로 나가는 문 — 시추공 목록 (wetherilli 418).

시추공 목록은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소는 IODP 가 Google Earth 용으로 내는 목록 `kml.iodp.org/Drilled_Holes.csv`(690 KB, 4 283 공). **열쇠가 없다.**
  열은 항차(DSDP·ODP 의 `leg`, IODP 의 `expedition`)·사이트·공·위경도·도착 일시·수심·뚫은 길이·회수 길이·코어 보기·검층 링크다
- 조건 — 목록에는 적힌 것이 없다. 시추 프로그램의 「Sample, Data, and Obligations Policy」(2024-10-01)가 "Project data are publicly
  available after the moratorium period" 라 적고, 쓰면 프로그램을 밝혀 달라고 한다. 인용 꼴은 `CREDIT` 이다
- **화면이 부를 때 상류를 타지 않는다.** `manage.py fetch_iodp_holes` 가 한 번 받아 `<EARTH_DIR>/iodp_holes.json` 에 줄여 적는다.
  항차가 끝나 목록이 고쳐질 때(1 년에 몇 번) 사람이 다시 부른다
- DSDP 의 코어 보기 링크(`www.ngdc.noaa.gov/mgg/geology/dsdp/…`)는 2026-10-23 에 403 이었다 — NCEI 가 내린 자리라 담지 않는다.
  검층 링크(LDEO)는 산다
- ANDRILL·케이프로버츠·CIROS·MSSTS 는 이 목록에 없다 — 우리가 PANGAEA 의 이벤트에서 옮겨 적은 `data/polar_boreholes.json` 을 덧붙인다
"""
import csv
import io
import json
import logging
import re
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

URL = "https://kml.iodp.org/Drilled_Holes.csv"
CREDIT = "IODP · ODP · DSDP drilled holes (kml.iodp.org) — samples and data from the scientific ocean drilling programs"
SOURCE_URL = "https://www.iodp.org/"
#: 손으로 더한 남극 대륙붕 시추 — 출처는 그 파일의 줄마다 적었다
EXTRA = Path(settings.REPO_DIR) / "data" / "polar_boreholes.json"
#: 이 고리를 넘는 DSDP 의 링크는 죽었다 — 담지 않는다
DEAD = ("www.ngdc.noaa.gov/mgg/geology/dsdp/",)
#: 한 줄의 열 — `rows` 의 차례
COLUMNS = ("program", "cruise", "hole", "lon", "lat", "date", "water", "penetrated", "recovered", "core", "log")


class IodpError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.EARTH_DIR) / "iodp_holes.json"


def available() -> bool:
    return path().exists()


def program(leg: str, expedition: str) -> str:
    """DSDP 는 레그 1–96, ODP 는 100–210, IODP(2003 부터, 지금의 IODP³ 까지)는 `expedition` 으로 적는다."""
    if expedition:
        return "iodp"
    return "dsdp" if int(leg) < 100 else "odp"


def day(text: str) -> str:
    """도착 일시 → `YYYY-MM-DD`(날을 모르면 `YYYY-MM`). 꼴이 여럿이다 — `07/18/2024 04:00`·`9/7/24`·`11/2005`. 1900 년은 빈 값이다"""
    m = re.match(r"^\s*(\d{1,2})/(?:(\d{1,2})/)?(\d{2}|\d{4})\b", text or "")
    if not m:
        return ""
    month, dd, year = int(m.group(1)), int(m.group(2) or 0), int(m.group(3))
    if year < 100:
        year += 1900 if year >= 60 else 2000
    if year <= 1900 or not 1 <= month <= 12:
        return ""
    return f"{year:04d}-{month:02d}" + (f"-{dd:02d}" if 1 <= dd <= 31 else "")


def _num(text: str):
    try:
        return round(float(text), 2)
    except (TypeError, ValueError):
        return None


def _link(url: str) -> str:
    url = (url or "").strip()
    if not url or any(d in url for d in DEAD):
        return ""
    return url.replace("http://web.iodp.tamu.edu/", "https://web.iodp.tamu.edu/")


def shrink(text: str) -> list:
    """CSV → 공마다 `COLUMNS` 의 줄. 위경도가 없는 줄은 버린다."""
    out = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        leg, exp = (r.get("leg") or "").strip(), (r.get("expedition") or "").strip()
        if not leg and not exp:
            continue
        prog = program(leg, exp)
        cruise = f"Exp. {exp}" if exp else f"Leg {leg}"
        hole = (r.get("site") or "").strip() + (r.get("hole") or "").strip()
        out.append([prog, cruise, hole, round(lon, 5), round(lat, 5), day(r.get("arrival")), _num(r.get("water_depth")),
                    _num(r.get("core_penetrated")), _num(r.get("core_recovered")), _link(r.get("url_core")),
                    _link(r.get("url_log"))])
    return out


def download(dest: Path) -> int:
    """목록을 받아 줄여 `dest` 에 적는다. 공 수."""
    left = usage.paused()
    if left:
        raise IodpError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(URL, timeout=(settings.UPSTREAM_TIMEOUT, 120), verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("iodp", ok=False)
        raise IodpError(f"IODP 에 닿지 못했다: {exc}") from exc
    log.info("IODP %s -> %s", r.url, r.status_code)
    if r.status_code != 200:
        usage.record("iodp", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
        raise IodpError(f"IODP 가 {r.status_code} 로 답했다")
    usage.record("iodp", ok=True, elapsed=r.elapsed)
    rows = shrink(r.content.decode("utf-8", "replace"))
    if not rows:
        raise IodpError("IODP 가 빈 목록을 주었다")
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps({"source": URL, "fetched": time.strftime("%Y-%m-%d"), "modified": r.headers.get("Last-Modified", ""),
                               "columns": COLUMNS, "holes": rows}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(dest)
    return len(rows)


# ── 읽기 ─────────────────────────────────────────────────────────────

def fetched() -> str:
    """받은 판 — 파일을 고친 때. 없으면 빈 값"""
    try:
        return str(int(path().stat().st_mtime))
    except OSError:
        return ""


def _extra() -> list:
    """손으로 더한 시추공 — `COLUMNS` 꼴로 맞춘다. 링크는 PANGAEA 의 자료다"""
    rows = json.loads(EXTRA.read_text(encoding="utf-8"))["holes"]
    return [["shelf", h["cruise"], h["hole"], h["lon"], h["lat"], h.get("date", ""), h.get("water"), h.get("penetrated"),
             h.get("recovered"), h["source"], ""] for h in rows]


def holes(w: float, s: float, e: float, n: float) -> list:
    """네모 안의 공 — 줄마다 `COLUMNS` 의 dict. 받아 둔 목록 다음에 손으로 더한 것"""
    rows = json.loads(path().read_text(encoding="utf-8"))["holes"] + _extra()
    return [dict(zip(COLUMNS, r)) for r in rows if w <= r[3] <= e and s <= r[4] <= n]
