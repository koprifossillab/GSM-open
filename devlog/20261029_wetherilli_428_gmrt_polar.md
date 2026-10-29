# 428 — 극지 수심 GMRT (남극 3031·북극 3995)

2026-10-29 · `feature/gmrt-polar` · wetherilli (polar-a 세션)

아라온 해역(로스해·브랜스필드·척치해)의 고해상 수심 — 극지 자료 3 차 조사의 4 순위. 새 문 `gmrt.py`, 레이어군 "극지 수심 (GMRT)" 을
남극 탭과 북극해 탭(북극 묶음에 들고 스발바르 탭이 빌린다)에 둔다. 레이어마다 두 판 — 합성 지형(`gmrt:sp`·`np`)과
다중빔으로 잰 곳만 색인 판(`gmrt:sp_mask`·`np_mask`).

## 확인한 것 (2026-10-29)

- `wms_SP` 는 3031·4326, `wms_NP` 는 **3995 뿐**. `_mask` 두 서비스도 같은 꼴이고 레이어 이름(`South_Polar_Bathymetry`·`North_Polar_Bathymetry`)이 같다 —
  서비스(주소)가 판을 가른다
- 한 장(512 px)에 2.1–2.9 초. PNG 는 투명을 주지 않는다(바다·땅을 다 칠한다). `_mask` 는 잰 곳 밖을 회색으로 죽인다 — 투명이 아니다
- `queryable="0"`, `GetLegendGraphic` 은 빈 그림
- **`services/PointServer?latitude=&longitude=&format=json`** 이 `{"elevation": "-261"}` 을 준다 — 누른 자리는 이것으로
- 버전 4.5.0, 바탕은 GEBCO 2026. 조건은 CC BY 4.0, "not for navigation"(3 차 조사). CORS `*`

## 왜 이렇게

- **배경이 아니라 레이어로 두었다.** GEBCO·IBCSO 배경이 이미 있고, GMRT 는 그 위에서 "여기를 다중빔으로 쟀나" 를 보는 것이 쓰임이라
  투명도를 손으로 낮춰 겹치거나 잰 곳만 판을 켜는 것이 맞다. 누르면 수심이 뜨는 것도 레이어라서 된다
- 문은 EMODnet 의 꼴(`/GSM/wms/` 중계, 행의 `projection`, `doors.REGISTRY` 의 `relay`·`projected`)을 그대로 따랐다. 열쇠 없고 CORS 가 열렸지만
  한 장에 2 초 남짓이라 서버 캐시에 담는 덕이 크다
- **북극은 3995 로 받고 화면이 옮겨 그린다** — NGU 의 3575(wetherilli 140)와 같은 길. map.js 에 3995 를 알렸고, 범위를 3413 과 같게(±4194304) 두어
  격자 줌이 화면 줌과 맞는다. 3D(`globe`)는 켜지 않았다 — 3857 을 그려 주지 않는다
- **누른 자리** — 화면이 보내는 `GetFeatureInfo`(평면 범위·픽셀)를 위경도로 풀어 PointServer 에 한 점을 묻는다. 극 평사도법의 역변환은
  `gmrt.stereo_to_latlon` 에 손으로 썼다(Snyder 21-39, 기준 위도 축척 1) — pyproj 를 들이지 않는다. 세종·장보고·다산·척치해의 참값을 화면의
  proj4.js 로 내 맞췄다(소수 다섯째 자리). `crs.py` 에 두지 않은 것은 쓰는 곳이 이 문 하나라서다 — 다른 곳이 쓰게 되면 옮긴다
- 팝업에는 수심(바다일 때)·표고·위경도. 속성 캐시는 다른 상류처럼 담는다 — 같은 자리를 다시 누르면 상류를 타지 않는다
- "not for navigation" 은 출처 줄(`ATTRIBUTION`, 켠 레이어 밑에 늘 뜬다)에 넣었다. 범례 그림이 비어 있어 범례 자리는 `noLegend`
- 스발바르 탭이 빌린다(`borrow`) — 다산 기지 앞 콩스피오르의 다중빔이 GMRT 에 들었다. map3d.js 의 같은 표도 맞췄다(시험이 지킨다).
  그린란드·아이슬란드 탭은 빌리지 않았다 — 북극 묶음 탭에서 본다

## 버린 것

- 4326 판(`wms_SP` 가 준다) — 남극 탭은 3031 로 곧장 받는 것이 옳다
- 정적 판에 싣기 — CORS 가 열려 곧장 부를 수 있지만 한 장에 2 초라 보는 사람마다 상류를 친다. 이 일은 연구소 판만. 싣는다면
  `static-kinds.js` 에 WMS 꼴 하나와 3995 정의가 든다
- GMRT 의 GridServer(잘라 받기)로 굽기 — WMS 가 다중빔 원해상도까지 그려 주어 구울 까닭이 없다

## 운영에서 할 일

- 판을 붙인 뒤 컨테이너가 뜨며 `seed_catalog` 가 씨앗 둘을 넣는다
- 서버에서 닿는지 한 번 — `curl -s -A 'GSM/0.1' -o /dev/null -w '%{http_code}\n' 'https://www.gmrt.org/services/PointServer?latitude=-62.2&longitude=-58.8&format=json'`
- `manage.py verify_layers` 를 부르는 날에 GMRT 넷도 본다
