# 영국 — 수리지질·G-BASE 시료 지점·하천 퇴적물 지화학 31 원소

2026-10-05 · `feature/bgs-gbase` · wetherilli

TODOs 의 "결정 없이 할 것" 다섯째 줄 — BGS 지화학(G-BASE)·지하수를 GeoIndex 꼴로.

| 레이어 | 서비스 | 누르면 |
|---|---|---|
| 수리지질 1:62만 5천 | GeoIndex `hydrogeology` WMS | 암석 단위·갈래·대수층 생산성·흐름·요약 |
| G-BASE 하천 퇴적물 시료 지점 | GeoIndex `geochemistry` 의 `Stream.sediment` WMS(줌 12 부터) | 시료 번호·분석 원소·사업 |
| 하천 퇴적물 지화학 31 원소 | **CMIC** `CMIC/Stream_Sediment_Geochemistry` REST | 그 자리의 함량 |

## 왜 이렇게

- **G-BASE 의 "지화학" 은 GeoIndex 에 시료 지점뿐이다** — 점마다 시료 번호와 분석한 원소 이름만 있고 값이 없다. 원소마다 칠한 지도는 BGS 의 핵심 광물
  정보센터(CMIC) 서비스에 있었다 — G-BASE 와 북아일랜드 Tellus 의 하천 퇴적물을 보간한 래스터 31 장(주원소 산화물 여섯·미량 원소 스물다섯). 이것이
  TODOs 가 바란 것에 가깝다. 시료 지점도 함께 둔다 — 어디서 쟀는지를 보여 준다
- CMIC 는 **WMS 를 켜지 않아** REST `export`·`identify`(`arcwms.rest_*`)로 옮긴다. 상류는 GeoIndex 와 같은 `bgsgi` 로 둔다 — 같은 서버(`map.bgs.ac.uk`)다
- 누르면 화소 값(`Classify.Pixel Value`)을 단위 붙여 보인다 — **단위는 서비스가 적지 않아** 범례 칸의 값(구리 1.4–12 000)과 G-BASE 의 관례로
  주원소 산화물은 %, 미량 원소는 mg/kg 로 적었다
- 범례는 REST 범례의 함량 구간을 목록으로(`list/legend/`, `bgs.legend_rows`)
- 표토(`Top.soil`)·암석 시료 지점은 덮는 곳이 성겨 뺐다. 토양 지화학(UKSO `UKSO_BGS_GBASE`)도 시료 위치뿐이다
- **조건** — GeoIndex WMS 는 OGL 이다. CMIC 는 REST 만이고 조건 글(copyrightText·설명)이 비었다. 조건표에 "(사람) 읽을 것" 으로 적었다. 정적 판에 싣지 않는다

## 확인

- 사본 DB: 구리 37.9 mg/kg(콘월), 수리지질 WARWICKSHIRE GROUP(2B · Moderately productive aquifer), G-BASE 시료 4 32 2782 C+, 구리 범례 11 칸
