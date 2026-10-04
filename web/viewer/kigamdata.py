"""KIGAM 오픈플랫폼의 자료 — 시료·분석, 조사·탐사, 지질자원주제도를 모아 둔다 (wetherilli 169).

`manage.py fetch_kigam_data` 가 문(`kigam.py` 의 `data_list`·`data_detail`)으로 1 초에 한 번씩 받아 `<KIGAM_DATA_DIR>/data.json`
에 적는다. 화면이 부를 때는 이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다.

- **처음은 한 시간 남짓**(목록 35 쪽 + 상세 3 450 건). 다음부터는 목록의 `lastModified` 가 바뀐 것과 새 것만 상세를 받는다
- 좌표는 상세의 `metadata.위치정보.좌표` — WKT `POINT (경도 위도)`(축은 경도 먼저, 2026-10-02 에 한국 안에 드는 것으로 확인),
  주제도는 `POLYGON`. **좌표 없이 행정구역만 적힌 것**(옛 소장 표본 따위)은 `--places` 로 부르면 VWorld 로 그 행정구역의
  가운데를 찾아 `places.json` 에 담는다(두 번 묻지 않는다). 나라가 대한민국이 아닌 것은 찾지 않는다
- 이용 조건은 자료마다 적혀 온다(대부분 CC BY-NC, 일부 CC BY-NC-ND) — 담아 둔다. DOI 가 출처다
- **무엇을 지도에 올릴지는 아직 정하지 않았다**(이슈 #153). 지어 본 레이어(모음마다 점·면, 행정구역 가운데 표본)는
  `feature/kigam-data-layers` 가지에 있다
"""
import json
import re
import time
from pathlib import Path

from django.conf import settings

DATA_FILE = "data.json"
PLACES_FILE = "places.json"



def data_dir() -> Path:
    return Path(settings.KIGAM_DATA_DIR)



def load(file_name: str = DATA_FILE) -> dict:
    path = data_dir() / file_name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, file_name: str = DATA_FILE):
    path = data_dir() / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def available() -> bool:
    return (data_dir() / DATA_FILE).exists()


# ── 모으기 ───────────────────────────────────────────────────────────

def trim(detail: dict) -> dict:
    """상세 한 건 → 담아 둘 것. 판 이력(`series`)·파일 목록은 덜어 낸다 — 파일은 수만 센다."""
    files = [f.get("name") for b in detail.get("bundles") or [] for f in b.get("files") or []]
    return {"id": detail.get("id"), "title": (detail.get("title") or "").strip(),
            "collection": (detail.get("collection") or {}).get("name", ""),
            "license": detail.get("license") or "", "doi": detail.get("doi") or "",
            "lastModified": detail.get("lastModified") or "", "metadata": detail.get("metadata") or {},
            "files": len(files)}


def harvest(log=print, pause: float = 1.0, limit: int = None) -> dict:
    """목록을 다 받고, 새것·바뀐 것의 상세를 받는다. 50 건마다 적어 두어 멈췄다 다시 불러도 이어 간다.
    상류가 거절하면 `kigam.UpstreamError` 가 그대로 올라간다 — 그때까지 받은 것은 남는다."""
    from . import kigam

    data = load() or {"items": {}}
    items = data.setdefault("items", {})
    listed, page, total_pages = {}, 0, None
    while total_pages is None or page < total_pages:
        if page:
            time.sleep(pause)
        got = kigam.data_list(page)
        total_pages = got.get("totalPages") or 0
        for row in got.get("content") or []:
            listed[row["id"]] = row.get("lastModified") or ""
        page += 1
    log(f"  목록 {len(listed):,} 건 ({total_pages} 쪽)")
    todo = [i for i, stamp in listed.items() if i not in items or items[i].get("lastModified") != stamp]
    gone = [i for i in items if i not in listed]
    for i in gone:
        del items[i]
    if limit is not None:
        todo = todo[:limit]
    log(f"  상세를 받을 것 {len(todo):,} 건 (없어진 것 {len(gone)} 건)")
    for n, dataset_id in enumerate(todo, 1):
        time.sleep(pause)
        items[dataset_id] = trim(kigam.data_detail(dataset_id))
        if n % 50 == 0:
            data["harvested"] = time.strftime("%Y-%m-%d %H:%M")
            save(data)
            log(f"  {n:,} / {len(todo):,}")
    data["harvested"] = time.strftime("%Y-%m-%d %H:%M")
    save(data)
    return {"listed": len(listed), "fetched": len(todo), "gone": len(gone)}


# ── 자리 ─────────────────────────────────────────────────────────────

_WKT_POINT = re.compile(r"^\s*POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)\s*$", re.I)
_WKT_POLYGON = re.compile(r"^\s*POLYGON\s*\(\((.*)\)\)\s*$", re.I | re.S)


def parse_wkt(text: str):
    """WKT `POINT`·`POLYGON`(바깥 고리 하나) → GeoJSON 기하. 모르는 꼴이면 None."""
    text = str(text or "")
    m = _WKT_POINT.match(text)
    if m:
        lon, lat = float(m.group(1)), float(m.group(2))
        return {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}
    m = _WKT_POLYGON.match(text)
    if m:
        ring = []
        for pair in m.group(1).split("),")[0].split(","):
            parts = pair.strip().strip("()").split()
            if len(parts) >= 2:
                ring.append([round(float(parts[0]), 6), round(float(parts[1]), 6)])
        if len(ring) >= 4:
            return {"type": "Polygon", "coordinates": [ring]}
    return None


def section(item: dict, name: str) -> dict:
    value = (item.get("metadata") or {}).get(name)
    return value if isinstance(value, dict) else {}


def admin_text(item: dict) -> str:
    """좌표 없이 적힌 행정구역 한 줄 — `강원도 태백시 장성동`. 나라가 대한민국이 아니면 빈 글."""
    place = section(item, "위치정보")
    if place.get("국가") and place.get("국가") != "대한민국":
        return ""
    parts = [place.get(k, "") for k in ("도,광역시", "시군구", "동,면")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def locate(places: dict, text: str, geocode, log=print):
    """행정구역 한 줄 → `[위도, 경도]`. 담아 둔 것이 먼저다. 못 찾으면 끝 마디를 떼며 다시 — 동·면이 옛 이름이거나 리가 붙어도
    시군구의 가운데는 선다. 못 찾은 것도 담는다(None) — 두 번 묻지 않는다."""
    if text in places:
        return places[text]
    words = text.split()
    found = None
    while words and found is None:
        try:
            hit = geocode(" ".join(words))
        except Exception as exc:          # VWorld 가 거절하면 이번에는 놓고 다음에 다시 묻는다
            log(f"  {text}: {exc}")
            return None
        if hit:
            found = [round(hit["lat"], 5), round(hit["lon"], 5)]
        words = words[:-1]
    places[text] = found
    return found
