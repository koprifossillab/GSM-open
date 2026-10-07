"""그때의 땅과 바다 밑 — PaleoDEM 6 분 격자를 `<EARTH_DIR>/paleodem/` 에 칠한 그림으로 굽는다 (wetherilli 375).

원본은 Zenodo 5460860 의 `Scotese_Wright_2018_Maps_1-88_6minX6min_PaleoDEMS_nc.zip`(207 MB, CC BY 4.0 — 묶음 안
`License.txt`)이다. NAS `sources/earth/` 에 둔다. 크기·SHA-256 은 WegenersDream `sources/paleodem.json` 과 같다.

**호스트에서만 돈다** — NetCDF-4 를 h5py 로, 음영을 numpy 로 셈한다. 제품 이미지에는 둘 다 없다:

    /srv/GSM/scripts/run.sh build_paleodem /nfs/temp-share/GSM/sources/earth/Scotese_Wright_2018_Maps_1-88_6minX6min_PaleoDEMS_nc.zip

109 시점에 몇 분 걸린다. 구운 것은 시점마다 WebP 한 장과 `index.json` 이다.
"""
import hashlib
import json
import zipfile
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from viewer import paleodem

#: WegenersDream 이 2026-09-29 에 적은 값(그쪽은 ETT 의 것과 맞췄다)
SHA256 = "ab360184d8260a815ef5ed6b8b4e0abdbf99ef5ee8aa87dfd070af323ceb42da"


class Command(BaseCommand):
    help = "PaleoDEM 6 분 격자 zip → <EARTH_DIR>/paleodem/ (그때의 땅과 바다 밑, 호스트에서만, wetherilli 375)"

    def add_arguments(self, parser):
        parser.add_argument("zip", help="Scotese_Wright_2018_Maps_1-88_6minX6min_PaleoDEMS_nc.zip")
        parser.add_argument("--only", type=float, nargs="*", help="이 시점(Ma)만 — 시험 삼아 몇 장")

    def handle(self, *args, **opts):
        try:
            import h5py  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            raise CommandError("numpy·h5py 가 없다 — 호스트의 /srv/GSM/scripts/run.sh build_paleodem <zip> 으로 부른다")
        digest = hashlib.sha256()
        with open(opts["zip"], "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != SHA256:
            raise CommandError(f"SHA-256 이 다르다 — {digest.hexdigest()}")
        out = paleodem.root()
        out.mkdir(parents=True, exist_ok=True)
        old = paleodem.index()
        ages = {float(a) for a in old["ages"]} if old and opts["only"] else set()
        with zipfile.ZipFile(opts["zip"]) as z:
            members = []
            for name in z.namelist():
                found = paleodem.NAME.search(name)
                if found and name.endswith(".nc") and not name.startswith("__MACOSX/"):
                    members.append((float(found.group("age")), found.group("label").replace("_", " ").strip(), name))
            if len(members) < 100:
                raise CommandError(f"격자가 {len(members)} 장뿐이다")
            for age, label, name in sorted(members):
                if opts["only"] and age not in opts["only"]:
                    continue
                image, land = paleodem.render(paleodem.read_grid(z.read(name)))
                image.save(out / f"{paleodem.key(age)}.webp", "WEBP", quality=paleodem.QUALITY, method=6)
                ages.add(age)
                self.stdout.write(f"  {age:6.1f} Ma  {label:40s} 뭍 {land:5.1%}")
        index = {"ages": sorted(ages),
                 "meta": {"cite": paleodem.CITE, "sha256": SHA256, "renderer": paleodem.RENDERER,
                          "built": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}}
        (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{len(ages)} 시점 → {out}"))
