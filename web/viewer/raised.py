"""남극 빙상의 후퇴 — RAISED 컨소시엄(Bentley 외 2014)의 20·15·10·5 ka 접지선 (wetherilli 420).

`manage.py build_raised` 가 Quantarctica3 사본을 NPI 의 문(`npolar.quantarctica`)으로 받아 `<GLACIO_DIR>/raised.json` 에
위경도로 옮겨 적는다. 화면이 부를 때는 이 파일만 읽는다. 문이 아니다.

- 원 자료는 논문(QSR 100, 1–9, CC BY 3.0)의 그림이고, 셰이프는 **Quantarctica 사본뿐이다**(2017-05-11 내려받음). 사본에 조건
  칸이 없다 — 사람이 "논문의 CC BY 를 자료에도 걸린다고 보고 붙인다, 정적 판에는 싣지 않는다" 로 정했다(2026-10-23)
- 선마다 신뢰도(측정·추정·짐작)와 시나리오가 붙는다. 동남극의 몇 곳은 시나리오 A(얼음이 거의 그대로)와 B(바깥으로 더 나갔다)가
  갈린다 — 둘 다 그리고 팝업에 어느 시나리오의 선인지 적는다
- 연대마다 레이어 하나다. 온 지구 화면의 시간 축(`icemargins.py`, NADI-1·DATED-1)에 잇는 것은 다음 일이다(TODOs)
"""
import functools
import json
import struct
import time
from pathlib import Path

from django.conf import settings

from . import geo3al, geomap, i18n
from .i18n import msg

#: Quantarctica 안의 자리(확장자 없이)
QUANTARCTICA_PATH = "Glaciology/RAISED Paleo Ice Extents/RAISED_PaleoIceExtents"
PAPER = "https://doi.org/10.1016/j.quascirev.2014.06.025"
SOURCE_URL = PAPER
CREDIT = "RAISED Consortium, Bentley et al. 2014 (QSR, CC BY) · Quantarctica"
AGES = ("20", "15", "10", "5")
#: 레이어 이름 → 연대(ka)
LAYERS = {f"raised:{age}ka": age for age in AGES}
#: 연대의 색 — 오래될수록 짙은 파랑, 가까울수록 주황. 여럿을 함께 켜도 갈려 보이게
COLORS = {"20": "#1d3c8f", "15": "#2a8fbd", "10": "#3fae6a", "5": "#e08a1e"}
#: 신뢰도 — 선의 굵기·끊김 (`map.js` 의 `classStyle` 의 stroke)
CONFIDENCE = [("Measured", msg("측정 — 연대 측정이 받친다"), {"width": 2.6}),
              ("Inferred", msg("추정 — 간접 근거"), {"width": 1.8, "dash": [7, 4]}),
              ("Speculative", msg("짐작 — 근거가 거의 없다"), {"width": 1.4, "dash": [2, 4]})]
LABELS = {"age": "연대", "conf": "신뢰도", "scenario": "시나리오", "link": "논문"}


class RaisedError(RuntimeError):
    pass


def path() -> Path:
    return Path(settings.GLACIO_DIR) / "raised.json"


def knows(name: str) -> bool:
    return name in LAYERS


def available() -> bool:
    return path().exists()


# ── 굽기 ─────────────────────────────────────────────────────────────

def read_lines(data: bytes) -> list:
    """셰이프파일(선, 3) → 행마다 선 목록(평면 좌표)."""
    if len(data) < 100 or struct.unpack(">i", data[:4])[0] != 9994:
        raise RaisedError("셰이프파일이 아니다")
    if struct.unpack("<i", data[32:36])[0] != 3:
        raise RaisedError("선 셰이프파일이 아니다")
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        parts = []
        if struct.unpack("<i", data[body:body + 4])[0] == 3:
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            for a, b in zip(starts, starts[1:]):
                parts.append([(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)])
        out.append(parts)
        at = body + words * 2
    return out


def convert(parts: dict) -> dict:
    """받은 셰이프 한 벌 → 적을 꼴 `{"lines": [{age, conf, a, b, coords}]}`. 좌표는 3031 → 위경도, 소수 넷째 자리."""
    if b"Stereographic_South_Pole" not in parts[".prj"] and b"Polar_Stereographic" not in parts[".prj"]:
        raise RaisedError("투영이 남극 평사도법(3031)이 아니다")
    shapes, rows = read_lines(parts[".shp"]), geo3al.read_dbf(parts[".dbf"])
    if len(shapes) != len(rows):
        raise RaisedError("셰이프와 속성 표의 행 수가 다르다")
    known = {c for c, _, _ in CONFIDENCE}
    lines = []
    for shape, row in zip(shapes, rows):
        age = str(row.get("Age", "")).strip().removesuffix("ka")
        conf = str(row.get("Confidence", "")).strip()
        if age not in AGES or conf not in known:
            continue
        for part in shape:
            coords = [[round(v, 4) for v in geomap.xy3031_to_lonlat(x, y)] for x, y in part]
            if len(coords) >= 2:
                lines.append({"age": age, "conf": conf, "a": row.get("ScenarioA") == "Y",
                              "b": row.get("ScenarioB") == "Y", "coords": coords})
    if not lines:
        raise RaisedError("그릴 선이 없다")
    return {"lines": lines}


def build(parts: dict, out: Path) -> dict:
    doc = {"built": time.strftime("%Y-%m-%d"), "source": "Quantarctica3 " + QUANTARCTICA_PATH, **convert(parts)}
    part = out.with_name(out.name + ".part")              # 다 적은 뒤 바꿔 넣는다 (`orda.download` 와 같다)
    part.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    part.replace(out)
    return {age: sum(1 for l in doc["lines"] if l["age"] == age) for age in AGES}


# ── 내주기 ───────────────────────────────────────────────────────────

def version() -> str:
    try:
        st = path().stat()
    except FileNotFoundError:
        return ""
    return f"{st.st_mtime_ns}-{st.st_size}"


def body(name: str, lang: str = "ko") -> bytes:
    """연대 하나의 접지선 GeoJSON — 신뢰도가 갈래(`code`), 색은 연대. 파일이 없으면 FileNotFoundError."""
    if not available():
        raise FileNotFoundError(path())
    return _body(name, lang, version())


def _scenario(line: dict, lang: str) -> str:
    if line["a"] and line["b"]:
        return i18n.t(msg("A·B 같다"), lang)
    return i18n.t(msg("A 만"), lang) if line["a"] else i18n.t(msg("B 만"), lang) if line["b"] else ""


@functools.lru_cache(maxsize=8)
def _body(name: str, lang: str, _stamp: str) -> bytes:
    age = LAYERS[name]
    lines = [l for l in json.loads(path().read_text(encoding="utf-8"))["lines"] if l["age"] == age]
    names = {code: i18n.t(label, lang) for code, label, _ in CONFIDENCE}
    features, counts = [], {}
    for line in lines:
        counts[line["conf"]] = counts.get(line["conf"], 0) + 1
        props = {"code": line["conf"], "age": f"{age} ka", "conf": names[line["conf"]],
                 "scenario": _scenario(line, lang), "link": PAPER}
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": line["coords"]},
                         "properties": {k: v for k, v in props.items() if v}})
    legend = [{"code": code, "label": str(label), "color": COLORS[age], "shape": "stroke", "count": counts[code], **look}
              for code, label, look in CONFIDENCE if counts.get(code)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": ["link"],
                       "legend": legend, "features": features},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


#: 우리 디스크의 파일이다 — 받는 문은 `npolar.quantarctica` (wetherilli 420)
REGISTRY = [
    {"upstream": "raised", "tag": "RAISED", "title": "RAISED 컨소시엄", "local": True},
]
