# CI 를 서버의 자체 러너로 — 시험·휴대폰 화면은 우리 서버, 이미지는 GitHub (계획)

2026-10-20 · `main`(계획) → `feature/self-hosted-runner` · wetherilli

사용자: 「C안으로 가자, P 문서 써 줘」. 검토는 `docs/CI_자체_러너.md` — 거기서 C 를 골랐다.

## 왜

개발 저장소를 비공개로 돌려(2026-10-20) Actions 가 Free 할당량 2 000 분에 걸린다. 공개였던 10 월 1–20 일에 1 048 번,
4 000 분 남짓 돌았다. 397 의 고침으로 PR 한 번이 2–8 분으로 줄어도 바쁜 달에는 넘친다. 넘치면 `release.sh` 가 태그 CI 를
기다리다 멈추니 **판이 막힌다.** 자체 러너는 지금 분을 세지 않는다.

## 정한 것

- **뷰어 시험·휴대폰 화면은 자체 러너, 이미지 굽기는 GitHub 러너.** 이미지 굽기는 docker 가 있어야 하고, docker 무리는
  서버의 root 와 같다. 397 뒤로 이미지 굽기는 태그와 `deploy/` 를 고친 PR 에서만 돌아 한 달에 수십 분이다
- **러너 하나, 계정 `ghrunner`.** sudo 없음, docker 무리 아님, `/srv/GSM/db`·`/data/GSM`·`.env` 를 못 읽는다.
  write 권한이 있는 넷 누구나 이 계정으로 셸을 얻는 셈이라 운영 자료에서 떼어 둔다
- **코어 4·메모리 8 GB 로 묶는다**(systemd 덧설정 `CPUQuota=400%`·`MemoryMax=8G`, `Nice=10`). GitHub 러너와 같은 4 코어라
  `--parallel 4` 로 박는다 — `auto` 는 12 코어를 다 본다. 운영 컨테이너 11 개의 몫이 8 코어 남는다
- **러너 폴더는 `/data/ghrunner/`.** `/` 는 70 GB 남았다. 작업 폴더·pip 캐시·브라우저가 쌓인다
- **되돌리는 손잡이는 저장소 변수 하나.** `runs-on: ${{ vars.GSM_RUNNER && fromJSON(vars.GSM_RUNNER) || 'ubuntu-latest' }}`.
  `GSM_RUNNER=["self-hosted","gsm"]` 를 지우면 코드를 안 고치고 GitHub 러너로 돌아간다. 서버가 내려갔을 때 CI 가 무한정
  기다리지 않게
- **연구소 망의 TLS 가로채기**("KOPRI SSL", `deploy/ca/`)는 `ghrunner` 의 러너 `.env` 에 시스템 묶음을 건다 —
  `PIP_CERT`·`REQUESTS_CA_BUNDLE`·`SSL_CERT_FILE`=`/etc/ssl/certs/ca-certificates.crt`, `NODE_EXTRA_CA_CERTS`=
  `/usr/local/share/ca-certificates/kopri_ssl_root.crt`. 뿌리는 이미 시스템 묶음에 있다. 검증을 끄지 않는다

## 버린 것

- **다 자체 러너(D)** — 이미지 굽기까지 오면 `ghrunner` 를 docker 무리에 넣어야 한다. rootless docker 도 따졌지만
  운영 docker 와 나란히 두는 품이 아낄 분(한 달 수십 분)보다 크다
- **Pro 로 올리기** — 3 000 분도 10 월만큼 바쁘면 넘친다. 자체 러너가 서면 필요 없다
- **컨테이너 안의 러너**(myoung34/github-runner 따위) — 그것도 docker 소켓을 쥐어야 편하다. 계정 하나가 더 단순하다
- **러너 여럿** — 하나로 시작한다. 줄이 길어지면 그때 둘째를 같은 계정에 더한다

## 단계

1. **관리자(서버 sudo)** — `ghrunner` 계정·`/data/ghrunner/`, `playwright install-deps chromium`(시스템 꾸러미, 러너는
   `--with-deps` 없이 브라우저만 받는다), python3.12 가 `setup-python` 으로 받히는지 한 번
2. **관리자(GitHub `koprifossillab`)** — Settings → Actions → Runners → New self-hosted runner 의 등록 토큰.
   토큰은 한 시간짜리라 3 단계 바로 앞에 받는다. 저장소에 적지 않는다
3. **`ghrunner`** — 러너를 풀고 `./config.sh --url https://github.com/koprifossillab/GSM --labels gsm --unattended`,
   `.env` 에 CA 변수, `sudo ./svc.sh install ghrunner`·덧설정·`start`. 이 손순서를 `deploy/host/runner.md` 에 적는다
4. **워크플로(`feature/self-hosted-runner`, PR)** — 뷰어 시험·휴대폰 화면의 `runs-on` 을 변수로, 자체 러너에서는
   `--with-deps` 빼기(`runner.environment == 'self-hosted'` 로 가른다), `--parallel 4`. 이미지 굽기는 그대로.
   **변수를 걸기 전에 병합해도 지금과 같다** — 변수가 비면 `ubuntu-latest`
5. **바꾸기** — 저장소 변수 `GSM_RUNNER` 를 걸고 `workflow_dispatch` 로 한 번, PR 하나로 한 번 돌려 본다.
   깨지면 변수를 지우고 devlog 에 적는다
6. **청소** — 한 달에 한 번 `_work` 와 pip 캐시를 비운다. 옛 이미지 정리 cron 옆에 둔다(`.guides/web/README.md`)

## 지켜볼 것

- 휴대폰 화면이 GitHub 러너보다 느리거나 흔들리는지 — 397 에서 느린 러너에 흔들린 시험을 하나 고쳤다
- 운영 응답이 CI 가 돌 때 느려지는지(`upstream_stats`·nginx 시간). 느려지면 `CPUQuota` 를 내린다
- GitHub 이 자체 러너 몫($0.002/분)을 다시 걸면 셈을 다시 한다 — 그래도 할당량에서 빠지는 것은 같다
