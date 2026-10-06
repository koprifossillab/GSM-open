# 호주 남은 주 — 노던테리토리는 열린자료 셰이프로, 뉴사우스웨일스는 아직

2026-10-05 · `feature/au-nsw-nt` · wetherilli

TODOs 의 "호주 남은 주"(wetherilli 318 의 남은 것) — 뉴사우스웨일스 이음매 없는 지질도는 503, 노던테리토리는 지질도 서비스를 찾지 못했다.
한 곳에 한두 번, 2 초 간격으로 다시 찾았다.

## 뉴사우스웨일스 — 아직 닫혀 있다

| 곳 | 결과 |
|---|---|
| `gs-seamless.geoscience.nsw.gov.au/geoserver/ows` | 여전히 503. 뿌리는 nginx 기본 쪽 — 뒤에 아무것도 없다 |
| Data.NSW 목록 "NSW Seamless Geology"(CC BY) | WMS·WFS 주소가 위의 503 을 가리킨다 |
| MinView(주 지도 화면)의 `env.json` | `gs-mv.geoscience.nsw.gov.au/geoserver/` — **공개 DNS 에 없다**(NXDOMAIN, 1.1.1.1·8.8.8.8). 주 화면 자신도 지금 밖에서는 지질도를 못 그린다 |
| 우리가 쓰는 `gs.geoscience.nsw.gov.au` | `gsml:MappedFeature` 가 있어 지질 단위인가 했는데 그려 보니 광물 산지 점이었다 |

옮겨 가는 중인 듯하다. 지역별 MBTiles 꾸러미(NE Z56 노출 기반암 따위)는 있지만 조각이라 붙이지 않았다. TODOs 에 "살아나면" 으로 남겼다.

## 노던테리토리 — 서비스는 없고 파일이 있다

NTGS 의 `geoscience.nt.gov.au/geoserver`·`/arcgis` 는 404, STRIKE 화면(Cohga Weave)은 주소를 감춘다. 그런데 주 열린자료(`data.nt.gov.au`)에
**"Northern Territory Geological Map (Interp) 2500K"·"… Geological Faults 2500K"** 가 셰이프 ZIP 으로 있었다 — 4.4 MB·0.2 MB, GDA94 경위도,
조건은 "Creative Commons Attribution"(판 번호를 적지 않아 CC BY 로만 적었다). NAS `sources/australia/nt_geology/`.

얀마옌(022)처럼 **파일을 서버에 두고 한 덩이로 화면에 준다** — `ntgeo.py`, 상류 이름 `ntgs`, 자리는 `GSM_NTGEO_DIR`(기본 `<DB 옆>/nt_geology`, ZIP 둘 그대로).

- 면 1 975(아라푸라해의 바다 면 넷은 뺀다), 꼭짓점 38 만 → 0.002°(200 m 남짓)로 줄여 11 만 8 천. 1:250만에서 0.5 mm 가 1.2 km 라 넉넉하다.
  줄이면 무너지는 작은 고리는 원래 고리를 둔다(처음엔 16 개가 사라졌다). 2.8 MB, gzip 0.7 MB — 중국 geo3al 처럼 `render: image` 로 한 장에 굽는다
- **색은 우리가 붙인다** — 색 열이 없다. ICS 기 색만 쓰면 원생누대가 70 % 라 한 분홍이 된다. 원생누대는 기(스타테로스기·오로세이라기·칼리마기 …)까지
  ICS 색을 쓰고, 기가 없으면 대·누대의 색. 걸침("Ectasian-Stenian")은 앞의 기 색. 범례는 시대 칸 열일곱
- 속성: 기호·층서 단위·암석·암석 갈래·지질구·시대(한국어판은 ICS 한글판)·연대 범위
- 단층 849 — 해석(지구물리, 571)은 끊은 선, 지도에서 옮긴 것(278)은 실선. 이름·변형대가 있으면 싣는다

그려 보니(PIL 로 한 장) 주 경계 꼴대로 차고, 남쪽의 띠 무늬(아마데우스 분지 쪽)와 북쪽 해안의 원생대 분홍이 보인다 — 눈으로 본 것이지 지점마다 맞춘 것은 아니다.

## 버린 것

- 서비스 없는 노던테리토리를 1:250만 도폭 스캔(STRIKE)으로 — 판매·제한 조건이 섞여 있고 그림이 무겁다
- 뉴사우스웨일스 지역 MBTiles — 나라 일부의 노출 기반암 조각이라 한 판이 아니다

## 운영

병합·배포 뒤 NAS `sources/australia/nt_geology/` 의 ZIP 둘(`GEO_INTERP_2500K_shp.zip`·`GEO_FAULTS_2500K_shp.zip`)을 `/srv/GSM/db/nt_geology/` 로.
씨앗(`data/ntgs_layers.json`)은 컨테이너가 뜰 때 들어간다.
