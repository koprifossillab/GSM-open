"""한반도 지질도 판(음영판·민판)을 5179 타일로 잘라 둔다 (devlog 027·028).

    manage.py build_peninsula                           원본이 있는 판을 다 자른다
    manage.py build_peninsula --layer plain             이 판만 자른다
    manage.py build_peninsula --layer shaded --source 다른.pdf

원본은 `<GSM_PENINSULA_DIR>/` 에 둔다 — 음영판은 `*.pdf`, 민판은 `*.png` 와 옆의 `.pgw`.
잘라 둔 것은 판마다 `tiles/`(음영판)·`tiles-plain/`(민판) 의 `{z}/{x}/{y}.webp` 다. 새로 자른
것을 옆 자리(`.new`)에 다 쓰고 나서 바꿔 끼운다 — 자르는 동안에도 뷰어는 옛것을 낸다.

원본을 통째로 풀어서 **메모리를 3.5 GB 쓴다** (음영판, 2026-09-28 에 쟀다, 24 초). 서버가
빠듯하면 다른 곳에서 잘라 타일 폴더만 옮겨도 된다. 다시 부를 일은 판이 바뀔 때뿐이다.
"""
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import peninsula


class Command(BaseCommand):
    help = "한반도 지질도 판(음영판 PDF·민판 PNG)을 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--layer", choices=[n.split(":", 1)[1] for n in peninsula.SHEETS],
                            help="이 판만 자른다 (기본: 원본이 있는 판 모두)")
        parser.add_argument("--source", help="잘라 낼 원본 (--layer 와 함께. 기본: GSM_PENINSULA_DIR 의 것)")

    def handle(self, *args, **options):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 1 억 7 천만 화소 — 폭탄이 아니라 지도다

        if options["source"] and not options["layer"]:
            raise CommandError("--source 는 --layer 와 함께 준다")
        if options["layer"]:
            sheet = peninsula.SHEETS[f"peninsula:{options['layer']}"]
            path = options["source"] or sheet.source_file()
            if not path:
                raise CommandError(f"{sheet.name} 의 원본({sheet.source})이 없다 — {peninsula.root()} 에 둔다 "
                                   "(원본은 NAS N:\\GSM\\sources\\peninsula\\)")
            jobs = [(sheet, path)]
        else:
            jobs = [(s, s.source_file()) for s in peninsula.SHEETS.values() if s.source_file()]
            if not jobs:
                raise CommandError(f"원본이 없다 — {peninsula.root()} 에 둔다 (원본은 NAS N:\\GSM\\sources\\peninsula\\)")
        for sheet, path in jobs:
            self._build(sheet, path)

    def _build(self, sheet, path):
        started = time.monotonic()
        try:
            image = peninsula.open_source(sheet, path)
        except (OSError, peninsula.PeninsulaError) as exc:
            raise CommandError(f"{path} — {exc}") from exc
        self.stdout.write(f"{sheet.name} ← {path} — {image.size[0]}×{image.size[1]}")
        # 흰 바탕을 투명하게 하고, 줄일 때 가장자리가 희게 번지지 않게 미리 곱해 둔다
        full = peninsula.transparent_white(image).convert("RGBa")
        del image

        out = sheet.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for z in range(sheet.max_zoom, -1, -1):
            factor = 2 ** (sheet.max_zoom - z)
            level = full if factor == 1 else full.reduce(factor)
            cols, rows = sheet.grid_size(z)
            for x in range(cols):
                for y in range(rows):
                    tile = peninsula.cut(sheet, level, factor, z, x, y)
                    if tile is None:
                        continue                    # 다 투명하다 — 서버가 빈 타일을 낸다
                    data = peninsula.encode(tile)
                    target = fresh / str(z) / str(x) / f"{y}.{peninsula.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            self.stdout.write(f"  z{z} — {cols}×{rows} 칸")

        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        fresh.rename(out)
        shutil.rmtree(old, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS(
            f"타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))
