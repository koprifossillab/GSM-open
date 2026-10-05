"""구운 자료의 나이 — `<DB 옆>` 아래 파일마다 있는지·크기·만든 날·원본 판을 한 표로 (wetherilli 312).

굽는 명령(`build_*`)·모으는 명령(`fetch_*`)이 늘어 어느 파일이 운영에 있고 언제 구웠는지 한눈에 보기 어려워졌다. 여기 **한 표**에 파일과 그것을
만드는 명령을 적어 둔다 — 새로 굽는 파일을 더하면 여기 한 줄 더한다(`ITEMS`). 읽기만 한다. 상류를 타지 않고 파일을 열지도 않는다 — 크기·고친 때는
`stat`, 원본 판은 sqlite 의 `meta` 표나 JSON 머리(앞 4 KB)에서 찾는다. 폴더는 위 칸만 센다(바람 3 GB 를 다 훑지 않는다).

- `manage.py data_status` — 터미널 표
- `/GSM/healthz` — "있어야 하는데 없는 것" 의 수만(`missing`). 상태(ok·degraded)는 바꾸지 않는다
- 관리 화면의 "구운 자료" 칸 — 같은 표, 읽기만

**열쇠 파일(kigam_key·vworld_key·geus_whoami·secret_key)은 적지 않는다** — 있다는 것도 화면에 내지 않는다. 저장소의 `data/` 씨앗도 적지 않는다(판과
함께 온다). 연구실 내부용(한반도 지질도·geo3al)은 밖에 연 판(`GSM_PUBLIC`)이면 "있어야 하는" 것에서 뺀다.
문이 아니다.
"""
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .i18n import msg

#: JSON 머리에서 판으로 읽을 열
_HEAD = re.compile(r'"(fetched|built|version|source|date|updated|generated)"\s*:\s*"([^"]{1,80})"')
#: sqlite `meta` 의 열 가운데 판으로 보일 것
_META_KEYS = ("built", "fetched", "version", "source", "date")
#: 폴더의 가장 새 칸이 날짜(20260930)일 때만 판으로 쓴다 — 타일 폴더의 줌 번호(`1`) 따위는 판이 아니다
_DATE = re.compile(r"\d{8}")


@dataclass(frozen=True)
class Item:
    key: str                  # 표의 이름 — 화면에도 그대로(경로의 끝)
    where: str                # 설정 이름(폴더) — 절대 경로는 화면에 내지 않는다
    name: str                 # 그 폴더 안의 이름. "" 면 폴더 자체
    what: object              # 무엇인가(msg)
    command: str              # 만드는 명령
    lab: bool = False         # 연구실 내부용 — 밖에 연 판에서는 없어도 된다
    needed: bool = True       # 없으면 "있어야 하는데 없는 것" 으로 센다

    def path(self) -> Path:
        base = Path(getattr(settings, self.where))
        return base / self.name if self.name else base


ITEMS = [
    # 남극
    Item("admap2/meta.json", "ADMAP_DIR", "meta.json", msg("남극 자력 이상 ADMAP-2"), "build_admap"),
    Item("geomap/*.gpkg", "GEOMAP_DIR", "", msg("남극 GeoMAP"), "(손으로 둔다)"),
    Item("ibcso/tiles-bed", "IBCSO_DIR", "tiles-bed", msg("남극 해저·빙저 지형 IBCSO v2"), "build_ibcso"),
    Item("npolar/NP_J250_Geologi", "NPOLAR_DIR", "NP_J250_Geologi", msg("얀마옌 지질도"), "(손으로 둔다)"),
    # 북미·카리브
    Item("caribbean/sim3534.sqlite", "CARIBBEAN_DIR", "sim3534.sqlite", msg("카리브 대앤틸리스 지질도"), "build_caribbean"),
    # 온 지구
    Item("earth/pbdb.sqlite", "EARTH_DIR", "pbdb.sqlite", msg("화석 산지 PBDB"), "fetch_pbdb"),
    Item("earth/gvp_volcanoes.json", "EARTH_DIR", "gvp_volcanoes.json", msg("홀로세 화산 GVP"), "fetch_gvp"),
    Item("earth/gvp_pleistocene.json", "EARTH_DIR", "gvp_pleistocene.json", msg("플라이스토세 화산 GVP"), "fetch_gvp"),
    Item("earth/quakes.sqlite", "EARTH_DIR", "quakes.sqlite", msg("지진 USGS M5 이상"), "fetch_quakes"),
    Item("earth/quakes_recent.json", "EARTH_DIR", "quakes_recent.json", msg("최근 지진"), "fetch_recent_quakes"),
    Item("earth/neotoma.sqlite", "EARTH_DIR", "neotoma.sqlite", msg("제4기 고생태 산지 Neotoma"), "fetch_neotoma"),
    Item("earth/paleocoastlines_v7.json", "EARTH_DIR", "paleocoastlines_v7.json", msg("옛 해안선"), "build_paleocoastlines"),
    Item("earth/mantle", "EARTH_DIR", "mantle", msg("맨틀 슬랩"), "build_mantle"),
    Item("earth/seafloor_age.json", "EARTH_DIR", "seafloor_age.json", msg("해양 지각 연대"), "build_seafloor"),
    Item("earth/seafloor_sediment.json", "EARTH_DIR", "seafloor_sediment.json", msg("해저 퇴적층 두께"), "build_seafloor"),
    Item("earth/heatflow.sqlite", "EARTH_DIR", "heatflow.sqlite", msg("지열류"), "build_heatflow"),
    Item("earth/stress.sqlite", "EARTH_DIR", "stress.sqlite", msg("지각 응력"), "build_stress"),
    Item("earth/minerals.sqlite", "EARTH_DIR", "minerals.sqlite", msg("광상"), "build_minerals"),
    Item("earth/earth_faults.json", "EARTH_DIR", "earth_faults.json", msg("활성 단층 GEM"), "build_faults"),
    Item("earth/glaciers.sqlite", "EARTH_DIR", "glaciers.sqlite", msg("세계 빙하 RGI 7.0"), "build_glaciers"),
    Item("wind/gfs", "WIND_DIR", "gfs", msg("지금의 바람·구름 GFS"), "fetch_gfs_wind"),
    Item("wind/gmgsi", "WIND_DIR", "gmgsi", msg("위성 구름 GMGSI"), "fetch_gmgsi"),
    Item("wind/era5", "WIND_DIR", "era5", msg("지난 바람 ERA5"), "build_era5_wind"),
    Item("ocean/ecco2", "OCEAN_DIR", "ecco2", msg("해류 ECCO2"), "build_ecco2"),
    # 달·화성·수성
    Item("moon/moon_originals.sqlite", "MOON_DIR", "moon_originals.sqlite", msg("달 지질도 원도"), "build_moon_originals"),
    Item("moon/spa_geomap_iqbal2026.tif", "MOON_DIR", "spa_geomap_iqbal2026.tif", msg("남극–에이트켄 분지 지질도"), "(손으로 둔다)"),
    Item("mars/mars_craters.sqlite", "MARS_DIR", "mars_craters.sqlite", msg("화성 크레이터"), "build_mars_craters"),
    Item("mars/mars_originals.sqlite", "MARS_DIR", "mars_originals.sqlite", msg("화성 옛 지질도"), "build_mars_originals"),
    Item("mercury/mercury_geology.sqlite", "MERCURY_DIR", "mercury_geology.sqlite", msg("수성 지질도"), "build_mercury_geology"),
    # 모아 둔 목록
    Item("kopri/rock.json", "KOPRI_DIR", "rock.json", msg("극지연구소 암석 시료"), "fetch_kopri"),
    Item("kopri/kpdc.json", "KOPRI_DIR", "kpdc.json", msg("극지연구소 KPDC 자료"), "fetch_kopri"),
    Item("kopri/araon.jsonl", "KOPRI_DIR", "araon.jsonl", msg("아라온호 항적"), "fetch_araon"),
    Item("kopri/araon_past.json", "KOPRI_DIR", "araon_past.json", msg("아라온호 지난 1 년"), "fetch_araon --past"),
    Item("kigam_data/data.json", "KIGAM_DATA_DIR", "data.json", msg("KIGAM 자료 목록"), "fetch_kigam_data"),
    Item("kigam50k/raw", "KIGAM50K_DIR", "raw", msg("KIGAM 5만 구조 요소"), "fetch_kigam50k"),
    Item("sgb/units.json", "SGB_DIR", "units.json", msg("브라질 지질 단위 이름표"), "fetch_sgb_units"),
    # 연구실 내부용
    Item("peninsula/tiles", "PENINSULA_DIR", "tiles", msg("한반도 지질도 음영판"), "build_peninsula", lab=True),
    Item("peninsula/tiles-plain", "PENINSULA_DIR", "tiles-plain", msg("한반도 지질도 민판"), "build_peninsula", lab=True),
    Item("usgs/geo3al", "USGS_DIR", "geo3al", msg("중국 USGS geo3al"), "(손으로 둔다)", lab=True),
]
# 대만 지질운 열린자료(wetherilli 305) — 그 판이 들어온 뒤에만
if hasattr(settings, "TAIWAN_OPEN_DIR"):
    ITEMS.append(Item("taiwan_open", "TAIWAN_OPEN_DIR", "", msg("대만 지질운 열린자료"), "fetch_taiwan_open"))


def _sqlite_version(path: Path) -> str:
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = dict(db.execute("SELECT k, v FROM meta").fetchall())
        finally:
            db.close()
    except sqlite3.Error:
        return ""
    return " · ".join(f"{k} {rows[k]}" for k in _META_KEYS if rows.get(k))[:120]


def _json_version(path: Path) -> str:
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096).decode("utf-8", "replace")
    except OSError:
        return ""
    seen = {}
    for k, v in _HEAD.findall(head):
        seen.setdefault(k, v)
    return " · ".join(f"{k} {v}" for k, v in seen.items())[:120]


def _index_span(folder: Path) -> str:
    """바람·해류처럼 `index.json` 의 `times` 를 두는 폴더 — 첫·끝 시점. 2 MB 를 넘으면 읽지 않는다"""
    index = folder / "index.json"
    try:
        if index.stat().st_size > 2_000_000:
            return ""
        times = json.loads(index.read_text(encoding="utf-8")).get("times") or []
    except (OSError, ValueError, AttributeError):
        return ""
    if not times:
        return ""
    first, last = str(times[0].get("t", "")), str(times[-1].get("t", ""))
    return first if first == last else f"{first} – {last}"


def _row(item: Item) -> dict:
    path = item.path()
    needed = _needed(item)
    row = {"key": item.key, "what": item.what, "command": item.command, "needed": needed, "exists": False,
           "size": None, "count": None, "modified": None, "version": ""}
    if item.key.endswith("*.gpkg"):                       # GeoMAP 은 판이 이름에 든다
        found = sorted(path.glob(item.key.split("/", 1)[1])) if path.is_dir() else []
        if not found:
            return row
        path = found[-1]
        found_v = re.search(r"_v(\d{4})_(\d{2})", path.stem)       # ATA_SCAR_GeoMAP_Geology_v2022_08 → 2022-08
        row["version"] = f"{found_v.group(1)}-{found_v.group(2)}" if found_v else ""
    try:
        st = path.stat()
    except OSError:
        return row
    row["exists"] = True
    row["modified"] = datetime.fromtimestamp(st.st_mtime)
    if path.is_dir():
        try:
            entries = list(path.iterdir())
        except OSError:
            entries = []
        row["count"] = len(entries)
        if entries:
            newest = max(entries, key=lambda e: e.stat().st_mtime if e.exists() else 0)
            row["modified"] = datetime.fromtimestamp(max(st.st_mtime, newest.stat().st_mtime))
            row["version"] = row["version"] or _index_span(path) or (newest.name if _DATE.fullmatch(newest.name) else "")
    else:
        row["size"] = st.st_size
        if path.suffix == ".sqlite":
            row["version"] = _sqlite_version(path)
        elif path.suffix in (".json", ".jsonl"):
            row["version"] = row["version"] or _json_version(path)
    return row


def rows() -> list:
    return [_row(item) for item in ITEMS]


def _needed(item: Item) -> bool:
    return item.needed and not (item.lab and settings.PUBLIC)


def _exists(item: Item) -> bool:
    path = item.path()
    if item.key.endswith("*.gpkg"):
        return path.is_dir() and any(path.glob(item.key.split("/", 1)[1]))
    return path.exists()


def missing(table=None) -> list:
    """있어야 하는데 없는 것의 이름. 표를 주지 않으면 있는지만 본다(`stat` 만 — healthz 가 부른다)"""
    if table is not None:
        return [r["key"] for r in table if r["needed"] and not r["exists"]]
    return [item.key for item in ITEMS if _needed(item) and not _exists(item)]


def human_size(n) -> str:
    if n is None:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""
