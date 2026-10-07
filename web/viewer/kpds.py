"""항우연 KPDS(KARI Planetary Data System)로 나가는 문 — 다누리(KPLO) 과학자료 (wetherilli 377).

KPDS 는 다누리의 과학자료를 NASA PDS4 꼴로 내는 곳이다. **회원가입·인증키가 없고**, "모든 과학자료는 계획된 일정에 따라
제약없이 일반인에게 공개" 한다(KPDS 소개). 따로 적힌 CC 라이선스는 없다. 인용은 탑재체 담당자에게 물으라고 한다.

**문서화된 API 가 없다.** 검색 화면의 자바스크립트(`search_table.js`·`search_detail_modal.js`)가 부르는 주소를 그대로 쓴다 —
예고 없이 바뀔 수 있다.

- 목록 — `POST /search/dataTableList`(DataTables 의 서버 쪽 꼴). 먼저 검색 화면을 한 번 열어 세션 쿠키를 받아야 답이 온다.
  `param[_txt]` 에 낱말(`(*kmag*)`), `param[processing_level_ss]` 에 처리 수준(`(Calibrated)`)
- 라벨 — `GET /search/xml/<_id>` (PDS4 XML)
- 내려받기 — `GET /search/download/<메타 파일 이름에서 .xml 을 뺀 것>` → 라벨과 자료를 담은 zip

**목록에 썸네일(base64)이 붙어 온다** — 영상 탑재체(LUTI·PolCam)는 한 행에 수백 KB 라 목록만 수 GB 다. 그래서 LUTI 촬영 자리는
접었다(TODOs). 자기장(KMAG)은 썸네일이 없어 942 행이 3 MB 남짓이다.

부르는 이는 `manage.py fetch_kmag` 하나다 — 화면이 부를 때 KPDS 를 타지 않는다.
"""
import io
import logging
import zipfile

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 내려받기 사이에 쉬는 초 — 한 번 모으는 일이라 서두르지 않는다 (devlog 010)
PAUSE = 1.5
INSTRUMENTS = ("kmag", "kgrs", "luti", "polcam")
LEVELS = ("Raw", "Partially Processed", "Calibrated", "Derived")
CREDIT = "KPLO (Danuri) · KARI KPDS"


class KpdsError(RuntimeError):
    pass


def _url(path: str) -> str:
    return settings.KPDS_URL.rstrip("/") + path


def session() -> requests.Session:
    """검색 화면을 한 번 열어 쿠키를 받은 세션. 쿠키가 없으면 목록이 비어 온다."""
    s = requests.Session()
    s.headers["User-Agent"] = "GSM/0.1"
    _send(s, "GET", "/search_view/levelproduct")
    return s


def _send(s: requests.Session, method: str, path: str, **kw):
    try:
        r = s.request(method, _url(path), timeout=max(settings.UPSTREAM_TIMEOUT, 120),
                      verify=settings.CA_BUNDLE or True, **kw)
    except requests.RequestException as exc:
        usage.record("kpds", ok=False)
        raise KpdsError(f"KPDS 에 닿지 못했다: {exc}") from exc
    log.info("kpds %s %s -> %s", method, path, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("kpds", ok=r.status_code == 200, blocked=blocked, elapsed=r.elapsed)
    if r.status_code != 200:
        raise KpdsError(f"KPDS 가 받지 않았다 (status={r.status_code})")
    return r


def search(s: requests.Session, instrument: str, level: str, start: int = 0, length: int = 200) -> tuple:
    """`(모두 몇 행, [행…])`. 행은 `{"id", "lid", "meta", "start", "stop", "bytes"}` — 썸네일은 버린다."""
    if instrument not in INSTRUMENTS or level not in LEVELS:
        raise KpdsError(f"모르는 탑재체·처리 수준 ({instrument}, {level})")
    data = {"draw": "1", "start": str(start), "length": str(length),
            "columns[0][data]": "identifier", "order[0][column]": "0", "order[0][dir]": "asc",
            "param[start]": "0", "param[type]": "table", "param[_txt]": f"(*{instrument}*)",
            "param[condition]": "OR", "param[processing_level_ss]": f'("{level}")' if " " in level else f"({level})"}
    r = _send(s, "POST", "/search/dataTableList", data=data, headers={"X-Requested-With": "XMLHttpRequest"})
    try:
        got = r.json()
    except ValueError as exc:
        raise KpdsError("KPDS 목록이 JSON 이 아니다") from exc
    rows = []
    for row in got.get("data") or []:
        first = lambda v: (v[0] if isinstance(v, list) and v else v)      # noqa: E731
        rows.append({"id": first(row.get("_id")), "lid": row.get("identifierS") or first(row.get("identifier")),
                     "meta": first(row.get("metaFileName")), "start": first(row.get("startDate")),
                     "stop": first(row.get("stopDate")), "bytes": first(row.get("allFileSize"))})
    return int(got.get("recordsFiltered") or 0), rows


def download(s: requests.Session, meta: str) -> dict:
    """한 산출물의 zip → `{파일 이름: 바이트}`. `meta` 는 라벨 파일 이름(`…_CAL_M_01.xml`)."""
    name = meta[:-4] if meta.lower().endswith(".xml") else meta
    r = _send(s, "GET", f"/search/download/{name}")
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            return {info.filename.rsplit("/", 1)[-1]: z.read(info) for info in z.infolist() if not info.is_dir()}
    except zipfile.BadZipFile as exc:
        raise KpdsError(f"{name} 이 zip 이 아니다") from exc
