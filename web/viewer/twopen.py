"""대만 지질운의 열린자료 — WMS 그림이 없는 탄층·토석류·낙석·GPS 상시 관측소·암체 강도 등급을 한 덩이씩 화면에 (wetherilli 305).

받기는 문(`gsmma.fetch_open`)이 하고 `manage.py fetch_taiwan_open` 이 `TAIWAN_OPEN_DIR` 에 GeoJSON 으로 둔다. 이 모듈은 그 파일만 읽는다 —
화면이 부를 때 상류를 타지 않는다. 문이 아니다. 그리는 것은 파나마·카리브와 같은 길(`/points/`, `kind: points`)이다.

- **5만 탄층**(CoalSeam, 선 146) — 검은 선
- **토석류**(DebrisFlowDeposition 퇴적 298·Fan 선상 214·Track 유동구 1 046) — 한 레이어에 갈래 셋. 10 MB 라 약 5 m 로 줄여 1.8 MB(gzip 0.4 MB)
- **낙석**(RockFall, 면 1 만 6 천) — 활동(`ACTIVITY`)의 앞 글자(A 새·잦음, B 옛·가끔, C 없음)로 칠한다. 32 MB 라 약 6 m 로 줄여 6.6 MB(gzip 0.8 MB)
- **GPS 상시 관측소**(CGPS, 점 65)
- **암체 강도 등급**(RockMassClassification, 면 3 084) — 등급 I–VII. 지질운이 등급의 뜻을 적지 않아 **값 그대로 갈래 색**으로 칠한다(차례를 뜻하는
  색띠를 쓰지 않는다). 같은 면의 "암석 강도"(RockMassStrength, A–H)는 모양이 똑같아 받지 않았다. 28 MB 라 약 20 m 로 줄여 3.5 MB(gzip 0.7 MB). 줄이다 사라질 작은 면은 줄이지 않는다
- 값(중국어)은 옮기지 않는다 — 속성 값이다. 팝업의 이름만 옮긴다
- 조건: 지질운 소개(`geohome/Introduction`) — "지질 자료는 공공재, 사성급 열린자료로 공급". 출처를 밝힌다(wetherilli 136·263)
"""
import functools
import json
import math
from pathlib import Path

from django.conf import settings

from . import tectonics
from .i18n import msg

PREFIX = "gsmma:open:"
SOURCE_URL = "https://www.geologycloud.tw/data/zh-tw"
ATTRIBUTION = ('地質雲 © <a href="https://www.geologycloud.tw/" target="_blank" rel="noopener">經濟部地質調查及礦業管理中心</a> — 開放資料')

#: 레이어 → 갈래(파일)·그리는 꼴·팝업 열(원본 열 → 한국어 이름)
LAYERS = {
    "gsmma:open:coal": {"apis": ["CoalSeam"], "style": "line",
                        "fields": {"Code": "기호", "Name": "이름", "Note": "비고"}},
    "gsmma:open:debris": {"apis": ["DebrisFlowDeposition", "DebrisFlowFan", "DebrisFlowTrack"], "style": "class", "tolerance": 0.00005,
                          "fields": {"FAN_AREA": "선상지 넓이", "PROT_TARG": "보호 대상", "CHAN_WIDTH": "하도 폭", "CHAN_ANGLE": "하도 경사",
                                     "CHAN_VEGE": "하도 식생", "CONSTRUCT": "정비", "CONST_NOW": "정비 상태", "TRAFFIC": "교통 영향",
                                     "SITECHECK": "현장 확인", "IDENTIFIER": "조사자"}},
    "gsmma:open:rockfall": {"apis": ["RockFall"], "style": "class", "tolerance": 0.00006,
                            "fields": {"ACTIVITY": "활동", "MAP_NAME": "도폭", "COUN_NAME": "시군", "IDEN_DATE": "판독일",
                                       "IDENTIFIER": "조사자", "RF_AREA": "넓이 (m²)"}},
    "gsmma:open:cgps": {"apis": ["CGPS"], "style": "class",
                        "fields": {"CGPS_ID": "관측소", "NAME": "이름", "CGPS_TYPE": "갈래", "UNIT": "기관", "TWD97H": "높이 (m)",
                                   "REMARK": "비고"}},
    "gsmma:open:rockmass": {"apis": ["RockMassClassification"], "style": "unit", "tolerance": 0.0002,
                            "fields": {"強度分級": "강도 등급", "ST_C": "지층", "ABBREV": "기호", "LITH_C": "암상"}},
}
#: 토석류 갈래 → (색, 범례 이름)
DEBRIS = {"DebrisFlowDeposition": ("#b35806", "토석류 퇴적 구역"), "DebrisFlowFan": ("#f1a340", "토석류 선상 구역"),
          "DebrisFlowTrack": ("#7f3b08", "토석류 유동 구역")}
#: 낙석 활동의 앞 글자 → 색. 이름은 자료의 값(중국어) 그대로 범례에 쓴다
ROCKFALL = {"A": "#d73027", "B": "#fc8d59", "C": "#91bfdb", "D": "#4575b4"}
#: 암체 강도 등급 → 색 (갈래 색 — 차례를 뜻하지 않는다)
ROCKMASS = {"I": "#1b9e77", "II": "#d95f02", "III": "#7570b3", "IV": "#e7298a", "V": "#66a61e", "VI": "#e6ab02", "VII": "#a6761d"}


def knows(name: str) -> bool:
    return name in LAYERS


def folder() -> Path:
    return Path(settings.TAIWAN_OPEN_DIR)


def _path(api: str) -> Path:
    return folder() / f"{api}.geojson"


def available(name: str) -> bool:
    return knows(name) and all(_path(a).exists() for a in LAYERS[name]["apis"])


def _mtime(name: str) -> float:
    return max(_path(a).stat().st_mtime for a in LAYERS[name]["apis"])


def forget():
    _body.cache_clear()


def _value(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    text = str(v).strip()
    return "" if text.lower() in ("null", "none") else text


def _ring(coords, tol):
    pts = [(round(x, 5), round(y, 5)) for x, y, *_ in coords]
    if tol:
        thin = tectonics.simplify(pts, tol)
        pts = thin if len(thin) >= 4 else pts        # 줄이다 사라질 작은 면은 줄이지 않고 둔다
    if len(pts) < 4:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return [list(p) for p in pts]


def _shrink(geometry, tol):
    """면을 줄이고 소수 다섯째 자리로 — 줄이다 사라지는 고리는 버린다"""
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Polygon":
        rings = [r for r in (_ring(c, tol) for c in coords) if r]
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if kind == "MultiPolygon":
        polys = [[r for r in (_ring(c, tol) for c in poly) if r] for poly in coords]
        polys = [p for p in polys if p]
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    if kind == "LineString":
        return {"type": "LineString", "coordinates": [[round(x, 5), round(y, 5)] for x, y, *_ in coords]}
    if kind == "MultiLineString":
        return {"type": "MultiLineString", "coordinates": [[[round(x, 5), round(y, 5)] for x, y, *_ in line] for line in coords]}
    if kind == "Point":
        return {"type": "Point", "coordinates": [round(coords[0], 5), round(coords[1], 5)]}
    return None


def _code(name: str, api: str, props: dict) -> str:
    if name == "gsmma:open:debris":
        return api
    if name == "gsmma:open:rockfall":
        return _value(props.get("ACTIVITY")) or "?"
    if name == "gsmma:open:rockmass":
        return _value(props.get("強度分級")) or "?"
    return {"gsmma:open:coal": "coal", "gsmma:open:cgps": "cgps"}[name]


def _legend(name: str, counts: dict, t) -> list:
    if name == "gsmma:open:coal":
        return [{"code": "coal", "label": t("5만 탄층"), "color": "#1a1a1a", "width": 1.6, "count": counts.get("coal", 0)}]
    if name == "gsmma:open:cgps":
        return [{"code": "cgps", "label": t("GPS 상시 관측소"), "color": "#2166ac", "shape": "triangle", "count": counts.get("cgps", 0)}]
    if name == "gsmma:open:debris":
        return [{"code": k, "label": t(label), "color": color, "count": counts.get(k, 0)} for k, (color, label) in DEBRIS.items()
                if counts.get(k)]
    if name == "gsmma:open:rockfall":
        return [{"code": k, "label": t("활동 적지 않음") if k == "?" else k, "color": ROCKFALL.get(k[:1], "#888888"), "count": n}
                for k, n in sorted(counts.items(), key=lambda kv: (kv[0] == "?", kv[0]))]
    rows = [{"code": k, "label": t("등급 {grade}", grade=k), "color": ROCKMASS[k], "count": counts.get(k, 0)}
            for k in ROCKMASS if counts.get(k)]
    if counts.get("?"):
        rows.append({"code": "?", "label": t("등급 없음"), "color": "#cccccc", "count": counts["?"]})
    return rows


@functools.lru_cache(maxsize=16)
def _body(name: str, lang: str, mtime: float) -> bytes:
    from .i18n import PROP_EN, msg, t as translate
    spec = LAYERS[name]

    def t(text, **params):
        return translate(msg(text, **params), lang)
    items, counts, fetched = [], {}, ""
    for api in spec["apis"]:
        data = json.loads(_path(api).read_text(encoding="utf-8"))
        fetched = max(fetched, data.get("fetched", ""))
        for f in data.get("features") or []:
            geometry = _shrink(f.get("geometry") or {}, spec.get("tolerance", 0))
            if geometry is None:
                continue
            raw = f.get("properties") or {}
            code = _code(name, api, raw)
            props = {"code": code}
            if name == "gsmma:open:rockmass":
                props["color"] = ROCKMASS.get(code, "#cccccc")
            for key in spec["fields"]:
                value = _value(raw.get(key))
                if value:
                    props[key] = value
            if name == "gsmma:open:debris":
                props["kind"] = t(DEBRIS[api][1])
            items.append({"type": "Feature", "geometry": geometry, "properties": props})
            counts[code] = counts.get(code, 0) + 1
    labels = {k: (PROP_EN.get(v, v) if lang == "en" else v) for k, v in spec["fields"].items()}
    if name == "gsmma:open:debris":
        labels = {"kind": PROP_EN.get("갈래", "갈래") if lang == "en" else "갈래", **labels}
    out = {"type": "FeatureCollection", "labels": labels, "style": spec["style"], "legend": _legend(name, counts, t),
           "fetched": fetched, "features": items}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 꼴은 `stri.body` 와 같다. 파일이 없으면 FileNotFoundError"""
    if not knows(name):
        raise KeyError(name)
    return _body(name, lang, _mtime(name))


def size_note(raw_bytes: int, sent_bytes: int) -> str:
    return f"{raw_bytes / 1e6:.1f} MB → {sent_bytes / 1e6:.1f} MB ({math.floor(100 * sent_bytes / max(raw_bytes, 1))}%)"


# ── 지질 민감구역 — 누른 자리가 어느 구역인가 (wetherilli 336) ─────────────
#
# 그림은 GSMMA 의 WMS 그대로이고, 누르기만 여기서 한다. `fetch_taiwan_open --sensitive` 가 구역 면을 `sensitive.sqlite` 에 담는다 —
# 면 조각(다각형)마다 한 줄, 범위는 R*Tree. 속성은 지질운이 주지 않아(`Gid` 뿐) 공고 목록에서 붙인 번호·이름·공고일·문호다

SENSITIVE_FILE = "sensitive.sqlite"
#: 갈래 기호 → 팝업의 갈래 이름(옮긴다)
SENSITIVE_KINDS = {"F": msg("활성단층 민감구역"), "G": msg("지하수 함양 민감구역"), "H": msg("지질 유산 민감구역"), "L": msg("산사태·지활 민감구역")}


def _parts(geometry: dict) -> list:
    kind = (geometry or {}).get("type")
    coords = (geometry or {}).get("coordinates") or []
    return [coords] if kind == "Polygon" else list(coords) if kind == "MultiPolygon" else []


def _sensitive_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS area (id INTEGER PRIMARY KEY, kind TEXT, code TEXT, name TEXT, town TEXT, date TEXT, doc TEXT, rings TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS area_box USING rtree(id, w, e, s, n);
        CREATE TABLE IF NOT EXISTS done (key TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS missing (key TEXT PRIMARY KEY, reason TEXT);""")


def open_sensitive(path: Path):
    """받을 자리(`<이름>.part`)를 연다 — (db, 받은 열쇠들, 앞서 못 받은 [(열쇠, 까닭)]). 이어 받기 (wetherilli 346)

    `.part` 가 있으면 거기서 잇는다(앞서 멈췄다). 없고 다 지은 파일에 못 받은 것이 적혀 있으면 그것을 `.part` 로 베껴 잇는다 —
    못 받은 것만 다시 묻는다. 아니면 새로 시작한다"""
    import shutil
    import sqlite3
    part = path.with_suffix(".part")
    if not part.exists() and path.exists():
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            left = db.execute("SELECT count(*) FROM missing").fetchone()[0]
            db.close()
        except sqlite3.Error:            # 옛 판(wetherilli 336)의 파일 — 받은 열쇠를 적지 않았다
            left = 0
        if left:
            shutil.copyfile(path, part)
    db = sqlite3.connect(part)
    if part.exists() and not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'done'").fetchone():
        # 옛 판(wetherilli 336)이 멈추며 남긴 것 — 어느 묻기를 받았는지 적지 않아 이으면 겹친다. 버리고 새로
        db.close()
        part.unlink()
        db = sqlite3.connect(part)
    _sensitive_tables(db)
    done = {k for (k,) in db.execute("SELECT key FROM done")}
    missing = list(db.execute("SELECT key, reason FROM missing"))
    return db, done, missing


def add_sensitive(db, key: str, areas) -> int:
    """묻기 하나의 구역들을 담고 열쇠를 받은 것으로 적는다 — 한 거래라 멈춰도 반쯤 담긴 묻기가 없다. 담은 조각 수"""
    n = 0
    with db:
        for a in areas:
            for rings in _parts(a.get("geometry")):
                rings = [[[round(p[0], 6), round(p[1], 6)] for p in ring] for ring in rings if ring]
                if not rings:
                    continue
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                cur = db.execute("INSERT INTO area (kind, code, name, town, date, doc, rings) VALUES (?,?,?,?,?,?,?)",
                                 (a["kind"], a.get("code", ""), a.get("name", ""), a.get("town", ""), a.get("date", ""), a.get("doc", ""),
                                  json.dumps(rings, separators=(",", ":"))))
                db.execute("INSERT INTO area_box VALUES (?,?,?,?,?)", (cur.lastrowid, min(xs), max(xs), min(ys), max(ys)))
                n += 1
        db.execute("INSERT OR IGNORE INTO done VALUES (?)", (key,))
        db.execute("DELETE FROM missing WHERE key = ?", (key,))
    return n


def close_sensitive(db, path: Path, missing: list) -> int:
    """받은 만큼 다 지은 파일을 쓴다 — 조각 수. 못 받은 것이 남으면 파일에 적어 두고 `.part` 도 남긴다(다시 부르면 그것만 묻는다)"""
    import shutil
    part = path.with_suffix(".part")
    with db:
        db.execute("DELETE FROM missing")
        db.executemany("INSERT OR REPLACE INTO missing VALUES (?, ?)", missing)
    n = db.execute("SELECT count(*) FROM area").fetchone()[0]
    db.close()
    if missing:
        tmp = path.with_suffix(".tmp")
        shutil.copyfile(part, tmp)
        tmp.replace(path)
    else:
        part.replace(path)
    return n


def write_sensitive(batches, path: Path) -> int:
    """[(열쇠, 구역들)] → 처음부터 다 지은 파일 (시험·손으로 담을 때)"""
    path.with_suffix(".part").unlink(missing_ok=True)
    db, _, _ = open_sensitive(path)
    for key, areas in batches:
        add_sensitive(db, key, areas)
    return close_sensitive(db, path, [])


def sensitive_at(kind: str, lon: float, lat: float) -> list:
    """누른 자리를 품은 `kind` 갈래 구역 — 팝업 열(`gsmma.FRIENDLY` 의 `Sens*`). 파일이 없으면 빈 것"""
    import sqlite3
    from . import gsmma
    path = folder() / SENSITIVE_FILE
    if not path.exists():
        return []
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = db.execute("""SELECT a.code, a.name, a.town, a.date, a.doc, a.rings FROM area_box b JOIN area a ON a.id = b.id
                             WHERE b.w <= ? AND b.e >= ? AND b.s <= ? AND b.n >= ? AND a.kind = ?""", (lon, lon, lat, lat, kind)).fetchall()
    finally:
        db.close()
    out, seen = [], set()
    for code, name, town, date, doc, rings in rows:
        if (code, town) in seen or not gsmma.contains({"type": "Polygon", "coordinates": json.loads(rings)}, lon, lat):
            continue
        seen.add((code, town))
        props = {"SensKind": str(SENSITIVE_KINDS[kind]), "SensName": name, "SensCode": code, "SensTown": town, "SensDate": date, "SensDoc": doc}
        out.append({k: v for k, v in props.items() if v})
    return out
