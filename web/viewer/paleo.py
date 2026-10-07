"""그때 그 자리 — PALEOMAP 2016 판 회전으로 오늘의 한 자리를 옛 연대로 옮긴다 (wetherilli P06 §3·087).

`data/paleomap2016.json`(`manage.py build_paleomap <zip>`)을 읽는다. 상류가 아니라 저장소의 파일이라 문이 아니다.

- **계산이지 관측이 아니다.** 판을 굳은 것으로 보고 그 판의 회전을 그대로 태운다. 판 안의 변형·해수면은 없다
- 모델은 **PALEOMAP 2016**(Scotese, CC BY 4.0)이다. EarthThruTime3D(ETT)가 핀과 기본 화면을 이 모델로 그렸다 —
  같은 모델이어야 ETT 로 건너갔을 때 같은 자리에 핀이 선다(P06 §4). 다른 모델은 100 Ma 에 4–10° 갈린다(ETT wwolf 014)
- 셈법은 ETT 의 `scripts/rotation_model.py`·`static/core/pins.js`(MIT, © 2026 PaleoBytes — 허가 문구는
  `docs/licenses/EarthThruTime3D-MIT.txt`)를 옮겼다. 오늘의 자리를 담는
  대륙 다각형을 고르고(구면 위의 감김 — 날짜변경선·극을 넘어도 맞다), 그 판의 회전을 판 사슬을 따라 쿼터니언으로
  잇는다. 두 표본 사이는 slerp 다
- **닿는 곳은 대륙 위, 그 다각형이 생긴 때와 판의 극이 끝나는 때 가운데 가까운 쪽까지다.** 바다 밑은 다각형이 없다 —
  섭입으로 대부분 사라졌다. 모델이 덮는 것은 1 100 Ma 까지다
"""
import functools
import json
import math
from collections import defaultdict

from django.conf import settings

IDENTITY = (1.0, 0.0, 0.0, 0.0)
_ASK = object()                  # `carry` 가 판을 스스로 찾는다 — None(바다 밑)과 가른다
ANCHOR = 0


def _quaternion(pole_lat, pole_lon, angle):
    """축(극)과 각 → 단위 쿼터니언. 잇고 사이를 채우기 좋은 꼴이다."""
    lat, lon = math.radians(pole_lat), math.radians(pole_lon)
    half = math.radians(angle) / 2.0
    s = math.sin(half)
    return (math.cos(half), math.cos(lat) * math.cos(lon) * s, math.cos(lat) * math.sin(lon) * s, math.sin(lat) * s)


def _multiply(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])


def _slerp(a, b, f):
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0.0:
        b, dot = tuple(-v for v in b), -dot
    if dot > 0.9999995:
        out = tuple(x + (y - x) * f for x, y in zip(a, b))
    else:
        theta = math.acos(max(-1.0, min(1.0, dot)))
        s = math.sin(theta)
        p, q = math.sin((1.0 - f) * theta) / s, math.sin(f * theta) / s
        out = tuple(x * p + y * q for x, y in zip(a, b))
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return tuple(v / norm for v in out)


def turn(q, lon, lat):
    """점(도)을 회전 `q` 로 옮긴다."""
    lo, la = math.radians(lon), math.radians(lat)
    p = (0.0, math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
    _, x, y, z = _multiply(_multiply(q, p), _conjugate(q))
    return math.degrees(math.atan2(y, x)), math.degrees(math.asin(max(-1.0, min(1.0, z))))


class Rotations:
    """회전 목록 — `{"움직이는 판:기준 판": [때, 극 위도, 극 경도, 각, …]}` (ETT 의 `rotations.json` 과 같은 꼴)."""

    def __init__(self, sequences: dict):
        self.samples = {}
        self.by_moving = defaultdict(list)
        for key, flat in sequences.items():
            moving, fixed = (int(v) for v in key.split(":"))
            rows = [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]
            self.samples[(moving, fixed)] = rows
            self.by_moving[moving].append((fixed, rows[0][0], rows[-1][0]))

    @staticmethod
    def _relative(rows, t):
        if not rows or t < rows[0][0] - 1e-9 or t > rows[-1][0] + 1e-9:
            return None
        prev = rows[0]
        for row in rows:
            if row[0] >= t - 1e-9:
                if abs(row[0] - prev[0]) < 1e-9 or abs(row[0] - t) < 1e-9:
                    return _quaternion(row[1], row[2], row[3])
                # 극을 섞지 않고 앞 표본에서 뒤 표본으로 가는 회전을 나눈다 — 단계 회전을 나누는 법이다
                start, end = _quaternion(prev[1], prev[2], prev[3]), _quaternion(row[1], row[2], row[3])
                stage = _multiply(_conjugate(start), end)
                return _multiply(start, _slerp(IDENTITY, stage, (t - prev[0]) / (row[0] - prev[0])))
            prev = row
        return _quaternion(rows[-1][1], rows[-1][2], rows[-1][3])

    def rotation(self, plate: int, t: float, _seen=frozenset()):
        """판 `plate` 의 `t` Ma 때 기준(판 0)에 대한 온 회전. 극이 없으면 None."""
        if plate == ANCHOR:
            return IDENTITY
        if plate in _seen:
            return None                                   # 사슬이 돈다 — 모델의 흠이다
        # 서른 남짓한 판은 넓은 줄 위에 좁은 줄을 겹쳐 "이 동안은 다른 이웃에 대어 잰다" 고 적었다.
        # 늦게 시작하는 좁은 줄이 하려는 말이라 겹친 곳에서는 그것이 이긴다 (ETT 와 같다)
        for fixed, start, end in sorted(self.by_moving.get(plate, []), key=lambda e: e[1], reverse=True):
            if not start - 1e-9 <= t <= end + 1e-9:
                continue
            relative = self._relative(self.samples[(plate, fixed)], t)
            if relative is None:
                continue
            upstream = self.rotation(fixed, t, _seen | {plate})
            if upstream is not None:
                return _multiply(upstream, relative)
        return None


def _unit(lon, lat):
    lo, la = math.radians(lon), math.radians(lat)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def inside(lon, lat, ring) -> bool:
    """구면 위의 고리(`[경도, 위도, …]`) 안인가. 안에서 보면 꼭짓점의 방위가 한 바퀴 돌고, 밖에서 보면 제자리로
    돌아온다 — 날짜변경선·극을 넘어도 맞는다. 대척점과는 못 가른다(`_facing`)."""
    x, y, z = _unit(lon, lat)
    flat = max(math.hypot(x, y), 1e-12)
    east = (-y / flat, x / flat, 0.0)
    north = (y * east[2] - z * east[1], z * east[0] - x * east[2], x * east[1] - y * east[0])
    turned, first, prev = 0.0, None, None
    for i in range(0, len(ring) + 1, 2):
        v = first if i == len(ring) else _unit(ring[i], ring[i + 1])
        bearing = math.atan2(v[0] * east[0] + v[1] * east[1],
                             v[0] * north[0] + v[1] * north[1] + v[2] * north[2])
        if prev is not None:
            step = bearing - prev
            turned += step - 2 * math.pi * round(step / (2 * math.pi))
        if first is None:
            first = v
        prev = bearing
    return abs(turned) > math.pi


def _facing(feature, lon, lat) -> bool:
    """대륙은 반구보다 좁다 — 안에 든 자리는 그 가운데를 바라본다."""
    c = feature.get("_centre")
    if c is None:
        c = [0.0, 0.0, 0.0]
        for ring in feature["rings"]:
            for i in range(0, len(ring), 2):
                for axis, v in enumerate(_unit(ring[i], ring[i + 1])):
                    c[axis] += v
        feature["_centre"] = c
    p = _unit(lon, lat)
    return p[0] * c[0] + p[1] * c[1] + p[2] * c[2] > 0


def holds(feature, lon, lat) -> bool:
    if not _facing(feature, lon, lat):
        return False
    held = False
    for ring in feature["rings"]:                         # 홀짝 — 구멍은 구멍이다
        if inside(lon, lat, ring):
            held = not held
    return held


def _densify(ring, step=1.0):
    """고리의 변을 대원을 따라 `step`° 안으로 잘게 나눈다 — 돌린 뒤 경위도 평면에 곧은 변으로 그려도 대원과 거의
    같게. 줄인 다각형(0.12°)의 변은 몇 도에 이르기도 한다. `[(경도, 위도)…]`, 닫는 점은 넣지 않는다."""
    pts = [(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)]
    out = []
    for k, a in enumerate(pts):
        b = pts[(k + 1) % len(pts)]
        out.append(a)
        u, v = _unit(*a), _unit(*b)
        dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(u, v))))
        arc = math.degrees(math.acos(dot))
        n = int(arc // step)
        if n < 1 or arc > 179.0:
            continue
        s = math.sin(math.radians(arc))
        for j in range(1, n + 1):
            f = j / (n + 1)
            p = math.sin((1 - f) * math.radians(arc)) / s
            q = math.sin(f * math.radians(arc)) / s
            x, y, z = (p * u[i] + q * v[i] for i in range(3))
            out.append((math.degrees(math.atan2(y, x)), math.degrees(math.asin(max(-1.0, min(1.0, z))))))
    return out


def plane(ring) -> list:
    """구면 위의 고리(`[경도, 위도, …]`)를 경위도 평면의 다각형 `[(x, y)…]` 로 편다. 경도를 끊지 않고 이어
    (날짜변경선에서 360° 를 더하거나 빼) 평면 위에 곧게 놓는다 — 그래서 x 가 −180–180 밖으로 나갈 수 있다. 그리는 쪽이
    360° 씩 옮겨 가며 겹친다. **극을 두른 고리**(이어 보니 경도가 한 바퀴 돈다)는 극까지 내려 막는다 — 남극 대륙이다."""
    pts = [(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)]
    if len(pts) < 3:
        return []
    xs, prev = [pts[0][0]], pts[0][0]
    for lon, _ in pts[1:]:
        d = lon - prev
        xs.append(xs[-1] + d - 360.0 * round(d / 360.0))
        prev = lon
    d = pts[0][0] - prev
    total = xs[-1] + d - 360.0 * round(d / 360.0) - xs[0]
    out = [(x, lat) for x, (_, lat) in zip(xs, pts)]
    if abs(total) > 180.0:
        pole = 90.0 if sum(lat for _, lat in pts) > 0 else -90.0
        out += [(xs[0] + total, pts[0][1]), (xs[0] + total, pole), (xs[0], pole)]
    return out


class Model:
    def __init__(self, data: dict):
        self.meta = {k: data[k] for k in ("title", "citation", "license", "license_url", "covers_ma") if k in data}
        self.deepest = float(data.get("covers_ma", [0, 1100])[1])
        self.rotations = Rotations(data["sequences"])
        self.features = data["features"]

    def reach(self, pid: int, older: float) -> float:
        """판을 어디까지 거슬러 옮길 수 있나 — 다각형이 생긴 때와 극이 끝나는 때 가운데 가까운 쪽."""
        older = min(older, self.deepest)
        if self.rotations.rotation(pid, older) is not None:
            return older
        newer = 0.0
        while older - newer > 0.01:
            mid = (older + newer) / 2
            if self.rotations.rotation(pid, mid) is None:
                older = mid
            else:
                newer = mid
        return round(newer, 1)

    def _now(self, pid: int):
        """판의 0 Ma 회전. PALEOMAP 은 거의 항등이지만 판마다 조금 어긋난다 — 다각형은 그 회전 앞의 좌표다."""
        cache = self.__dict__.setdefault("_now_cache", {})
        if pid not in cache:
            cache[pid] = self.rotations.rotation(pid, 0.0) or IDENTITY
        return cache[pid]

    def _today_boxes(self):
        """오늘 있는 다각형마다 경위도 네모(다각형의 좌표로, 2° 넉넉히). 날짜변경선을 넘거나 극을 두른 것은 None — 늘 따져 본다.
        27 만 곳의 화석 산지(098)에 판을 붙일 때 감김 셈을 네모 안에서만 하려는 것이다."""
        boxes = self.__dict__.get("_boxes")
        if boxes is None:
            boxes = []
            for f in self.features:
                if f["to"] > 1e-9 or f["from"] < -1e-9:
                    continue
                lons = [v for ring in f["rings"] for v in ring[0::2]]
                lats = [v for ring in f["rings"] for v in ring[1::2]]
                wide = max(lons) - min(lons) > 180 or max(abs(v) for v in lats) > 85
                boxes.append((f, None if wide else (min(lons) - 2, max(lons) + 2, min(lats) - 2, max(lats) + 2)))
            self._boxes = boxes
        return boxes

    def plate_at(self, lon: float, lat: float):
        """오늘의 자리를 담는 대륙 다각형의 판. 여럿이 겹치면 가장 멀리 거슬러 가는 것. 바다 밑이면 None.
        `lon`·`lat` 은 판의 0 Ma 회전을 되돌린 좌표다 — 이것을 옛 연대의 회전으로 옮긴다 (ETT `pinAt` 과 같다)."""
        best, heres = None, {}
        for f, box in self._today_boxes():                 # 오늘 있는 다각형만
            # 다각형은 판의 0 Ma 회전 앞의 좌표다 — 판에 따라 수십 도 어긋난다. 점을 되돌린 뒤 네모로 거른다
            here = heres.get(f["pid"])
            if here is None:
                here = heres[f["pid"]] = turn(_conjugate(self._now(f["pid"])), lon, lat)
            if box and not (box[0] <= here[0] <= box[1] and box[2] <= here[1] <= box[3]):
                continue
            if not holds(f, *here):
                continue
            if best is None or f["from"] > best["from"]:
                best = {"pid": f["pid"], "from": f["from"], "lon": here[0], "lat": here[1]}
        if best is not None:
            best["reach"] = self.reach(best["pid"], best["from"])
        return best

    def reconstruct(self, age: float) -> list:
        """`age` Ma 의 판 조각 — `[{pid, from, reach, rings: [[경도, 위도, …]…]}]`, 고리는 그때의 좌표다 (wetherilli 091).
        그 연대에 있던 다각형(`from ≥ age ≥ to`)만, 극이 있는 판만이다. 연대마다 한 번 셈한다."""
        cache = self.__dict__.setdefault("_reconstructed", {})
        if age in cache:
            return cache[age]
        out = []
        for f in self.features:
            if age > f["from"] + 1e-9 or age < f["to"] - 1e-9:
                continue
            q = self.rotations.rotation(f["pid"], age)
            if q is None:
                continue
            rings = []
            for ring in f["rings"]:
                moved = []
                for lon, lat in _densify(ring):
                    moved.extend(turn(q, lon, lat))
                rings.append(moved)
            out.append({"pid": f["pid"], "from": f["from"], "reach": self.reach(f["pid"], f["from"]), "rings": rings})
        if len(cache) > 64:
            cache.clear()
        cache[age] = out
        return out

    def plate_then(self, lon: float, lat: float, age: float):
        """`age` Ma 의 지구에서 (lon, lat) 에 있던 판 조각과 그 자리의 **오늘의 좌표**. 판 밖(바다)이면 None.
        그때의 지구를 누르면 부른다 — 그 판의 회전을 되돌려 다각형의 좌표로 가서 담기는지 본다."""
        best = None
        for f in self.features:
            if age > f["from"] + 1e-9 or age < f["to"] - 1e-9:
                continue
            q = self.rotations.rotation(f["pid"], age)
            if q is None:
                continue
            here = turn(_conjugate(q), lon, lat)
            if not holds(f, *here):
                continue
            if best is None or f["from"] > best["from"]:
                best = {"pid": f["pid"], "from": f["from"], "here": here}
        if best is None:
            return None
        today = turn(self._now(best["pid"]), *best.pop("here"))
        best.update(today_lon=round(today[0], 4), today_lat=round(today[1], 4),
                    reach=self.reach(best["pid"], best["from"]))
        # 오늘까지 남지 않은 조각(`to` > 0)이면 "오늘의 좌표" 는 그 판이 오늘 있을 자리일 뿐이다
        best["gone"] = not any(f["pid"] == best["pid"] and f["to"] <= 1e-9 for f in self.features)
        return best

    def plate_at_cached(self, lon: float, lat: float):
        """`plate_at` 을 담아 둔다 — 판은 연대와 상관없어, 점묶음을 연대마다 옮길 때 다시 셈하지 않는다."""
        cache = self.__dict__.setdefault("_plates", {})
        key = (round(lon, 6), round(lat, 6))
        if key not in cache:
            if len(cache) > 200000:
                cache.clear()
            cache[key] = self.plate_at(lon, lat)
        return cache[key]

    def carry(self, lon: float, lat: float, age: float, plate=_ASK) -> dict:
        """오늘의 (lon, lat) 이 `age` Ma 에 있던 자리. 못 옮기면 `reason` 만 — `ocean`·`beyond`·`future`.
        같은 자리를 여러 연대로 옮길 때는 `plate_at` 을 한 번 불러 `plate` 로 넘긴다."""
        if plate is _ASK:
            plate = self.plate_at(lon, lat)
        if plate is None:
            return {"age": age, "reason": "ocean"}
        if age < 0:
            return {"age": age, "reason": "future"}
        if age > plate["reach"] + 1e-9:
            return {"age": age, "reason": "beyond", "reach": plate["reach"], "pid": plate["pid"]}
        q = self.rotations.rotation(plate["pid"], age)
        if q is None:
            return {"age": age, "reason": "beyond", "reach": plate["reach"], "pid": plate["pid"]}
        plon, plat = turn(q, plate["lon"], plate["lat"])
        return {"age": age, "lon": round(plon, 2), "lat": round(plat, 2), "pid": plate["pid"], "reach": plate["reach"]}


@functools.lru_cache(maxsize=1)
def model():
    """저장소의 파일을 한 번 읽는다. 없으면 None — 화면은 "옛 위치" 줄을 빼고 돈다."""
    try:
        with open(settings.PALEOMAP_FILE, encoding="utf-8") as fh:
            return Model(json.load(fh))
    except FileNotFoundError:
        return None


# ── 그때의 지구를 타일로 (wetherilli 091) ──────────────────────────────
#
# 돌린 판 조각을 **서버가 칠해** 경위도 타일로 낸다. 구(Cesium 의 경위도 격자)와 평면(4326, 극 평면은 OpenLayers 가
# 옮겨 그린다)이 같은 타일을 쓴다. 브라우저가 다각형을 칠하는 길은 버렸다 — 극을 두른 판(남극 대륙)과 날짜변경선을
# 넘는 판을 구·평면·극 평면에서 저마다 다르게 풀어야 하고, 판을 돌리는 셈이 브라우저에도 한 벌 더 생긴다.
#
# 격자는 Cesium 의 `GeographicTilingScheme` 과 같다 — 줌 0 이 180° 두 장, 줌마다 반씩. 256 칸.
TILE = 256
MAX_ZOOM = 6                     # 180/2⁶/256 ≈ 0.011° — 0.12° 로 줄인 다각형에는 넉넉하다. 그 너머는 늘려 쓴다
STYLES = ("land", "edge")        # 칠한 땅(옛 연대) · 경계선만(오늘, 배경 위에)
RENDERER = "2"                   # 그리는 법을 고치면 올린다 — 캐시 열쇠에 든다
SEA = (0, 0, 0, 0)
EDGE = (40, 30, 20, 230)
LINE = (255, 196, 64, 235)
SEAM = (24, 20, 16, 120)         # 칠한 고도 위의 판 경계 — 땅을 가리지 않게 가늘고 옅게
SHELF = (120, 170, 196, 255)     # 고도 격자가 없는 연대(540 Ma 너머) — 판 둘레에 두르는 얕은 바다


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def land_colour(pid: int) -> tuple:
    """판마다 조금씩 다른 낮은 뭍빛 — 이웃한 조각이 갈려 보이게. 번호에서 뽑아 늘 같은 색이다.

    고도 격자의 0–800 m 고리(`paleodem.LAND`) 안에서 고른다 — 540 Ma 를 넘나들 때 빛이 갑자기 바뀌지 않게."""
    h = (pid * 2654435761) & 0xFFFFFFFF
    k = ((h >> 8) & 0xFF) / 255.0
    j = (h & 0xFF) / 255.0 - 0.5
    return (int(130 + 56 * k), int(160 + 22 * k + 8 * j), int(100 + 18 * k), 255)


def _shapes(model_, age: float) -> list:
    """`[(pid, 평면 다각형, 진짜 변의 수, x 범위)…]` — 연대마다 한 번."""
    cache = model_.__dict__.setdefault("_planes", {})
    if age not in cache:
        out = []
        for piece in model_.reconstruct(age):
            for ring in piece["rings"]:
                poly = plane(ring)
                if poly:
                    xs = [p[0] for p in poly]
                    out.append((piece["pid"], poly, len(ring) // 2, (min(xs), max(xs))))
        if len(cache) > 64:
            cache.clear()
        cache[age] = out
    return cache[age]


def render_tile(age: float, style: str, z: int, x: int, y: int) -> bytes:
    """`age` Ma 의 판 조각을 한 장에. 두 배로 그려 줄인다 — Pillow 의 다각형에는 가장자리 다듬기가 없다.

    `land` 는 그 시점의 고도 격자(`paleodem`, wetherilli 375)를 칠한 그림을 깔고 판 경계를 가늘게 얹는다. 격자가 없는
    연대(540 Ma 너머)나 구운 것이 없을 때는 판 조각을 낮은 뭍빛으로 칠하고 둘레에 얕은 바다를 두른다."""
    import io

    from PIL import Image, ImageDraw

    from . import paleodem

    m = model()
    span = 180.0 / 2 ** z
    west, north = -180.0 + x * span, 90.0 - y * span
    k = 2
    size = TILE * k
    scale = size / span
    relief = paleodem.crop(age, west, north, span, size) if style == "land" else None
    image = relief.convert("RGBA") if relief is not None else Image.new("RGBA", (size, size), SEA)
    if m is not None:
        over = Image.new("RGBA", (size, size), SEA) if relief is not None else image
        draw = ImageDraw.Draw(over)
        polys, lines = [], []
        for pid, poly, real, (lo, hi) in _shapes(m, age):
            for shift in (-720.0, -360.0, 0.0, 360.0, 720.0):
                if hi + shift < west or lo + shift > west + span:
                    continue
                pts = [((px + shift - west) * scale, (north - py) * scale) for px, py in poly]
                polys.append((pid, pts))
                # 극까지 내려 막은 변은 긋지 않는다 — 진짜 해안이 아니다
                lines.append(pts[:real + 1] if len(pts) > real + 1 else pts + pts[:1])
        if style == "land" and relief is None:
            # 얕은 바다를 먼저 두르고 뭍을 덮는다 — 줌과 상관없이 화면에서 몇 픽셀
            for pts in lines:
                draw.line(pts, fill=SHELF, width=7 * k, joint="curve")
            for pid, pts in polys:
                draw.polygon(pts, fill=land_colour(pid))
        if style == "edge":
            colour, width = LINE, 2 * k
        elif relief is not None:
            colour, width = SEAM, k
        else:
            colour, width = EDGE, k + 1
        for pts in lines:
            draw.line(pts, fill=colour, width=width)
        if over is not image:
            image = Image.alpha_composite(image, over)
    buf = io.BytesIO()
    image.resize((TILE, TILE), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()
