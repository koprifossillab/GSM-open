# `/healthz/` — 판·DB·백업 상태를 한 장으로

2026-09-30 · `feature/healthz` · koprifossillab

## 1. 왜

[koprifossillab 001](20260930_koprifossillab_001_weekly_backup.md) 을 쓰면서 WegenersDream 의 문장을 옮겨 "`/healthz` 가 백업
상태를 모른다" 고 적었다. 사람이 "GSM 에 `/healthz/` 없다고 했던가?" 라고 물었다. 찔러 보니 404 였다 — **아예 없었다.**
백업이 멈춰도 알릴 자리가 없었던 것이다. 사람이 "만들자" 를 골랐다.

## 2. 무엇을 했나

- **`/GSM/healthz/`** — ForGIA·DiaRUGA 의 `/healthz` 와 같은 모양이다(`status`·`version`·`db`·`notes`). 거기에 `backup`
  (백업 결과 파일 그대로, `age_days` 를 더해)을 얹었다

  | 상태 | 코드 | 언제 |
  |---|---|---|
  | `ok` | 200 | 다 괜찮다 |
  | `degraded` | 200 | 백업 기록이 없다 · 멈췄다(`result != ok`) · **여드레**를 넘었다 · NAS·캐시 거울·원본 거울 가운데 `fail` |
  | `unhealthy` | 503 | DB 를 못 연다 · **레이어가 0** |

- **레이어 0 을 unhealthy 로 둔 것** — DB 마운트가 어긋나면 빈 DB 가 새로 생긴다. 그래도 "열리는가" 는 통과한다(ForGIA 가
  슬라이드 0 을 보는 것과 같다). GSM 에서 비어 있으면 안 되는 표는 카탈로그다. 점묶음은 0 이 정상이다
- **여드레** — 매주 한 번에 하루를 얹었다. cron 이 몇 분 늦거나 사람이 손으로 하루 늦게 돌려도 degraded 가 뜨지 않게
- **백업 결과를 DB 옆에도 적는다**(`backup_status.json`). 로그 자리(`/data/GSM/logs`)는 컨테이너에 붙어 있지 않다. 붙이려면
  `/srv/GSM/docker-compose.yml` 을 고쳐야 하는데, 그 파일은 사람이 sudo 로 고친다. `db/` 는 이미 붙어 있고 paleoadmin 이
  쓸 수 있다. 이 파일은 백업의 목록에서 뺀다 — 넣으면 매주 달라져 ② 가 늘 새로 뜬다
- `status()` 가 설명의 `"`·`\` 를 바꾼다 — tar 의 오류 문장이 그대로 들어가 JSON 이 깨질 수 있었다
- **`smoke.sh` 는 unhealthy 면 멈추고 degraded 는 적기만 한다** — ForGIA 는 degraded 도 배포를 세운다. GSM 에서 degraded 는
  백업 이야기뿐이라, 백업이 멈췄다고 화면 고침을 못 올리게 하면 둘 다 멈춘다

## 3. 버린 것

- **compose 에 `/data/GSM/logs` 를 붙이기** — 위의 sudo. DB 옆 한 벌로 충분하다
- **백업 tar 의 mtime 을 보기**(ForGIA 처럼) — 컨테이너에서 `/data/GSM/backups` 가 안 보인다. 또 파일의 나이만으로는 NAS 가
  빠졌는지 모른다
- **degraded 를 503 으로** — ForGIA 가 적은 까닭 그대로다. 뷰어는 멀쩡히 돈다
- **`notes` 를 영어로 옮기기** — 화면이 아니라 운영자가 읽는 것이다. `msg()` 로 감싸지 않는다

## 4. 해 본 것

- `test_healthz` 여덟: 레이어 0 → 503, 다 괜찮으면 ok, 기록 없음·멈춤·아흐레·NAS 실패·깨진 JSON → degraded, `no-store`
- 뷰어 시험 855 개 전부 통과(v0.25.6 이미지에 이 브랜치를 얹어)
- 이 브랜치의 `weekly_backup.sh --backup-only` 로 운영의 `db/backup_status.json` 을 처음 만들었다 — 판이 올라가면 곧장 `ok`
