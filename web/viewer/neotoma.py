"""Neotoma 고생태 데이터베이스로 나가는 문 — 온 지구의 제4기 고생태 산지 (wetherilli 139).

산지·자료(dataset) 목록은 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소 `api.neotomadb.org/v2.0`. **열쇠가 없다.** 자료는 CC BY 4.0 이다 — Neotoma·구성 데이터베이스(북미 꽃가루 DB 따위)·
  원 조사자를 함께 밝혀 달라고 한다. 팝업이 구성 DB·조사자·DOI 를 싣는다
- **화면이 부를 때 상류를 타지 않는다.** `manage.py fetch_neotoma` 가 `data/datasets` 를 쪽마다 받아 `paleoeco.py` 가
  sqlite 로 굽는다 — PBDB(098)·USGS(138)와 같은 틀이다
- 쪽 넘기기(`offset`)는 4 만 건쯤부터 2 분 기다리다 502 를 준다. 그래서 **자료 번호를 500 개씩 묶어** 묻는다(한 번에
  20 초 남짓, 1 초씩 쉰다). 7 만 번호 남짓이라 한 시간쯤 걸린다. 빈 묶음이 열 번 잇따르면 끝으로 본다
"""
import json
import logging
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

API = "https://api.neotomadb.org/v2.0/data"
CREDIT = "Neotoma Paleoecology Database (CC BY 4.0) · neotomadb.org"
BATCH = 500                      # 자료 번호를 이만큼 묶어 묻는다 — 한 번에 20 초 남짓
EMPTY_STOP = 10                  # 빈 묶음이 이만큼 잇따르면 끝이다 (번호 5 000 개)
PAUSE = 1.0


class NeotomaError(RuntimeError):
    pass


def site_url(siteid: int) -> str:
    """사람이 읽는 산지 쪽 — Neotoma Explorer."""
    return f"https://apps.neotomadb.org/explorer/?siteids={int(siteid)}"


def _centre(geography) -> tuple | None:
    """`geography`(GeoJSON 글) → 경위도 하나. 면이면 꼭짓점의 가운데."""
    try:
        geom = json.loads(geography) if isinstance(geography, str) else geography
    except ValueError:
        return None
    if not geom:
        return None
    coords = geom.get("coordinates")
    if geom.get("type") == "Point":
        return float(coords[0]), float(coords[1])
    flat = []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for part in c or []:
                walk(part)
    walk(coords)
    if not flat:
        return None
    return sum(p[0] for p in flat) / len(flat), sum(p[1] for p in flat) / len(flat)


def _bp(value, units: str):
    """연대 값 → 1950 년 앞 햇수(BP). AD/BC 는 1950 에서 뺀다. 방사성탄소 연대는 보정하지 않는다."""
    if value is None:
        return None
    v = float(value)
    return 1950.0 - v if units and "AD/BC" in units else v


def shrink(entries: list) -> list:
    """`data/datasets` 의 한 쪽 → 자료마다 한 줄."""
    out = []
    for entry in entries:
        site = entry.get("site") or {}
        at = _centre(site.get("geography"))
        if at is None or site.get("siteid") is None:
            continue
        for ds in site.get("datasets") or []:
            olds, youngs = [], []
            for a in ds.get("agerange") or []:
                old, young = _bp(a.get("ageold"), a.get("units")), _bp(a.get("ageyoung"), a.get("units"))
                if old is not None:
                    olds.append(old)
                if young is not None:
                    youngs.append(young)
            old = max(olds + youngs) if olds or youngs else None
            young = min(olds + youngs) if olds or youngs else None
            pis = "; ".join(p.get("contactname") or "" for p in ds.get("datasetpi") or [] if p.get("contactname"))
            dois = ds.get("doi") or []
            out.append({"site": site["siteid"], "name": site.get("sitename") or "", "desc": site.get("sitedescription") or "",
                        "alt": site.get("altitude"), "lon": round(at[0], 5), "lat": round(at[1], 5),
                        "dataset": ds.get("datasetid"), "type": ds.get("datasettype") or "", "db": ds.get("database") or "",
                        "old": old, "young": young, "pi": pis, "doi": dois[0] if dois else ""})
    return out


def download(dest: Path, log_line=print, pause: float = PAUSE, batch: int = BATCH, start: int = 1) -> int:
    """모든 자료를 한 줄에 하나씩(JSON Lines) `dest` 에 적는다. 적은 자료 수.

    자료 번호를 `batch` 개씩 묶어 `data/datasets/<번호들>` 로 묻는다. 빈 묶음이 `EMPTY_STOP` 번 잇따르면 끝으로 본다."""
    tmp = Path(str(dest) + ".part")
    count, first, empty = 0, start, 0
    with open(tmp, "w", encoding="utf-8") as fh:
        while empty < EMPTY_STOP:
            left = usage.paused()
            if left:
                raise NeotomaError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
            if first != start:
                time.sleep(pause)
            ids = ",".join(str(i) for i in range(first, first + batch))
            try:
                r = requests.get(f"{API}/datasets/{ids}", params={"limit": batch * 2},
                                 timeout=(settings.UPSTREAM_TIMEOUT, 300), verify=settings.CA_BUNDLE or True,
                                 headers={"User-Agent": "GSM/0.1"})
            except requests.RequestException as exc:
                usage.record("neotoma", ok=False)
                raise NeotomaError(f"Neotoma 에 닿지 못했다: {exc}") from exc
            log.info("Neotoma datasets %s–%s -> %s", first, first + batch - 1, r.status_code)
            if r.status_code != 200:
                usage.record("neotoma", ok=False, blocked=usage.looks_blocked(r.status_code, r.content[:200]))
                raise NeotomaError(f"Neotoma 가 {r.status_code} 로 답했다 (자료 {first}–{first + batch - 1})")
            try:
                entries = r.json().get("data") or []
            except ValueError as exc:
                usage.record("neotoma", ok=False)
                raise NeotomaError("Neotoma 가 JSON 이 아닌 것을 주었다") from exc
            usage.record("neotoma", ok=True)
            rows = shrink(entries)
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += len(rows)
            empty = 0 if rows else empty + 1
            log_line(f"  자료 {first:,}–{first + batch - 1:,}  {len(rows):,} 건 (모두 {count:,})")
            first += batch
    if not count:
        tmp.unlink(missing_ok=True)
        raise NeotomaError("Neotoma 가 빈 목록을 주었다")
    tmp.replace(dest)
    return count
