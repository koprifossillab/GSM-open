# 외부 자료원을 한 장부로 — 명세·기록 표·관리 화면 "자료원" 탭 (계획)

2026-10-06 · `main` · jikhanjung

> **지금** — 1–3 단계는 끝나 나갔다(#368·#369·#373, 검토 고침 #375·#377 — jikhanjung 011–014). 화면의 말은 사람이 "데이터소스" 로
> 정했다(이 문서의 "자료원" 은 그날의 기록이라 두었다). 4 단계는 `feature/raw-prune`. 명세를 Django DB 로 옮기는 것은 jikhanjung P03

[docs/외부_자료원.md](../docs/외부_자료원.md)(목록)와 [docs/자료_적재_구조.md](../docs/자료_적재_구조.md)(검토)를 바탕으로, **받아 두는
자료원을 관리하는 길**을 정한다. 검토가 "사람이 정할 것" 으로 남긴 것 가운데 넷을 사람이 정했다(2026-10-06).

| 물음 | 정한 것 |
|---|---|
| 무엇부터 | **장부·화면 먼저** — 명세와 기록 표, 그리고 관리 화면의 "자료원" 탭. 적재(②, `store.sqlite` 에 행을 담기)는 뒤의 계획으로 |
| 명세 JSON 의 자리 | **`<DB 옆>`** — 곧장 운영에 닿는다. 대신 이력을 따로 남긴다 |
| ① 원본을 얼마나 | **바뀐 판만, 최근 3 벌** — sha256 이 같으면 새 벌 없이 확인한 날만, 그 너머는 `prune_raw` 가 지운다 |
| "지금 받기" 단추 | **처음엔 두지 않는다** — 화면은 읽기만 |

## 1. 무엇을 다루나

**받아 두는 자료원**만이다 — `외부_자료원.md` 의 1(`fetch_*` 명령 열일곱)과 2(사람이 원본을 굽는 `build_*` 명령 스물여덟).
3(그때그때 중계하는 상류 여든 남짓)·4(브라우저가 곧장)·5(연결 레이어)는 갱신이 없어 들이지 않는다 — 중계 상류의 조건은 지금처럼
[docs/상류_조건표.md](../docs/상류_조건표.md) 가, 물은 수는 `UpstreamDay` 가 맡는다.

## 2. 세 조각

| 조각 | 자리 | 누가 쓰나 | 바뀌는 것 |
|---|---|---|---|
| **명세** — 자료원마다 사람이 정하는 것 | `<DB 옆>/sources.json` | 사람(처음엔 서버에서 손으로) | 조건·주기·돌리는 곳·명령·산출물 |
| **기록 표** — 받은 차례마다 한 줄 | `<DB 옆>/store.sqlite` 의 `fetch_log` | 명령이 끝날 때 스스로 | 받은 때·결과·행 수·걸린 초·원본 자리·구운 판 |
| **화면** — 둘을 엮어 한 줄씩 | `/GSM/manage/` 의 "자료원" 탭 | 읽기만 | — |

`store.sqlite` 는 검토의 ② 적재가 들어갈 그 파일이다. 이 계획에서는 **기록 표 하나만** 둔다 — 적재가 오면 같은 파일에 자료원마다
표가 는다. Django 의 `GSM.db` 에는 넣지 않는다(검토의 "버린 것" 그대로 — 백업 대상이 부푼다).

## 3. 명세 — `<DB 옆>/sources.json`

### 칸

```json
{
  "id": "pbdb",
  "name": {"ko": "화석 산지 PBDB", "en": "PBDB fossil collections"},
  "org": "Paleobiology Database",
  "kind": "fetch",                       // fetch · build · once
  "commands": ["fetch_pbdb"],
  "runs_on": "container",                // container · host · person
  "schedule": "monthly-first-monday",    // hourly · weekly · monthly-first-monday · manual · once
  "license": "CC BY 4.0",
  "flags": [],                           // nc · sold · lab_only · no_store
  "outputs": ["earth/pbdb.sqlite"],      // datastatus 의 열쇠
  "raw": "earth/pbdb_collections.csv",   // ① 원본의 자리(<DB 옆> 아래). 날짜 폴더면 raw/<id>/
  "docs": ["wetherilli 098"],
  "note": ""
}
```

- `schedule` 이 "늦었나" 를 정한다 — hourly 는 3 시간, weekly 는 9 일, monthly 는 40 일 넘게 된 적이 없으면 붉게. manual·once 는 늦지 않는다
- 사람에게 보이는 글은 `name` 처럼 **두 말로** 적는다 — `i18n` 표를 거치지 않는다(자료다). `i18n_missing` 이 이 파일도 긁어 영어가 빈 줄을 알린다

### 씨앗과 이력

- 저장소에는 **씨앗** `data/sources.seed.json` 을 둔다. 컨테이너가 뜰 때 `<DB 옆>/sources.json` 이 없으면 씨앗을 옮겨 놓고, 있으면
  **씨앗에만 있는 `id` 를 덧붙이기만** 한다 — 사람이 고친 줄은 덮지 않는다(`seed_catalog` 가 손질한 제목을 지키는 것과 같다).
  처음 씨앗은 `외부_자료원.md`·`datastatus.ITEMS`·`상류_조건표.md`·`hourly.sh`·`weekly_backup.sh` 에서 옮긴다
- **이력** — 읽을 때 파일의 sha256 이 앞서 본 것과 다르면 그 판을 `<DB 옆>/sources_history/<YYYYMMDD-HHMMSS>.json` 에 떠 두고
  `fetch_log` 에 `source="_spec"` 한 줄을 남긴다. 고친 사람은 파일만으로 알 수 없으니 `note` 칸(사람이 적는다)과 서버의 파일 주인을 적는다
- 주간 백업이 `sources.json`·`sources_history/`·`store.sqlite` 를 "다시 못 얻는 것" 으로 담는다(`weekly_backup.sh` 의 `WEEKLY`)

### 읽기와 검사 — `viewer/sources.py`(문이 아니다)

- 칸이 틀리거나 빠진 줄은 **건너뛰고 화면 머리에 띄운다** — 뷰어는 멈추지 않는다
- 시험이 지키는 것(씨앗에 대해) — 모든 `fetch_*`·`build_*` 명령이 어느 자료원의 `commands` 에 들어 있다, 모든 `datastatus.ITEMS` 의 열쇠가
  어느 자료원의 `outputs` 에 있다, `id` 가 겹치지 않는다. 새 명령을 더하고 씨앗에 안 적으면 시험이 깨진다
- **지금 있는 파이썬 표는 그대로 둔다** — `datastatus.ITEMS`·`static_site.UPSTREAMS`·`views.LAB_ONLY`·`views.NO_STORE`. 검토의 "손댈 일이
  생길 때 하나씩 JSON 으로" 를 따른다. 명세의 `flags` 와 이 표들이 어긋나면 시험이 알린다(어느 쪽을 고칠지는 사람이)

## 4. 기록 표 — `store.sqlite` 의 `fetch_log`

검토의 초안 그대로에 둘을 더한다.

| 칸 | 뜻 |
|---|---|
| `source` · `command` | 자료원 id, 부른 명령 |
| `started_at` · `seconds` | 시작한 때, 걸린 초 |
| `result` · `note` | ok · fail · skip(할 일 없음), 사람에게 한 말 마지막 줄 |
| `upstream_version` | 상류가 밝힌 판 — 없으면 빈칸 |
| `expected` · `rows` · `changed` | **상류가 센 수**, 받은(적재한) 수, 그 가운데 바뀐 것 — `expected` 와 `rows` 가 다르면 "상류가 일부만 줬다" |
| `raw_path` · `raw_sha256` | ① 원본의 자리와 sha — 같은 sha 면 새 벌을 두지 않았다는 뜻 |
| `built_at` · `built_by` | ③ 구운 때, 구운 명령과 그리는 법의 판(`RENDERER` 따위) |
| `estimated` | 1 이면 지난 것을 파일 `stat` 으로 어림해 채운 줄(아래 "처음 채우기") |

`expected` 는 kigam50k 의 `manifest.json`(`numberMatched` 대 받은 수)에서 왔다 — 상류가 잘라 준 것을 가리는 칸이다
(국토지반정보 지층 파일이 엑셀 한계에서 잘린 것 같은 일, `docs/국토지반정보_시추공.md`).

### 누가 쓰나

- **컨테이너의 명령** — `sources.record(source, command)` 문맥 관리자 하나를 `fetch_*`·`build_*` 의 `handle` 이 감싼다. 끝나면 결과·초를
  적고, 명령은 아는 것(`rows`·`expected`·`raw_path` …)을 그 안에서 채운다. 예외가 나면 `fail` 과 마지막 줄을 적고 다시 던진다
- **호스트 cron 의 일**(`hourly.sh` — 바람·구름·아라온호·최근 지진)은 지금처럼 `hourly_status.json` 만 쓴다 — 호스트와 컨테이너가 한 sqlite 에
  쓰지 않게(검토의 "잠금"). 컨테이너가 화면·healthz 를 그릴 때 그 JSON 의 새 차례(`at` 이 기록 표에 없는 것)를 `fetch_log` 로 옮겨 적는다.
  JSON 은 일마다 마지막 차례만 있으므로 **매시의 지난 차례는 사이가 빈다** — 그것으로 충분하다(늦었나만 보면 된다)
- **주간 백업의 받기**(`fetch_kopri`·`fetch_pbdb`)는 컨테이너 안의 manage.py 라 위 문맥 관리자가 그대로 적는다

### 처음 채우기

빈 표로 시작하면 화면이 한동안 "모름" 투성이다. `manage.py sources_backfill` 이 한 번 — `datastatus` 가 지금 하는 어림(파일 mtime·sqlite 의
`meta.built`·`rows`)으로 자료원마다 한 줄을 `estimated=1` 로 넣는다. 화면은 어림한 줄을 흐리게 그린다.

## 5. ① 원본 — 바뀐 판만, 최근 3 벌

- 원본을 날짜 폴더에 두는 자료원(지금은 kigam50k 하나, `raw/<YYYYMMDD>/` + `manifest.json`)의 틀을 `sources.save_raw(id, files)` 로 뽑아
  모두가 쓰게 한다 — sha256 이 바로 앞 벌과 같으면 새 폴더를 만들지 않고 기록 표에 "같다" 만 적는다
- `manage.py prune_raw` — 자료원마다 **최근 3 벌**만 남긴다. 사람이 부른다(cron 에 두지 않는다 — 지우는 일이다). `--dry-run` 이 먼저
- 원본을 날짜 없이 덮어쓰는 자료원(PBDB·지진 CSV 따위)을 날짜 폴더로 옮기는 것은 **적재 계획(뒤)에서** — 그때 굽기와 받기를 가른다.
  이 계획에서는 그 원본의 sha256 만 기록 표에 적어, 바뀌었는지는 지금부터 보인다

## 6. 관리 화면 — "자료원" 탭

검토의 표 그대로. 자료원 하나가 한 줄이고 **읽기만** 한다.

| 칸 | 어디서 |
|---|---|
| 자료원·기관 | 명세 |
| 조건 — 라이선스·비상업·판매·내부용 | 명세(`license`·`flags`) |
| 주기·돌리는 곳 | 명세 |
| 마지막으로 받은 때·결과·걸린 초·마지막 말 | 기록 표의 마지막 줄 |
| 마지막으로 **된** 때, 늦었나(붉게) | 기록 표 + 명세의 주기 |
| 상류 판·센 수 대 받은 수·바뀐 행 | 기록 표 |
| 산출물이 있나·크기·구운 판 | `datastatus`(명세의 `outputs`) + 기록 표 |

- 줄을 누르면 지난 차례들이 펼쳐진다(최근 20). 센 수와 받은 수가 어긋난 차례는 표시한다
- 탭 머리에 명세의 검사 결과(건너뛴 줄)와 마지막으로 명세를 고친 때
- **"구운 자료" 탭은 이 탭에 녹인다** — 같은 것을 다 보이게 된 판에서 지운다. "상류 응답 시간" 탭은 그대로(중계 상류 때문)
- 휴대폰에서는 줄을 카드로(#364·wetherilli 369 가 "저장 자료 관리" 탭에 들이는 틀 — 그 PR 이 병합된 뒤). CI 의 휴대폰 시험에 이 탭을 더한다
- 영어판 — 화면 글은 `i18n.EN`, 자료원 이름은 명세의 `name.en`
- healthz 에 `sources: {"late": n, "failed": n, "invalid": n}` 를 더한다

## 7. 차례

한 단계마다 브랜치·PR·devlog 하나. 병합·판은 판 세션(gsm-31)이 한다.

| 단계 | 브랜치 | 담는 것 | 어림 |
|---|---|---|---|
| 1 | `feature/source-spec` | `sources.py`(읽기·검사·씨앗 덧붙이기·이력), 씨앗 `data/sources.seed.json`, 컨테이너 시작 때 씨앗 옮기기, 시험(명령·산출물 빠짐 없음) | 하루 |
| 2 | `feature/fetch-log` | `store.sqlite` 의 `fetch_log`, `sources.record()` 를 `fetch_*`·`build_*` 에, `hourly_status.json` 옮겨 적기, `sources_backfill`, 주간 백업에 셋 담기 | 하루 |
| 3 | `feature/manage-sources` | "자료원" 탭(줄·펼침·늦음·검사 결과), "구운 자료" 탭을 녹이기, healthz, 휴대폰 시험, 영어 | 하루 |
| 4 | `feature/raw-prune` | `sources.save_raw()`(kigam50k 의 틀을 뽑는다), `prune_raw`, 기록 표에 원본 sha | 반나절 |

1–3 이 이 계획의 쓸모(화면)이고 4 는 따로 가도 된다.

## 8. 이 계획에 넣지 않은 것

- **② 적재**(행 자료를 `store.sqlite` 의 표로, 증분 upsert, 굽기와 받기를 가르기) — 검토의 "해 본다면" 1·2. 화석·지진 시범부터 **따로 계획**한다.
  이 계획의 기록 표와 `store.sqlite` 를 그대로 쓴다
- **명세를 화면에서 고치기** — 관리 화면에 계정이 없다(지금은 "그 브라우저의 것만 고친다" 는 전제다). 서버의 명세를 웹에서 고치려면 누가
  고쳤는지를 가릴 길이 먼저다. 그때까지는 서버에서 손으로 고치고(`/srv/GSM/db/` 는 `paleoadmin` 무리가 쓴다) 이력은 3 의 떠 두기가 남긴다
- **"지금 받기" 단추** — 사람이 정했다(처음엔 두지 않는다). 기록 표가 서면 다시 본다
- 중계 상류 여든 남짓의 조건을 이 명세로 옮기기 — `상류_조건표.md` 그대로

## 9. 위험

- **명세와 파이썬 표가 두 벌이 된다**(조건·내부용) — 옮기기 전까지는 시험이 어긋남을 알리는 것으로 버틴다. 사람이 고칠 쪽을 정한다
- **sqlite 쓰기가 겹친다** — 주간 백업의 받기와 사람이 부른 받기가 같은 때 돌면. WAL 과 짧은 트랜잭션(줄 하나)이면 대개 괜찮다. 호스트는 쓰지 않는다
- **씨앗과 운영 명세가 어긋난다** — 씨앗을 고쳐도 있는 `id` 는 덮지 않으므로, 씨앗의 고침이 운영에 안 닿는다. 화면이 "씨앗과 다른 줄" 을 표시해
  사람이 옮길지 정하게 한다
- 손으로 고친 JSON 이 깨진다 — 파일째 못 읽으면 마지막으로 읽힌 판(`sources_history/` 의 끝)을 쓰고 화면 머리에 붉게 띄운다

## 10. 확인하는 법

- 새 `fetch_*` 명령을 더하고 씨앗에 안 적으면 시험이 깨진다
- `fetch_kigam50k` 를 같은 날 두 번 부르면 기록 표에 두 줄, 둘째 줄은 "같다"(새 폴더 없음)
- 운영의 `hourly_status.json` 이 바뀌면 화면을 다시 열 때 "자료원" 탭의 바람·구름 줄이 새 시각
- `sources.json` 의 한 줄을 깨뜨리면 그 줄만 빠지고 머리에 띄고, 뷰어와 다른 줄은 돈다
- 주기보다 오래 안 된 자료원(예: 매시 일을 세 시간 멈춤)이 붉다. healthz 의 `late` 가 는다
