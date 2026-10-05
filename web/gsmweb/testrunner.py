"""시험 러너 — 시험이 개발 캐시·자료 자리를 더럽히지 않게 (wetherilli 354).

- 받은 타일 캐시(`TILE_CACHE_DIR`)와 `<DB 옆>` 의 자료 자리(`GSM_*_DIR`)를 **시험을 돌리는 동안 빈 임시 디렉터리로** 돌린다.
  개발 장비에 자료가 있든 없든 CI 와 같은 판에서 돈다 — 자료가 있어야 하는 시험은 제 임시 자리에 만들어 쓴다
- 타일 캐시는 **시험마다** 새 빈 디렉터리다 — 앞 시험이 담은 것이 뒤 시험의 캐시 적중이 되지 않게
- 다 돌고 나서 저장소 안에 새로 생긴 파일이 있으면 깨진다 — 시험이 제 임시 자리 밖에 쓰면 여기서 잡힌다

`settings.TEST_RUNNER` 가 이것을 가리킨다. 병렬(`--parallel`)은 fork 로 갈라지므로 여기서 바꾼 것을 일꾼이 물려받는다.
spawn 으로 뜨는 일꾼을 위해 환경변수에도 적는다.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.test.runner import DiscoverRunner

#: 시험 동안 빈 임시 자리로 돌리는 설정 → 환경변수. 새 `GSM_*_DIR` 을 settings 에 더하면 여기에도 더한다
#: (`test_testrunner` 가 settings 의 `*_DIR` 과 견주어 빠진 것을 잡는다)
REDIRECT = {name: f"GSM_{name}" for name in (
    "MOON_DIR", "CARIBBEAN_DIR", "MARS_DIR", "MERCURY_DIR", "EARTH_DIR", "WIND_DIR", "OCEAN_DIR", "GEOMAP_DIR", "NPOLAR_DIR",
    "USGS_DIR", "PENINSULA_DIR", "IBCSO_DIR", "ADMAP_DIR", "KOPRI_DIR", "TAIWAN_OPEN_DIR", "KIGAM_DATA_DIR", "SGB_DIR",
    "KIGAM50K_DIR", "VERIFY_DIR", "SARAD_DIR", "TILE_CACHE_DIR")}
#: 시험이 손대지 않는 설정 — 저장소 자리 자체, 비면 꺼지는 로그
KEEP = {"BASE_DIR", "REPO_DIR", "LOG_DIR"}
#: 저장소를 훑을 때 건너뛰는 것 — 바이트코드, git, 다른 세션의 worktree
SKIP = {".git", ".claude", "__pycache__", "node_modules"}


def snapshot(root: Path) -> dict:
    """저장소 안 파일 → (크기, 고친 때). 건너뛸 디렉터리는 들어가지 않는다."""
    seen = {}
    for here, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(here, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            seen[os.path.relpath(path, root)] = (st.st_size, st.st_mtime_ns)
    return seen


def changed(before: dict, after: dict) -> list:
    """새로 생긴 파일. 있던 파일이 바뀐 것은 세지 않는다 — 돌리는 동안 사람이 고친 것까지 깨지면 안 되고, 고친 추적 파일은 git status 가 보인다"""
    return sorted(p for p in after if p not in before)


class GSMTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._root = Path(tempfile.mkdtemp(prefix="gsm-test-"))
        values = {name: str(self._root / name.lower()) for name in REDIRECT}
        for name, env in REDIRECT.items():
            os.environ[env] = values[name]
        self._override = override_settings(**values)
        self._override.enable()
        self._call = SimpleTestCase.__call__
        root, call = self._root / "tiles", self._call
        root.mkdir()

        def fresh_cache(case, result=None):
            # 시험마다 빈 타일 캐시. 시험이 스스로 override_settings 로 바꾸면 그쪽이 안쪽이라 이긴다
            here = tempfile.mkdtemp(dir=root)
            try:
                with override_settings(TILE_CACHE_DIR=here):
                    return call(case, result)
            finally:
                shutil.rmtree(here, ignore_errors=True)
        SimpleTestCase.__call__ = fresh_cache

    def teardown_test_environment(self, **kwargs):
        SimpleTestCase.__call__ = self._call
        self._override.disable()
        shutil.rmtree(self._root, ignore_errors=True)
        super().teardown_test_environment(**kwargs)

    def run_tests(self, test_labels, **kwargs):
        repo = Path(settings.REPO_DIR)
        before = snapshot(repo)
        failures = super().run_tests(test_labels, **kwargs)
        left = changed(before, snapshot(repo))
        if left:
            print(f"\n시험이 저장소 안에 파일을 남겼다 ({len(left)}개) — 임시 디렉터리에 쓰게 고친다:", file=sys.stderr)
            for path in left[:20]:
                print(f"  {path}", file=sys.stderr)
            failures += 1
        return failures
