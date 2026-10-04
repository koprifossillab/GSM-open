# 유럽 — BGS GeoIndex 의 자력·중력·광산·광물 산지 (EGDI 광물은 못 붙였다)

2026-10-05 · `feature/europe-resources` · wetherilli

미국(247)·호주(241)·캐나다(250)·일본(255)과 같은 꼴로 유럽의 광물·지구물리를 찾았다. 붙인 것은 영국(BGS GeoIndex)뿐이다.

## EGDI — 못 붙였다

- 광물 목록 **MIN4EU**(Minerals4EU·ProSUM·MINTELL4EU 의 광산·광징, 유럽 육상)는 메타데이터에 "WMS service" 기록이 있지만 주소가 없다. EGDI 지도
  뷰어(`maps.europe-geology.eu`)는 `egdi_mines` 를 안쪽 경로(`…&id=1552&dynamic=true`)로만 부르고, `maps.europe-geology.eu/wms` 는
  `/egdi/wms/` 로 돌려 404 다. GEUS 의 옛 주소(`data.geus.dk/egdi/wms`)도 그리로 돌린다
- 조건도 **CC BY-NC-ND 4.0**(비상업·변경 금지)이다. 주소를 찾아도 정적 판·밖에 열기 전에 사람이 읽어야 한다
- ProMine·EGDI 지구물리도 공개 WMS 주소를 찾지 못했다 — TODOs

## BGS GeoIndex — 붙였다

- 서버 `map.bgs.ac.uk/arcgis/rest/services` 는 목록이 열려 있다. `GeoIndex_Onshore` 폴더의 `geophysics`·`minerals_wms`(그리고 `geochemistry`·
  `hydrogeology`…)
- **조건** — BGS WMS 쪽 "Terms of use": **Open Government Licence**, 출처 "Contains British Geological Survey materials © UKRI [해]".
  광물 서비스의 copyrightText 는 "All rights reserved" 지만 WMS 로 내준 것은 위의 조건이다
- 문은 `bgs.py` 안의 `GEOINDEX`(상류 이름 `bgsgi`) — GSNI·AGA·GSN 처럼 같은 서버라 문을 늘리지 않았다

| 레이어군 | 레이어 | 누르면 |
|---|---|---|
| 영국 지구물리 | 자력 이상·중력 이상(1:62만 5천 지도의 색 음영) | 없음 |
| 영국 광물 자원 | 광산·채석장(BritPits, 줌 10 부터), 광물 산지(MINGOL) | 이름·운영 상태 / 이름·광종, 영국 격자 좌표 |

- 지구물리는 상류 maxScale 이 62만 5천이라 줌 9 까지만 그린다(`lastZoom`). 범례 그림이 "RGB 밴드 세 줄" 뿐이라 범례를 두지 않았다
- 광맥(Vein.Minerals)은 콘월 둘레에서 빈 그림이라 뺐다

## 확인

- 사본 DB 로 영국 탭: 자력 이상이 그레이트브리튼 전체(줌 6)에 그려지고, 멀리언 자갈 채취장을 누르면 "Mullion Gravel Pit · Ceased · E 167795 · N 19141".
  페이지 오류 없음
