# koprifossillab 024 — 이미지 안의 pip 을 26.1 이상으로 · 서버 디스크가 바뀐 자리

2026-10-23 · `fix/pip-security` · koprifossillab

기능 변경이 없는 고침이다. 판 세션이 다음 판(`release/v<판>`)에 묶어 내도록 브랜치만 넘긴다.
같은 날 서버에 일이 겹쳐 함께 적는다 — ① 보안 점검, ② `/data` 디스크(sda) 고장과
`/data3` 디스크(sdc) 열화, ③ Ubuntu 26.04 로 올린 뒤 깨진 호스트 환경. 판으로 나가는 것은
①뿐이고 ②·③은 이 저장소 밖에서 바뀐 것을 기록한다. **②가 이 저장소에 가장 크게 걸린다 —
`/data/GSM` 이 지금은 다른 디스크에 있다.**

## 1. 보안 — 왜 고치나

2026-10 에 pip·uv·PHP 의 취약점이 잇달아 나와 서버와 컨테이너를 점검했다. 이
저장소의 이미지에 걸리는 것은 **pip** 하나였다.

| 무엇 | 취약점 | 이 저장소 |
|---|---|---|
| pip | CVE-2026-6357 (설치 직후 자기 갱신 확인이 방금 깐 wheel 의 모듈을 임포트해 코드가 돈다) · CVE-2026-3219 (tar 이면서 zip 인 파일을 zip 으로 읽어 다른 파일이 깔린다) · CVE-2026-8643 (entry point 이름으로 scripts 디렉토리 밖에 쓴다) · CVE-2026-13346 (두 번 인코딩한 URL 로 인덱스가 임의 경로에 쓴다) · CVE-2026-1703 (wheel 을 설치 디렉토리 밖 형제 경로에 푼다). 대부분 **26.1 미만** | 이미지 **25.0.1**. 걸린다 |
| uv | CVE-2026-114109 (0.11.15 에서 고침) · CVE-2026-114110 (0.11.6) | 이미지·CI 에 uv 가 없다. 안 걸린다 |
| PHP | CVE-2026-109618 · 109619 ("PHP2Shell", 원격 코드 실행) | PHP 가 없다. 안 걸린다 |

pip 의 결함은 전부 **악성 패키지나 인덱스로 설치할 때** 일어난다. 컨테이너는 돌면서
pip 을 안 부르므로 운영 이미지가 바로 위험한 것은 아니다 — 위험한 자리는 **이미지를
굽는 순간**이다. **pip 은 베이스 이미지를 새로 받아도 안 올라간다** — `python:3.12-slim`
의 pip 은 그 파이썬 판이 묶어 낸 것이라 지금 받아도 25.0.1 이다. 그래서 Dockerfile 에서
직접 올린다(`pip install --upgrade "pip>=26.1"`, 하한만 둔다).

## 2. 디스크 — 자리가 바뀐 것

**`/data` 디스크(sda, 8 TB)가 고장 났다**(SMART 재할당 7,912 · 읽기 불가 1,512 · 파일시스템
비트맵 오류가 07-31 부터 3만 건). **`/data3` 디스크(sdc, 같은 모델)도 열화 중이다** — 재할당이
10-23 하루에 6,136 → 6,272, 요청 한 건에 읽기 1초·쓰기 3초. 두 디스크 다 바꿀 때까지의 임시 배치다.

| 무엇 | 전 | 지금 (2026-10-23) |
|---|---|---|
| **`/data/GSM`** (tiles · wind/era5 · logs · backups · sources) | sda | **`/data3/data-rescue/GSM` 을 `/data` 에 bind mount** (sdc). 경로 `/data/GSM/...` 는 그대로라 compose·스크립트를 안 고쳤다. 고장 난 sda 에서 `rsync -aHAX` 로 옮겼고 파일 111,434 개 · 25,103 MB 가 원본과 같았다 |
| GitHub Actions 러너 `/data/ghrunner` | sda | 같은 bind 로 sdc 에. 소유자 `ghrunner` 를 지켜 옮겼다 · 다시 띄워 "Connected to GitHub" |
| Docker 데이터 루트 | `/data3/docker` (sdc) | **`/data2/docker`** (sdb SSD) · `containerd-snapshotter: false`. 이미지는 Docker Hub 에서 **같은 digest** 로 다시 받았다(`gsm:v1.1.0`) |
| `/data3`·`/data` 마운트 | `relatime` | `noatime` (지금 부팅에서만) |
| NAS 의 03:00 백업 수신(rsync 데몬) | 켜짐 | 꺼짐 — NAS 는 지금 백업이 없다 |

**GSM 에 걸리는 것**

- **`/srv/GSM/docker-compose.yml` 은 판을 `.env` 가 아니라 `GSM_TAG` 환경변수로 받는다.** Docker 를
  옮기며 컨테이너를 다시 만들 때 이것을 안 줘 `latest` 를 찾다 한 번 실패했다 — `GSM_TAG=v1.1.0`
  으로 다시 띄웠다. 손으로 다시 띄울 일이 있으면 `GSM_TAG` 를 꼭 준다
- **지난 바람 ERA5(`/data/GSM/wind/era5`, koprifossillab 021 에서 루트 SSD 를 비우려고 8 TB 하드로 옮긴 것)도 같이 sdc 로 왔다** — 그 하드가 고장 난 sda 였다
- `/data/GSM/tiles/` 는 주간 백업이 NAS(`/nfs/temp-share/GSM/tiles`)로도 보낸다. 다만 `/data/GSM`
  전체는 지금 **열화 중인 sdc 위에만 있다** — `backups/`(다시 못 얻는 것의 tar)는 주간 백업이
  NAS 로도 보내므로 거기서 되살린다
- 구조 작업 동안(10-23 10:15~10:42) 호스트 cron 의 `hourly.sh`(`:40`)와 주간 백업을 잠시
  꺼 두었다 — `/data` 가 읽기 전용이었다. 지금은 원래대로 켜져 있다
- `/srv/GSM/scripts/venv` 는 Ubuntu 26.04(파이썬 3.14)에서 `hourly.sh` 가 스스로 다시 만들었다(10-23 09:40).
  개발용 `~/venv/GSM` 은 uv 가 받은 파이썬 **3.12.15** 로 다시 만들어 같은 판의 패키지를 깔았다(옛 것은
  `~/venv/GSM.py312-bak`) — 26.04 에 3.12 가 없어 깨졌었다

## 확인

- `docker build -f deploy/Dockerfile.web` 로 구운 이미지 안에서 `pip --version` → **26.2.2**
- 로컬 시험 `manage.py test viewer --parallel 8` 2,290 개 OK (skipped 17) · 개발 venv(3.12.15)
- CI 는 판 PR 이 처음 본다
