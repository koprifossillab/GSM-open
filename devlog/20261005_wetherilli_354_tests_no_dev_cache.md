# 시험이 개발 캐시를 더럽히지 않게

2026-10-05 · `test/no-dev-cache` · wetherilli

349 에서 coverage 를 두 번 재니 `views.py` 의 20 줄이 두 번째에 빠졌다 — 해저·지열류 타일 시험이 개발 캐시(`web/.tilecache`)에
담아 두어 둘째 판에는 캐시에서 꺼냈다. 시험이 개발 장비의 상태를 읽고 쓰면 장비마다·판마다 다른 길을 탄다. 판 세션이 이것을 막으라 했다.

## 한 것

`settings.TEST_RUNNER` 를 `gsmweb.testrunner.GSMTestRunner` 로.

- 시험을 돌리는 동안 `TILE_CACHE_DIR` 과 `<DB 옆>` 의 자료 자리 열아홉(`MOON_DIR`…`VERIFY_DIR`)을 **빈 임시 디렉터리**로 돌린다.
  개발 장비에 달 원도·지열류 sqlite 가 있든 없든 CI 와 같은 판에서 돈다
- 타일 캐시는 **시험마다** 새 빈 디렉터리다 — `SimpleTestCase.__call__` 을 감싸 `override_settings` 한 겹을 씌운다.
  시험이 스스로 `override_settings(TILE_CACHE_DIR=…)` 를 쓰면 그쪽이 안쪽이라 이긴다. 앞 시험이 담은 것이 뒤 시험의 적중이 되지 않는다
- 다 돈 뒤 저장소를 다시 훑어 **새로 생긴 파일**이 있으면 깨진다(실패 하나를 더한다). `.git`·`.claude`(다른 세션의 worktree)·
  `__pycache__` 는 건너뛴다 — 1 600 파일이라 훑는 데 몇 ms
- `test_testrunner` — settings 에 `*_DIR` 이 새로 생기면 러너의 표(`REDIRECT`)에도 있어야 깨지지 않는다. 다음에 자료 자리를 더하는
  사람이 러너를 잊지 않게

## 숫자

| | 시험 | 저장소에 남긴 파일 |
|---|---|---|
| 전 (`--testrunner django.test.runner.DiscoverRunner`) | 1 939 | `web/.tilecache` 에 타일 9 장 |
| 후 | 1 939 통과(건너뜀 12), 브라우저 시험 44 통과 | 0 |

남긴 것은 해저(`test_seafloor`)·지열류·암상(`test_heatflow_glim`)·한국(`test_korea_more`) 쪽의 "캐시에 없으면 그려 담는다" 갈래다.
시험마다 고치지 않고 러너 한 곳에서 막았다 — 앞으로 생길 시험도 같이 막힌다.

## 버린 것

- **바뀐 파일도 잡는 것** — 처음엔 크기·고친 때가 바뀐 것도 셌는데, 돌리는 사이에 사람이 파일을 고치면(나도 그랬다) 그것까지
  깨졌다. 시험이 추적 파일을 고치면 `git status` 가 보이니 새로 생긴 것만 센다
- **기본 TestCase 를 하나 두고 모든 시험이 물려받게** — 시험 파일 수백 개의 import 를 바꿔야 하고, 새 시험이 `django.test` 를 곧장
  쓰면 빠진다. 러너는 고칠 곳이 하나다
- **시험마다 자료 자리까지 새로** — 자료 자리는 시험이 제 임시 자리를 만들어 `override_settings` 로 넘기는 것이 이미 관례라,
  돌리는 동안 한 번만 저장소 밖으로 돌렸다
- spawn 으로 뜨는 일꾼 — 지금 리눅스는 fork 라 러너가 바꾼 것을 물려받는다. 파이썬 3.14 에서 기본이 forkserver 로 바뀌면
  `__call__` 감싸기가 일꾼에 닿지 않는다. 자리만은 환경변수에도 적어 두었지만 시험마다의 캐시는 그때 다시 본다
