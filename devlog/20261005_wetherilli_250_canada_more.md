# 캐나다 — NRCan 의 편찬 지질도·핵심 광물·광상 유망도

2026-10-05 · `feature/canada-more` · wetherilli

호주(GA, 241)·미국(USGS, 247)처럼 캐나다 탭에도 지질도 밖의 국가 자료를 더했다. 문은 `nrcan.py` 를 넓혔다(`SERVICES`). OGL–Canada.

## 찾기

NRCan 지도 서버(`maps-cartes.services.geo.ca/server_serveur/rest/services/NRCan`)는 목록이 열려 있다 — 서비스 278 개(영·불 짝). 지질과 닿는 것:
`cdn_geol_compil_en`(편찬 지질도)·`critical_minerals_en`·`carbonatite_ree_en`·`pegmatite_lithium_en`·`graphite_prospectivity_en`·
아연·니켈 유망도(2023)·`gsc_bedrock_geology_en`(도폭 색인)·`earthquakes_en`. **자력·중력 격자는 이 서버에 없다.** 검색에서 나온 GSC 의
CAGDB WMS(`wms.agg.nrcan.gc.ca`)는 60 초 안에 답하지 않았다 — TODOs.

## 한 것

| 레이어군 | 레이어 | 누르면 |
|---|---|---|
| 캐나다 지질도 편찬 (CGMC) | 주·준주 지질도를 모은 래스터 | 없음 — 범례 그림 |
| 캐나다 광물 자원 | 핵심 광물 시설(광산·처리·고급 탐사·처리 계획 넷을 한 레이어로), 탄산염암 희토류·니오븀 유망도, 페그마타이트 리튬 유망도 | 시설: 이름·갈래·광종·개발 단계·운영·운영사·주 |

## 왜 이렇게

- **CGMC 는 누르지 않는다** — 래스터라 GetFeatureInfo 가 `Pixel Value`·`Count` 만 준다. 번호 → 단위 표를 찾지 못했다. 범례 그림(150×612)은 있다
- **유망도 둘은 래스터 모형**이다(딥러닝·자연어 처리로 지질·지구물리를 섞은 것). 누를 값이 없고 범례 그림만. 흑연·아연·니켈 유망도는 같은 꼴이라
  더하기 쉽지만 레이어가 늘어 미뤘다
- 지진은 이미 지역 탭의 지구 자료 점(USGS 지진, wetherilli 185)이 있어 싣지 않았다. 도폭 색인은 도폭 쪽 링크를 다루는 길이 따로 들어 미뤘다
- **느린 서버** — 처음 잴 때(2026-10-05 새벽) 대륙 한 장이 40–77 초, Wheeler 도 13 초였다. 다시 재니 1.8 초. 캐시가 받아 주는 것에 기댄다
- `개발 단계` 라벨은 #234(미국)가 더한 것을 함께 쓴다

## 확인

- 사본 DB: 카탈로그에 네 레이어가 3978 로, 편찬 지질도 타일 200, 비버브룩 광산을 누르면 "Beaver Brook · Antimony · Past producer · Hunan Nonferrous…",
  희토류 유망도 범례 그림 200
