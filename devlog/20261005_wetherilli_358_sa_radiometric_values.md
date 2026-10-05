# 남호주 방사능 — 누르면 K·Th·U 값 (그리고 TODOs 다시 묶기)

2026-10-05 · `feature/sa-radiometrics-values` · wetherilli

판 세션의 일 둘 — ① 병합된 PR 이 끝낸 TODOs 줄을 걷는다(main 361dbe0, 문서만) ② 결정 없는 것 하나를 골라 잇는다.
처음엔 TODOs 맨 위 "앨버타 광물 산지" 를 골랐는데 gsm-57 이 #311 로 이미 했다 — 그 줄이 ① 의 찌꺼기였다. ① 에서 일곱 줄을 걷었다.
② 는 "남호주 지구물리의 값 누르기"(wetherilli 329 의 남은 것)다.

## TODOs 가 틀렸던 것 — "43 MB 가 가장 싸다"

329 는 SARIG 목록에서 "2025 State radiometric grid merge" 의 ZIP 43 MB 를 보고 가장 싸다고 적었다. 받아 보니 **격자가 아니라 탐사 구역 셰이프**였다
(`SA_Rad_Merge.shp` 136 MB 를 줄인 것). 격자는 다른 목록 — "South Australian regional radiometric images, 2024"(`mesac771`, CC BY 4.0 Australia) —
에 원소마다 ZIP 하나로 S3 에 있다. K·Th·U 셋이 650 MB 남짓씩, 2 GB. 받은 것은 NAS `sources/australia/sa_radiometrics/`.

## 굽는 법

ER Mapper 격자 — `.ers` 글 머리와 머리 없는 float32 몸. GDA94 경위도, 0.00077°(80 m 남짓), 15 581×15 796 칸(원소마다 몇 칸씩 다르다 — 원소마다 자리를 따로 적는다).
메타데이터 PDF 가 K 는 %, Th·U 는 등가 ppm 이라 적는다.

- **네 칸에 하나를 고른다** — 320 m 남짓, 원소마다 30 MB. 원본이 이미 80 m 로 보간한 매끄러운 격자라 누른 자리의 값으로 넉넉하다.
  평균을 내지 않은 것은 numpy 없이 2 억 4 천만 칸을 파이썬으로 돌지 않으려는 것이다 — 고르기는 `array` 자르기(`line[2::4]`)라 C 에서 돈다.
  원소마다 9–27 초, 메모리 78 MB(줄 하나)라 컨테이너에서도 굽는다
- int16 — K ×1000, Th·U ×100. 빈 곳 −32768. GDA94↔WGS84 의 1 m 남짓은 칸(320 m)보다 훨씬 작아 옮기지 않는다
- 타일은 굽지 않는다 — SARIG 영상 WMS(`rad_rgb`)가 이미 그린다. **누르기만 우리 파일**이다. 파일이 없으면 `rad_rgb` 는 하던 대로 누르지 않는다
  (`austates.queryable` 이 `sarad.available()` 을 본다). 범위 범례도 뜨지 않게 `is_unit` 에서 뺐다

## 맞는지

| 자리 | K % | eTh ppm | eU ppm |
|---|---|---|---|
| 올림픽댐 (−30.44, 136.88) | 1.87 | 23.2 | **73.4** |
| 마운트페인터 (−30.21, 139.36) | **5.44** | 45.5 | 35.5 |
| 포트링컨 (−34.72, 135.86) | 1.49 | 15.5 | 8.8 |

우라늄 광상과 마운트페인터의 고열 화강암이 제 원소로 높다. 자리는 캥거루섬 북쪽 해안(137.4°E)을 남→북으로 가로질러 보았다 — −35.60 까지 값,
−35.55 부터 빈 곳이고 해안은 −35.59 남짓이라 칸 하나 안에서 맞는다.

시험(`test_sarad`)이 하나 잡았다 — 칸 번호를 `int()` 로 내면 0 쪽으로 잘려, 격자 바로 서·북 바깥을 첫 칸으로 읽었다. `math.floor` 로.

## 버린 것

- 자력·중력 — 중력 격자는 4.7 GB, 주 총자력 합본은 PDF·PNG 만 보였고 가울러 크라톤 합본 TMI 는 18 GB 다. TODOs 에 남겼다
- 값으로 칠한 우리 타일(원소마다 따로 켜는 레이어) — SARIG WMS 에 K·Th·U 낱장 영상이 이미 있다(29 레이어 가운데). 필요하면 그쪽을 씨앗에 더하는 것이 싸다
- 평균 내기 — 위의 까닭

## 운영

`manage.py build_sa_radiometrics <K.zip> <Th.zip> <U.zip>` 이 `<GSM_SARAD_DIR>`(기본 `<DB 옆>/sa_radiometrics`)에 쓴다. 구운 것(92 MB)은
NAS `sources/australia/sa_radiometrics/baked/` 에도 두었다 — 그대로 `/srv/GSM/db/sa_radiometrics/` 에 옮기면 된다.
