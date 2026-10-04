# 화성 — Trek 판의 극지 길과 누른 자리의 높이

2026-10-04 · `feature/mars-polar-values` · wetherilli

docs/새_일거리.md §16·§17. 화성 화면을 달 수준으로 맞추는 일이다. 달은 극 평면에서 Trek 판의 극지 짝을 받고(085),
켠 값 판의 값을 누른 자리에서 읽는다(103·150). 화성은 둘 다 "화성 세션이 볼 일" 로 남아 있었다.

## 1. 극지 짝 — 달의 길로는 하나뿐이다

달은 ArcGIS 서비스 목록에서 `_SP`·`_NP` 로 끝나는 이름을 모아 짝을 찾았다(085). 같은 틀을 화성에 돌렸더니:

- 화성은 서비스 뿌리가 `trekarcgis` 하나뿐이다. `trekarcgis2` 는 404 라 목록을 받다 멈췄다 — 404 뿌리는 건너뛰게 고쳤다
- 목록의 `_NP`·`_SP` 가운데 씨앗에 있는 판은 **MOLA 합본(ImageServer) 하나**였다(2026-10-04)

그래서 길을 둘 더 냈다(`trek._mars_twins`).

- **WMTS 짝은 `tiles/Mars/NP/<판>_np`** — 영상 배경의 극지 판(065)이 쓰는 꼴이다. 꼬리가 소문자라 서비스 목록으로는
  찾지 못한다. 극까지 닿는 WMTS 판(위도 60° 너머) 17 개를 남북 한 번씩, 1 초 간격으로 Capabilities 를 물었다.
  짝이 있는 것은 다섯이다: Viking 색 모자이크·MOLA–HRSC 색 음영·MOLA–HRSC 음영·MOLA 색 음영(남북 모두), 피닉스 HiRISE 모자이크(북극만).
  TES 광물 다섯·열관성·알베도·MSSS 지도·거칠기·MOLA 합본(WMTS)은 둘 다 404 였다. THEMIS 는 65° 에서 끝나 묻지 않았다
- **MapServer 판은 짝이 없어도 된다.** 우리 문이 화성 극 투영(극 반지름 구의 WKT, 065)으로 `export` 를 물으면 Trek 이 옮겨 그린다.
  SIM 3292 극 타일이 이미 쓰는 길이다. 빙하 닮은 지형·사구·함수 광물 셋을 남북 줌 0 으로 물어 다 그려지는 것을 보고,
  극까지 닿는 MapServer 판 13 개에 묻지 않고 그 판 자신의 서비스를 적었다(`kind: map`, `Self`)

씨앗에는 19 판 37 짝이 적혔다(WMTS 5 판·9 짝, 우리 문 14 판·28 짝).

**Capabilities 의 모서리를 믿지 않는다.** 화성 극지 판은 왼쪽 위를 ±1 821 000 m 로 적는다. 그러나 참은 ±1 809 300 m 이다
(065 가 export 와 대조해 정했다). 달의 `parse_polar_wmts` 는 모서리가 우리 격자와 다르면 버리므로, 화성은 모서리를 보지 않고
범위를 우리 격자 안으로 자른다. 줌 끝은 Capabilities 대로다 — Viking 5, 화면에 손으로 적어 둔 값과 같다.

화면(`mars.js`)에는 달의 `trekFlat` 을 옮겼다. 극 평면으로 넘어가면 짝이 있는 판은 짝을, 없는 판은 적도 판을 옮겨 그린다.
우리 문의 극 길(`trek/mars/map/<판>/p/…`)이 화성도 받게 열었다.

## 2. 누른 자리의 값 — 화성은 높이뿐이다

달의 값 판은 같은 이름의 ImageServer 에 `getSamples` 로 묻는다. 화성의 광물·열관성 판은 그 짝이 없다.

- TES 먼지·휘석·사장석·유리·점토·열관성은 `getLayerServices` 가 WMTS 하나만 준다(둘을 물어 보았다)
- 화성 `trekarcgis` 의 ImageServer 17 개는 표고(MOLA–HRSC 200 m·MOLA 합본·지역 1 m DEM)와 영상 모자이크뿐이다

**광물·원소·열관성의 값은 읽을 길이 없어 뺐다.** 대신 높이를 그린 판을 켜면 누른 자리의 높이를 낸다(`trek.MARS_VALUES`).

| 판 | 읽는 곳 |
|---|---|
| MOLA–HRSC 색 음영·음영, MOLA 색 음영, MOLA 합본 | MOLA–HRSC 200 m DEM |
| 게일 HiRISE DEM 1 m | 그 DEM |
| 빅토리아 크레이터 HiRISE DEM 1 m | 그 DEM |

세 자리에서 값이 왔다 — 올림푸스 몬스 19 995 m, 게일 −4 502 m, 빅토리아 −1 429 m. 1 m DEM 은 판 밖을 물으면
200 에 "Invalid or missing input parameters" 를 실어 준다. 그것은 오류가 아니라 빈 값으로 다룬다. 끝점은 `mars/values/` 로,
`moon/values/` 와 한 몸(`_trek_values`)이다.

## 3. 확인

- 시험: 화성 Capabilities(±1 821 000)를 받아 범위를 자른다, 짝 후보(극에 닿는 판만, MapServer 는 묻지 않는다),
  우리 문이 화성 극 투영을 밝힌다, 표고 판의 값과 판 밖의 빈 값. 전체 시험 통과
- 브라우저: 화성 북극 평면(북위 80°)에서 MOLA–HRSC 색 음영이 `_np` 짝으로, 빙하 닮은 지형이 우리 문으로 섰다.
  누르니 "높이 −3 799 m · MOLA–HRSC 200 m" 가 떴다. 이 서버의 브라우저는 연구소 망의 TLS 가로채기로 Trek 에 곧장 닿지 못한다
  — 확인할 때만 HTTPS 오류를 무시했다

## 4. 수성에 옮길 것 — 적어만 둔다

- **MapServer 판을 극 투영으로 굽기** — 수성 씨앗에는 MapServer 판이 없다(2026-10-04). 생기면 같은 수가 된다.
  다만 수성 극 평면(`IAU_2015:19930`·`19935`)의 격자를 우리가 정해야 한다 — 지금은 경위도 타일을 옮겨 그린다(144)
- **WMTS 극지 짝** — 수성은 `tiles/Mercury/NP` 가 404 다(P10). 그대로 없다
- **높이 값** — 수성 MESSENGER 665 m DEM 은 ImageServer 가 있다(`trek.MERCURY_DEM`, 점묶음 표고가 이미 쓴다).
  색 음영·음영 판(`Mercury_Messenger_USGS_DEM_665m_v2_Hillshade*`·`ClrShade_Global_2km`)을 켜면 높이를 내는 일은 화성의
  `MARS_VALUES` 를 그대로 옮기면 된다. 지역 DEM(`MSGR_*_DEM_*`)도 ImageServer 가 있는지 물어 봐야 한다
