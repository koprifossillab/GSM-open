# prewarm 이 유럽·북극의 새 상류를 안다

2026-10-04 · `feature/prewarm-europe` · wetherilli

`prewarm` 은 KIGAM·GEUS·VWorld·NPI·KOPRI·GSJ·GeoMAP·PGC 표고·Trek 만 알았다. 그 뒤에 들어온 상류 열 곳 — EMODnet·NGU·GTK
(wetherilli 135·140), BGS·GSNI·BRGM·EGDI(143), BGR·IGME·GSI(147) — 은 `--layers` 에 넣으면 "타일이 아니다" 로 거절됐다.
화면은 이들을 모두 `npolarSource` 로, 카탈로그 행의 `projection` 격자에서 받는다. prewarm 도 같은 행의 같은 값을 읽게 했다.

## 투영은 `views._layer_extra` 에서 읽는다 — 표를 새로 두지 않는다

화면에 투영을 알려 주는 곳이 `_layer_extra` 하나다. prewarm 이 상류마다 투영을 따로 적으면 둘이 갈라질 때 캐시가 조용히
빗나간다 — 받은 타일은 쌓이는데 화면은 다른 열쇠를 묻는다. 그래서 레이어 행을 꺼내 `_layer_extra` 를 그대로 부른다.
같은 상류 안에서도 갈리기 때문이기도 하다.

- EMODnet 은 레이어군의 지역으로 갈린다 — 북극해는 3413, 유럽 바다(영국에 둔 것, 176)는 3857
- IGME 는 판으로 갈린다 — 1:100만은 4326, MAGNA 1:5만은 3857

투영 표를 문마다 하나 더 두는 길(`ngu.PROJECTION` 처럼)은 버렸다. 위의 두 갈림이 문 바깥(레이어군)에 걸려 있어 문 하나로 다
적을 수 없다.

## 격자 둘을 더했다 — 3575 와 4326

`tilegrid.PolarGrid` 를 `Grid` 로 넓혔다. 극 평사도법 둘(3413·3031)에 NGU 의 북극 람베르트(3575)와 IGME 1:100만의 4326 을 더했다.
3857 은 `createXYZ({extent: 3857})` 가 KIGAM 의 `wmsSource` 격자와 같아 따로 두지 않았다.

4326 은 함정이 둘이다.

- **OpenLayers 가 해상도를 가로 폭으로 정한다**(`resolutionsFromExtent` 가 가로·세로 중 큰 것). 그래서 줌 0 은 360° 네모 한 장이고
  BBOX 의 남쪽이 -270° 다. 줄 수는 칸 수의 반이다 — `Grid.last` 가 그것을 알고, 큰 그림을 자를 때 없는 줄을 묻지 않는다.
  대만(GSMMA)은 이 격자를 피해 180° 네모 두 장짜리 격자를 따로 지었지만(`TAIWAN_GRID`), IGME 는 `npolarSource` 의 기본 격자를
  탄다. 받는 쪽을 화면에 맞췄다 — 화면을 바꾸면 이미 쌓인 캐시가 버려진다
- **WMS 1.3.0 의 4326 은 위도가 먼저다.** OpenLayers 가 BBOX 를 남,서,북,동 으로 적는다. 열쇠는 그 글자 그대로라
  `Grid.bbox_text` 가 같은 차례로 적는다. 큰 그림(`--meta`)의 BBOX 도 같은 길을 탄다 — 문(`igme._wms`)이 1.1.1 로 옮기며 다시 뒤집는다

3575 의 타일 고르기는 `crs.latlon_to_laea_north`(중앙 경선 10°)로 한다. proj4.js 와 오슬로에서 나노미터까지 같았다.

## 대조 — 브라우저가 부른 글자와

같은 판의 `vendor/ol.js` 를 node 로 돌려 `npolarSource` 와 같은 소스에서 타일 주소를 뽑았다(3575 여섯·4326 여덟).
BBOX 가 열네 개 모두 한 글자까지 같았다. 시험(`test_prewarm_europe`)은 그 주소 셋을 `/wms/` 에 그대로 보내 문이 받은 것이 캐시에
앉게 하고, prewarm 이 같은 줌·칸에서 지은 열쇠로 그것을 찾는다. 상류는 문을 갈아 끼워 타지 않는다.

## 화면이 그리지 않는 줌은 받지 않는다

BGS 1:5만은 화면 줌 13 부터, BRGM 스캔은 판마다 좁은 줌에서만 그린다(`minZoom`·`lastZoom`). 그 밖의 타일은 화면이 묻지 않으니
받아도 헛것이고, BGS 는 줌 13 밑에서 빈 그림을 준다. 512 px 격자의 줌은 화면 줌보다 하나 작고, 화면은 반 단계 넉넉히 보이며
(`makeLayer`), OpenLayers 는 가까운 줌을 고른다. 그래서 격자 줌으로 `처음 - 2` 부터 `마지막` 까지만 받는다. 한 단계 넉넉한 쪽으로
잡았다 — 모자라면 화면이 상류를 타지만 남으면 몇 장 더 받을 뿐이다.

## 하지 않은 것

- 실제로 받아 보지 않았다. 운영에서 prewarm 을 언제·어디를 돌릴지는 사람이 정한다(010). 셈만(`--dry-run`) 연구소 카탈로그로 돌렸다 —
  오슬로 둘레 NGU·GTK 줌 3–12 가 395 장, 런던 둘레 일곱 레이어 줌 8–14 가 394 장
- PGC 경사·등고선(`pgc`)도 `npolarSource` 를 타지만 이번 일에 없었다. 붙이려면 `PROJECTED` 에 넣으면 된다 — `_layer_extra` 가 투영
  (`spec["srs"]`)과 `minZoom` 을 이미 준다
