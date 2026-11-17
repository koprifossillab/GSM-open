# NASA Earthdata 로그인 뒤의 자료 — 반입 후보

2026-11-17 · 검토(계획이 아니다). 사람이 Earthdata 토큰을 받아 와서, 로그인 뒤라 미뤄 둔 자료를 다시 훑었다.
조사는 두 갈래로 나눴다 — 극지·빙권, 그리고 극지 밖(온 지구·지역 탭)의 고체 지구·지표 자료.
극지가 주력이라 차례도 극지를 앞에 둔다(`docs/극지_자료_후보.md` 의 이어짐).

- 목록은 CMR(`cmr.earthdata.nasa.gov/search/`)에서 로그인 없이 봤다. 받히는지는 토큰을 붙여 **Range 1 KB 만** 30 번 남짓 불러 봤다(1.2–1.5 초 간격, 429 없음)
- **[확인]** 은 요청을 보내 응답(206·첫 바이트)을 본 것, **[추정]** 은 CMR 메타데이터만 본 것
- 조건은 모두 NASA 지구과학 자료 정책(열린 자료, 인용을 바란다) — 따로 적은 것만 다르다
- **이미 붙인 것** — 그린란드 BedMachine v7(IDBMG4, wetherilli 459)

## 받는 길 — 먼저 알아 둘 것

| 자리 | 토큰(Bearer)을 붙이면 | 비고 |
|---|---|---|
| NSIDC 클라우드 `data.nsidc.earthdatacloud.nasa.gov/…-protected/` | **206** — CloudFront 로 한 번 넘긴다 [확인] | Range 가 되니 부분 읽기(`itslive.py` 꼴)도 된다 |
| LP DAAC·ORNL DAAC·PO.DAAC | **206** — 서명된 CloudFront 주소로 [확인] | |
| CDDIS·SEDAC | **206** — 그 자리에서 [확인] | |
| **NSIDC 옛 자리 `daacdata.apps.nsidc.org`**(CMR provider `NSIDCV0`) | **로그인 화면(HTML)** [확인] | **토큰으로는 안 된다.** RGI 7.0(NSIDC-0770)·MOA2014·RAMP·해빙 나이가 여기 있다 |
| GES DISC(MERRA-2) | **403 `EULA Acceptance Failure`** [확인] | 사람이 Earthdata 프로필에서 "NASA GESDISC DATA ARCHIVE" 앱을 한 번 승인 |
| ASF(OPERA) | **403** [확인] | ASF 앱 승인이 빠진 것으로 본다 [추정] |

- requests 는 **다른 호스트로 넘길 때 `Authorization` 을 뗀다** — CloudFront 로 가는 곳은 그게 맞다. 넘김을 여러 번 하는 곳(ASF)은 문이 손으로 따라가야 한다
- 컨테이너 안에서도 맨 `requests` 는 TLS 가로채기에 깨진다 — Django 를 띄워 `verify=settings.CA_BUNDLE` 로 부른다
- 토큰은 DB 옆 파일 하나로만 두고, 저장소·로그·문구에 적지 않는다. 60 일마다 새로 받는다

## 추린 것 — 차례

### 가. 작고, 한 번 받으면 끝나고, 지금의 틀로 굽힌다 — 먼저

| | 무엇 | short_name | 크기 | 어디에 | 굽는 길 |
|---|---|---|---|---|---|
| 1 | **남극 InSAR 접지선 1992–2025** | NSIDC-0498 v2.1 | gpkg 27 MB [확인] | 남극 탭 선, 해(年)로 색 — 접지선이 물러나는 것(스웨이츠·파인아일랜드) | gpkg 는 sqlite3+WKB 라 컨테이너에서 numpy 없이 → 위경도 GeoJSON(`raised`·`antpapers` 꼴) |
| 2 | **남극 경계 — 빙붕(이름)·IMBIE 유역·빙하 유역·접지선** | NSIDC-0709 v2 | 셰이프 여섯, 각 0.5–2 MB [확인] | 남극 탭 면·선, 누르면 빙붕·유역 이름 | 셰이프를 순수 파이썬으로(`geo3al`·`caribmap` 이 이미 읽는다). 3 차 조사가 "ADD 로 갈음" 했지만 **유역과 빙붕 이름은 ADD 에 없다** |
| 3 | **그린란드 바닥 열 상태**(언 바닥·녹은 바닥) | RDBTS4 v2 | nc 17 MB [추정] | 그린란드 탭, BedMachine 레이어군 옆 | 호스트 h5py → `polargrid` 3413(459 가 연 틀 그대로) |
| 4 | **그린란드 출구 빙하 끝, 해마다 1972–2021** | NSIDC-0642 v2 | 셰이프 50, 각 0.3 MB [확인] | 그린란드 탭 선, 해로 색 | 셰이프 → GeoJSON 한 덩이. 2021 에서 멈춘 것이 흠 |
| 5 | **GNSS 관측소 3 차원 속도** | MEaSURES_SESES_prod_3D_stn_velcty_est (CDDIS) | 글 파일 250 KB [확인] | 온 지구·지역 탭(한국·일본 포함) — 수평은 화살, 수직은 색 | `stress.py` 의 R*Tree·막대 그리기를 빌린다. 판 운동이 지금은 모형뿐인데 이것은 **관측** |
| 6 | **EMIT 지표 광물 존재비 0.5°**(방해석·적철석·고령석 등 10 종) | EMITL3ASA v002 (LP) | nc 20 MB [확인] | 온 지구, 광물을 칸으로. 사우디·몽골·호주·미국 탭이 빌린다 | 호스트 h5py → `glim` 같은 0.5° 격자. 먼지 근원지(건조 지대)만 덮는다 |

### 나. 호스트에서 h5py 로 굽는다 — 그다음

| | 무엇 | short_name | 크기 | 어디에 | 비고 |
|---|---|---|---|---|---|
| 7 | **ICESat-2 빙상 고도 변화 2019–** | ATL15 v006 | 10 km 판 합쳐 ~170 MB [확인] | 남극·그린란드·스발바르·아이슬란드 탭, 발산 색 | "얼음이 어디서 얇아지나" 가 지금 없다. 유속·두께와 짝. 1 km 판(남극 12 GB)은 나중 |
| 8 | **GRACE·GRACE-FO 질량 변화 2002–2026** | TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4 (PO.DAAC) | nc 46 MB [확인] | 온 지구 추세(cm/년), 극지 탭 | 두 조사가 모두 꼽았다. 지하수·빙하 뒤 되튐·큰 지진. 실효 해상도 ~300 km |
| 9 | **흙·풍화층·퇴적층 두께 1 km**(Pelletier 2016) | Global_Soil_Regolith_Sediment_1304 (ORNL) | GeoTIFF 6 장, 16–523 MB [확인] | 온 지구, 지역 탭이 빌린다 | 기반암 위 덮개 — 지질도와 바로 짝. **모형**이라고 캡션에 |
| 10 | **남극 빙붕 고도 변화·바닥 녹음 1992–2017** | NSIDC-0792 v1 | nc 2.1 GB [추정] | 남극 탭, 녹는 곳 빨강 | 1·2 와 한 레이어군. 2017 에서 멈춘 것이 흠 |
| 11 | **환북극 열카르스트** | Thermokarst_Circumpolar_Map_1332 (ORNL) | 셰이프 zip 63 MB [확인] | 북극 묶음의 탭들·캐나다·알래스카 | 영구동토 면 자료가 아직 없다. GTN-P 시추공(422)과 같이 |

### 다. 사람이 정할 것이 걸린 것

| | 무엇 | 걸린 것 |
|---|---|---|
| 12 | **RGI 7.0 빙하 윤곽**(NSIDC-0770, CC BY 4.0) — TODOs 의 줄(wetherilli 289) | **토큰으로 안 받힌다**(옛 자리). (가) 사람이 브라우저로 받아 NAS `sources/earth/rgi7/` 에 둔다, (나) Earthdata 사용자명·비밀번호(.netrc)를 컨테이너에 둔다. **(가) 를 권한다** — 지킬 비밀이 늘지 않는다. 극지 둘레 지역(01·03·04·05·07·09·19)만 먼저 |
| 13 | **매일 해빙 농도·눈 범위**(AMSR2 근실시간, NISE_A2, 25 km) | GIBS 마이크로파 해빙이 2025-08-31 에 멈춘 자리를 잇는다(어제까지 있다 [확인]). **HDF4 라 호스트 venv 에 pyhdf 나 GDAL** 을 들이고 매일 cron 하나를 더해야 한다. 평년 해빙 가장자리만 원하면 NSIDC-0051(netCDF4, 2025 년까지)로 갈음 |
| 14 | **ASTER GED 열적외 방출률 → 석영·탄산염·고철질 지수**(AG1km) | 위성으로 본 온 세계 암상, GLiM 보다 자세하다. 다만 1° 타일 2 만 5 천 장·11 GB, 1 초 간격으로 7 시간 받는다 |
| 15 | MERRA-2 먼지(GES DISC)·OPERA 지표 변위(ASF) | 앱 승인부터. 값은 중간 아래 — MERRA-2 는 먼지만 새롭고, OPERA 는 북미만 덮고 20 만 장이다 |

### 라. 낮음 — 적어만 둔다

- 북극 해빙 두께 월별(IS2SITMOGR4, 겨울만)·남극 접지대(NSIDC-0778, 1 에 덧붙이기)·그린란드 SAR 모자이크(NSIDC-0723, 장마다 1.9 GB)
- 산사태·지진 PGA 재해 격자(SEDAC, 2005 년 판)·ECCO V4r4 PO.DAAC 판(NAS 포털이 이미 로그인 없이 준다)·NASADEM 기울기(표고는 Terrarium 과 겹친다)
- EMIT L2B 60 m 장면 — 6 을 해 보고 쓸 만한 지역(사우디 순상지·고비)에만
- 남극 BedMachine v4(Bedmap3 와 겹친다)·환북극 식생 CAVM(지질 뷰어 밖)

## 뺀 것

- **유속 여덟**(NSIDC-0761·0484·0725 등) — ITS_LIVE(433)·GIBS 유속과 겹친다
- **ATL14·SRTM·ASTER GDEM·ICESat-2 지형** — REMA·ArcticDEM·Terrarium 과 겹친다
- **AMSR2 통합 해빙 AU_SI12·25** — 2025-08-31 에 멈췄다. LANCE NRT 판은 우리 서버에서 닿지 않는다 [확인]
- **광학 해빙(VIIRS·MODIS)·HLS 영상** — GIBS 에 이미 있다
- **IceBridge 레이더 측선** — Bedmap3·BedMachine 이 그 측정을 품었다
- **HWSD 토양·MODIS 지표 피복** — 로그인 없는 SoilGrids·ESA WorldCover 가 낫다
- **GEDI·SMAP·GLDAS·해수면** — 지질이 아니거나 날마다 바뀌는 수문·기상이다
- **중력·자력 정적 판** — Earthdata 에 온 세계 판이 없다. EMAG2·EIGEN-6C4 가 이미 돈다
- **NISAR** — 2025-10 에 시작해 아직 이르다

## 사람이 정할 것

1. **가(1–6)를 이 차례로 붙여도 되나** — 작고 조건이 열려 있어 결정 없이 할 수 있는 쪽이다
2. RGI 7.0 — 브라우저로 받아 둘지(권함), 비밀번호를 둘지
3. 매일 해빙(13) — 호스트에 pyhdf·GDAL 을 들이고 cron 을 하나 늘릴지
4. ASTER GED(14) — 7 시간 받기를 할지
5. MERRA-2·OPERA — Earthdata 프로필에서 앱 둘을 승인할지
