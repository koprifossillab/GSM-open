"""온 지구의 지명·강·호수·빙하 — Natural Earth 10 m 를 `data/earth_*.json` 셋으로 굽는다 (wetherilli 102).

Natural Earth(naturalearthdata.com, v5)는 **퍼블릭 도메인**이다. 일곱 묶음을 받아 폴더 하나에 두고 부른다. NAS
`sources/earth/natural_earth/` 에 확인값과 함께 둔다. 구운 것은 수백 KB 씩이라 저장소에 둔다(달·화성 지명과 같은 자리).

| 묶음 | 쓰는 것 |
|---|---|
| `ne_10m_geography_regions_polys` | 산맥·사막·고원·반도·섬 따위 1 047 — 이름(한국어 `NAME_KO`)과 큰 순위 |
| `ne_10m_geography_marine_polys` | 대양·바다·만·해협 306 |
| `ne_10m_populated_places` | 도시 7 342 (한국어 이름이 있는 판) |
| `ne_10m_lakes` · `ne_10m_rivers_lake_centerlines` | 호수 면 · 강 중심선 (운하는 뺀다) |
| `ne_10m_glaciated_areas` · `ne_10m_antarctic_ice_shelves_polys` | 빙하·빙상 · 남극 빙붕 |

면은 이름표 자리로 **가장 큰 고리의 무게중심**을 쓴다. 휘어진 산맥은 무게중심이 산맥 밖에 설 수 있다 — 그러면 가장 큰
고리의 꼭짓점 가운데 무게중심에 가장 가까운 것으로 옮긴다. 선·면은 0.02°(2 km 남짓) 로 줄인다 — 저장소에 두려고.
"""
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer.management.commands.build_paleomap import simplify
from viewer.management.commands.build_paleocoastlines import signed_area

#: 2026-09-30 받은 값. 넷은 EarthThruTime3D 가 2026-09-13·16·25 에 적은 것과 같다
SHA256 = {
    "ne_10m_geography_regions_polys.zip": "cb7b9db200284ed1551f20eacc7f3333e9b5f311c19f7cb2670694529f688682",
    "ne_10m_geography_marine_polys.zip": "a2d3395904c41e718e02c3ec5bc988712164c524c236fad32d95d282ca303b2a",
    "ne_10m_populated_places.zip": "cd149186f03d2603e0410da399b980a4357d0ac32d3a2305a49ed3dffcc41d7b",
    "ne_10m_lakes.zip": "0803a06f9c3cb4671d89b68c48b142aad9366ba40f665245e12a913fbc61722a",
    "ne_10m_rivers_lake_centerlines.zip": "ded71b01870855ccfe19b51f2ec14c9bb48fae23c0e9f3c11974d426433b5c38",
    "ne_10m_glaciated_areas.zip": "de6ff396ab7eee8cbe2146030cc29278ef67c468e5675c748b1372e241ecbbff",
    "ne_10m_antarctic_ice_shelves_polys.zip": "1d421d2487e2721a6e0aee8187e008c9bd8f0adbf4a5297b8503f7bf3c30b04d",
}
TOLERANCE = 0.02
CREDIT = "Natural Earth 10 m v5 (public domain) · naturalearthdata.com"


def dbf(data: bytes) -> list:
    """dBASE 표 → 행 목록(열 이름은 작은 글자로). 빈 값의 NUL 은 뗀다."""
    n, hlen, rlen = struct.unpack("<4xIHH", data[:12])
    fields, at = [], 32
    while data[at] != 0x0D:
        fields.append((data[at:at + 11].split(b"\0")[0].decode().lower(), data[at + 16]))
        at += 32
    rows = []
    for i in range(n):
        rec, off, row = data[hlen + i * rlen:hlen + (i + 1) * rlen], 1, {}
        for name, length in fields:
            row[name] = rec[off:off + length].decode("utf-8", "replace").replace("\0", "").strip()
            off += length
        rows.append(row)
    return rows


def shapes(data: bytes) -> list:
    """셰이프파일 → 레코드마다 부분 목록 `[[(x, y)…]…]`(점은 `[[(x, y)]]`). 빈 레코드는 `[]`."""
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        kind = struct.unpack("<i", data[body:body + 4])[0]
        parts = []
        if kind == 1:
            parts = [[struct.unpack("<2d", data[body + 4:body + 20])]]
        elif kind in (3, 5):
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            parts = [[(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)] for a, b in zip(starts, starts[1:])]
        out.append(parts)
        at = body + words * 2
    return out


def read(folder: Path, name: str):
    path = folder / name
    if not path.exists():
        raise CommandError(f"{name} 이 없다 — {folder} 에 일곱 묶음을 둔다")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256[name]:
        raise CommandError(f"{name} 의 확인값이 다르다 — {digest[:12]}… (기대 {SHA256[name][:12]}…)")
    with zipfile.ZipFile(path) as zf:
        stem = name[:-4]
        return dbf(zf.read(f"{stem}.dbf")), shapes(zf.read(f"{stem}.shp"))


def flat(points, tolerance=TOLERANCE) -> list:
    return [round(v, 3) for p in simplify(points, tolerance) for v in p]


def ring(points) -> list:
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    kept = simplify(points + points[:1], TOLERANCE)[:-1]
    return [round(v, 3) for p in kept for v in p] if len(kept) >= 3 else []


def anchor(parts) -> tuple:
    """면의 이름표 자리 — 가장 큰 고리의 무게중심, 그 고리 밖이면 무게중심에 가장 가까운 꼭짓점."""
    from viewer import paleo
    big = max(parts, key=lambda r: abs(signed_area(r)))
    area = signed_area(big)
    if abs(area) < 1e-12:
        xs, ys = zip(*big)
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx = sum((a[0] + b[0]) * (a[0] * b[1] - b[0] * a[1]) for a, b in zip(big, big[1:] + big[:1])) / (6 * area)
    cy = sum((a[1] + b[1]) * (a[0] * b[1] - b[0] * a[1]) for a, b in zip(big, big[1:] + big[:1])) / (6 * area)
    if paleo.inside(cx, cy, [v for p in big for v in p]):
        return cx, cy
    return min(big, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)


def _rank(row) -> int:
    try:
        return int(float(row.get("scalerank") or 10))
    except ValueError:
        return 10


def places(folder: Path) -> list:
    """`[이름, 한국어 이름, 갈래, 경도, 위도, 순위]` — 찾기와 이름표가 쓴다. 순위는 작을수록 크다(scalerank)."""
    out = []
    for name in ("ne_10m_geography_regions_polys.zip", "ne_10m_geography_marine_polys.zip"):
        rows, shp = read(folder, name)
        for row, parts in zip(rows, shp):
            if row.get("name") and parts:
                lon, lat = anchor(parts)
                out.append([row["name"], row.get("name_ko", ""), row["featurecla"], round(lon, 3), round(lat, 3), _rank(row)])
    rows, shp = read(folder, "ne_10m_populated_places.zip")
    for row in rows:
        if row.get("name") and row.get("longitude"):
            out.append([row["name"], row.get("name_ko", ""), "city", round(float(row["longitude"]), 3),
                        round(float(row["latitude"]), 3), _rank(row)])
    rows, shp = read(folder, "ne_10m_lakes.zip")
    for row, parts in zip(rows, shp):
        if row.get("name") and parts:
            lon, lat = anchor(parts)
            out.append([row["name"], row.get("name_ko", ""), "lake", round(lon, 3), round(lat, 3), _rank(row)])
    rows, shp = read(folder, "ne_10m_rivers_lake_centerlines.zip")
    seen = set()
    for row, parts in zip(rows, shp):
        if not row.get("name") or not parts or row["featurecla"] == "Canal" or row["name"] in seen:
            continue
        seen.add(row["name"])                      # 한 강이 여러 토막이다 — 첫 토막의 가운데 하나
        longest = max(parts, key=len)
        lon, lat = longest[len(longest) // 2]
        out.append([row["name"], row.get("name_ko", ""), "river", round(lon, 3), round(lat, 3), _rank(row)])
    return out


def water(folder: Path) -> dict:
    rows, shp = read(folder, "ne_10m_rivers_lake_centerlines.zip")
    lines = [[_rank(row), flat(part)] for row, parts in zip(rows, shp) if row["featurecla"] != "Canal"
             for part in parts if len(part) > 1]
    rows, shp = read(folder, "ne_10m_lakes.zip")
    lakes, islands = [], []
    for row, parts in zip(rows, shp):
        for part in parts:
            packed = ring(part)
            if packed:
                (islands if signed_area(part) > 0 else lakes).append([_rank(row), packed])
    return {"lines": lines, "lakes": lakes, "islands": islands}


def ice(folder: Path) -> dict:
    polys, holes = [], []
    for kind, name in ((0, "ne_10m_glaciated_areas.zip"), (1, "ne_10m_antarctic_ice_shelves_polys.zip")):
        rows, shp = read(folder, name)
        for parts in shp:
            for part in parts:
                packed = ring(part)
                if packed:
                    (holes if signed_area(part) > 0 else polys).append([kind, packed])
    return {"polys": polys, "holes": holes}


class Command(BaseCommand):
    help = "Natural Earth 10 m 묶음 폴더 → data/earth_places.json·earth_water.json·earth_ice.json (wetherilli 102)"

    def add_arguments(self, parser):
        parser.add_argument("folder", help="ne_10m_*.zip 일곱이 든 폴더")
        parser.add_argument("--out", help="적을 폴더 (기본 저장소의 data/)")

    def handle(self, *args, **opts):
        folder = Path(opts["folder"])
        out = Path(opts["out"] or Path(settings.EARTH_PLACES_FILE).parent)
        meta = {"source": CREDIT, "license": "public domain", "tolerance": TOLERANCE}
        written = {
            "earth_places.json": {"meta": meta, "fields": ["name", "name_ko", "kind", "lon", "lat", "rank"],
                                  "places": places(folder)},
            "earth_water.json": {"meta": meta, **water(folder)},
            "earth_ice.json": {"meta": meta, **ice(folder)},
        }
        for name, data in written.items():
            path = out / name
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            self.stdout.write(f"{name} {path.stat().st_size / 1e3:.0f} KB")
        self.stdout.write(f"지명 {len(written['earth_places.json']['places']):,} · 강 토막 "
                          f"{len(written['earth_water.json']['lines']):,} · 호수 {len(written['earth_water.json']['lakes']):,} · "
                          f"빙하·빙붕 {len(written['earth_ice.json']['polys']):,}")
