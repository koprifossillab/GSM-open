# CI 를 우리 서버(paleo-server)의 자체 러너로 — 검토

2026-10-20 · wetherilli · 정해진 것이 아니다. 정하면 P 문서를 쓴다

## 왜 따지나

개발 저장소 `koprifossillab/GSM` 을 2026-10-20 에 비공개로 돌렸다. 공개였을 때는 Actions 가 공짜였는데, 이제 월
할당량에서 빠진다. 계정은 Free 로 보인다(저장소 규칙 조회가 "Pro 로 올려라" 며 거절한다). 그러면 월 **2 000 분**이다.

- 10 월 1–20 일에 1 048 번, 4 000 분 남짓 돌았다(관리자 계정이 셌다). 병합한 PR 이 300 개를 넘는다
- 한 번에 드는 시간: 뷰어 시험 1.9 분, 휴대폰 화면 5.4 분, 이미지 굽기 1.0 분(최근 PR 24 번의 평균, 1 분 단위로 올림)
- 줄이는 고침(#432, wetherilli 397)을 넣으면 파이썬만 고친 PR 은 2 분쯤, 화면을 고친 PR 은 8 분쯤이다.
  한 달에 PR 실행이 500 번이면 1 500–3 000 분이라 **여전히 넘을 수 있다.** 넘으면 CI 가 멈추고 판이 막힌다
  (`release.sh` 가 태그 CI 의 성공을 기다린다)

## 자체 러너는 돈이 드나

**지금은 들지 않는다.** GitHub 이 2025-12 에 "2026-03-01 부터 자체 러너도 1 분에 $0.002, 할당량에서 뺀다" 고
알렸다가 미뤘다. 2026-10 현재 결제 문서에는 여전히 공짜로 적혀 있고 새 날짜는 없다. **거둬들인 것은 아니다** —
다시 걸리면 이 검토의 셈이 바뀐다.

## 서버가 감당하나

| | |
|---|---|
| CPU | 12 코어. 평균 부하 3–6 (운영 컨테이너 11 개: GSM·Cropobite·DiaRUGA·ForGIA·WegenersDream·phyloserver·scoda·refserver, 시험판 셋) |
| 메모리 | 62 GB 가운데 53 GB 남음 |
| 디스크 | `/` 70 GB 남음, `/data` 4.2 TB 남음 |
| OS | Ubuntu 24.04 — GitHub 러너(ubuntu-latest)와 같다 |

한 달 4 000 분이면 67 시간, 하루 두세 시간이다. 러너를 하나 두고 **코어 4·메모리 8 GB 로 묶으면**(systemd `CPUQuota=400%`·
`MemoryMax=8G`) GitHub 러너(4 코어)와 같은 속도이고 운영의 몫은 8 코어가 남는다. 일이 몰리면 줄을 서서 늦어질 뿐 깨지지 않는다.

## 걱정거리와 막는 법

1. **러너는 밀어 올린 코드를 무엇이든 돌린다.** write 권한이 있는 넷(koprifossillab·jikhanjung·wetherilli·summer02kini)
   누구나 이 서버에서 셸을 얻는 셈이다. 저장소가 비공개라 바깥 사람의 PR 은 없다. 그래도 운영 자료는 막는다.
   - 러너만 쓰는 계정(`ghrunner`)을 둔다 — sudo 없음, **docker 무리에 넣지 않는다**(docker 무리는 root 와 같다),
     `/srv/GSM/db`·`.env`·`/data/GSM` 을 못 읽게
   - 그래서 **이미지 굽기는 GitHub 러너에 남긴다.** #432 뒤로는 태그와 `deploy/` 를 고친 PR 에서만 돌아 한 달에 수십 분이다
2. **연구소 망의 TLS 가로채기.** 몇몇 https 를 "KOPRI SSL" 로 다시 서명한다(`deploy/ca/`). pip·playwright 의 브라우저 받기·
   setup-python 이 깨질 수 있다. `ghrunner` 의 환경에 `PIP_CERT`·`NODE_EXTRA_CA_CERTS`·`REQUESTS_CA_BUNDLE` 을 시스템
   묶음(`/etc/ssl/certs/ca-certificates.crt`, 뿌리가 이미 들어 있다)으로 건다. 처음 띄울 때 가장 오래 걸릴 자리다
3. **`playwright install --with-deps` 는 sudo 로 apt 를 부른다.** 관리자가 시스템 꾸러미를 한 번 깔고(`playwright install-deps`),
   러너에서는 `--with-deps` 를 뺀다
4. **시험이 운영을 건드리나.** 시험은 임시 DB 를 쓰고 LiveServer 는 빈 포트를 고른다. `GSM_*` 자리의 기본값이 `<DB 옆>` 이라
   `ghrunner` 가 운영 자리를 못 읽으면 잘못 짚어도 깨질 뿐 해는 없다. `--parallel auto` 는 12 코어를 다 보니 `--parallel 4` 로 박는다
5. **러너가 꺼지면 CI 가 무한정 기다린다.** `runs-on` 을 저장소 변수로 고르게 한다 —
   `runs-on: ${{ vars.GSM_RUNNER && fromJSON(vars.GSM_RUNNER) || 'ubuntu-latest' }}`. 서버가 내려가면 관리자가 변수 하나만 지우면 GitHub 러너로 돌아간다
6. **찌꺼기.** 작업 폴더·pip 캐시·브라우저(~500 MB)가 쌓인다. 러너 폴더를 `/data/ghrunner/` 에 두고, 한 달에 한 번
   `_work` 를 비운다. 옛 이미지 정리(`.guides/web/README.md`)와 같은 cron 에 얹을 수 있다
7. **형제 저장소.** DiaRUGA·ForGIA·WegenersDream 은 공개라 지금은 필요 없다. phyloserver 는 비공개지만 CI 가 없다.
   러너를 저장소에 걸지 계정 전체에 걸지 — 개인 계정이라 **저장소마다 따로 걸어야 한다**(계정 단위 러너는 조직에만 있다)

## 고르는 길

| | 한 달 분 | 일 | 위험 |
|---|---|---|---|
| A. #432 만 넣고 지켜본다 | 1 500–3 000 | 없음 | 바쁜 달에 할당량을 넘겨 CI 가 멈춘다 |
| B. Pro 로 올린다($4/월) | 3 000 까지 | 없음 | 10 월만큼 바쁘면 그래도 넘는다. 넘친 분은 1 분에 $0.006 쯤 |
| **C. 시험·휴대폰 화면은 자체 러너, 이미지는 GitHub** | 수십 | 반나절(관리자) | 1·2 번. 막는 법이 위에 있다 |
| D. 다 자체 러너 | 0 | C 와 같음 + docker | `ghrunner` 가 docker 무리 = 서버 root |

**권하는 것은 C 다.** A 를 #432 와 함께 이미 했으니 한 달 지켜보고 C 로 갈지 정해도 늦지 않다. 다만 10 월의 속도라면 11 월
중순쯤 할당량에 닿는다. C 를 하면 B 는 필요 없다.

## C 를 하면 할 일

1. 관리자(sudo): `ghrunner` 계정, `/data/ghrunner/`, `playwright install-deps`, CA 환경 변수
2. 관리자(GitHub `koprifossillab`): Settings → Actions → Runners → New self-hosted runner 에서 등록 토큰을 받는다.
   딱지는 `gsm`
3. `ghrunner` 로 러너를 풀고 `./config.sh --url https://github.com/koprifossillab/GSM --token … --labels gsm`,
   `sudo ./svc.sh install ghrunner`, systemd 덧설정에 CPU·메모리 한도
4. 워크플로(브랜치·PR): 뷰어 시험·휴대폰 화면의 `runs-on` 을 `vars.GSM_RUNNER` 로, 자체 러너에서는 `--with-deps` 빼기,
   `--parallel 4`. 이미지 굽기는 `ubuntu-latest` 그대로
5. 저장소 변수 `GSM_RUNNER=["self-hosted","gsm"]` — 이 값을 지우면 GitHub 러너로 돌아간다

## 출처

- GitHub Changelog, 2025-12-16 — Actions 가격 바꿈 알림과 자체 러너 몫을 미룬다는 덧글: <https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/>
- 미룬 뒤의 형편: <https://socket.dev/blog/github-actions-pricing-whiplash>, <https://craci.com/compare/github-actions-runner-providers>
