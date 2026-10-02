"""옛 해안선 — PaleoCoastlines v7.1 을 `<EARTH_DIR>/paleocoastlines_v7.json` 한 장으로 굽는다 (wetherilli 097).

원본은 Zenodo 4297693 의 `PaleoCoastlines_v7.1.zip`(88 MB, CC BY 4.0 — 묶음 안 `Data/Readme.md` 도 그렇게 적는다)이다.
NAS `sources/earth/` 에 둔다. 그 안의 `Data/CS/<N>Ma_CS_v7.shp`(해안선, 81 시점)만 읽는다 — 대륙 가장자리(`CM`, −1400 m
등심선)와 그림(PNG·PDF)은 쓰지 않는다.

EarthThruTime3D 의 `scripts/pack_coastlines.py`(MIT)처럼 **0.1° 로 줄이고 네 점이 안 되는 고리는 버린다.** 셰이프파일의
관례대로 시계 방향 고리는 뭍, 반시계 방향은 그 안의 구멍(내해·호수)이다. 저장소에 두지 않는다 — 운영은 /srv/GSM/db/earth.
"""
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import paleocoast
from viewer.management.commands.build_paleomap import simplify

#: 2026-09-13 ETT 가 적고(`sources/paleogeography/paleocoastlines2021.json`) 2026-09-30 우리가 받아 맞춘 값
SHA256 = "4d039888bce4548f8126e0ad70a4ecb21472daad7671a4560c06a6bcd7734ddd"
MEMBER = re.compile(r"^Data/CS/(\d+)Ma_CS_v7\.shp$")
TOLERANCE = 0.1
MIN_POINTS = 4


def polygons(data: bytes) -> list:
    """면 셰이프파일(5) → 고리 목록 `[[(x, y)…]…]` (레코드 구분 없이)."""
    if struct.unpack("<i", data[32:36])[0] != 5:
        raise CommandError("면 셰이프파일이 아니다")
    at, rings = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        if struct.unpack("<i", data[body:body + 4])[0] == 5:
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            for a, b in zip(starts, starts[1:]):
                rings.append([(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)])
        at = body + words * 2
    return rings


def signed_area(ring) -> float:
    """경위도 평면의 넓이(부호 있음). 양이면 반시계 — 셰이프파일에서는 구멍이다."""
    return sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1])) / 2


def pack(ring) -> list:
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    points = simplify(ring + ring[:1], TOLERANCE)[:-1]
    if len(points) < MIN_POINTS:
        return []
    return [round(v, 2) for p in points for v in p]


class Command(BaseCommand):
    help = "PaleoCoastlines v7.1 zip → <EARTH_DIR>/paleocoastlines_v7.json (옛 해안선, wetherilli 097)"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="PaleoCoastlines_v7.1.zip")
        parser.add_argument("--out", help="적을 파일 (기본 <EARTH_DIR>/paleocoastlines_v7.json)")

    def handle(self, *args, **opts):
        src = Path(opts["zip"])
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest != SHA256:
            raise CommandError(f"확인값이 다르다 — {digest[:12]}… (기대 {SHA256[:12]}…). 판이 바뀌었으면 읽고 나서 고친다")
        rings, holes = {}, {}
        with zipfile.ZipFile(src) as zf:
            for name in zf.namelist():
                m = MEMBER.match(name)
                if not m:
                    continue
                age = str(float(m.group(1)))
                land, hole = [], []
                for ring in polygons(zf.read(name)):
                    packed = pack(ring)
                    if packed:
                        (hole if signed_area(ring) > 0 else land).append(packed)
                rings[age], holes[age] = land, hole
        if not rings:
            raise CommandError("Data/CS/ 의 해안선이 없다")
        out = Path(opts["out"] or paleocoast.path())
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "meta": {"title": "PaleoMAP PaleoCoastlines v7.1", "cite": paleocoast.CITE,
                     "license": "CC BY 4.0", "record": "https://zenodo.org/records/4297693", "sha256": SHA256,
                     "tolerance": TOLERANCE},
            "rings": rings, "holes": holes,
        }, separators=(",", ":")), encoding="utf-8")
        n = sum(len(v) for v in rings.values())
        h = sum(len(v) for v in holes.values())
        self.stdout.write(f"{len(rings)} 시점, 뭍 고리 {n} · 구멍 {h} → {out} ({out.stat().st_size / 1e6:.1f} MB)")
