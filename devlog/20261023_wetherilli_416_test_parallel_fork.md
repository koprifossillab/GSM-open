# 시험 — 파이썬 3.14 에서 병렬을 fork 로 고정한다

2026-10-23 · `fix/test-parallel-fork` · wetherilli

서버의 시스템 파이썬이 3.12 에서 3.14.4 로 올라갔다(2026-10-23, 3.12 는 지워졌다). 3.12 로 만든 `~/venv/GSM` 은 실행 파일이
3.14 를 가리키게 되어 패키지를 못 찾았다 — 다시 만들어 돈다(`python3 -m venv --clear`, requirements 다시). 그 뒤
`manage.py test viewer --parallel 8` 이 이렇게 깨졌다.

```
django.db.utils.NotSupportedError: Cloning with start method 'forkserver' is not supported.
```

3.14 부터 리눅스에서 `multiprocessing` 의 기본 시작 방식이 fork 에서 forkserver 로 바뀌었다. Django 5.2 의 시험 DB 복제는
fork·spawn 만 안다. 병렬 없이 돌리면 통과한다. CI 는 3.12 라 안 깨진다 — 로컬에서만 막혔고, CLAUDE.md 가 "넘기기 전에 로컬에서
나란히 돌려 본다" 고 하니 기능 세션마다 막힌다.

## 고른 것

`GSMTestRunner.__init__` 에서 병렬이고 리눅스이고 시작 방식이 forkserver 일 때만 `set_start_method("fork", force=True)`.

- **러너에 둔다** — 이 러너는 이미 "병렬 일꾼이 fork 로 갈라져 바꾼 설정을 물려받는다" 에 기대고 있다(임시 자리 돌리기).
  fork 를 전제한 곳에서 fork 를 못 박는 것이 맞다
- **spawn 으로 바꾸지 않았다** — 일꾼마다 Django 를 새로 띄우고 시험 DB 를 파일로 복제해 느리고, 러너가 바꾼 설정을 환경변수로만
  넘기게 된다. 3.12 의 CI 와도 갈린다
- **`manage.py` 에 두지 않았다** — 시험이 아닌 명령까지 시작 방식을 바꿀 까닭이 없다
- macOS·윈도는 fork 가 기본이 아니거나 없으니 건드리지 않는다. 3.12 의 CI 는 이미 fork 라 조건에 걸리지 않는다

3.14 의 fork 는 스레드가 있는 프로세스에서 DeprecationWarning 을 낼 수 있다. Django 가 forkserver 를 받아 주면 이 줄을 지운다.
