# 캐나다 — 주의 광물 산지 다섯

2026-10-05 · `feature/canada-minerals` · wetherilli

캐나다 탭에 주마다 광물 산지를 더했다. 모두 이미 있는 주의 문을 넓혔다 — 새 문은 없다.

| 주 | 레이어 | 수 | 길 |
|---|---|---|---|
| 브리티시컬럼비아 | MINFILE | 1 만 6 261 | openmaps GeoServer WMS(3978) — 기반암과 **레이어마다 주소가 따로**다 |
| 유콘 | MINFILE | 3 223 | 같은 `GY_Geological`, WMS 57(REST 4) |
| 온타리오 | MDI(OMEIS Mineral Inventory) | 1 만 8 697 | 같은 `GeologyOntario_Map`, WMS 11 · 속성은 REST 46 identify |
| 퀘벡 | 가동 광산·진행 사업 | — | 같은 SIGÉOM WMS `SGM:Mines_projets`, 문으로만(Origin 403) |
| 사스카치원 | SMDI · 광산 위치 | 6 012 · — | `Economy/Mineral_Exploration` — **WMS 가 없어**(400) REST export·identify(#271 의 `arcwms.rest_*`) |

## 왜 이렇게

- 한 레이어군("캐나다 주 광물 산지")에 모았다 — 북미 묶음에서 나라를 가로질러 켜고 끄기 쉽다. 씨앗은 상류마다 따로다
- 열 이름이 길마다 다르다 — 유콘 WMS 는 작은 글자(`minfile_number`), 온타리오 identify 는 별칭(`MDI Identifier`), 사스카치원 identify 는
  섞인 글자(`PrimaryCommodities`)다. 문마다 둘 다 읽는다
- 사스카치원은 넓게 보면 한 장에 10 초라 줌 6 부터. 범례는 두지 않았다(누르면 광종이 뜬다)
- 상세 쪽이 있는 곳(MINFILE·MDI·SMDI)은 링크를 붙였다
- 시험하다 알았다 — `version` 없이 `i`·`j` 로 물으면 ArcGIS WMS 가 JSON 이 아닌 것을 준다. 화면(OpenLayers)은 늘 `1.3.0` 을 보내 문제가 없다.
  퀘벡 WMS 는 거꾸로 1.1.1 만 받는다(문이 이미 옮긴다)

## 버린 것

- 앨버타 — 금속·산업 광물 산지가 ArcGIS Online 피처 서비스뿐이라 그림 길(export·WMS)이 없다. TODOs
- 노바스코샤 — 광물 산지 서비스가 없다(`databases` 는 에너지뿐)
- 퀘벡 광물 산지(gîte) — 이 WMS 에 없다

## 확인

- 사본 DB: BC FORSTER(Uranium, Niobium …, MINFILE 링크), 유콘 Dublin Gulch(gold, silver · 생산), 온타리오 Ricketts(Iron, Titanium · MDI 링크),
  사스카치원 0003(Iron, SMDI 링크), 퀘벡 Niobec(Niobium · Mine active). 타일 200
