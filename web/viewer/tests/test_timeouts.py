"""시간 한계의 사슬 (wetherilli 300) — nginx 90 초 > 문 한계 + 메타타일 잠금 기다림, 넘으면 504 대신 "느리다" 안내 타일."""
import fcntl
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import metatile, sgm, tiles, views

VIEWER = Path(views.__file__).parent
REPO = VIEWER.parent.parent
#: 화면이 부르지 않는 받기 — 호스트 cron·사람이 부르는 명령만 쓰는 문, 또는 그 함수
OFF_PATH = {"gfs.py", "era5.py", "gmgsi.py", "ecco.py", "neotoma.py", "gvp.py", "usgs.py", "pbdb.py", "kpds.py"}
OFF_PATH_LINES = ("def fetch_capabilities", "def _wfs", "def _data_get")     # kigam 의 씨앗·5만 WFS·자료 API


class Chain(SimpleTestCase):
    def test_바깥이_안보다_길다(self):
        conf = (REPO / "deploy" / "nginx" / "GSM-subpath.conf").read_text()
        nginx = int(re.search(r"proxy_read_timeout\s+(\d+)s", conf).group(1))
        self.assertGreater(nginx, settings.UPSTREAM_TIMEOUT_MAX + settings.METATILE_LOCK_WAIT)

    def test_화면의_문은_한계를_넘겨_기다리지_않는다(self):
        over = []
        for path in sorted(VIEWER.glob("*.py")):
            if path.name in OFF_PATH:
                continue
            text = path.read_text()
            consts = {m.group(1): int(m.group(2)) for m in re.finditer(r"^([A-Z_]*TIMEOUT) = (\d+)$", text, re.M)}
            for name, value in consts.items():
                if value > settings.UPSTREAM_TIMEOUT_MAX:
                    over.append(f"{path.name}: {name} = {value}")
            func = ""
            for line in text.splitlines():
                if line.startswith("def "):
                    func = line
                if func.startswith(OFF_PATH_LINES):
                    continue
                for m in re.finditer(r"timeout=\(?(?:max\(settings\.UPSTREAM_TIMEOUT,\s*)?(\d+)", line):
                    if int(m.group(1)) > settings.UPSTREAM_TIMEOUT_MAX:
                        over.append(f"{path.name}: {line.strip()[:90]}")
        self.assertEqual(over, [], "문 한계(UPSTREAM_TIMEOUT_MAX)보다 길게 기다린다")


class Slow(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-timeouts-"), METATILE_LOCK_WAIT=0.3)
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        span = 2 * metatile.R / 2 ** 8
        w, n = -metatile.R + 56 * span, metatile.R - 112 * span
        self.q = {"SERVICE": "WMS", "REQUEST": "GetMap", "LAYERS": "sgm:datos:7", "CRS": "EPSG:3857", "FORMAT": "image/png",
                  "WIDTH": "512", "HEIGHT": "512", "BBOX": f"{w!r},{n - span!r},{w + span!r},{n!r}"}

    def test_상류가_늦으면_느리다(self):
        with mock.patch.object(sgm.requests, "get", side_effect=sgm.requests.ReadTimeout("늦다")) as get, \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            got = self.client.get("/GSM/wms/", self.q)
        self.assertEqual(get.call_count, 1)                                          # 칸 하나로 되받지 않는다
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, tiles.notice_tile(512, 512, tiles.SLOW))

    def test_잠금을_오래_기다리면_느리다(self):
        lock = metatile._lock_path("sgm:datos:7", 512, 8, 56, 112)
        with open(lock, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)                      # 다른 워커가 같은 큰 장을 받고 있다
            with mock.patch.object(sgm.requests, "get", side_effect=AssertionError("상류를 타면 안 된다")), \
                 mock.patch.object(sgm.usage, "paused", return_value=0):
                got = self.client.get("/GSM/wms/", self.q)
        self.assertEqual(got.content, tiles.notice_tile(512, 512, tiles.SLOW))

    def test_다른_실패는_그대로(self):
        bad = mock.Mock(status_code=500, headers={"content-type": "text/html"}, content=b"no", url="u")
        with mock.patch.object(sgm.requests, "get", return_value=bad), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            got = self.client.get("/GSM/wms/", self.q)
        self.assertEqual(got.content, tiles.notice_tile(512, 512, tiles.NO_MAP))
