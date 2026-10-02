"""최근 빙기의 빙상 가장자리 — NADI-1·DATED-1 을 `data/ice_margins.json` 으로 굽는다 (wetherilli 104).

| 원본 | 무엇 | 허가 |
|---|---|---|
| NADI-1 (Dalton et al. 2023, Zenodo 8161764, 55 MB) | 북미 빙상(로렌타이드·코딜레라·이누이트) 25–1 ka, 500 년마다. 최적·최소·최대 가운데 **최적**(`OPTIMAL`) | CC BY 4.0 |
| DATED-1 (Hughes et al. 2016, PANGAEA 848117, 12 MB) | 유라시아 빙상(영국–아일랜드·스칸디나비아·스발바르–바렌츠–카라) 25–10 ka, 천 년마다. **가장 믿을 만한 것**(`mc`) | CC BY 3.0 |

두 묶음 모두 NAS `sources/earth/` 에 둔다. EarthThruTime3D 가 적은 확인값과 같다. DATED-1 은 북극 람베르트 등적 방위도법(WGS84)이라
`crs.laea_north_to_latlon` 으로 편다. 고리는 셰이프파일 관례로 가른다(시계 방향이 얼음, 반시계가 그 안의 구멍) — 편 좌표가 아니라
원본의 평면 좌표에서 가른다. 0.05°(5 km 남짓)로 줄여 저장소에 둔다.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import crs
from viewer.management.commands.build_natural_earth import shapes
from viewer.management.commands.build_paleocoastlines import signed_area
from viewer.management.commands.build_paleomap import simplify

SHA256 = {"nadi": "cbfdc0c14a8bd08eb13036ca488ec611de7d2d9b61bed22f03aec2e272b4cb44",
          "dated": "a916de31ff31b0bb63863b82d61a6be02659ecfe36a7cab0fdf00034b38be1f1"}
NADI = re.compile(r"/(\d+(?:\.\d+)?)ka_cal_OPTIMAL_NADI-1_Dalton_etal_QSR\.shp$")
DATED = re.compile(r"/TS(\d+)_mc\.shp$")
TOLERANCE = 0.05
CITE = {"nadi": "Dalton, A. S. et al. (2023) NADI-1, Quaternary Science Reviews 321, 108345 · CC BY 4.0",
        "dated": "Hughes, A. L. C. et al. (2016) DATED-1, Boreas 45, 1–45 · CC BY 3.0"}


def pack(ring_ll) -> list:
    pts = ring_ll[:-1] if len(ring_ll) > 1 and ring_ll[0] == ring_ll[-1] else ring_ll
    kept = simplify(pts + pts[:1], TOLERANCE)[:-1]
    return [round(v, 3) for p in kept for v in p] if len(kept) >= 3 else []


def slices(path: Path, which: str, pattern, to_ll) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256[which]:
        raise CommandError(f"{path.name} 의 확인값이 다르다 — {digest[:12]}… (기대 {SHA256[which][:12]}…)")
    out = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            m = pattern.search(name)
            if not m:
                continue
            ice, holes = [], []
            for parts in shapes(zf.read(name)):
                for part in parts:
                    packed = pack([to_ll(x, y) for x, y in part])
                    if packed:
                        (holes if signed_area(part) > 0 else ice).append(packed)
            out[f"{float(m.group(1)):g}"] = {"ice": ice, "holes": holes}
    if not out:
        raise CommandError(f"{path.name} 에서 조각을 찾지 못했다")
    return out


def _dated_ll(x, y):
    lat, lon = crs.laea_north_to_latlon(x, y)
    return lon, lat


class Command(BaseCommand):
    help = "NADI-1·DATED-1 zip → data/ice_margins.json (최근 빙기의 빙상 가장자리, wetherilli 104)"

    def add_arguments(self, parser):
        parser.add_argument("nadi", help="NADI-1 shapefiles Dalton et al. QSR.zip")
        parser.add_argument("dated", help="DATED-1_TimeSlices_shp.zip")
        parser.add_argument("--out", help="적을 파일 (기본 settings.ICE_MARGINS_FILE)")

    def handle(self, *args, **opts):
        data = {"meta": {"cite": CITE, "tolerance": TOLERANCE, "unit": "ka"},
                "nadi": slices(Path(opts["nadi"]), "nadi", NADI, lambda x, y: (x, y)),
                "dated": slices(Path(opts["dated"]), "dated", DATED, _dated_ll)}
        out = Path(opts["out"] or settings.ICE_MARGINS_FILE)
        out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        self.stdout.write(f"NADI-1 {len(data['nadi'])} 조각 · DATED-1 {len(data['dated'])} 조각 → {out} "
                          f"({out.stat().st_size / 1e6:.1f} MB)")
