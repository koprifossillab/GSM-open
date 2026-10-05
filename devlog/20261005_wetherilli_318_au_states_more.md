# 호주의 남은 주 — 태즈메이니아 지질, 뉴사우스웨일스 광물

2026-10-05 · `feature/au-states-more` · wetherilli

판 세션이 "결정이 필요 없는 남은 것 가운데 가장 값이 큰 것" 을 고르라 했다. TODOs 의 "호주의 남은 것"(뉴사우스웨일스·태즈메이니아·노던테리토리의 지질도를
찾지 못했다, wetherilli 241)을 골랐다 — 호주 탭에서 주 판이 빈 곳이 셋이라서다. 다시 찾아(한 곳에 한두 번, 2 초 간격) 둘을 붙였다.

## 찾은 것

| 주 | 곳 | 결과 |
|---|---|---|
| 태즈메이니아 | 주 토지정보 **theLIST** `services.thelist.tas.gov.au/arcgis/rest/services/Public/GeologicalAndSoils` | **지질 1:25만 합본(면 16·선 15)·1:2.5만(면 14·선 13)** — 241 이 본 MRT 자신의 서버에는 도폭 색인뿐이었는데, 주 토지정보 서버에 있었다 |
| 뉴사우스웨일스 | GSNSW GeoServer `gs.geoscience.nsw.gov.au/geoserver/ows` (CC BY 4.0) | 지질도는 없고 광물 산지·광산·광업권·시추공 — **광물 산지·광산**을 붙였다 |
| 뉴사우스웨일스 | `gs-seamless.geoscience.nsw.gov.au` | 503 — 이름으로 보아 이음매 없는 지질도의 자리다. 살아나면 |
| 노던테리토리 | `geoscience.nt.gov.au/geoserver` | 404. 찾지 못했다 |

## 어떻게

- 같은 문(`austates.py`)에 상류 둘(`mrt`·`gsnsw`)을 더했다. 태즈메이니아는 퀸즐랜드처럼 REST `export`·`identify` 라, 퀸즐랜드의 두 함수를 상류·주소를 받는
  `_rest_map`·`_rest_identify` 로 빼서 함께 쓴다. 뉴사우스웨일스는 빅토리아·남호주의 GeoServer 길(`_gs`)에 한 갈래
- **태즈메이니아는 줌 11 부터** — 1:25만 판은 1:50만, 1:2.5만 판은 1:35만보다 넓으면 상류가 그리지 않는다(310 의 셈 — 512 px 격자 줌 10 이 96 dpi 로 1:29만).
  면의 색이 피처마다라 REST 범례가 빈 칸 하나다 — 범례는 없고(`NO_LEGEND`), 누르면 기호·단위(층원·층·아층군·층군·초층군 가운데 가장 작은 것)·지역·시대·설명
- 뉴사우스웨일스는 광물 산지(`erl:MineralOccurrenceView` — 이름·광종·광산 이름)와 광산(`erl:MineView` — 이름·상태). 빈 값이 `None`·`Unnamed` 로 와서 지운다.
  `mo:MinOccView` 는 광종이 거의 `unknown` 이라 버렸다

## 조건

- 뉴사우스웨일스는 Capabilities 의 AccessConstraints 가 CC BY 4.0 이다
- 태즈메이니아 theLIST 의 웹 서비스 약관(2014-12)은 열어 쓰는 것을 막지 않지만 자료의 이용 허락을 "서비스·레이어의 저작권 글" 로 미루는데, 지질 레이어의 그 글이
  비었다(서비스 글은 "the LIST State of Tasmania" 뿐). 우루과이처럼 서버 문으로 보이기만 하고 **정적 판에 싣지 않는다**. MRT 에 물을지는 TODOs 에 사람의 일로 남겼다

## 확인

`verify_layers` 의 길로 실제 상류에 넷 모두 그림(태즈메이니아 격자 줌 10, 뉴사우스웨일스 7). 태즈메이니아를 누르면 "Jd · Tasmanian Dolerite · 쥐라기" 가 온다.

곁에서 — TODOs 의 그린란드 지구물리 줄은 #290(wetherilli 301)으로 끝나 지웠다.
