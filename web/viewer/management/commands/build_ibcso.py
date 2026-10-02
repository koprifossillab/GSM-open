"""IBCSO v2 의 칠한 판(해저면·얼음 위)을 3031 타일로 잘라 둔다 (devlog 047).

    manage.py build_ibcso                   원본이 있는 판을 다 자른다
    manage.py build_ibcso --layer bed       이 판만 자른다
    manage.py build_ibcso --dem             수치 격자만 자른다 (3D 의 지형, 051)
    manage.py build_ibcso --tid             자료 출처(TID)만 자른다 (071)

원본은 `<GSM_IBCSO_DIR>/` 에 둔다 — `IBCSO_v2_bed_RGB.tif`·`IBCSO_v2_ice-surface_RGB.tif`
(PANGAEA 937574, 원본은 NAS N:\\GSM\\sources\\ibcso\\). 잘라 둔 것은 `tiles-bed/`·`tiles-ice/` 의
`{z}/{x}/{y}.webp` 다. 3D 가 쓰는 한 벌은 원본의 9354 격자 그대로 `wide-bed/`·`wide-ice/` 에 든다.
새로 자른 것을 옆 자리(`.new`)에 다 쓰고 나서 바꿔 끼운다 — 자르는 동안에도
뷰어는 옛것을 낸다.

수치 격자(`IBCSO_v2_bed.tif`·`IBCSO_v2_ice-surface.tif`)가 있으면 그것도 원본의 9354 격자대로
`dem-bed/`·`dem-ice/` 의 `{단계}/{x}/{y}.png`(16 비트) 로 자른다 — 3D 가 지형으로 쓴다.

자료 출처 격자(`IBCSO_v2_TID.tif`)가 있으면 `tiles-tid/`(2D 레이어, 칠한 PNG)와 `tid-raw/`(누른 자리 읽기,
번호 그대로)로 자른다 — 번호라 섞지 않고 가장 가까운 화소를 쓴다.

원본을 통째로 풀어서 메모리를 몇 GB 쓴다. 다시 부를 일은 판이 바뀔 때뿐이다.
"""
import math
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import ibcso


class Command(BaseCommand):
    help = "IBCSO v2 의 칠한 판(해저면·얼음 위)을 남극 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--layer", choices=[n.split(":", 1)[1] for n in ibcso.SHEETS],
                            help="이 판만 자른다 (기본: 원본이 있는 판 모두)")
        parser.add_argument("--dem", action="store_true",
                            help="수치 격자(3D 지형)만 자른다. 칠한 판은 건드리지 않는다")
        parser.add_argument("--tid", action="store_true",
                            help="자료 출처(TID)만 자른다")

    def handle(self, *args, **options):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 3 억 7 천만 화소 — 폭탄이 아니라 지도다

        layer = options["layer"]
        if options["tid"]:
            path = ibcso.tid_source_file()
            if path is None:
                raise CommandError(f"원본이 없다 — {ibcso.TID_SOURCE} 를 {ibcso.root()} 에 둔다 "
                                   "(원본은 NAS N:\\GSM\\sources\\ibcso\\, PANGAEA 937574)")
            self._build_tid(path)
            return
        sheets = [] if options["dem"] else (
            [ibcso.SHEETS[f"ibcso:{layer}"]] if layer else list(ibcso.SHEETS.values()))
        dems = [ibcso.DEMS[layer]] if layer else list(ibcso.DEMS.values())
        jobs = [(s, s.source_file()) for s in sheets + dems]
        # 칠한 판을 자를 때 수치 격자는 덤이다 — 없으면 건너뛴다(운영에는 아직 없을 수 있다)
        required = sheets or dems
        missing = [s.source for s, path in jobs if path is None and s in required]
        if layer and missing or not any(path for _, path in jobs):
            raise CommandError(f"원본이 없다 — {', '.join(missing)} 를 {ibcso.root()} 에 둔다 "
                               "(원본은 NAS N:\\GSM\\sources\\ibcso\\, PANGAEA 937574)")
        for sheet, path in jobs:
            if not path:
                continue
            if isinstance(sheet, ibcso.DemSheet):
                self._build_dem(sheet, path)
            else:
                self._build(sheet, path)
        # 자료 출처는 덤이다 — 판 하나만 자를 때는 건드리지 않는다
        if not layer and ibcso.tid_source_file():
            self._build_tid(ibcso.tid_source_file())

    def _build(self, sheet, path):
        started = time.monotonic()
        try:
            full = ibcso.open_source(path)
        except (OSError, ibcso.IbcsoError) as exc:
            raise CommandError(f"{path} — {exc}") from exc
        self.stdout.write(f"{sheet.name} ← {path}")

        out = sheet.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for z in range(ibcso.MAX_ZOOM, -1, -1):
            # 줌 z 의 한 화소보다 거칠지 않게 원본을 줄여 둔다 — 줄인 것에서 자르면 빠르다
            res = ibcso.geomap.resolution(z) / ibcso.SCALE          # 9354 미터
            factor = max(1, 2 ** int(math.log2(res / ibcso.SOURCE_RES))) if res > ibcso.SOURCE_RES else 1
            level = full if factor == 1 else full.reduce(factor)
            n = 2 ** z
            for x in range(n):
                for y in range(n):
                    tile = ibcso.cut(level, factor, z, x, y)
                    if tile is None:
                        continue                    # 자료 밖 — 서버가 빈 타일을 낸다
                    data = ibcso.encode(tile)
                    target = fresh / str(z) / str(x) / f"{y}.{ibcso.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            self.stdout.write(f"  z{z} — {n}×{n} 칸, 원본 1/{factor}")
            del level

        self._swap(out, fresh)
        self.stdout.write(self.style.SUCCESS(
            f"타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))
        self._build_wide(sheet, full)

    def _build_wide(self, sheet, full):
        """3D 의 배경 — 같은 판을 원본의 9354 격자 그대로(수치 격자와 같은 단계) 자른다 (051)."""
        started = time.monotonic()
        out = sheet.wide_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for level in range(ibcso.DEM_MAX_LEVEL, -1, -1):
            factor = 2 ** (ibcso.DEM_MAX_LEVEL - level)
            image = full if factor == 1 else full.reduce(factor)
            n = ibcso.dem_tiles(level)
            for x in range(n):
                for y in range(n):
                    tile = ibcso.cut_wide(image, x, y)
                    if tile is None:
                        continue
                    data = ibcso.encode(tile)
                    target = fresh / str(level) / str(x) / f"{y}.{ibcso.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            del image
        self._swap(out, fresh)
        self.stdout.write(self.style.SUCCESS(
            f"  3D 배경 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))

    def _build_dem(self, sheet, path):
        """수치 격자 — 9354 격자 그대로, 단계 6(원본)에서 0 으로 반씩 줄여 가며 자른다."""
        started = time.monotonic()
        try:
            value, fill = ibcso.open_dem(path)
        except (OSError, ibcso.IbcsoError) as exc:
            raise CommandError(f"{path} — {exc}") from exc
        self.stdout.write(f"수치 {sheet.kind} ← {path}")

        out = sheet.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for level in range(ibcso.DEM_MAX_LEVEL, -1, -1):
            if level < ibcso.DEM_MAX_LEVEL:
                value, fill = ibcso.halve(value, fill)
            n = ibcso.dem_tiles(level)
            for x in range(n):
                for y in range(n):
                    tile = ibcso.cut_dem(value, fill, x, y)
                    if tile is None:
                        continue
                    data = ibcso.encode_dem(tile)
                    target = fresh / str(level) / str(x) / f"{y}.{ibcso.DEM_FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            self.stdout.write(f"  단계 {level} — {n}×{n} 칸, 한 화소 {ibcso.dem_res(level):.0f} m")

        self._swap(out, fresh)
        self.stdout.write(self.style.SUCCESS(
            f"수치 타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))

    def _build_tid(self, path):
        """자료 출처 — 누른 자리 읽기용 번호 타일(9354 단계 6)과 2D 레이어용 칠한 타일(3031 줌 0–6)."""
        from PIL import Image
        started = time.monotonic()
        try:
            codes = ibcso.open_tid(path)
        except (OSError, ibcso.IbcsoError) as exc:
            raise CommandError(f"{path} — {exc}") from exc
        self.stdout.write(f"자료 출처 ← {path}")

        out = ibcso.tid_raw_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = 0
        n = ibcso.dem_tiles(ibcso.DEM_MAX_LEVEL)
        for x in range(n):
            for y in range(n):
                tile = ibcso.cut_tid_raw(codes, x, y)
                if tile is None:
                    continue
                target = fresh / str(ibcso.DEM_MAX_LEVEL) / str(x) / f"{y}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                tile.save(target, format="PNG", optimize=True)
                written += 1
        self._swap(out, fresh)
        self.stdout.write(f"  번호 타일 {written} 장 — {out}")

        painted = ibcso.tid_paint(codes)
        del codes
        out = ibcso.tid_tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for z in range(ibcso.MAX_ZOOM, -1, -1):
            res = ibcso.geomap.resolution(z) / ibcso.SCALE
            factor = max(1, 2 ** int(math.log2(res / ibcso.SOURCE_RES))) if res > ibcso.SOURCE_RES else 1
            # 번호라 평균하지 않는다 — factor 칸마다 한 화소를 집는다
            level = painted if factor == 1 else painted.resize(
                (ibcso.SOURCE_SIZE // factor, ibcso.SOURCE_SIZE // factor), Image.NEAREST)
            for x in range(2 ** z):
                for y in range(2 ** z):
                    tile = ibcso.cut_tid(level, factor, z, x, y)
                    if tile is None:
                        continue
                    data = ibcso.encode_tid(tile)
                    target = fresh / str(z) / str(x) / f"{y}.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            del level
        self._swap(out, fresh)
        self.stdout.write(self.style.SUCCESS(
            f"자료 출처 타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))

    @staticmethod
    def _swap(out, fresh):
        """새로 자른 것을 옆 자리에서 바꿔 끼운다 — 자르는 동안에도 뷰어는 옛것을 낸다."""
        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        fresh.rename(out)
        shutil.rmtree(old, ignore_errors=True)
