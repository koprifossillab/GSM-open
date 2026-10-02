# ECCO2 해류를 온 지구 화면에서 흐르게 — 검토

2026-10-01 · koprifossillab · **검토다. 계획이 아니다** — 하기로 정해지면 devlog 에 P 문서를 쓴다(CLAUDE.md "devlog")

사람이 "ECCO2 데이터셋에 대해 알아봐" 라고 했다. 이어서 NASA SVS 의 ECCO2 묶음
(`svs.gsfc.nasa.gov/search/?datasets=707`)처럼 **동적으로** 그리려면 무엇이 필요한지 물었다. 이 문서는 그 두 답을
모은 것이다. 숫자 가운데 **잰 것과 셈한 것을 가른다** — 셈한 것에는 "셈" 이라 적는다.

## 1. ECCO2 는 무엇인가

**Estimating the Circulation and Climate of the Ocean, Phase II**(NASA JPL·MIT). MITgcm 해양–해빙 모델에 관측을 맞춘
전 지구 **상태 추정**이다. 맞춘 관측은 고도계(Topex/Poseidon·Jason-1/2), GRACE 해저압, QuikScat 바람 응력, AMSR-E 해수면
온도, SSM/I 해빙, Argo·계류 수온·염분이다.

- **맞춘 방식은 Green 함수다** — 민감도 실험(cube20–cube90)을 거듭해 매개변수·초기·경계 조건을 고르고, 그 최종 해가
  **cube92** 다. ECCO v4 처럼 adjoint 로 처음부터 끝까지 맞춘 해가 아니라 **열·염분 수지가 닫히지 않는다.** ECCO 그룹도
  이제 ECCO2 를 "Legacy Product" 로 두고 V4 를 권한다
- 모델 격자는 정육면체 구(cube-sphere, cs510), 18 km 남짓 — 와류가 겨우 보이는 해상도다. 깊이 50 층, 맨 위 10 m 에서 맨
  밑 456.5 m 두께까지, 최대 수심 6 150 m
- 배포본은 **1/4° 위경도 격자로 옮긴 netCDF** 다(`cube92_latlon_quart_90S90N`, 1440×720, 90°S–90°N)

| 갈래 | 변수 | 평균 | 파일 이름 |
|---|---|---|---|
| 3D | `THETA`(수온)·`SALT`(염분)·`UVEL`·`VVEL`(동서·남북 유속), 연직 유속 | **3 일** | `THETA.1440x720x50.19920102.nc` |
| 2D | `SSH`(해수면 높이)·`PHIBOT`(해저압), 혼합층 깊이, 표면 열·담수 플럭스, 바람 응력, 해빙 | 하루 | `SSH.1440x720.19920101.nc` |

**기간은 출처마다 다르다** — NAS 포털의 readme 는 1992-01-01 ~ 2019-03-31, ECCO 그룹 제품 목록은 1992–2023, 다른 색인은
하루치를 2024-12 까지로 적는다. 이어 붙여 온 것으로 보이나 **끝 날짜는 받는 곳의 목록을 직접 봐야 한다.**

조건 — NASA 자료라 쓰는 데 제한이 없다. 인용은 Menemenlis et al. (2008, *Mercator Ocean Quarterly Newsletter* 31).

## 2. 받는 길 — 2026-10-01 에 이 서버에서 찔러 본 것

| 길 | 결과 |
|---|---|
| **ECCO Drive** `ecco.jpl.nasa.gov/drive/files/ECCO2/cube92_latlon_quart_90S90N/` | 302 → **Earthdata 로그인.** wget 으로 받을 때는 Earthdata 비밀번호가 아니라 ECCO Drive 가 내주는 **WebDAV 비밀번호**를 쓴다 |
| **NASA NAS 데이터 포털** `data.nas.nasa.gov/ecco/cs_510/` | **로그인 없이 받힌다**(같은 날 다시 찔러 봄, [ECCO_V4_해류.md](ECCO_V4_해류.md) §2). `eccodata/…` 꼴 주소는 500 을 주고, 목록의 링크 꼴(`/ecco/cs_510/UVEL.nc/UVEL.1440x720x50.19920105.nc`)이 맞다. 처음 찔렀을 때 못 읽은 것은 주소 꼴이 틀려서였다 |
| 하와이대 APDRC 거울 | 문서 페이지가 404 |

옛 FTP(`ftp://ecco.jpl.nasa.gov/ECCO2/…`, 2018 년 안내)는 지금 HTTPS 의 ECCO Drive 로 옮겨 갔다.

## 3. 양 — 셈

| | 한 장 | 30 여 년 |
|---|---|---|
| 3D 변수 하나(1440×720×50 float32) | **207 MB**(셈, 압축 전) | 3 일마다 4 000 장 남짓 → **0.8 TB 안팎** |
| 2D 변수 하나(1440×720 float32) | 4 MB(셈) | 하루마다 → 50 GB 안팎 |
| **표층 유속 u·v 한 시점** | 8 MB(셈) | Perpetual Ocean 기간(2.5 년, 300 시점) → 2.4 GB |

파일이 netCDF 압축을 썼는지는 아직 모른다. **통째로 받는 것은 무리다** — 쓸 층과 기간을 골라 받는다.

## 4. SVS 의 ECCO2 묶음은 무엇이었나

SVS 검색 API(`/api/search/?datasets=707`)로 읽었다. 묶음은 스무 편 남짓이다. 대표는 **Perpetual Ocean**(2011, SVS 3827)과
그 후속 **Perpetual Ocean 2**(2024–2025, 5505·5479 등)다.

- 2005-06 ~ 2007-12 의 **표층 해류를 흐르는 선**으로 그렸다. ECCO2 는 모든 깊이의 흐름을 주지만 표층만 썼다
- 밑에 **해저 지형을 어둡게** 깔았다(GTOPO30·ETOPO, 육지 20 배·해저 40 배 과장). 그 덕에 선이 떠 보인다
- Perpetual Ocean 2 는 선에 **600 m 아래 수온이나 염분 색**을 입혔다(600 m 위는 흰색)
- **미리 렌더링한 영상이다** — 브라우저에서 도는 것이 아니다. Science on a Sphere 용 등장방형 판도 따로 낸다

## 5. 동적으로 그리려면 필요한 것

### 5.1 자료 — 표층 `UVEL`·`VVEL`, 색을 입힐 거면 `THETA`

맨 위 한 층(또는 몇 층)만 쓴다. 3D 변수라 **3 일 평균**이다. 3D 파일은 한 장이 207 MB 라, 첫 층만 쓰려고 통째로 받으면 쓰는
양의 25 배를 받는다. **OPeNDAP 으로 첫 층만 잘라 받을 수 있는지가 가장 먼저 볼 것이다**(§7).

### 5.2 굽기 — 유속을 PNG 텍스처로 (서버, `manage.py build_ecco2` 같은 명령)

시점마다 u·v 를 줄여 PNG 한 장에 담는다 — R=u, G=v, A=육지 가리개. 되돌릴 최솟값·최댓값은 곁의 JSON 에. earth.nullschool·
windy·mapbox `webgl-wind` 가 쓰는 꼴이다. 8 비트면 한 장에 1–2 MB(셈)라 300 시점이 수백 MB 다. 느린 해류의 결이 8 비트로
뭉개지면 16 비트(R·G 두 칸씩)로 간다.

CLAUDE.md 의 틀로는 **PBDB·KPDC 처럼 모아 두고 그린다**:

- 상류로 나가는 길은 **새 문 하나**(`ecco.py`) — `requests` 를 쓰는 자리가 열셋에서 열넷이 된다. 받기는 사람이 명령을 부를
  때만 간다. 화면이 부를 때 상류를 타지 않는다
- 구운 것은 `<DB 옆>/ecco2/`(`GSM_ECCO2_DIR`). 저장소에 두지 않는다. 파일이 없으면 그 레이어 자리에 안내가 뜬다
- netCDF 를 읽는 라이브러리(netCDF4·h5netcdf·scipy 가운데 하나)는 **굽는 쪽만** 쓴다 — `build_crust` 가 h5py 를 그렇게
  쓴다. 제품은 PNG 와 JSON 만 낸다
- Earthdata 의 WebDAV 비밀번호는 `GSM_EARTHDATA_*` 나 `<DB 옆>/earthdata` 로 들인다. **저장소에 적지 않는다.** 백업
  (`weekly_backup.sh`)의 비밀 목록에도 더한다

### 5.3 화면 — WebGL 입자 흐름

입자 수만~수십만 개의 자리를 텍스처에 담는다. 프레임마다 셰이더가 유속 텍스처를 읽어 자리를 옮기고, 앞 프레임을 조금씩
흐리게 겹쳐 꼬리를 만든다. 수온 텍스처를 같이 읽어 색을 입히고, 두 시점의 텍스처를 섞어 3 일 간격을 매끄럽게 잇는다.

온 지구 화면(`earth.js`)에는 **입자 코드가 아직 없다** — 지금은 Cesium `ImageryLayer` 와 OpenLayers `WebGLTile` 로 타일만 얹는다.

| 자리 | 길 | 어려움 |
|---|---|---|
| 평면(4326 경위도) | OpenLayers 위에 WebGL 캔버스 하나. ECCO2 위경도 격자와 화면이 같은 꼴이라 옮김이 거의 없다 | 쉽다 |
| 구(Cesium) | 입자를 그린 캔버스를 프레임마다 영상 레이어로 덮거나, Primitive 를 직접 짠다(공개된 `cesium-wind-layer` 류) | 중간 |
| 극 평면(3413·3031) | 셰이더 안에서 투영을 옮긴다 | 나중 |

`webgl-wind`(ISC)처럼 AGPL 과 어울리는 것은 옮겨 와도 된다 — 전문을 `docs/licenses/` 에, README 에 한 줄(CLAUDE.md "라이선스").

### 5.4 시간 고르개 — 날짜 축이 따로 하나

온 지구 화면의 시간 축(`?age=`, wetherilli 091)은 **지질 연대(Ma)** 다. 1992–2024 의 날짜는 거기에 얹을 수 없다. 해양
레이어를 켰을 때만 뜨는 날짜 막대와 재생·멈춤이 따로 있어야 한다. 화면의 글이 늘어나니 영어도 같은 커밋에(CLAUDE.md "영어판").

### 5.5 밑그림 — 어두운 해저

SVS 가 그렇게 보이는 것은 어두운 바다 밑 지형 덕이 크다. 온 지구 화면이 이미 받는 표고(AWS Terrarium)를 바다 쪽만
어둡게 칠하면 된다 — 새 자료가 들지 않는다.

## 6. 두 길의 견줌

| | 동적(§5) | SVS 처럼 미리 굽기 |
|---|---|---|
| 하는 일 | 텍스처만 굽고 화면이 그린다 | 서버가 날짜별 프레임을 렌더링해 영상·타일 묶음으로 |
| 디스크 | 수백 MB(셈) | 해상도·길이에 따라 수 GB |
| 확대·회전 | 그대로 고와진다 | 확대하면 거칠다 |
| 날짜·깊이·색 바꾸기 | 화면에서 | 다시 굽는다 |
| 브라우저 부담 | GPU 를 쓴다. 휴대폰에서 입자를 줄여야 할 수 있다 | 없다 |
| 모양 | 셰이더를 다듬어야 SVS 에 닿는다 | SVS 에 가장 가깝다 |

**동적인 쪽이 낫다고 본다** — 자료가 작고, GSM 의 다른 레이어처럼 확대·회전·날짜가 산다.

## 7. 정하기 전에 확인할 것

- [x] ~~Earthdata 계정이 있는가~~ — **필요 없다.** NAS 포털이 로그인 없이 준다
- [x] **첫 층만 잘라 받을 수 있는가** — **된다.** NAS 포털이 Range 를 받고(206), 파일이 압축 없는 netCDF classic(`CDF\x01`,
  `UVEL` 한 장 207 369 800 바이트)이라 첫 층(1440×720 float32, 4 MB)의 자리가 머리에서 셈으로 나온다. OPeNDAP 이 없어도 된다
- [x] **배포본의 끝 날짜** — NAS 의 `UVEL` 은 1992-01-05 ~ **2019-03-29**, 3 일마다 2 939 장
- [x] **netCDF 가 압축돼 있는가** — 아니다(classic). 굽는 쪽은 표준 라이브러리만으로 읽을 수 있다
- [ ] ECCO Drive 의 호출 제한 — KIGAM 처럼 **재려고 두드리지 않는다**(devlog 010). 받기는 천천히, `upstream_stats` 로 본다

## 8. 사람이 정할 것

- **기간** — Perpetual Ocean 과 같은 2005-06 ~ 2007-12 한 토막부터인가, 30 여 년 전체인가
- **깊이** — 표층 하나인가, 몇 층(예: 600 m)을 골라 보게 하는가
- **색** — 속도 크기인가, 수온·염분인가
- **ECCO2 인가 ECCO V4r4 인가** — 보기에는 ECCO2(1/4°)가 곱다. 수지까지 따질 거면 V4r4(llc90, 1° 남짓, PO.DAAC·클라우드)가
  맞다. 화면에 흐름을 보이는 것이 목적이면 ECCO2 다

## 9. 하기로 하면 — 단계 (안)

1. 문(`ecco.py`)과 받기·굽기 명령 — 한 토막(2005-06 ~ 2007-12)의 표층 u·v 를 PNG 로
2. 평면(4326)에 입자 흐름 — 한 시점, 속도 크기로 색
3. 날짜 막대와 재생 — 시점 사이를 섞어 매끄럽게
4. 수온 색, 어두운 해저 밑그림
5. 구(Cesium)로 옮기기

단계마다 브랜치·PR·devlog 하나(CLAUDE.md "커밋과 PR").

## 10. 한 장 구워 본 것 (2026-10-01)

사람이 "한 장 먼저 만들어 보자" 라고 했다. 2006-06-17(3 일 평균)의 표층(5 m) `UVEL`·`VVEL` 을 NAS 포털에서 Range 로 첫 층만
받았다 — 4 147 200 바이트씩 둘. 굽는 것은 scratchpad 에서 했고 저장소·운영에는 아직 아무것도 두지 않았다.

- **머리에 적힌 시작 자리는 변수마다 다르다** — `UVEL` 9 800, `VVEL` 9 804(이름이 길다). 머리를 읽고 받아야 한다
- **유속 파일의 경도가 머리와 다르다.** 머리는 `LONGITUDE_T` 를 0.125° 부터라 적지만, 자료는 **107.5° 남짓 밀려 있다**(동경
  110° 언저리가 첫 열). 처음 구운 미리보기에서 아프리카가 서경 90° 에 서 있어 알았다. 같은 날의 `SST`(2D, 경도가 머리와
  맞다)의 육지와 맞춰 보니 `UVEL` 은 **430 열**, `VVEL` 은 **429 열**, 둘 다 위도 **한 줄** 밀렸다 — 유속이 칸 가장자리에 놓인
  엇갈린 격자라 반 칸이 갈린다. 1996·2012·2018 의 `UVEL` 도 같았다. 남는 어긋남(2 % 남짓)은 해안 한 칸이다
- 육지는 0 이다(FillValue 가 아니다). 남극 안쪽 두 줄(−89.875·−89.625)에는 쓰레기 값(10 m/s 넘게, 1e35 까지)이 있어 버린다.
  그 밖에 3 m/s 를 넘는 칸은 없었다
- **발트해는 모델 밖이다**(SST 도 없다). 동해·오호츠크·황해·지중해·홍해는 있다
- 바람과 같은 꼴로 구웠다 — R=u·G=v(그 장의 최솟값·최댓값), **B=바다 가리개**(바람은 비운다), 북쪽 위·경도 −180 부터.
  1440×720 한 장이 **596 KB**. 바람의 1440×721 과 한 줄이 다르다(ECCO2 는 칸 가운데 −89.875…89.875)
- 입자 자취 미리보기로 쿠로시오(일본 남안에서 떨어져 굽이치는 확장부)·쓰시마 난류·멕시코 만류의 분리와 고리·아굴라스 고리가
  제자리에 섰다

## 출처

- ECCO2 cs_510 readme (NASA NAS) — https://data.nas.nasa.gov/ecco/eccodata/cs_510/readme.txt
- All ECCO Products (ECCO Group) — https://ecco-group.org/products.htm
- ECCO2 cube92 의 옮긴 자리 (ecco-support, 2018-12) — https://mailman.mit.edu/pipermail/ecco-support/2018-December/000299.html
- ECCO Drive 를 wget 으로 (ecco-support, 2020-04) — https://mailman.mit.edu/pipermail/ecco-support/2020-April/000414.html
- Using wget to download from ECCO Drive (PDF) — https://ecco-group.org/docs/wget_download_multiple_files_and_directories.pdf
- Menemenlis et al., ECCO2: High Resolution Global Ocean and Sea Ice Data Synthesis — https://www.semanticscholar.org/paper/f8d55e91613094731bd77aeef066542bf5b8139e
- SVS — Perpetual Ocean (3827) https://svs.gsfc.nasa.gov/3827 · Perpetual Ocean 2: Equirectangular (5505) https://svs.gsfc.nasa.gov/5505 ·
  Ocean Currents in equirectangular projection (5479) https://svs.gsfc.nasa.gov/5479
