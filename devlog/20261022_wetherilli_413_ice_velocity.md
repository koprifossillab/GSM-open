# 남극·그린란드 빙하 속도 — NASA GIBS 의 MEaSUREs 를 레이어로

2026-10-22 · `feature/ice-velocity` · wetherilli

극지 자료 후보(docs/극지_자료_후보.md) 4 순위. 장보고 둘레의 빙하·그린란드 유출 빙하의 흐름을 지질도 위에 겹쳐 본다.

## 상류 (2026-10-22, Capabilities 한 번씩·타일 두세 장, `curl -A 'GSM/0.1'`)

| | 남극 | 그린란드 |
|---|---|---|
| GIBS 레이어 | `MEaSUREs_Ice_Velocity_Antarctica` (epsg3031) | `MEaSUREs_Ice_Velocity_Greenland` (epsg3413) |
| 원자료 | NSIDC-0484 v2 (Rignot·Mouginot·Scheuchl 2017), 1996–2016 InSAR 합성 | NSIDC-0478 v2 (Joughin 외 2015) |
| 시점(`Time`) | `1996-01-01` 하나 | 2000·2005·2006·2007·2008 겨울 다섯, 기본 `2008-12-01` |
| 격자 | `500m` — 줌 0–4, 512 px, 원점 (-4194304, 4194304). **Blue Marble 과 같은 격자** | 같다 |
| 꼴 | PNG(팔레트, 빈 곳 투명), CORS `*` | 같다 |
| 범례 | `legends/…_H.svg`·`_V.svg` (matplotlib 이 그린 색 막대, 0–5600 m/yr 로그) | 같다 |

## 조건 — 원문

- NASA Earthdata 자료 이용 지침(https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance):
  "NASA data are freely accessible", "While there are no restrictions on the use of these data", "data users are very strongly urged to cite the data used in their work products",
  "NASA material may not be used to suggest or imply endorsement by NASA"
- NSIDC 자료 쪽(NSIDC-0484·0478 v2): "As a condition of using these data, you must cite the use of this data set." —
  권하는 인용은 `Rignot, E., Mouginot, J. & Scheuchl, B. (2017). MEaSUREs InSAR-Based Antarctica Ice Velocity Map. (NSIDC-0484, Version 2). https://doi.org/10.5067/D7GK8F5J8M8R`,
  `Joughin, I., Smith, B., Howat, I. & Scambos, T. (2015). MEaSUREs Greenland Ice Sheet Velocity Map from InSAR Data. (NSIDC-0478, Version 2). https://doi.org/10.5067/OC7B04ZM9G6Q`.
  내려받기에는 Earthdata 로그인이 걸리지만 GIBS 타일은 열쇠가 없다

저장 금지·비상업 같은 것이 없다 — 묻지 않고 붙였다. 인용은 레이어의 출처 줄(attribution)에 DOI 링크로 단다.

## 왜 카탈로그 레이어 + `basemaps.py` 인가

- **배경이 아니라 레이어다.** 지질도 위에 겹치고, 켜고 끄고, 투명도를 잡고, 범례를 연다 — 그건 레이어 패널의 일이다.
  그래서 씨앗(`data/gibs_antarctica_layers.json`·`gibs_greenland_layers.json`, 상류 `gibs`)으로 둔다. 레이어명이 지역 하나에만 걸리므로
  지역마다 한 장이다(PGC 씨앗과 같은 꼴). 그린란드 것은 북극 묶음에도 그대로 선다
- **문은 새로 내지 않았다.** GIBS 는 이미 `basemaps.py` 가 문이다(wetherilli 184) — 같은 주인, 같은 격자, 같은 조건이다. 상류마다 문 하나라는
  규칙에도 맞는다. 다른 것은 PNG 라는 것, 경로에 시점이 든다는 것뿐이라 표 하나(`GIBS_OVERLAYS`)와 함수 몇을 더했다.
  우리 주소는 `gibs/<투영>/<GIBS 레이어>/z/y/x.png`(Blue Marble 의 `.jpeg` 와 갈린다)이고, 받는 레이어·시점은 표가 고른다 — 남의 서버를 아무렇게나 부르는 길이 되지 않게
- **서버가 받아 담는다.** Blue Marble 처럼 한 장에 1 초 남짓이고, 판이 굳은 자료(2017·2015 판)라 담아 둘 덕이 크다. 캐시 열쇠에 **시점을 넣었다** —
  표의 시점을 바꾸면(그린란드를 다른 겨울로) 옛 그림을 내지 않게
- **못 받은 칸은 투명하게 낸다**(`_open_basemap(..., overlay=True)`) — 배경은 "지도를 받지 못했다" 안내 타일이 맞지만, 겹쳐 그리는 레이어에서는
  그 그림이 아래 지질도를 가린다(판 세션 pan 의 리뷰). 담지 않으므로 다음에 다시 묻는다
- 화면은 Bedmap3 의 `esriGridSource` 를 고쳐 쓰지 않고 `gibsOverlaySource` 를 따로 두었다 — 투영(3031·3413)과 칸 크기(512)가 다르고,
  정적 판이면 `direct`(GIBS 주소)를 부른다. `verify_layers` 의 칸 고르기는 행의 `grid.tileSize` 를 읽게 했다(전에는 256 을 박아 두었다)

## 딱지

레이어 패널의 딱지는 `NASA`, 기관 이름은 "미국 항공우주국 GIBS" 다(`basemaps.REGISTRY`) — 원자료는 NSIDC 지만 받는 곳이 GIBS 다.

## 범례 — SVG 를 화면이 곧장

GIBS 의 가로 범례(`_H.svg`)를 `<img>` 로 띄운다. 행에 `legendImg` 를 실으면 지질도Navi 판의 범례 손(`geonaviLegend`)이 그대로 그린다.
SVG 안에 matplotlib 의 툴팁 스크립트가 있지만 `<img>` 에서는 돌지 않는다. **우리 서버로 옮겨 내지 않은 것은 그래서다** — 우리 출처에서
SVG 를 내면 "새 창에서 크게 본다" 로 열 때 남의 스크립트가 우리 출처에서 돈다. 범례 한 장은 상류를 거의 타지 않는다.
범례 글자(Ice Surface Velocity, m/yr)는 그림 안의 글자라 옮기지 않는다(CLAUDE.md "영어판").

연구소 망에서 헤드리스 크로미엄으로 보면 범례가 "받지 못했다" 로 뜬다 — TLS 가로채기(KOPRI SSL) 탓이고 같은 때 Esri 남극 위성도 같다.
인증서를 무시하고 다시 보니 403×60 으로 섰다.

## 누른 자리의 속도 — 하지 않았다

WMTS 라 `GetFeatureInfo` 가 없다. 색표(`colormaps/v1.3/…xml`)가 RGB → 값의 구간을 주므로 캐시에 담은 타일의 픽셀을 읽어 풀 수는 있다.
하지만 512 px·500 m 격자를 다시 읽는 값이라 원자료의 값과 다르고, 맡은 범위를 넘는다. 레이어는 `queryable: False` 다.
원 값이 필요해지면 NSIDC 의 격자(로그인 뒤)를 받아 굽는 길이 맞다.

## 정적 판 — 싣는다

NASA 자료라 쓰임에 제한이 없고 CORS `*` 다. Blue Marble 배경도 정적 판에서 GIBS 를 곧장 부른다. 그래서 `static_site.UPSTREAMS` 에 `gibs` 를 더했다 —
정적 판의 화면은 `row.direct` 를 부른다. `static_smoke.py` 는 판 세션이 굽을 때 본다(이번에 굽지 않았다).

## 버린 것

- 그린란드 시점 다섯을 고르게 하기(아라온 항적의 `periods` 꼴) — 겨울 다섯이 거의 같은 그림이고, 기본(2008–09)이 가장 넓게 덮는다
- 같은 Capabilities 의 `SCAR_Land_Water_Map`·`Coastlines` — 맡은 일이 아니다. 극지연구소 KPDC 기본도가 해안선을 이미 준다
