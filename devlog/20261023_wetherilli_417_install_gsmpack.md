# 호스트 cron 사본에 묶음 패키지도 옮긴다

2026-10-23 · `fix/install-gsmpack` · wetherilli

1.2.0 을 배포하고 본 healthz 가 degraded 였다 — 호스트 cron 의 받기 넷(`fetch_araon`·`fetch_gfs_wind`·`fetch_gmgsi`·`fetch_recent_quakes`)이
`ModuleNotFoundError: No module named 'gsmpack'` 로 깨지고 GFS 바람은 53 시간, GMGSI 는 46 시간 묵어 있었다. 1.2.0 탓이 아니다.
1.1.0 부터 `settings.py` 가 `<저장소>/tools/gsmpack` 을 sys.path 에 얹고 `viewer/views.py` 가 `gsmpack` 을 import 하는데,
`deploy/scripts/install.sh` 는 호스트 사본(`/srv/GSM/scripts/app`)에 `web/`·`data/`·requirements 만 옮겼다. 관리 명령이 viewer 를 타니
1.1.0 배포(10-21)부터 호스트에서 도는 것이 다 깨졌다.

## 고친 것

install.sh 의 tar 목록에 `tools/gsmpack/gsmpack`(패키지만)을 더했다. settings 가 얹는 자리가 `REPO_DIR/tools/gsmpack` 이고
`REPO_DIR` 는 사본에서 `/srv/GSM/scripts/app` 이니 같은 자리에 두면 된다.

버린 것
- **호스트 venv 에 `pip install ./tools/gsmpack`** — settings 의 머리글이 "깔게 하면 개발 venv·CI·이미지·호스트 venv 를 다 챙겨야 하고 하나를 빠뜨리면
  깨진다" 며 깔지 않기로 한 것과 어긋난다. run.sh 의 venv 지문에도 넣어야 한다
- **viewer 가 gsmpack 을 늦게 import** — 묶음 굽기·요청 뷰가 여럿이라 고칠 자리가 흩어지고, 다음에 머리에 import 를 더하면 또 깨진다
- **README·js·pyproject·시험까지 통째로** — cron 은 패키지만 쓴다

## 운영에서 한 것

사람이 정해(2026-10-23) 1.2.1 을 기다리지 않고 컨테이너 안에서 `/app/tools/gsmpack/gsmpack` 을 `/srv/GSM/scripts/app/tools/gsmpack/` 에 손으로
복사했다 — 컨테이너를 다시 띄우면 install.sh 가 app/ 를 새로 깔아 사라지고, 그때부터는 이 고침이 옮긴다.

## 확인

고친 install.sh 를 빈 자리에 돌리고 그 사본에서 `GSM_RUN_PLACE=host` 로 `django.setup(); import viewer.views, gsmpack` — 된다.
