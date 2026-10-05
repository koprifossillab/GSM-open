# 판을 다시 띄워도 남는 기록 — DB 옆 logs/ 에 하루 한 장

2026-10-05 · `feature/persistent-logs` · wetherilli

wetherilli 347 에서 걸렸다 — 판마다 컨테이너를 다시 띄워 `docker logs` 가 사라지고, 오늘만 여섯 번이라 299 의 점검표("지난 하루의 메타타일")를 셀 수 없었다.

## 한 것

- **자리는 `<DB 옆>/logs`**(`/srv/GSM/db/logs`). DB 자리는 운영 compose 가 이미 붙여 두었다 — **운영 compose 를 고칠 것이 없다.** 엔트리포인트가 `GSM_LOG_DIR` 를 그리로 정하고 만든다.
  못 만들면 화면에만 낸다
- 접근 기록(gunicorn)은 `access-YYYYMMDD.log`, 앱 기록(gunicorn 오류 + Django)은 `app-YYYYMMDD.log`. `docker logs` 에도 여전히 낸다
- **크기 한도 하루 한 장 50 MB, 지우는 날 30 일**(`GSM_LOG_MAX_MB`·`GSM_LOG_KEEP_DAYS`). 어제 nginx 접근 기록이 324 KB 였으니 넉넉하다. 한도를 넘으면 그날은 넘었다는 줄 하나만 남기고 멈춘다
- **키를 남기지 않는다** — 질의 변수 이름에 key·token·secret·password·whoami·signature 가 든 값은 `…` 로 지운다. 연결 레이어(`linked/fetch/?url=`)처럼
  남의 주소가 인코딩돼 들어오는 것(`%3Fapikey%3D…%26`)도 본다. 같은 지우기를 **`docker logs` 로 가는 줄에도** 건다 — 앞에는 브라우저가 보낸 질의가 그대로 나갔다.
  우리 KIGAM 키는 브라우저에 없으니 원래 접근 기록에 들 일이 없지만, 연결 레이어에 사람이 넣은 남의 키는 들 수 있었다
- 주간 백업의 ②(구운 것)에서 `logs/` 를 뺐다 — 날마다 바뀌어 넣으면 ② 가 매주 새로 뜬다(`weekly_backup.sh` 의 `SECRETS`). 판을 올리면 엔트리포인트가 cron 사본을 새로 깐다

## 고른 것과 버린 것

- **돌려 쓰기(`TimedRotatingFileHandler`)를 버렸다** — 워커 셋이 저마다 한밤에 이름을 바꾸다 서로의 장을 덮는다. 대신 이름에 날짜를 넣고 `O_APPEND` 로 한 줄씩 쓴다.
  날이 바뀌면 각 프로세스가 새 장을 열 뿐이라 부딪힐 것이 없고, 지우기는 먼저 지운 워커가 있어도 넘어간다
- **gunicorn `--access-logfile <파일>` 을 버렸다** — 화면과 파일 둘에 내지 못하고, 날로 끊지도 못한다. `on_starting` 에서 손잡이를 더해 워커가 물려받는다(`deploy/gunicorn.conf.py`).
  워커·스레드·시간 한계는 명령줄 그대로다
- **compose 의 `logging:`(json-file 의 max-size)을 버렸다** — 그것은 컨테이너가 사라지면 같이 사라진다. 그리고 그 파일은 운영 compose 라 사람이 고쳐야 한다
- 개발·시험은 `GSM_LOG_DIR` 가 없어 파일을 쓰지 않는다

## 확인

이미지를 구워 빈 자리에 띄웠다 — `logs/` 에 두 장이 생기고, `?key=SECRET` 은 파일과 `docker logs` 모두에서 `key=…` 다. 진짜 gunicorn(워커 둘)으로도 워커의 Django 경고가 `app-` 에 든다.
