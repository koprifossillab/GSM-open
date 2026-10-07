# 매시 일의 `note()` 값도 기록에

2026-10-07 · `feature/hourly-notes` · jikhanjung

매시 일(GFS·GMGSI·아라온호·최근 지진)의 받은 수·판·바뀐 수가 기록 표에 안 남았다(jikhanjung 018 의 TODOs). 사람이 "DB 해당 테이블에 컬럼 하나
추가하면 되는 거 아냐?" 라고 물었다 — **칸은 이미 있다**(`FetchRun` 의 `rows`·`expected`·`changed`·`upstream_version`). 빠진 것은 길이었다.

## 1. 왜 빠졌나

매시 일은 호스트의 `hourly.sh` 가 부른다. `note()` 로 모은 값은 그 파이썬 프로세스만 안다. 그런데 매시 일은 `hourly_status.json` 이 기록을
맡기로 해(같은 차례가 두 줄 되지 않게, jikhanjung 012) 프로세스가 jsonl 에 쓰지 않았고, `hourly_status.json` 은 bash 가 써서 종료 코드·초·마지막
말뿐이다. 프로세스가 끝나면 값이 버려졌다. 게다가 매시 넷은 `note()` 를 부르지도 않았다.

## 2. 무엇을 정했나

1. **매시 일도 jsonl 에 한 줄**(`fetch_log_host/<날짜>.jsonl`, `"hourly": true` 표시) — `note()` 값까지. 옮길 때 origin `hourly`
2. **같은 차례는 jsonl 이 이긴다** — `hourly_status.json` 의 줄은, 같은 데이터소스의 매시 줄이 이번에 함께 옮기는 jsonl 에나 표에 그 끝난 때에서
   `HOURLY_LIMIT`(900 초) 안쪽에 있으면 버린다. 다음 옮기기에도 같은 차례를 또 적지 않는다(표를 본다)
3. **`hourly_status.json` 은 예비로 남긴다** — 시간을 넘겨 죽으면 파이썬은 jsonl 에 못 쓴다. 그때는 bash 가 남긴 실패가 기록이 된다. healthz 도 그것을 읽는다
4. **매시 넷이 `note()` 를 부른다** — GFS 판·센 장·받은 장·바뀐 장, GMGSI 장과 바뀌었나, 아라온호 자리의 때와 새 자리인가, 최근 지진 곳 수와 피드를 지은 때

## 3. 버린 것

- **`hourly.sh` 가 `hourly_status.json` 에 칸을 더하기** — bash 가 파이썬의 값을 받으려면 출력을 긁어야 한다. 파이썬이 jsonl 에 쓰면 그 길이 있다
- **매시 일의 기록을 jsonl 하나로만** — 시간을 넘겨 죽은 차례가 기록에서 사라진다

## 4. 확인

- 시험 — jsonl 의 값이 이기고 한 줄, 다음 옮기기에도 한 줄, jsonl 이 없으면(죽었을 때) `hourly_status` 의 실패, 실패 전의 성공도 jsonl 이 있으면 한 줄,
  호스트가 매시 일도 표시를 달고 jsonl 에. 전체 통과
- 호스트 방식으로 매시 한 차례(`GSM_HOURLY_JOB=1 fetch_recent_quakes`) — jsonl 줄에 `rows: 314`·`upstream_version`·`hourly: true`
