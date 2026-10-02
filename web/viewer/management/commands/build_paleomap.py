"""PALEOMAP 2016 의 판 회전과 대륙 다각형을 `data/paleomap2016.json` 에 적는다 (wetherilli 087).

원본은 Zenodo 10251792 의 `Scotese_PaleoAtlas_v3.zip`(58 MB, CC BY 4.0, sha256 7bf15709…)이다. NAS
`sources/earth/` 에 둔다. 그 안의 `PALEOMAP Global Plate Model/` 에서 둘만 쓴다 — 회전 목록(`.rot`, 80 KB)과
판 다각형(`.gpml`, 5 MB). 같은 묶음의 고지리 지도 그림은 PALEOMAP 누리집의 조건을 따로 받으므로 풀지 않는다.

**EarthThruTime3D 의 `scripts/pack_plates.py`(MIT, `docs/licenses/EarthThruTime3D-MIT.txt`)와 같은 꼴·같은 줄임으로 굽는다** — 다각형은 0.12° 로 줄이고
네 점이 안 되는 고리는 버린다. 줄임이 같아야 ETT 의 핀과 같은 판을 고른다(P06 §4). 수백 KB 라 저장소에 둔다.
"""
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PREFIX = "Scotese PaleoAtlas_v3/PALEOMAP Global Plate Model/"
ROTATION = PREFIX + "PALEOMAP_PlateModel.rot"
POLYGONS = PREFIX + "PALEOMAP_PlatePolygons.gpml"
#: 2026-09-13 ETT 가 적고 2026-09-30 우리가 받아 맞춘 값
SHA256 = {ROTATION: "d56846bb3c6260805d088171066bc18e9d54e831892b660fd31315260e288022"}
TOLERANCE = 0.12
MIN_POINTS = 4
DISTANT_PAST, DISTANT_FUTURE = 1e9, -1e9


def simplify(points, tolerance):
    """경위도 위의 더글러스–포이커 — 이 축척에서는 넉넉하다 (ETT 와 같다)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        (ax, ay), (bx, by) = points[first], points[last]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        worst, index = -1.0, first
        for i in range(first + 1, last):
            px, py = points[i]
            d = math.hypot(px - ax, py - ay) if length < 1e-12 else abs(dy * px - dx * py + bx * ay - by * ax) / length
            if d > worst:
                worst, index = d, i
        if worst > tolerance:
            keep[index] = True
            stack.extend([(first, index), (index, last)])
    return [p for p, k in zip(points, keep) if k]


def _time(value):
    if "distantPast" in value:
        return DISTANT_PAST
    if "distantFuture" in value:
        return DISTANT_FUTURE
    try:
        return float(value)
    except ValueError:
        return DISTANT_PAST


def features(text):
    for block in re.findall(r"<gml:featureMember>.*?</gml:featureMember>", text, re.S):
        plate = re.search(r"<gpml:reconstructionPlateId>.*?<gpml:value>(\d+)</gpml:value>", block, re.S)
        if plate is None:
            continue
        begin = re.search(r"<gml:begin>.*?timePosition[^>]*>([^<]+)<", block, re.S)
        end = re.search(r"<gml:end>.*?timePosition[^>]*>([^<]+)<", block, re.S)
        rings = []
        for raw in re.findall(r"<gml:posList[^>]*>(.*?)</gml:posList>", block, re.S):
            numbers = raw.split()
            # GPML 은 위도를 먼저 적는다 — 우리는 경도가 먼저다
            points = simplify([(float(numbers[i + 1]), float(numbers[i])) for i in range(0, len(numbers) - 1, 2)],
                              TOLERANCE)
            if len(points) >= MIN_POINTS:
                rings.append([round(v, 3) for p in points for v in p])
        if rings:
            yield {"pid": int(plate.group(1)),
                   "from": round(_time(begin.group(1)) if begin else DISTANT_PAST, 2),
                   "to": round(_time(end.group(1)) if end else DISTANT_FUTURE, 2),
                   "rings": rings}


def rotations(text):
    """`{"움직이는 판:기준 판": [때, 극 위도, 극 경도, 각, …]}`. 같은 때가 거듭 적히면 하나만 둔다."""
    seqs = {}
    for line in text.splitlines():
        body = line.split("!", 1)[0].split()
        if len(body) < 6:
            continue
        try:
            moving, fixed = int(body[0]), int(body[5])
            values = [float(v) for v in body[1:5]]
        except ValueError:
            continue
        if any(math.isnan(v) for v in values):
            continue
        seqs.setdefault(f"{moving}:{fixed}", []).append(values)
    out = {}
    for key, rows in seqs.items():
        rows.sort(key=lambda r: r[0])
        unique = []
        for r in rows:
            if unique and abs(unique[-1][0] - r[0]) < 1e-9:
                continue
            unique.append(r)
        out[key] = [round(v, 6) for r in unique for v in r]
    return out


class Command(BaseCommand):
    help = "PALEOMAP 2016 묶음(Zenodo 10251792)에서 판 회전·대륙 다각형을 뽑아 data/paleomap2016.json 에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="Scotese_PaleoAtlas_v3.zip")
        parser.add_argument("--out", default="")

    def handle(self, *args, **o):
        with zipfile.ZipFile(o["zip"]) as zf:
            try:
                rot, gpml = zf.read(ROTATION), zf.read(POLYGONS)
            except KeyError as exc:
                raise CommandError(f"묶음에 {exc} 가 없다 — PALEOMAP PaleoAtlas v3 가 맞나") from exc
        digest = hashlib.sha256(rot).hexdigest()
        if digest != SHA256[ROTATION]:
            raise CommandError(f"회전 목록의 확인값이 다르다 ({digest[:12]}…) — 판이 바뀌었으면 SHA256 을 고친다")
        # 0 Ma 에서 0 Ma 까지만 있는 다각형이 200 개 남짓이다. 그 한순간에만 있고 바다까지 거의 온 지구를 덮는다 —
        # 두면 바다 밑도 판을 얻는다. ETT 도 버린다(`drop_zero_span`)
        feats = [f for f in features(gpml.decode("utf-8", "replace")) if f["from"] - f["to"] > 1e-9]
        seqs = rotations(rot.decode("utf-8", "replace"))
        out = Path(o["out"] or settings.PALEOMAP_FILE)
        out.write_text(json.dumps({
            "title": "Scotese 2016 PALEOMAP",
            "citation": "Scotese, C. R., 2016. PALEOMAP PaleoAtlas for GPlates and the PaleoData Plotter Program. "
                        "PALEOMAP Project. doi:10.5281/zenodo.10251792",
            "license": "Creative Commons Attribution 4.0 International",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "covers_ma": [0, 1100],
            "derived": "PALEOMAP_PlateModel.rot + PALEOMAP_PlatePolygons.gpml, polygons simplified "
                       f"{TOLERANCE}° (min {MIN_POINTS} points) as EarthThruTime3D scripts/pack_plates.py (MIT)",
            "anchor": 0,
            "sequences": seqs,
            "features": feats,
        }, separators=(",", ":")), encoding="utf-8")
        points = sum(len(r) // 2 for f in feats for r in f["rings"])
        self.stdout.write(f"다각형 {len(feats)} · 꼭짓점 {points} · 회전 줄 {len(seqs)} → {out} "
                          f"({out.stat().st_size // 1024} KB)")
