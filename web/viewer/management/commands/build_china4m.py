"""중국 지질도 1:400만 스캔을 3857 타일로 잘라 둔다 (wetherilli 387).

    manage.py build_china4m                 <GSM_CHINA4M_DIR>/GeoChina400*.jpg + GeoChina400_mask.png → tiles/{z}/{x}/{y}.webp
    manage.py build_china4m --max-zoom 6    시험 삼아 거친 줌만
    manage.py build_china4m --units-only    색 번호 격자(units.u8)만 — 범례(data/china4m_legend.json)를 고쳤을 때

마스크(`build_china4m_mask`, numpy 가 있는 곳에서 한 번)가 먼저 있어야 한다. 이 명령은 **Pillow 만** 쓴다 — 컨테이너에서도 돈다.
새로 자른 것을 옆 자리(`.new`)에 다 쓰고 나서 바꿔 끼운다 — 자르는 동안에도 뷰어는 옛것을 낸다.

원본을 통째로 풀어 땅 밖을 투명하게 하고 미리 곱해 둔다. 메모리를 1.2 GB 남짓 쓴다.

타일과 함께 **색 번호 격자**(`units.u8`·`units.json`, wetherilli 388)도 굽는다 — 원본을 범례 색으로 칠한 것이다. 누른 자리의 속성과
보는 범위의 범례가 이것을 읽는다.
"""
import hashlib
import json
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import china4m


class Command(BaseCommand):
    help = "중국 지질도 1:400만 스캔을 3857 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--source", help="원본 스캔 (기본: GSM_CHINA4M_DIR 의 GeoChina400*.jpg)")
        parser.add_argument("--max-zoom", type=int, default=china4m.MAX_ZOOM, help="여기까지만 자른다")
        parser.add_argument("--units-only", action="store_true", help="색 번호 격자만 다시 굽는다")

    def handle(self, *args, **options):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 1 억 5 천만 화소 — 폭탄이 아니라 지도다

        started = time.monotonic()
        path = options["source"] or china4m.source_file()
        if not path:
            raise CommandError(f"원본이 없다 — {china4m.root()}/{china4m.SOURCE} (원본은 NAS N:\\GSM\\sources\\china4m\\)")
        mask_path = china4m.mask_file()
        if not mask_path.exists():
            raise CommandError(f"마스크가 없다 — {mask_path}. numpy·scipy 가 있는 파이썬으로 build_china4m_mask 를 먼저 부른다")
        image = Image.open(path).convert("RGB")
        if image.size != china4m.SIZE:
            raise CommandError(f"그림이 {image.size} 다 — {china4m.SIZE} 를 기다렸다")
        mask = Image.open(mask_path).convert("L")
        if mask.size != image.size:
            raise CommandError(f"마스크가 {mask.size} 다 — 원본과 크기가 다르다")
        self._units(image, mask)
        if options["units_only"]:
            return
        image.putalpha(mask)
        del mask
        # 줄일 때 투명한 가장자리가 희게 번지지 않게 미리 곱해 둔다 (peninsula 와 같다)
        full = image.convert("RGBa")
        del image
        self.stdout.write(f"{china4m.NAME} ← {path}")

        out = china4m.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        levels = {1: full}
        written = size = 0
        for z in range(min(options["max_zoom"], china4m.MAX_ZOOM), china4m.MIN_ZOOM - 1, -1):
            factor = china4m.factor_for(z)
            if factor not in levels:
                levels[factor] = full.reduce(factor)
            level = levels[factor]
            x0, y0, x1, y1 = china4m.tile_range(z)
            count = 0
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    tile = china4m.cut(level, factor, z, x, y)
                    if tile is None:
                        continue                    # 중국 밖 — 서버가 빈 타일을 낸다
                    data = china4m.encode(tile)
                    target = fresh / str(z) / str(x) / f"{y}.{china4m.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    count += 1
                    size += len(data)
            written += count
            self.stdout.write(f"  z{z} — 1/{factor} 에서 {count} 장")

        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        fresh.rename(out)
        shutil.rmtree(old, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS(
            f"타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))

    def _units(self, image, mask):
        w, h, data = china4m.build_units(image, mask)
        out = china4m.root() / china4m.UNITS
        fresh = out.with_name(out.name + ".new")
        fresh.write_bytes(data)
        fresh.replace(out)
        legend = china4m.legend_path().read_bytes()
        meta = {"width": w, "height": h, "scale": china4m.UNITS_SCALE, "classes": len(china4m.classes()),
                "legend_sha256": hashlib.sha256(legend).hexdigest()}
        (china4m.root() / china4m.UNITS_META).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        inside = sum(1 for v in data[::97] if v != china4m.OUTSIDE)
        ink = sum(1 for v in data[::97] if v == china4m.INK)
        self.stdout.write(f"색 번호 격자 {w}×{h}, 범례 색 {sum(1 for ids in china4m.classes() if ids)} — 땅 안의 먹 {ink / max(inside, 1) * 100:.1f} %")
