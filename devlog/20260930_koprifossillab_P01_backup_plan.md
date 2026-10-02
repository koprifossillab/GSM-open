# 백업 — WegenersDream 의 틀로, 바뀌는 빠르기에 따라 넷으로 (계획)

2026-09-30 · `main` · koprifossillab

사람이 "GSM 에도 딱히 DB 를 쓸 일은 없어 보인다. WegenersDream 의 백업 정책을 보고 비슷하게 세워 달라 — 자료를 가져오는
파이프라인의 종류·주기·양을 가늠해서" 라고 했다. 본보기는 WegenersDream 의 `docs/백업.md` 와
WegenersDream koprifossillab 032 다. 숫자는 모두 2026-09-30 저녁에 운영(v0.25.6)에서 쟀다.

## 1. 지금 GSM 은 백업이 하나도 없다

crontab 에 GSM 줄이 없고 저장소에도 백업 스크립트가 없다. 운영 자리는 셋이다.

| 자리 | 크기 | 무엇 |
|---|---|---|
| `/srv/GSM/db/` (루트 SSD) | 1.5 GB | `GSM.db`·설정 파일·**모아 둔 것**·**구운 것**·원본 사본 |
| `/data/GSM/tiles/` (8 TB 하드) | 1.2 GB, 파일 3 만 4 천 | 타일 캐시 — 타일·범례(png) 3 만 3 900, 속성·점(json) 630 (wetherilli 082 가 옮겼다) |
| `/nfs/temp-share/GSM/sources/` (NAS) | 3.9 GB | 굽기 전의 원본. **사본이 여기 하나뿐이다** |

`/srv/GSM/tiles/`(664 MB)는 082 로 옮기기 전의 캐시가 남은 것이다. compose 가 더는 붙이지 않는다. 지울지는 사람이 본다.

### DB 는 정말 비어 있다

`GSM.db` 는 384 KB 다. 점묶음·점·모양이 **0 건**이고, 레이어 203·레이어군 42 는 저장소의 씨앗(`data/*_layers.json`)에서
`seed_catalog` 가 다시 채운다. 사람이 손질한 한글 제목도 씨앗 파일에 있다. DB 에만 있는 것은 상류 호출 기록(`UpstreamDay`
33 줄)과 지운 점묶음 기록(1 줄)뿐이다. 그래도 점묶음을 올리는 순간 **다시 만들 수 없는 유일한 자료**가 되므로 매주 사본을
뜬다. 작아서 부담이 없다.

## 2. 파이프라인 — 무엇을, 얼마나 자주, 얼마만큼 받나

갈래는 넷이다. 백업을 가르는 기준은 하나다 — **그날의 것을 다시 얻을 수 있나.**

### 가. 상류에서 모아 두는 것 — 다시 못 얻는다 (백업 1순위)

| 명령 | 자리 | 지금 크기 | 받는 데 드는 것 | 주기(제안) | 왜 다시 못 얻나 |
|---|---|---|---|---|---|
| `fetch_kopri` | `db/kopri/` | 2.7 MB (json 둘) | 처음 두 시간(상세 3 500 쪽, 2 초 간격), 다음부터 목록 여덟 장 + 새 상세 — 수 분 | **매주** | **목록에서 사라진 자료는 파일에서도 뺀다.** 지난주 목록은 백업에만 남는다 |
| (손으로 받음, 명령은 jikhanjung P01 1 단계) `fetch_kigam50k` | `db/kigam50k/raw/<날짜>/` | 2.5 MB (gz, 19 레이어) | WFS 40 번 남짓, 2 초 간격 | **매달** | **문서에 없는 주소(GeoServer WFS)다.** 닫히면 새로 받을 길이 없다. 날짜 폴더는 지우지 않고, 같은 sha256 이면 새 폴더를 만들지 않는다 |
| `fetch_pbdb` | `<EARTH_DIR>/pbdb_collections.csv`·`pbdb.sqlite` | 운영에 아직 없다 (`db/earth/` 없음). 받으면 CSV 110–160 MB | 한 번에 몇 분 | **매달** | WegenersDream 과 같다 — PBDB 는 자라고, 그날의 것은 다시 못 받는다. sqlite 는 CSV 로 다시 굽는다 |

PBDB 는 WegenersDream 이 매주 받는다. 두 앱이 같은 것을 매주 받을 까닭은 없으므로 GSM 은 매달로 둔다. 자료를 나누지 않는
규약(CLAUDE.md)이 있으니 WegenersDream 의 사본을 읽지는 않는다.

### 나. 상류에서 받아 캐시에 보태는 것 — 다시 얻을 수 있지만 느리다

| 명령·길 | 자리 | 크기 | 주기 |
|---|---|---|---|
| 화면이 부를 때(타일·범례·속성) | `/data/GSM/tiles/` | 1.2 GB, 늘어난다 | 늘 |
| `prewarm` (1 초에 한 장, 최대 2 000) | 같은 자리 | 부를 때마다 | 사람이 |
| `fetch_grportal` (그린란드 시료 2 만·NPI 점·지명·도폭 경계) | 같은 자리(json) | 수십 MB | 배포 뒤 한 번, 가끔 `--refresh` |

캐시는 "덤이지 자료가 아니다"(CLAUDE.md). 그래도 통째로 잃으면 3 만 4 천 번을 다시 물어야 한다. `prewarm` 의 빠르기(1 초에
한 장)로 치면 아홉 시간 반이다. 한 번에 몰아 묻지 않는다는 규칙(010)을 생각하면, 싼 거울 하나를 둘 값이 있다. **이력은
필요 없다** — 새 것이 이기므로(“받아온 것의 순위”) 옛 판 타일로 되돌릴 일이 없다.

### 다. 원본에서 굽는 것 — 다시 구울 수 있다

| 명령 | 자리 | 크기 | 다시 굽는 데 드는 것 |
|---|---|---|---|
| `build_ibcso` | `db/ibcso/` | 627 MB | 13 분, 메모리 5.8 GB |
| `build_peninsula` | `db/peninsula/` | 96 MB | 24 초, 메모리 3.5 GB |
| `build_moon_originals` | `db/moon/` | 193 MB (spa tif 108 MB 포함) | 몇 분 |
| `build_mars_originals`·`build_mars_craters` | `db/mars/` | 74 MB | 몇 분 |
| `build_paleocoastlines`·`build_mantle` | `db/earth/` | 운영에 아직 없다 (mantle 175 MB 예정) | 몇 분 |
| (굽지 않고 그대로 두는 원본 사본) | `db/geomap/`·`db/usgs/`·`db/npolar/` | 481 MB | 복사 |

주기는 **판이 바뀔 때뿐이다** — 원본이 새 판이거나 굽는 법을 고쳤을 때 사람이 부른다. 저장소에 담는 작은 결과물
(`build_paleomap`·`build_crust`·`build_natural_earth`·`build_ice_margins`·`build_zhurong`, `fetch_moon_places`·
`fetch_trek_catalog`)은 git 이 지킨다.

### 라. 원본 — NAS 에 하나뿐이다

`/nfs/temp-share/GSM/sources/` 3.9 GB — 남극 1.2 GB·IBCSO 660 MB·지구 642 MB·달 494 MB·화성 490 MB·그린란드 323 MB·
한반도 54 MB·얀마옌 14 MB·중국 9 MB. 대부분 Zenodo·USGS·PANGAEA 에서 다시 받을 수 있다. 다만 주소는 사라지기도 한다.
**한반도 지질도(음영판·민판)는 김선호 님께 받은 것이라 공개된 곳이 없다.** 원본이 NAS 한 곳에만 있으면, NAS 가 곧
유일한 사본이 된다.

## 3. 계획 — 넷으로 가른다

WegenersDream 은 한 tar 에 다 넣었다(주 140 MB). GSM 에서 그렇게 하면 주 2.7 GB, 1 년에 140 GB 가 되고 그 대부분이 안
바뀐 것이다. 그래서 **바뀌는 빠르기대로 가른다.** 자리 규약(`/data/<앱>/backups/`·`/nfs/temp-share/<앱>/backup/`)과
권한·검증·결과 파일은 WegenersDream 의 것을 그대로 쓴다.

| | 무엇 | 언제 | 어떻게 | 크기·늘어남 | 보관 |
|---|---|---|---|---|---|
| **① 주간 tar** | `GSM.db`(sqlite `.backup` 사본) · `kopri/` · `kigam50k/` · PBDB CSV(생기면) · `/srv/GSM/docker-compose.yml` · `db/` 전체의 목록(경로·크기·sha256) | 매주 | `GSM.<YYYYMMDD>.tar.gz` → 로컬과 NAS, sha256 대조 | 지금 5 MB 남짓, PBDB 가 들면 40 MB 남짓 → 1 년 0.3–2 GB | 모두 둔다 |
| **② 구운 것 tar** | `db/` 의 나머지(가 ①·설정 파일 빼고) | 매주 보되 **목록이 지난번과 다를 때만** | `GSM-built.<YYYYMMDD>.tar` (압축 안 함 — webp·tif 가 대부분이다) → 로컬과 NAS | 1.1–1.5 GB 한 벌 | 나이로 줄인다: 30 일까지 전부 · 그 뒤 달 1 개 (ForGIA·DiaRUGA 의 계단식) |
| **③ 캐시 거울** | `/data/GSM/tiles/` | 매주 | `rsync -a`(`--delete` 없음) → NAS `GSM/tiles/` | 1.2 GB, 캐시만큼 늘어난다 | 거울 하나 |
| **④ 원본 거울** | NAS `GSM/sources/` | 매주 | `rsync -a`(`--delete` 없음) → `/data/GSM/sources/` | 3.9 GB, 원본이 올 때만 늘어난다 | 거울 하나 |

② 에 목록 비교를 쓰는 것은, 판을 올릴 때마다 사람이 "구운 것 백업" 을 기억하지 않아도 되게 하려는 것이다. 목록(①에 든다)은
sha256 이라 1.5 GB 를 다 읽는다. SSD 라 수십 초다.

③·④ 는 **방향이 반대다** — 캐시는 로컬 → NAS, 원본은 NAS → 로컬. 어느 쪽이든 한 곳이 죽어도 다른 곳에 남게 하려는 것이다.

### 백업하지 않는 것

| 것 | 다시 얻는 법 |
|---|---|
| 코드 | GitHub `koprifossillab/GSM` — 판마다 태그 `v*` |
| 웹 이미지 | Docker Hub `koprifossillab/gsm:<태그>` |
| 레이어 카탈로그 | 저장소 씨앗 → `seed_catalog` (컨테이너가 뜰 때 돈다) |
| `db/kigam_key`·`db/vworld_key` | **일부러 뺀다.** NAS 는 누구나 읽는 공유다. 각 누리집의 마이페이지(data.kigam.re.kr·vworld.kr)에서 다시 본다 |
| `db/secret_key`·`/srv/GSM/.env` | 뺀다. 비밀키는 새로 만들면 열린 화면의 CSRF 만 무효가 된다 |
| `db/geus_whoami`·`db/allowed_hosts` | 뺀다(이메일이 든다). 한 줄짜리라 손으로 다시 쓴다 |
| 옛 캐시 `/srv/GSM/tiles/` | 082 전의 것. 거울에 넣지 않는다 |

## 4. 언제 — 월요일 01:40, 백업을 먼저

WegenersDream 과 같은 요일에 **한 시간 먼저** 돈다. 새벽 자리는 이렇게 차 있다 — 매시 :20·:25(DiaRUGA·ForGIA 스냅샷),
월 02:30(WegenersDream), 03:00·04:00(phyloserver), 04:40·05:10(NAS 동기화), 05:00(타임랩스). ①② 는 1 분 남짓, 첫 ③④ 는
5 GB 를 옮기니 수십 분이다. 그다음부터는 늘어난 것만 옮기므로 수 분이다. 02:30 전에 끝난다.

순서는 WegenersDream 처럼 **백업 → 받기**다. `fetch_kopri` 가 사라진 자료를 지우므로, 받기 전에 떠야 지난주 목록이 남는다.

```
flock
① 주간 tar            (늘)
② 구운 것 tar          (목록이 다를 때만)
③ 캐시 → NAS           (NAS 가 붙어 있을 때만)
④ NAS 원본 → /data     (NAS 가 붙어 있을 때만)
⑤ fetch_kopri          (매주 — 새 것만, 수 분)
⑥ fetch_kigam50k       (그달의 첫 월요일 — 명령이 생기면)
⑦ fetch_pbdb           (그달의 첫 월요일 — db/earth 가 운영에 서면)
결과 → /data/GSM/logs/last_backup.json
```

⑤–⑦ 은 컨테이너 안에서 부른다(`docker compose -f /srv/GSM/docker-compose.yml exec -T web python manage.py …`).
컨테이너에는 KPDC 의 `extra_hosts` 가 박혀 있어 이름을 찾는다(wetherilli 095). 호스트에는 GSM venv 가 없다.
받기가 실패해도 지난 파일이 남는다 — `fetch_kopri` 는 25 쪽마다 적고, kigam50k 는 받은 수가 센 수와 같을 때만 적는다.

NAS 는 WegenersDream 과 같이 다룬다. `mountpoint` 로 붙어 있는지 보고, `hard` 마운트라 `timeout` 으로 감싼다. `.part` 로
옮긴 뒤 sha256 을 대조하고 이름을 바꾼다. **NAS 가 실패해도 로컬 백업과 받기는 한다** — 결과의 `nas` 칸에 남는다.
`/data` 는 누구나 들어오는 디스크(777)라 `umask 027`(파일 640·디렉토리 750)이다.

## 5. 되살리기 — 서버를 통째로 잃었을 때

1. `/srv/GSM/` 에 compose(① 에 든다)와 `.env`(키는 누리집에서 다시 본다), `db/` 에 설정 파일 한 줄씩
2. ② 의 가장 새 tar 를 `db/` 에 푼다 — 없으면 NAS 원본(또는 ④ 의 거울)으로 `build_*` 를 부른다
3. ① 의 가장 새 tar 에서 `GSM.db`·`kopri/`·`kigam50k/`·PBDB CSV 를 제자리에 둔다
4. ③ 의 거울을 `/data/GSM/tiles/` 로 되돌린다 — 없어도 뷰어는 돈다
5. `docker compose pull && docker compose up -d web`, `deploy/host/smoke.sh`

되살리기는 스크립트를 만든 날 한 번, 임시 폴더에 풀어 확인한다(WegenersDream 이 09-30 에 한 것처럼).

## 6. 단계

1. `deploy/host/weekly_backup.sh` — ①②, `--backup-only`·`--no-fetch` 로 나눠 부를 수 있게. 조각
   `deploy/host/crontab.GSM`
2. ③④ NAS 거울
3. ⑤ `fetch_kopri` 를 매주 — 처음 몇 주는 `upstream_stats` 로 KPDC 에 얼마나 묻는지 본다
4. ⑥⑦ 은 그 명령·자리가 운영에 서는 판에서 더한다
5. 되살리기를 한 번 해 보고 `docs/백업.md` 로 옮겨 적는다 — "지금 어떻게 돈다" 는 거기서 늘 지금에 맞춘다

## 7. 버린 것

- **한 tar 에 다 넣기**(WegenersDream 처럼) — 주 2.7 GB 가운데 안 바뀐 것이 2.6 GB 다
- **캐시를 tar 로 날마다** — 이력이 쓸모없고(새 것이 이긴다) 파일이 3 만 개라 tar 가 느리다
- **DB 시간별 스냅샷**(DiaRUGA·ForGIA 의 hourly track) — 점묶음이 0 건이다. 점묶음을 쓰기 시작하면 그때 더한다(§8)
- **cron 이 `git pull`·배포까지** — WegenersDream 032 와 같은 까닭이다. 코드는 사람이 병합·배포할 때만 바뀐다
- **`prewarm`·`fetch_grportal --refresh` 를 cron 에** — 상류에 크게 묻는 일은 사람이 보고 부른다(010)

## 8. 사람이 정할 것

- **키를 어디에도 두지 않아도 되나** — 이 계획은 키를 백업에서 뺀다. 로컬 `/data` 에만 600 으로 따로 둘 수도 있다
- **③ 캐시 거울을 둘까** — 없어도 된다는 것이 CLAUDE.md 의 입장이다. 1.2 GB 를 NAS 에 더할 값이 있는지
- **점묶음을 쓰기 시작하면** — 그때는 ① 의 주 1 회로 모자란다. DiaRUGA 처럼 날마다(또는 시간마다) `GSM.db` 사본을 더한다
- **`/srv/GSM/tiles/`(664 MB, 082 전의 캐시)를 지울까** — 루트 SSD 가 73% 다
- **남는 한계** — WegenersDream 과 같다. NAS 와 서버가 같은 건물이라 건물 사고는 못 막는다. `/healthz` 가 백업 상태를 모른다
