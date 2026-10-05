# HANDOFF

이 문서는 **지금 어디까지 왔고 다음이 무엇인지** 한 곳에서 답한다.
왜 그렇게 했는지는 `devlog/`, 무엇이 언제 붙었는지는 `CHANGELOG.md`.

마지막으로 손본 날: **2026-10-04**

## 작업 방식 (2026-09-30 부터)

**브랜치** `main` = `0.62.0`(2026-10-05 배포). 코드 작업은 각자 자기 계정에서 `feature/<기능 이름>` 브랜치를 `main` 에서 만들고, 끝나면 PR 을 만든다.
**PR 병합과 판 올리기·배포는 판 세션(gsm-31)이 한다** — 다른 세션은 PR 을 열고 알린다. 판은 몇 PR 이 모이면 따로 올린다. 문서만 고치는 것은 `main` 에 바로. devlog 는 글쓴이마다 번호를 센다 — CLAUDE.md "커밋과 PR"·"devlog",
[devlog/README.md](devlog/README.md). WegenersDream 과 같은 규약이다.

## 한 줄

**배포했고, 인증키로 돈다.** `http://paleolab/GSM/` 에 서 있다 (짧은 주소 `/geomap/`).
2026-09-27 에 키가 들어와 임시 스위치를 껐다. 타일·범례는 `/openapi/wms` +
키로, **속성만 GeoServer 로** 받는다 — `/openapi/wms` 가 `GetFeatureInfo` 를
막아 두었기 때문이다 (devlog 006).

키는 `/srv/GSM/db/kigam_key` 에 있다. `/srv/GSM/.env` 는 root 의 것이라 못
고쳐서 설정을 **DB 옆 파일**로도 읽게 해 두었다 —
`kigam_key`·`allowed_hosts`·`dev_direct_wms`·`secret_key`.

## 지금 서 있는 것

판마다 무엇이 붙었는지는 `CHANGELOG.md`, 왜 그랬는지는 괄호 안의 devlog 다.

- **지역 스물과 묶음 넷** — 한국(기본)·일본·중국·대만·그린란드·스발바르·얀마옌·북극해·노르웨이·핀란드(한 탭)·영국·아일랜드·프랑스·독일·스페인·
  콜롬비아·브라질·페루·아르헨티나·우루과이·남극, 묶음 탭 동아시아·북극·유럽·남미 (016·017·021·024·076, wetherilli 136·140·143·147·188·191·195·196).
  화면 투영은 3857·3413·3031 이다. 지역 탭에는 화석 산지·화산·지진·고생태 점도 뜬다(wetherilli 185)
- **상류로 나가는 문 서른여섯** — 목록은 CLAUDE.md "구조" 의 끝. 문이 아닌 것(우리 디스크의 파일을 굽거나 읽는다)도 거기 있다
- **정적 판** — 연구소 밖 `https://koprifossillab.github.io/GSM-open/`. 보는 사람이 KIGAM·VWorld 키를 각자 넣는다. 판 세션이 판마다
  `deploy/publish_pages.sh` 로 굽고, 소스는 `deploy/publish_open.sh` 로 GSM-open 에 민다 (wetherilli P11·149·162·174)
- **공유 링크** — 지역 탭·온 지구·달·화성·수성의 "링크" 단추. 주소의 해시에 자리·레이어·배경을 담고, 받은 쪽의 기억은 덮지 않는다 (wetherilli 189)
- **달·화성·수성** — 아이콘의 숨은 차림에서 `/GSM/moon/`·`/GSM/mars/`·`/GSM/mercury/`. 둥근 몸(Cesium)과 평면(OpenLayers)을 오가고,
  위도 65° 너머는 극 평면이다 (036·038·052·058·065). Trek 판 목록은 씨앗 `data/<몸>_trek_layers.json` (060).
  화성에는 크레이터 38 만 개·옛 지질도 I-1802 와 지역도·주룽 경로를 우리가 굽는다 (066–068, wetherilli 079).
  달 SPA 지질도는 Trek 의 그림에 원본 GeoTIFF 의 속성을 붙인다 (wetherilli 081). 달 지형은 LOLA 256 ppd(가까이서는 극 5 m·NAC DTM, wetherilli 107), 극 평면에서는 Trek 판의 극지 짝을 받는다, 잰 선의 높이 그래프, 켠 값 판의 누른 자리 값 (wetherilli 083·085·100·103).
  화성도 극지 짝과 표고 판의 누른 자리 높이를 받는다(wetherilli 192). 수성은 USGS 1:500만 도폭 합본을 우리가 굽는다(wetherilli 137·144·194).
  세 화면 모두 높이 그래프 밑에 지질 띠(wetherilli 180)
- **온 지구** — 같은 숨은 차림에서 `/GSM/earth/`. 둥근 지구에 Macrostrat 지질도 (wetherilli 086). 시간 축과 그때의 지구,
  누른 자리의 그때의 자리(PALEOMAP 2016)와 ETT 링크 (wetherilli 087·088·091), 옛 해안선·화석 산지·지각 두께·지명·빙상 가장자리
  (wetherilli 097·098·101·102·104), 홀로세·플라이스토세 화산·지진·고생태 산지·맨틀 슬랩 (wetherilli 106·134·138·139·194), 높이 그래프(186)
  **바람** — 지금(GFS)·지난(ERA5 2005-06 ~ 2007-12), 지상 10 m·250 hPa 를 입자로. 지금의 바람은 앞뒤 두 장(분석·예보)을 지금 시각으로 섞는다 (koprifossillab P02·003·007·008).
  **해류** — ECCO2 표층을 입자로, 달마다 한 장 1992–2019(`build_ecco2 --monthly` 로 사람이 굽는다, `<DB 옆>/ocean/`). 지금의 해류는 아직 없다 (koprifossillab 014·015).
  **구름** — 같은 시각 축으로 전체·하층·중층·상층 구름량 (koprifossillab P03·011). **위성 구름** — NOAA GMGSI 적외선 합성,
  한 시간마다 가장 새 장 (koprifossillab 012)
- **3D** — 도구 막대의 단추로 늘 연다 (059). 한국·일본·북극·남극·유럽·남미 지형과 지질, 점묶음 (wetherilli 187·188)
- **영어판** — 설정의 "언어 · Language". 화면의 글을 고치면 `viewer/i18n.py` 에 영어도 적는다 (008)
- **연구실 내부용** — geo3al·phyloserver·한반도 지질도·kopri. 밖에 열 때 `GSM_PUBLIC=1` 로 내린다 (025·029·053)

### 운영에 두는 파일

모두 `/srv/GSM/db/` 아래다. 저장소에 두지 않고, 원본은 NAS `N:\GSM\sources\` 에 있다.

| 자리 | 무엇 | 채우는 법 |
|---|---|---|
| `geomap/` | 남극 GeoMAP gpkg (490 MB) | 파일을 둔다 (018) |
| `npolar/` | 얀마옌 지질도 GeoJSON | 파일을 둔다 (022) |
| `usgs/geo3al/` | 중국 geo3al `{shp,dbf,prj}` | 파일을 둔다 (025) |
| `peninsula/` | 한반도 지질도 음영판·민판과 잘라 둔 타일 | `manage.py build_peninsula [--layer plain]` (027·028) |
| `moon/` | 달 원도 6 장 sqlite, SPA 지질도 원본 `spa_geomap_iqbal2026.tif`(112 MB) | `manage.py build_moon_originals <zip>` (039). SPA 는 Zenodo `GeoMap.tif.zip` 을 풀어 이름만 바꿔 둔다 (wetherilli 081) |
| `ibcso/` | IBCSO 타일·수치 격자·TID | `manage.py build_ibcso` (047·051·071) |
| `mars/` | 화성 크레이터·옛 지질도 sqlite | `manage.py build_mars_craters <zip>`·`build_mars_originals <zip>` (067·068) |
| `earth/` | 옛 해안선 `paleocoastlines_v7.json`, 화석 산지 `pbdb.sqlite`, 화산 `gvp_volcanoes.json`(·`gvp_pleistocene.json`), 지진 `quakes.sqlite`, 고생태 `neotoma.sqlite`, 맨틀 `mantle/` | `build_paleocoastlines`·`fetch_pbdb`·`fetch_gvp`·`fetch_quakes`·`fetch_neotoma`·`build_mantle` (wetherilli 097·098·106·134·138·139·194) |
| `mercury/` | 수성 지질도 sqlite | `manage.py build_mercury_geology <zip>` (wetherilli 144) |
| `wind/`·`ocean/` | 바람·구름(GFS·GMGSI·ERA5)·해류(ECCO2) PNG | 호스트 cron 의 `hourly.sh`, 지난 것은 사람이 `build_era5_wind`·`build_ecco2` (koprifossillab P02·005·014) |
| `kigam_data/` | KIGAM `/openapi/data` 의 시료·분석·주제도·조사 | `manage.py fetch_kigam_data` (wetherilli 169) |
| `kopri/` | 극지연구소 목록·상세 | `manage.py fetch_kopri` — 가끔, 새 것만 받는다 (053) |
| `kigam50k/` | KIGAM 5만 지질도 층리·엽리·절리·단층 등 19 레이어(WFS, 2026-09-30). 0.25.1 부터 자세 기호의 커서·팝업이 읽는다 | 지금은 손으로 받아 둔 `raw/20260930/`. 받는 명령은 jikhanjung P01 |

그 밖에 가끔 돌리는 것 — `data_status`(위 표의 파일마다 있는지·크기·고친 날·원본 판, wetherilli 312), `fetch_grportal`(그린란드 시료·NPI 점·지명), `verify_layers --probe-info`
(`/openapi/wms` 가 속성을 열었는지), `upstream_stats`(얼마나 묻는지).

## 돌려보는 법

```bash
python -m venv ~/venv/GSM && . ~/venv/GSM/bin/activate
pip install -r requirements.txt
cp .env.template .env            # 아래 "지금의 .env" 를 본다
cd web && python manage.py migrate && python manage.py seed_catalog
python manage.py runserver
```

`http://127.0.0.1:8000/GSM/`.

### 지금의 .env

로컬에서도 키를 채우고 스위치를 끈다. 키가 없으면 `GSM_DEV_DIRECT_WMS=1` 로
돌려볼 수 있다 (화면 맨 위에 띠가 뜬다).

```
GSM_KIGAM_KEY=<받은 키>
GSM_DEV_DIRECT_WMS=0
```

둘의 갈래는 CLAUDE.md 의 "두 개의 상류 주소".

## 무엇이 확인됐나

2026-09-23 에 임시 스위치로, 2026-09-27 에 인증키로 직접 받아본 것들이다.

| | |
|---|---|
| 타일 | 25만 지질도 400×300 PNG 122 KB — 그려진다 |
| 클릭 속성 | 지질시대·도폭·지층명·지질기호·대표암석 — **상류가 한국어 이름으로 준다** |
| 범례 | 223×5218 PNG 48 KB |
| 카탈로그 | `geoOpen` 61 개, 레이어군 8 갈래 |
| 점묶음 | UTF-8 CSV·CP949 CSV·GeoJSON 올라간다. 위경도 열 없으면 까닭을 말한다 |
| 좌표 | 십진도·도분초 오가고, 찍어서 이동하고, 눌러서 복사한다 |
| 시험 | 1 370 개 다 돈다 (`manage.py test viewer`, 2026-10-04). 휴대폰 화면은 CI 의 "휴대폰 화면" job(`test_mobile`, 모든 지역 탭) |
| 오픈API | 키로 61 개 전부 그려진다. 범례도 된다. **속성은 막혀 있다** (006) |
| 배포 | `http://paleolab/GSM/` 200. 짧은 주소 `/geomap/` 301 |
| 배경지도 | VWorld `Base`·`Satellite`·`Hybrid` 200. 자리 차례는 `z/y/x` (003) |

## 무엇이 아직 아닌가

- **속성이 문서에 없는 주소에 기대고 있다.** `/mgeo/geoserver/wms` 가 닫히면
  클릭 속성이 멈춘다 (타일은 그대로 돈다). 그때는 `kigam.DIRECT_REQUESTS` 를
  보고, `/openapi/wms` 가 열렸는지 다시 찔러본다
- 호출 제한의 실제 수치를 모른다. 문서는 "지나치게 잦은 호출" 이라고만 적었다.
  타일 캐시를 둔 것이 이 때문이다 (브라우저 쪽 하루, 디스크 쪽은 지우지 않고 3 년마다 다시 묻는다)
- 운영 DB 의 대조는 2026-09-27 에 끝났다 (KIGAM 61/61). 이제 모든 상류를 본다 — 개발 기계에서 2026-10-05 에 670 개 가운데
  그림 456·빈 그림 35·오류 6·건너뜀 173 (wetherilli 298). 운영에서 돌릴 때는 20 분 남짓
  `docker exec -w /app/web gsm-web-1 python manage.py verify_layers --redo`
- **사용자가 정할 것은 이슈 #153 에 모은다** — 다음 대륙(북미·아프리카), 정적 판의 3D, 남미 1:500만(CGMW)·우루과이(DINAMIGE)의 이용 조건,
  VWorld 지오코더 결과의 저장, PGC 음영·Trek 영상의 서버 캐시, KIGAM 자료를 지도에 올리는 범위 따위. 세션은 갈림길을 만나면 거기 댓글을 남기고
  다른 일로 넘어간다

## 알아두면 좋은 것

### 상류 문서를 믿지 않는다

안내 페이지의 레이어 목록에 틀린 것이 있다 — 지화학도 12 종이 전부 바나듐으로,
변성암·광상 동위원소가 심성암과 같은 이름으로 적혀 있고, 좋은물지도 15 종은
아예 빠져 있다. 그래서 카탈로그를 표로 두고 `GetCapabilities` 에서 채운다.
자세한 것은 devlog 001.

### KOPRI 망이 TLS 를 가로챈다

`data.kigam.re.kr` 의 인증서 체인 끝이 `CN=KOPRI SSL` 이다. 그 루트는 시스템
꾸러미에만 있고 `requests` 가 보는 certifi 에는 없어서, 그냥 두면 **상류 요청이
전부 `CERTIFICATE_VERIFY_FAILED` 로 멈춘다.** `settings._default_ca_bundle()` 이
시스템 꾸러미를 찾아 쓰고, 컨테이너는 `deploy/ca/` 를 이미지에 넣는다.
ForGIA `deploy/ca/README.md` 가 같은 것을 먼저 겪었다.

**망 밖에서 쓰려면** `deploy/ca/` 를 비우면 된다.

### OpenLayers 를 저장소에 담았다

`web/viewer/static/viewer/vendor/`. CDN 에서 부르지 않는 까닭은 위의 TLS
가로채기와, 형제 저장소(DiaRUGA·ForGIA)에 바깥 링크가 하나도 없다는 집 규칙
둘이다. 판을 올릴 때는 `vendor/README.md` 를 함께 고친다.

### 브라우저는 인증키를 모른다

타일은 `./wms/`, 속성은 `./featureinfo/`, 범례는 `./legend/` 로 부르고, 키는
Django 가 붙인다. `kigam.clean_params()` 가 브라우저가 보낸 `key` 를 **버린다** —
시험(`test_kigam.py`)이 그것을 지킨다.

## 배포한 자리에서 알아둘 것

`/srv/GSM` 은 배포한 사람(root)의 것이라 **`.env` 도 `docker-compose.yml` 도
못 고친다.** 쓸 수 있는 것은 `db/` 뿐이다(고칠 때는 사람이 sudo 로). 타일 캐시는 2026-09-30 에
`/data/GSM/tiles`(8 TB 하드)로 옮겼다 — 컨테이너 안의 경로는 그대로 `/srv/GSM/tiles` 다 (wetherilli 082). 서버 DNS 가
kopri.re.kr 을 못 찾아 compose 에 KPDC 주소를 `extra_hosts` 로 박아 둔다 — 서버 DNS 가 고쳐지면 지운다 (wetherilli 095). 2026-09-23 에 이것이
세 번 걸렸다 — 빈 `SECRET_KEY` 로 기동 실패, `ALLOWED_HOSTS` 에 `paleolab` 이
없어 400, 그리고 임시 스위치.

그래서 설정을 **DB 옆 파일**로도 읽는다.

| 파일 | 하는 일 |
|---|---|
| `secret_key` | 없으면 entrypoint 가 만든다 |
| `allowed_hosts` | 들어와도 되는 이름. 한 줄에 하나 |
| `kigam_key` | 상류 인증키 |
| `dev_direct_wms` | `1` 이면 임시 경로로 간다 |
| `vworld_key` | 배경지도 열쇠. 있으면 고르개에 VWorld 가 오른다 (넣어 두었다) |
| `public` | `1` 이면 밖에 연 뷰어 — 연구실 내부용 레이어를 내린다 (029). 지금은 없다 |

환경변수가 있으면 그쪽이 이긴다. 파일은 없어도 된다.

**파일은 `640` 으로 둔다** (`chmod 640`). 컨테이너는 uid 1000 으로 돌고 파일
주인은 1006 이라, 무리(gid 1000)에게 읽기를 열어야 한다. 2026-09-27 에
`kigam_key` 를 `600` 으로 만들었더니 컨테이너가 못 읽어 "인증키가 없다" 띠가
떴다. 설정은 기동할 때 읽으므로 고친 뒤에는 `docker restart gsm-web-1`.

### 백업

매주 월요일 01:40 `/srv/GSM/scripts/weekly_backup.sh`(원본 `deploy/scripts/`) — 다시 못 얻는 것(GSM.db·kopri·kigam50k)과 구운 것을 `/data/GSM/backups`
와 NAS 에, 캐시·원본은 거울로. 그 뒤 `fetch_kopri`. 무엇이 어디에 있고 어떻게 되살리나는 [docs/백업.md](docs/백업.md)
(koprifossillab 001). 2026-09-30 에 paleoadmin 의 crontab 에 붙였다(`deploy/host/crontab.GSM`) — 첫 차례는 10-05(월).
결과는 DB 옆 `backup_status.json` 에도 적혀 **`/GSM/healthz/` 가 읽는다** — 멈췄거나 여드레 넘게 없으면 `degraded`
(koprifossillab 002).

### cron

**cron 은 저장소를 부르지 않는다** — `/srv/GSM/scripts/` 의 사본을 부른다. 컨테이너가 뜰 때 이미지의 `deploy/scripts/`
와 앱 코드 사본(`app/`)을 거기 깔고(`install.sh`), 파이썬 일은 `run.sh <관리 명령>` 이 전용 venv(`scripts/venv`)로 돌린다.
venv 는 requirements 가 바뀌면 스스로 다시 만든다. cron 은 **두 줄**이다 — 주간 백업(월 01:40)과 **매시 받기**(매시 :40,
`hourly.sh`, koprifossillab 013). `hourly.sh` 가 차례로 부르는 일: 지금의 바람·구름(`fetch_gfs_wind` → `db/wind/gfs/`, 판마다 분석과
+12 시간까지의 예보, 48 시간만), 위성 구름(`fetch_gmgsi` → `db/wind/gmgsi/`, 스물네 장만), 아라온호 위치(`fetch_araon` →
`db/kopri/araon.jsonl`). 일마다의 결과는 `db/hourly_status.json` 에 남고 **`/GSM/healthz/` 가 읽는다** — 기록이 2 시간 넘게 멈추거나,
한 일이 실패하거나, GFS 판이 12 시간·위성 장이 3 시간을 넘으면 `degraded`. 로그는 `/data/GSM/logs/hourly.log`.
지난 바람·구름(`db/wind/era5/`, 944 날)은 2026-10-01 저녁에 굽기 시작했다(바람 `/data/GSM/logs/era5_build.log`, 이어서 구름
`era5_clouds.log`) — 다 구우면 다시 구울 일은 기간을 늘릴 때뿐이다. 판을 올리기 전에 고친 것을 돌려 보려면 저장소에서
`deploy/scripts/install.sh . /srv/GSM/scripts` (koprifossillab 005). 운영 compose 에는 `scripts` 마운트를
2026-10-01 에 더했다 — 2026-10-01 에 v0.34.0 으로 다시 떠, 지금 도는 것은 이미지가 깐 사본이다.

### 판을 올릴 때

- 기동할 때 이주와 씨앗(`seed_catalog`)이 저절로 들어간다
- 새 파일이 드는 판이면 **판보다 먼저** 위 "운영에 두는 파일" 자리에 둔다
- 새 상류가 생기면 운영 장비에서 그 주소로 나갈 수 있는지 먼저 본다 (KOPRI 망의 TLS 는 위)
- 올린 뒤 `deploy/host/smoke.sh`

## 걸린 것 — 없음

지금 막힌 것은 없다.
