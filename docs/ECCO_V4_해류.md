# ECCO V4 해류는 어떤가 — 검토

2026-10-01 · koprifossillab · **검토다. 계획이 아니다** — ECCO2 검토([ECCO2_해류_시각화.md](ECCO2_해류_시각화.md))의 짝

사람이 "ECCO2 는 조건이 붙어 있고, 누구나 받을 수 있는 바람 자료와는 다르다고 했어. ECCO4 는 어떤지 한 번 알아봐"
라고 했다. ECCO2 검토에서 걸린 "조건" 은 **쓰는 조건이 아니라 받는 길**이었다 — ECCO Drive 가 Earthdata 로그인을
묻는다. 그래서 V4 도 같은 두 물음으로 본다. 쓰는 데 조건이 있나, 로그인 없이 받히나.

## 1. ECCO V4 는 무엇인가

**ECCO Version 4**(NASA JPL·MIT·AER 외). MITgcm 에 관측을 **adjoint 로 처음부터 끝까지** 맞춘 상태 추정이다 — 모델을
돌린 그대로라 열·염분·질량 수지가 닫힌다. ECCO 그룹이 지금 권하는 판이다(ECCO2 는 "Legacy").

- 모델 격자는 **LLC90**(위경도–극 덮개 섞음), 1° 남짓, 적도 둘레는 더 촘촘하다. 깊이 50 층
- **Release 4(V4r4)** — 1992-01 ~ 2017-12. PO.DAAC 의 정식 배포본이다. 1/2° 위경도 격자로 옮긴 판(`latlon_0p50deg`)이
  하루·한 달 평균으로 있다
- **Release 5(V4r5)** — 2019 까지 늘렸다(근실시간 연장은 2022-09 까지라는 발표가 있다). 배포는 PO.DAAC 의 클라우드(S3)와
  ECCO Drive — **둘 다 로그인을 묻는다**(§2). 끝 날짜는 받는 곳의 목록을 직접 봐야 한다

| | ECCO2 (cube92) | ECCO V4r4 |
|---|---|---|
| 맞춘 방식 | Green 함수 — 수지가 안 닫힌다 | adjoint — 수지가 닫힌다 |
| 배포 격자 | **1/4°**(1440×720) | **1/2°**(720×360) |
| 시간 | 3 일 평균(3D), 하루(2D) | **하루** 평균, 한 달 평균 |
| 기간 | 1992-01 ~ 2019-03 | 1992-01 ~ 2017-12 |
| 와류 | 겨우 보인다 | 안 보인다 — 큰 흐름만 |

## 2. 받는 길 — 2026-10-01 에 이 서버에서 찔러 본 것

| 길 | 결과 |
|---|---|
| PO.DAAC 아카이브 `archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/…` | 302 → **Earthdata 로그인** |
| PO.DAAC OPeNDAP `opendap.earthdata.nasa.gov/…` | 302 → **Earthdata 로그인** |
| PO.DAAC 메타데이터(`…-public/…cmr.json`)·CMR 검색 | 로그인 없이 된다 — 목록과 주소만 |
| ECCO Drive `ecco.jpl.nasa.gov/drive/files/Version4/Release5/` | 302 → 로그인 |
| **NASA NAS 데이터 포털** `data.nas.nasa.gov/ecco/ECCOv4/Release4/` | **로그인 없이 받힌다.** `interp_daily/<변수>/<해>/<날>/` 에 하루 한 파일 |

NAS 포털에서 본 것:

- `interp_daily/` 에 `EVEL`·`NVEL`(동서·남북 유속)·`SALT`·`SSH`·`MXLDEPTH`·해빙·대기 강제력(`EXF*`) 따위가 변수마다 있다.
  `EVEL/1992/001/EVEL_1992_01_01.nc` 부터 `2017/365/` 까지
- 한 파일이 **98.9 MB**(`EVEL` 하루, 103 718 003 바이트). 머리가 `\x89HDF` — **netCDF-4(HDF5)** 다. 압축했는지·덩이(chunk)를
  어떻게 잘랐는지는 아직 안 열어 봤다
- Range 를 받는다(206). 다만 HDF5 라 첫 층의 자리를 셈으로 낼 수 없다 — 덩이 색인을 읽어야 한다(h5py + 원격 파일). 안 되면
  통째로 받아 첫 층만 남긴다
- 주소 꼴에 주의 — `eccodata/llc_90/…` 꼴(검색에 나오는 옛 꼴)은 500 을 준다. 목록의 링크 꼴(`/ecco/ECCOv4/Release4/…`)이 맞다
- 이 포털이 **ECCO2 도 로그인 없이 준다**(`/ecco/cs_510/UVEL.nc/…`) — ECCO2 검토의 §2·§7 을 고쳤다

## 3. 쓰는 조건

ECCO2 와 같다 — **NASA 지구과학 자료 정책(열린 자료)이라 쓰는 데 제한이 없고**, 인용을 바란다. Earthdata 로그인은 쓰는
조건이 아니라 받는 사람을 세는 창구다(무료 가입). 인용은 자료마다 DOI 가 있다 — 하루 유속 1/2° 는
ECCO Consortium et al. (2021), doi:10.5067/ECG5D-OVE44.

바람(GFS·ERA5)과 다른 점은 **조건이 아니라 문**이다 — 바람은 공개 버킷·NOMADS 라 로그인이 없고, ECCO 는 PO.DAAC·ECCO Drive 가
로그인을 묻는다. 그 둘을 비켜 NAS 포털로 가면 V4r4 도 ECCO2 도 바람처럼 받힌다.

**NAS 포털을 써도 된다.** NASA Ames 의 NAS(고성능 계산 부문)가 차린 공식 데이터 포털이고, ECCO 그룹이 V4r4 하루 자료를
받는 곳으로 직접 안내한다(ecco-support, 2022-01). 쪽마다 디렉토리를 통째로 받는 `wget` 명령을 내주는 공개 내려받기 쪽이다.
처음에 KIGAM GeoServer(문서에 없는 주소, CLAUDE.md "두 개의 상류 주소")에 빗댔다가 사람이 "NAS 도 NASA 사이트잖아? 안 될
이유가 있어?" 라고 물었다 — 없다. 빗댐이 틀렸다. 남는 것은 어느 상류에나 붙는 것뿐이다 — 천천히 받고(devlog 010), 인용은
자료의 DOI 로, 주소가 PO.DAAC 만큼 오래 고정될지는 장담하지 않는다(받아 굽고 나면 화면은 상류를 타지 않는다).

## 4. 해류를 흐르게 그리는 데에는 어느 쪽인가

| | ECCO2 | ECCO V4r4 |
|---|---|---|
| 보기 | **곱다** — 1/4°, 와류가 조금 보인다 | 거칠다 — 1/2°, 와류 없이 큰 흐름 |
| 시간 결 | 3 일 | **하루** |
| 표층 한 시점 받는 양 | **4 MB**(첫 층만 Range, 셈) | 98.9 MB 파일에서 첫 층 — 덩이를 읽으면 수 MB, 못 읽으면 통째 |
| 굽는 쪽 라이브러리 | 표준 라이브러리로 된다(classic) | h5py 가 든다(`build_crust` 처럼 굽는 쪽만) |
| 기간 | 2019-03 까지 | 2017-12 까지 |
| 수지·과학적 무게 | 약하다 | **닫힌다** — 수송량·열 수지를 따질 때 |

**화면에 흐름을 보이는 것이 목적이면 여전히 ECCO2 다.** 받는 길의 차이(로그인)는 NAS 포털로 둘 다 풀렸고, 남는 차이는 해상도와
수지다. V4r4 는 "흐름이 곱다" 보다 "수송량을 따진다" 쪽에 쓸 자료다 — 그 화면(단면 수송·열 수지)을 만들 생각이 생기면 그때 본다.

## 5. 정하기 전에 확인할 것

- [x] NAS 포털을 쓸지 — **쓴다**(§3). Earthdata 계정은 들지 않는다
- [ ] V4r4 를 고르면 — `EVEL` 파일의 덩이·압축(h5py 로 머리만), 첫 층만 Range 로 읽히는지
- [ ] V4r5 의 끝 날짜와 위경도 판이 있는지 — PO.DAAC 클라우드 목록(CMR)으로 본다
- [ ] 받기는 천천히 — 재려고 두드리지 않는다(devlog 010)

## 출처

- ECCO Ocean Velocity — Daily Mean 0.5 Degree (V4r4), PO.DAAC — https://podaac.jpl.nasa.gov/dataset/ECCO_L4_OCEAN_VEL_05DEG_DAILY_V4R4
- NASA ECCO — Latest: V4r4 — https://ecco-group.org/products-ECCO-V4r4.htm
- ECCO Version 4 Release 5 (Fukumori, ECCO 연례 회의 2023) — https://ecco-group.org/docs/ecco_annual_mtg23_day2_01_fukumori.pdf
- ecco_access 문서 — https://ecco-access.readthedocs.io/en/latest/
- Downloading v4r4 daily products (ecco-support, 2022-01) — https://mailman.mit.edu/pipermail/ecco-support/2022-January/000585.html
- NAS ECCO 데이터 포털 — https://data.nas.nasa.gov/ecco/ECCOv4/Release4/
