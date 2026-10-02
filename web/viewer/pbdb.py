"""Paleobiology Database 로 나가는 문 — 온 지구의 화석 산지 (wetherilli P07 §3·098).

화석 산지(collection)는 여기로만 받는다 (CLAUDE.md "상류마다 문이 하나").

- 주소 `paleobiodb.org/data1.2`. **열쇠가 없다.** 자료는 CC BY 4.0 이다(2013-12-19 PBDB 공지) — 산지마다 원 논문을
  함께 적어 달라고 한다. 팝업이 산지의 첫 문헌(`primary_reference`)을 싣는다
- **화면이 부를 때 상류를 타지 않는다.** 산지는 27 만 곳 남짓이라 `manage.py fetch_pbdb` 가 한 번에 받아(CSV 110 MB 남짓)
  `fossils.py` 가 sqlite 로 굽는다 — 극지연구소 목록과 같은 틀이다(053). 살아 있는 DB 라 가끔 다시 받는다
- 받는 것은 `colls/list` 의 `all_records` 하나다. 한 번 부르고 스트림으로 적는다 — 쪼개 여러 번 두드리지 않는다
"""
import logging
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

API = "https://paleobiodb.org/data1.2"
CREDIT = "Paleobiology Database (CC BY 4.0) · paleobiodb.org"
#: 산지 목록 — 자리·옛 자리(PALEOMAP, 연대의 가운데)·지층·환경·첫 문헌
QUERY = {"all_records": "", "show": "loc,paleoloc,strat,geo,time,ref", "pgm": "scotese", "vocab": "pbdb"}


class PbdbError(RuntimeError):
    pass


def collection_url(no: int) -> str:
    """사람이 읽는 산지 쪽."""
    return f"https://paleobiodb.org/classic/displayCollectionDetails?collection_no={int(no)}"


def download(dest: Path, timeout: int = 900) -> int:
    """모든 산지를 CSV 로 `dest` 에 적는다. 적은 바이트 수."""
    left = usage.paused()
    if left:
        raise PbdbError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    tmp = Path(str(dest) + ".part")
    try:
        with requests.get(f"{API}/colls/list.csv", params=QUERY, stream=True, timeout=(settings.UPSTREAM_TIMEOUT, timeout),
                          verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"}) as r:
            log.info("PBDB %s -> %s", r.url, r.status_code)
            if r.status_code != 200:
                usage.record("pbdb", ok=False, blocked=usage.looks_blocked(r.status_code, b""))
                raise PbdbError(f"PBDB 가 {r.status_code} 로 답했다")
            size = 0
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
                    size += len(chunk)
    except requests.RequestException as exc:
        usage.record("pbdb", ok=False)
        raise PbdbError(f"PBDB 에 닿지 못했다: {exc}") from exc
    usage.record("pbdb", ok=True)
    tmp.replace(dest)
    return size
