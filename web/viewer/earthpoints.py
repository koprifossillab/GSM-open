"""지역 탭의 지구 자료 점 — 화석 산지(PBDB)·홀로세 화산(GVP)·지진(USGS)·제4기 고생태 산지(Neotoma) (wetherilli 185),
지열류(IHFC, wetherilli 275). 그리고 온 지구 화면에 구워 둔 선·면·막대 — 활성단층(GEM)·판 경계와 지질구(Hasterok)·지각 응력(WSM)·
세계 광상(USGS) (wetherilli 390). 이름은 "점" 이지만 선·면도 같은 덩이로 낸다 — 화면의 `classStyle` 이 범례 줄의 모양대로 그린다.

온 지구 화면이 경위도 타일로 그리는 것을, 지역 탭은 **점 레이어**(`kind: points`)로 받는다 — 지역의 네모 안만 잘라
극지연구소 파일 레이어(`kopri.file_body`)와 같은 꼴의 GeoJSON 으로 낸다. 화면이 제 투영(3857·3413·3031)으로 옮겨 그리고,
누르면 속성이 팝업에 선다. 자료는 모아 둔 sqlite·JSON(`fossils`·`volcanoes`·`quakes`·`paleoeco`)이라 상류를 타지 않는다.
오늘의 것만 싣는다 — 옛 연대로 옮기는 일은 온 지구 화면의 몫이다. 문이 아니다.
"""
import functools
import json
import os
import re

from django.conf import settings

from . import (faults, fossils, gvp, heatflow, i18n, minerals, neotoma, paleoeco, pbdb, quakes, recentquakes, stress, tectonics,
               usgs, volcanoes)
from .i18n import msg

#: 지역 → 자르는 네모 (서, 남, 동, 북). 북극은 북극해에 두고 그린란드·스발바르·얀마옌·노르웨이·핀란드가 빌린다(`borrow`) —
#: 노르웨이 남쪽 끝(58°N)까지 품는다
BOXES = {
    "korea": (123.0, 32.0, 132.5, 43.5),
    "antarctica": (-180.0, -90.0, 180.0, -60.0),
    "arctic": (-180.0, 58.0, 180.0, 90.0),
    # 묶음마다 네모 하나 — 묶음의 한 탭(`HOSTS`)에 두고 나머지 나라 탭이 빌린다(`map.js` 의 `borrow`) (wetherilli 331)
    "eastasia": (73.0, 18.0, 150.0, 54.0),
    "southeast_asia": (92.0, -11.0, 141.0, 21.0),
    "southasia": (34.0, 5.0, 98.0, 38.0),
    "europe": (-25.0, 35.0, 41.0, 72.0),
    "north_america": (-170.0, 14.0, -50.0, 84.0),
    "central_america": (-93.0, 7.0, -59.0, 24.0),
    "south_america": (-82.0, -56.0, -34.0, 13.0),
    "oceania": (110.0, -48.0, 180.0, -8.0),
    "africa": (-20.0, -36.0, 52.0, 38.0),
}
#: 네모 → 레이어를 두는 지역 탭, 제목에 붙일 이름. 한국·남극·북극은 앞 판 그대로 제목에 이름을 붙이지 않는다
HOSTS = {"eastasia": ("japan", "동아시아"), "southeast_asia": ("indonesia", "동남아"), "southasia": ("india", "남·서아시아"),
         "europe": ("uk", "유럽"), "north_america": ("usa", "북미"), "central_america": ("caribbean", "중미·카리브"),
         "south_america": ("brazil", "남미"), "oceania": ("australia", "오세아니아"), "africa": ("africa", "아프리카")}
#: 덩이 하나의 점이 이보다 많으면 가까운 점을 한 칸으로 모은다(`_merge`) — 유럽 화석 산지 7 만·북미 8 만 5 천은 화면이 받기 무겁다 (wetherilli 331)
CAP = 20000
#: 모으는 칸(°) — 가는 것부터 써서 `CAP` 밑으로 떨어지는 첫 칸
MERGE_CELLS = (0.01, 0.05, 0.1, 0.2, 0.5)
SOURCES = ("pbdb", "gvp", "quakes", "neotoma", "heatflow", "recentquakes", "faults", "plates", "provinces", "stress", "minerals")
#: 레이어 이름 `earth:<자료>_<네모>` → (자료, 네모)
LAYERS = {f"earth:{src}_{box}": (src, box) for src in SOURCES for box in BOXES}

#: 소수 자리 — 5 자리면 1 m 남짓이다
DIGITS = 5

#: 화석 산지의 색 — 산지 연대의 가운데가 든 기(period). `fossils.PERIODS` 와 같은 차례·색이다
PERIOD_NAMES = (msg("제4기"), msg("신진기"), msg("고진기"), msg("백악기"), msg("쥐라기"), msg("트라이아스기"),
                msg("페름기"), msg("석탄기"), msg("데본기"), msg("실루리아기"), msg("오르도비스기"), msg("캄브리아기"),
                msg("선캄브리아"))

#: 팝업의 열 — 열쇠 → 이름(한국어, 영어판은 화면이 `PROP_EN` 으로 옮긴다). 차례가 팝업의 차례다
LABELS = {
    "pbdb": {"name": "산지", "formation": "지층", "age": "시대", "ma": "연대 (Ma)", "env": "퇴적 환경",
             "occs": "화석 수", "cc": "나라", "ref": "첫 문헌", "link": "PBDB 산지 페이지"},
    "gvp": {"name": "화산", "type": "화산 종류", "last": "마지막 분화", "evidence": "근거", "country": "나라",
            "elev": "표고 (m)", "tectonic": "지구조 환경", "rock": "주 암석", "link": "GVP 화산 페이지"},
    "quakes": {"mag": "규모", "time": "일시 (UTC)", "depth": "깊이 (km)", "place": "곳", "link": "USGS 지진 페이지"},
    # 최근 지진(wetherilli 292) — 지난 지진과 같은 열, 색만 지난 시간이다
    "recentquakes": {"mag": "규모", "time": "일시 (UTC)", "depth": "깊이 (km)", "place": "곳", "link": "USGS 지진 페이지"},
    "neotoma": {"name": "산지", "desc": "설명", "alt": "표고 (m)", "types": "자료", "link": "Neotoma 산지 페이지"},
    # 지열류(wetherilli 275) — IHFC 는 측정마다 쪽이 없어 링크가 없다
    "heatflow": {"q": "지열류 (mW/m²)", "unc": "오차 (mW/m²)", "name": "자리", "env": "환경", "method": "잰 법", "year": "해",
                 "quality": "품질", "ref": "문헌"},
    # 온 지구 화면의 팝업과 같은 열이다 (`faults.near`·`tectonics.province_at`·`views.earth_stress_at`·`earth_minerals_at`, wetherilli 390)
    "faults": {"name": "단층", "kind": "갈래", "slip": "미끄럼 (원문)", "dip": "경사 (°)", "dipdir": "경사 방향", "rake": "레이크 (°)",
               "rate": "미끄럼 속도 (mm/yr)", "depth": "지진 발생 깊이 (km)", "catalog": "원 목록"},
    "plates": {"kind": "갈래", "plates": "판", "comment": "설명"},
    "provinces": {"name": "지질구", "kind": "갈래", "group": "묶음", "orogen": "마지막 조산 운동", "continent": "대륙", "crust": "지각"},
    "stress": {"azi": "최대 수평 응력 방향", "regime": "응력 체제", "quality": "품질", "type": "측정법", "depth": "깊이 (km)",
               "place": "곳", "mag": "규모", "date": "일시", "ref": "참고 문헌"},
    "minerals": {"name": "광상", "commodity": "광종", "status": "상태", "kind": "광상 유형", "country": "나라", "link": "USGS 쪽"},
}
LINKS = ("link",)
CREDITS = {"pbdb": pbdb.CREDIT, "gvp": gvp.CREDIT, "quakes": usgs.CREDIT, "neotoma": neotoma.CREDIT,
           "heatflow": heatflow.CREDIT, "recentquakes": usgs.CREDIT, "faults": faults.CITE, "plates": tectonics.CITE,
           "provinces": tectonics.CITE, "stress": stress.CREDIT, "minerals": minerals.CREDIT}
#: 범례 칸의 원본 자료 글 (화면이 `T()` 로 옮긴다). GVP 는 비상업·인용 조건을 적는다 (wetherilli 134)
SOURCE_LABELS = {
    "pbdb": msg("원본 자료 — Paleobiology Database, CC BY 4.0"),
    "gvp": msg("원본 자료 — 스미스소니언 GVP, 비상업·인용 조건"),
    "quakes": msg("원본 자료 — USGS ComCat, 공공 영역"),
    "neotoma": msg("원본 자료 — Neotoma, CC BY 4.0"),
    "heatflow": msg("원본 자료 — IHFC 세계 지열류 자료 2024, CC BY 4.0"),
    "recentquakes": msg("원본 자료 — USGS 실시간 피드(지난 7 일 M2.5 이상, 매시 받음), 공공 영역"),
    "faults": msg("원본 자료 — GEM Global Active Faults, CC BY-SA 4.0"),
    "plates": msg("원본 자료 — Hasterok 외 2022, CC BY 4.0"),
    "provinces": msg("원본 자료 — Hasterok 외 2022, CC BY 4.0"),
    "stress": msg("원본 자료 — World Stress Map 2025, CC BY 4.0"),
    "minerals": msg("원본 자료 — USGS MRDS·세계 광물 자원 평가, 공공 영역"),
}
SOURCE_URLS = {"pbdb": "https://paleobiodb.org/", "gvp": "https://volcano.si.edu/",
               "quakes": "https://earthquake.usgs.gov/earthquakes/search/", "neotoma": "https://www.neotomadb.org/",
               "heatflow": heatflow.DOI, "recentquakes": "https://earthquake.usgs.gov/earthquakes/map/",
               "faults": "https://github.com/GEMScienceTools/gem-global-active-faults",
               "plates": "https://doi.org/10.5281/zenodo.5093930", "provinces": "https://doi.org/10.5281/zenodo.5093930",
               "stress": stress.DOI, "minerals": minerals.LINK}
#: 자료가 없을 때 패널에 띄우는 글 — 어느 명령이 모으는지 적는다
MISSING = {
    "pbdb": msg("화석 산지 자료를 아직 모으지 않았다 (fetch_pbdb)"),
    "gvp": msg("홀로세 화산 자료를 아직 모으지 않았다 (fetch_gvp)"),
    "quakes": msg("지진 자료를 아직 모으지 않았다 (fetch_quakes)"),
    "neotoma": msg("고생태 산지 자료를 아직 모으지 않았다 (fetch_neotoma)"),
    "heatflow": msg("지열류 자료를 아직 굽지 않았다 (build_heatflow)"),
    "recentquakes": msg("최근 지진 피드를 아직 받지 않았다 (fetch_recent_quakes)"),
    "faults": msg("활성단층 자료를 아직 굽지 않았다 (build_faults)"),
    "plates": msg("판 경계 자료를 아직 굽지 않았다 (build_tectonics)"),
    "provinces": msg("지질구 자료를 아직 굽지 않았다 (build_tectonics)"),
    "stress": msg("응력 자료를 아직 굽지 않았다 (build_stress)"),
    "minerals": msg("광상 자료를 아직 굽지 않았다 (build_minerals)"),
}
_AVAILABLE = {"pbdb": fossils.available, "gvp": volcanoes.available, "quakes": quakes.available, "neotoma": paleoeco.available,
              "heatflow": heatflow.available, "recentquakes": recentquakes.available, "faults": faults.available,
              "plates": tectonics.available, "provinces": tectonics.available, "stress": stress.available,
              "minerals": minerals.available}


def knows(name: str) -> bool:
    return name in LAYERS


def source_of(name: str) -> str:
    return LAYERS[name][0]


def box_of(name: str) -> tuple:
    return BOXES[LAYERS[name][1]]


def available(name: str) -> bool:
    return _AVAILABLE[source_of(name)]()


def stamp(name: str) -> str:
    """캐시·브라우저가 판을 가를 것 — 모으거나 다시 구운 날."""
    src = source_of(name)
    if src == "gvp":
        return volcanoes.fetched()
    if src == "quakes":
        return quakes.built()
    if src == "neotoma":
        return paleoeco.built()
    if src == "heatflow":
        return heatflow.built()
    if src == "recentquakes":
        return recentquakes.generated()
    if src == "faults":
        return _file_stamp(settings.FAULTS_FILE)
    if src in ("plates", "provinces"):
        return _file_stamp(settings.TECTONICS_FILE)
    if src == "stress":
        return stress.built()
    if src == "minerals":
        return minerals.built()
    conn = fossils.db()
    row = conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone() if conn else None
    return row[0] if row else ""


#: 덩이를 짓는 법 — 열·색·네모를 고치면 올린다. 판(`version`)에 들어 주소가 바뀐다
RENDERER = "3"                      # 2 — 넓은 네모의 점을 칸으로 모은다 (wetherilli 331). 3 — 범례 줄마다 모양 (390)


def _file_stamp(path) -> str:
    try:
        return str(int(os.stat(path).st_mtime))
    except OSError:
        return ""


def version(name: str) -> str:
    """주소의 판(`?v=`) — 짓는 법과 모으거나 다시 구운 날. 바뀌면 화면이 새 주소로 묻는다 (wetherilli 183·185)."""
    return RENDERER + "-" + re.sub(r"[^0-9A-Za-z]+", "", stamp(name))


def _hex(rgb: tuple) -> str:
    return "#%02x%02x%02x" % rgb


def _point(lon, lat, props: dict, fid) -> dict:
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Point", "coordinates": [round(lon, DIGITS), round(lat, DIGITS)]},
            "properties": {k: v for k, v in props.items() if v not in (None, "")}}


def _period(mid: float) -> int:
    for i, (base, _) in enumerate(fossils.PERIODS):
        if mid <= base:
            return i
    return len(fossils.PERIODS) - 1


def _fossil_features(box, lang):
    conn = fossils.db()
    w, s, e, n = box
    rows = conn.execute(
        "SELECT c.* FROM coll_xy x JOIN coll c ON c.no = x.id WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?",
        (w, e, s, n))
    out = []
    for r in rows:
        mid = (r["max_ma"] + r["min_ma"]) / 2
        span = r["early"] + (f" – {r['late']}" if r["late"] and r["late"] != r["early"] else "")
        ma = f"{r['max_ma']:g}" if r["min_ma"] == r["max_ma"] else f"{r['max_ma']:g} – {r['min_ma']:g}"
        out.append(_point(r["lon"], r["lat"], {
            "code": f"p{_period(mid)}", "name": r["name"], "formation": r["formation"],
            "age": i18n.age_ko(span) if lang == "ko" else span, "ma": ma, "env": r["env"],
            "occs": r["n_occs"] or None, "cc": r["cc"], "ref": r["ref"], "link": pbdb.collection_url(r["no"]),
        }, r["no"]))
    legend = [(f"p{i}", PERIOD_NAMES[i], hexa) for i, (_, hexa) in enumerate(fossils.PERIODS)]
    return out, legend


def _volcano_features(box, lang):
    out = []
    for v in volcanoes.points(*box):
        last = volcanoes.year_text(v["last"])
        out.append(_point(v["lon"], v["lat"], {
            "code": f"e{volcanoes.era(v['last'])}", "name": v["name"], "type": v["type"],
            "last": i18n.t(last, lang) if last else "", "evidence": v["evidence"], "country": v["country"],
            "elev": f"{v['elev']:,}" if v["elev"] is not None else "", "tectonic": v["tectonic"], "rock": v["rock"],
            "link": gvp.volcano_url(v["no"]),
        }, v["no"]))
    legend = [(f"e{i}", label, hexa) for i, (_, hexa, label) in enumerate(volcanoes.ERAS)]
    legend.append((f"e{len(volcanoes.ERAS)}", volcanoes.UNKNOWN[1], volcanoes.UNKNOWN[0]))
    return out, legend


def _depth_class(depth) -> int:
    d = 0 if depth is None else depth
    for i, (below, _, _) in enumerate(quakes.DEPTHS):
        if d < below:
            return i
    return len(quakes.DEPTHS) - 1


def _quake_features(box, lang):
    out = []
    for q in quakes.points(list(quakes.BANDS), *box):
        out.append(_point(q["lon"], q["lat"], {
            "code": f"d{_depth_class(q['depth'])}", "mag": f"{q['mag']:g} {q['mag_type'] or ''}".strip(),
            "time": (q["time"] or "").replace("T", " ")[:16],
            "depth": f"{q['depth']:g}" if q["depth"] is not None else "", "place": q["place"],
            "link": usgs.event_url(q["id"]),
        }, q["id"]))
    legend = [(f"d{i}", label, hexa) for i, (_, hexa, label) in enumerate(quakes.DEPTHS)]
    return out, legend


def _neotoma_features(box, lang):
    conn = paleoeco.db()
    w, s, e, n = box
    sites = {}
    for r in conn.execute(
            "SELECT s.site, s.name, s.desc, s.alt, s.lon, s.lat, d.band, d.type FROM site_xy x "
            "JOIN site s ON s.site = x.id JOIN ds d ON d.site = s.site "
            "WHERE x.x0 >= ? AND x.x1 <= ? AND x.y0 >= ? AND x.y1 <= ?", (w, e, s, n)):
        site = sites.setdefault(r["site"], {"row": r, "bands": {}, "types": []})
        site["bands"][r["band"]] = site["bands"].get(r["band"], 0) + 1
        if r["type"] and r["type"] not in site["types"]:
            site["types"].append(r["type"])
    out = []
    order = list(paleoeco.BANDS)
    for no, site in sites.items():
        r = site["row"]
        # 산지 하나에 자료형이 여럿이면 가장 많은 것의 색 — 같으면 `BANDS` 의 앞 것
        band = max(site["bands"], key=lambda b: (site["bands"][b], -order.index(b)))
        out.append(_point(r["lon"], r["lat"], {
            "code": band, "name": r["name"], "desc": r["desc"],
            "alt": f"{r['alt']:g}" if r["alt"] is not None else "",
            "types": ", ".join(site["types"][:6]), "link": neotoma.site_url(no),
        }, no))
    legend = [(band, label, hexa) for band, (hexa, label) in paleoeco.BANDS.items()]
    return out, legend


def _heatflow_class(q) -> int:
    v = 0 if q is None else q
    for i, (below, _, _) in enumerate(heatflow.CLASSES):
        if v < below:
            return i
    return len(heatflow.CLASSES) - 1


def _heatflow_features(box, lang):
    """지열류 측정(wetherilli 275) — 온 지구 화면의 점 타일(`heatflow.render_tile`)과 같은 칸·색. 높은 값을 뒤에 두어 위에 그린다"""
    num = lambda v: f"{v:g}" if v is not None else ""      # noqa: E731
    rows = sorted(heatflow.points(*box), key=lambda r: r["q"] if r["q"] is not None else -1)
    out = [_point(r["lon"], r["lat"], {
        "code": f"h{_heatflow_class(r['q'])}", "q": num(r["q"]), "unc": num(r["q_unc"]), "name": r["name"],
        "env": r["environment"], "method": r["method"], "year": r["year"], "quality": r["quality"], "ref": r["reference"],
    }, r["n"]) for r in rows]
    legend = [(f"h{i}", label, hexa) for i, (_, hexa, label) in enumerate(heatflow.CLASSES)]
    return out, legend


def _recent_quake_features(box, lang):
    """최근 지진(wetherilli 292) — 지난 시간의 칸(`r0` 지난 한 시간·`r1` 하루·`r2` 일주일). 최근 것을 뒤에 두어 위에 그린다"""
    d = recentquakes.data()
    now = d[0] if d else 0
    rows = sorted(recentquakes.points(*box), key=lambda q: q["ms"] or 0)
    out = [_point(q["lon"], q["lat"], {
        "code": f"r{recentquakes.age_class(q['ms'], now)}", "mag": f"{q['mag']:g} {q['mag_type']}".strip(),
        "time": recentquakes.when(q["ms"]), "depth": f"{q['depth']:g}" if q["depth"] is not None else "",
        "place": q["place"], "link": usgs.event_url(q["id"]),
    }, q["id"]) for q in rows]
    legend = [(f"r{i}", label, hexa) for i, (_, hexa, label) in enumerate(recentquakes.AGES)]
    return out, legend


#: 칸 하나에 모일 때 남길 점 — 큰 것이 앞이다(화석 수·지열류·자료형 수·규모)
_KEEP = {
    "pbdb": lambda p: float(p.get("occs") or 0),
    "heatflow": lambda p: float(p.get("q") or 0),
    "neotoma": lambda p: len(str(p.get("types") or "").split(",")),
    "quakes": lambda p: float(str(p.get("mag") or "0").split()[0]),
    "gvp": lambda p: 0.0,
    "recentquakes": lambda p: float(str(p.get("mag") or "0").split()[0]),
    "stress": lambda p: -"ABCD".index(p.get("q") or "D"),
    "minerals": lambda p: 1.0 if p.get("shape") == "diamond" else 0.0,
}


def _merge(src: str, features: list) -> list:
    """점이 `CAP` 보다 많으면 `MERGE_CELLS` 의 첫 칸부터 같은 칸의 점을 하나로 — 그 칸에서 가장 큰 것(`_KEEP`)을 남기고
    모인 수(`merged`)를 적는다. 같은 자리에 산지 여럿이 겹친 PBDB 가 많아 1 km 칸(0.01°)이면 유럽 7 만이 2 만 5 천이 된다"""
    if len(features) <= CAP:
        return features
    keep = _KEEP[src]
    for cell in MERGE_CELLS:
        groups = {}
        for f in features:
            x, y = f["geometry"]["coordinates"]
            groups.setdefault((round(x / cell), round(y / cell)), []).append(f)
        if len(groups) <= CAP or cell == MERGE_CELLS[-1]:
            break
    out = []
    for members in groups.values():
        best = max(members, key=lambda f: keep(f["properties"]))
        if len(members) > 1:
            best = dict(best, properties=dict(best["properties"], merged=len(members)))
        out.append(best)
    return out


# ── 온 지구 화면에 구워 둔 선·면·막대 (wetherilli 390) ───────────────────

def _hits(bbox, box) -> bool:
    """겉네모가 지역의 네모에 걸치는가"""
    return bbox[0] <= box[2] and bbox[2] >= box[0] and bbox[1] <= box[3] and bbox[3] >= box[1]


def _pairs(flat) -> list:
    return [[flat[i], flat[i + 1]] for i in range(0, len(flat) - 1, 2)]


def _shape(geometry: dict, props: dict, fid) -> dict:
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": {k: v for k, v in props.items() if v not in (None, "")}}


def _fault_features(box, lang):
    """GEM 활성단층 — 갈래의 색·굵기·끊김으로 긋는다(`faults.KINDS`). 해령은 옅게, 활동성 단층이 위에 오게 차례를 둔다"""
    order = list(faults.KINDS)[::-1]
    items = sorted((f for f in faults.data()["faults"] if _hits(f["bbox"], box)), key=lambda f: -order.index(f["kind"]))
    out = [_shape({"type": "MultiLineString", "coordinates": [_pairs(p) for p in f["parts"]]}, {
        "code": f["kind"], "name": f["name"] or i18n.t(msg("이름 없는 단층"), lang), "kind": i18n.t(faults.KINDS[f["kind"]][1], lang),
        "slip": f["slip"].replace("_", " "), "dip": f["dip"], "dipdir": f["dipdir"], "rake": f["rake"], "rate": f["rate"],
        "depth": f["depth"], "catalog": f["catalog"]}, i) for i, f in enumerate(items)]
    legend = [(k, label, color, {"shape": "stroke", "width": round(1.6 * w, 2), **({"dash": list(dash)} if dash else {})})
              for k, (color, label, w, dash) in faults.KINDS.items()]
    return out, legend


def _slug(text: str) -> str:
    return re.sub(r"[^a-z]+", "_", text.lower()).strip("_")


def _plate_features(box, lang):
    """판 경계 — 갈래의 색. 큰 판의 경계(`level` 1)도 같은 굵기다 — 굵기는 범례 줄마다라서"""
    out = []
    for i, b in enumerate(tectonics.data()["boundaries"]):
        if not _hits(b["bbox"], box) or b["type"] not in tectonics.BOUNDARY_TYPES:
            continue
        out.append(_shape({"type": "MultiLineString", "coordinates": [_pairs(p) for p in b["parts"]]}, {
            "code": _slug(b["type"]), "kind": i18n.t(tectonics.BOUNDARY_TYPES[b["type"]][1], lang), "plates": b["plates"],
            "comment": b["comment"]}, i))
    legend = [(_slug(k), label, color, {"shape": "stroke", "width": 2.4, **({"dash": list(dash)} if dash else {})})
              for k, (color, label, dash) in tectonics.BOUNDARY_TYPES.items()]
    return out, legend


def _province_features(box, lang):
    """세계 지질구 — 면을 갈래의 색으로 옅게 칠한다(`classStyle` 의 면). 누르면 이름·갈래·마지막 조산 운동"""
    out = []
    for i, p in enumerate(tectonics.data()["provinces"]):
        if not _hits(p["bbox"], box):
            continue
        crust = tectonics.CRUST.get(p["crust"])
        out.append(_shape({"type": "MultiPolygon", "coordinates": [[_pairs(r) for r in poly] for poly in p["polys"]]}, {
            "code": _slug(p["type"]) or "other", "name": p["name"], "group": p["group"], "orogen": p["orogen"],
            "continent": p["continent"], "crust": i18n.t(crust, lang) if crust else p["crust"],
            "kind": i18n.t(tectonics.PROVINCE_TYPES[p["type"]][1], lang) if p["type"] in tectonics.PROVINCE_TYPES else p["type"]}, i))
    legend = [(_slug(k), label, color, {"shape": "area"}) for k, (color, label) in tectonics.PROVINCE_TYPES.items()]
    return out, legend


def _stress_features(box, lang):
    """지각 응력 — S_Hmax 방향의 막대(`azimuth`), 길이는 품질(`q`), 색은 응력 체제. 품질 좋은 것이 위에 오게 D 부터"""
    rows = sorted(stress.points(*box), key=lambda r: -"ABCD".index(r["quality"]))
    out = []
    for r in rows:
        kind = stress.TYPES.get(r["type"])
        regime = r["regime"] if r["regime"] in stress.REGIMES else "U"
        out.append(_point(r["lon"], r["lat"], {
            "code": regime, "azimuth": round(r["azi"] % 180, 1), "q": r["quality"], "azi": f"N{r['azi']:.0f}°E",
            "regime": i18n.t(stress.REGIMES[regime][1], lang), "quality": r["quality"],
            "type": i18n.t(kind, lang) if kind else r["type"], "depth": f"{r['depth']:g}" if r["depth"] is not None else "",
            "place": " · ".join(x for x in (r["locality"], r["country"]) if x), "mag": r["mag"], "date": r["date"],
            "ref": r["ref"]}, r["id"]))
    legend = [(k, label, color, {"shape": "bar"}) for k, (color, label) in stress.REGIMES.items()]
    return out, legend


def _mineral_features(box, lang):
    """세계 광상 — 광종 칸의 색. 세계 광상 표·대규모(무게 2)는 마름모(점의 `shape` 가 범례 줄의 모양을 덮는다), 나머지는 점.
    무거운 것이 위에 오게"""
    rows = sorted(minerals.points(list(minerals.BANDS), *box), key=lambda r: r["weight"])
    out = [_point(r["lon"], r["lat"], {
        "code": r["band"], "shape": "diamond" if r["weight"] == 2 else "", "name": r["name"] or i18n.t(msg("이름 없는 곳"), lang),
        "commodity": r["commodity"], "status": r["status"], "kind": r["kind"], "country": r["country"], "link": r["url"]},
        f"{r['src']}:{r['rid']}") for r in rows]
    legend = [(band, label, color) for band, (color, label) in minerals.BANDS.items()]
    return out, legend


_FEATURES = {"pbdb": _fossil_features, "gvp": _volcano_features, "quakes": _quake_features,
             "neotoma": _neotoma_features, "heatflow": _heatflow_features, "recentquakes": _recent_quake_features,
             "faults": _fault_features, "plates": _plate_features, "provinces": _province_features, "stress": _stress_features,
             "minerals": _mineral_features}


def body(name: str, lang: str = "ko") -> bytes:
    """레이어 하나의 GeoJSON. 자료가 없으면 FileNotFoundError. 북극의 화석 산지(2 만 2 천 점, 12 MB)는 굽는 데 1 초 가까이
    걸려 모으거나 다시 구운 날(`stamp`)마다 한 번만 굽는다."""
    if not available(name):
        raise FileNotFoundError(source_of(name))
    return _body(name, lang, stamp(name))


@functools.lru_cache(maxsize=8)
def _body(name: str, lang: str, _stamp: str) -> bytes:
    src = source_of(name)
    features, table = _FEATURES[src](box_of(name), lang)
    features = _merge(src, features)
    counts = {}
    for f in features:
        code = f["properties"]["code"]
        counts[code] = counts.get(code, 0) + 1
    shape = "triangle" if src == "gvp" else "ring" if src == "recentquakes" else "dot"
    # 범례 줄의 넷째 칸(있으면)이 그 줄의 모양·굵기·끊김이다 — 선·면·막대 (wetherilli 390)
    legend = [{"code": code, "label": str(label), "color": color, "shape": shape, "count": counts[code], **(extra[0] if extra else {})}
              for code, label, color, *extra in table if counts.get(code)]
    labels = dict(LABELS[src], merged="같은 칸에 모인 수")
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": labels, "links": list(LINKS),
                       "legend": legend, "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "earth", "tag": "EARTH", "title": "온 지구 화면에 모아 둔 자료 — PBDB·GVP·USGS·Neotoma"},
]
