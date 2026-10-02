# cron 은 /srv/GSM/scripts 의 사본을 전용 venv 로 돈다

2026-10-01 · `feature/araon-track` · koprifossillab

## 1. 왜

아라온호 위치(koprifossillab 004)를 cron 에 붙이고 보니 cron 이 **저장소 체크아웃**(`~/projects/GSM/web`)과
개발용 venv(`~/venv/GSM`)를 부르고 있었다. 주간 백업도 그랬다. 그러면 체크아웃을 다른 브랜치로 옮기는 순간
운영의 일이 멈추거나 남의 브랜치 코드를 돈다 — 그날 `feature/wind-data` 로 돌아가면 `fetch_araon` 이 없었다.
사람이 "/srv/GSM 밑에 scripts 디렉토리 만들고 cron 으로 돌려야 하는 작업들은 그쪽 스크립트에 전용 venv 만들어서
해야 될 거야. 그리고 스크립트들은 docker image 에 넣고 컨테이너 올리면서 scripts/ 에 복사해 놓고" 라고 했다.

## 2. 어떻게

- `deploy/scripts/` 가 원본이다. `COPY . .` 로 이미 이미지에 들어간다
- **컨테이너가 뜰 때** entrypoint 가 `install.sh` 로 `/srv/GSM/scripts/` 에 깐다 — 스크립트(`*.sh`)와 **앱 코드 사본**
  (`app/` = `web/{manage.py,gsmweb,viewer}`·`data/`·requirements). 판을 올리면 cron 도 그 판을 돈다
- 파이썬 일은 `run.sh <관리 명령>` 이 `scripts/venv` 로 돈다. venv 는 호스트가 만든다
- 운영 compose 에 `/srv/GSM/scripts` 마운트를 더했다. 마운트가 없으면 `install.sh` 는 아무것도 하지 않는다

## 3. 고른 것과 버린 것

- **앱 코드도 함께 옮긴다.** 스크립트만 옮기면 `fetch_araon` 같은 관리 명령이 기댈 `viewer` 가 없다. 일을
  스크립트로 따로 다시 짜는 길은 버렸다 — 상류마다 문이 하나라는 규칙이 깨진다(`kopri.py` 와 같은 것을 두 벌).
  정적 파일·시험은 빼서 7 MB 다
- **venv 는 컨테이너가 만들지 않는다.** 이미지의 파이썬은 `/usr/local/bin/python3` 라 거기서 만든 venv 는 호스트에서
  돌지 않는다. 호스트의 `/usr/bin/python3` 로 `run.sh` 가 만든다
- **venv 는 스스로 맞춘다.** 파이썬 판과 `app/requirements-*.txt` 의 지문을 `venv/.stamp` 에 두고, 다르면 다음
  차례에 다시 만든다. 판을 올릴 때 사람이 venv 를 손볼 일을 없애려는 것이다. 다 깔린 뒤에만 지문을 적어, 깔다
  멈추면 다음 차례에 다시 한다. 만드는 동안 다른 명령은 기다린다(돌고 있는 쪽 공유 잠금, 만드는 쪽 배타 잠금)
- 바꿔 끼우기는 `.app.new` 에 다 풀고 나서 한다 — 옮기다 멈춰도 앞의 사본이 깨지지 않는다
- `docker exec` 로 컨테이너 안에서 도는 길(ForGIA 의 `dbrun.sh`)은 이번에 고르지 않았다 — 바람(koprifossillab P02)이
  numpy·ecCodes 를 쓰는데 운영 이미지에 넣지 않기로 했기 때문이다. 주간 백업의 `fetch_kopri` 는 KPDC 의
  `extra_hosts` 때문에 여전히 컨테이너 안에서 부른다(wetherilli 095)
- `weekly_backup.sh` 를 `deploy/host/` 에서 `deploy/scripts/` 로 옮겼다. 저장소 경로를 안 쓰므로 고친 것은 머리말뿐이다

## 4. 지금

2026-10-01 에 저장소에서 `install.sh . /srv/GSM/scripts` 로 손수 깔고 crontab 의 두 줄(주간 백업·아라온)을
`/srv/GSM/scripts/` 로 돌렸다. venv 를 새로 만드는 첫 차례가 7 초. 이미지를 구워 임시 자리에 `install.sh` 를 돌려
보니 손으로 깐 것과 같았다. 운영 컨테이너가 이 판으로 뜨기 전까지는 손으로 깐 사본이 돈다.

바람의 `fetch_gfs_wind` 는 아직 `feature/wind-data` 에 있다. 그것이 들어오면 `install.sh` 의 `REQS` 에
`requirements-wind.txt` 를 더하고 cron 줄을 `run.sh fetch_gfs_wind` 로 바꾼다.
