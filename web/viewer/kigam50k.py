"""KIGAM 5만 지질도의 자세 기호 — 층리·엽리·편리·절리의 자리와 값.

**문이 아니다.** 상류를 부르지 않고, 받아 둔 파일(`settings.KIGAM50K_DIR`)을 읽는다.
파일은 KIGAM GeoServer WFS 에서 한 번 받아 둔 것이다 — `raw/<YYYYMMDD>/<이름>.geojson.gz`
와 `manifest.json`(docs/KIGAM_5만_구조요소.md §5). 날짜 폴더가 여럿이면 **가장 새 것**을 읽는다.

5만 지질도 타일에는 이 기호가 그림으로 박혀 있어 누를 수 없다. 여기서 자리와 값을
주면 화면이 커서를 바꾸고 팝업을 띄운다 (jikhanjung 004). 층리 뺀 판에서는 그 자리를
찾는 길이 된다.

값을 읽는 법 (§4):
- `roangle` 은 **경사 방향**이다. 주향은 `roangle − 90°`(오른손 법칙)
- `strike`·`dip` 은 사분면(`NW`·`SW`)뿐이다. 팝업에 원문으로 곁들인다
- `dipangle = -99` 는 경사 미상. 0–90 밖의 값은 적지 않는다
"""
import gzip
import json
import threading
from pathlib import Path

from django.conf import settings

#: 받아 둔 레이어 가운데 자세 기호. 차례가 화면에서 겹칠 때의 차례다
KINDS = ("bedding", "foliation", "schistosity", "joint")

#: 한 번에 내주는 점의 수. 줌 11 의 한 화면(≈ 40 km)에 많아야 천 남짓이다
LIMIT = 5000

_lock = threading.Lock()
_cache = {"folder": None, "rows": None}


def root() -> Path:
    return Path(settings.KIGAM50K_DIR)


def latest() -> Path | None:
    """가장 새 날짜 폴더. 없으면 None."""
    raw = root() / "raw"
    if not raw.is_dir():
        return None
    days = sorted(p for p in raw.iterdir() if p.is_dir() and p.name.isdigit())
    return days[-1] if days else None


def available() -> bool:
    folder = latest()
    return bool(folder) and any((folder / f"{k}.geojson.gz").exists() for k in KINDS)


def _row(kind, feature):
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "MultiPoint":
        coords = coords[0] if coords else None
    if not coords or len(coords) < 2:
        return None
    p = feature.get("properties") or {}
    ro = p.get("roangle")
    dip = p.get("dipangle")
    return {
        "lon": round(float(coords[0]), 6),
        "lat": round(float(coords[1]), 6),
        "kind": kind,
        "type": p.get("type") or "",
        "dipdir": (round(float(ro)) % 360) if isinstance(ro, (int, float)) else None,
        "dip": dip if isinstance(dip, (int, float)) and 0 <= dip <= 90 else None,
        "quad": "/".join(q for q in (p.get("strike"), p.get("dip")) if q),
        "sheet": p.get("mapname") or "",
        "sheet_no": p.get("mapidx") or "",
    }


def load() -> list:
    """네 레이어를 한 줄로. 폴더가 바뀌면 다시 읽는다 — 새 판을 받으면 재기동 없이 따라간다."""
    folder = latest()
    with _lock:
        if folder is not None and _cache["folder"] == folder and _cache["rows"] is not None:
            return _cache["rows"]
        rows = []
        if folder is not None:
            for kind in KINDS:
                path = folder / f"{kind}.geojson.gz"
                if not path.exists():
                    continue
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    for feature in json.load(fh).get("features") or []:
                        row = _row(kind, feature)
                        if row:
                            rows.append(row)
        _cache.update(folder=folder, rows=rows)
        return rows


def within(west: float, south: float, east: float, north: float, limit: int = LIMIT) -> tuple[list, bool]:
    """범위(위경도) 안의 점. (점들, 잘렸나)."""
    out = []
    for row in load():
        if west <= row["lon"] <= east and south <= row["lat"] <= north:
            out.append(row)
            if len(out) >= limit:
                return out, True
    return out, False


def strike_of(dipdir):
    """경사 방향 → 주향(오른손 법칙). 없으면 None."""
    return None if dipdir is None else (dipdir - 90) % 360


def fetched_on() -> str:
    """받은 날 — 폴더 이름(YYYYMMDD)을 YYYY-MM-DD 로."""
    folder = latest()
    if folder is None:
        return ""
    n = folder.name
    return f"{n[:4]}-{n[4:6]}-{n[6:8]}" if len(n) == 8 else n
