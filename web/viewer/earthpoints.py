"""지역 탭의 지구 자료 점 — 화석 산지(PBDB)·홀로세 화산(GVP)·지진(USGS)·제4기 고생태 산지(Neotoma) (wetherilli 185),
지열류(IHFC, wetherilli 275).

온 지구 화면이 경위도 타일로 그리는 것을, 지역 탭은 **점 레이어**(`kind: points`)로 받는다 — 지역의 네모 안만 잘라
극지연구소 파일 레이어(`kopri.file_body`)와 같은 꼴의 GeoJSON 으로 낸다. 화면이 제 투영(3857·3413·3031)으로 옮겨 그리고,
누르면 속성이 팝업에 선다. 자료는 모아 둔 sqlite·JSON(`fossils`·`volcanoes`·`quakes`·`paleoeco`)이라 상류를 타지 않는다.
오늘의 것만 싣는다 — 옛 연대로 옮기는 일은 온 지구 화면의 몫이다. 문이 아니다.
"""
import functools
import json
import re

from . import fossils, gvp, heatflow, i18n, neotoma, paleoeco, pbdb, quakes, recentquakes, usgs, volcanoes
from .i18n import msg

#: 지역 → 자르는 네모 (서, 남, 동, 북). 북극은 북극해에 두고 그린란드·스발바르·얀마옌·노르웨이·핀란드가 빌린다(`borrow`) —
#: 노르웨이 남쪽 끝(58°N)까지 품는다
BOXES = {
    "korea": (123.0, 32.0, 132.5, 43.5),
    "antarctica": (-180.0, -90.0, 180.0, -60.0),
    "arctic": (-180.0, 58.0, 180.0, 90.0),
}
SOURCES = ("pbdb", "gvp", "quakes", "neotoma", "heatflow", "recentquakes")
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
}
LINKS = ("link",)
CREDITS = {"pbdb": pbdb.CREDIT, "gvp": gvp.CREDIT, "quakes": usgs.CREDIT, "neotoma": neotoma.CREDIT,
           "heatflow": heatflow.CREDIT, "recentquakes": usgs.CREDIT}
#: 범례 칸의 원본 자료 글 (화면이 `T()` 로 옮긴다). GVP 는 비상업·인용 조건을 적는다 (wetherilli 134)
SOURCE_LABELS = {
    "pbdb": msg("원본 자료 — Paleobiology Database, CC BY 4.0"),
    "gvp": msg("원본 자료 — 스미스소니언 GVP, 비상업·인용 조건"),
    "quakes": msg("원본 자료 — USGS ComCat, 공공 영역"),
    "neotoma": msg("원본 자료 — Neotoma, CC BY 4.0"),
    "heatflow": msg("원본 자료 — IHFC 세계 지열류 자료 2024, CC BY 4.0"),
    "recentquakes": msg("원본 자료 — USGS 실시간 피드(지난 7 일 M2.5 이상, 매시 받음), 공공 영역"),
}
SOURCE_URLS = {"pbdb": "https://paleobiodb.org/", "gvp": "https://volcano.si.edu/",
               "quakes": "https://earthquake.usgs.gov/earthquakes/search/", "neotoma": "https://www.neotomadb.org/",
               "heatflow": heatflow.DOI, "recentquakes": "https://earthquake.usgs.gov/earthquakes/map/"}
#: 자료가 없을 때 패널에 띄우는 글 — 어느 명령이 모으는지 적는다
MISSING = {
    "pbdb": msg("화석 산지 자료를 아직 모으지 않았다 (fetch_pbdb)"),
    "gvp": msg("홀로세 화산 자료를 아직 모으지 않았다 (fetch_gvp)"),
    "quakes": msg("지진 자료를 아직 모으지 않았다 (fetch_quakes)"),
    "neotoma": msg("고생태 산지 자료를 아직 모으지 않았다 (fetch_neotoma)"),
    "heatflow": msg("지열류 자료를 아직 굽지 않았다 (build_heatflow)"),
    "recentquakes": msg("최근 지진 피드를 아직 받지 않았다 (fetch_recent_quakes)"),
}
_AVAILABLE = {"pbdb": fossils.available, "gvp": volcanoes.available, "quakes": quakes.available, "neotoma": paleoeco.available,
              "heatflow": heatflow.available, "recentquakes": recentquakes.available}


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
    conn = fossils.db()
    row = conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone() if conn else None
    return row[0] if row else ""


#: 덩이를 짓는 법 — 열·색·네모를 고치면 올린다. 판(`version`)에 들어 주소가 바뀐다
RENDERER = "1"


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


_FEATURES = {"pbdb": _fossil_features, "gvp": _volcano_features, "quakes": _quake_features,
             "neotoma": _neotoma_features, "heatflow": _heatflow_features, "recentquakes": _recent_quake_features}


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
    counts = {}
    for f in features:
        code = f["properties"]["code"]
        counts[code] = counts.get(code, 0) + 1
    shape = "triangle" if src == "gvp" else "ring" if src == "recentquakes" else "dot"
    legend = [{"code": code, "label": str(label), "color": color, "shape": shape, "count": counts[code]}
              for code, label, color in table if counts.get(code)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS[src], "links": list(LINKS),
                       "legend": legend, "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
