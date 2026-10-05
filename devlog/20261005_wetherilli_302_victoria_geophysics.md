# 빅토리아 — 중력 측점, 지구물리 선형 셋 (GSV GeoServer)

2026-10-05 · `feature/oceania-more` · wetherilli

wetherilli 269 가 남긴 오세아니아의 것 가운데 빅토리아 둘이다. 같은 GeoServer(`opendata.maps.vic.gov.au/geoserver`, CC BY 4.0)의 레이어라 문(`austates.py`)의
표에 줄을 더했다. Capabilities(레이어 491 개)를 한 번 받아 이름을 찾았다 — TODOs 의 `gravity`·`lineaments_tmi` 곁에 `lineaments_gravity`·`lineaments_radio` 가 있다.

## 더한 것 (주 전체 3857 한 장, 2026-10-05)

| 레이어 | 상류 | 한 장 | 누르기 |
|---|---|---:|---|
| 중력 측점 | `gravity` | 4.0 초 | 측점·조사·표고·프리에어·부게 이상 |
| 자력 선형 (총자력) | `lineaments_tmi` | 1.8 초 | 없다 |
| 중력 선형 | `lineaments_gravity` | 1.7 초 | 없다 |
| 방사능 선형 | `lineaments_radio` | 1.5 초 | 없다 |

- **중력 측점은 한 색(초록) 점**이다 — 범례 규칙이 하나뿐이라 범례를 두지 않는다. 주 전체로 보면 그림의 55 % 가 점으로 덮여 줌 9 부터 그린다.
  값은 누르면 본다 — 이상은 mGal 이고, 관측 중력(`obs_grav`, 9 798 270 꼴 — µm/s²)은 단위를 헷갈리기 쉬워 싣지 않았다. 부게 이상은 지형 보정한 것(`comp_ba`)을
  먼저, 없으면 단순(`simple_ba`)
- 선형 셋은 속성이 `recnum` 하나라 누르지 않는다(`queryable: False`). 줌 6 부터
- 레이어군 "빅토리아 지구물리 (GSV)" 를 새로 두었다 — 광상(269)과 갈래가 달라서다

## 버린 것

- 빅토리아의 중력·자력 **격자** — Capabilities 에서 이름에 grav·magn·tmi·radio 가 든 것은 측점과 선형뿐이었다. 다른 이름으로 있는지는 훑지 않았다
- 남호주 지구물리(SARIG 영상)·뉴질랜드 GERM — TODOs 에 남긴다. 이번에는 빅토리아만
