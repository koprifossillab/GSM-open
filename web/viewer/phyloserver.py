"""phyloserver 로 나가는 문 — 연구실이 모아 온 암맥 기록.

`kigam.py`·`vworld.py`·`geus.py`·`grportal.py`·`npolar.py`·`gsj.py` 와 나란한
문이다 (CLAUDE.md "상류마다 문이 하나"). 이 상류의 레이어는 여기로만 나간다.

- 주소: 같은 서버의 phyloserver(`/dikesync/`). **열쇠가 없다.** 들여다보기만
  한다 — 읽는 요청(GET)만 보내고, 기록을 고치는 길(`submit-*`)은 부르지 않는다
- 자료의 주인은 phyloserver 다. 암맥 기록은 야외 앱이 거기로 동기화하고
  사람이 거기서 고친다. **우리는 사본을 들지 않는다** — 캐시만 둔다. 그래서
  캐시가 오래 묵으면 안 된다. 타일의 3 년이 아니라 하루(`FRESH_SECONDS`)다
- 암맥 9 천 건을 **한 번에** 받는다 (`/dikesync/dike-records/?format=json`,
  7 MB). 장을 넘기지 않는다 — phyloserver 가 쪽을 나누지 않고 준다
- 주향은 `angle_from_endpoints` 를 쓴다. 들어온 `angle` 은 위경도 1° 를 같은
  길이로 놓고 잰 값이라 최대 6.8° 어긋난다 (phyloserver devlog 045). 끝점이
  하나뿐인 기록은 주향이 없고, 선이 아니라 점으로 그린다
- 암석 갈래(`cls`)는 **우리가 가른 것이다.** 암석 이름이 200 가지가 넘게
  제각각이라("산성암", "암맥류: 산성암", "석영반암 및 규장암" …) 색을 칠하려면
  몇 갈래로 묶어야 한다. 팝업에는 적힌 이름을 그대로 올린다. devlog 026
"""
import json
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 캐시를 믿는 시간. 기록이 날마다 동기화되므로 하루가 지나면 다시 묻는다.
#: 같은 서버라 한 번 받는 데 1 초 남짓이다 — 자주 물어도 짐이 아니다.
FRESH_SECONDS = 86400
#: 좌표를 이 자리까지만 둔다. 소수 다섯째 자리가 1 m 남짓이다 (`arcpoints.DIGITS`).
DIGITS = 5
#: 이 네모 밖의 좌표는 잘못 적힌 것이다 (0, 경위도가 뒤바뀐 것). 남한과 둘레 섬.
KOREA = (124.0, 33.0, 132.0, 39.0)

DIKES = "phyloserver:dikes"
#: 지도 귀퉁이의 출처. 기관 이름이 아니라 자료가 사는 곳의 이름이라 옮기지 않는다
ATTRIBUTION = "phyloserver · dikesync"

#: 팝업에 올리는 열과 그 이름. 영어는 `i18n.PROP_EN` 에 적는다.
LABELS = {
    "sym": "기호",
    "rock": "암석",
    "strat": "지층",
    "era": "시대",
    "strike": "주향 (끝점에서 잰 값)",
    "len": "길이 (m)",
    "sheet": "도폭",
    "addr": "주소",
    "memo": "메모",
    "uid": "기록 번호",
    "link": "phyloserver 기록",
    # 로즈(낮은 줌) — 화면이 도폭마다 세어 만든 것이다
    "n": "암맥 수",
    "mean": "평균 주향",
}

LAYERS = {
    DIKES: {"style": "dike", "path": "/dikesync/dike-records/?format=json"},
}

# ── 한반도 지질도 — phyloserver 가 들고 있는 타일 (devlog 026) ───────────
#
# phyloserver 의 `uploads/geolmap/map_tiles/` 에 한반도(북한 포함) 지질도 한 장이
# **카카오맵 격자로** 잘려 있다. 옛 화면(geolmap2.html)이 카카오 지도 위에 얹던
# 것이다. 격자는 EPSG:5181(중부원점, GRS80) 에 원점 (-30 000, -60 000), 레벨 L 의
# 한 픽셀이 2^(L-3) m, 타일 번호는 **아래에서 위로** 센다. 레벨 13 이 가로 2·세로
# 5 장이고 한 단계 내려갈 때마다 두 배다. 7 이 가장 자세하다.
#
# 우리 쪽에서 다시 굽지 않는다 — 화면(OpenLayers)이 5181 격자를 그대로 받아
# 3857 로 옮겨 그린다. 캐시에도 담지 않는다. 같은 서버 디스크의 파일이라 담으면
# 925 MB 가 두 벌이 될 뿐이다.

SCANS = {
    "phyloserver:peninsula": {"path": "/media/geolmap/map_tiles/{level}/{x}_{y}.png"},
}
#: 격자 — 화면(`map.js` 의 phyloserverSource)이 같은 값을 쓴다
SCAN_LEVELS = (7, 13)
SCAN_ORIGIN = (-30000, -60000)
SCAN_TOP = (2, 5)          # 레벨 13 의 가로·세로 장 수


def knows_scan(name: str) -> bool:
    return name in SCANS


def valid_scan_tile(name: str, level: int, x: int, y: int) -> bool:
    if name not in SCANS or not (SCAN_LEVELS[0] <= level <= SCAN_LEVELS[1]):
        return False
    mult = 2 ** (SCAN_LEVELS[1] - level)
    return 0 <= x < SCAN_TOP[0] * mult and 0 <= y < SCAN_TOP[1] * mult


def get_scan_tile(name: str, level: int, x: int, y: int):
    """타일 한 장(PNG 바이트). 그 자리에 타일이 없으면(바다·격자 밖) None."""
    if not enabled():
        raise PhyloserverError("phyloserver 주소가 없다")
    path = SCANS[name]["path"].format(level=level, x=x, y=y)
    url = f"{settings.PHYLOSERVER_URL.rstrip('/')}{path}"
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("phyloserver", ok=False)
        raise PhyloserverError(f"phyloserver 에 닿지 못했다: {exc}") from exc
    if r.status_code == 404:
        usage.record("phyloserver", ok=True)
        return None
    if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
        usage.record("phyloserver", ok=False)
        raise PhyloserverError(f"phyloserver 가 타일을 주지 않았다 (status={r.status_code})")
    usage.record("phyloserver", ok=True)
    return r.content


class PhyloserverError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def enabled() -> bool:
    return bool(settings.PHYLOSERVER_URL)


def source_url(name: str = DIKES) -> str:
    """사람이 보는 원본 화면. 암맥 기록 목록이다."""
    return f"{settings.PHYLOSERVER_URL.rstrip('/')}/dikesync/web/dike-records/"


def signature(name: str) -> str:
    """캐시 열쇠. 받는 꼴이 바뀌면 `v` 를 올린다 — 받아 둔 옛 꼴을 쓰지 않게."""
    return f"{name}|v1"


# ── 암석 갈래 ───────────────────────────────────────────────────────────
#
# 차례가 뜻이다. 적힌 **갈래 낱말**(염기성·중성·산성)이 있으면 그것을 믿는다 —
# 원 지질도가 그렇게 묶었다. 없으면 암석 이름으로 가른다. 염기성·중성을 산성보다
# 먼저 보는 것은 "반암과 황반암" 처럼 둘이 섞인 이름 때문이고, 석영맥을 산성보다
# 먼저 보는 것은 "석영" 이 "석영반암" 의 앞머리이기도 해서다.

ROCK_CLASSES = ("acid", "intermediate", "basic", "vein", "other")

_BY_WORD = (
    ("basic", ("염기성", "엽기성")),                # "엽기성암맥" 은 적을 때의 오타다
    ("intermediate", ("중성", "준성")),
    ("acid", ("산성",)),
)
_BY_NAME = (
    ("basic", ("황반암", "빈암", "휘록", "현무", "반려", "각섬", "스페사", "스펫", "람프로")),
    ("intermediate", ("안산", "섬록", "조면")),
    ("vein", ("석영맥", "광맥")),
    ("acid", ("석영반암", "규장", "유문", "화강", "페그마", "패그마", "애풀라이트", "aplite",
              "그래노파이어", "그라노파이어", "장석반암", "펄사이트")),
)
#: 이름이 이것뿐이면 석영맥이다. "석영, 화강암 …" 처럼 뒤가 이어지면 아니다
_VEIN_EXACT = {"석영", "석영류", "맥암류: 석영", "암맥류: 석영", "암맥류 석영"}


def rock_class(rock: str, stratum: str = "") -> str:
    for text in (rock or "", stratum or ""):
        text = text.strip()
        if not text:
            continue
        for cls, words in _BY_WORD:
            if any(w in text for w in words):
                return cls
        if text in _VEIN_EXACT:
            return "vein"
        for cls, words in _BY_NAME:
            if any(w in text for w in words):
                return cls
    return "other"


# ── 받기 ────────────────────────────────────────────────────────────────

def _get(path: str):
    url = f"{settings.PHYLOSERVER_URL.rstrip('/')}{path}"
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("phyloserver", ok=False)
        raise PhyloserverError(f"phyloserver 에 닿지 못했다: {exc}") from exc
    log.info("phyloserver %s -> %s", path, r.status_code)
    if r.status_code != 200:
        usage.record("phyloserver", ok=False)
        raise PhyloserverError(f"phyloserver 가 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        usage.record("phyloserver", ok=False)
        raise PhyloserverError("phyloserver 가 JSON 이 아닌 것을 주었다") from exc
    usage.record("phyloserver", ok=True)
    return data


def fetch(name: str) -> list:
    """레이어 하나를 **모두** 받아 우리 꼴의 feature 목록으로. 이 목록이 캐시에 담긴다."""
    if not enabled():
        raise PhyloserverError("phyloserver 주소가 없다")
    rows = _get(LAYERS[name]["path"])
    if not isinstance(rows, list):
        # DRF 에 쪽 나누기를 켜면 {"results": […]} 로 온다. 그러면 여기를 고친다
        raise PhyloserverError("phyloserver 가 목록이 아닌 것을 주었다")
    return [f for f in (dike_feature(row) for row in rows) if f is not None]


def _coord(lon, lat):
    try:
        lon, lat = float(lon), float(lat)
    except (TypeError, ValueError):
        return None
    if not (KOREA[0] < lon < KOREA[2] and KOREA[1] < lat < KOREA[3]):
        return None
    return [round(lon, DIGITS), round(lat, DIGITS)]


def _text(value):
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def dike_feature(row: dict):
    """암맥 기록 하나 → feature. 지운 기록·좌표가 없는 기록은 None.

    끝점이 둘이면 선, 하나면 점이다. 값은 고치지 않는다 — 빈칸만 떼고 빈 값은 뺀다.
    """
    if row.get("is_deleted"):
        return None
    start = _coord(row.get("lng_1"), row.get("lat_1"))
    if start is None:
        return None
    end = _coord(row.get("lng_2"), row.get("lat_2"))
    geometry = ({"type": "LineString", "coordinates": [start, end]} if end and end != start
                else {"type": "Point", "coordinates": start})

    rock, stratum = _text(row.get("rock_type")), _text(row.get("stratum"))
    props = {
        "sym": _text(row.get("symbol")),
        "rock": rock if rock != "0" else None,
        "strat": stratum,
        "era": _text(row.get("era")),
        "sheet": _text(row.get("map_sheet")),
        "addr": _text(row.get("address")),
        "memo": _text(row.get("memo")),
        "uid": _text(row.get("unique_id")),
        "cls": rock_class(rock or "", stratum or ""),
    }
    strike = row.get("angle_from_endpoints")
    if isinstance(strike, (int, float)) and geometry["type"] == "LineString":
        props["strike"] = round(float(strike) % 180, 1)
    length = row.get("distance")
    if isinstance(length, (int, float)) and length > 0:
        props["len"] = round(float(length), 1)
    if isinstance(row.get("id"), int):
        props["link"] = f"{settings.PHYLOSERVER_URL.rstrip('/')}/dikesync/web/dike-records/{row['id']}/"
    props = {k: v for k, v in props.items() if v is not None}
    return {"type": "Feature", "id": row.get("unique_id") or row.get("id"),
            "geometry": geometry, "properties": props}


def body(name: str, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이 (`arcpoints.body` 와 같은 꼴)."""
    head = json.dumps({"type": "FeatureCollection", "labels": LABELS, "links": ["link"],
                       "style": LAYERS[name]["style"]}, ensure_ascii=False)
    return head[:-1].encode("utf-8") + b', "features": ' + features_json + b"}"


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "phyloserver", "tag": "LAB", "title": "연구실 자료"},
]
