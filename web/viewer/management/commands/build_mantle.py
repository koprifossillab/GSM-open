"""맨틀 슬랩 — Müller et al. (2022) OPT1 의 ParaView 묶음을 시점마다 풀어 `<EARTH_DIR>/mantle/` 에 둔다 (wetherilli 106).

원본은 Zenodo 6622194 의 `OPT1_3D_visualisation_ParaView.zip`(206 MB, CC BY 4.0 — 레코드가 그렇게 적는다). NAS `sources/earth/` 에
둔다. 확인값은 EarthThruTime3D 가 적은 것(8e6d64a5…)과 같다. 시점 51 개 × 레이어 셋(섭입한 판·하부 더미·판 경계)을 float32 xyz
+ uint32 이음으로 적고 gzip 한 것을 곁에 둔다(합쳐 175 MB 남짓, gzip 90 MB 남짓). 저장소에 두지 않는다.
"""
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import mantle

SHA256 = "8e6d64a5910bc6fc1f335a135b4e53d0be5a51f8b38a772f82376cf905482f67"


class Command(BaseCommand):
    help = "OPT1 ParaView zip → <EARTH_DIR>/mantle/ (맨틀 슬랩, wetherilli 106)"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="OPT1_3D_visualisation_ParaView.zip")
        parser.add_argument("--frames", nargs="+", type=int, help="시점만 골라서 (0–50, 50 이 오늘)")

    def handle(self, *args, **opts):
        src = Path(opts["zip"])
        h = hashlib.sha256()
        with open(src, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != SHA256:
            raise CommandError(f"확인값이 다르다 — {h.hexdigest()[:12]}… (기대 {SHA256[:12]}…)")
        out = mantle.folder()
        out.mkdir(parents=True, exist_ok=True)
        frames = sorted(set(opts["frames"] or range(mantle.FRAMES)))
        cat = {"source": "Müller et al. 2022 OPT1 supplementary data v3.0", "sha256": SHA256, "credit": mantle.CREDIT,
               "layout": "little-endian float32 xyz (unit sphere, z north), then uint32 indices", "frames": []}
        total = 0
        with zipfile.ZipFile(src) as zf:
            for frame in frames:
                entry = {"frame": frame, "age_ma": mantle.age_of(frame), "layers": {}}
                for name in mantle.LAYERS:
                    try:
                        points, conn = mantle.read_layer(zf, name, frame)
                    except (KeyError, mantle.MantleError) as exc:
                        raise CommandError(f"{frame} 시점 {name}: {exc}") from exc
                    data = points.tobytes() + conn.tobytes()
                    digest = hashlib.sha256(data).hexdigest()
                    fname = f"{name}-{frame:02d}-{digest[:12]}.bin"
                    (out / fname).write_bytes(data)
                    (out / (fname + ".gz")).write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
                    entry["layers"][name] = {"file": fname, "points": len(points) // 3, "indices": len(conn),
                                             "bytes": len(data)}
                    total += len(data)
                cat["frames"].append(entry)
                self.stdout.write(f"  {entry['age_ma']:g} Ma")
        (out / "catalogue.json").write_text(json.dumps(cat, indent=1), encoding="utf-8")
        mantle._catalogue.cache_clear()
        self.stdout.write(f"{len(frames)} 시점 · {total / 1e6:.0f} MB → {out}")
