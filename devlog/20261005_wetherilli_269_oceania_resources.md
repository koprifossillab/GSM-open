# 오세아니아 — 호주 세 주의 광물·지구물리, 뉴질랜드 중력

2026-10-05 · `feature/oceania-resources` · wetherilli

미국·호주(GA)·캐나다·일본·영국·그린란드·남미와 같은 꼴로 호주 주(wetherilli 225)와 뉴질랜드(218)를 더 채웠다. 문은 그대로 — `austates.py`·`gns.py`
의 표에 줄을 더했다.

## 실측과 한 것

| 곳 | 서비스 | 올린 것 | 조건 |
|---|---|---|---|
| 퀸즐랜드 GSQ | `GeoscientificInformation/MiningResources`·`GeophysicalImagery` ArcGIS | 광산·광물 산지 MINOCC(줌 7 부터), 자력 TMI·방사능 3색·완전 부게 중력 영상 | © State of Queensland (225 와 같다) |
| 빅토리아 GSV | 열린 자료 GeoServer `open-data-platform:mineral`·`mineralp` | 광상 면 237·점 620(줌 7 부터) | 225 와 같다 |
| 남호주 GSSA | SARIG GeoServer `erl:MineralOccurrenceView` | 광물 산지(EarthResourceML 라이트, 줌 7 부터) | **CC BY 4.0** (AccessConstraints) |
| 뉴질랜드 GNS | **GNS 전체 서비스** `maps.gns.cri.nz/gns/wms` 의 `gns:NZGravity` | 중력 이상 | **CC BY 3.0 NZ** (AccessConstraints) |

## 왜 이렇게

- **뉴질랜드는 서비스가 둘이다.** 지금 쓰는 `/geology/wms` 에는 지질도만 있고, 중력·광물은 `/gns/wms`(레이어 182)에 있다. 레이어 표에 `service: "all"` 을
  두고 문이 주소를 고르게 했다(`GNS_ALL_WMS_URL`). 광물 산지(`GERM_ERML_VIEW`·`MINERAL.GERM_FEATURE_VIEW`)는 나라 전체로도 가까이서도 빈 그림이라 뺐다
- **주 판의 "단위" 판정을 갈랐다.** 지금까지는 누를 수 있으면 지질 단위로 보고 보는 범위의 범례(`austates/legend/`)를 붙였다. 광산·광물 산지는 누를 수
  있지만 단위가 아니라 `RESOURCES` 로 가르고(`queryable`·`is_unit`), 범례는 두지 않는다
- **빅토리아·남호주는 속성 열을 레이어마다** 고른다(`LAYER_PROPERTIES`) — 단위의 열(`name,description,rank,…`)을 광상 레이어에 물으면 GeoServer 가
  예외를 낸다
- 라벨 "광상 규모"·"광산"·"모암" 은 남미(#254, 265)가 더한 것을 같이 쓴다 — 그 브랜치 위에 얹었다

## 확인

- 사본 DB: 퀸즐랜드 "BANTAM · Gold · Abandoned mine · Very small", 빅토리아 "ROCKY CAMP (BUCHAN) · Limestone · a major deposit…", 남호주
  "DONNAS RUSH SOUTH · Opal · occurrence" + SARIG 상세 링크. 뉴질랜드 중력·퀸즐랜드 TMI 타일 200
