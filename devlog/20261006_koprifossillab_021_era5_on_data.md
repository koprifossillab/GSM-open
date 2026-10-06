# 지난 바람 ERA5 를 8 TB 하드로 — 루트 SSD 를 비운다

2026-10-06 · `main`(운영 서버만 고쳤다) · koprifossillab

## 무엇을 보았나

루트 SSD(228 GB)가 94% 였다. 옛 `/var/lib/docker`(52 GB)·시험이 흘린 `/tmp`(20 GB, koprifossillab 020)·옛 타일 캐시 `/srv/GSM/tiles`(664 MB,
캐시를 `/data` 로 옮기기 전의 것 — wetherilli 082)를 지워 60% 가 되었다. `/srv/GSM` 6.7 GB 의 가장 큰 덩이는 **ERA5 2.8 GB** 였다.
ERA5 는 2005-06 ~ 2007-12 의 00 UTC 만 구운 것이라(koprifossillab P02) 더 크지 않지만, 기간을 넓히면 해마다 1.1 GB 씩 는다.

## 어떻게 옮겼나

- `/data/GSM/wind/era5` 로 복사하고(파일 5 665·바이트까지 같은지 보고) `/srv/GSM/db/wind/era5` 를 그리로 가는 **링크**로 바꿨다
- 운영 `/srv/GSM/docker-compose.yml` 에 `/data/GSM/wind/era5:/data/GSM/wind/era5:ro` 를 더했다(고치기 전 사본은 `docker-compose.yml.bak-20261006`).
  **호스트와 컨테이너가 같은 절대 경로**로 붙어야 링크가 양쪽에서 풀린다 — 타일 캐시처럼 다른 자리에 붙이면(`/data/GSM/tiles:/srv/GSM/tiles`)
  `WIND_DIR` 을 바꿔야 하고, 호스트의 `run.sh`(`build_era5_wind`)와 컨테이너가 다른 설정을 갖게 된다
- 컨테이너는 읽기만 한다(`:ro`) — ERA5 를 굽는 것은 호스트의 `run.sh` 다(koprifossillab P02, 005)
- 갈아 띄운 뒤 `earth/wind/` 목록에 era5 944 시점, `earth/wind/era5/20060615/10m.png` 가 200

## 버린 것

- **`WIND_DIR` 을 통째로 `/data` 로** — gfs·gmgsi 는 매시 바뀌는 작은 것(합쳐 140 MB)이고 healthz·주간 백업의 제외 규칙이 `wind/gfs`·`wind/gmgsi`
  경로에 걸려 있다. 큰 것 하나만 옮겼다
- **저장소의 `deploy/docker-compose.yml` 에 같은 줄** — 그 파일은 운영과 다른 틀이다(타일 캐시도 `/srv/GSM/tiles` 를 붙인다). `/data` 가 없는
  자리에서 빈 폴더를 만들게 된다

## 알아 둘 것

- **주간 백업의 ② 구운 것에서 ERA5 가 빠진다** — `weekly_backup.sh` 는 `find -type f` 로 목록을 짓는데 링크는 따라가지 않는다.
  다음 차례에 목록이 달라져 ② 를 새로 뜨고(4.7 GB → 2 GB 남짓), 그 뒤로는 ERA5 가 백업에 없다. 상류(ARCO-ERA5)에서 다시 구울 수 있고
  원본 자리(`/data`)가 같은 하드라, 따로 담지 않았다. 담기로 하면 `GSM-built` 와 따로 한 번 떠 두면 된다
- 기간을 넓히면(`build_era5_wind --from … --to …`) 이제 `/data` 에 쌓인다
