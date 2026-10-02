# 매주 월요일 새벽: 운영 자료 백업과 KPDC 목록 갱신

2026-09-30 · `feature/weekly-backup` · koprifossillab

## 1. 왜

[P01](20260930_koprifossillab_P01_backup_plan.md) 의 1–3 단계다. GSM 에는 백업이 하나도 없었다. 사람이 "커밋하고
weekly_backup.sh 도 만들어 달라" 고 했다.

## 2. 무엇을 했나 — `deploy/host/weekly_backup.sh`

P01 의 넷(① 주간 tar · ② 구운 것 · ③ 캐시 거울 · ④ 원본 거울)과 받기 셋(⑤ `fetch_kopri` 매주 · ⑥ `fetch_kigam50k`·
⑦ `fetch_pbdb` 첫 월요일)을 한 스크립트에 담았다. cron 조각은 `deploy/host/crontab.GSM`(월 01:40)이다. 틀은 WegenersDream 의
`weekly_refresh.sh`(WegenersDream koprifossillab 032) 그대로다 — `umask 027`, `flock`, NAS 는 `mountpoint` 로 보고 `timeout`
으로 감싸 `.part` → sha256 대조 → 이름 바꾸기, 결과는 `logs/last_backup.json`.

- **② 는 목록으로 가른다.** `db/` 의 파일을 비밀과 ① 에 드는 것을 빼고 sha256 을 낸다(`manifest-built.txt`). 지난번
  목록(`backups/.manifest-built.last`)과 같으면 뜨지 않는다. 다르면 압축하지 않은 tar 를 뜬다. 목록은 ① 에도 넣어,
  어느 주의 ① 이 어느 ② 와 짝인지 되짚을 수 있다
- **② 의 NAS 사본은 "가장 새 것이 NAS 에 있나" 로 본다** — 뜬 주에 NAS 가 빠졌어도 다음 주에 따라잡는다
- **② 를 나이로 줄인다** — 30 일까지 전부, 그 뒤는 달마다 가장 새 것 하나. 로컬과 NAS 둘 다
- **GSM.db 는 sqlite 의 backup API 로 뜨고** `integrity_check` 를 본다. 컨테이너가 쓰는 중이어도 맞는 사본이 된다.
  호스트에 `sqlite3` 명령이 없어 `python3` 로 부른다
- **받기는 컨테이너 안에서**(`docker compose exec -T -w /app/web web python manage.py …`). 호스트에 GSM venv 가 없다.
  또 KPDC 의 `extra_hosts` 가 컨테이너에만 있다(wetherilli 095). 그래서 WegenersDream 처럼 "저장소가 main 이고 깨끗할
  때만" 을 따지지 않는다 — 받는 코드는 운영 이미지의 것이다
- **⑥ 은 명령이 이미지에 있을 때만**(`manage.py help fetch_kigam50k`), **⑦ 은 `db/earth/` 가 섰을 때만** 돈다. 그 판이
  배포되면 스크립트를 고치지 않아도 붙는다
- 비밀(`kigam_key`·`vworld_key`·`secret_key`·`geus_whoami`·`allowed_hosts`)은 목록에서부터 뺀다. 스위치 파일
  (`dev_direct_wms`·`public`)은 ① 에 넣는다 — ② 에 두면 스위치를 켜고 끌 때마다 1.4 GB 를 새로 뜬다

## 3. 해 본 것 (2026-09-30)

- `--backup-only`: ① 4.7 MB(파일 29), ② 1.4 GB(파일 46 561 — IBCSO 43 189·한반도 3 361), NAS 둘 다 sha256 일치,
  **21 초.** tar 안에 비밀 파일이 없는 것, ① 의 `GSM.db` 를 풀어 레이어 203 이 읽히는 것을 보았다
- 한 번 더 돌리니 "구운 것: 지난번과 같다 — 뜨지 않는다"
- 기본 모드(③④⑤): 아래 §5

## 4. 버린 것

- **`fetch_kopri --refresh` 를 cron 에** — 상세 3 500 쪽을 다시 받는 데 두 시간이다. 매주는 새 것만 받는다
- **②를 gzip** — 대부분 webp·tif·gpkg 라 줄지 않고 시간만 든다
- **③④ 에 `--delete`** — 캐시는 "받은 것은 계속 보탠다"(007), 원본은 NAS 에서 실수로 지운 것을 되살리려고 둔다
- **받기 실패를 백업 실패로** — 백업은 이미 떴다. 결과는 `fail` 에 `step: fetch` 로 남아 사람이 보게 한다

## 5. 기본 모드를 처음 돌렸을 때

18:34:46 에 시작해 18:38:47 에 끝났다 — **4 분.** 결과는 `ok` 이고 칸이 다 `ok` 다.

- ③ 캐시 1.2 GB 를 NAS 로, ④ 원본 3.9 GB 를 `/data/GSM/sources` 로 옮겼다. 둘 다 첫 번이라 통째로 옮겼는데도
  3 분이 안 걸렸다. P01 이 "수십 분" 이라 적은 것보다 훨씬 빠르다. 다음부터는 늘어난 것만 옮긴다
- ⑤ `fetch_kopri` — 암석 시료 22 장(2 722 건)·KPDC 목록 여덟 장·운석 목록 두 장, 목록 3 489 건에 빠진 것 0, 새로
  받을 상세 0. 1 분 남짓. 로그의 "새 것 500" 은 그 장에서 읽은 행 수다 — 상세를 받을 것은 0 건이었다
- 스위치 파일을 ① 로 옮긴 뒤 `--backup-only` 를 다시 돌리니 ② 의 목록이 그대로였다. 지금 운영에는 스위치 파일이 없다

② 를 임시 폴더에 풀고 ① 의 `manifest-built.txt` 로 `sha256sum -c` — 46 561 파일이 다 맞았다.

**cron 에는 아직 붙이지 않았다** — 사람이 이 브랜치를 병합한 뒤 `crontab.GSM` 을 붙인다.
