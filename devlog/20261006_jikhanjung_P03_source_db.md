# 데이터소스 명세와 받은 차례의 기록을 Django DB 로 — 관리 화면에서 고치고 이력을 남긴다 (계획)

2026-10-06 · `main` · jikhanjung (2026-10-07 — 사람이 정할 것 셋을 정하고, 기록 표도 함께 옮기기로)

> **지금** — 1 단계는 0.73.0·0.73.1 로 나갔다(#381·#383·#385·#388, jikhanjung 016–018). 옮기기는 계획의 "표가 비었을 때만" 이 아니라 표지로 한 번(명세)·
> 늘(기록)으로 바뀌었고(#381 검토), 호스트는 `GSM.db` 를 읽지도 않는다(§3 A). 2 단계는 탭에서 고치기·탭 안의 로그인(jikhanjung 020)과 파일 길 지우기 — 기록 줄이기는 하지 않기로 했다(§4)

jikhanjung P02 는 데이터소스의 명세를 **`<DB 옆>/sources.json`** 에 두었다 — 사람이 정하는 것(조건·주기·돌리는 곳·명령·산출물)을
코드 PR·시험 없이 고치게 하려는 것이었다. 지금 고치는 길은 **서버에 들어가 그 파일을 손으로 고치는 것뿐**이고, 잘못 고치면 그 줄이
"건너뛴 줄" 로 뜰 뿐이다. 사람이 **"그 명세를 DB 에서 관리하는 게 제일 바람직해 보인다"** 고 했다(2026-10-06). 같은 목적(PR 없이 고친다)을
DB 가 더 잘 이룬다 — 이 문서는 그 길을 정한다. 다음 날 **받은 차례의 기록(`fetch_log`)도 같은 작업에서 `GSM.db` 로 옮기기로** 했다(§3).

## 1. 지금 (2026-10-06, 0.71.2 + #379)

| 무엇 | 어디에 | 꼴 |
|---|---|---|
| 명세 49 곳 | `/srv/GSM/db/sources.json` | JSON. 칸은 id·name·org·license·flags·schedule·runs_on·commands·outputs·kind·raw·docs·note |
| 씨앗 | 저장소 `data/sources.seed.json` | 컨테이너가 뜰 때 `sources_seed` 가 운영에 없는 id 만 덧붙인다 |
| 명세의 이력 | `/srv/GSM/db/sources_history/` | 바뀔 때마다 사본 한 장 |
| 받은 차례의 기록 | `/srv/GSM/db/store.sqlite` 의 `fetch_log` | sqlite, 받을 때마다 쌓인다(지금 39 줄) |
| 받은 판의 정보 | 원본 폴더 안 `manifest.json`(`kigam50k/raw/20260930/`) | 파일마다 크기·sha256, 받은 때, 확인한 때 |
| Django `GSM.db` | `/srv/GSM/db/GSM.db` | 데이터소스 표가 없다 |

명세를 읽는 자리는 `sources.load()` 하나다 — `apps.py`(명령 → 데이터소스)·`fetchlog.sync`·`overview`(화면·healthz)·`sources_log`·
`sources_backfill`·`sources_seed`·`prune_raw`. 기록을 읽고 쓰는 자리는 `fetchlog.py` 하나다.

## 2. 왜 DB 인가

- **화면에서 고친다** — 서버에 들어가지 않는다. 고칠 때 칸을 검사해 **잘못된 값은 저장되지 않는다**(지금은 저장된 뒤에 "건너뛴 줄" 로 뜬다)
- **이력이 표 하나** — 누가·언제·무엇을(앞뒤 값). 지금의 `sources_history/` 사본 파일보다 찾고 견주기 쉽다
- **같은 틀이 이미 있다** — 레이어 카탈로그가 그렇게 돈다: 씨앗은 `data/*_layers.json`, `seed_catalog` 가 `Layer` 에 넣고, 사람은
  제목만 손질한다. 데이터소스도 `data/sources.seed.json` → `DataSource`. Django 의 폼·마이그레이션을 그대로 쓴다
- **이미 백업된다** — `GSM.db` 는 주간 백업에 든다. 명세 49 줄, 기록은 한 해 3 만 5 천 줄 남짓(몇 MB)이라 커질 걱정이 없다

## 3. 정한 것 (사람, 2026-10-06–07)

| 물음 | 정한 것 | 까닭 |
|---|---|---|
| **A. 호스트가 명세를 어떻게 읽나** — 매시 cron(`run.sh`)이 명령 이름으로 데이터소스를 찾는다 | ~~호스트가 `GSM.db` 를 읽는다~~ → **호스트는 `GSM.db` 를 열지 않는다**(사람, 2026-10-07) — 명령 이름을 적어 두면 컨테이너가 옮겨 적을 때 데이터소스로 바꾼다. DB 가 필요한 일은 컨테이너를 거친다 | 읽기만이어도 호스트·컨테이너가 한 파일의 잠금·스키마에 묶인다. 이미 있던 쓰기(`usage.record` → `UpstreamDay`)도 같이 뗐다 — 호스트는 `upstream_host.jsonl` 에 남기고 컨테이너가 더한다. 호스트의 설정은 DB 엔진이 dummy 다 |
| **B. 누가 고칠 수 있나** — 관리 화면은 계정을 묻지 않는다 | **Django 계정(staff) 로그인** | `/GSM/admin/` 이 이미 붙어 있고 이력에 "누가" 가 남는다. **운영 `auth_user` 는 지금 0 명** — 사람마다 계정을 만드는 일이 먼저다 |
| **C. 어디서 고치나** | **1 단계 뒤 바로 Django admin, 2 단계에서 관리 화면 탭** | admin 은 거의 공짜로 선다. 탭의 고치기는 쓰기 편하게 하는 것 |
| D. 씨앗을 운영에 어떻게 | 지금처럼 **없는 id 만 덧붙인다** | 사람이 고친 줄을 덮지 않는다. "씨앗과 다른 줄" 표시(#379)도 그대로 |
| **E. 받은 판의 정보(매니페스트)** | **원본 폴더 옆에 그대로 둔다** — DB 로 옮기지 않는다 | 원본이 스스로를 설명한다(폴더째 NAS 로 옮기거나 백업에서 되살려도 DB 없이 무엇을 언제 받았고 온전한지 안다). 코드가 그것을 읽는다(`kigam50k.latest`, `prune_raw` 의 "매니페스트가 든 날짜 폴더만 판으로" — #379 검토 1). 요약(원본 자리·전체 sha·바뀐 수)은 이미 기록 표에 든다 — 둘 다 DB 면 같은 것을 두 곳에서 맞춰야 한다 |
| **F. 기록 표(`fetch_log`)** | **명세와 함께 `GSM.db` 로** — 같은 작업, 마이그레이션 한 번 | 따로 둔 까닭(② 적재의 수백 MB 행 자료)은 기록에 맞지 않는다. 옮기면 명세와 기록을 Django 질의로 잇고(문자열 id 맞추기가 사라진다), 표 구조를 마이그레이션이 맡고(지금은 `fetchlog.py` 의 `CREATE TABLE IF NOT EXISTS` — 칸을 더할 길이 없다), 백업·되살리기가 한 파일이라 명세와 기록이 어긋나지 않는다 |

나뉨은 셋이다.

| 무엇 | 어디에 |
|---|---|
| **명세** — 무엇을 받나(조건·주기·명령·원본 자리) | `GSM.db` 의 `DataSource` |
| **받은 차례의 기록** — 언제 돌았고 성공했나, 몇 개 받았나, 바뀌었나 | `GSM.db` 의 `FetchRun` |
| **받은 판의 정보** — 이번에 받은 원본의 파일·sha256·받은 때 | 원본 폴더의 `manifest.json` |

기록 한 줄의 `raw_path` 가 그 판의 폴더(곧 매니페스트)를 가리킨다 — 화면에서 기록을 따라가면 매니페스트에 닿는다.
`store.sqlite` 는 남긴다 — 원래 목적인 ② 적재(화석·지진 행 자료)를 시작하기 전까지는 비어 있어도 된다.

**매니페스트를 뒤에 DB 로 옮기기로 바꾼다면** `rawstore.versions` 의 안전장치("매니페스트가 든 날짜 폴더만 판으로")를 "DB 에 기록이 있는
폴더만" 으로 함께 바꿔야 한다 — 그러지 않으면 `prune_raw` 가 다시 아무 날짜 폴더나 지울 수 있다.

## 4. 꼴

```
DataSource                     ← 명세 한 줄 (pk = id 글, `^[a-z][a-z0-9_]*$`)
  name_ko · name_en · org · kind · runs_on · schedule · license · raw · note
  flags · commands · outputs · docs           JSONField (글의 목록)
  updated_at · updated_by(→ User, null)
DataSourceChange               ← 명세의 이력. 고칠 때마다 한 줄
  source(id 글 — 지운 줄도 남게 FK 가 아니다) · at · by(→ User, null) · origin(admin·tab·seed·import)
  before · after               JSONField (줄 전체)
FetchRun                       ← 받은 차례 한 줄 (지금의 fetch_log 그대로)
  source(id 글 — `_spec` 따위 명세 밖의 것도 받게 FK 가 아니다) · command · started_at · seconds · result · note
  upstream_version · expected · rows · changed · raw_path · raw_sha256 · built_at · built_by · estimated · origin
  unique (source, started_at, origin) · index (source, started_at)
```

- 명세의 검사는 지금의 `sources.problems_of` 를 모델의 `clean()` 으로 옮긴다 — 화면·admin·명령이 같은 검사를 지난다
- `sources.load()` 는 **이름과 돌려주는 꼴(`Spec`)을 지킨다** — 부르는 자리 일곱을 고치지 않으려고. 속만 DB 를 읽는다
- `fetchlog` 의 바깥(`record`·`note`·`write`·`latest`·`history_many`·`sync`·`shown`)도 이름과 꼴을 지킨다 — 속만 ORM 으로.
  `latest()` 의 "때로 정렬"(#375, 시간대가 섞여도)은 `started_at` 을 **UTC 로 맞춰 적는** 것으로 바꾼다 — 옮길 때 한 번 맞춘다
- 호스트가 남긴 것을 옮겨 적는 읽은 자리(`fetch_log_meta` 의 `host_offset`)는 작은 표 하나 또는 `FetchRun` 옆의 키·값 한 줄로
- `sources.coverage()`(명령·구운 파일이 빠짐없이 든다) 시험은 **씨앗**을 본다 — 그대로
- 명세가 DB 에 없으면(새 설치) 씨앗을 넣는다 — `seed_catalog` 처럼 컨테이너가 뜰 때

### 쓰는 자리

- **호스트는 `FetchRun` 에 쓰지 않는다** — 지금처럼 `hourly_status.json`·`fetch_log_host.jsonl` 에 남기고 컨테이너가 옮겨 적는다(`hourly.sh`
  끝의 `sources_log --sync-only`). 쓰는 곳이 `store.sqlite` 에서 `GSM.db` 로 바뀔 뿐이다. 명세는 읽기만 한다
- **쓰기가 겹친다** — `GSM.db` 에는 화면이 점묶음을 저장하는 쓰기도 있다. 기록 한 줄은 아주 짧은 쓰기라 대개 괜찮지만, 명령 끝의 기록이
  부딪히면 기다렸다가 쓴다(sqlite `timeout`). 그래도 실패하면 지금처럼 **기록만 버리고 명령은 그대로** 끝난다

### 기록 줄이기 — 하지 않는다 (사람, 2026-10-07)

한 번은 "1 년 안은 다, 옛것은 하루 한 줄(실패·바뀐 것은 늘)" 로 정해 `prune_fetch_log` 를 만들었다가 접었다. 기록은 `GSM.db` 의
`viewer_fetchrun` 에 한 해 3 만 5 천 줄 남짓 — **한 해 10 MB 안팎**이고 주간 백업 ①(압축)도 크게 늘지 않는다. 옛 기록은 "언제부터
깨졌나" 를 볼 때 쓸모가 있다. 정말 커지면 그때 다시 꺼낸다. 지울 것은 오히려 이미 DB 로 들인 호스트의 jsonl 쪽이다(TODOs)

## 5. 차례

한 단계마다 브랜치·PR·devlog 하나. 병합·판은 판 세션이 한다.

| 단계 | 브랜치 | 담는 것 |
|---|---|---|
| 1 | `feature/source-db` | 모델 셋(`DataSource`·`DataSourceChange`·`FetchRun`)·마이그레이션 한 번. `sources.load()`·`fetchlog` 의 속을 DB 로. `sources_seed` 가 DB 에(없는 id 만). **운영의 것을 한 번 옮기는 명령**(`sources_import` — `sources.json` 과 `store.sqlite` 의 `fetch_log`, DB 가 비었을 때만, 이력에 `import` 한 줄). admin 등록(명세는 고치기, 기록은 읽기만). healthz·화면은 그대로 |
| 2 | `feature/source-edit` | 관리 화면 "데이터소스" 탭에 고치기(로그인한 staff 만, 줄을 펼친 자리의 폼), 명세의 이력을 펼친 줄에, `sources.json`·`sources_history/`·`store.sqlite` 의 기록을 읽는 길을 지운다 |

1 단계가 끝나면 **서버에서 파일을 고칠 일이 없다**(admin 으로). 2 단계는 쓰기 편하게 하는 것이다.

## 6. 옮기는 날

1. 1 단계가 나간 판에서 컨테이너가 뜨면 마이그레이션 뒤 `sources_import` 가 운영의 `sources.json`(사람이 고친 것까지)과 `store.sqlite` 의
   `fetch_log` 를 DB 로 — **표가 비었을 때만**. 이미 차 있으면 아무것도 하지 않는다(두 번 옮겨 덮지 않게)
2. **판 세션이 할 일** — 사람마다 staff 계정을 만든다(`manage.py createsuperuser` 또는 admin 에서). 계정이 없으면 admin 으로도 못 고친다
3. `sources.json`·`sources_history/`·`store.sqlite` 의 `fetch_log` 는 지우지 않고 남긴다 — 한 판 동안 둘이 같은지 본다. 2 단계에서 읽는 길을
   지우고, 파일은 사람이 치운다. 주간 백업의 `sources.json`·`sources_history/` 줄도 2 단계에서 뺀다(GSM.db 에 든다). `store.sqlite` 의 백업 줄은
   ② 적재를 위해 남긴다

## 7. 넣지 않은 것

- **"지금 받기" 단추** — P02 와 같다. 고치기가 서고 계정이 생기면 그때 다시 본다
- **매니페스트를 DB 로** — §3 E
- **② 적재**(화석·지진 행 자료를 `store.sqlite` 에) — 따로 계획
- 레이어 카탈로그를 이 틀로 — 이미 DB 다
- 중계 상류 여든 남짓의 조건(`상류_조건표.md`)을 이 표로 — P02 와 같다

## 8. 위험

- **WAL** — 컨테이너에서는 WAL 이 낫지만 지금은 바꾸지 않는다(사람, 2026-10-07) — 사용자 트랜잭션이 있는 것이 아니다. 호스트가 `GSM.db` 를 열지 않게 되어 바꿀 때는 컨테이너만 보면 된다
- **계정이 없는 채로 나가면** 아무도 못 고친다 — §6 의 2 를 1 단계 PR 의 "배포 뒤" 에 적는다
- 옮기는 날 운영의 `sources.json` 이 깨져 있으면 — `sources_import` 는 떠 둔 판(`sources_history/` 의 끝)을 쓴다. 지금 `load()` 와 같다
- 판을 되돌리면(0.71 로) 명세·기록이 다시 파일에서 읽힌다 — 1 단계 동안 파일을 지우지 않는 까닭이다. 그 사이 DB 에만 쌓인 기록은 그 판에서 안 보인다
- 시간대 — 옮길 때 `started_at` 을 UTC 로 맞추면 `unique (source, started_at, origin)` 의 비교가 바뀐다. 옮기는 명령이 맞춘 뒤 겹치는 줄은 하나로

## 9. 확인하는 법

- 1 단계 뒤 — 운영 `sources.json` 의 49 줄과 `fetch_log` 의 줄이 DB 에 그대로(`sources_log` 의 목록이 같다), 화면·healthz 의 수가 앞과 같다,
  admin 에서 한 줄을 고치면 화면에 곧 뜨고 `DataSourceChange` 에 한 줄, 매시 차례가 `FetchRun` 에 쌓이고 `store.sqlite` 에는 더 쌓이지 않는다
- 2 단계 뒤 — 로그인하지 않으면 고치기가 안 보인다, 틀린 값(없는 주기)은 저장되지 않고 까닭이 뜬다, 고친 줄의 펼친 자리에 이력
