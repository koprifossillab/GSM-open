"""타일 캐시를 줄인다.

    manage.py prune_tiles              지금 얼마나 들고 있는지 보고 줄인다 (나이·크기 한계로)
    manage.py prune_tiles --dry-run    줄이지 않고 보기만
    manage.py prune_tiles --all        통째로 비운다

늙은 것(`GSM_TILE_CACHE_MAX_AGE_DAYS`)을 먼저 버리고, 그래도 크면
(`GSM_TILE_CACHE_MAX_BYTES`) **오래 안 쓰인 것부터** 버린다.

**저절로 돌지 않는다.** 2026-09-27 부터 캐시는 받은 것을 계속 보탠다
(devlog 007). 디스크를 비워야 할 때 사람이 부른다. 속성(`.json`)도 함께 센다.
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from viewer import tilecache


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} GB"


class Command(BaseCommand):
    help = "타일 캐시를 줄인다"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="줄이지 않고 보기만")
        parser.add_argument("--all", action="store_true", help="통째로 비운다")
        parser.add_argument("--max-bytes", type=int, default=None)
        parser.add_argument("--max-age-days", type=int, default=None)

    def handle(self, *args, **options):
        if not tilecache.enabled():
            self.stdout.write("캐시가 꺼져 있다 (GSM_TILE_CACHE_DIR 가 비었다).")
            return

        before = tilecache.stats()
        self.stdout.write(
            f"캐시: {settings.TILE_CACHE_DIR}\n"
            f"지금  {before['count']}장 · {human(before['bytes'])}")

        if options["all"]:
            if options["dry_run"]:
                self.stdout.write("--dry-run 이라 비우지 않았다.")
                return
            root = Path(settings.TILE_CACHE_DIR)
            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
            self.stdout.write(self.style.SUCCESS("통째로 비웠다."))
            return

        max_bytes = (options["max_bytes"] if options["max_bytes"] is not None
                     else settings.TILE_CACHE_MAX_BYTES)
        max_age = (options["max_age_days"] if options["max_age_days"] is not None
                   else settings.TILE_CACHE_MAX_AGE_DAYS)
        self.stdout.write(f"한계  {max_age}일 · {human(max_bytes)}")

        if options["dry_run"]:
            over = max(0, before["bytes"] - max_bytes) if max_bytes > 0 else 0
            self.stdout.write(
                f"--dry-run — 크기로 버릴 것 약 {human(over)}. "
                "나이로 버릴 것은 실제로 돌려야 안다.")
            return

        result = tilecache.prune(max_bytes=max_bytes, max_age_days=max_age)
        self.stdout.write(self.style.SUCCESS(
            f"늙어서 버린 것 {result['removed_age']}장, "
            f"자리가 모자라 버린 것 {result['removed_size']}장\n"
            f"남은 것  {result['count']}장 · {human(result['bytes'])}"))
