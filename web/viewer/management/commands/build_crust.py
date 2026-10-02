"""지각 두께 — CRUST 2.0 을 1° 격자 `data/crust2_thickness.json` 으로 굽는다 (wetherilli 101).

원본은 EarthByte 의 GPlates 2.3 배포본 `Crustal_Thickness.zip`(84 MB, 묶음 안 `License.txt` 가 CC BY 4.0) 이다 — Laske, Masters &
Reif (2000) 의 2° 모형을 2 분 격자로 다시 뽑은 NetCDF 다. NAS `sources/earth/` 에 둔다. 원 누리집(UCSD)의 판은 허가를 적지 않아
EarthThruTime3D 처럼 이 배포본을 쓴다.

**EarthThruTime3D 의 `scripts/build_crust.py`(MIT)처럼 1° 칸의 가운데에 선 원본 격자점을 그대로 뽑는다** — 대륙·바다 경계를
가로질러 평균하지 않는다. 모형은 2° 라 1° 로 뽑아도 새로 자세해지지 않는다. 0.1 km 로 적고 빈 칸은 null 이다.

NetCDF4(HDF5)를 읽으려면 `h5py` 가 있어야 한다. 제품은 h5py 를 쓰지 않는다 — 구운 것(수백 KB, CC BY 4.0)을 저장소에 두고,
굽는 사람만 h5py 가 있는 파이썬으로 부른다.
"""
import hashlib
import json
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

#: 2026-09-16 ETT 가 적고(`sources/crust/crust2.json`) 2026-09-30 우리가 받아 맞춘 값
SHA256 = "0375cf41ea79d007ffe3452825131de69a438ff1ef1101c9faca5eb3c1299933"
MEMBER = "Crustal_Thickness/Crustal_Thickness/Crustal_Thickness.nc"
LICENSE = "Crustal_Thickness/License.txt"


def sample(z, lat, lon) -> list:
    """2 분 격자(5401 × 10801, 남→북·서→동의 격자점) → 1° 칸 가운데의 값, 북→남 줄 180 개 × 360. 0.1 km 정수, 빈 칸 None."""
    if z.shape != (5401, 10801) or abs(lat[0] + 90) > 1e-6 or abs(lon[0] + 180) > 1e-6 or abs(lat[30] - lat[0] - 1) > 1e-6:
        raise CommandError("원본 격자의 꼴이 다르다")
    rows = []
    for j in range(179, -1, -1):                       # 북쪽 줄부터
        row = []
        for v in z[15 + 30 * j, 15:10800:30]:
            v = float(v)
            if v != v:                                  # NaN
                row.append(None)
            elif not 0 <= v <= 80:
                raise CommandError(f"범례(0–80 km) 밖의 값 {v}")
            else:
                row.append(round(v * 10))
        rows.append(row)
    return rows


class Command(BaseCommand):
    help = "CRUST 2.0 (EarthByte GPlates 2.3) zip → data/crust2_thickness.json (지각 두께, wetherilli 101)"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="Crustal_Thickness.zip")
        parser.add_argument("--out", help="적을 파일 (기본 settings.CRUST_FILE)")

    def handle(self, *args, **opts):
        try:
            import h5py
        except ImportError as exc:
            raise CommandError("h5py 가 없다 — NetCDF4(HDF5)를 읽으려면 h5py 가 있는 파이썬으로 부른다") from exc
        src = Path(opts["zip"])
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest != SHA256:
            raise CommandError(f"확인값이 다르다 — {digest[:12]}… (기대 {SHA256[:12]}…)")
        import io
        with zipfile.ZipFile(src) as zf:
            if "Creative Commons Attribution 4.0" not in zf.read(LICENSE).decode():
                raise CommandError("묶음의 허가가 CC BY 4.0 이 아니다")
            with h5py.File(io.BytesIO(zf.read(MEMBER)), "r") as f:
                rows = sample(f["z"], f["lat"][:], f["lon"][:])
        out = Path(opts["out"] or settings.CRUST_FILE)
        out.write_text(json.dumps({
            "meta": {"title": "CRUST 2.0 crustal thickness", "unit": "0.1 km", "grid": "1° cells, north to south, "
                     "west to east from 180° W", "model_resolution_deg": 2,
                     "cite": "Laske, G., Masters, G. & Reif, C. (2000) CRUST 2.0: A new global crustal model at 2×2 degrees. "
                             "EarthByte GPlates 2.3 raster distribution",
                     "license": "CC BY 4.0", "sha256": SHA256},
            "rows": rows,
        }, separators=(",", ":")), encoding="utf-8")
        missing = sum(v is None for r in rows for v in r)
        self.stdout.write(f"180 × 360 칸, 빈 칸 {missing} → {out} ({out.stat().st_size / 1e3:.0f} KB)")
