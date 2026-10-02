"""받아온 타일을 디스크에 두는 자리.

여기서 지키는 것은 넷이다 — **인증키가 열쇠에 섞이지 않는 것**(섞이면 키가
나온 날 받아둔 것을 전부 버린다), **캐시가 깨져도 뷰어가 멈추지 않는 것**,
**늙은 것은 다시 묻되 상류가 못 주면 옛것을 내는 것**, 그리고 **디스크가
모자라면 더 담지 않는 것**. 사람이 부르면 줄이기도 한다(`prune`).
"""
import os
import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from viewer import tilecache

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


class CacheCase(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-tiles-")
        patch = override_settings(
            TILE_CACHE_DIR=self.dir,
            TILE_CACHE_MAX_AGE_DAYS=30,
            TILE_CACHE_MAX_BYTES=10 * 1024 * 1024,
            TILE_CACHE_MIN_FREE_BYTES=0,
        )
        patch.enable()
        self.addCleanup(patch.disable)

    def files(self):
        return [p for p in Path(self.dir).rglob("*") if p.is_file()]


class Key(CacheCase):
    MAP = {"layers": "L_50K_Geology_Map", "bbox": "1,2,3,4",
           "width": "256", "height": "256", "srs": "EPSG:3857"}

    def test_같은_요청은_같은_열쇠(self):
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", dict(self.MAP)))

    def test_인증키는_열쇠에_섞이지_않는다(self):
        """키가 없을 때 받아둔 타일을, 키가 생긴 뒤에도 그대로 쓴다."""
        with_key = dict(self.MAP, key="SECRET")
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", with_key))

    def test_범위가_다르면_열쇠도_다르다(self):
        other = dict(self.MAP, bbox="9,9,9,9")
        self.assertNotEqual(tilecache.key_for("map", self.MAP),
                            tilecache.key_for("map", other))

    def test_레이어가_다르면_열쇠도_다르다(self):
        other = dict(self.MAP, layers="L_250K_Geology_Map")
        self.assertNotEqual(tilecache.key_for("map", self.MAP),
                            tilecache.key_for("map", other))

    def test_대소문자와_빈칸은_같은_것으로_본다(self):
        other = dict(self.MAP, layers=" l_50k_geology_map ")
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", other))

    def test_속성의_변수가_타일_열쇠를_바꾸지_않는다(self):
        """KEY_PARAMS 에 속성 변수를 더해도 받아둔 타일의 열쇠는 그대로다."""
        import hashlib
        parts = ["map", "layers=l_50k_geology_map", "srs=epsg:3857",
                 "bbox=1,2,3,4", "width=256", "height=256"]
        old = hashlib.sha256("&".join(parts).encode()).hexdigest()
        self.assertEqual(tilecache.key_for("map", self.MAP), old)

    def test_누른_픽셀이_다르면_속성_열쇠도_다르다(self):
        a = dict(self.MAP, query_layers="L_50K_Geology_Map", x="10", y="10")
        self.assertNotEqual(tilecache.key_for("info", a),
                            tilecache.key_for("info", dict(a, x="11")))

    def test_지도와_범례는_섞이지_않는다(self):
        self.assertNotEqual(tilecache.key_for("map", {"layer": "a"}),
                            tilecache.key_for("legend", {"layer": "a"}))


class PutGet(CacheCase):
    def test_넣고_꺼낸다(self):
        tilecache.put("a" * 64, PNG)
        self.assertEqual(tilecache.get("a" * 64), PNG)

    def test_없으면_None(self):
        self.assertIsNone(tilecache.get("b" * 64))

    def test_두자씩_갈라_담는다(self):
        key = "abcd" + "0" * 60
        tilecache.put(key, PNG)
        self.assertTrue((Path(self.dir) / "ab" / "cd" / f"{key}.png").exists())

    def test_빈_것은_넣지_않는다(self):
        tilecache.put("c" * 64, b"")
        self.assertEqual(self.files(), [])

    def test_늙으면_없는_셈_친다(self):
        key = "d" * 64
        tilecache.put(key, PNG)
        old = time.time() - 31 * 86400
        os.utime(tilecache._path(key), (old, old))
        self.assertIsNone(tilecache.get(key))

    def test_늙은_것도_달라면_내준다(self):
        """상류가 못 줄 때를 위한 것이다. 늙었다고 지우지 않는다."""
        key = "d" * 64
        tilecache.put(key, PNG)
        old = time.time() - 400 * 86400
        os.utime(tilecache._path(key), (old, old))
        self.assertEqual(tilecache.get(key, stale=True), PNG)

    def test_JSON_은_PNG_와_따로_담긴다(self):
        key = "9" * 64
        tilecache.put(key, b'{"a":1}', ".json")
        self.assertIsNone(tilecache.get(key))
        self.assertEqual(tilecache.get(key, ".json"), b'{"a":1}')
        self.assertEqual(tilecache.stats()["count"], 1)

    def test_디스크_여유가_모자라면_더_담지_않는다(self):
        with override_settings(TILE_CACHE_MIN_FREE_BYTES=1 << 62):
            tilecache.put("8" * 64, PNG)
        self.assertEqual(self.files(), [])

    def test_반쯤_쓰다_만_파일을_남기지_않는다(self):
        tilecache.put("e" * 64, PNG)
        self.assertEqual([p.suffix for p in self.files()], [".png"])

    @override_settings(TILE_CACHE_DIR="")
    def test_꺼두면_아무_일도_하지_않는다(self):
        self.assertFalse(tilecache.enabled())
        tilecache.put("f" * 64, PNG)          # 터지지 않는다
        self.assertIsNone(tilecache.get("f" * 64))

    def test_쓸_수_없는_자리여도_멈추지_않는다(self):
        """캐시는 덤이다. 디스크가 막혀도 뷰어는 돌아야 한다."""
        with override_settings(TILE_CACHE_DIR="/proc/못쓰는자리"):
            tilecache.put("g" * 64, PNG)      # 예외가 새어나오면 안 된다
            self.assertIsNone(tilecache.get("g" * 64))


class Prune(CacheCase):
    def test_늙은_것을_버린다(self):
        fresh, old = "1" * 64, "2" * 64
        tilecache.put(fresh, PNG)
        tilecache.put(old, PNG)
        stamp = time.time() - 40 * 86400
        os.utime(tilecache._path(old), (stamp, stamp))

        result = tilecache.prune()
        self.assertEqual(result["removed_age"], 1)
        self.assertIsNotNone(tilecache.get(fresh))
        self.assertFalse(tilecache._path(old).exists())

    def test_자리가_모자라면_오래_안_쓰인_것부터_버린다(self):
        keys = [str(i) * 64 for i in range(1, 5)]
        for i, key in enumerate(keys):
            tilecache.put(key, PNG)
            stamp = time.time() - (100 - i)     # 앞의 것일수록 오래 안 쓰였다
            os.utime(tilecache._path(key), (stamp, time.time()))

        # 두 장만 들어갈 만큼으로 조인다
        result = tilecache.prune(max_bytes=len(PNG) * 2, max_age_days=0)
        self.assertEqual(result["count"], 2)
        self.assertFalse(tilecache._path(keys[0]).exists())
        self.assertTrue(tilecache._path(keys[-1]).exists())

    def test_한계_안이면_버리지_않는다(self):
        tilecache.put("3" * 64, PNG)
        result = tilecache.prune()
        self.assertEqual((result["removed_age"], result["removed_size"]), (0, 0))
        self.assertEqual(result["count"], 1)


class DefaultAge(SimpleTestCase):
    def test_다시_묻는_나이는_3년이다(self):
        """한 달마다 다시 물으면 "계속 보탠다" 가 절반만 된다 (devlog 007)."""
        from django.conf import settings
        self.assertEqual(settings.TILE_CACHE_MAX_AGE_DAYS, 3 * 365)


class Stats(CacheCase):
    def test_수와_크기를_센다(self):
        tilecache.put("4" * 64, PNG)
        tilecache.put("5" * 64, PNG)
        got = tilecache.stats()
        self.assertEqual(got["count"], 2)
        self.assertEqual(got["bytes"], len(PNG) * 2)


class NoticeTile(SimpleTestCase):
    """안내 타일.

    **한글을 적지 않는다.** 컨테이너 이미지에 폰트가 없어 PIL 기본 글꼴로
    한글을 그리면 네모가 찍힌다 — 첫 배포 화면이 그랬다. 까닭은 레이어
    패널의 안내 띠가 한국어로 말한다.
    """

    def test_png_이_나온다(self):
        from viewer import tiles
        data = tiles.notice_tile(256, 256, tiles.NO_KEY)
        self.assertTrue(data.startswith(b"\x89PNG"))

    def test_적는_말에_한글이_없다(self):
        import re

        from viewer import tiles
        for text in (tiles.NO_KEY, tiles.NO_MAP):
            self.assertIsNone(re.search(r"[가-힣]", text), text)

    def test_아주_작은_타일도_견딘다(self):
        from viewer import tiles
        self.assertTrue(tiles.notice_tile(1, 1, tiles.NO_KEY).startswith(b"\x89PNG"))

    def test_터무니없이_큰_것은_잘린다(self):
        from PIL import Image
        import io

        from viewer import tiles
        img = Image.open(io.BytesIO(tiles.notice_tile(99999, 99999, tiles.NO_KEY)))
        self.assertEqual(img.size, (4096, 4096))
