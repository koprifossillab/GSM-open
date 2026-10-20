# CI 자체 러너 — paleo-server 에 세우고, 고치고, 내리는 손순서

계획과 까닭은 devlog wetherilli P15. 뷰어 시험·휴대폰 화면만 여기서 돌고 이미지 굽기는 GitHub 러너다.
워크플로는 저장소 변수 `GSM_RUNNER` 가 있을 때만 이 러너를 고른다.

| | |
|---|---|
| 계정 | `ghrunner` (시스템 계정, sudo·docker 무리 아님) |
| 자리 | `/data/ghrunner/runner`(러너), `/data/ghrunner/_work`(작업 폴더) |
| 이름·딱지 | `paleo-server` · `gsm` |
| 서비스 | `actions.runner.koprifossillab-GSM.paleo-server.service` |
| 한도 | `CPUQuota=400%`·`MemoryMax=8G`·`Nice=10`·`IOSchedulingClass=idle` |

## 세우기

1. 계정 — `sudo adduser --system --group --home /data/ghrunner --shell /bin/bash ghrunner`, `sudo chmod 750 /data/ghrunner`.
   `sudo -u ghrunner ls /srv/GSM/db /data/GSM` 가 Permission denied 여야 한다. 열려 있으면 `sudo chmod o-rwx /srv/GSM/db /data/GSM` —
   운영 컨테이너는 주인(paleoadmin, uid 1000)으로 돌아 그대로 읽는다. paleoadmin 무리가 아닌 다른 계정도 함께 못 읽게 된다(2026-10-20)
2. 브라우저 꾸러미 — 러너는 sudo 가 없어 `playwright install --with-deps` 를 못 한다. 관리자가 한 번:
   `python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright==<requirements-browser.txt 의 판> && sudo /tmp/pw/bin/playwright install-deps chromium`.
   playwright 판을 올리면 다시 한다
3. 러너 — `actions/runner` 의 linux-x64 릴리스를 `~/runner` 에 풀고 sha256 을 맞춘다
4. TLS — 연구소 망이 몇몇 https 를 "KOPRI SSL" 로 다시 서명한다(`deploy/ca/`). `~/runner/.env` 에
   ```
   PIP_CERT=/etc/ssl/certs/ca-certificates.crt
   REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
   SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
   NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/kopri_ssl_root.crt
   ```
5. 등록 — 관리자 계정(`koprifossillab`)의 `gh api -X POST repos/koprifossillab/GSM/actions/runners/registration-token --jq .token`.
   한 시간짜리다. 받은 자리에서
   ```
   TOKEN=$(gh api -X POST repos/koprifossillab/GSM/actions/runners/registration-token --jq .token)
   cd /data/ghrunner/runner && sudo -u ghrunner ./config.sh --url https://github.com/koprifossillab/GSM --token "$TOKEN" \
     --name paleo-server --labels gsm --work /data/ghrunner/_work --unattended
   unset TOKEN
   ```
   **`sudo -u ghrunner -i bash -c "… $TOKEN …"` 로 감싸지 않는다** — 2026-10-20 에 그렇게 불러 토큰이 빈 채로 넘어가 등록이
   한 번 깨졌다. `-i` 없이 러너 폴더에서 곧장 부른다. 토큰은 어디에도 적지 않는다
6. 서비스 — `sudo ./svc.sh install ghrunner`, `sudo systemctl edit <서비스>` 로 위 한도를 `[Service]` 에, `sudo ./svc.sh start`
7. 켜기 — 저장소 변수 `GSM_RUNNER` = `["self-hosted","gsm"]` (Settings → Secrets and variables → Actions → Variables,
   또는 `gh variable set GSM_RUNNER -R koprifossillab/GSM --body '["self-hosted","gsm"]'`)

## 내리기·되돌리기

- **잠깐 GitHub 러너로** — `gh variable delete GSM_RUNNER -R koprifossillab/GSM`. 기다리던 실행은 취소하고 다시 부른다
- **러너를 없앤다** — `sudo ./svc.sh stop && sudo ./svc.sh uninstall`, 관리자 계정의 remove-token 으로 `./config.sh remove --token …`

## 살피기

- 살았나 — `gh api repos/koprifossillab/GSM/actions/runners --jq '.runners[]|[.name,.status,.busy]|@tsv'`
- 기록 — `journalctl -u <서비스> -n 100`, 작업마다 `~/runner/_diag/`
- 청소 — 한 달에 한 번 `sudo -u ghrunner rm -rf /data/ghrunner/_work/GSM` 과 `~/.cache/pip`. 브라우저(`~/.cache/ms-playwright`)는 판이 바뀔 때만
- 러너 판 — 러너가 스스로 올린다. 올리지 못하면(GitHub 이 너무 옛 판을 거절한다) 3 단계를 다시 한다
