"""ArcGIS 의 점을 통째로 받아 브라우저에 한 덩이로 주는 틀 — 문이 아니다.

그린란드 정부 포털(`grportal.py`, devlog 019)에서 생긴 것을 노르웨이 극지연구소
(`npolar.py`, devlog 021)가 함께 쓰려고 떼어 냈다. **여기서는 상류를 부르지
않는다** (`requests` 가 없다 — CLAUDE.md "상류마다 문이 하나"). 한 장을 받는
손(`get_page`)은 문이 건넨다. 여기 있는 것은 받은 feature 를 우리 꼴로 줄이고,
장을 넘기고, 브라우저에 보낼 덩이를 싸는 일뿐이다.

레이어 하나의 명세(`spec`)는 이렇다.

    {"style": "age",                     그리는 갈래 (map.js 의 portalPointStyle)
     "fields": {"age": field("age_num", "연대 (Ma)", "number"), …}}

`fields` 의 열쇠가 짧은 까닭 — 수천 점마다 되풀이되는 이름이라 짧을수록 덜
싣는다. 팝업의 이름(`label`)은 한 번만 따로 보낸다. `label` 이 없는 열(색
따위)은 그리는 데만 쓰고 팝업에 올리지 않는다.
"""
import json
import logging
import re
import time
import unicodedata

log = logging.getLogger(__name__)

#: 좌표를 이 자리까지만 둔다. 소수 다섯째 자리가 1 m 남짓이다.
DIGITS = 5


def field(upstream, label, kind="text"):
    return {"from": upstream, "label": label, "kind": kind}


def signature(spec: dict, head: str) -> str:
    """캐시 열쇠에 넣는 것 — 받는 열이 바뀌면 받아 둔 것을 쓰지 않는다.
    팝업 이름(`label`)은 넣지 않는다. 이름을 고쳤다고 상류에 다시 물을 까닭이 없다."""
    cols = ",".join(f"{k}={f['from']}:{f['kind']}" for k, f in sorted(spec["fields"].items()))
    return f"{head}|{cols}"


def labels(spec: dict) -> dict:
    return {k: f["label"] for k, f in spec["fields"].items() if f["label"]}


def links(spec: dict) -> list:
    """링크로 그릴 열. 팝업이 이것을 보고 `<a>` 를 만든다."""
    return sorted(k for k, f in spec["fields"].items() if f["kind"] == "link")


def collect(get_page, fields: dict, *, page: int, max_pages: int, pause: float, name: str = "",
            oid: str = "FID", areal: bool = False) -> list:
    """`get_page(offset)` 로 장을 넘기며 끝까지 받아 우리 꼴의 feature 목록으로.

    상류는 한 번에 `page` 점까지 준다. 덜 오거나 `exceededTransferLimit` 가
    없으면 끝이다. 장과 장 사이에 `pause` 초 쉰다. `areal` 이면 면도 받는다(`compact`).
    """
    out, offset = [], 0
    for index in range(max_pages):
        if index:
            time.sleep(pause)
        data = get_page(offset)
        got = data.get("features") or []
        for feature in got:
            row = compact(feature, fields, oid, areal=areal)
            if row is not None:
                out.append(row)
        more = (data.get("exceededTransferLimit")
                or (data.get("properties") or {}).get("exceededTransferLimit"))
        if not got or (len(got) < page and not more):
            break
        offset += len(got)
    else:
        log.warning("%s: %d 장을 넘겨도 끝나지 않아 멈췄다", name, max_pages)
    return out


def _round(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), DIGITS), round(float(coords[1]), DIGITS)]
    return [_round(c) for c in coords]


def compact(feature: dict, fields: dict, oid: str = "FID", *, areal: bool = False):
    """상류 feature 하나 → 우리 것. 점이 아니면(기하가 없으면) None.
    `areal` 이면 면(Polygon·MultiPolygon)도 받는다 — 스발바르 도폭 경계."""
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if areal and geom.get("type") in ("Polygon", "MultiPolygon") and coords:
        try:
            geometry = {"type": geom["type"], "coordinates": _round(coords)}
        except (TypeError, ValueError, IndexError):
            return None
    elif geom.get("type") != "Point" or not coords or len(coords) < 2:
        return None
    else:
        try:
            geometry = {"type": "Point", "coordinates": [round(float(coords[0]), DIGITS),
                                                         round(float(coords[1]), DIGITS)]}
        except (TypeError, ValueError):
            return None
    src = feature.get("properties") or {}
    props = {}
    for key, spec in fields.items():
        value = clean(src.get(spec["from"]), spec["kind"])
        if value is not None:
            props[key] = value
    fid = feature.get("id")
    if fid is None:
        fid = src.get(oid, src.get("FID", src.get("OBJECTID", src.get("ObjectId"))))
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": props}


def clean(value, kind):
    """값 하나. 고치지 않는다 — 앞뒤 빈칸만 떼고, 빈 값은 뺀다."""
    if value is None:
        return None
    if kind in ("number", "measure"):
        try:
            number = round(float(value), 3)
        except (TypeError, ValueError):
            return None
        # `measure` — GEUS 의 다이아몬드 자료처럼 모르는 값을 -999 로 적는 열
        return None if kind == "measure" and number <= -999 else number
    text = " ".join(str(value).split())       # 앞뒤 빈칸·줄바꿈("\r\n")을 한 칸으로
    if not text:
        return None
    if kind == "link":
        # 주소는 http·https 만 받는다 — `javascript:` 를 팝업에 들이지 않는다
        return text if text.lower().startswith(("http://", "https://")) else None
    if kind == "rgb":
        try:
            r, g, b = (int(p) for p in text.split()[:3])
        except ValueError:
            return None
        return "#%02x%02x%02x" % (r, g, b)
    return text


def body(spec: dict, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이. 캐시에 든 feature 목록(바이트)을 다시 풀지 않고 감싼다.

    `labels` 는 팝업 이름(한국어 — 영어는 브라우저가 `PROP_EN` 으로 옮긴다),
    `links` 는 링크로 그릴 열, `style` 은 그리는 갈래다.
    """
    head = json.dumps({"type": "FeatureCollection", "labels": labels(spec), "links": links(spec),
                       "style": spec["style"]}, ensure_ascii=False)
    return head[:-1].encode("utf-8") + b', "features": ' + features_json + b"}"


# ── 지명 찾기 (wetherilli 096) ──────────────────────────────────────
#
# 스발바르·드로닝모드랜드(NPI)와 그린란드(정부 포털)의 지명을 같은 틀로 찾는다. 이름 열이 여럿일 수
# 있다 — 그린란드는 새 철자·옛 철자·덴마크어·다른 이름. 색인(`name_index`)을 한 번 짓고 찾을 때마다
# 그것만 훑는다. 짓는 것은 부르는 쪽(`views`)이 메모리에 들고 있는다.


def fold(text: str) -> str:
    """찾기를 위해 접는다 — 작은 글자로, 노르웨이·덴마크 글자는 로마자로(å→a, ø→o, æ→ae),
    그린란드 옛 철자의 `ĸ`(kra)는 새 철자처럼 q 로, 나머지 덧붙임표는 떼고."""
    text = (text or "").lower().replace("æ", "ae").replace("ø", "o").replace("å", "a").replace("ĸ", "q")
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def name_index(features: list, names=("name",), sub=(), prefer=None) -> list:
    """feature 목록 → [(접은 이름들, 이름들, 곁말, 위도, 경도, 앞세움)]. `names` 의 첫 열이 보이는 이름이고,
    **그 열이 빈 것은 뺀다** — 그린란드 지명에 그린란드어 이름 없이 덴마크어만 적힌 것이 스무 건 남짓 있는데,
    스발바르의 Longyearbyen 이 경도 부호가 뒤집혀(동경 15.98° → 서경 16°) 든 것 따위다.
    `prefer` 는 (열, 값들) — 같은 이름이면 이 값의 것(도시·마을)을 앞세운다."""
    out = []
    for f in features:
        props = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates")
        if not props.get(names[0]) or not coords:
            continue
        shown = tuple(dict.fromkeys(str(props[k]) for k in names if props.get(k)))
        side = " · ".join(dict.fromkeys(str(props[k]) for k in sub if props.get(k) and str(props[k]) not in shown[:1]))
        first = 0 if prefer and str(props.get(prefer[0], "")) in prefer[1] else 1
        out.append((tuple(fold(n) for n in shown), shown, side, coords[1], coords[0], first))
    return out


def match_index(index: list, query: str, limit: int = 20) -> list:
    """색인에서 `query` 에 맞는 것. 같은 이름 → 앞이 같은 것 → 들어 있는 것 차례, 같으면 짧은 이름.
    같은 차례면 앞세울 것(`prefer`)이 먼저다. 다른 이름(옛 철자·덴마크어)으로 맞았으면 제목에 괄호로 곁들인다 — 화면은 괄호를 떼고 옮겨 간다.
    화면의 찾기 결과 꼴(`title`·`sub`·`lat`·`lon`·`kind`)로 준다."""
    q = fold(query)
    if not q:
        return []
    ranked = []
    for folded, shown, side, lat, lon, first in index:
        best = None
        for i, name in enumerate(folded):
            if q in name:
                rank = 0 if name == q else 1 if name.startswith(q) else 2
                if best is None or rank < best[0]:
                    best = (rank, i)
        if best is not None:
            ranked.append((best[0], first, len(shown[best[1]]), shown[0], best[1], shown, side, lat, lon))
    ranked.sort(key=lambda r: r[:4])
    out = []
    for _, _, _, main, i, shown, side, lat, lon in ranked[:limit]:
        title = main if i == 0 else f"{main} ({shown[i]})"
        out.append({"kind": "name", "title": title, "sub": side, "lat": lat, "lon": lon})
    return out
