# 암석 시료 DB 의 이름도 박아 둔다

2026-10-12 · `fix/kopri-rock-host` · wetherilli

10-12 03:10 주간 백업에서 `fetch_kopri` 가 멈췄다 — `rock.kopri.re.kr` 의 이름을 못 찾았다(NameResolutionError). 백업·NAS·PBDB `--changed` 는
돌았고 운영 `healthz` 가 그 때문에 `degraded` 로 떴다. 서버가 먼저 묻는 DNS 가 `kopri.re.kr` 을 모르는 것은 095 와 같은 까닭이다 —
호스트에서도 못 찾고, 8.8.8.8·1.1.1.1 은 `203.250.179.26` 을 준다. 10-05 에는 받혔으니 그사이 그 DNS 가 rock 도 놓쳤다.

095 처럼 `extra_hosts` 에 한 줄 더했다. 버린 것 — 돌고 있는 컨테이너의 `/etc/hosts` 에 손으로 적기. 다시 띄우면 사라지고 기록이 남지 않는다.

**운영 compose(`/srv/GSM/docker-compose.yml`)는 paleoadmin 의 것이라 판 세션이 고치지 못한다.** 사람이 같은 한 줄을 더하고
`docker compose up -d web` 하면 다음 주간 백업부터 돈다. 서버 DNS 가 고쳐지면 095 의 줄들과 함께 지운다.
