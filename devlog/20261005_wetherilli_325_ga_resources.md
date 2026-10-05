# 호주 — GA 확인 자원(광종 29)과 수리지질도

2026-10-05 · `feature/ga-resources` · wetherilli

판 세션이 준 일(gsm-91 의 정리 목록 6번) — 호주 GA 의 확인 자원과 지하수를 ecat 에서 서비스 이름을 찾아 호주 탭에. 남은 주는 gsm-57(#309)의 몫이다.

## 찾기

GA 의 서비스 목록(`/gis/rest/services`)은 여전히 403(CloudFront)이다(wetherilli 241 과 같다). ecat 의 GeoNetwork 검색 API(`/geonetwork/srv/api/search/records/_search`)에
"identified mineral resources"·"groundwater"·"hydrogeology" 를 물어 이름을 모았다.

- **확인 자원** — `AustraliasIdentifiedMineralResources`(2025 판). 광종 29 가 WMS 레이어 하나씩(안티몬…바나듐), 모두 누를 수 있다. 조건 **CC BY 4.0**
  (Capabilities 의 AccessConstraints)
- **지하수** — 분지별 조사(쿠퍼·갈릴리·아다베일·보웬·머리·달링 …)가 수십 개이고, 온 나라를 덮는 것은 **`Hydrogeology_of_Australia`**(1987 1:500만의
  수치판, 대수층 갈래·분포·생산성) 하나다. 그것만 골랐다. CC BY 4.0. 격자(`groundwater-grids`)·수질(HYDROCHEM WFS)은 분지 단위라 두었다

## 광종마다 레이어 하나

처음엔 29 광종을 한 레이어로 묶으려 했다. 그런데 범례가 광종마다 **상태(광상·생산 광산) × 크기 칸**이라 모두 257 칸이다 — 한 레이어의 범례로는
읽을 수 없다. 광종마다 레이어 하나(`ga:resource:<광종>`)로 두니 범례 그림이 그 광종의 몇 칸(구리 138×194)이고, 이미 있는 `OTHER` 길(WMS 그림·첫 레이어
범례 그림·geo+json 속성)을 그대로 탄다. 레이어군 "호주 확인 자원 (GA 2025)" 이 패널에서 접혀 있으면 스물아홉이 자리를 먹지 않는다.

- 팝업 — 이름·광종·운영(생산 광산·광상)·광상 유형·자원량 칸(`>50 Mt` — 크기와 단위)·주·출처. 값은 영어 그대로
- 수리지질도 팝업 — 대수층 설명·갈래·분포·생산성
- 손으로 물어 올림픽댐(구리, 생산 광산, >50 Mt, SA)과 남동부의 공극 대수층이 뜨는 것을 보았다

## 두지 않은 것

- 가공 시설(`ProcessingPlants`) — 핵심 광물(wetherilli 241)의 처리 시설과 겹친다
