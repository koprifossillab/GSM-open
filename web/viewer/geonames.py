"""온 세계의 도시 이름 — GeoNames `cities1000`(인구 1 000 이상 17 만 곳, CC BY 4.0)을 sqlite 로 굽고 이름으로 찾는다 (wetherilli 374).

`manage.py build_geonames <폴더>` 가 받아 둔 파일 셋(`cities1000.zip`·`admin1CodesASCII.txt`, 그리고 나라 이름을 한국어로
옮기려고 Natural Earth 의 `ne_10m_admin_0_countries.zip`)에서 `<EARTH_DIR>/geonames.sqlite` 를 굽는다. 화면이 찾을 때는
이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다. 20 MB 남짓이라 저장소에 두지 않는다.

- 온 지구의 찾기(Natural Earth 1 만여 이름)와 **지역 탭 가운데 주소·지명 찾기가 없던 곳**의 찾기가 쓴다
- 이름은 GeoNames 의 이름·ASCII 이름으로, 별칭 가운데 **한글인 것**(8 천 곳 남짓)과 **로마자인 것**(München·Wien)으로도 찾는다.
  보이는 한국어 이름은 한글 별칭 하나다. 나라 밖의 큰 도시는 Natural Earth 가 한국어 이름을 준다
- 같은 이름 → 앞이 같은 것 → 들어 있는 것 차례, 같으면 **보는 범위 안**의 것, 그다음 인구가 많은 것이 먼저다
"""
import functools
import io
import re
import sqlite3
import time
import zipfile
from pathlib import Path

from django.conf import settings

from . import arcpoints

CREDIT = "GeoNames (CC BY 4.0)"
HANGUL = re.compile("[가-힣]")
#: 찾기에 넣는 별칭 — 로마자 것만(München·Wien). 온갖 글자의 별칭을 다 넣으면 파일이 두 배가 된다
LATIN = re.compile("^[ -ɏḀ-ỿʼ’]+$")
SCHEMA = """
CREATE TABLE city (id INTEGER PRIMARY KEY, name TEXT, ko TEXT, cc TEXT, admin1 TEXT, lon REAL, lat REAL, pop INTEGER,
                   keys TEXT);
CREATE TABLE country (cc TEXT PRIMARY KEY, en TEXT, ko TEXT);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""


def path() -> Path:
    return Path(settings.EARTH_DIR) / "geonames.sqlite"


def keys(*names) -> str:
    """찾기 열 — 접은 이름들을 `|` 로 감싼다. 같은 이름은 `|이름|`, 앞이 같은 것은 `|이름` 으로 `LIKE` 한 번에 가른다."""
    folded = [f for f in dict.fromkeys(arcpoints.fold(n) for n in names if n) if f]
    return "|" + "|".join(folded) + "|"


def read_cities(text: str, admin1: dict):
    """`cities1000.txt` 의 줄 → (id, 이름, 한글 이름, 나라, 도·주, 경도, 위도, 인구, 찾기 열)."""
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) < 15:
            continue
        alts = [a for a in c[3].split(",") if a]
        hangul = [a for a in alts if HANGUL.search(a)]
        latin = [a for a in alts if LATIN.match(a)]
        # 한글 별칭이 여럿이면(빈·비엔나, 상파울로·상파울루) 모두 `|` 로 담고, 보일 때 찾은 말이 든 것을 고른다
        ko = "|".join(hangul)
        yield (int(c[0]), c[1], ko, c[8], admin1.get(f"{c[8]}.{c[10]}", ""), round(float(c[5]), 4),
               round(float(c[4]), 4), int(c[14] or 0), keys(c[1], c[2], *hangul, *latin))


def read_admin1(text: str) -> dict:
    """`admin1CodesASCII.txt` → {'KR.11': 'Seoul', …}"""
    out = {}
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) >= 2:
            out[c[0]] = c[1]
    return out


def build(folder, out_path=None, countries=None) -> dict:
    """받아 둔 폴더 → sqlite. `countries` 는 [(ISO 두 글자, 영어 이름, 한국어 이름)] — 부르는 쪽이 Natural Earth 에서 뽑아 넘긴다."""
    folder = Path(folder)
    out_path = Path(out_path or path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    admin1 = read_admin1((folder / "admin1CodesASCII.txt").read_text(encoding="utf-8"))
    with zipfile.ZipFile(folder / "cities1000.zip") as zf:
        text = io.TextIOWrapper(zf.open("cities1000.txt"), encoding="utf-8").read()
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    rows = list(read_cities(text, admin1))
    db.executemany("INSERT OR REPLACE INTO city VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    db.executemany("INSERT OR REPLACE INTO country VALUES (?, ?, ?)", countries or [])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("built", time.strftime("%Y-%m-%d")), ("rows", str(len(rows))),
        ("source", "download.geonames.org/export/dump cities1000"), ("license", "CC BY 4.0")])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    _open.cache_clear()
    return {"rows": len(rows), "korean": sum(1 for r in rows if r[2]), "seconds": round(time.time() - started)}


# ── 읽기 ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _open(mtime):
    db = sqlite3.connect(f"file:{path()}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def db():
    """구운 파일. 없으면 None."""
    try:
        return _open(path().stat().st_mtime)
    except (FileNotFoundError, sqlite3.OperationalError):
        return None


def available() -> bool:
    return db() is not None


def _like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _korean(names: str, query: str) -> str:
    """한글 별칭 가운데 보일 것 — 찾은 말이 든 것, 없으면 가나다 끝의 것(빈·비엔나 → 빈, 상파울로·상파울루 → 상파울루).
    한국 도시는 옛 이름(경성·한양)이 섞여 맞지 않을 수 있지만 Natural Earth 의 이름이 앞서 겹친 것을 지운다"""
    names = names.split("|")
    return next((n for n in names if query.strip() and query.strip() in n), names[-1])


def search(query: str, lang: str = "ko", bbox=None, limit: int = 12) -> list:
    """이름에 `query` 가 든 도시. `bbox`(서·남·동·북 경위도)를 주면 그 안의 것을 앞세운다 — 서가 동보다 크면 날짜변경선을 넘는다.
    화면의 찾기 결과 꼴(`title`·`sub`·`lat`·`lon`)에 같은 이름의 차례(`match`)와 범위 안인지(`inside`)를 붙여 준다."""
    conn = db()
    q = arcpoints.fold(query)
    if conn is None or len(q) < 2 or "|" in q:
        return []
    like = _like(q)
    inside = "0"
    args = []
    if bbox:
        west, south, east, north = bbox
        lon_ok = "(lon BETWEEN ? AND ?)" if west <= east else "(lon >= ? OR lon <= ?)"
        inside = f"({lon_ok} AND lat BETWEEN ? AND ?)"
        args = [west, east, south, north]
    rows = conn.execute(
        "SELECT c.name, c.ko, c.keys, c.admin1, c.lon, c.lat, c.pop, n.en, n.ko AS country_ko, "
        "CASE WHEN keys LIKE ? ESCAPE '\\' THEN 0 WHEN keys LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END AS match, "
        f"{inside} AS inside FROM city c LEFT JOIN country n ON n.cc = c.cc WHERE keys LIKE ? ESCAPE '\\' "
        "ORDER BY match, inside DESC, pop DESC LIMIT ?",
        [f"%|{like}|%", f"%|{like}%"] + args + [f"%{like}%", limit]).fetchall()
    out = []
    for r in rows:
        main = _korean(r["ko"], query) if lang == "ko" and r["ko"] else r["name"]
        # 다른 이름으로 맞았으면 괄호로 곁들인다 — `arcpoints.match_index` 와 같은 꼴, 화면은 괄호를 떼고 옮겨 간다
        other = ""
        if q not in arcpoints.fold(main):
            # 별칭으로 맞았으면 그 별칭을(접은 꼴이다 — Emerson (etna)), 한국어 이름이면 원래 이름을 곁들인다
            aliases = [k for k in r["keys"].strip("|").split("|") if q in k]
            aliases.sort(key=lambda k: (k != q, not k.startswith(q), len(k)))
            other = r["name"] if q in arcpoints.fold(r["name"]) or not aliases else aliases[0]
            other = "" if other == main else other
        country = (r["country_ko"] if lang == "ko" else "") or r["en"] or ""
        out.append({"title": f"{main} ({other})" if other else main,
                    "sub": " · ".join(x for x in (r["admin1"], country) if x),
                    "lat": r["lat"], "lon": r["lon"], "match": r["match"], "inside": bool(r["inside"])})
    return out
