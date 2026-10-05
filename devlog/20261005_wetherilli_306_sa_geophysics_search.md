# 남호주 SARIG 지구물리 — 열린 길을 찾지 못했다

2026-10-05 · `main`(기록만) · wetherilli

판 세션이 맡긴 일이다 — 남호주 SARIG 의 자력·중력·방사능 격자나 선형을 빅토리아(wetherilli 302)처럼 남호주 판에 둔다. **찾지 못해 코드는 고치지 않았다.**
상류마다 한두 번, 2 초 간격으로 물었다.

## 본 곳

| 곳 | 결과 |
|---|---|
| SARIG GeoServer `sarigdata.pir.sa.gov.au/geoserver/ows` (지금 남호주 판의 문) | WMS 레이어 31 개 — 시추공·지질 단위·접촉·습곡·엽리·단층·광물 산지뿐. 이름·제목에 grav·magn·tmi·radiom·bouguer 가 든 것이 없다 |
| 같은 GeoServer 의 GWC WMTS | 위와 같은 레이어의 타일 캐시뿐 |
| `services.sarig.sa.gov.au`·`sarigdata.pir.sa.gov.au`·`map.sarig.sa.gov.au` 의 `/arcgis/rest/services` | 404 (ArcGIS 서버가 아니다) |
| `services.pir.sa.gov.au` | 연결되지 않는다 |
| `location.sa.gov.au/arcgis` | 403 (CloudFront) |
| `data.sa.gov.au` CKAN 검색 API | 403 |
| SARIG 지도(`map.sarig.sa.gov.au`) | 레이어를 DB 번호(`dbLayerIds`)로 부르는 자체 뷰어다. 지구물리 영상은 그 뷰어 안에서만 도는 듯하다 — 뷰어의 속을 뜯어 주소를 캐지는 않았다 |

## 그래서

- **남호주의 지구물리는 이미 Geoscience Australia 의 온 나라 격자가 덮는다** — `ga:tmi`(총자력)·`ga:gravity`(완전 부게)·`ga:radiometric`(삼색 방사능),
  wetherilli 241. 해상도가 주 판보다 거칠 뿐 같은 측량을 모은 것이다
- SARIG 의 영상을 쓰려면 SARIG 이 열린 WMS 를 내주거나(주소를 GSSA 에 묻는다), 원본 격자(SARIG 의 내려받기)를 받아 우리가 굽는 길(ADMAP-2 꼴, wetherilli 262)이다.
  둘 다 이번 일의 크기를 넘는다 — TODOs 의 줄을 그렇게 고쳐 둔다
- 뉴질랜드 GERM 은 맡긴 대로 그대로 둔다
