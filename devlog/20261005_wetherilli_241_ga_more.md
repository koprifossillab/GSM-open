# 호주 — Geoscience Australia 의 다른 서비스

2026-10-05 · `feature/ga-more` · wetherilli

호주 탭(wetherilli 212)의 GA 는 지표 지질도뿐이었다. 서비스 목록(`/gis/rest/services`)이 403 이라 이름을 알아야 부를 수 있어, GA 자료 목록(ecat)과
검색으로 이름을 찾아 셋을 같은 문(`ga.py` 의 `OTHER`)으로 올렸다.

## 한 것

| 레이어군 | 서비스 | 레이어 |
|---|---|---|
| 호주 지질구 | `Australian_Geological_Provinces` (ArcGIS WMS) | 지각 요소, 지질구 전부(퇴적분지·지구조구·화성구 — 겹친 테두리) |
| 호주 핵심 광물 (2025) | `AustralianCriticalMineralsOperatingMinesAndDeposits` | 광산(운영·개발·휴지 셋을 한 레이어로), 광상 |
| 호주 지구물리 | `/gis/geophysical-grids/ows` (GeoServer, 101 레이어) | 자력 TMI(2019, HSI), 완전 부게 중력(2019, 색 음영), 방사능 3색(K·Th·U, 2019) |

- 셋 다 CC BY 4.0(서비스의 저작권 칸)이다. 출처 표기는 "© Geoscience Australia (CC BY 4.0)"
- 팝업 — 지질구는 이름·갈래(형·아형·서열)·상위 단위·시대(`olderNameAge`~`youngerNamedAge`, ICS 라 옮긴다)·설명·주·문헌. 광산은 이름·광종·운영·주
- 범례 — 지질구·광물은 상류의 범례 그림(WMS GetLegendGraphic), 격자는 없다

## 왜 이렇게

- **격자는 png8 로 받는다.** 512² 한 장이 PNG 로 1 MB(색 음영이 빽빽하다), JPEG 는 70 KB 지만 투명도가 없어 대륙 밖이 칠해진다.
  `image/png8` 은 260 KB 에 투명도가 남는다. 화면은 PNG 를 달라고 하고 문이 바꿔 묻는다 — 내주는 꼴은 `image/png`
- **격자는 누르지 않는다.** 고른 것이 HSI·3색 **그림**이라 GetFeatureInfo 가 그림 값(GRAY_INDEX)을 준다. 값 격자(`magmap_v7_2019_TMI` 의 nT)를
  따로 물어 팝업에 낼 수도 있지만 그림과 다른 레이어라 미뤘다
- **골라 실었다.** 격자 서비스에는 101 레이어(위로 연속·미분·비율·옛 판)가 있다. 처음 보는 사람에게 뜻이 있는 셋만 실었다
- 확인 자원(`AustraliasIdentifiedMineralResources`)은 광종마다 레이어가 스물아홉이라 이번에는 싣지 않았다 — TODOs

## 확인

- 사본 DB 로 호주 탭: 자력 TMI 가 대륙 전체(줌 4)에 그려지고, 아룬타 둘레 지질구를 누르면 "Burt Paleovalley · sedimentary · province · 신생대",
  얌바 광산은 "Yaamba · Magnesium · Operating mine · QLD". 페이지 오류 없음
