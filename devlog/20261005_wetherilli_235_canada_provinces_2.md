# 캐나다 주 판 둘째 — 앨버타·사스카치원·노바스코샤

2026-10-05 · `feature/canada-provinces-2` · wetherilli

퀘벡·유콘(wetherilli 210)에 이어 나머지 주·준주를 실측했다. 조건이 글로 읽히는 셋만 올리고 나머지는 TODOs 에 남겼다.

## 실측 (2026-10-04)

| 곳 | 서비스 | 조건 | 한 것 |
|---|---|---|---|
| 앨버타 AGS | ArcGIS Online 타일(3857 z/x/y, 줌 0–12, TilesOnly) + 피처 서비스 | OGL–Alberta (타일 서비스 저작권 칸) | 올림 |
| 사스카치원 SGS | `gis.saskatchewan.ca` ArcGIS WMS | Standard Unrestricted Use Data Licence 2.0 (열린 정부 포털 기록) | 올림 |
| 노바스코샤 NRR | `fletcher.novascotia.ca` ArcGIS REST, WMS 없음 | DP ME 43 사용 허락 — 출처를 밝히면 원본·가공물로 쓰고 나눈다 | 올림 |
| 뉴브런즈윅 | WMS·WFS 열림 | 조건 쪽 403, WMS 조건 칸 빔 | (사람) |
| 뉴펀들랜드래브라도 | WMS 열림 | 저작권 칸 빔, 조건 글을 못 찾음 | (사람) |
| 매니토바 | `maps.gov.mb.ca` | — | 502 |
| 노스웨스트준주 | ArcGIS Online 피처 서비스뿐 | — | 그림이 없어 미룸 |
| 누나부트 | 못 찾음 | — | — |

## 왜 이렇게

- **문 셋.** 상류마다 문 하나라는 규칙을 지켰다. 사스카치원은 유콘(`ygs.py`)과 같은 ArcGIS WMS 라 3978 로 곧장 — Capabilities 에 3978 이 없어도
  그렸다. **WMS 번호가 REST 와 거꾸로다**(기반암 1:100만이 REST 11, WMS 2) — 처음 REST 번호로 물어 빈 그림을 받았다. 노바스코샤는 WMS 가 없어
  멕시코(`sgm.py`)처럼 문이 WMS 변수를 REST `export` 로 옮기는데, 3857 고정이 아니라 **화면의 투영을 `bboxSR` 로 넘긴다** — 상류가 3978 로 그린다
- **앨버타는 그림이 문을 거치지 않는다.** ArcGIS Online 의 타일 서비스는 `export` 가 없고(TilesOnly) 3857 타일뿐이다. 일본 지리원 주제 타일
  (wetherilli 172)처럼 카탈로그 행의 `tiles` 를 화면이 곧장 받고 OpenLayers 가 3978 로 옮겨 그린다(3D 도 그대로 받는다). 누른 자리만 문
  (`ags.py`)이 같은 자료의 피처 서비스에 점 하나로 `query` 한다. 타일 소스는 WMS 속성 주소를 지을 수 없어, 누른 자리 둘레 101 픽셀 네모로
  GetFeatureInfo 꼴 주소를 짓는 `pointInfoUrl` 을 화면에 두었다 — 문은 그 네모의 가운데를 누른 자리로 읽는다
- **주 밖을 묻지 않는다.** 앨버타 타일은 주 밖이 404 이고 나머지도 빈 그림이라, 묶음 탭에만 걸던 "레이어 범위(`bbox`) 밖 타일을 묻지 않기"를
  캐나다 탭(3978)의 이 셋에도 걸었다
- **시대.** 사스카치원은 ICS 영어(가장 자세한 마디 — 기·대·누대), 노바스코샤는 `Cambrian - Ordovician`, 앨버타는 `Upper Cretaceous` 처럼
  Upper·Lower 를 써서 Late·Early 로 바꿔 옮긴다. 못 옮기면 원문
- 정적 판에는 싣지 않았다 — 기본값에 넣지 않는다는 #153 의 규칙대로, 실을지는 판 세션·사람이

## 확인

- 사본 DB 로 캐나다 탭을 열어 에드먼턴(앨버타 "Horseshoe Canyon Formation · 백악기 후기"), 애서배스카(사스카치원 "PAMd · 스타테로스기 ·
  1814 Ma"), 핼리팩스(노바스코샤 "Halifax Formation · Meguma Group · 캄브리아기~오르도비스기")를 눌렀다. 타일 모두 200, 페이지 오류 없음
